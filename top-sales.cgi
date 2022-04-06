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

use constant TOP_SALES_DAYS => qq(
select row_number() over (order by sales desc) id, date_format(posted_dt, "%Y-%m-%d (%a)") posted_dt
       , sum(product_charges + shipping_charges + giftwrap_charges + product_charges_tax + shipping_charges_tax + giftwrap_charges_tax + marketplace_facilitator_tax) sales
  from financial_shipment_events fse
 group by date_format(posted_dt, "%Y-%m-%d (%a)")
 order by 3 desc
limit ? ;
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $top_days = $cgi->param('days') || 25 ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Top Sales Days",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ; 
print $cgi->br() ;
print $cgi->br() ;

my $s_sth = $mkpDBro->prepare(${\TOP_SALES_DAYS}) ;

print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;
$s_sth->execute($top_days) or die $DBI::errstr ;
print "<TABLE id=\"downloadabletable\"><TR>" .
      "<TH>Rank</TH>"  .
      "<TH>Date</TH>"  .
      "<TH>Sales</TH>" .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=number>$ref->{id}       </TD>\n" ;
    print "<TD class=string>$ref->{posted_dt}</TD>\n" ;
    print "<TD class=number>" . &format_currency($ref->{sales},2) . "</TD>\n" ;
    print "</TR>\n" ;
}
print "</TABLE>\n" ;
$s_sth->finish() ;
$mkpDBro->disconnect() ;

print q(
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
) ;

