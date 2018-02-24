#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

use constant SKU_DETAILS_SELECT_STATEMENT => qq(
    select s.sku
           ,s.description
           ,v.vendor_name
           ,v.description vendor_description
      from skus s
      join vendors v
        on s.vendor_name = v.vendor_name
     where s.sku = ?
) ;

use constant SKU_COST_DETAILS_SELECT_STATEMENT => qq(
    select sc.sku
           ,sc.cost
           ,sc.start_date
           ,sc.end_date
      from sku_costs sc
     where sc.sku = ?
     order by sc.start_date
) ;

use constant SKU_PNL_SELECT_STATEMENT => qq(
    select date_format(so.posted_dt,"%Y") year
           ,date_format(so.posted_dt, "%m") month
           ,so.sku
           ,count(distinct so.source_order_id      ) order_count
           ,sum(so.quantity                        ) unit_count
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
           , sum(promotional_rebates                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) +
                 sum(promotional_rebates                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from financial_shipment_events so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.posted_dt
       and (sc.end_date is null or
            sc.end_date > so.posted_dt)
     where so.sku = ?
    group by date_format(so.posted_dt,"%Y")
             ,date_format(so.posted_dt,"%m")
             ,sku
    order by date_format(so.posted_dt,"%Y")
             ,date_format(so.posted_dt,"%m")
             ,sku
) ;

use constant SKU_OHI_SELECT_STATEMENT => qq(
    select min(posted_dt) oldest_order
           ,so.sku
           ,ifnull(last_onhand_inventory_report.source_name, "N/A") source_name
           ,ifnull(last_onhand_inventory_report.condition_name, "N/A") condition_name
           ,ifnull(last_onhand_inventory_report.quantity, 0) quantity
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
           ,ifnull(last_onhand_inventory_report.quantity, 0) /
                (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                     ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
           , sum(promotional_rebates                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from financial_shipment_events so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.posted_dt
       and (sc.end_date is null or
            sc.end_date > so.posted_dt)
      left outer join (
            select ohi.sku
                   ,ohi.report_date
                   ,ohi.source_name
                   ,ohi.condition_name
                   ,ohi.quantity
              from onhand_inventory_reports ohi
             where report_date = ( select max(report_date) from onhand_inventory_reports )
          ) last_onhand_inventory_report
        on last_onhand_inventory_report.sku = so.sku
     where so.posted_dt > NOW() - INTERVAL ? DAY
       and so.sku = ?
     group by sku
              ,last_onhand_inventory_report.source_name
              ,last_onhand_inventory_report.condition_name
              ,last_onhand_inventory_report.quantity
     order by contrib_margin
) ;

use constant SKU_ORDER_DETAILS_SELECT_STATEMENT => qq(
    select so.posted_dt
           ,so.sku
           ,so.source_order_id
           ,so.event_type
           ,so.quantity
           ,so.product_charges
           ,so.product_charges_tax
           ,so.shipping_charges
           ,so.shipping_charges_tax
           ,so.giftwrap_charges
           ,so.giftwrap_charges_tax
           ,so.promotional_rebates
           ,so.marketplace_facilitator_tax
           ,so.other_fees
           ,so.selling_fees
           ,so.fba_fees
           ,so.total
      from financial_shipment_events so
     where so.sku = ?
     order by so.posted_dt
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $sku = $cgi->param('SKU') || 'MKP-F5117-4' ;
my $days = $cgi->param('days') || 90 ;
print $cgi->header;
print $cgi->start_html( -title => "MKP Products SKU Details", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );
my $dbh ;

$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

print "<h3>SKU</h3>\n" ;
print "<TABLE><TR>"          .
      "<TH>SKU</TH>"         .
      "<TH>Description</TH>" .
      "<TH>Vendor Name</TH>" .
      "<TH>Description</TH>" .
      "</TR> \n" ;
my $sku_details_sth = $dbh->prepare(${\SKU_DETAILS_SELECT_STATEMENT}) ;
$sku_details_sth->execute($sku) or die $DBI::errstr ;
while (my $ref = $sku_details_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string><a href=https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string>$ref->{description}</a></TD>" ;
    print "<TD class=string>$ref->{vendor_name}</TD>" ;
    print "<TD class=string>" . &nvl($ref->{vendor_description}) . "</TD>" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$sku_details_sth->finish() ;

print "<h3>Costs</h3>\n" ;
print "<TABLE><TR>"           .
      "<TH>SKU</TH>"         .
      "<TH>Cost</TH>"        .
      "<TH>Start Date</TH>"  .
      "<TH>End Date</TH>"  .
      "</TR> \n" ;
my $sku_cost_sth = $dbh->prepare(${\SKU_COST_DETAILS_SELECT_STATEMENT}) ;
$sku_cost_sth->execute($sku) or die $DBI::errstr ;
while (my $ref = $sku_cost_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string><a href=https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=number>" . &format_currency($ref->{cost},2) . "</TD>" ;
    print "<TD class=string>$ref->{start_date}</TD>" ;
    print "<TD class=string>" . (defined $ref->{end_date} ? $ref->{end_date} : "No end") . "</TD>" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$sku_cost_sth->finish() ;

my $ohi_sth = $dbh->prepare(${\SKU_OHI_SELECT_STATEMENT}) ;
$ohi_sth->execute($days, $days, $days, $days, $days, $sku) or die $DBI::errstr ;
print "<h3>Inventory</h3>\n" ;
print "<TABLE id=\"pnl\">"           .
      "<TBODY><TR>"                  .
      "<TH>Ordest Order</TH>"        .
      "<TH>SKU</TH>"                 .
      "<TH>Source of Inventory</TH>" .
      "<TH>Condition</TH>"           .
      "<TH>On Hand Quantity</TH>"    .
      "<TH>Order Count</TH>"         .
      "<TH>Unit Count</TH>"          .
      "<TH>Weekly Velocity</TH>"     .
      "<TH>Weeks of Coverage</TH>"   .
      "<TH>Sales</TH>"               .
      "<TH>Selling Fees</TH>"        .
      "<TH>FBA Fees</TH>"            .
      "<TH>Cogs</TH>"                .
      "<TH>Contribution Margin</TH>" .
      "</TR>\n" ;
while (my $ref = $ohi_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{oldest_order}</TD>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
    if(not $ref->{source_name} =~ m/www/)
    {
        print "<TD class=string>$ref->{source_name}</TD>" ;
    }
    else
    {
        print "<TD class=string><a href=http://$ref->{source_name}>$ref->{source_name}</a></TD>" ;
    }
    print "<TD class=string>$ref->{condition_name}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})                    . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count})                    . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})                     . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2)                     . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{woc},2)                     . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})  . ">" . &format_currency($ref->{product_sales})  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})   . ">" . &format_currency($ref->{selling_fees})   . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})       . ">" . &format_currency($ref->{fba_fees})       . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})           . ">" . &format_currency($ref->{cogs})           . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{contrib_margin}) . ">" . &format_currency($ref->{contrib_margin}) . "</TD>" ;
    print "</TR>\n" ;
}
print qq(</TBODY></TABLE>) ;
$ohi_sth->finish() ;

print "<h3>Monthly Contribution</h3>\n" ;
print "<TABLE><TR>"                  .
      "<TH>Year</TH>"                .
      "<TH>Month</TH>"               .
      "<TH>SKU</TH>"                 .
      "<TH>Order Count</TH>"         .
      "<TH>Unit Count</TH>"          .
      "<TH>Sales</TH>"               .
      "<TH>per Unit</TH>"            .
      "<TH>Selling Fees</TH>"        .
      "<TH>per Unit</TH>"            .
      "<TH>as Pct</TH>"              .
      "<TH>FBA Fees</TH>"            .
      "<TH>per Unit</TH>"            .
      "<TH>as Pct</TH>"              .
      "<TH>Cogs</TH>"                .
      "<TH>per Unit</TH>"            .
      "<TH>as Pct</TH>"              .
      "<TH>Contribution Margin</TH>" .
      "<TH>per Unit</TH>"            .
      "<TH>as Pct</TH>"              .
      "</TR> \n" ;
my $pnl_sth = $dbh->prepare(${\SKU_PNL_SELECT_STATEMENT}) ;
$pnl_sth->execute($sku) or die $DBI::errstr ;
while (my $ref = $pnl_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{year}</TD>" ;
    print "<TD class=string>$ref->{month}</TD>" ;
    print "<TD class=string><a href=https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count})     . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})      . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})       . ">" . &format_currency($ref->{product_sales})    . "</TD>\n" ;
    if($ref->{product_sales} == 0 or $ref->{unit_count} == 0)
    {
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees})   . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees})       . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs})           . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin}) . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
    }
    else
    {
        print "<TD class=number" . &add_neg_tag($ref->{product_sales})     . ">" . &format_currency($ref->{product_sales}/$ref->{unit_count},2)      . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees})                            . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees}/$ref->{unit_count},2)       . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_percent($ref->{selling_fees}/$ref->{product_sales},1)     . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees})                                . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees}/$ref->{unit_count},2)           . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_percent($ref->{fba_fees}/$ref->{product_sales},1)         . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs})                                    . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs}/$ref->{unit_count},2)               . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_percent($ref->{cogs}/$ref->{product_sales},1)             . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin})                          . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin}/$ref->{unit_count},2)     . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_percent($ref->{contrib_margin}/$ref->{product_sales},1)   . "</TD>\n" ;
    }

}
print "</TABLE>\n" ;
$pnl_sth->finish() ;

