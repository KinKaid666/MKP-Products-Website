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

use constant MONTHLY_PNL_SELECT_STATEMENT => qq(
    select sku_activity_by_month.year
           ,sku_activity_by_month.month
           , order_count
           , unit_count
           , product_sales
           , (shipping_credits + gift_wrap_credits + promotional_rebates + sales_tax_collected + marketplace_facilitator_tax + transaction_fees + other + selling_fees) selling_fees
           , fba_fees
           , cogs , ifnull(expenses_by_month.expenses,0) expenses
           , ifnull(sga_by_month.expenses,0) sga
           , (product_sales + shipping_credits + gift_wrap_credits + promotional_rebates + sales_tax_collected + marketplace_facilitator_tax + transaction_fees + other + selling_fees + fba_fees + cogs + ifnull(expenses_by_month.expenses,0) + ifnull(sga_by_month.expenses,0) ) net_income
      from ( select date_format(so.order_datetime,"%Y") year
                    ,date_format(so.order_datetime, "%m") month
                    ,count(distinct so.source_order_id      ) order_count
                    ,sum(so.quantity                        ) unit_count
                    ,sum(so.product_sales                   ) product_sales
                    ,sum(shipping_credits                   ) shipping_credits
                    ,sum(gift_wrap_credits                  ) gift_wrap_credits
                    ,sum(promotional_rebates                ) promotional_rebates
                    ,sum(sales_tax_collected                ) sales_tax_collected
                    ,sum(marketplace_facilitator_tax        ) marketplace_facilitator_tax
                    ,sum(transaction_fees                   ) transaction_fees
                    ,sum(other                              ) other
                    ,sum(so.selling_fees                    ) selling_fees
                    ,sum(so.fba_fees                        ) fba_fees
                    ,sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
               from sku_orders so
               join sku_costs sc
                 on so.sku = sc.sku
                and sc.start_date < so.order_datetime
                and (sc.end_date is null or
                     sc.end_date > so.order_datetime)
             group by date_format(so.order_datetime,"%Y")
                      ,date_format(so.order_datetime,"%m")
      ) as sku_activity_by_month
      left outer join ( select date_format(e.expense_datetime,"%Y") year
                    ,date_format(e.expense_datetime,"%m") month
                    ,sum(e.total) expenses
               from expenses e
              where type <> "Salary"
                and type <> "Rent"
             group by date_format(e.expense_datetime,"%Y")
                      ,date_format(e.expense_datetime,"%m")
           ) expenses_by_month
        on sku_activity_by_month.year = expenses_by_month.year
       and sku_activity_by_month.month = expenses_by_month.month
      left outer join ( select date_format(e.expense_datetime,"%Y") year
                    ,date_format(e.expense_datetime,"%m") month
                    ,sum(e.total) expenses
               from expenses e
              where type = "Salary"
                 or type = "Rent"
             group by date_format(e.expense_datetime,"%Y")
                      ,date_format(e.expense_datetime,"%m")
           ) sga_by_month
        on sku_activity_by_month.year = sga_by_month.year
       and sku_activity_by_month.month = sga_by_month.month
     order by year, month
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
print $cgi->header;
print $cgi->start_html( -title => "MKP Products P&L", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );

my $dbh ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

my $s_sth = $dbh->prepare(${\MONTHLY_PNL_SELECT_STATEMENT}) ;
$s_sth->execute() or die $DBI::errstr ;
print "<TABLE><TR>"           .
      "<TH>Year</TH>"         .
      "<TH>Month</TH>"        .
      "<TH>Order Count</TH>"  .
      "<TH>Unit Count</TH>"   .
      "<TH>Sales</TH>"        .
      "<TH>per Unit</TH>"     .
      "<TH>Selling Fees</TH>" .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "<TH>FBA Fees</TH>"     .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "<TH>Cogs</TH>"         .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "<TH>Expenses</TH>"     .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "<TH>SG&A</TH>"         .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "<TH>Net Income</TH>"   .
      "<TH>per Unit</TH>"     .
      "<TH>as Pct</TH>"       .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=string>$ref->{year}</TD>\n" ;
    print "<TD class=string>$ref->{month}</TD>\n" ;
    print "<TD class=number>" . &format_integer($ref->{order_count}) . "</TD>\n" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})  . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales}) . ">" . &format_currency($ref->{product_sales})                       . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales}) . ">" . &format_currency($ref->{product_sales}/$ref->{unit_count},2)  . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})  . ">" . &format_currency($ref->{selling_fees})                        . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})  . ">" . &format_currency($ref->{selling_fees}/$ref->{unit_count},2)   . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})  . ">" . &format_percent($ref->{selling_fees}/$ref->{product_sales},1) . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})      . ">" . &format_currency($ref->{fba_fees})                            . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})      . ">" . &format_currency($ref->{fba_fees}/$ref->{unit_count},2)       . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})      . ">" . &format_percent($ref->{fba_fees}/$ref->{product_sales},1)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})          . ">" . &format_currency($ref->{cogs})                                . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})          . ">" . &format_currency($ref->{cogs}/$ref->{unit_count},2)           . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})          . ">" . &format_percent($ref->{cogs}/$ref->{product_sales},1)         . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . "<a href=expenses.cgi?YEAR=$ref->{year}\&MONTH=$ref->{month}>" . &format_currency($ref->{expenses}) . "</a></TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . &format_currency($ref->{expenses}/$ref->{unit_count},2)       . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . &format_percent($ref->{expenses}/$ref->{product_sales},1)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sga})           . ">" . "<a href=expenses.cgi?YEAR=$ref->{year}\&MONTH=$ref->{month}>" . &format_currency($ref->{sga})      . "</a></TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sga})           . ">" . &format_currency($ref->{sga}/$ref->{unit_count},2)            . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sga})           . ">" . &format_percent($ref->{sga}/$ref->{product_sales},1)          . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_currency($ref->{net_income})                          . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_currency($ref->{net_income}/$ref->{unit_count},2)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_percent($ref->{net_income}/$ref->{product_sales},1)   . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$dbh->disconnect() ;

# TODO: put in library
sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}
