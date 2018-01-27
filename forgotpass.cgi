#!/usr/bin/perl -wT
use CGI qw(:standard) ;
use CGI::Carp qw(fatalsToBrowser) ;
use DBI ;
use Email::Valid ;
use strict ;

my $cgi = CGI->new() ;
print $cgi->header;
print $cgi->start_html("Password Change Results");

my $dbh = DBI->connect( "dbi:mysql:usertable", "usertable", "jutedi2") or &dienice("Can't connect to db: $DBI::errstr");

my $username = $cgi->param('username');
my $email = $cgi->param('email');

unless (Email::Valid->address($email)) {
   &dienice("`$email' doesn't appear to be a valid e-mail address.");
}

my $sth = $dbh->prepare("select * from users where username = ?") or &dbdie;
$sth->execute($username) or &dbdie;
if (my $uinfo = $sth->fetchrow_hashref) {
   # even if the username is valid, we want to check and be sure the email
   # address matches.
   if ($uinfo->{email} !~ /$email/i) {
       &dienice("Either your username or e-mail address was not found.");
   }
} else {
    &dienice("Either your username or e-mail address was not found.");
}

# ok, it's a valid user. First, we create a random password.  This uses
# the random password code from chapter 10.
my $randpass = &random_password();

# now we encrypt it:
my $encpass = &encrypt($randpass);

# now store it in the database...
$sth = $dbh->prepare("update users set password=? where username=?")  or &dbdie;
$sth->execute($encpass, $username) or &dbdie;

# ...and send email to the person telling them their new password.
# be sure to send them the un-encrypted version! 
$ENV{PATH} = "/usr/sbin";
open(MAIL,"|/usr/sbin/sendmail -t -oi");
print MAIL "To: $email\n";
print MAIL "From: webmaster\n";
print MAIL "Subject: Your FooWeb Password\n\n";
print MAIL <<EndMail;
Your FooWeb Password has been changed. The new password is '$randpass'.

You can login and change your password at 
http://www.cgi101.com/book/ch20/secure2/passchg.html.
EndMail

print qq(<h2>Success!</h2>
<p>Your password has been changed!  A new password has been e-mailed to you.</p>\n);
print end_html;

sub encrypt {
    my($plain) = @_;
    my(@salt) = ('a'..'z', 'A'..'Z', '0'..'9', '.', '/');
    return crypt($plain, $salt[int(rand(@salt))] . $salt[int(rand(@salt))] 	);
}

sub random_password {
    my($length) = @_;
    if ($length eq "" or $length < 3) {
        $length = 6;            # make it at least 6 chars long.
    }
    my @letters = ('a'..'z', 'A'..'Z', '0'..'9');
    my $randpass = "";
    foreach my $i (0..$length-1) {
      $randpass .= $letters[int(rand(@letters))];
    }
    return $randpass;
}

sub dienice {
    my($msg) = @_;
    print "<h2>Error</h2>\n";
    print $msg;
    exit;
}


sub dbdie {
    my($package, $filename, $line) = caller;
    my($errmsg) = "Database error: $DBI::errstr<br>
                called from $package $filename line $line";
    &dienice($errmsg);
}