print "<h3>Order Details</h3>\n" ;
print "<TABLE><TR>"                        .
      "<TH>Posted Datetime</TH>"           .
      "<TH>SKU</TH>"                       .
      "<TH>Source Order Id</TH>"           .
      "<TH>Type</TH>"                      .
      "<TH>Quantity</TH>"                  .
      "<TH>Product Charges</TH>"           .
      "<TH>Product Charges Tax</TH>"       .
      "<TH>Shipping Charges</TH>"          .
      "<TH>Shipping Charges Tax</TH>"      .
      "<TH>Giftwrap Charges</TH>"          .
      "<TH>Giftwrap Charges Tax</TH>"      .
      "<TH>Promotional Rebates</TH>"       .
      "<TH>Markplace Facilitator Tax</TH>" .
      "<TH>Other Fees</TH>"                .
      "<TH>Selling Fees</TH>"              .
      "<TH>FBA Fees</TH>"                  .
      "<TH>Total</TH>"                     .
      "</TR> \n" ;
my $s_sth = $dbh->prepare(${\SKU_ORDER_DETAILS_SELECT_STATEMENT}) ;
$s_sth->execute($sku) or die $DBI::errstr ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{posted_dt}</TD>" ;
    print "<TD class=string><a href=https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string><a href=order.cgi?SOURCE_ORDER_ID=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
    print "<TD class=string>$ref->{event_type}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})                . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_charges})             . ">" . &format_currency($ref->{product_charges},2)             . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_charges_tax})         . ">" . &format_currency($ref->{product_charges_tax},2)         . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{shipping_charges})            . ">" . &format_currency($ref->{shipping_charges},2)            . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{shipping_charges_tax})        . ">" . &format_currency($ref->{shipping_charges_tax},2)        . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{giftwrap_charges})            . ">" . &format_currency($ref->{giftwrap_charges},2)            . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{giftwrap_charges_tax})        . ">" . &format_currency($ref->{giftwrap_charges_tax},2)        . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{promotional_rebates})         . ">" . &format_currency($ref->{promotional_rebates},2)         . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{marketplace_facilitator_tax}) . ">" . &format_currency($ref->{marketplace_facilitator_tax},2) . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{other_fees})                  . ">" . &format_currency($ref->{other_fees},2)                  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})                . ">" . &format_currency($ref->{selling_fees},2)                . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})                    . ">" . &format_currency($ref->{fba_fees},2)                    . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{total})                       . ">" . &format_currency($ref->{total},2)                       . "</TD>" ;
    print "</TR>\n" ;
}
$dbh->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}
