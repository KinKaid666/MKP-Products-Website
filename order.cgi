#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;

use constant ORDER_PNL_SELECT_STATEMENT => qq(
    select date_format(so.order_datetime,"%Y") year
           ,date_format(so.order_datetime, "%m") month
           ,so.source_order_id
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
     where so.source_order_id = ?
    group by date_format(so.order_datetime,"%Y")
             ,date_format(so.order_datetime,"%m")
             ,sku
    order by date_format(so.order_datetime,"%Y")
             ,date_format(so.order_datetime,"%m")
             ,sku
) ;

use constant ORDER_DETAILS_SELECT_STATEMENT => qq(
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
     where so.source_order_id = ?
     order by so.order_datetime
) ;

my $cgi = CGI->new() ;
my $sku = $cgi->param('SOURCE_ORDER_ID') ;
my $dbh ;

$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "ericferg_ro",
                    "ericferg_ro_2018",
                    {'RaiseError' => 1});

my $pnl_sth = $dbh->prepare(${\ORDER_PNL_SELECT_STATEMENT}) ;
$pnl_sth->execute($sku) or die $DBI::errstr ;
print "Content-type: text/html\n\n";
print "<head><style>
table, th, tr, td {border:1px solid black; white-space:nowrap}

tr:nth-child(odd)   {background-color:#f1f1f1;}
tr:nth-child(even)  {background-color:#ffffff;}

td.string {text-align:left; }
td.number {text-align:right; }
td.number-neg {text-align:right; color:#FF0000;}

#green { background-color:#00FF00; }
#amber { background-color:#ffff00; }
#red   { background-color:#ff3300; }
pre { display: block; font-family: monospace; }
</head></style>
" ;

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
    print "<TD class=string><a href=order.cgi?SOURCE_ORDER_ID=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
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
my $s_sth = $dbh->prepare(${\ORDER_DETAILS_SELECT_STATEMENT}) ;
$s_sth->execute($sku) or die $DBI::errstr ;

print "<TABLE><TR>"           .
      "<TH>Order Datetime</TH>"         .
      "<TH>Source Order Id</TH>"  .
      "<TH>SKU</TH>"        .
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
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{order_datetime}</TD>" ;
    print "<TD class=string><a href=order.cgi?SOURCE_ORDER_ID=$ref->{source_order_id}>$ref->{source_order_id}</a></TD>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string>$ref->{type}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})                . "</TD>" ;
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
    print "</TR>" ;
}
$dbh->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

