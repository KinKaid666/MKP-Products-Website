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
    select date_format(so.order_datetime,"%Y") year
           ,date_format(so.order_datetime, "%m") month
           ,so.sku
           ,count(distinct so.source_order_id      ) order_count
           ,sum(so.quantity                        ) unit_count
           ,sum(so.product_sales                   ) product_sales
           , sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_sales                   ) +
                 sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from sku_orders so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.order_datetime
       and (sc.end_date is null or
            sc.end_date > so.order_datetime)
     where so.sku = ?
    group by date_format(so.order_datetime,"%Y")
             ,date_format(so.order_datetime,"%m")
             ,sku
    order by date_format(so.order_datetime,"%Y")
             ,date_format(so.order_datetime,"%m")
             ,sku
) ;

use constant SKU_OHI_SELECT_STATEMENT => qq(
    select min(order_datetime) oldest_order
           ,so.sku
           ,ifnull(last_onhand_inventory_report.source_name, "N/A") source_name
           ,ifnull(last_onhand_inventory_report.condition_name, "N/A") condition_name
           ,ifnull(last_onhand_inventory_report.quantity, 0) quantity
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(order_datetime)) > ? then ? else datediff(NOW(),min(order_datetime)) end)/ 7) weekly_velocity
           ,ifnull(last_onhand_inventory_report.quantity, 0) /
                (sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                     ((case when datediff(NOW(),min(order_datetime)) > ? then ? else datediff(NOW(),min(order_datetime)) end)/7)) woc
           ,sum(so.product_sales                   ) product_sales
           ,sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_sales                   ) +
                 sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from sku_orders so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.order_datetime
       and (sc.end_date is null or
            sc.end_date > so.order_datetime)
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
     where so.order_datetime > NOW() - INTERVAL ? DAY
       and so.sku = ?
     group by sku
              ,last_onhand_inventory_report.source_name
              ,last_onhand_inventory_report.condition_name
              ,last_onhand_inventory_report.quantity
     order by contrib_margin
) ;

use constant SKU_ORDER_DETAILS_SELECT_STATEMENT => qq(
    select so.order_datetime
           ,so.sku
           ,so.source_order_id
           ,so.type
           ,so.quantity
           ,so.product_sales
           ,so.shipping_credits
           ,so.gift_wrap_credits
           ,so.promotional_rebates
           ,so.sales_tax_collected
           ,so.marketplace_facilitator_tax
           ,so.transaction_fees
           ,so.other
           ,so.selling_fees
           ,so.fba_fees
      from sku_orders so
     where so.sku = ?
     order by so.order_datetime
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
    print "<TD class=string>$ref->{vendor_description}</TD>" ;
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
print "<TABLE><TR>"           .
      "<TH>Order Datetime</TH>"         .
      "<TH>SKU</TH>"        .
      "<TH>Source Order Id</TH>"  .
      "<TH>Type</TH>"  .
      "<TH>Quantity</TH>"  .
      "<TH>Sales</TH>"        .
      "<TH>Shipping Credits</TH>" .
      "<TH>Gift Wrap Credits</TH>" .
      "<TH>Promotional Rebates</TH>" .
      "<TH>Sales Tax Collected</TH>" .
      "<TH>Markplace Facilitator Tax</TH>" .
      "<TH>Transaciton Fees</TH>" .
      "<TH>Other</TH>" .
      "<TH>Selling Fees</TH>" .
      "<TH>FBA Fees</TH>"     .
      "</TR> \n" ;
my $s_sth = $dbh->prepare(${\SKU_ORDER_DETAILS_SELECT_STATEMENT}) ;
$s_sth->execute($sku) or die $DBI::errstr ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{order_datetime}</TD>" ;
    print "<TD class=string><a href=https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string><a href=order.cgi?SOURCE_ORDER_ID=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
    print "<TD class=string>$ref->{type}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})                 . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})               . ">" . &format_currency($ref->{product_sales},2)               . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{shipping_credits})            . ">" . &format_currency($ref->{shipping_credits},2)            . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{gift_wrap_credits})           . ">" . &format_currency($ref->{gift_wrap_credits},2)           . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{promotional_rebates})         . ">" . &format_currency($ref->{promotional_rebates},2)         . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{sales_tax_collected})         . ">" . &format_currency($ref->{sales_tax_collected},2)         . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{marketplace_facilitator_tax}) . ">" . &format_currency($ref->{marketplace_facilitator_tax},2) . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{transaction_fees})            . ">" . &format_currency($ref->{transaction_fees},2)            . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{other})                       . ">" . &format_currency($ref->{other},2)                       . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})                . ">" . &format_currency($ref->{selling_fees},2)                . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})                    . ">" . &format_currency($ref->{fba_fees},2)                    . "</TD>" ;
    print "</TR>\n" ;
}
$dbh->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}
