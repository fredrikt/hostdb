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
}

my $q = SUCGI->new ($sucgi_ini);
my $subnet = $q->param ('subnet');

$q->begin (title => "Subnet(s) matching $subnet");

$q->print ("&nbsp;</TD></TR><TR><TD COLSPAN='3' ALIGN='center'><H3>Subnet(s) matching $subnet</H3></TD></TR>\n");

$q->print ("<TR><TD COLSPAN='2'>&nbsp;</TD></TR>\n");

list_subnet ($subnet);

$q->end ();


sub list_subnet
{
	my $subnet = shift;

	if ($hostdb->check_valid_subnet ($subnet)) {
		my @hosts = $hostdb->findhostbyiprange ($hostdb->get_netaddr ($subnet),
				$hostdb->get_broadcast ($subnet));
		my @subnets;
		
		@subnets = $hostdb->findsubnetlongerprefix ($subnet);
		
		if ($#subnets != -1) {
			my $subnet;
			
			foreach $subnet (@subnets) {
				$q->print ("<TR><TD><STRONG>" . $subnet->subnet() . "</STRONG></TD>" .
					"<TD COLSPAN='2' ALIGN='center'><STRONG>\n" .
					($subnet->description ()?$subnet->description ():"no description") .
					"</STRONG></TD></TR>");

				$q->print ("<TR><TD COLSPAN='3'>&nbsp;</TD></TR>\n");

				my @subnet_hosts = get_hosts_in_subnet ($subnet->subnet(), @hosts);

				$q->print ("<TR><TD>Netmask</TD><TD>" . $subnet->netmask () . "</TD></TR>\n" .
					   "<TR><TD>Address usage</TD><TD>" . ($#subnet_hosts + 1) . "/" .
					   $subnet->addresses () . " (" .
					   int ((($#subnet_hosts + 1) / ($subnet->addresses () - 1)) * 100) . "%)</TD></TR>\n");

				$q->print ("<TR><TD COLSPAN='2'>&nbsp;</TD></TR>\n");

				# loop from first to last host address in subnet
				my $i;
				for $i (1 .. $subnet->addresses () - 1) {
					my $ip = $hostdb->ntoa ($subnet->n_netaddr () + $i);
					my $host = get_host_with_ip ($ip, @subnet_hosts);
					if (! defined ($host)) {
						# there is a gap here, output a ... line
						$q->print ("<TR><TD><FONT COLOR='green'>$ip</FONT></TD><TD COLSPAN='2'>&nbsp;</TD></TR>\n");
					} else {
						$q->print ("<TR>" .
							   "	<TD>" . $host->ip () . "</TD>\n" .
							   "	<TD>" . $host->hostname () . "</TD>\n" .
							   "	<TD>" . $host->mac_address () . "</TD>\n" .
							   "</TR>\n");
					}
				}
				$q->print ("<TR><TD COLSPAN='3'>&nbsp;</TD></TR>\n");
			}
			
			$q->print ("\n\n");
		} else {
			$q->print ("<H3><FONT COLOR='red'>No matching subnet '$subnet'</FONT></H3>");
		}
	} else {
		$q->print ("<H3><FONT COLOR='red'>Illegal subnet address '$subnet'</FONT></H3>");
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
	
	$q->print ("<!-- S4IP $ip -->\n");
	my $host;
	foreach $host (@hosts) {
		return $host if ($host->ip () eq $ip);	
	}
	
	return undef;
}
