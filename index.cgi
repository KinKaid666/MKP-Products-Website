#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(warningsToBrowser fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;
use MKPDatabase ;

use constant TRAILING_DAY_SALES => qq(
select a.posted_dt date
       , sum(sales) sales
       , sum(sales) over (order by a.posted_dt asc rows 6 preceding ) as '7_day'
       , sum(sales) over (order by a.posted_dt asc rows 29 preceding ) as '30_day'
       , sum(fees) fees
       , sum(ifnull(expenses,0)) expenses
       , sum(cogs) cogs
       , sum(sales) + sum(fees) + sum(cogs) + sum(ifnull(expenses,0)) total
  from (
      select date_format(posted_dt, "%Y-%m-%d (%a)") posted_dt
             , sum(product_charges + shipping_charges + giftwrap_charges + product_charges_tax + shipping_charges_tax + giftwrap_charges_tax + marketplace_facilitator_tax) sales
             , sum(promotional_rebates + selling_fees + fba_fees + other_fees) fees
             , sum(case when fse.event_type = 'Refund' and fse.product_charges <> 0 then sc.cost*fse.quantity*1
                     when fse.event_type = 'Refund' and fse.product_charges = 0 then 0
                     else sc.cost*fse.quantity*-1 end) cogs
        from financial_shipment_events fse
        join sku_costs sc
          on fse.sku = sc.sku
         and sc.start_date < fse.posted_dt
         and (sc.end_date is null or
              sc.end_date > fse.posted_dt)
       where posted_dt >= DATE(NOW() - INTERVAL ? DAY)
       group by date_format(posted_dt, "%Y-%m-%d (%a)")
) a left outer join (
    select posted_dt, sum(expenses) expenses from (
      select date_format(expense_dt, "%Y-%m-%d (%a)") posted_dt
             , sum(total) expenses
        from financial_expense_events fse
       where expense_dt >= DATE(NOW() - INTERVAL ? DAY)
       group by date_format(expense_dt, "%Y-%m-%d (%a)")
       union all
      select date_format(expense_datetime, "%Y-%m-%d (%a)") posted_dt
             , sum(total) expenses
        from expenses fse
       where expense_datetime >= DATE(NOW() - INTERVAL ? DAY)
       group by date_format(expense_datetime, "%Y-%m-%d (%a)")
    ) c group by posted_dt
) b on a.posted_dt = b.posted_dt
group by a.posted_dt
order by a.posted_dt desc
) ;

use constant MTD_SALES => qq(
select a.mon
       , sum(sales)    sales
       , sum(fees)     fees
       , sum(ifnull(expenses,0)) expenses
       , sum(cogs) cogs
       , sum(sales) + sum(fees) + sum(cogs) + sum(ifnull(expenses,0)) total
  from (
      select 'A' mon
             , sum(product_charges + shipping_charges + giftwrap_charges + product_charges_tax + shipping_charges_tax + giftwrap_charges_tax + marketplace_facilitator_tax) sales
             , sum(promotional_rebates + selling_fees + fba_fees + other_fees) fees
             , sum(case when fse.event_type = 'Refund' and fse.product_charges <> 0 then sc.cost*fse.quantity*1
                     when fse.event_type = 'Refund' and fse.product_charges = 0 then 0
                     else sc.cost*fse.quantity*-1 end) cogs
        from financial_shipment_events fse
        join sku_costs sc
          on fse.sku = sc.sku
         and sc.start_date < fse.posted_dt
         and (sc.end_date is null or
              sc.end_date > fse.posted_dt)
       where posted_dt >= NOW() - INTERVAL ? DAY
) a left outer join (
    select mon,
           sum(expenses) expenses
    from (
     select mon, sum(expenses) expenses from (
      select 'A' mon
             , sum(total) expenses
        from financial_expense_events fse
       where expense_dt >= NOW() - INTERVAL ? DAY
       union all
      select 'A' mon
             , sum(total) expenses
        from expenses fse
       where expense_datetime >= NOW() - INTERVAL ? DAY
         and expense_datetime <= NOW() - INTERVAL 1 DAY
     ) c group by mon
    ) a group by a.mon
) b on a.mon = b.mon
group by a.mon
) ;

