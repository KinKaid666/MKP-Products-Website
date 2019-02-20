#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

use constant CSS_ID_GREEN => 'green' ;
use constant CSS_ID_AMBER => 'amber' ;
use constant CSS_ID_RED   => 'red' ;
use constant WOC_ID_GREEN => 8 ;
use constant WOC_ID_AMBER => 4 ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

use constant SKU_PNL_SELECT_STATEMENT => qq(
    select oldest_order
           ,sku
           ,vendor_name
           ,source_name
           ,quantity_instock
           ,quantity_total
           ,is_active
           ,order_count
           ,unit_count
           ,weekly_velocity
           ,product_sales
           ,woc
           ,selling_fees
           ,fba_fees
           ,cogs
           ,contrib_margin
      from
      (
                select min(posted_dt) oldest_order
                       ,so.sku
                       ,v.vendor_name
                       ,ri.source_name
                       ,ri.quantity_instock
                       ,ri.quantity_total
                       ,ifnull(acts.active,0) is_active
                       ,count(distinct so.source_order_id      ) order_count
                       ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
                       ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
                       ,ifnull(ri.quantity_total, 0) /
                               (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
                       ,sum(promotional_rebates                ) +
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
                  left outer join active_sources acts
                    on acts.sku = so.sku
                  left outer join realtime_inventory ri
                    on ri.sku = so.sku
                  join skus s
                    on sc.sku = s.sku
                  join vendors v
                    on v.vendor_name = s.vendor_name
                 where so.posted_dt > NOW() - INTERVAL ? DAY
                 group by sku
                          ,v.vendor_name
                          ,ri.source_name
                          ,ri.quantity_instock
                          ,ri.quantity_total
            union
            select min(posted_dt) oldest_order
                       ,ri.sku
                       ,v.vendor_name
                       ,ri.source_name
                       ,ri.quantity_instock
                       ,ri.quantity_total
                       ,ifnull(acts.active,0) is_active
                       ,count(distinct so.source_order_id      ) order_count
                       ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) unit_count
                       ,sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/ 7) weekly_velocity
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax) product_sales
                       ,ifnull(ri.quantity_total, 0) /
                               (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
                       ,sum(promotional_rebates                ) +
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
                  from realtime_inventory ri
                  join skus s
                    on ri.sku = s.sku
                  join vendors v
                    on v.vendor_name = s.vendor_name
                  left outer join active_sources acts
                    on acts.sku = ri.sku
                  left outer join financial_shipment_events so
                    on ri.sku = so.sku
                  left outer join sku_costs sc
                    on so.sku = sc.sku
                   and sc.start_date < so.posted_dt
                   and (sc.end_date is null or
                        sc.end_date > so.posted_dt)
                where so.posted_dt is null
                  and ri.quantity_total > 0
                 group by sku
                          ,v.vendor_name
                          ,ri.source_name
                          ,ri.quantity_instock
                          ,ri.quantity_total
                          ,is_active
    ) a
    order by weekly_velocity desc
) ;

my $dbh ;
my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 90 ;
my $show_active = $cgi->param('show_active') ;


print $cgi->header;
print $cgi->start_html( -title => "MKP Products SKU Performance",
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
                     "Settings:"),
            $cgi->td($cgi->checkbox( -name      => 'show_active',
                                     -checked   => $show_active,
                                     -label     => "Show only active"))
      ) ;
print $cgi->Tr(
            $cgi->td(),
            $cgi->td($cgi->submit( -name     => 'submit_form',
                                   -value    => 'Submit',
                                   -onsubmit => 'javascript: validate_form()')),
      );
print $cgi->end_table() ;
print $cgi->end_form() ;


$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=mkp.cjulnvkhabig.us-east-2.rds.amazonaws.com",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {PrintError => 0});

