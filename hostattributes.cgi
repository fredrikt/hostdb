#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to view host attributes
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='3'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='3'><hr></td></tr>\n";
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

if (! $is_admin and ! $is_helpdesk) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You do not have permissions to access host attributes.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Unauthorized host attribute access attempt.");
}

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td ALIGN='left' COLSPAN='3'><h3>Host attributes :</h3></td>
		</tr>
		$table_blank_line
EOH

my $id = $q->param ('id');
my $host = $hostdb->findhostbyid ($id);

if (! defined ($host)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host with id '$id' found in database.</strong></font></ul>\n\n");
} else {
	show_hostattributes ($q, $host);
}

$q->print (<<EOH);
	</table>
EOH

$q->end ();


sub show_hostattributes
{
	my $q = shift;
	my $host = shift;
	
	return undef if (! defined ($host));

	# HTML
	my $id = $host->id ();
	my $ip = $host->ip ();
	my $hostname = $host->hostname () || 'NULL';

	my $host_link = '';
	$host_link = "<a HREF='$links{whois};whoisdatatype=ID;whoisdata=$id'>$id</a>" if ($links{whois});
	
	$q->print (<<EOH);
	   <tr>
		<th ALIGN='left' COLSPAN='3'>Host :</th>
	   </tr>
	   $table_blank_line

	   <tr>
		<td WIDTH='33%'>&nbsp;ID</td>
		<td ALIGN='left' COLSPAN='2'>$host_link</td>
	   </tr>	
	   <tr>
		<td>&nbsp;IP address</td>
		<td ALIGN='left' COLSPAN='2'><strong>$ip</strong></td>
	   </tr>	
	   <tr>
		<td>&nbsp;Hostname</td>
		<td ALIGN='left' COLSPAN='2'><strong>$hostname</strong></td>
	   </tr>	

	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='3'>Attributes :</th>
	   </tr>
	   $table_blank_line

EOH

	my @attrs = $host->init_attributes ();

	my $lastsection = '';

	foreach my $attr (@attrs) {
		my $key = $attr->key ();
		my $section = $attr->section ();
		my $value = $attr->get ();
					
		if ($section ne $lastsection) {
			$q->print (<<EOH);
	   <tr>
		<th ALIGN='left' COLSPAN='3'>&nbsp;&nbsp;$section</th>
	   </tr>
EOH
			$lastsection = $section;
		}
					
		$q->print (<<EOH);
	   <tr>
		<td>&nbsp;&nbsp;&nbsp;&nbsp;$key</td>
		<td COLSPAN='2'>$value</td>
	   </tr>
EOH
	}
				
	$q->print ($table_blank_line);	

	return 1;
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
