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

my $table_blank_line = "<tr><td COLSPAN='3'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='3'><hr></td></tr>\n";

my $debug = 0;
if ($ARGV[0] eq "-d") {
	shift (@ARGV);
	$debug = 1;
}

my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());

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

$q->begin (title => "Subnet(s) matching $subnet");

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='600'>
	   $table_blank_line
	   <td COLSPAN='3' ALIGN='center'><h3>Subnet(s) matching $subnet</h3></td></tr>
	   $table_blank_line
EOH

list_subnet ($hostdb, $q, $subnet);

$q->end ();


sub list_subnet
{
	my $hostdb = shift;
	my $q = shift;
	my $subnet = shift;

	if ($hostdb->check_valid_subnet ($subnet)) {
		my @hosts = $hostdb->findhostbyiprange ($hostdb->get_netaddr ($subnet),
				$hostdb->get_broadcast ($subnet));
		my @subnets;
		
		@subnets = $hostdb->findsubnetlongerprefix ($subnet);
		
		if ($#subnets != -1) {
			my $subnet;
			
			foreach $subnet (@subnets) {
				# HTML
				my $h_subnet = $subnet->subnet ();
				my $h_desc = $subnet->description ()?$subnet->description ():'no description';
				$q->print (<<EOH);
					<tr>
					   <td>
						<strong>$h_subnet</strong>
					   </td>
					   <td COLSPAN='2' ALIGN='center'>
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

				# HTML
				my $netmask = $subnet->netmask ();
				my $num_hosts = ($#subnet_hosts + 1);
				my $num_addrs = ($subnet->addresses () - 2);
				my $usage_percent = int (safe_div ($num_hosts, $num_addrs) * 100);

				$q->print (<<EOH);
					<tr>
					   <td>Netmask</td>
					   <td>$netmask</td>
					</tr>
					<tr>
					   <td>Address usage</td>
					   <td>$num_hosts/$num_addrs ($usage_percent%)</td>
					</tr>
					$table_blank_line
EOH

				# loop from first to last host address in subnet
				my $i;
				for $i (1 .. $subnet->addresses () - 2) {
					my $ip = $hostdb->ntoa ($subnet->n_netaddr () + $i);
					my $host = get_host_with_ip ($ip, @subnet_hosts);
					if (! defined ($host)) {
						# there is a gap here, output a ... line
						$q->print ("<tr><td><FONT COLOR='green'>$ip</FONT></td><td COLSPAN='2'>&nbsp;</td></tr>\n");
					} else {
						# HTML
						my $ip = $host->ip ();
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
				$q->print ($table_blank_line);
			}
			
			$q->print ("\n\n");
		} else {
			error_line ("No matching subnet '$subnet'");
		}
	} else {
		error_line ("Illegal subnet address '$subnet'");
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
		<td COLSPAN='3'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
}
