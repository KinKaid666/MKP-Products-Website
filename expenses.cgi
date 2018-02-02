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

use constant MONTHLY_EXPENSES_SELECT_STATEMENT => qq(
    select year(expense_datetime) year
           ,month(expense_datetime) month
           ,sum(total) total
           ,case when type = 'Consulting' or type = 'Salary' or type = 'Rent' then 'SG&A' else 'Expense' end category
           ,type
           ,description
      from expenses
     where year(expense_datetime) = ?
       and month(expense_datetime) = ?
     group by year(expense_datetime)
              ,month(expense_datetime)
              ,type
              ,description
     order by year(expense_datetime)
              ,month(expense_datetime)
              ,total
) ;

use constant WEEKLY_EXPENSES_SELECT_STATEMENT => qq(
    select date_format(expense_datetime,"%X-%V") period
           ,sum(total) total
           ,case when type = 'Consulting' or type = 'Salary' or type = 'Rent' then 'SG&A' else 'Expense' end category
           ,type
           ,description
      from expenses
     where date_format(expense_datetime,"%X-%V") = ?
     group by date_format(expense_datetime,"%X-%V")
              ,type
              ,description
     order by date_format(expense_datetime,"%X-%V")
              ,total
) ;

my $username = &validate() ;
my $cgi = CGI->new() ;
my $year  = $cgi->param('YEAR') || undef ;
my $month = $cgi->param('MONTH') || undef ;
my $week  = $cgi->param('WEEK') || undef ;
print $cgi->header;
print $cgi->start_html( -title => "MKP Products Expenses Details", -style => {'src'=>'http://prod.mkpproducts.com/style.css'} );

my $dbh ;
$dbh = DBI->connect("DBI:mysql:database=mkp_products;host=localhost",
                    "mkp_reporter",
                    "mkp_reporter_2018",
                    {'RaiseError' => 1});

my $expenses_sth ;
if( defined $week )
{
    $expenses_sth = $dbh->prepare(${\WEEKLY_EXPENSES_SELECT_STATEMENT}) ;
    $expenses_sth->execute("$year-$week") or die $DBI::errstr ;
}
else
{
    $expenses_sth = $dbh->prepare(${\MONTHLY_EXPENSES_SELECT_STATEMENT}) ;
    $expenses_sth->execute($year,$month) or die $DBI::errstr ;
}


print "<TABLE><TR>"                  .
      "<TH>Year</TH>"                .
      "<TH>" . (defined $week ? "Week" : "Month") . "</TH>" .
      "<TH>Category</TH>"            .
      "<TH>Expense Type</TH>"        .
      "<TH>Expense Description</TH>" .
      "<TH>Expenses</TH>"            .
      "</TR> \n" ;
my $expenses = 0 ;
while (my $ref = $expenses_sth->fetchrow_hashref())
{
    my ($y, $m_or_w) ;
    if( defined $week )
    {
        ($y, $m_or_w) = split( '-', $ref->{period} ) ;
    }
    else
    {
        $y      = $ref->{year} ;
        $m_or_w = $ref->{month} ;
    }
    print "<TR>" ;
    print "<TD class=number>$y</TD>" ;
    print "<TD class=number>$m_or_w</TD>" ;
    print "<TD class=string>$ref->{category}</TD>" ;
    print "<TD class=string>$ref->{type}</TD>" ;
    print "<TD class=string>$ref->{description}</TD>" ;
    print "<TD class=number" . &add_neg_tag($ref->{total})   . ">" . &format_currency($ref->{total},2)  . "</TD>" ;
    print "</TR>" ;
    $expenses += $ref->{total} ;
}
print "<TR><TD colspan=\"5\"><strong>Total</strong></TD>" ;
print "<TD class=number" . &add_neg_tag($expenses)   . "><strong>" . &format_currency($expenses,2)  . "</strong></TD>" ;
print "</TR>\n" ;
print "</TABLE>\n" ;
$expenses_sth->finish() ;

sub add_neg_tag
{
    my $number = shift || 0 ;
    return ($number < 0 ? "-neg" : "" ) ;
}

