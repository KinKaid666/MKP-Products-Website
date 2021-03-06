#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;
use Data::Dumper ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;
use MKPDatabase ;

use constant LOW_SKU_VELOCITY_THRESHOLD => 13 ;
use constant SKU_OHI_SELECT_STATEMENT => qq(
    select so.sku
           ,s.title
           ,v.vendor_name
           ,ifnull(scp.vendor_sku,'Unknown') vendor_sku
           ,ifnull(scp.pack_size,1) pack_size
           ,ifnull(ri.source_name, "N/A") source_name
           ,ifnull(ri.quantity_total, 0) quantity_total
           ,ifnull(acts.active,0) is_active
           ,sc.cost cost
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
           ,ifnull(ri.quantity_total, 0) /
                   (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
      from financial_shipment_events so
      join (select max(start_date), sku, cost from sku_costs group by sku) sc
        on sc.sku = so.sku
      left outer join realtime_inventory ri
        on ri.sku = so.sku
      join skus s
        on sc.sku = s.sku
      left outer join active_sources acts
        on acts.sku = s.sku
      join vendors v
        on v.vendor_name = s.vendor_name
      left outer join sku_case_packs scp
        on scp.sku = s.sku
     where so.posted_dt > NOW() - INTERVAL ? DAY
     group by sku
              ,s.title
              ,v.vendor_name
              ,scp.vendor_sku
              ,scp.pack_size
              ,sc.cost
              ,ri.source_name
              ,ri.quantity_total
     order by weekly_velocity desc
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 180 ;
my $woc = $cgi->param('woc') || 13 ;
my $lvt = $cgi->param('lvt') || ${\LOW_SKU_VELOCITY_THRESHOLD}   ;
my $buy_amount = $cgi->param('buy_amount') || 2500 ;
my $show_only_active = 'on' ;

if($cgi->param('submit_form'))
{
    $show_only_active = $cgi->param('show_active') ;
}

print $cgi->header;
print $cgi->start_html( -title => "MKP Products New Buy",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->a( { -href => "/" }, "Back" ) ; 
print $cgi->br() ;
print $cgi->br() ;

print $cgi->start_form(
    -name    => 'main_form',
    -method  => 'POST',
    -enctype => &CGI::URL_ENCODED,
    -onsubmit => 'return javascript:validation_function()',
);
print $cgi->start_table ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Days of History"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'days',
                                      -value     => $days,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Buy Amount"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'buy amount',
                                      -value     => $buy_amount,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Weeks of Coverage Goal"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'woc',
                                      -value     => $woc,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Low Velocity Threshold"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'lvt',
                                      -value     => $lvt,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" }, "Settings"),
            $cgi->td($cgi->checkbox( -name    => 'show_active',
                                     -checked => 'on',
                                     -label   => "Show only active"))
      ) ;

print $cgi->Tr($cgi->td(),
            $cgi->td($cgi->submit( -name     => 'submit_form',
                                   -value    => 'Submit',
                                   -onsubmit => 'javascript: validate_form()')),
      );
print $cgi->end_table() ;
print $cgi->end_form() ;
my $ohi_sth = $mkpDBro->prepare(${\SKU_OHI_SELECT_STATEMENT}) ;
$ohi_sth->execute($days, $days, $days, $days, $days) or die $DBI::errstr ;

print $cgi->br() ;
print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;

print "<BR><TABLE id=\"downloadabletable\">" .
      "<TBODY><TR>"            .
      "<TH>SKU</TH>"           .
      "<TH>Title</TH>"         .
      "<TH>Vendor</TH>"        .
      "<TH>Vendor SKU</TH>"    .
      "<TH>Pack Size</TH>"     .
      "<TH>Source</TH>"        .
      "<TH>Total Qty</TH>"     .
      "<TH>Desired OH</TH>"    .
      "<TH>Desired OH\$</TH>"  .
      "<TH>To Buy</TH>"        .
      "<TH>To Buy Vendor</TH>".
      "<TH>To Buy \$</TH>"    .
      "<TH>Velocity</TH>"     .
      "<TH>WOC</TH>"          .
      "<TH>Sold</TH>"         .
      "</TR>\n" ;
while (my $ref = $ohi_sth->fetchrow_hashref())
{
    my $units_to_cover = (floor($ref->{weekly_velocity} * $woc) < 0 ? 0 : (floor($ref->{weekly_velocity} * $woc))) ;
    my $dollars_to_cover = $units_to_cover * $ref->{cost} ;
    my $units_to_buy = ($units_to_cover < $ref->{quantity_total} ? 0 : ($units_to_cover - $ref->{quantity_total})) ;

    #
    # don't buy back into slow selling SKUs
    $units_to_buy = $ref->{unit_count} if($units_to_buy and $ref->{unit_count} < $lvt) ;

    #
    # Round up to the next pack size
    my $vendor_units_to_buy = $units_to_buy * $ref->{pack_size} ;


    # convert to dollars
    my $dollars_to_buy = $units_to_buy * $ref->{cost} ;

    # Don't bother
    next if (not $units_to_buy or (not $ref->{is_active} and $show_only_active eq 'on')) ;

    # print
    print "<TR>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string>$ref->{title}</TD>" ;
    print "<TD class=string>$ref->{vendor_name}</TD>" ;
    print "<TD class=string>$ref->{vendor_sku}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{pack_size}) . "</TD>" ;
    if(not $ref->{source_name} =~ m/www/)
    {
        print "<TD class=string>$ref->{source_name}</TD>" ;
    }
    else
    {
        print "<TD class=string><a href=http://$ref->{source_name}>$ref->{source_name}</a></TD>" ;
    }


    print "<TD class=number>" . &format_integer($ref->{quantity_total})     . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_cover)            . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_cover ,2)      . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_buy)              . "</TD>" ;
    print "<TD class=number>" . &format_integer($vendor_units_to_buy)       . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_buy ,2)        . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2)  . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{woc},2)              . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{unit_count},0)       . "</TD>" ;
    print "</TR>\n" ;
}
print qq(</TBODY></TABLE>
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
</BODY> </HTML>) ;
$ohi_sth->finish() ;
$mkpDBro->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

sub download
{
    ;
}
