#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to search for different things in the database
#

use strict;
use HOSTDB;
use SUCGI;

my $table_blank_line = "<tr><td COLSPAN='2'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='2'><hr></td></tr>\n";

my $debug = 0;
if (defined ($ARGV[0]) and ($ARGV[0] eq "-d")) {
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

my $remote_user = '';
if (defined ($ENV{REMOTE_USER}) and $ENV{REMOTE_USER} =~ /^[a-z0-9]{,50}/) {
	$remote_user = $ENV{REMOTE_USER};
}
# XXX JUST FOR DEBUGGING UNTIL PUBCOOKIE IS FINISHED
$remote_user = 'andreaso';


my $showsubnet_path = $q->state_url($hostdbini->val('subnet','showsubnet_uri'));
my $modifyhost_path = $q->state_url($hostdbini->val('subnet','modifyhost_uri'));

$q->begin (title => "Whois");

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='600'>
		$table_blank_line
		<tr>
			<td COLSPAN='2' ALIGN='center'><h3>HOSTDB: Search</h3></td>
			<td>&nbsp;</td>
		</tr>
		$table_blank_line
EOH

whois_form ($q);

$q->print ($table_hr_line);

perform_search ($hostdb, $q, $remote_user);

$q->print (<<EOH);
	</table>
EOH

$q->end ();


sub whois_form
{
	my $q = shift;

	# HTML 
        my $state_field = $q->state_field ();
	my $me = $q->state_url ();
        my $popup = $q->popup_menu (-name => 'whoisdatatype', -values => ['Guess', 'IP', 'FQDN', 'MAC', 'ID'], -default => 'Guess');
	my $datafield = $q->textfield ('whoisdata');
	my $submit = $q->submit ('Search');

	$q->print (<<EOH);
		<tr>
		   <td COLSPAN='2' ALIGN='center'>
			<form ACTION='$me' METHOD='post'>
				$state_field
				Search for &nbsp;
				$popup &nbsp;
				$datafield &nbsp;
				$submit
			</form>
		   </td>
		   <td>&nbsp;</td>
		</tr>
		$table_blank_line
EOH
}

sub perform_search
{
	my $hostdb = shift;
	my $q = shift;
	my $remote_user = shift;

	if ($q->param ('whoisdata')) {
		my $search_for = $q->param ('whoisdata');
		my $whoisdatatype = $q->param ('whoisdatatype');

		my @host_refs = $hostdb->findhost ($whoisdatatype, $search_for);
		if ($hostdb->{error}) {
			error_line ($q, $hostdb->{error});
			return undef;
		}
		
		if (@host_refs) {
			if (1 == @host_refs) {
				# only one host, show detailed information
				foreach my $host (@host_refs) {
					$q->print ("<tr><th COLSPAN='2' ALIGN='left'>Host :</th></tr>");
		
					print_host_info ($q, $hostdb, $remote_user, $host);
				}
			} else {
				# more than one host record, show brief information
				foreach my $host (@host_refs) {
					# HTML
					my $ip = $host->ip ();
					my $id = $host->id ();
					my $me = $q->state_url ();

					$ip = "<a HREF='$me;whoisdatatype=ID;whoisdata=$id'>$ip</a>";
					my $hostname = $host->hostname ();
					my $mac = $host->mac_address ();
						
					$q->print (<<EOH);
						<tr>
						   <td>$ip</td>
						   <td>$hostname</td>
						   <td>$mac</td>
						</tr>
EOH
				}
			}

			#$q->print ($table_hr_line);

			return 1;
		} else {
			error_line ($q, "No match, searched for '$search_for' of type '$whoisdatatype'");
		}

		return 0;
	} else {
		$q->print ("<!-- no whoisdata, not searching -->\n");
		return undef;
	}
}

sub print_host_info
{
	my $q = shift;
	my $hostdb = shift;
	my $remote_user = shift;
	my $host = shift;
	
	return undef if (! defined ($host));

	# HTML
	my $me = $q->state_url();
	my $id = $host->id ();
	my $parent = '-';
	my $ip = $host->ip ();
	my $mac = $host->mac_address () || 'NULL';
	my $hostname = $host->hostname () || 'NULL';
	my $user = $host->user () || 'NULL';
	my $owner = $host->owner ();
	my $dhcpstatus = $host->dhcpstatus ();
	my $dhcpmode = $host->dhcpmode ();
	my $dnsstatus = $host->dnsstatus ();
	my $dnsmode = $host->dnsmode ();
	my $ttl = $host->ttl () || 'default';
	#my $dhcpprofile = $host->dhcpprofile () || 'default';

	my $zone;
	my $z = $hostdb->findzonebyhostname ($host->hostname ());

	if (defined ($z)) {
		$zone = $z->zonename ();
	} else {
		$zone = 'No zone found';
	}
	
	if ($host->partof ()) {
		my @host_refs  = $hostdb->findhost ('id', $host->partof ());
		if ($host_refs[0]) {
			my $parent_name = $host_refs[0]->hostname ();
			my $parent_id = $host_refs[0]->id ();
			$parent = "<a HREF='$me;whoisdatatype=ID;whoisdata=$parent_id'>$parent_id</a>&nbsp;($parent_name)";
		} else {
			$parent = "$parent <font COLOR='red'><strong>Not found</strong></font>";
		}
	}


	# get subnet
	my $subnet = $hostdb->findsubnetclosestmatch ($host->ip () || $q->param ('ip'));

	# get zone
	my $zone = $hostdb->findzonebyhostname ($host->hostname ());

	# check that user is allowed to edit both current zone and subnet

	my $authorized = 1;

	if (! $hostdb->auth->is_admin ($remote_user)) {
		$authorized = 0 if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user));

		# if there is no zone, only base desicion on subnet rights
		$authorized = 0 if (defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user));
	}

	my $zone_link;
	if (defined ($zone)) {
		my $z = $zone->zonename ();
		$zone_link = "<a HREF='http://not-implemented-yet.example.org?zone=$z'>$z</a>";
	} else {
		$zone_link = "<font COLOR='red'>No zone found for hostname</font>";
	}
	
	my $modify_link = $authorized?"[<a HREF='$modifyhost_path;id=$id'>modify</a>]":'<!-- not authorized to modify -->';

	if ($dhcpstatus ne 'ENABLED') {
		$dhcpstatus = "<font COLOR='red'>$dhcpstatus</font>";
	}

	if ($dnsstatus ne 'ENABLED') {
		$dnsstatus = "<font COLOR='red'>$dnsstatus</font>";
	}

	$q->print (<<EOH);
	   <tr>
		<td>&nbsp;&nbsp;ID</td>
		<td>$id&nbsp;$modify_link</td>
	   </tr>	
	   <tr>
		<td>&nbsp;&nbsp;Parent</td>
		<td>$parent</td>
	   </tr>
