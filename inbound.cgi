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

use constant INBOUND_SHIPMENTS_SQL => qq(
    select ib.id
           , ib.condition_name
           , ib.ext_shipment_id
           , ib.ext_shipment_name
           , ib.destination
           , sum(quantity_shipped) shipped
           , sum(quantity_received) received
       from inbound_shipments ib
       join inbound_shipment_items isi
         on isi.inbound_shipment_id = ib.id
      group by ib.id
               , ib.condition_name
               , ib.ext_shipment_id
               , ib.ext_shipment_name
               , ib.destination
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 14 ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Financials",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

my $dbh ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

my $s_sth = $dbh->prepare(${\INBOUND_SHIPMENTS_SQL}) ;
$s_sth->execute() or die $DBI::errstr ;
print "<TABLE><TR>"            .
      "<TH>id</TH>"            .
      "<TH>Condition</TH>"     .
      "<TH>Shipment Id</TH>"   .
      "<TH>Shipment Name</TH>" .
      "<TH>Destination</TH>"   .
      "<TH>Shipped</TH>"       .
      "<TH>Received</TH>"      .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=number>$ref->{id}               </TD>\n" ;
    print "<TD class=string>$ref->{condition_name}   </TD>\n" ;
    print "<TD class=string>$ref->{ext_shipment_id}  </TD>\n" ;
    print "<TD class=string>$ref->{ext_shipment_name}</TD>\n" ;
    print "<TD class=string>$ref->{destination}      </TD>\n" ;
    print "<TD class=number>$ref->{shipped}          </TD>\n" ;
    print "<TD class=number>$ref->{received}         </TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$dbh->disconnect() ;
