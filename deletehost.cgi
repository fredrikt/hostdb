#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to delete host objects
#

use strict;
use HOSTDB;
use SUCGI;

my $table_blank_line = "<tr><td COLSPAN='2'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='2'><hr></td></tr>\n";

my $debug = 0;
if (defined($ARGV[0]) and $ARGV[0] eq "-d") {
	shift (@ARGV);
	$debug = 1;
}

my $hostdb = HOSTDB::DB->new (inifile => HOSTDB::get_inifile (),
			      debug => $debug
			     );

my $hostdbini = $hostdb->inifile ();

my $sucgi_ini;
if (-f $hostdbini->val ('sucgi', 'cfgfile')) {
	$sucgi_ini = Config::IniFiles->new (-file => $hostdbini->val ('sucgi', 'cfgfile'));
} else {
	warn ("No SUCGI config-file ('" . $hostdbini->val ('sucgi', 'cfgfile') . "')");
}

my $q = SUCGI->new ($sucgi_ini);
my %links = $hostdb->html_links ($q);

$q->begin (title => 'Delete Host');
my $remote_user = '';
if (defined ($ENV{REMOTE_USER}) and $ENV{REMOTE_USER} =~ /^[a-z0-9]{,50}$/) {
	$remote_user = $ENV{REMOTE_USER};
} else {
	#$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
	#$q->end ();
	#die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");

	# XXX JUST FOR DEBUGGING UNTIL PUBCOOKIE IS FINISHED
	$remote_user = 'ft';
}
my $is_admin = $hostdb->auth->is_admin ($remote_user);

my (@links, @admin_links);
push (@admin_links, "[<a HREF='$links{netplan}'>netplan</a>]") if ($is_admin and $links{netplan});
push (@links, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@links, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}


$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='600'>
		$table_blank_line
		<tr>
			<td ALIGN='center'>
				<h3>HOSTDB: Delete Host</h3>
			</td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH



my $action = $q->param('action');
$action = 'Search' unless $action;
SWITCH:
{
	my $id = $q->param('id');
	my $host;

	$host = $hostdb->findhostbyid ($id);
	error_line ($q, "$0: Could not find host object with ID '$id'\n"), last SWITCH unless (defined ($host));

	$action eq 'Delete' and do
	{
		my $ip = $host->ip ();
		
		# get subnet
		my $subnet = $hostdb->findsubnetbyip ($host->ip ());

		# get zone
		my $zone = $hostdb->findzonebyhostname ($host->hostname ());

		# check that user is allowed to edit both zone and subnet
		my $authorized = 1;

		if (! $is_admin) {
			if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
				error_line ($q, "You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
			}

			# if there is no zone, only base desicion on subnet rights
			if (defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
				error_line ($q, "You do not have sufficient access to zone '" . $zone->zone () . "'");
				$authorized = 0;
			}
		}

		if ($authorized) {
			my $identify_str = "id:'" . ($host->id () || 'no id') . "' hostname:'" . ($host->hostname () || 'no hostname') . "' ip:'" . ($host->ip () || 'no ip') . "'";

			if (delete_host ($hostdb, $host, $q)) {
				my $i = localtime () . " deletehost.cgi[$$]";
				warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) deleted the following host -- $identify_str\n");

				my @links;
				
				$q->print (<<EOH);
					<tr>
						<td COLSPAN='2'><strong><font COLOR='red'>Host deleted</font></strong></td>
					</tr>
EOH
				if (defined ($subnet) and $links{showsubnet}) {
					my $s = $subnet->subnet ();
			
					my $link = "<a HREF='$links{showsubnet};subnet=$s'>Show subnet</a>";
				
					push (@links, <<EOH);
						<tr>
							<td COLSPAN='2'>&nbsp;&nbsp;[$link $s]<br></td>
						</tr>
EOH
				}
		
				if ($links{modifyhost}) {
					$ip = "<a HREF='$links{modifyhost};ip=$ip'>New host</a> with IP $ip";

					push (@links, <<EOH);
						<tr>
							<td COLSPAN='2'>&nbsp;&nbsp;[$ip]</td>
						</tr>
EOH
				}

				if (@links) {
					$q->print (<<EOH);

					$table_blank_line

					<tr>
						<td COLSPAN='2'><strong>Courtesy links :</td>
					</tr>
					@links
EOH
				}
			} else {
				error_line ($q, "Delete failed: $host->{error}");
			}
		}
	},last SWITCH;

	print_host_info ($q, $hostdb, $host);
	delete_form ($q, $host);
}

