#!/usr/bin/perl -wT
use CGI qw(:standard);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use strict;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

my $username = &validate() ;
my $cgi = CGI->new() ;

# get the cookie data
my $sth = $userdbh->prepare("select * from user_cookies where username=?") or &dbdie;
$sth->execute($username) or &dbdie ;
my $rec = $sth->fetchrow_hashref ;

# set a new cookie that expires NOW
my $cookie = cookie(-name=>'cid', -value=>$rec->{cookie_id}, -expires=>'now') ;

# and delete the cookie from the user_cookies database too
$sth = $userdbh->prepare("delete from user_cookies where username=?") or &dbdie ;
$sth->execute($username) or &dbdie ;

print $cgi->header(-cookie=>$cookie) ;
print $cgi->start_html( -title => "MKP Logout Page",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

print qq(<h2>Goodbye!</h2>\n) ;
print qq(You are now logged out.<br>\n) ;
print $cgi->end_html() ;
