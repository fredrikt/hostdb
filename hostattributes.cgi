#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to view host attributes
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_cols = 4;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Host attributes', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, $me);
## end generic initialization

## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
HOSTDB::StdCGI::print_cgi_header ($q, 'Host attributes', $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

my $id = $q->param ('id');
my $host = $hostdb->findhostbyid ($id);

if (! defined ($host)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host with id '$id' found in database.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: No host with id '$id' found in database.");
}

# get subnet of host
my $subnet = $hostdb->findsubnetbyip ($host->ip ());

if (! $is_admin and ! $is_helpdesk) {
	if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
		$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You do not have permissions to access host attributes.</strong></font></ul>\n\n");
		$q->end ();
		die ("$0: Unauthorized host attribute access attempt.");
	}
}

if (! defined ($host)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host with id '$id' found in database.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: No host with id '$id' found in database.");
}

my @sectionfilter;
foreach my $t (split (',', $hostdbini->val ('host', 'semipublic_attributesections'))) {
    $t =~ s/^\s*(\S+)\s*$/$1/o;	# trim
    push (@sectionfilter, $t);
}
show_hostattributes ($q, $host, $is_admin, $is_helpdesk, \@sectionfilter);

$q->end ();


sub show_hostattributes
{
	my $q = shift;
	my $host = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my $attributesection_filter_ref = shift;

	return undef if (! defined ($host));

	# HTML
	my $id = $host->id ();
	my $ip = $host->ip ();
	my $hostname = $host->hostname () || 'NULL';

	my $host_link = '';
	$host_link = "<a HREF='$links{whois};whoisdatatype=ID;whoisdata=$id'>$id</a>" if ($links{whois});
	
	$q->print (<<EOH);
	   <table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
	   <tr>
		<th ALIGN='left' COLSPAN='4'>Host :</th>
	   </tr>
	   $table_blank_line

	   <tr>
		<td WIDTH='33%'>&nbsp;ID</td>
		<td ALIGN='left' COLSPAN='3'>$host_link</td>
	   </tr>	
	   <tr>
		<td>&nbsp;IP address</td>
		<td ALIGN='left' COLSPAN='3'><strong>$ip</strong></td>
	   </tr>	
	   <tr>
		<td>&nbsp;Hostname</td>
		<td ALIGN='left' COLSPAN='3'><strong>$hostname</strong></td>
	   </tr>	

	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='2'>Attributes :</th>
		<th ALIGN='left'>Last modified</th>
		<th ALIGN='left'>Last updated</th>
	   </tr>
	   $table_blank_line

EOH

	my @attrs = $host->init_attributes ();

	my $lastsection = '';
	my $showsection = 0;

	foreach my $attr (sort attributesort @attrs) {
		my $section = $attr->section ();
					
		if ($section ne $lastsection) {
			if (! $is_admin and ! $is_helpdesk) {
				my @attributesection_filter = @$attributesection_filter_ref;
				# user is not helpdesk or admin, only show this section if the name of
				# this section occurs in @attributesection_filter, or if
				# @attributesection_filter is undefined.
				if (! defined (@attributesection_filter)) {
					$showsection = 1;
				} else {
					$showsection = 1 if (grep (/^${section}$/, @attributesection_filter));
				}

				$q->print ("<!-- SECTION $section SHOWSECTION $showsection -->\n");
			} else {
				$showsection = 1;
			}

			if ($showsection) {
				$q->print (<<EOH);
	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='4'>&nbsp;&nbsp;$section</th>
	   </tr>
EOH
			}

			$lastsection = $section;
		}

		if ($showsection) {
			my $key = $attr->key () || 'NULL';
			my $value = $attr->get () || 'NULL';
			my $lastmodified = $attr->lastmodified () || 'NULL';
			my $lastupdated = $attr->lastupdated () || 'NULL';

			$q->print (<<EOH);
		   <tr>
			<td NOWRAP>&nbsp;&nbsp;&nbsp;&nbsp;$key</td>
			<td>$value</td>
			<td NOWRAP>$lastmodified&nbsp;&nbsp;</td>
			<td NOWRAP>$lastupdated&nbsp;&nbsp;</td>
		   </tr>
EOH
		}
	}
				
	$q->print ("\t$table_blank_line\n\t</table>");

	return 1;
}

sub attributesort
{
	my $a_section = $a->section ();
	my $b_section = $b->section ();
	
	if ($a_section eq $b_section) {
		my $a_key = $a->key ();
		my $b_key = $b->key ();
		
		if ($a_key =~ /^(.*?)(\d+)$/) {
			my $a_prefix = $1;
			my $a_num = int ($2);
			
			if ($b_key =~ /^(.*?)(\d+)$/) {
				my $b_prefix = $1;
				my $b_num = int ($2);

				if ($a_prefix eq $b_prefix) {
					# both keys begin with the same text and ends in digits,
					# do numeric comparision
					
					return $a_num <=> $b_num;
				}
			}
		}
		
		return $a_key cmp $b_key;
	}

	return $a_section cmp $b_section;	
}

sub error_line
{
	my $q = shift;
	my $error = shift;
	chomp ($error);
	$q->print (<<EOH);
	   <tr>
		<td COLSPAN='4'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
	my $i = localtime () . " hostattributes.cgi[$$]";
	warn ("$i: $error\n");
}