if ($@) {
	error_line($q, "$@\n");
}

$q->print (<<EOH);
	</table>
EOH

$q->end();


sub delete_host
{
	my $hostdb = shift;
	my $host = shift;
	my $q = shift;
	
	if ($q->param ("_hostdb.deletehost") ne "yes") {
		error_line ($q, "Delete without verification not supported, don't try to trick me.");
		return undef;
	}

	eval {
		die ("No host object") unless ($host);

		$host->delete ("YES");
	};
	if ($@) {
		chomp ($@);
		error_line ($q, "Failed to delete host: $@: $host->{error}");
		return 0;
	}
	
	return 1;
}

sub delete_form
{
	my $q = shift;
	my $host = shift;

	# HTML 
        my $state_field = $q->state_field ();
	my $delete = $q->submit ('action', 'Delete');
	my $me = $q->state_url ();
	my $id = $host->id ();

	$q->print (<<EOH);
		<tr>
			<td ALIGN='right'><font COLOR='red'><strong>Are you SURE you want to delete this host?</strong></font></td>
			<td ALIGN='right'>
			   <form ACTION='$me' METHOD='post'>
				$state_field
		                <input TYPE='hidden' NAME='id' VALUE='$id'>
				<input TYPE='hidden' NAME='_hostdb.deletehost' VALUE='yes'>
				$delete
			   </form>
			</td>
		</tr>
		
		$table_blank_line
EOH

	return 1;
}

sub print_host_info
{
	my $q = shift;
	my $hostdb = shift;
	my $host = shift;
	
	return undef if (! defined ($host));

	# HTML
	my $me = $q->state_url();
	my $id = $host->id ();
	my $parent = $host->partof ()?$host->partof ():'-';
	$parent = "<a href='$links{whois};whoisdatatype=ID;whoisdata=$parent'>$parent</a>" if ($parent ne '-' and $links{whois});
	my $ip = $host->ip ();
	my $mac = $host->mac_address () || '';
	my $hostname = $host->hostname ();
	my $comment = $host->comment () || '';
	my $owner = $host->owner ();

	# get subnet
	my $subnet = $hostdb->findsubnetbyip ($host->ip () || $q->param ('ip'));
	my $subnet_link = $subnet->subnet ();
	$subnet_link = "<a HREF='$links{showsubnet};subnet=$subnet_link'>$subnet_link</a>" if ($links{showsubnet});

	
	$q->print (<<EOH);
	   <tr>
		<td>ID</td>
		<td><a HREF="$links{whois};whoisdatatype=ID;whoisdata=$id">$id</a>&nbsp;</td>
	   </tr>	
	   <tr>
		<td>Parent</td>
		<td>$parent</td>
	   </tr>
EOH

	my $t_host;
	foreach $t_host ($hostdb->findhostbypartof ($id)) {
		my $child = $t_host->id ()?$t_host->id ():'-';
		$child = "<a HREF='$me;whoisdatatype=ID;whoisdata=$child'>$child</a>";
		
		$q->print (<<EOH);
			<tr>
				<td>Child</td>
				<td>$child</td>
			</tr>
EOH
	}

	$q->print (<<EOH);
	   <tr>
		<td ALIGN='center'>---</td>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<td>IP address</td>
		<td><strong>$ip</strong></td>
	   </tr>	
	   <tr>
		<td>Subnet</td>
		<td>$subnet_link</td>
	   </tr>	
	   <tr>
		<td>MAC Address</td>
		<td>$mac</td>
	   </tr>	
	   <tr>
		<td>Hostname</td>
		<td><strong>$hostname</strong></td>
	   </tr>	
	   <tr>
		<td>Comment</td>
		<td>$comment</td>
	   </tr>	
	   <tr>
		<td>Owner</td>
		<td>$owner</td>
	   </tr>	
EOH

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
	my $i = localtime () . " deletehost.cgi[$$]";
	warn ("$i: $error\n");
}
