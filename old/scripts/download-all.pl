#!/usr/bin/perl

use strict;
use warnings;
use LWP::Simple;
use POSIX qw/strftime/;
use Scalar::Util qw/looks_like_number/;
use Time::Local;
use List::Util qw/max/;

# files to look for
my @files = qw/assignment4.txt/;

# Due dates.  The format is (second, minute, hour, date, (month-1),
# year).  Yes, you read that right: the month is given in months since
# January (0..11).
my %due = (
    'assignment1.txt' => timelocal(0,0,0,23,1,2012),
    'assignment2.txt' => timelocal(0,0,0,2,3,2012),
    'assignment3.txt' => timelocal(0,0,0,04,3,2012),
    'assignment4.txt' => timelocal(0,0,0,16,3,2012),
);

# always do score if true
my $force_scoring = 0;

# verbose
my $verbose = shift || 0;

# storage
my %urls;

# read in the list of users and base URLs
open URLs, "users.txt" or die "can't read users.txt file";
while (my $line = <URLs>) {
  my @tokens = split('\|', $line);
  next unless @tokens == 6;
  map { $_ =~ s/^\s+|\s+$//g; } @tokens;
  my (undef,$name,$email,$handle,$base_url) = @tokens;
  next if $name eq "Name";

  $handle =~ s/ //g;

  $base_url .= "/" unless $base_url =~ /\/$/;
  $urls{$handle} = $base_url;
}
close(URLs);

foreach my $assignment (@files) {
    # if (time() > $due{$assignment}) {
    # 	print STDERR "Skipping past-due assignment $assignment\n"
    # 	    if $verbose;
    # 	next;
    # }

    print STDERR "Processing $assignment\n"
	if $verbose;
    
  foreach my $user (keys %urls) {
    my $url = $urls{$user} . $assignment;

    # download the file
    my $rundir = "$assignment/$user";
    system("mkdir -p $rundir") unless -d $rundir;
    my $datestr = strftime "%F-%H-%M", localtime;
    my $filename = "$assignment.$datestr";
    my $retval = getstore($url, "$rundir/$filename");
    if ($retval == 200) {
	print STDERR "  -> found $user ($url) [$retval]\n"
	    if $verbose;

      # if it was downloaded, see if it changed
      if (-e "$rundir/latest") {
        # if the files are different
        if (system("diff $rundir/latest $rundir/$filename > /dev/null")) {
          # move the old file
          unlink "$rundir/score";

          # update the symlink
          system("ln -sf $filename $rundir/latest");

          print STDERR "    --> updating new document\n"
	      if $verbose;
        } else {
          # file not new, delete it
          unlink "$rundir/$filename";
        }
      } else {
        # first download -- update symlink
        system("ln -sf $filename $rundir/latest");
      }

      if (-e "$rundir/latest" and (! -e "$rundir/score" or $force_scoring)) {
        my $score = score($assignment,$user);

        system("echo $score > $rundir/score");
      }
    }
  }
}

sub score {
  my ($assignment,$user) = @_;

  if ($assignment eq "assignment0.txt") {
      return score_number($user);
  } elsif ($assignment eq "assignment1.txt") {
      return score_alignments($user);
  } elsif ($assignment eq "assignment2.txt") {
      return score_translations($user);
  } elsif ($assignment eq "assignment3.txt") {
      return score_evaluation($user);
  } elsif ($assignment eq "assignment4.txt") {
      return score_reranker($user);
  }
}

# recompute oracle score
my $total = 0.0;
open CMD, "paste assignment2.txt/*/scores | head -n 48 |" or die;
while (my $scores = <CMD>) {
    chomp($scores);
    my @tokens = split(' ', $scores);
    $total += max(@tokens);
}
close CMD;
system("echo $total > assignment2.txt/oracle/score");


sub score_translations {
    my ($user) = @_;
    
    my $output = "assignment2.txt/$user/latest";

    my $datadir = "/users/post/code/mt-class/hw/dreamt/decoder/data";
    my $input = "$datadir/input";
    my $tm = "$datadir/tm";
    my $lm = "$datadir/lm";
    my $grade = "/users/post/code/mt-class/hw/dreamt/decoder/grade";

    # make sure the output has the right number of lines
    my $linecount = countlines($output);
    if ($linecount != 48) {
	return -1;
    }

    my $cmd = "cat $output | $grade -i $input -t $tm -l $lm -v 1 2> /dev/null | egrep 'Total sentence|Total corpus' | awk '{print \$NF}' | tee assignment2.txt/$user/scores | tail -n1";
#    print "$cmd\n";
    chomp(my $score = `$cmd`);
    return $score;
}


sub score_alignments {
    my ($user) = @_;

    my $file = "assignment1.txt/$user/latest";

    my $data = "/users/post/code/mt-class/hw/dreamt/aligner/gold_data";
    my $check = "/users/post/code/mt-class/hw/dreamt/aligner/check";
    my $grade = "/users/post/code/mt-class/hw/dreamt/aligner/grade";

    # make sure the output has the right number of lines
    my $linecount = countlines($file);
    if ($linecount != 100000) {
	return -1;
    }

    # check the output
    my $ok = system("cat $file | $check -d $data/hansards 2>&1 | grep ERROR > /dev/null");
    if ($ok == 0) { # bad, found error
	return -1;
    }

    chomp(my $score = `paste $data/sort_key assignment1.txt/$user/latest| sort -n | cut -f 2- | $grade -d $data/hansards -n 0 | tail -n1 | awk '{print \$NF}'`);
    return sprintf("%.2f", $score * 100.0);
}


sub score_number {
  my ($user) = @_;

  my $file = "assignment0.txt/$user/latest";
  return 0 unless -e $file;

  chomp(my $number = `head -n1 $file`);

  if (! looks_like_number($number) or $number <= 0) {
      return 0;
  } else {
      return ($number - 1) % 100 + 1;
  }
}

sub score_evaluation {
    my ($user) = @_;

    my $file = "assignment3.txt/$user/latest";
    return 0 unless -e $file;

    # only score once per day -- return the old score if it was
    # generated in the past 24 hours
    my $scorefile = "assignment3.txt/$user/score";
    my $curtime = time();
    if (-e $scorefile && ($curtime - (stat $scorefile)[9]) > 43200) {
	chomp(my $score = `cat $scorefile`);
	return $score;
    }

    # if the score file doesn't exist, or it's old, update it
    my $datadir = "/users/post/code/mt-class/hw/dreamt/evaluator/data";
    my $grade = "/users/post/code/mt-class/hw/dreamt/evaluator/grade";

    # make sure the output has the right number of lines
    my $linecount = countlines($file);
    if ($linecount != 20) {
	return -1;
    }

    my $cmd = "cat $file | $grade -k $datadir/answer_key.test";

    chomp(my $score = `$cmd`);
    return sprintf("%.2f", $score * 100.0);
}

# score the reranking assignment
sub score_reranker {
    my ($user) = @_;

    my $file = "assignment4.txt/$user/latest";

    my $datadir = "/users/post/code/mt-class/hw/dreamt/reranker/data";
    my $grade = "/users/post/code/mt-class/hw/dreamt/reranker/grade";

    my $linecount = countlines($file);
    return -1 unless $linecount == 500;
    
    my $cmd = "tail -n 250 $file | /users/alopez/bin/python $grade -r $datadir/hidden-test.en";
    chomp(my $score = `$cmd`);

    return sprintf("%.2f", $score * 100);
}



# wc does not count lines that aren't newline-terminated
sub countlines {
    my ($file) = @_;

    my $numlines = 0;

    open READ, $file or return 0;
    while (my $line = <READ>) {
	$numlines++;
    }
    close(READ);

    return $numlines;
}
