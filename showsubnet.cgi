#!/usr/local/bin/perl
#
# $Id$
#
# cgi-script to show information about subnets
#

use strict;
use Config::IniFiles;
#use lib 'blib/lib';
use HOSTDB;
use SUCGI;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";

my $debug = 0;
if (defined ($ARGV[0]) and $ARGV[0] eq "-d") {
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
my $subnet = $q->param ('subnet');

my $whois_path = create_url ($q, $hostdbini->val ('subnet', 'http_base'),
			     $hostdbini->val ('subnet', 'whois_path'));
my $modifyhost_path = create_url ($q, $hostdbini->val ('subnet', 'http_base'),
			     $hostdbini->val ('subnet', 'modifyhost_path'));

$q->begin (title => "Subnet(s) matching $subnet");

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='600'>
	   $table_blank_line
	   <td COLSPAN='4' ALIGN='center'><h3>Subnet(s) matching $subnet</h3></td></tr>
	   $table_blank_line
EOH

list_subnet ($hostdb, $q, $subnet);

$q->end ();


sub list_subnet
{
	my $hostdb = shift;
	my $q = shift;
	my $subnet = shift;

	if ($hostdb->is_valid_subnet ($subnet)) {
		my @hosts = $hostdb->findhostbyiprange ($hostdb->get_netaddr ($subnet),
				$hostdb->get_broadcast ($subnet));
		my @subnets;
		
		@subnets = $hostdb->findsubnetlongerprefix ($subnet);
		
		if ($#subnets != -1) {
			my $subnet;
			
			foreach $subnet (@subnets) {
				# HTML
				my $h_subnet = $subnet->subnet ();
				my $me = $q->state_url ();

				$h_subnet = "<a href='$me&subnet=$h_subnet'>$h_subnet</a>";
				my $h_desc = $subnet->description ()?$subnet->description ():'no description';
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
				my ($i, @o, $in_use_count);
				push (@o, <<EOH);
					<tr>
						<th ALIGN='left'>IP</th>
						<th ALIGN='left'>Hostname</th>
						<th ALIGN='left'>MAC address</th>
						<th ALIGN='left'>Last used</th>
					</tr>
EOH
				for $i (1 .. $subnet->addresses () - 2) {
					my $ip = $hostdb->ntoa ($subnet->n_netaddr () + $i);
					my $host = get_host_with_ip ($ip, @subnet_hosts);
					if (! defined ($host)) {
						# there is a gap here, output IP in green
						
						if ($modifyhost_path) {
							$ip = "<a href='$modifyhost_path&ip=$ip'>$ip</a>";
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
						my $hostname = $host->hostname ();
						my $mac = $host->mac_address () || "";
						my $mac_ts = $host->mac_address_ts () || "";
						
						if ($whois_path) {
							$ip = "<a href='$whois_path&whoisdatatype=ID&whoisdata=$id'>$ip</a>";
						}
						
						my $ts_font = "";
						my $ts_font_end = "";
						
						# XXX make these two parameters configurable from hostdb.ini
						my $ts_flag_days = 30;
						my $ts_flag_color = '#dd0000';
						
						my $h_u_t = $host->unix_mac_address_ts ();
						if ($h_u_t and time () - $h_u_t >= ($ts_flag_days * 86400)) {
							$ts_font = "<font COLOR='$ts_flag_color'>";
							$ts_font_end = "</font>";
						} else {
							$in_use_count++;
						}
						
						push (@o, <<EOH);
							<tr>
							   <td ALIGN='left'>$ip</td>
							   <td ALIGN='left'>$hostname</td>
							   <td ALIGN='center'><font SIZE='2'><pre>$mac  </pre></font></td>
							   <td ALIGN='left' NOWRAP>${ts_font}${mac_ts}${ts_font_end}</td>
							</tr>
EOH
					}
				}

				# HTML
				my $netmask = $subnet->netmask ();
				my $num_hosts = ($#subnet_hosts + 1);
				my $num_addrs = ($subnet->addresses () - 2);
				my $dns_usage_percent = int (safe_div ($num_hosts, $num_addrs) * 100);
				my $active_usage_percent = int (safe_div ($in_use_count, $num_addrs) * 100);

				$q->print (<<EOH);
					<tr>
					   <td COLSPAN='2'>Netmask</td>
					   <td COLSPAN='2'>$netmask</td>
					</tr>
					<tr>
					   <td COLSPAN='2'>Host object usage</td>
					   <td COLSPAN='2'>$num_hosts/$num_addrs ($dns_usage_percent%)</td>
					</tr>
					<tr>
					   <td COLSPAN='2'>Hosts in active use</td>
					   <td COLSPAN='2'>$in_use_count/$num_addrs ($active_usage_percent%)</td>
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
		# all their parameters with & as separator
		$url .= '?_sucgi_foo=bar';
	}

	return undef if ($url !~ '^https*://');
	return $url;
}
