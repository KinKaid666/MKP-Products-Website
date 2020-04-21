#!/usr/bin/perl -w

use strict ;
use warnings ;
use DBI ;
use CGI ;
use CGI::Carp qw(fatalsToBrowser); # Remove this in production
use POSIX ;
use Locale::Currency::Format ;

# AMZL Specific Libraries
use lib "/mkp/src/bin/lib" ;
use MKPFormatter ;
use MKPUser ;

use constant LAST_USER_VIEWS => qq(
    select u.realname
           , uv.page
           , uv.remote_ip
           , uv.creation_time
      from user_views uv
      join users u
        on u.username = uv.username
     where uv.creation_time > NOW() - INTERVAL 7 DAY
     order by uv.creation_time desc limit 10
) ;

use constant LAST_VIEW => qq(
    select u.realname
           , u.username
           , ifnull(latest.page,"N/A") page
           , ifNull(latest.creation_time,"N/A") creation_time
      from users u
      left outer join (
            select uv.username
                   , uv.page
                   , uv.creation_time
              from user_views uv
              join (
                    select iuv.username
                           , max(iuv.creation_time) creation_time
                      from user_views iuv
                     group by iuv.username
                   ) last_views
                on last_views.creation_time = uv.creation_time
               and last_views.username = uv.username
           ) latest
        on latest.username = u.username ;
) ;

use constant TRENDING_SKUS => qq(
    select substring(page, instr(page,'SKU=')+4) sku
           , count(1) views
      from user_views
     where lower(page) like '%sku=%'
     group by substring(page, instr(page,'SKU=')+4)
    having count(1) > 5
    order by count(1) desc
) ;

use constant TRENDING_PAGES => qq(
    select substring_index(page,'?',1) page
           , count(1) views
      from user_views
     where creation_time > NOW() - INTERVAL 7 DAY
     group by substring_index(page,'?',1)
     order by views desc
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;

print $cgi->header;
print $cgi->start_html( -title => "MKP Products Financials",
                        -style => {'src'=>'http://prod.mkpproducts.com/style.css'},
                        -head => [$cgi->Link({-rel=>'shortcut icon',
                                              -href=>'favicon.png'})]);

{
    print $cgi->h3("Last Login") ;
    my $s_sth = $userdbh->prepare(${\LAST_VIEW}) ;
    $s_sth->execute() or die $DBI::errstr ;
    print "<TABLE><TR>"             .
          "<TH>User</TH>"           .
          "<TH>Page</TH>"           .
          "<TH>Time (Eastern)</TH>" .
          "</TR> \n" ;
    while (my $ref = $s_sth->fetchrow_hashref())
    {
        print "<TR>\n" ;
        print "<TD class=string>$ref->{realname}</TD>\n" ;
        if( $ref->{page} eq "N/A" )
        {
            print "<TD class=string>$ref->{page}</TD>\n" ;
        }
        else
        {
            print "<TD class=string><a href=$ref->{page}>$ref->{page}</a></TD>\n" ;
        }
        print "<TD class=string>$ref->{creation_time}</TD>\n" ;
        print "</TR>\n" ;
    }
    print "</TABLE>\n" ;
    $s_sth->finish() ;
}
{
    print $cgi->h3("Last 10 Page Views") ;
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
        print "<TD class=string><a href=$ref->{page}>$ref->{page}</a></TD>\n" ;
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
        print "<TD class=string><a href=$ref->{page}>$ref->{page}</a></TD>\n" ;
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
        print "<TD class=string><a href=sku.cgi?SKU=$ref->{sku}>$ref->{sku}</a></TD>\n" ;
        print "<TD class=string>$ref->{views}</TD>\n" ;
        print "</TR>\n" ;
    }
    print "</TABLE>\n" ;
    $s_sth->finish() ;
}
