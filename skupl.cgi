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
use MKPDatabase ;

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
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) product_sales
                       ,ifnull(ri.quantity_total, 0) /
                               (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
                       ,sum(promotional_rebates                ) +
                            sum(other_fees                         ) +
                            sum(so.selling_fees                    ) selling_fees
                       ,sum(so.fba_fees                        ) fba_fees
                       ,sum(case when so.event_type = 'Refund' and so.product_charges <> 0 then sc.cost*so.quantity*1
                                 when so.event_type = 'Refund' and so.product_charges = 0 then 0
                                 else sc.cost*so.quantity*-1 end) cogs
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) +
                             sum(promotional_rebates                ) +
                             sum(other_fees                         ) +
                             sum(so.selling_fees                    ) +
                             sum(so.fba_fees                        ) +
                             sum(case when so.event_type = 'Refund' then sc.cost*so.quantity*1 else sc.cost*so.quantity*-1 end) contrib_margin
                  from financial_shipment_events so
                  join sku_costs sc
                    on so.sku = sc.sku
                   and sc.start_date <= date(so.posted_dt)
                   and (sc.end_date is null or
                        sc.end_date >= date(so.posted_dt))
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
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) product_sales
                       ,ifnull(ri.quantity_total, 0) /
                               (sum(case when so.event_type = 'Refund' then -1 * CAST(so.quantity as SIGNED) else 1 * CAST(so.quantity as SIGNED) end) /
                               ((case when datediff(NOW(),min(posted_dt)) > ? then ? else datediff(NOW(),min(posted_dt)) end)/7)) woc
                       ,sum(promotional_rebates                ) +
                            sum(other_fees                         ) +
                            sum(so.selling_fees                    ) selling_fees
                       ,sum(so.fba_fees                        ) fba_fees
                       ,sum(case when so.event_type = 'Refund' and so.product_charges <> 0 then sc.cost*so.quantity*1
                                 when so.event_type = 'Refund' and so.product_charges = 0 then 0
                                 else sc.cost*so.quantity*-1 end) cogs
                       ,sum(so.product_charges + product_charges_tax + shipping_charges + shipping_charges_tax + giftwrap_charges + giftwrap_charges_tax + marketplace_facilitator_tax) +
                             sum(promotional_rebates                ) +
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
                   and sc.start_date <= date(so.posted_dt)
                   and (sc.end_date is null or
                        sc.end_date >= date(so.posted_dt))
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

my $username = &validate() ;
my $cgi = CGI->new() ;
my $days = $cgi->param('days') || 90 ;
my $show_only_active = 'on' ;

if($cgi->param('submit_form'))
{
    $show_only_active = $cgi->param('show_active') ;
}


print $cgi->header;
print $cgi->start_html( -title => "MKP Products SKU Performance",
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
            $cgi->td({ -class => "string" }, "Settings") ,
            $cgi->td($cgi->checkbox( -name      => 'show_active',
                                     -checked   => 'on',
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

my $s_sth = $mkpDBro->prepare(${\SKU_PNL_SELECT_STATEMENT}) ;
$s_sth->execute($days, $days, $days, $days, $days, $days, $days, $days, $days) or die $DBI::errstr ;
print $cgi->br ;
print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;

print "<TABLE id=\"downloadabletable\">" .
      "<TBODY><TR>"                  .
      "<TH>SKU</TH>"                 .
      "<TH>Vendor</TH>"              .
      "<TH>Source of Inventory</TH>" .
      "<TH>In-stock Qty</TH>"        .
      "<TH>Total Qty</TH>"           .
      "<TH>Orders</TH>"              .
      "<TH>Units</TH>"               .
      "<TH>Velocity</TH>"            .
      "<TH>WOC</TH>"                 .
      "<TH>Sales</TH>"               .
      "<TH>/ unit</TH>"              .
      "<TH>Selling Fees</TH>"        .
      "<TH>/ unit</TH>"              .
      "<TH>%</TH>"                   .
      "<TH>FBA Fees</TH>"            .
      "<TH>/ unit</TH>"              .
      "<TH>%</TH>"                   .
      "<TH>Cogs</TH>"                .
      "<TH>/ unit</TH>"              .
      "<TH>%</TH>"                   .
      "<TH>Contribution Margin</TH>" .
      "<TH>/ unit</TH>"              .
      "<TH>%</TH>"                   .
      "</TR>\n" ;
while (my $ref = $s_sth->fetchrow_hashref())
{
    next if ($show_only_active eq "on" and not $ref->{is_active}) ;
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
print qq(</TBODY></TABLE>
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
</BODY> </HTML>) ;
$s_sth->finish() ;
$mkpDBro->disconnect() ;

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

