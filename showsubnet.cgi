#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to show information about subnets
#

use strict;
use Config::IniFiles;
use HOSTDB;
use SUCGI;

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

my $q = SUCGI->new ($sucgi_ini);
my $subnet = $q->param ('subnet');

my $whois_path = create_url ($q, $hostdbini->val ('subnet', 'http_base'),
			     $hostdbini->val ('subnet', 'whois_path'));
my $modifyhost_path = create_url ($q, $hostdbini->val ('subnet', 'http_base'),
			     $hostdbini->val ('subnet', 'modifyhost_path'));

$q->begin (title => "Subnet(s) matching $subnet");
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


$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='600'>
		$table_blank_line
		<tr>
			<td COLSPAN='4' ALIGN='center'><h3>Subnet(s) matching $subnet</h3></td>
		</tr>
		$table_blank_line
EOH

my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
list_subnet ($hostdb, $q, $subnet, $static_flag_days, $dynamic_flag_days);

$q->print (<<EOH);
	</table>
EOH
$q->end ();


sub list_subnet
{
	my $hostdb = shift;
	my $q = shift;
	my $subnet = shift;
	my $static_flag_days = shift;
	my $dynamic_flag_days = shift;

	if ($hostdb->is_valid_subnet ($subnet)) {
		my @hosts = $hostdb->findhostbyiprange ($hostdb->get_netaddr ($subnet),
				$hostdb->get_broadcast ($subnet));
		my @subnets;
		
		@subnets = $hostdb->findsubnetlongerprefix ($subnet);
		
		if ($#subnets != -1) {
			my $subnet;
			
			foreach $subnet (@subnets) {
				my $static_hosts = 0;
				my $static_in_use = 0;
				my $dynamic_in_use = 0;
				my $dynamic_hosts = 0;

				# check that user is allowed to list subnet

				if (! $hostdb->auth->is_admin ($remote_user)) {
					if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
						error_line ($q, "You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
						next;
					}
				}

				# HTML
				my $h_subnet = $subnet->subnet ();
				my $me = $q->state_url ();

				$h_subnet = "<a href='$me;subnet=$h_subnet'>$h_subnet</a>";
				my $h_desc = $q->escapeHTML ($subnet->description ()?$subnet->description ():'no description');
				$q->print (<<EOH);
					<tr>
					   <td NOWRAP>
						<strong>$h_subnet</strong>
					   </td>
					   <td COLSPAN='3' ALIGN='center'>
						<strong>$h_desc</strong>
					   </td>
					</tr>
					$table_blank_line
EOH

				my @subnet_hosts = get_hosts_in_subnet ($subnet->subnet(), @hosts);

				if (get_host_with_ip ($subnet->netaddr (), @subnet_hosts) or
				    get_host_with_ip ($subnet->broadcast (), @subnet_hosts)) {
					if (get_host_with_ip ($subnet->netaddr (), @subnet_hosts)) {
						error_line ($q, 'WARNING: There is a host entry for the network address ' . $subnet->netaddr ());
					}
					if (get_host_with_ip ($subnet->broadcast (), @subnet_hosts)) {
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
					my $host = get_host_with_ip ($ip, @subnet_hosts);
					if (! defined ($host)) {
						# there is a gap here, output IP in green
						
						if ($modifyhost_path) {
							$ip = "<a href='$modifyhost_path;ip=$ip'>$ip</a>";
						}
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
						my $id = $host->id();
						my $hostname = $host->hostname () || 'NULL';
						my $mac = $host->mac_address () || '';
						my $mac_ts = $host->mac_address_ts () || '';

						# split at space to only get date and not time
						$mac_ts = (split (/\s/, $mac_ts))[0] || '';

						if ($whois_path) {
							$ip = "<a HREF='$whois_path;whoisdatatype=ID;whoisdata=$id'>$ip</a>";
						}
						
						my $ts_font = "";
						my $ts_font_end = "";
						
						my $ts_flag_color = '#dd0000'; # bright red
						my $ts_flag_days = $static_flag_days;
						
						my $h_u_t = $host->unix_mac_address_ts ();

						if ($host->dhcpmode () eq 'DYNAMIC') {
							$ts_flag_days = $dynamic_flag_days;
							$dynamic_hosts++;
							$dynamic_in_use++ if (defined ($h_u_t));
							$mac = 'dynamic';
						} else {
							$static_hosts++;
						}
						
						if (defined ($h_u_t) and
						    (time () - $h_u_t) >= ($ts_flag_days * 86400)) {
							# host has not been seen in active use
							# for $ts_flag_days days
							$ts_font = "<font COLOR='$ts_flag_color'>";
							$ts_font_end = "</font>";
						} else {
							$static_in_use++ if (defined ($h_u_t) and
									     $host->dhcpmode () eq 'STATIC');
						}
						
						push (@o, <<EOH);
							<tr>
							   <td ALIGN='left'>$ip</td>
							   <td ALIGN='left'>$hostname</td>
							   <td ALIGN='center'><font SIZE='2'><pre>$mac</pre></font></td>
							   <td ALIGN='right' NOWRAP>${ts_font}${mac_ts}${ts_font_end}</td>
							</tr>
EOH
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

				$q->print (join ("\n", @o), $table_blank_line);
			}
			
			$q->print ("\n\n");
		} else {
			error_line ($q, "No matching subnet '$subnet'");
		}
	} else {
		error_line ($q, "Illegal subnet address '$subnet'");
	}
}

sub get_hosts_in_subnet
{
	my $subnet = shift;
	my @hosts = @_;
	my @result;

	my $low = $hostdb->aton ($hostdb->get_netaddr ($subnet));
	my $high = $hostdb->aton ($hostdb->get_broadcast ($subnet));

	my $host;
	foreach $host (@hosts) {
		my $ip = $hostdb->aton ($host->ip ());
		push (@result, $host) if ($ip >= $low and $ip <= $high);
	}

	return @result;
}

sub get_host_with_ip
{
	my $ip = shift;
	my @hosts = @_;
	
	my $host;
	foreach $host (@hosts) {
		return $host if ($host->ip () eq $ip);	
	}
	
	return undef;
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

sub create_url
{
	my $q = shift;
	my $base = shift;
	my $in_url = shift;

	return undef if (! $in_url);
	
	my $url;
	if ($in_url !~ '^https*://') {
		# in_url appears to be relative
		$url = "$base/$in_url";
	} else {
		$url = $in_url;
	}

	$url =~ s#([^:])//#$1#;	# replace double slashes, but not the ones in http://

	if ($q) {
		$url .= '?_sucgi_sid=' . $q->getSID ();
	} else {
		# put this here since our users expects to be able to add
		# all their parameters with ; as separator
		$url .= '?';
	}

	return undef if ($url !~ '^https*://');
	return $url;
}
