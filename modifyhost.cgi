#!/usr/local/bin/perl
#
# $Id$
#
# cgi-script to modify/create/delete host objects
#

use strict;
use Config::IniFiles;
#use lib 'blib/lib';
use HOSTDB;
use SUCGI;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";

my $debug = 0;
if (defined($ARGV[0]) and $ARGV[0] eq "-d") {
	shift (@ARGV);
	$debug = 1;
}

my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());
die ("$0: Config file access problem.\n") unless ($hostdbini);

my $hostdb = HOSTDB::DB->new (dsn => $hostdbini->val ('db', 'dsn'),
			  db => $hostdbini->val ('db', 'database'),
			  user => $hostdbini->val ('db', 'user'),
			  password => $hostdbini->val ('db', 'password'),
			  debug => $debug
			 );

my $sucgi_ini;
if (-f $hostdbini->val ('sucgi', 'cfgfile')) {
	$sucgi_ini = Config::IniFiles->new (-file => $hostdbini->val ('sucgi', 'cfgfile'));
} else {
	warn ("No SUCGI config-file ('" . $hostdbini->val ('sucgi', 'cfgfile') . "')");
}

my $q = SUCGI->new ($sucgi_ini);

my $showsubnet_path = $q->state_url($hostdbini->val('subnet','showsubnet_uri'));
my $modifyhost_path = $q->state_url($hostdbini->val('subnet','modifyhost_uri'));

$q->begin (title => 'Modify/Add/Delete Host');

$q->print ("<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='600'>\n" .
	   "$table_blank_line");

$q->print ("<tr><td COLSPAN='2' ALIGN='center'><h3>HOSTDB: Modify</h3></td></tr>\n" .
	   "$table_blank_line");

my $action = $q->param('action');
$action = 'Search' unless $action;
SWITCH:
{
	$action eq 'Commit' and do
	{
		my $id = $q->param('id');
		my $host;

		#die "No ID specified for commit" unless $id;
		if (defined ($id) and $id ne '') {
			#warn ("GET HOST: $id\n");
			$host = get_host ($hostdb,'ID',$id);
		} else {
			$host = $hostdb->create_host ();
			die ("$0: Could not create host entry: $hostdb->{error}\n") unless (defined ($host));
		}

		if (modify_host ($hostdb, $host, $q)) {
			eval
			{
				$host->commit ();
			};
			if ($@) {
				error_line ($q, "Could not commit changes: $@");
			}
		}

		$id = $host->id () unless ($id);
		$host = get_host($hostdb,'ID',$id); # read-back
		die "Host mysteriously vanished" unless $host;
		host_form($q, $host);
	},last SWITCH;

	$action eq 'Search' and do
	{
		my $host = get_host ($hostdb, 'ID', $q->param('id')) if $q->param('id');
		$host = $hostdb->create_host () unless defined $host;

		host_form($q, $host);
	},last SWITCH;
}

if ($@) {
	error_line($q, "$@\n");
}

$q->end();


sub modify_host
{
	my $hostdb = shift;
	my $host = shift;
	my $q = shift;
	
	eval {
		die ("No host object") unless ($host);

		if ($q->param ('dhcpmode')) {
			$host->dhcpmode ($q->param ('dhcpmode')) or die ("dhcpmode\n");
		}
		if ($q->param ('dhcpstatus')) {
			$host->dhcpstatus ($q->param ('dhcpstatus')) or die ("dhcpstatus\n");
		}
		if ($q->param ('mac_address')) {
			$host->mac_address ($q->param ('mac_address')) or die ("mac_address\n");
		}
		if ($q->param ('dnsmode')) {
			$host->dnsmode ($q->param ('dnsmode')) or die ("dnsmode\n");
		}
		if ($q->param ('dnsstatus')) {
			$host->dnsstatus ($q->param ('dnsstatus')) or die ("dnsstatus\n");
		}
		if ($q->param ('hostname')) {
			$host->hostname ($q->param ('hostname')) or die ("Invalid hostname\n");
		}
		if ($q->param ('ip')) {
			my $ip = $q->param ('ip');
			unless ($ip eq $host->ip ()) {
				my $t_host = $hostdb->findhostbyip ($ip);
				if (defined ($t_host)) {
					my $t_id = $t_host->id () ;
					die "ip: Another host object (ID $t_id) currently have the IP '$ip'\n";
				}
				$host->ip ($ip) or die "ip\n";
			}
		}
		if ($q->param ('owner')) {
			$host->owner ($q->param ('owner')) or die ("owner\n");
		}
		if ($q->param ('ttl')) {
			$host->ttl ($q->param ('ttl')) or die ("ttl\n");
		}
		if ($q->param ('user')) {
			$host->user ($q->param ('user')) or die ("user\n");
		}
		if ($q->param ('partof')) {
			$host->partof ($q->param ('partof')) or die ("partof\n");
		}
	};
	
	if ($@) {
		chomp ($@);
		error_line ($q, "Failed to set host attribute: $@: $host->{error}");
		return 0;
	}
	
	return 1;
}

