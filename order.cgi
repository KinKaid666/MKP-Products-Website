#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;
use MKPDatabase ;

use constant ORDER_PNL_SELECT_STATEMENT => qq(
    select date_format(so.posted_dt,"%Y") year
           ,date_format(so.posted_dt, "%m") month
           ,so.source_order_id
           ,so.sku
           ,count(distinct so.source_order_id      ) order_count
           ,sum(so.quantity                        ) unit_count
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) product_sales
           , sum(promotional_rebates                ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.event_type = 'Refund' and so.product_charges <> 0 then sc.cost*so.quantity*1
                     when so.event_type = 'Refund' and so.product_charges = 0 then 0
                     else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) +
                 sum(promotional_rebates                ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from financial_shipment_events so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date <= date(so.posted_dt)
       and (sc.end_date is null or
            sc.end_date >= date(so.posted_dt))
     where so.source_order_id = ?
    group by date_format(so.posted_dt,"%Y")
             ,date_format(so.posted_dt,"%m")
             ,sku
    order by date_format(so.posted_dt,"%Y")
             ,date_format(so.posted_dt,"%m")
             ,sku
) ;

use constant ORDER_DETAILS_SELECT_STATEMENT => qq(
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
     where so.source_order_id = ?
     order by so.posted_dt
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $order = $cgi->param('SOURCE_ORDER_ID') ;
print $cgi->header;
print $cgi->start_html( -title => "MKP Products Order Details",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ; 
print "&nbsp&nbsp" ;
print $cgi->a( { -href => "https://sellercentral.amazon.com/orders-v3/order/$order" }, "Amazon Link: $order" ) ; 
print $cgi->br() ;
print $cgi->br() ;

my $pnl_sth = $mkpDBro->prepare(${\ORDER_PNL_SELECT_STATEMENT}) ;
$pnl_sth->execute($order) or die $DBI::errstr ;

print "<TABLE><TR>"                  .
      "<TH>Year</TH>"                .
      "<TH>Month</TH>"               .
      "<TH>Source Order Id</TH>"     .
      "<TH>SKU</TH>"                 .
      "<TH>Order Count</TH>"         .
      "<TH>Unit Count</TH>"          .
      "<TH>Sales</TH>"               .
      "<TH>Selling Fees</TH>"        .
      "<TH>FBA Fees</TH>"            .
      "<TH>Cogs</TH>"                .
      "<TH>Contribution Margin</TH>" .
      "</TR> \n" ;
while (my $ref = $pnl_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{year}</TD>" ;
    print "<TD class=string>$ref->{month}</TD>" ;
    print "<TD class=string><a href=https://sellercentral.amazon.com/hz/orders/details?_encoding=UTF8&orderId=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count}) . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})   . ">" . &format_currency($ref->{product_sales},2)  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})    . ">" . &format_currency($ref->{selling_fees},2)   . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})        . ">" . &format_currency($ref->{fba_fees},2)       . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})            . ">" . &format_currency($ref->{cogs},2)           . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})  . ">" . &format_currency($ref->{contrib_margin},2) . "</TD>" ;
    print "</TR>" ;
}
print "</TABLE>\n" ;
$pnl_sth->finish() ;

print "<BR><BR>" ;
my $s_sth = $mkpDBro->prepare(${\ORDER_DETAILS_SELECT_STATEMENT}) ;
$s_sth->execute($order) or die $DBI::errstr ;

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
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>" . &format_date($ref->{posted_dt}) . "</TD>" ;
    print "<TD class=string><a href=https://sellercentral.amazon.com/hz/orders/details?_encoding=UTF8&orderId=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
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
    print "</TR>" ;
}
$mkpDBro->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

