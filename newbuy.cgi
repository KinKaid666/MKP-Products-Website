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
    select min(posted_dt) oldest_order
           ,so.sku
           ,ifnull(last_onhand_inventory_report.source_name, "N/A") source_name
           ,ifnull(last_onhand_inventory_report.condition_name, "N/A") condition_name
           ,ifnull(last_onhand_inventory_report.quantity, 0) quantity
           ,ifnull(last_onhand_inventory_report.quantity, 0) * sc.cost value
           ,sc.cost cost
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
           ,ifnull(last_onhand_inventory_report.quantity, 0) /
                   (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                   ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
           , sum(promotional_rebates                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) +
                 sum(promotional_rebates                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(other_fees                         ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from financial_shipment_events so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.posted_dt
       and (sc.end_date is null or
            sc.end_date > so.posted_dt)
      left outer join (
            select ohi.sku
                   ,ohi.report_date
                   ,ohi.source_name
                   ,ohi.condition_name
                   ,ohi.quantity
              from onhand_inventory_reports ohi
             where report_date = ( select max(report_date) from onhand_inventory_reports )
          ) last_onhand_inventory_report
        on last_onhand_inventory_report.sku = so.sku
     where so.posted_dt > NOW() - INTERVAL ? DAY
     group by sku
              ,sc.cost
              ,last_onhand_inventory_report.source_name
              ,last_onhand_inventory_report.condition_name
              ,last_onhand_inventory_report.quantity
     order by contrib_margin
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 90 ;
my $woc = $cgi->param('woc') || 6 ;
my $buy_amount = $cgi->param('buy_amount') || 2500 ;
my $dbh ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products New Buy", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );
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
      "<TH onclick=\"sortTable(0)\" style=\"cursor:pointer\">Ordest Order</TH>"         .
      "<TH onclick=\"sortTable(1)\" style=\"cursor:pointer\">SKU</TH>"                  .
      "<TH onclick=\"sortTable(2)\" style=\"cursor:pointer\">Source of Inventory</TH>"  .
      "<TH onclick=\"sortTable(3)\" style=\"cursor:pointer\">Condition</TH>"            .
      "<TH onclick=\"sortTable(4)\" style=\"cursor:pointer\">On Hand Units</TH>"        .
      "<TH onclick=\"sortTable(5)\" style=\"cursor:pointer\">On Hand \$</TH>"           .
      "<TH onclick=\"sortTable(6)\" style=\"cursor:pointer\">Desired OH Units</TH>"     .
      "<TH onclick=\"sortTable(7)\" style=\"cursor:pointer\">Desired OH\$</TH>"         .
      "<TH onclick=\"sortTable(8)\" style=\"cursor:pointer\">Amount to Buy Units</TH>"  .
      "<TH onclick=\"sortTable(9)\" style=\"cursor:pointer\">Amount to Buy \$</TH>"     .
      "<TH onclick=\"sortTable(10)\" style=\"cursor:pointer\">Order Count</TH>"         .
      "<TH onclick=\"sortTable(11)\" style=\"cursor:pointer\">Unit Count</TH>"          .
      "<TH onclick=\"sortTable(12)\" style=\"cursor:pointer\">Weekly Velocity</TH>"     .
      "<TH onclick=\"sortTable(13)\" style=\"cursor:pointer\">Weeks of Coverage</TH>"   .
      "<TH onclick=\"sortTable(14)\" style=\"cursor:pointer\">Sales</TH>"               .
      "<TH onclick=\"sortTable(15)\" style=\"cursor:pointer\">Selling Fees</TH>"        .
      "<TH onclick=\"sortTable(16)\" style=\"cursor:pointer\">FBA Fees</TH>"            .
      "<TH onclick=\"sortTable(17)\" style=\"cursor:pointer\">Cogs</TH>"                .
      "<TH onclick=\"sortTable(18)\" style=\"cursor:pointer\">Contribution Margin</TH>" .
      "</TR>\n" ;
while (my $ref = $ohi_sth->fetchrow_hashref())
{
    print "<TR>" ;
    print "<TD class=string>$ref->{oldest_order}</TD>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
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
    my $units_to_buy = ($units_to_cover < $ref->{quantity} ? 0 : ($units_to_cover - $ref->{quantity})) ;
    my $dollars_to_buy = $units_to_buy * $ref->{cost} ;

    print "<TD class=string>$ref->{condition_name}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})           . "</TD>" ;
    print "<TD class=number>" . &format_currency($ref->{value},2)           . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_cover)            . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_cover ,2)      . "</TD>" ;
    print "<TD class=number>" . &format_integer($units_to_buy)              . "</TD>" ;
    print "<TD class=number>" . &format_currency($dollars_to_buy ,2)        . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count})        . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})         . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2)  . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{woc},2)              . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})  . ">" . &format_currency($ref->{product_sales})  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})   . ">" . &format_currency($ref->{selling_fees})   . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})       . ">" . &format_currency($ref->{fba_fees})       . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})           . ">" . &format_currency($ref->{cogs})           . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{contrib_margin}) . ">" . &format_currency($ref->{contrib_margin}) . "</TD>" ;
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