use constant TOTAL_INVENTORY_COST => qq(
    select sum(ri.quantity_instock * sc.cost) instock_cost
           ,sum(ri.quantity_total * sc.cost) total_cost
           ,sum(ri.quantity_instock) instock_units
           ,sum(ri.quantity_total) total_units
      from realtime_inventory ri
      join sku_costs sc
        on ri.sku = sc.sku
       and sc.start_date < now()
       and (sc.end_date is null or sc.end_date > now())
     where ri.quantity_total > 0
) ;

use constant LATEST_ORDER => qq(
    select max(posted_dt) latest_order from financial_shipment_events
) ;

use constant LATEST_INVENTORY => qq(
    select max(latest_update) latest_report from realtime_inventory
) ;

use constant FIND_UNKNOWN_ACTIVE_SKUS => qq(
    select s.sku, s.vendor_name, s.title, s.description, coalesce(sc.cost,'N/A') cost
      from skus s
      left join active_sources a
        on a.sku = s.sku
      left join sku_costs sc
        on sc.sku = s.sku
     where a.active = 1
       and (s.vendor_name = 'Unknown' or sc.cost is null)
) ;

my $cgi = CGI->new() ;

my $username = &validate() ;
my $sku   = $cgi->param('sku') || undef ;
my $order = $cgi->param('order') || undef ;

print $cgi->redirect( -url=>"/sku.cgi?SKU=$sku")                 if( defined $sku   ) ;
print $cgi->redirect( -url=>"/order.cgi?SOURCE_ORDER_ID=$order") if( defined $order ) ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Homepage",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

#print $cgi->print( "user = '" . getlogin() . "'" ) ;
{
    my $latest_sth = $mkpDBro->prepare(${\LATEST_INVENTORY}) ;
    $latest_sth->execute() or die $DBI::errstr ;
    my $row = $latest_sth->fetchrow_hashref() ;

    print $cgi->small($cgi->i($cgi->b("Latest "))) ;
    print $cgi->small($cgi->i($cgi->b(" inventory: ") . &format_date($row->{latest_report}))) ;
}
{
    my $latest_sth = $mkpDBro->prepare(${\LATEST_ORDER}) ;
    $latest_sth->execute() or die $DBI::errstr ;
    my $row = $latest_sth->fetchrow_hashref() ;

    print $cgi->small($cgi->i($cgi->b(" order: ") . &format_date($row->{latest_order}))) ;
}

my $s_sth = $mkpDBro->prepare(${\TRAILING_DAY_SALES}) ;
my $lookback_days = 61 ;
my $days = 7 ;
$s_sth->execute($lookback_days,$lookback_days,$lookback_days) or die $DBI::errstr ;

print $cgi->h3("Trailing " . ($days + 1) . " Days Sales Flash") ;
print "<TABLE><TR>"       .
      "<TH>Date</TH>"     .
      "<TH>Sales</TH>"    .
      "<TH>Trailing 7-day Sales</TH>"  .
      "<TH>Trailing 30-day Sales</TH>" .
      "<TH>Fees</TH>"     .
      "<TH>COGS</TH>"     .
      "<TH>Expenses</TH>" .
      "<TH>Total</TH>"    .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=string>$ref->{date} </TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sales})    . ">" . &format_currency($ref->{sales})    . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sales})    . ">" . &format_currency($ref->{'7_day'})  . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{sales})    . ">" . &format_currency($ref->{'30_day'}) . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{fees})     . ">" . &format_currency($ref->{fees})     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})     . ">" . &format_currency($ref->{cogs})     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{expenses}) . ">" . &format_currency($ref->{expenses}) . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{total})    . ">" . &format_currency($ref->{total})    . "</TD>\n" ;
    print "</TR>\n" ;
    last if $days-- < 1 ;
}
$s_sth->finish() ;

#
# Put MTD sales
my $mdays = 30 ;
my $mtd_sth = $mkpDBro->prepare(${\MTD_SALES}) ;
$mtd_sth->execute($mdays, $mdays, $mdays) or die $DBI::errstr ;
my $mtd_row = $mtd_sth->fetchrow_hashref() ;
$mtd_sth->finish() ;
print "</TABLE>\n" ;

#
# Total Inventory
print $cgi->h3("Inventory") ;
print "<TABLE><TR>"              .
      "<TH>Type</TH>"            .
      "<TH>Total (\$\$)</TH>"           .
      "<TH>Total (units)</TH>"           .
      "<TH>Coverage (days)</TH>" .
      "</TR> \n" ;
