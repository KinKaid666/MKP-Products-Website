#!/usr/bin/perl -wT
use CGI::Carp qw(warningsToBrowser fatalsToBrowser);
use CGI qw(:standard);
use strict;

my $cgi = CGI->new() ;
print $cgi->header() ;
print $cgi->start_html("Login") ;

my $page = $ENV{QUERY_STRING} ;

print <<EndHTML ;
<form action="login2.cgi" method="POST">

Please login!
<br>
<br>
<input type="hidden" name="page" value="$page">

username: <input type="text" name="username" size=10><br>
password: <input type="password" name="password" size=10><p>

Be sure you have cookies turned on in your browser.<p>

<input type="submit" value="Log In">

</form>
EndHTML

print $cgi->end_html() ;
