#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to show information about subnets
#

use strict;
use Config::IniFiles;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";

my $debug = 0;
if (defined ($ARGV[0]) and $ARGV[0] eq "-d") {
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

my $q = SUCGI2->new ($sucgi_ini,'hostdb');
my %links = $hostdb->html_links ($q);

$q->begin (title => "Subnet details");
my $remote_user = $q->user();
unless ($remote_user) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");
}
my $is_admin = $hostdb->auth->is_admin ($remote_user);
my $is_helpdesk = $hostdb->auth->is_helpdesk ($remote_user);


my $subnet;
if (defined ($q->param ('id'))) {
	my $id = $q->param ('id');
	$subnet = $hostdb->findsubnetbyid ($id);

	if (! defined ($subnet)) {
		$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No subnet with ID '$id' found.</strong></font></ul>\n\n");
		$q->end ();
		die ("No subnet with ID '$id' found.\n");
	}

} elsif (defined ($q->param ('subnet'))) {
	my $subnetname = $q->param ('subnet');
	
	$subnet = $hostdb->findsubnet ($subnetname);

	if (! defined ($subnet)) {
		my $errormsg = '';
		if ($hostdb->{error}) {
			$errormsg = "(HOSTDB error $hostdb->{error}";
		}
		$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No subnet '$subnetname' found${errormsg}.</strong></font></ul>\n\n");
		$q->end ();
		die ("No subnet '$subnetname' found.\n");
	}
}

if (! $subnet) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No subnet found.</strong></font></ul>\n\n");
	$q->end ();
	die ("No subnet found\n");
}

my $subnetname = $subnet->subnet ();

