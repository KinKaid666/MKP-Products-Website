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
use MKPUser ;

use constant LAST_USER_VIEWS => qq(
    select u.realname, uv.page, uv.remote_ip, uv.creation_time from user_views uv join users u on u.username = uv.username where uv.creation_time >= date_format(NOW(), "%Y-%m-%d") order by uv.creation_time desc limit 5
) ;

use constant TRENDING_SKUS => qq(
    select substring(page, instr(page,'SKU=')+4) sku, count(1) views from user_views where lower(page) like '%sku=%' group by substring(page, instr(page,'SKU=')+4) order by count(1) desc
) ;

use constant TRENDING_PAGES => qq(
    select substring_index(page,'?',1) page, count(1) views from user_views where creation_time > NOW() - INTERVAL 7 DAY group by substring_index(page,'?',1) order by views desc ;
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Financials",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

{
    print $cgi->h3("Last 5 Page Views") ;
    my $s_sth = $userdbh->prepare(${\LAST_USER_VIEWS}) ;
    $s_sth->execute() or die $DBI::errstr ;
    print "<TABLE><TR>"   .
          "<TH>User</TH>" .
          "<TH>Page</TH>" .
          "<TH>IP</TH>"   .
          "<TH>Time (Eastern)</TH>" .
          "</TR> \n" ;
    while (my $ref = $s_sth->fetchrow_hashref())
    {
        print "<TR>\n" ;
        print "<TD class=string>$ref->{realname}     </TD>\n" ;
        print "<TD class=string>$ref->{page}         </TD>\n" ;
        print "<TD class=string>$ref->{remote_ip}    </TD>\n" ;
        print "<TD class=string>$ref->{creation_time}</TD>\n" ;
        print "</TR>\n" ;
    }
    print "</TABLE>\n" ;
    $s_sth->finish() ;
}

{
    print $cgi->h3("Trending Pages") ;
    my $s_sth = $userdbh->prepare(${\TRENDING_PAGES}) ;
    $s_sth->execute() or die $DBI::errstr ;
    print "<TABLE><TR>"    .
          "<TH>Page</TH>"  .
          "<TH>Views</TH>" .
          "</TR> \n" ;
    while (my $ref = $s_sth->fetchrow_hashref())
    {
        print "<TR>\n" ;
        print "<TD class=string>$ref->{page} </TD>\n" ;
        print "<TD class=string>$ref->{views}</TD>\n" ;
        print "</TR>\n" ;
    }
    print "</TABLE>\n" ;
    $s_sth->finish() ;
}

{
    print $cgi->h3("Trending SKUs") ;
    my $s_sth = $userdbh->prepare(${\TRENDING_SKUS}) ;
    $s_sth->execute() or die $DBI::errstr ;
    print "<TABLE><TR>"    .
          "<TH>SKU</TH>"   .
          "<TH>Views</TH>" .
          "</TR> \n" ;
    while (my $ref = $s_sth->fetchrow_hashref())
    {
        print "<TR>\n" ;
        print "<TD class=string>$ref->{sku}  </TD>\n" ;
        print "<TD class=string>$ref->{views}</TD>\n" ;
        print "</TR>\n" ;
    }
    print "</TABLE>\n" ;
    $s_sth->finish() ;
}