my $s_sth = $dbh->prepare(${\SKU_PNL_SELECT_STATEMENT}) ;
$s_sth->execute($days, $days, $days, $days, $days, $days, $days, $days, $days) or die $DBI::errstr ;
print "<TABLE id=\"pnl\">"           .
      "<TBODY><TR>"                  .
      "<TH onclick=\"sortTable(0)\" style=\"cursor:pointer\">SKU</TH>"                  .
      "<TH onclick=\"sortTable(1)\" style=\"cursor:pointer\">Vendor</TH>"               .
      "<TH onclick=\"sortTable(2)\" style=\"cursor:pointer\">Source of Inventory</TH>"  .
      "<TH onclick=\"sortTable(3)\" style=\"cursor:pointer\">In-stock Qty</TH>"         .
      "<TH onclick=\"sortTable(4)\" style=\"cursor:pointer\">Total Qty</TH>"            .
      "<TH onclick=\"sortTable(5)\" style=\"cursor:pointer\">Orders</TH>"               .
      "<TH onclick=\"sortTable(6)\" style=\"cursor:pointer\">Units</TH>"                .
      "<TH onclick=\"sortTable(7)\" style=\"cursor:pointer\">Velocity</TH>"             .
      "<TH onclick=\"sortTable(8)\" style=\"cursor:pointer\">WOC</TH>"                  .
      "<TH onclick=\"sortTable(9)\" style=\"cursor:pointer\">Sales</TH>"                .
      "<TH onclick=\"sortTable(10)\" style=\"cursor:pointer\">/ unit</TH>"              .
      "<TH onclick=\"sortTable(11)\" style=\"cursor:pointer\">Selling Fees</TH>"        .
      "<TH onclick=\"sortTable(12)\" style=\"cursor:pointer\">/ unit</TH>"              .
      "<TH onclick=\"sortTable(13)\" style=\"cursor:pointer\">%</TH>"                   .
      "<TH onclick=\"sortTable(14)\" style=\"cursor:pointer\">FBA Fees</TH>"            .
      "<TH onclick=\"sortTable(15)\" style=\"cursor:pointer\">/ unit</TH>"              .
      "<TH onclick=\"sortTable(16)\" style=\"cursor:pointer\">%</TH>"                   .
      "<TH onclick=\"sortTable(17)\" style=\"cursor:pointer\">Cogs</TH>"                .
      "<TH onclick=\"sortTable(18)\" style=\"cursor:pointer\">/ unit</TH>"              .
      "<TH onclick=\"sortTable(19)\" style=\"cursor:pointer\">%</TH>"                   .
      "<TH onclick=\"sortTable(20)\" style=\"cursor:pointer\">Contribution Margin</TH>" .
      "<TH onclick=\"sortTable(22)\" style=\"cursor:pointer\">/ unit</TH>"              .
      "<TH onclick=\"sortTable(23)\" style=\"cursor:pointer\">%</TH>"                   .
      "</TR>\n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    next if ($show_active and not $ref->{is_active}) ;
    print "<TR>" ;
    print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>" ;
    print "<TD class=string>$ref->{vendor_name}</TD>" ;
    if(not $ref->{source_name} =~ m/www/)
    {
        print "<TD class=string>$ref->{source_name}</TD>" ;
    }
    else
    {
        print "<TD class=string><a href=http://$ref->{source_name}>$ref->{source_name}</a></TD>" ;
    }
    print "<TD class=number>" . &format_integer($ref->{quantity_instock})  . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{quantity_total})    . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{order_count})       . "</TD>" ;
    print "<TD class=number>" . &format_integer($ref->{unit_count})        . "</TD>" ;
    print "<TD class=number>" . &format_decimal($ref->{weekly_velocity},2) . "</TD>" ;
    print "<TD class=number id=" . &get_color_code($ref->{woc}) . ">" . &format_decimal($ref->{woc},2) . "</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{product_sales}) . ">" . &format_currency($ref->{product_sales}) . "</TD>\n" ;
    if($ref->{product_sales} == 0 or $ref->{unit_count} == 0)
    {
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees})   . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees})       . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs})           . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin}) . "</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
        print "<TD class=number>NaN</TD>\n" ;
    }
    else
    {
        print "<TD class=number" . &add_neg_tag($ref->{product_sales})     . ">" . &format_currency($ref->{product_sales}/$ref->{unit_count},2)    . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees})                          . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_currency($ref->{selling_fees}/$ref->{unit_count},2)     . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{selling_fees})      . ">" . &format_percent($ref->{selling_fees}/$ref->{product_sales},1)   . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees})                              . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_currency($ref->{fba_fees}/$ref->{unit_count},2)         . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{fba_fees})          . ">" . &format_percent($ref->{fba_fees}/$ref->{product_sales},1)       . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs})                                  . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_currency($ref->{cogs}/$ref->{unit_count},2)             . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{cogs})              . ">" . &format_percent($ref->{cogs}/$ref->{product_sales},1)           . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin})                        . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_currency($ref->{contrib_margin}/$ref->{unit_count},2)   . "</TD>\n" ;
        print "<TD class=number" . &add_neg_tag($ref->{contrib_margin})    . ">" . &format_percent($ref->{contrib_margin}/$ref->{product_sales},1) . "</TD>\n" ;
    }
    print "</TR>" ;
}
print qq(</TBODY></TABLE> <script>
function sortTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("pnl");
  switching = true;
  // Set the sorting direction to ascending:
  dir = "desc";
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
      if (switchcount == 0 && dir == "desc") {
        dir = "asc";
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

