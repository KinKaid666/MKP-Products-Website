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

use constant INBOUND_SHIPMENTS_SQL => qq(
    select ib.id
           , ib.condition_name
           , ib.ext_shipment_id
           , ib.ext_shipment_name
           , ib.destination
           , sum(quantity_shipped) shipped
           , sum(quantity_received) received
           , sum(sc.cost *quantity_shipped) cost
       from inbound_shipments ib
       join inbound_shipment_items isi
         on isi.inbound_shipment_id = ib.id
       join sku_costs sc
         on isi.sku = sc.sku
       and sc.start_date < NOW()
       and (sc.end_date is null or
            sc.end_date > NOW())
      group by ib.id
               , ib.condition_name
               , ib.ext_shipment_id
               , ib.ext_shipment_name
               , ib.destination
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $showclosed = $cgi->param('showclosed') || 0 ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Inbound Shipments",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ; 
print $cgi->br() ;
print $cgi->br() ;

my $s_sth = $mkpDBro->prepare(${\INBOUND_SHIPMENTS_SQL}) ;
$s_sth->execute() or die $DBI::errstr ;
print "<TABLE><TR>"            .
      "<TH>id</TH>"            .
      "<TH>Condition</TH>"     .
      "<TH>Shipment Id</TH>"   .
      "<TH>Shipment Name</TH>" .
      "<TH>Destination</TH>"   .
      "<TH>Shipped</TH>"       .
      "<TH>Received</TH>"      .
      "<TH>Total Value</TH>"   .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    next if not $showclosed and ($ref->{condition_name} eq "CLOSED" or $ref->{condition_name} eq "DELETED") ;
    print "<TR>\n" ;
    print "<TD class=number>$ref->{id}               </TD>\n" ;
    print "<TD class=string>$ref->{condition_name}   </TD>\n" ;
    print "<TD class=string><a href=inbound-details.cgi?id=$ref->{ext_shipment_id}>$ref->{ext_shipment_id}</a></TD>\n" ;
    print "<TD class=string>$ref->{ext_shipment_name}</TD>\n" ;
    print "<TD class=string>$ref->{destination}      </TD>\n" ;
    print "<TD class=number>$ref->{shipped}          </TD>\n" ;
    print "<TD class=number>$ref->{received}         </TD>\n" ;
    print "<TD class=number>" . &format_currency($ref->{cost},2) . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$mkpDBro->disconnect() ;
