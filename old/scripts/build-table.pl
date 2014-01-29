#!/usr/bin/perl

use strict;
use warnings;
use POSIX qw/strftime/;
use sort 'stable';

# the current assignment number
my $assNo = 4;

# files to look for
my %urls;

# an array of assignment scores for each user
my %users;
my %valid_users;
# a parallel hash of sort keys (sometimes different from the scores)
my %sort_scores;

# an array of modification dates for each user
my %dates;

# sort directions
my %sort_direction = (
  0 => "descending",
  1 => "ascending",    # AER
  2 => "descending",
  3 => "descending",
  4 => "descending",
);
  
# read in the valid users
open READ, "users.txt" or die;
while (my $line = <READ>) {
    next unless $. >= 3;
    chomp($line);
    my @tokens = split(/\|/, $line);
    my (undef,$name,$email,$handle,$url) = @tokens;
    $handle =~ s/ //g;
    $valid_users{$handle} = 1;
}
close(READ);

# read in the data points for each user and assignment
foreach my $assignment (0,1,2,3,4) {
    foreach my $user (keys %valid_users) {
	my $file = "assignment$assignment.txt/$user";
	if (-e "$file/score") {
	    chomp(my $score = `cat $file/score`);
	    $users{$user}[$assignment] = $score;
	    $sort_scores{$user}[$assignment] = $score;
	    if ($score == -1) { # an error
		if ($sort_direction{$assignment} eq "ascending") {
		    $sort_scores{$user}[$assignment] = 999999999;
		} else {
		    $sort_scores{$user}[$assignment] = -999999999;
		}
	    }
	    $dates{$user}[$assignment] = (stat "$file/latest")[9] || "9328665630";
	}
    }
}

my @rows;
foreach my $user (sort by_user (keys %users)) {
  while (@{$users{$user}} < 5) {
    push(@{$users{$user}}, "-");
  }
  push(@{$users{$user}}, total($users{$user}));
  my $resultstr = join (", ", map { "\"$_\"" } @{$users{$user}});
  push @rows, "  [\"$user\", " . $resultstr . "],\n";
}

# @rows = sort by_column @rows;

print "var data = [\n";
map { print $_ } @rows;
print "];\n";

sub total {
  my $array = shift;

  my $sum = 0;
  my $num = 0;

  foreach my $item (@$array) {
      $item = 0 unless $item;
    next if $item eq "-" or $item eq "X";
    $sum += $item;
    $num++;
  }

  return sprintf("%.2f", 1.0 * $sum / $num);
}

sub by_user {
    return 1 if (! defined $users{$a}[$assNo]);
    return -1 if (! defined $users{$b}[$assNo]);

  # if the scores match, return the earliest-updated file
  if ($users{$a}[$assNo] eq $users{$b}[$assNo]) {
    return $dates{$a}[$assNo] <=> $dates{$b}[$assNo];
  }

  # else sort by score (descending)
  if ($sort_direction{$assNo} eq "ascending") {
    return $sort_scores{$a}[$assNo] <=> $sort_scores{$b}[$assNo];
  }

  # else
  return $sort_scores{$b}[$assNo] <=> $sort_scores{$a}[$assNo];
}

sub by_column {
  my @a = split /", "/, $a;
  my @b = split /", "/, $b;

  return $b[$assNo] <=> $a[$assNo];
}
