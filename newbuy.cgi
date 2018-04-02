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

use constant SKU_OHI_SELECT_STATEMENT => qq(
    select so.sku
           ,s.title
           ,v.vendor_name
           ,ifnull(scp.vendor_sku,'Unknown') vendor_sku
           ,ifnull(scp.pack_size,1) pack_size
           ,ifnull(ri.source_name, "N/A") source_name
           ,ifnull(ri.quantity_total, 0) quantity_total
           ,sc.cost cost
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
           ,ifnull(ri.quantity_total, 0) /
                   (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
      from financial_shipment_events so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.posted_dt
       and (sc.end_date is null or
            sc.end_date > so.posted_dt)
     left outer join realtime_inventory ri
       on ri.sku = so.sku
      join skus s
        on sc.sku = s.sku
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
my $days = $cgi->param('days') || 90 ;
my $woc = $cgi->param('woc') || 6 ;
my $buy_amount = $cgi->param('buy_amount') || 2500 ;
my $dbh ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products New Buy",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print $cgi->start_form(
    -name    => 'main_form',
    -method  => 'POST',
    -enctype => &CGI::URL_ENCODED,
    -onsubmit => 'return javascript:validation_function()',
);
print $cgi->start_table ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Days of History:"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'days',
                                      -value     => $days,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Buy Amount:"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'buy amount',
                                      -value     => $buy_amount,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Weeks of Coverage Goal:"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'woc',
                                      -value     => $woc,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td($cgi->submit( -name     => 'download_form',
                                   -value    => 'Download',
                                   -onsubmit => '')),
            $cgi->td($cgi->submit( -name     => 'submit_form',
                                   -value    => 'Submit',
                                   -onsubmit => 'javascript: validate_form()')),
      );
print $cgi->end_table() ;
print $cgi->end_form() ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

my $ohi_sth = $dbh->prepare(${\SKU_OHI_SELECT_STATEMENT}) ;
$ohi_sth->execute($days, $days, $days, $days, $days) or die $DBI::errstr ;

print "<BR><TABLE id=\"pnl\">" .
      "<TBODY><TR>"            .
      "<TH onclick=\"sortTable(0)\" style=\"cursor:pointer\">SKU</TH>"           .
      "<TH onclick=\"sortTable(1)\" style=\"cursor:pointer\">Title</TH>"         .
      "<TH onclick=\"sortTable(2)\" style=\"cursor:pointer\">Vendor</TH>"        .
      "<TH onclick=\"sortTable(3)\" style=\"cursor:pointer\">Vendor SKU</TH>"    .
      "<TH onclick=\"sortTable(4)\" style=\"cursor:pointer\">Pack Size</TH>"     .
      "<TH onclick=\"sortTable(5)\" style=\"cursor:pointer\">Source</TH>"        .
      "<TH onclick=\"sortTable(6)\" style=\"cursor:pointer\">Total Qty</TH>"     .
      "<TH onclick=\"sortTable(7)\" style=\"cursor:pointer\">Desired OH</TH>"    .
      "<TH onclick=\"sortTable(8)\" style=\"cursor:pointer\">Desired OH\$</TH>"  .
      "<TH onclick=\"sortTable(9)\" style=\"cursor:pointer\">To Buy</TH>"        .
      "<TH onclick=\"sortTable(10)\" style=\"cursor:pointer\">To Buy Vendor</TH>".
      "<TH onclick=\"sortTable(11)\" style=\"cursor:pointer\">To Buy \$</TH>"    .
      "<TH onclick=\"sortTable(12)\" style=\"cursor:pointer\">Velocity</TH>"     .
      "<TH onclick=\"sortTable(13)\" style=\"cursor:pointer\">WOC</TH>"          .
      "</TR>\n" ;
while (my $ref = $ohi_sth->fetchrow_hashref())
{
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

    my $units_to_cover = (floor($ref->{weekly_velocity} * $woc) < 0 ? 0 : (floor($ref->{weekly_velocity} * $woc))) ;
    my $dollars_to_cover = $units_to_cover * $ref->{cost} ;
    my $units_to_buy = ($units_to_cover < $ref->{quantity_total} ? 0 : ($units_to_cover - $ref->{quantity_total})) ;

    #
    # Round up to the next pack size
    my $vendor_units_to_buy = $units_to_buy * $ref->{pack_size} ;

    # convert to dollars
    my $dollars_to_buy = $units_to_buy * $ref->{cost} ;

    print "<TD class=number>" . &format_integer($ref->{quantity_total})     . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_cover)            . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_cover ,2)      . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_buy)              . "</TD>" ;
    print "<TD class=number>" . &format_integer($vendor_units_to_buy)       . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_buy ,2)        . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2)  . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{woc},2)              . "</TD>" ;
    print "</TR>\n" ;
}
print qq(</TBODY></TABLE> <script>
function sortTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("pnl");
  switching = true;
  // Set the sorting direction to ascending:
  dir = "asc";
  /* Make a loop that will continue until
  no switching has been done: */
  while (switching) {
    // Start by saying: no switching is done:
    switching = false;
    rows = table.getElementsByTagName("TR");
    /* Loop through all table rows (except the
    first, which contains table headers): */
    for (i = 1; i < (rows.length - 1); i++) {
      // Start by saying there should be no switching:
      shouldSwitch = false;
      /* Get the two elements you want to compare, one from current row and one from the next: */
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i + 1].getElementsByTagName("TD")[n];
      /* Check if the two rows should switch place, based on the direction, asc or desc: */

      var a, b ;
      if( n >= 4 )
      {
        a = Number(x.innerHTML.toLowerCase().replace(/[^0-9\.-]+/g,""));
        b = Number(y.innerHTML.toLowerCase().replace(/[^0-9\.-]+/g,""));
      }
      else
      {
        a = x.innerHTML.toLowerCase();
        b = y.innerHTML.toLowerCase();
      }
      if (dir == "asc") {
        if (a > b) {
          // If so, mark as a switch and break the loop:
          shouldSwitch= true;
          break;
        }
      } else if (dir == "desc") {
        if (a < b) {
          // If so, mark as a switch and break the loop:
          shouldSwitch= true;
          break;
        }
      }
    }
    if (shouldSwitch) {
      /* If a switch has been marked, make the switch and mark that a switch has been done: */
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      // Each time a switch is done, increase this count by 1:
      switchcount ++;
    } else {
      /* If no switching has been done AND the direction is "asc", set the direction to "desc" and run the while loop again. */
      if (switchcount == 0 && dir == "asc") {
        dir = "desc";
        switching = true;
      }
    }
  }
}
</script> </BODY> </HTML>) ;

$ohi_sth->finish() ;
$dbh->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

sub download
{
    ;
}