EOH

	my $t_host;
	foreach $t_host ($hostdb->findhostbypartof ($id)) {
		my $child = $t_host->id ()?$t_host->id ():'-';
		my $child_name = $t_host->hostname ();
		$child = "<a HREF='$me;whoisdatatype=ID;whoisdata=$child'>$child</a>&nbsp;($child_name)";
		
		$q->print (<<EOH);
			<tr>
				<td>&nbsp;&nbsp;Child</td>
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
		<th ALIGN='left'>DNS</th>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<td>&nbsp;&nbsp;IP address</td>
		<td><strong>$ip</strong></td>
	   </tr>	
	   <tr>
		<td>&nbsp;&nbsp;Hostname</td>
		<td><strong>$hostname</strong></td>
	   </tr>	
	   <tr>
		<td>&nbsp;&nbsp;Zone</td>
		<td>$zone_link</td>
	   </tr>	
	   <tr>
		<td>&nbsp;&nbsp;TTL</td>
		<td>$ttl</td>
	   </tr>
	   <tr>
	   	<td>&nbsp;&nbsp;Mode</td>
	   	<td>$dnsmode</td>
	   </tr>	
	   <tr>
	   	<td>&nbsp;&nbsp;Status</td>
	   	<td>$dnsstatus</td>
	   </tr>	


	   <tr>
		<td ALIGN='center'>---</td>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<th ALIGN='left'>DHCP</th>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<td>&nbsp;&nbsp;MAC Address</td>
		<td>$mac</td>
	   </tr>
	   <tr>
	   	<td>&nbsp;&nbsp;Mode</td>
	   	<td>$dhcpmode</td>
	   </tr>	
	   <tr>
	   	<td>&nbsp;&nbsp;Status</td>
	   	<td>$dhcpstatus</td>
	   </tr>	
	   	
	   <tr>
		<td ALIGN='center'>---</td>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<th ALIGN='left'>General</th>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<td>&nbsp;&nbsp;User</td>
		<td>$user</td>
	   </tr>	
	   <tr>
		<td>&nbsp;&nbsp;Owner</td>
		<td>$owner</td>
	   </tr>	
	   
	   $table_blank_line
EOH
	if ($subnet) {
		# HTML
		my $s = $subnet->subnet ();
		my $netmask = $subnet->netmask ();
		my $desc = $subnet->description ();
	
		if ($showsubnet_path) {
			$s = "<a HREF='$showsubnet_path;subnet=$s'>$s</a>";
		}
	
		$q->print (<<EOH);
			<tr>
			   <th ALIGN='left'>Subnet</th>
			   <td>$s</td>
			</tr>
			<tr>
			   <td>&nbsp;&nbsp;Netmask</td>
			   <td>&nbsp;&nbsp;$netmask</td>
			</tr>
			<tr>
			   <td>&nbsp;&nbsp;Description</td>
			   <td>$desc</td>
			</tr>
EOH

	} else {
		error_line ($q, "Search failed: could not find subnet in database");
	}
	
	$q->print ($table_blank_line);	

	return 1;
}

sub error_line
{
	my $q = shift;
	my $error = shift;
	$q->print (<<EOH);
	   <tr>
		<td COLSPAN='2'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
}

