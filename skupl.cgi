#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use POSIX ;
use Locale::Currency::Format ;

use constant CSS_ID_GREEN => 'green' ;
use constant CSS_ID_AMBER => 'amber' ;
use constant CSS_ID_RED   => 'red' ;
use constant WOC_ID_GREEN => 8 ;
use constant WOC_ID_AMBER => 4 ;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;

use constant SKU_PNL_SELECT_STATEMENT => qq(
    select min(order_datetime) oldest_order
           ,so.sku
           ,ifnull(last_onhand_inventory_report.source_name, "N/A") source_name
           ,ifnull(last_onhand_inventory_report.condition_name, "N/A") condition_name
           ,ifnull(last_onhand_inventory_report.quantity, 0) quantity
           ,count(distinct so.source_order_id      ) order_count
           ,sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
           ,sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) / (?/7)  weekly_velocity
           ,ifnull(last_onhand_inventory_report.quantity, 0) / (sum(case when so.type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) / (?/7)) woc
           ,sum(so.product_sales                   ) product_sales
           ,sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) selling_fees
           ,sum(so.fba_fees                        ) fba_fees
           ,sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) cogs
           ,sum(so.product_sales                   ) +
                 sum(shipping_credits                   ) +
                 sum(gift_wrap_credits                  ) +
                 sum(promotional_rebates                ) +
                 sum(sales_tax_collected                ) +
                 sum(marketplace_facilitator_tax        ) +
                 sum(transaction_fees                   ) +
                 sum(other                              ) +
                 sum(so.selling_fees                    ) +
                 sum(so.fba_fees                        ) +
                 sum(case when so.type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
      from sku_orders so
      join sku_costs sc
        on so.sku = sc.sku
       and sc.start_date < so.order_datetime
       and (sc.end_date is null or
            sc.end_date > so.order_datetime)
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
     where so.order_datetime > NOW() - INTERVAL ? DAY
     group by sku
              ,last_onhand_inventory_report.source_name
              ,last_onhand_inventory_report.condition_name
              ,last_onhand_inventory_report.quantity
     order by contrib_margin
) ;

my $dbh ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 180 ;

$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "ericferg_ro",
                    "ericferg_ro_2018",
                    {'RaiseError' => 1});

my $s_sth = $dbh->prepare(${\SKU_PNL_SELECT_STATEMENT}) ;
$s_sth->execute($days, $days, $days) or die $DBI::errstr ;
print "Content-type: text/html\n\n";
print qq(
<head><style>
table, th, tr, td {border:1px solid black; white-space:nowrap}

tr:nth-child(odd)   {background-color:#f1f1f1;}
tr:nth-child(even)  {background-color:#ffffff;}

td.string {text-align:left; }
td.number {text-align:right; }
td.number-neg {text-align:right; color:#FF0000;}

#green { background-color:#00FF00; }
#amber { background-color:#ffff00; }
#red   { background-color:#ff3300; }
pre { display: block; font-family: monospace; }
</head></style>
<body>
) ;
print "<TABLE id=\"pnl\">"           .
      "<TBODY><TR>"                  .
      "<TH onclick=\"sortTable(0)\" style=\"cursor:pointer\">Ordest Order</TH>"        .
      "<TH onclick=\"sortTable(1)\" style=\"cursor:pointer\">SKU</TH>"                 .
      "<TH onclick=\"sortTable(2)\" style=\"cursor:pointer\">Source of Inventory</TH>" .
      "<TH onclick=\"sortTable(3)\" style=\"cursor:pointer\">Condition</TH>"           .
      "<TH onclick=\"sortTable(4)\" style=\"cursor:pointer\">On Hand Quantity</TH>"    .
      "<TH onclick=\"sortTable(5)\" style=\"cursor:pointer\">Order Count</TH>"         .
      "<TH onclick=\"sortTable(6)\" style=\"cursor:pointer\">Unit Count</TH>"          .
      "<TH onclick=\"sortTable(7)\" style=\"cursor:pointer\">Weekly Velocity</TH>"     .
      "<TH onclick=\"sortTable(8)\" style=\"cursor:pointer\">Weeks of Coverage</TH>"   .
      "<TH onclick=\"sortTable(9)\" style=\"cursor:pointer\">Sales</TH>"               .
      "<TH onclick=\"sortTable(10)\" style=\"cursor:pointer\">Selling Fees</TH>"        .
      "<TH onclick=\"sortTable(11)\" style=\"cursor:pointer\">FBA Fees</TH>"            .
      "<TH onclick=\"sortTable(12)\" style=\"cursor:pointer\">Cogs</TH>"                .
      "<TH onclick=\"sortTable(13)\" style=\"cursor:pointer\">Contribution Margin</TH>" .
      "</TR>\n" ;
while (my $ref = $s_sth->fetchrow_hashref())
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
    print "<TD class=string>$ref->{condition_name}</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity})          . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count})       . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})        . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2) . "</TD>" ;
    print "<TD class=number id=" . &get_color_code($ref->{woc}) . ">" . &format_decimal($ref->{woc},2)             . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales})  . ">" . &format_currency($ref->{product_sales})  . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{selling_fees})   . ">" . &format_currency($ref->{selling_fees})   . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{fba_fees})       . ">" . &format_currency($ref->{fba_fees})       . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{cogs})           . ">" . &format_currency($ref->{cogs})           . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{contrib_margin}) . ">" . &format_currency($ref->{contrib_margin}) . "</TD>" ;
    print "</TR>" ;
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
$s_sth->finish() ;
$dbh->disconnect() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

sub get_color_code
{
    my $number = shift || 0 ;
    my $color = ${\CSS_ID_RED} ;
    $color = ${\CSS_ID_GREEN} if( $number > ${\WOC_ID_GREEN} ) ;
    $color = ${\CSS_ID_AMBER} if( $number > ${\WOC_ID_AMBER}  and $number < ${\WOC_ID_GREEN} ) ;
    return $color ;
}