my $inv_sth = $mkpDBro->prepare(${\TOTAL_INVENTORY_COST}) ;
$inv_sth->execute() or die $DBI::errstr ;
my $inv_row = $inv_sth->fetchrow_hashref() ;
print "<TR>\n" ;
print "<TD class=string>In-stock</TD>\n" ;
print "<TD class=number>" . &format_currency($inv_row->{instock_cost},0) . "</TD>\n" ;
print "<TD class=number>" . &format_decimal($inv_row->{instock_units},0) . "</TD>\n" ;
if(defined $mtd_row->{cogs} and $mtd_row->{cogs} != 0)
{
    print "<TD class=number>" . &format_decimal(-1 * ($inv_row->{instock_cost}/($mtd_row->{cogs}/$mdays)),2) . "</TD>\n" ;
}
else
{
    print "<TD class=number>" . &format_decimal(0) . "</TD>\n" ;
}
print "</TR>\n" ;
print "<TR>\n" ;
print "<TD class=string>Total</TD>\n" ;
print "<TD class=number>" . &format_currency($inv_row->{total_cost},0) . "</TD>\n" ;
print "<TD class=number>" . &format_decimal($inv_row->{total_units},0) . "</TD>\n" ;
if(defined $mtd_row->{cogs} and $mtd_row->{cogs} != 0)
{
    print "<TD class=number>" . &format_decimal(-1 * ($inv_row->{total_cost}/($mtd_row->{cogs}/$mdays)),2) . "</TD>\n" ;
}
else
{
    print "<TD class=number>" . &format_decimal(0) . "</TD>\n" ;
}
print "</TR>\n" ;
print "</TABLE>\n" ;
$inv_sth->finish() ;

#
# Unknown SKUs
my $unk_sth = $mkpDBro->prepare(${\FIND_UNKNOWN_ACTIVE_SKUS}) ;
$unk_sth->execute() or die $DBI::errstr ;
if( $unk_sth->rows > 0 )
{
    print $cgi->h3("Found Active Problem SKUs") ;
    print "<TABLE><TR>"     .
          "<TH>SKU</TH>"    .
          "<TH>Vendor</TH>" .
          "<TH>Cost</TH>"   .
          "</TR> \n" ;
    while (my $ref = $unk_sth->fetchrow_hashref())
    {
        print "<TR>" ;
        print &format_html_column($cgi->a({href => "/sku.cgi?SKU=$ref->{sku}"}, $ref->{sku} ),0,"string") ;
        print &format_html_column($ref->{vendor_name},0,"string") ;
        print &format_html_column(($ref->{cost} ne "N/A" ? &format_currency($ref->{cost},2) : "--"),0,"number") ;
        print "</TR>" ;
    }
    print "</TABLE>" ;
}

print $cgi->br() ;
print $cgi->a({href => "/get-orders.cgi"}, "Get Amazon Orders" ) ;
print $cgi->br() ;
print $cgi->a({href => "/pl.cgi"}, "Profit and Loss Statement") ; print " " ;
print $cgi->a({href => "/pl.cgi?granularity=WEEKLY"}, "(weekly)") ;
print $cgi->br() ;
print $cgi->a({href => "/skupl.cgi"}, "SKU Performance" ) ;
print $cgi->br() ;
print $cgi->a({href => "/newbuy.cgi"}, "SKU Buying" ) ;
print $cgi->br() ;
print $cgi->a({href => "/feg.cgi"}, "Financial Event Groups" ) ;
print $cgi->br() ;
print $cgi->a({href => "/userviews.cgi"}, "User Statistics" ) ;
print $cgi->br() ;
print $cgi->a({href => "/inbound.cgi"}, "Inbound Shipments" ) ; print " " ;
print $cgi->a({href => "/inbound.cgi?showclosed=1"}, "(incl closed)" ) ;
print $cgi->br() ;
print $cgi->a({href => "/inventory.cgi"}, "Inventory" ) ;
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

print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Order Lookup:"),
            $cgi->td({ -class => "string" },
                     $cgi->textfield( -name      => 'order',
                                      -value     => $order,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) if $cgi->param('debug') ;
print $cgi->end_table() ;
print $cgi->submit( -name     => 'submit_form',
                    -value    => 'Submit') ;
print $cgi->end_form() ;
print q(
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
) ;

print $cgi->end_html() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

