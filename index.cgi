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

my $cgi = CGI->new() ;

my $sku   = $cgi->param('sku') || undef ;
my $order = $cgi->param('order') || undef ;

print $cgi->redirect( -url=>"/sku.cgi?SKU=$sku")                 if( defined $sku   ) ;
print $cgi->redirect( -url=>"/order.cgi?SOURCE_ORDER_ID=$order") if( defined $order ) ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Homepage", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );

print $cgi->a({href => "/pl.cgi"}, "Profit and Loss Statement") ;
print $cgi->br() ;
print $cgi->a({href => "/skupl.cgi"}, "SKU Performance Page" ) ;
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
print $cgi->Tr(
            $cgi->td(),
            $cgi->td($cgi->submit( -name     => 'submit_form',
                                   -value    => 'Submit')),
      );
print $cgi->end_table() ;
print $cgi->end_form() ;
print $cgi->end_html() ;