my (@links, @admin_links);
push (@admin_links, "[<a HREF='$links{netplan}'>netplan</a>]") if (($is_admin or $is_helpdesk) and $links{netplan});
push (@links, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@links, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td COLSPAN='3' ALIGN='center'><h3>HOSTDB: Subnet $subnetname</h3></td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
list_subnet ($hostdb, $q, $subnet, $remote_user, $is_admin, $is_helpdesk, $static_flag_days, $dynamic_flag_days);

$q->print (<<EOH);
	</table>
EOH
$q->end ();


sub list_subnet
{
	my $hostdb = shift;
	my $q = shift;
	my $subnet = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my $static_flag_days = shift;
	my $dynamic_flag_days = shift;

	my @hosts = $hostdb->findhostbyiprange ($subnet->netaddr (), $subnet->broadcast ());

	my $static_hosts = 0;
	my $static_in_use = 0;
	my $dynamic_in_use = 0;
	my $dynamic_hosts = 0;

	# check that user is allowed to list subnet
	if (! $is_admin and ! $is_helpdesk) {
		if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
			error_line ($q, "You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
			return 0;
		}
	}

	# HTML
	my $subnet_name = $subnet->subnet ();
	my $me = $q->state_url ();
	my $id = $subnet->id ();
	my $owner = $subnet->owner ();

	my $edit_link = '';
	if ($is_admin and $links{modifysubnet}) {
		$edit_link =  "[<a HREF='$links{modifysubnet};id=$id'>edit</a>]";
	}

	my $h_desc = $q->escapeHTML ($subnet->description ()?$subnet->description ():'no description');
	$q->print (<<EOH);
		<tr>
		   <td NOWRAP>
			<strong>$subnet_name</strong>
		   </td>
		   <td COLSPAN='3' ALIGN='left'>
			&nbsp;&nbsp;<strong>$h_desc</strong>
		   </td>
		</tr>

EOH
	if ($edit_link) {
		$q->print (<<EOH);
		<tr>
		  <td COLSPAN='4'>
		    $edit_link
		  </td>
		</tr>

EOH
	}

	$q->print (<<EOH);
		<tr>
		  <td>Owner</td>
		  <td COLSPAN='3'>&nbsp;&nbsp;$owner</td>
		</tr>

EOH

	$q->print ($table_blank_line);

	if (get_hosts_with_ip ($subnet->netaddr (), @hosts) or
	    get_hosts_with_ip ($subnet->broadcast (), @hosts)) {
		if (get_hosts_with_ip ($subnet->netaddr (), @hosts)) {
			error_line ($q, 'WARNING: There is a host entry for the network address ' . $subnet->netaddr ());
		}
		if (get_hosts_with_ip ($subnet->broadcast (), @hosts)) {
			error_line ($q, 'WARNING: There is a host entry for the broadcast address ' . $subnet->broadcast ());
		}
		$q->print ($table_blank_line);
	}

	# loop from first to last host address in subnet
	my ($i, @o);
	push (@o, <<EOH);
		<tr>
			<th ALIGN='left'>IP</th>
			<th ALIGN='left'>Hostname</th>
			<th ALIGN='left'>MAC address</th>
			<th ALIGN='right'>Last used&nbsp;</th>
		</tr>
EOH
	for $i (1 .. $subnet->addresses () - 2) {
		my $ip = $hostdb->ntoa ($subnet->n_netaddr () + $i);
		my @thesehosts = get_hosts_with_ip ($ip, @hosts);
		if (! defined (@thesehosts)) {
			# there is a gap here, output IP in green
						
			$ip = "<a href='$links{modifyhost};ip=$ip'>$ip</a>" if ($links{modifyhost});
			push (@o, <<EOH);
				<tr>
					<td>
						<font COLOR='green'>$ip</font>
					</td>
					<td COLSPAN='3'>
						&nbsp;
					</td>
				</tr>
EOH
		} else {
			my $dup = 0;
			my ($parent, $firsthostpartof);
			foreach my $host (sort parentchildsort @thesehosts) {
				if (! $dup) {
					$parent = $host->id ();	
					$firsthostpartof = $host->partof () || 'NULL';
				}
				
				print_host (\@o, $host, $dup, $parent, $firsthostpartof,
					    $static_flag_days, $dynamic_flag_days,
					    \$static_hosts, \$dynamic_hosts,
					    \$static_in_use, \$dynamic_in_use);
				$dup = 1;
			}
		}
	}

	# HTML
	my $netmask = $subnet->netmask ();
	my $num_hosts = $static_hosts + $dynamic_hosts;
	my $num_addrs = ($subnet->addresses () - 2);
	my $static_percent = int (safe_div ($static_hosts, $num_addrs) * 100);
	my $dynamic_percent = int (safe_div ($dynamic_hosts, $num_addrs) * 100);
	my $host_object_usage_percent = int (safe_div ($num_hosts, $num_addrs) * 100);
	my $static_usage_percent = int (safe_div ($static_in_use, $static_hosts) * 100);
	my $dynamic_usage_percent = int (safe_div ($dynamic_in_use, $dynamic_hosts) * 100);
	my $addresses_needed = $static_in_use + $dynamic_hosts;
	my $needed_percent = int (safe_div ($addresses_needed, $num_addrs) * 100);

	$q->print (<<EOH);
		<tr>
		   <td COLSPAN='2'>Netmask</td>
		   <td COLSPAN='2'>$netmask</td>
		</tr>
		<tr>
		   <td COLSPAN='2'>Hosts registered</td>
		   <td COLSPAN='2'>$num_hosts/$num_addrs ($host_object_usage_percent%)</td>
		</tr>
		
		$table_blank_line
		
		<tr>
		   <td>Static hosts</td>
		   <td>$static_hosts/$num_addrs ($static_percent%)</td>
		   <td>in use</td>
		   <td>$static_in_use/$static_hosts ($static_usage_percent%)</td>
		</tr>
		<tr>
		   <td>Dynamic hosts</td>
		   <td>$dynamic_hosts/$num_addrs ($dynamic_percent%)</td>
		   <td>in use</td>
		   <td>$dynamic_in_use/$dynamic_hosts ($dynamic_usage_percent%)</td>
		</tr>
		
		$table_blank_line
		
		<tr>
		   <td COLSPAN='2'>Addresses needed</td>
		   <td COLSPAN='2'>$static_in_use + $dynamic_hosts = $addresses_needed/$num_addrs ($needed_percent%)</td>
		</tr>
		$table_blank_line
EOH

	$q->print (join ("\n", @o), $table_blank_line, "\n\n");
	
	return 1;
}

sub print_host
{
	my $o = shift;
	my $host = shift;
	my $dup = shift;
	my $thisip_parent = shift;
	my $thisip_partof = shift;
	my $static_flag_days = shift;
	my $dynamic_flag_days = shift;
	my $static_hosts_ref = shift;
	my $dynamic_hosts_ref = shift;
	my $static_in_use_ref = shift;
	my $dynamic_in_use_ref = shift;
	
	my $id = $host->id ();
	my $ip = $host->ip ();
	my $hostname = $host->hostname () || 'NULL';
	my $mac = $host->mac_address () || '';
	my $mac_ts = $host->mac_address_ts () || '';

	# split at space to only get date and not time
	$mac_ts = (split (/\s/, $mac_ts))[0] || '';

	my $ip_align = 'left';
	
	if ($dup) {
		my $partof = $host->partof () || 'NULL';
		if ($partof eq $thisip_parent) {
			$ip = 'child';
			$ip_align = 'center';
		} elsif ($partof eq $thisip_partof) {
			$ip = '(child)';
			$ip_align = 'center';
		} else {
			$ip = 'DUPLICATE';
			$ip_align = 'center';
		}
	} else {
		my $partof = $host->partof () || 'NULL';
		if ($partof ne 'NULL') {
			$ip = "$ip (child)";
		}
	}

	if ($links{whois}) {
		$ip = "<a HREF='$links{whois};whoisdatatype=ID;whoisdata=$id'>$ip</a>";
	}
			
	my $h_u_t = $host->unix_mac_address_ts ();

	my $in_use = 0;
	if ($host->dhcpmode () eq 'DYNAMIC') {
		$$dynamic_hosts_ref++;
		$in_use = 1 if (defined ($h_u_t) and
			(time () - $h_u_t) < ($dynamic_flag_days * 86400));
		$$dynamic_in_use_ref += $in_use;
		$mac = 'dynamic';
	} else {
		$$static_hosts_ref++;
		$in_use = 1 if (defined ($h_u_t) and
			(time () - $h_u_t) < ($static_flag_days * 86400));
		$$static_in_use_ref += $in_use;
	}
			
	my $ts_font = '';
	my $ts_font_end = '';
			
	my $ts_flag_color = '#dd0000'; # bright red
			
	if (! $in_use) {
		$ts_font = "<font COLOR='$ts_flag_color'>";
		$ts_font_end = '</font>';
	}
	
	push (@$o, <<EOH);
		<tr>
		   <td ALIGN='$ip_align'>$ip</td>
		   <td ALIGN='left'>$hostname</td>
		   <td ALIGN='center'><font SIZE='2'><pre>$mac</pre></font></td>
		   <td ALIGN='right' NOWRAP>${ts_font}${mac_ts}${ts_font_end}</td>
		</tr>
EOH

	return 1;
}

sub get_hosts_with_ip
{
	my $ip = shift;
	my @hosts = @_;

	my (@retval, $host);
	foreach $host (@hosts) {
		push (@retval, $host) if ($host->ip () eq $ip);	
	}
	
	wantarray ? @retval : $retval[0];
}

sub parentchildsort
{
	if ($a->partof () == $b->id ()) {
		return 1;
	}
	
	if ($b->partof () == $a->id ()) {
		return -1;
	}
	
	return $a->id () <=> $b->id ();
}

sub safe_div
{
	my $a = shift;
	my $b = shift;

	return ($a / $b) if ($a != 0 and $b != 0);

	return 0;
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
	my $i = localtime () . " showsubnet.cgi[$$]";
	warn ("$i: $error\n");
}
