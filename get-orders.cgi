#!/usr/bin/perl -w

use strict ;
use warnings ;

use Try::Tiny ;
use Amazon::MWS::Client ;
use Amazon::MWS::Exception ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;
use Data::Dumper ;
use Date::Manip ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;
use MKPDatabase ;
use MKPMWS ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $start = $cgi->param('start') || UnixDate(DateTime->now()->add(days=>-7)->set_time_zone($timezone),"%Y-%m-%d") ;
my $end = $cgi->param('end') ;

#
# Only way I can figure out how to get checkbox groups to work
my @order_statuses_selected ;
my @os_defaults = ( 'Unshipped' ) ;
my @order_status_options = ( 'PendingAvailability', 'Pending', 'Unshipped', 'PartiallyShipped', 'Shipped', 'Canceled', 'Unfulfillable') ;
if($cgi->param('order_statuses'))
{
    foreach my $i ($cgi->param('order_statuses'))
    {
        push @order_statuses_selected, $i ;
    }
}
else
{
    # set default if we here on a new page load
    @order_statuses_selected = @os_defaults if(not defined $cgi->param('submit_form')) ;
}
my @fulfillment_channel_selected ;
my @fc_defaults = ('MFN') ;
my @fulfillment_channel_options = ('MFN', 'AFN') ;
if($cgi->param('fulfillment_channel'))
{
    foreach my $i ($cgi->param('fulfillment_channel'))
    {
        push @fulfillment_channel_selected, $i ;
    }
}
else
{
    # set default if we here on a new page load
    @fulfillment_channel_selected = @fc_defaults if(not defined $cgi->param('submit_form'))
}

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Amazon Unshipped Orders",
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
print $cgi->start_table( ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Start:"),
            $cgi->td({ -class => "string" },
                     $cgi->textfield( -name      => 'start',
                                      -value     => $start,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print "\n" ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "End: "),
            $cgi->td({ -class => "string" },
                     $cgi->textfield( -name      => 'end',
                                      -value     => $end,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print "\n" ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Fulfillment Channel "),
            $cgi->td({ -class => "string" },
                     $cgi->checkbox_group( -name => 'fulfillment_channel',
                                           -values => \@fulfillment_channel_options,
                                           -defaults => \@fc_defaults))
      ) ;
print "\n" ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Order Statuses"),
            $cgi->td({ -class => "string" },
                     $cgi->checkbox_group( -name => 'order_statuses',
                                           -values => \@order_status_options,
                                           -defaults => \@os_defaults))
      ) ;
print "\n" ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Verbose"),
            $cgi->td({ -class => "string" },
                     $cgi->checkbox( -name    => 'verbose',
                                     -checked => ($cgi->param('verbose')>0?'on':''),
                                     -label   => ''))) if($cgi->param('verbose')) ;
print $cgi->end_table() ;
print $cgi->submit( -name     => 'submit_form',
                    -value    => 'Submit') ;
print $cgi->end_form() ;

my @orders ;
my $orderItems ;
my $req ;
my @marketplaces ;
push @marketplaces, "ATVPDKIKX0DER" ;
my $arguments ;
$arguments->{CreatedAfter}       = $start if(defined $start) ;
$arguments->{CreatedBefore}      = $end   if($end ne '' )  ;
$arguments->{MarketplaceId}      = \@marketplaces ;
$arguments->{FulfillmentChannel} = \@fulfillment_channel_selected if(defined @fulfillment_channel_selected) ;
$arguments->{OrderStatus}        = \@order_statuses_selected      if(defined @order_statuses_selected) ;


if($cgi->param('verbose'))
{
    print $cgi->print("<BR>DEBUG: ". Dumper($arguments)) ;
}

if($start ne "" and defined $cgi->param('submit_form'))
{
    $req = $mws->ListOrders(%$arguments) ;
}

if( exists $req->{Orders}->{Order} )
{
    my $count = 1 ;
    print $cgi->br() ;
    print $cgi->a({-href => "#", -id=>"xx"}, "Download Table") ;
    print "<TABLE id=\"downloadabletable\"><tr>" .
          "<th>Id</th>"                                  .
          "<th>Amazon Order Id</th>"                     .
          "<th>Purchase Date</th>"                       .
          "<th>Latest Ship Date</th>"                    .
          "<th>Order Type</th>"                          .
          "<th>Fulfillment Channel</th>"                 .
          "<th>Is Prime</th>"                            .
          "<th>Order Total</th>"                         .
          "<th>Order Status</th>"                        .
          "<th>Last Update Date</th>"                    .
          "<th>Shipment Service Level Category</th>"     .
          "</tr> \n" ;
    while(1)
    {
        foreach my $order (@{$req->{Orders}->{Order}})
        {
            print "<tr>" ;
            print &format_html_column($count++,0,"number") ;
            print &format_html_column("<a href=order.cgi?SOURCE_ORDER_ID=$order->{AmazonOrderId}>$order->{AmazonOrderId}</a>",0,"string") ;
            print &format_html_column(&format_date($order->{PurchaseDate}),0,"string") ;
            print &format_html_column(&format_date($order->{LatestShipDate}),0,"string") ;
            print &format_html_column($order->{OrderType},0,"string") ;
            print &format_html_column($order->{FulfillmentChannel},0,"string") ;
            print &format_html_column($order->{IsPrime},0,"string") ;
            print &format_html_column(&format_currency($order->{OrderTotal}->{Amount},2),0,"number") ;
            print &format_html_column($order->{OrderStatus},0,"string") ;
            print &format_html_column(&format_date($order->{LastUpdateDate}),0,"string") ;
            print &format_html_column($order->{ShipmentServiceLevelCategory},0,"string") ;
            print "</tr>" ;
        }
        last if( not defined $req->{NextToken} ) ;
        $req = $mws->ListOrdersByNextToken(NextToken => $req->{NextToken}) ;
    }
    print "</TABLE>\n" ;
}

# just load jquery library before referecinng $(document)
print q(
<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>
<script type="text/javascript" src="mkp_js.js"></script>
) ;

print $cgi->end_html() ;
