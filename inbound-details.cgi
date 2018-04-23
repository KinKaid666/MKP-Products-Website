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

use constant INBOUND_SHIPMENT_ITEMS_SQL => qq(
    select ib.id
           , ib.condition_name
           , ib.ext_shipment_id
           , ib.ext_shipment_name
           , ib.destination
           , isi.sku
           , quantity_shipped shipped
           , quantity_received received
           , sum(sc.cost*quantity_shipped) cost
       from inbound_shipments ib
       join inbound_shipment_items isi
         on isi.inbound_shipment_id = ib.id
       join sku_costs sc
         on isi.sku = sc.sku
        and sc.start_date < NOW()
        and (sc.end_date is null or
             sc.end_date > NOW())
      where ib.ext_shipment_id = ?
    group by ib.id
           , ib.condition_name
           , ib.ext_shipment_id
           , ib.ext_shipment_name
           , ib.destination
           , isi.sku
           , quantity_shipped
           , quantity_received
      order by quantity_shipped desc
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $id = $cgi->param('id') ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Inbound Shipment Items",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

my $dbh ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {PrintError => 0});

my $s_sth = $dbh->prepare(${\INBOUND_SHIPMENT_ITEMS_SQL}) ;
$s_sth->execute($id) or die $DBI::errstr ;
print "<TABLE><TR>"            .
      "<TH>Id</TH>"            .
      "<TH>Condition</TH>"     .
      "<TH>Shipment Id</TH>"   .
      "<TH>Shipment Name</TH>" .
      "<TH>Destination</TH>"   .
      "<TH>SKU</TH>"           .
      "<TH>Shipped</TH>"       .
      "<TH>Received</TH>"      .
      "<TH>Total Value</TH>"   .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=number>$ref->{id}               </TD>\n" ;
    print "<TD class=string>$ref->{condition_name}   </TD>\n" ;
    print "<TD class=string>$ref->{ext_shipment_id}  </TD>\n" ;
    print "<TD class=string>$ref->{ext_shipment_name}</TD>\n" ;
    print "<TD class=string>$ref->{destination}      </TD>\n" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>\n" ;
    print "<TD class=number>$ref->{shipped}          </TD>\n" ;
    print "<TD class=number>$ref->{received}         </TD>\n" ;
    print "<TD class=number>" . &format_currency($ref->{cost},2) . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$dbh->disconnect() ;
