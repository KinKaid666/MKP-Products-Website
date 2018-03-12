#!/usr/bin/perl -w

use CGI qw(:standard);
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use strict;

# AMZL Specific Libraries
use lib "/home/ericferg/mkp/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

my $cgi = CGI->new() ;
my $user = $cgi->param('username');
my $pass = $cgi->param('password');
my $username = "";

my $sth = $userdbh->prepare("select * from users where username=?") or &dbdie;
$sth->execute($user);
if (my $rec = $sth->fetchrow_hashref) {
    my $salt = substr($rec->{password}, 0, 2);
    if ($rec->{password} ne crypt($pass, $salt) ) {
        &dienice(qq(You entered the wrong password.));
    }
    $username = $rec->{username};
} else {
    &dienice("Username <b>$user</b> does not exist.");
}
my $cookie_id = &random_id;
my $cookie = cookie(-name=>'cid', -value=>$cookie_id, -expires=>'+7d');

$sth = $userdbh->prepare("replace into user_cookies values(?, ?, current_timestamp(), ?)") or &dbdie;
$sth->execute($cookie_id, $username, $ENV{REMOTE_ADDR}) or &dbdie;

if ($cgi->param('page')) {
   my $url = $cgi->param('page');

   print $cgi->redirect(-location=>"http://prod.mkpproducts.com/$url", -cookie=>$cookie);
} else {
   print $cgi->redirect(-location=>"http://prod.mkpproducts.com", -cookie=>$cookie);
}

sub random_id {
    # This routine generates a 32-character random string
    # out of letters and numbers.
    my $rid = "";
    my $alphas = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    my @alphary = split(//, $alphas);
    foreach my $i (1..32) {
       my $letter = $alphary[int(rand(@alphary))];
       $rid .= $letter;
    }
    return $rid;
}
