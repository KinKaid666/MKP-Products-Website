#!/usr/bin/perl -wT
use CGI qw(:standard) ;
use CGI::Carp qw(warningsToBrowser fatalsToBrowser) ;
use Email::Valid ;
use DBI ;
use strict ;

my $cgi = new CGI() ;
print $cgi->header() ;
print $cgi->start_html("Registration Results") ;

my $dbh = DBI->connect( "dbi:mysql:usertable", "usertable", "jutedi2") or
    &dienice("Can't connect to db: $DBI::errstr") ;

my $username = $cgi->param('username') ;
my $password = $cgi->param('password') ;
my $realname = $cgi->param('realname') ;
my $email = $cgi->param('email') ;

# be sure the username is alphanumeric - no spaces or funny characters
if ($username !~ /^\w{3,}$/) {
    &dienice("Please use an alphanumeric username at least 3 letters long, with no spaces.") ;   
}

# be sure their real name isn't blank
if ($realname eq "") {
    &dienice("Please enter your real name.") ;
}

# be sure the password isn't blank or shorter than 6 chars
if (length($password) < 6) {
    &dienice("Please enter a password at least 6 characters long.") ;
}

# be sure they gave a valid e-mail address
unless (Email::Valid->address($email)) {
    &dienice("Please enter a valid e-mail address.") ;
}

# check the db first and be sure the username isn't already registered

my $sth = $dbh->prepare("select * from users where username = ?") or &dbdie ;
$sth->execute($username) or &dbdie ;
if (my $rec = $sth->fetchrow_hashref) {
    &dienice("The username `$username' is already in use. Please choose
another.") ;
}

# we're going to encrypt the password first, then store the encrypted
# version in the database.
my $encpass = &encrypt($password) ;

$sth = $dbh->prepare("insert into users values(?, ?, ?, ?, ?)")  or &dbdie ;
$sth->execute($username, $encpass, "CURRENT", $realname, $email)  or &dbdie ;

print qq(<p>
You're now registered!  Your username is <b>$username</b>, and your
password is <b>$password</b>.  Login <a href="/login.cgi">here</a>.</p>\n) ;

print $cgi->end_html() ;

sub encrypt {
    my($plain) = @_ ;
    my(@salt) = ('a'..'z', 'A'..'Z', '0'..'9', '.', '/') ;
    return crypt($plain, $salt[int(rand(@salt))] .  $salt[int(rand(@salt))] 	) ;
}

sub dienice {
    my($msg) = @_ ;
    print "<h2>Error</h2>\n" ;
    print $msg ;
    exit ;
}

sub dbdie {
    my($package, $filename, $line) = caller ;
    my($errmsg) = "Database error: $DBI::errstr<br>
                called from $package $filename line $line" ;
    &dienice($errmsg) ;
}

