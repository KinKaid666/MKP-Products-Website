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

use constant INVENTORY_SQL => qq(
    select ri.sku
           , ri.quantity_instock
           , ri.quantity_instock * sc.cost instock_cost
           , ri.quantity_total
           , ri.quantity_total * sc.cost total_cost
           , sc.cost
      from realtime_inventory ri
      left outer join sku_costs sc
        on ri.sku = sc.sku
       and sc.start_date < now()
       and (sc.end_date is null or sc.end_date > now())
     where ri.quantity_total > 0
     order by 5 desc
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Inventory",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

my $dbh ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

my $s_sth = $dbh->prepare(${\INVENTORY_SQL}) ;
$s_sth->execute() or die $DBI::errstr ;
print "<TABLE><TR>"                .
      "<TH>SKU</TH>"               .
      "<TH>Currenty Cost</TH>"     .
      "<TH>In-stock Qty</TH>"      .
      "<TH>In-stock Qty \$\$</TH>" .
      "<TH>Total Qty</TH>"         .
      "<TH>Total Qty \$\$</TH>"    .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>\n" ;
    if( defined $ref->{total_cost} )
    {
        print "<TD class=number>" . &format_currency($ref->{cost},2) . "</TD>\n" ;
    }
    else
    {
        print "<TD class=number-neg>Missing Cost</TD>\n" ;
    }
    print "<TD class=number>$ref->{quantity_instock}</TD>\n" ;
    print "<TD class=number>" . &format_currency($ref->{instock_cost},2) . "</TD>\n" ;
    print "<TD class=number>$ref->{quantity_total}</TD>\n" ;
    print "<TD class=number>" . &format_currency($ref->{total_cost},2) . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$dbh->disconnect() ;