sub get_host
{
	my $hostdb = shift;
	my $datatype = shift;
	my $search_for = shift;
	my @host_refs;

	if ($datatype eq "ID") {
		if ($search_for =~ /^\d+$/) {
			@host_refs = $hostdb->findhostbyid ($search_for);
		} else {
			warn ("Search failed: '$search_for' is not a valid ID");
			return undef;
		}
	} elsif ($datatype eq "IP") {
		if ($hostdb->is_valid_ip ($search_for)) {
			@host_refs = $hostdb->findhostbyip ($search_for);
		} else {
			warn ("Search failed: '$search_for' is not a valid IP address");
			return undef;
		}
	} else {
		warn ("Search failed: don't recognize datatype '$datatype'");
		return undef;
	}

	if ($#host_refs == -1) {
		warn ("$0: Search for '$search_for' (type '$datatype') failed - no match\n");
		return undef;
	}
	if ($#host_refs == -1) {
		my $count = $#host_refs + 1;
		warn ("$0: Search for '$search_for' (type '$datatype') failed - more than one ($count) match\n");
		return undef;
	}
	
	return $host_refs[0];
}


sub host_form
{
	my $q = shift;
	my $host = shift;

	# HTML 
        my $state_field = $q->state_field ();
        #my $popup = $q->popup_menu (-name => "whoisdatatype", -values => ['Guess', 'IP', 'FQDN', 'MAC', 'ID']);
	#my $datafield = $q->textfield ("whoisdata");
	my $commit = $q->submit ('action', 'Commit');
	#my $delete = $q->submit ('action', 'Delete');
	my $delete = "<font SIZE='1'>[delete not implemented yet]</font>";

	my ($id, $partof, $ip, $mac, $hostname, $user, $owner, 
	    $dnsmode, $dnsstatus, $dhcpmode, $dhcpstatus, $subnet);
	
	# HTML
	my $me = $q->state_url ();
	if (defined ($host)) {
		$id = $host->id ();
		$partof = $q->textfield ('partof', $host->partof ());
		$ip = $q->textfield ('ip', $host->ip ());
		$mac = $q->textfield ('mac_address', $host->mac_address ());
		$hostname = $q->textfield ('hostname', $host->hostname ());
		$user = $q->textfield ('user', $host->user ());
		$owner = $q->textfield ('owner', $host->owner ());
		$dnsmode = $q->popup_menu (-name => 'dnsmode', -values => ['A_AND_PTR', 'A'], -default => $host->dnsmode ());
		$dnsstatus = $q->popup_menu (-name => 'dnsstatus', -values => ['ENABLED', 'DISABLED'], -default => $host->dnsstatus ());
		$dhcpmode = $q->popup_menu (-name => 'dhcpmode', -values => ['STATIC', 'DYNAMIC'], -default => $host->dhcpmode ());
		$dhcpstatus = $q->popup_menu (-name => 'dhcpstatus', -values => ['ENABLED', 'DISABLED'], -default => $host->dhcpstatus ());

		# get subnet (just as info and to provide a link)
		my $h_subnet = $hostdb->findsubnetclosestmatch ($host->ip ());
		
		if ($h_subnet) {
			$subnet = $h_subnet->subnet ();
			if ($showsubnet_path) {
				$subnet = "<a HREF='$showsubnet_path&subnet=$subnet'>$subnet</a>";
			}
		} else {
			$subnet = "not in database";
		}
	}
		
	my $empty_td = '<td>&nbsp;</td>';
	
	$q->print (<<EOH);
	   <form METHOD='post'>
		$state_field
                <input type="hidden" name="id" value="$id"/>
		<tr>
			<td>ID</td>
			<td><a href="$me&id=$id">$id</a></td>
			$empty_td
			$empty_td
		</tr>	
		<tr>
			<td>Subnet</td>
			<td>$subnet</td>
			$empty_td
			$empty_td
		</tr>	
		<tr>
			<td ALIGN='center' COLSPAN='2'>---</td>
			<td ALIGN='center' COLSPAN='2'>---</td>
		</tr>
		<tr>
			<td>Parent</td>
			<td>$partof</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>IP address</td>
			<td><strong>$ip</strong></td>
			<td>DNS</td>
			<td>$dnsstatus</td>
		</tr>
		<tr>
			<td>MAC Address</td>
			<td>$mac</td>
			<td>DHCP</td>
			<td>$dhcpstatus</td>
		</tr>	
		<tr>
			<td>Hostname</td>
			<td><strong>$hostname</strong></td>
			$empty_td
			$empty_td
		</tr>	
		<tr>
			<td>DNS mode</td>
			<td>$dnsmode</td>
			<td>DHCP mode</td>
			<td>$dhcpmode</td>
		<tr>
		<tr>
			<td>User</td>
			<td>$user</td>
			$empty_td
			$empty_td
		</tr>	
		<tr>
			<td>Owner</td>
			<td>$owner</td>
			$empty_td
			$empty_td
		</tr>	
		<tr>
			<td COLSPAN='2' ALIGN='left'>$commit</td>
			<td COLSPAN='2' ALIGN='right'>$delete</td>
		</tr>
		
		$table_blank_line
	   </form>	   

EOH

	return 1;
}

sub error_line
{
	my $q = shift;
	my $error = shift;
	$q->print (<<EOH);
	   <tr>
		<td COLSPAN='4'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
}
