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

use constant FEG_SQL => qq(
select id
       , ext_id
       , processing_status
       , start
       , end
       , total
       , shipments_value s_value
       , shipments_count s_ct
       , expenses_value e_value
       , expenses_count e_ct
       , shipments_value + expenses_value det_total
       , (shipments_value + expenses_value) - total gap
  from (
        select feg.id
               , feg.ext_financial_event_group_id ext_id
               , processing_status
               , event_start_dt start
               , event_end_dt end
               , feg.total
               , ifnull((select sum(fse.total) from financial_shipment_events fse where fse.feg_id = feg.id),0) shipments_value
               , ifnull((select count(1)       from financial_shipment_events fse where fse.feg_id = feg.id),0) shipments_count
               , ifnull((select sum(fee.total) from financial_expense_events  fee where fee.feg_id = feg.id),0) expenses_value
               , ifnull((select count(1)       from financial_expense_events  fee where fee.feg_id = feg.id),0) expenses_count
          from financial_event_groups feg
       ) a
 order by start desc
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 14 ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Financials",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ;
print $cgi->br() ;
print $cgi->br() ;

my $s_sth = $mkpDBro->prepare(${\FEG_SQL}) ;
$s_sth->execute() or die $DBI::errstr ;
print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;

print "<TABLE id=\"downloadabletable\"><TR>" .
      "<TH>id</TH>"                          .
      "<TH>Ext Id</TH>"                      .
      "<TH>Processing Status</TH>"           .
      "<TH>Start Date</TH>"                  .
      "<TH>End Date</TH>"                    .
      "<TH>Total \$\$</TH>"                  .
      "<TH>Shipment \$\$</TH>"               .
      "<TH>Shipments</TH>"                   .
      "<TH>Expense \$\$</TH>"                .
      "<TH>Expenses</TH>"                    .
      "<TH>Details \$\$</TH>"                .
      "<TH>Gap</TH>"                         .
      "</TR> \n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    print "<TR>\n" ;
    print "<TD class=number>$ref->{id}               </TD>\n" ;
    print "<TD class=string>$ref->{ext_id}           </TD>\n" ;
    print "<TD class=string>$ref->{processing_status}</TD>\n" ;
    print "<TD class=string>$ref->{start}            </TD>\n" ;
    print "<TD class=string>$ref->{end}              </TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{total})     . ">" . &format_currency($ref->{total},2)     . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{s_value})   . ">" . &format_currency($ref->{s_value},2)   . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{s_ct})      . ">" . &format_decimal($ref->{s_ct})         . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{e_value})   . ">" . &format_currency($ref->{e_value},2)   . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{e_ct})      . ">" . &format_decimal($ref->{e_ct})         . "</TD>\n" ;
    print "<TD class=number" . &add_neg_tag($ref->{det_total}) . ">" . &format_currency($ref->{det_total},2) . "</TD>\n" ;
    print "<TD class=number" . ($ref->{gap} != 0 ? "-neg":"")  . ">" . &format_currency($ref->{gap},2)       . "</TD>\n" ;
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
