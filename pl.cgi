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

use constant WEEKLY_PNL_SELECT_STATEMENT => qq(
    select sku_activity_by_week.year
           ,sku_activity_by_week.week
           , order_count
           , unit_count
           , product_sales
           , (promotional_rebates + marketplace_facilitator_tax + other_fees + selling_fees) selling_fees
           , fba_fees
           , cogs
           , ifnull(sga_by_week.expenses,0) + ifnull(expenses_by_week.expenses,0) expenses
           , (product_sales + promotional_rebates + marketplace_facilitator_tax + other_fees + selling_fees + fba_fees + cogs + ifnull(expenses_by_week.expenses,0) + ifnull(sga_by_week.expenses,0) ) net_income
      from ( select date_format(so.posted_dt,"%X") year
                    ,date_format(so.posted_dt, "%V") week
                    ,count(distinct so.source_order_id      ) order_count
                    ,sum(so.quantity                        ) unit_count
                    ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
                    ,sum(so.promotional_rebates             ) promotional_rebates
                    ,sum(so.marketplace_facilitator_tax     ) marketplace_facilitator_tax
                    ,sum(so.other_fees                      ) other_fees
                    ,sum(so.selling_fees                    ) selling_fees
                    ,sum(so.fba_fees                        ) fba_fees
                    ,sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
               from financial_shipment_events so
               join sku_costs sc
                 on so.sku = sc.sku
                and sc.start_date < so.posted_dt
                and (sc.end_date is null or
                     sc.end_date >= so.posted_dt)
             group by date_format(so.posted_dt,"%X")
                      ,date_format(so.posted_dt,"%V")
      ) as sku_activity_by_week
      left outer join ( select date_format(e.expense_dt,"%X") year
                    ,date_format(e.expense_dt,"%V") week
                    ,sum(e.total) expenses
               from financial_expense_events e
             group by date_format(e.expense_dt,"%X")
                      ,date_format(e.expense_dt,"%V")
           ) expenses_by_week
        on sku_activity_by_week.year = expenses_by_week.year
       and sku_activity_by_week.week = expenses_by_week.week
      left outer join ( select date_format(e.expense_datetime,"%X") year
                    ,date_format(e.expense_datetime,"%V") week
                    ,sum(e.total) expenses
               from expenses e
             group by date_format(e.expense_datetime,"%X")
                      ,date_format(e.expense_datetime,"%V")
           ) sga_by_week
        on sku_activity_by_week.year = sga_by_week.year
       and sku_activity_by_week.week = sga_by_week.week
     order by year, week
) ;

use constant MONTHLY_PNL_SELECT_STATEMENT => qq(
    select sku_activity_by_month.year
           ,sku_activity_by_month.month
           , order_count
           , unit_count
           , product_sales
           , (promotional_rebates + marketplace_facilitator_tax + other_fees + selling_fees) selling_fees
           , fba_fees
           , cogs 
           , ifnull(sga_by_month.expenses,0) + ifnull(expenses_by_month.expenses,0) expenses
           , (product_sales + promotional_rebates + marketplace_facilitator_tax + other_fees + selling_fees + fba_fees + cogs + ifnull(expenses_by_month.expenses,0) + ifnull(sga_by_month.expenses,0) ) net_income
      from ( select date_format(so.posted_dt,"%Y") year
                    ,date_format(so.posted_dt, "%m") month
                    ,count(distinct so.source_order_id      ) order_count
                    ,sum(so.quantity                        ) unit_count
                    ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
                    ,sum(promotional_rebates                ) promotional_rebates
                    ,sum(marketplace_facilitator_tax        ) marketplace_facilitator_tax
                    ,sum(so.other_fees                      ) other_fees
                    ,sum(so.selling_fees                    ) selling_fees
                    ,sum(so.fba_fees                        ) fba_fees
                    ,sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
               from financial_shipment_events so
               join sku_costs sc
                 on so.sku = sc.sku
                and sc.start_date < so.posted_dt
                and (sc.end_date is null or
                     sc.end_date >= so.posted_dt)
             group by date_format(so.posted_dt,"%Y")
                      ,date_format(so.posted_dt,"%m")
      ) as sku_activity_by_month
      left outer join ( select date_format(e.expense_dt,"%Y") year
                    ,date_format(e.expense_dt,"%m") month
                    ,sum(e.total) expenses
               from financial_expense_events e
             group by date_format(e.expense_dt,"%Y")
                      ,date_format(e.expense_dt,"%m")
           ) expenses_by_month
        on sku_activity_by_month.year = expenses_by_month.year
       and sku_activity_by_month.month = expenses_by_month.month
      left outer join ( select date_format(e.expense_datetime,"%Y") year
                    ,date_format(e.expense_datetime,"%m") month
                    ,sum(e.total) expenses
               from expenses e
             group by date_format(e.expense_datetime,"%Y")
                      ,date_format(e.expense_datetime,"%m")
           ) sga_by_month
        on sku_activity_by_month.year = sga_by_month.year
       and sku_activity_by_month.month = sga_by_month.month
     order by year, month
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $option = $cgi->param('granularity') || "MONTHLY" ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products P&L",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ; 
print $cgi->br() ;
print $cgi->br() ;

my $s_sth ;

if( $option eq "WEEKLY" )
{

    $s_sth = $mkpDBro->prepare(${\WEEKLY_PNL_SELECT_STATEMENT}) ;
}
else
{
    $s_sth = $mkpDBro->prepare(${\MONTHLY_PNL_SELECT_STATEMENT}) ;
}
$s_sth->execute() or die $DBI::errstr ;
print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;
print "<TABLE id=\"downloadabletable\"><TR>"           .
      "<TH>Year</TH>"         .
      "<TH>" . ($option eq 'WEEKLY' ? "Week" : "Month") . "</TH>" .
      "<TH>Orders</TH>"       .
      "<TH>Units</TH>"        .
      "<TH>Sales</TH>"        .
      "<TH>/ unit</TH>"       .
      "<TH>Selling Fees</TH>" .
      "<TH>/ unit</TH>"       .
      "<TH>%</TH>"            .
      "<TH>FBA Fees</TH>"     .
      "<TH>/ unit</TH>"       .
      "<TH>%</TH>"            .
      "<TH>COGS</TH>"         .
      "<TH>/ unit</TH>"       .
      "<TH>%</TH>"            .
      "<TH>Expenses</TH>"     .
      "<TH>/ Unit</TH>"       .
      "<TH>%</TH>"            .
      "<TH>Net Income</TH>"   .
      "<TH>/ unit</TH>"       .
      "<TH>%</TH>"            .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=number>$ref->{year}</TD>\n" ;
    print "<TD class=number>" . ($option eq "WEEKLY" ? $ref->{week} : $ref->{month}) . "</TD>\n" ;
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
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . "<a href=expenses.cgi?YEAR=$ref->{year}\&" . ($option eq "WEEKLY" ? "WEEK=$ref->{week}" : "MONTH=$ref->{month}") . ">" . &format_currency($ref->{expenses}) . "</a></TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . &format_currency($ref->{expenses}/$ref->{unit_count},2)       . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses})      . ">" . &format_percent($ref->{expenses}/$ref->{product_sales},1)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_currency($ref->{net_income})                          . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_currency($ref->{net_income}/$ref->{unit_count},2)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{net_income})    . ">" . &format_percent($ref->{net_income}/$ref->{product_sales},1)   . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
print q(
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
) ;

$s_sth->finish() ;
$mkpDBro->disconnect() ;

# TODO: put in library
sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}
