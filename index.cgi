#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(warningsToBrowser fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

use constant TRAILING_DAY_SALES => qq(
select a.posted_dt date
       , sum(sales)    sales
       , sum(fees)     fees
       , sum(ifnull(expenses,0)) expenses
       , sum(cogs) cogs
       , sum(sales) + sum(fees) + sum(cogs) + sum(ifnull(expenses,0)) total
  from (
      select date_format(posted_dt, "%Y-%m-%d") posted_dt
             , sum(product_charges + shipping_charges + giftwrap_charges) sales
             , sum(product_charges_tax + shipping_charges_tax + giftwrap_charges_tax + marketplace_facilitator_tax) taxes
             , sum(promotional_rebates + selling_fees + fba_fees + other_fees) fees
             , sum(case when fse.event_type = 'Refund' then sc.cost*fse.quantity*1 else sc.cost*fse.quantity*-1 end) cogs
        from financial_shipment_events fse
        join sku_costs sc
          on fse.sku = sc.sku
         and sc.start_date < fse.posted_dt
         and (sc.end_date is null or
              sc.end_date > fse.posted_dt)
       where posted_dt > DATE(NOW() - INTERVAL ? DAY)
       group by date_format(posted_dt, "%Y-%m-%d")
) a left outer join (
      select date_format(expense_dt, "%Y-%m-%d") posted_dt
             , sum(total) expenses
        from financial_expense_events fse
       where expense_dt > DATE(NOW() - INTERVAL ? DAY)
       group by date_format(expense_dt, "%Y-%m-%d")
       union all
      select date_format(expense_datetime, "%Y-%m-%d") posted_dt
             , sum(total) expenses
        from expenses fse
       where expense_datetime > DATE(NOW() - INTERVAL ? DAY)
       group by date_format(expense_datetime, "%Y-%m-%d")
) b on a.posted_dt = b.posted_dt
group by a.posted_dt
order by a.posted_dt desc
) ;

use constant LATEST_INVENTORY => qq(
    select date_format(max(report_date),"%Y-%m-%d") latest_report from onhand_inventory_reports
) ;

my $cgi = CGI->new() ;

my $username = &validate() ;
my $sku   = $cgi->param('sku') || undef ;
my $order = $cgi->param('order') || undef ;

print $cgi->redirect( -url=>"/sku.cgi?SKU=$sku")                 if( defined $sku   ) ;
print $cgi->redirect( -url=>"/order.cgi?SOURCE_ORDER_ID=$order") if( defined $order ) ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Homepage", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );

my $dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                       "mkp_reporter",
                       "mkp_reporter_2018",
                       {'RaiseError' => 1});

{
    my $latest_sth = $dbh->prepare(${\LATEST_INVENTORY}) ;
    $latest_sth->execute() or die $DBI::errstr ;
    my $row = $latest_sth->fetchrow_hashref() ;

    print $cgi->i($cgi->b("Latest ")) ;
    print $cgi->i($cgi->b(" inventory: ") . $row->{latest_report}) ;
}

my $s_sth = $dbh->prepare(${\TRAILING_DAY_SALES}) ;
my $days = 7 ;
$s_sth->execute($days, $days, $days) or die $DBI::errstr ;

print $cgi->h3("Trailing $days Sales Flash") ;
print "<TABLE><TR>"       .
      "<TH>Date</TH>"     .
      "<TH>Sales</TH>"    .
      "<TH>Fees</TH>"     .
      "<TH>COGS</TH>"     .
      "<TH>Expenses</TH>" .
      "<TH>Total</TH>"    .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=string>$ref->{date} </TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sales})    . ">" . &format_currency($ref->{sales},2)    . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{fees})     . ">" . &format_currency($ref->{fees},2)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})     . ">" . &format_currency($ref->{cogs},2)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses}) . ">" . &format_currency($ref->{expenses},2) . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{total})    . ">" . &format_currency($ref->{total},2)    . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE><br><br>\n" ;
$s_sth->finish() ;

print $cgi->a({href => "/pl.cgi"}, "Profit and Loss Statement") ; print " " ;
print $cgi->a({href => "/pl.cgi?granularity=WEEKLY"}, "(weekly)") ;
print $cgi->br() ;
print $cgi->a({href => "/skupl.cgi"}, "SKU Performance" ) ;
print $cgi->br() ;
print $cgi->a({href => "/newbuy.cgi"}, "SKU Buying" ) ;
print $cgi->br() ;
print $cgi->a({href => "/feg.cgi"}, "Financial Event Groups" ) ;
print $cgi->br() ;
print $cgi->br() ;

print $cgi->start_form(
    -name    => 'main_form',
    -method  => 'POST',
);
print $cgi->start_table ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "SKU Lookup:"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'sku',
                                      -value     => $sku,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Order Lookup:"),
            $cgi->td({ -class => "string" },
                     $cgi->textfield( -name      => 'order',
                                      -value     => $order,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->end_table() ;
print $cgi->submit( -name     => 'submit_form',
                    -value    => 'Submit') ;
print $cgi->end_form() ;
print $cgi->end_html() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

