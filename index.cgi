#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(warningsToBrowser fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

use constant LATEST_ORDER => qq(
    select date_format(max(order_datetime),"%Y-%m-%d") latest_order from sku_orders
) ;

use constant LATEST_INVENTORY => qq(
    select date_format(max(report_date),"%Y-%m-%d") latest_report from onhand_inventory_reports
) ;

my $cgi = CGI->new() ;

my $username = &validate() ;
my $sku   = $cgi->param('sku') || undef ;
my $order = $cgi->param('order') || undef ;

print $cgi->redirect( -url=>"/sku.cgi?SKU=$sku")                 if( defined $sku   ) ;
print $cgi->redirect( -url=>"/order.cgi?SOURCE_ORDER_ID=$order") if( defined $order ) ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Homepage", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );

my $dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                       "mkp_reporter",
                       "mkp_reporter_2018",
                       {'RaiseError' => 1});

{
    my $latest_sth = $dbh->prepare(${\LATEST_ORDER}) ;
    $latest_sth->execute() or die $DBI::errstr ;
    my $row = $latest_sth->fetchrow_hashref() ;

    print $cgi->i($cgi->b("Latest ")) ;
    print $cgi->i($cgi->b("order: ") . $row->{latest_order}) ;
}
{
    my $latest_sth = $dbh->prepare(${\LATEST_INVENTORY}) ;
    $latest_sth->execute() or die $DBI::errstr ;
    my $row = $latest_sth->fetchrow_hashref() ;

    print $cgi->i($cgi->b(" inventory: ") . $row->{latest_report}) ;
}
print $cgi->br() ;
print $cgi->br() ;
print $cgi->a({href => "/pl.cgi"}, "Profit and Loss Statement") ; print " " ;
print $cgi->a({href => "/pl.cgi?granularity=WEEKLY"}, "(weekly)") ;
print $cgi->br() ;
print $cgi->a({href => "/skupl.cgi"}, "SKU Performance" ) ;
print $cgi->br() ;
print $cgi->a({href => "/newbuy.cgi"}, "SKU Buying" ) ;
print $cgi->br() ;
print $cgi->br() ;

print $cgi->start_form(
    -name    => 'main_form',
    -method  => 'POST',
);
print $cgi->start_table ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "SKU Lookup:"),
            $cgi->td({ -class => "number" },
                     $cgi->textfield( -name      => 'sku',
                                      -value     => $sku,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->Tr(
            $cgi->td({ -class => "string" },
                     "Order Lookup:"),
            $cgi->td({ -class => "string" },
                     $cgi->textfield( -name      => 'order',
                                      -value     => $order,
                                      -size      => 20,
                                      -maxlength => 30,))
      ) ;
print $cgi->end_table() ;
print $cgi->submit( -name     => 'submit_form',
                    -value    => 'Submit') ;
print $cgi->end_form() ;
print $cgi->end_html() ;

