#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to view host attributes
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";
my $empty_td = "<td>&nbsp;</td>\n";

my $debug = 0;
if (defined ($ARGV[0]) and ($ARGV[0] eq "-d")) {
	shift (@ARGV);
	$debug = 1;
}

my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());
my $sucgi_ini;
if (-f $hostdbini->val ('sucgi', 'cfgfile')) {
	$sucgi_ini = Config::IniFiles->new (-file => $hostdbini->val ('sucgi', 'cfgfile'));
} else {
	warn ("No SUCGI config-file ('" . $hostdbini->val ('sucgi', 'cfgfile') . "')");
}
my $q = SUCGI2->new ($sucgi_ini, 'hostdb');
$q->begin (title => 'Host attributes');

my $hostdb = eval {
	HOSTDB::DB->new (ini => $hostdbini, debug => $debug);
};

if ($@) {
	my $e = $@;
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>Could not create HOSTDB object: $e</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not create HOSTDB object: '$e'");
}

my %links = $hostdb->html_links ($q);

my $remote_user = $q->user();
unless ($remote_user) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");
}
my $is_admin = $hostdb->auth->is_admin ($remote_user);
my $is_helpdesk = $hostdb->auth->is_helpdesk ($remote_user);

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
} else {
	$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td ALIGN='left' COLSPAN='4'><h3>Host attributes :</h3></td>
		</tr>
		$table_blank_line
EOH

	my @sectionfilter;
	foreach my $t (split (',', $hostdbini->val ('host', 'semipublic_attributesections'))) {
		$t =~ s/^\s*(\S+)\s*$/$1/o;	# trim
		push (@sectionfilter, $t);
	}
	show_hostattributes ($q, $host, $is_admin, $is_helpdesk, \@sectionfilter);
}

$q->print (<<EOH);
	</table>
EOH

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
				
	$q->print ($table_blank_line);	

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
