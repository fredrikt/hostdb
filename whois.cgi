#!/usr/local/bin/perl
#
# $Id$
#
# cgi-script to search for different things in the database
#

use strict;
use Config::IniFiles;
#use lib 'blib/lib';
use HOSTDB;
use SUCGI;

my $table_blank_line = "<tr><td COLSPAN='2'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='2'><hr></td></tr>\n";

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

my $showsubnet_path = create_url ($q, $hostdbini->val ('subnet', 'http_base'),
				  $hostdbini->val ('subnet', 'showsubnet_path'));

$q->begin (title => "Whois");

$q->print ("<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='600'>\n" .
	   "$table_blank_line");

$q->print ("<tr><td COLSPAN='2' ALIGN='center'><h3>Web-based whois</h3></td></tr>\n" .
	   "$table_blank_line");

whois_form ($q);

$q->print ($table_hr_line);

perform_search ($hostdb, $q);

$q->print ("</table>\n");

$q->end ();


sub whois_form
{
	my $q = shift;

	# HTML 
        my $state_field = $q->state_field ();
        my $popup = $q->popup_menu (-name => "whoisdatatype", -values => ['Guess', 'IP', 'FQDN', 'MAC', 'ID']);
	my $datafield = $q->textfield ("whoisdata");
	my $submit = $q->submit ("Search");

	$q->print (<<EOH);
	   <form>
		$state_field
		<tr>
		   <td COLSPAN='2'>
			<table BORDER='0' CELLSPACING='0' CELLPADDING='0' WIDTH='600'>
			   <tr>
				<td>
					Search for &nbsp;
					$popup &nbsp;
					$datafield &nbsp;
					$submit
				</td>
			   </tr>
			   $table_blank_line
			</table>
		</tr>
	   </form>	   
EOH
}

sub perform_search
{
	my $hostdb = shift;
	my $q = shift;

	if ($q->param ('whoisdata')) {
		# get type of data

		my $search_for = $q->param ('whoisdata');
		my $whoisdatatype = $q->param ('whoisdatatype');

		if ($whoisdatatype eq "Guess" or ! $whoisdatatype) {
			my $t = $search_for;
			if ($hostdb->clean_mac_address ($t)) {
				$search_for = $t;
				$whoisdatatype = "MAC";
			} elsif ($hostdb->is_valid_ip ($search_for)) {
				$whoisdatatype = "IP";
			} elsif ($hostdb->is_valid_fqdn ($search_for)) {
				$whoisdatatype = "FQDN";
			} elsif ($search_for =~ /^\d+$/) { 
				$whoisdatatype = "ID";
			} else {
				error_line ($q, "Search failed: could not guess data type");
				return undef;
			}
		}

		my @host_refs;
			
		if ($whoisdatatype eq "IP") {
			if ($hostdb->is_valid_ip ($search_for)) {
				my $host = $hostdb->findhostbyip ($search_for);
				my @gaah;
				push (@gaah, $host);
				push (@host_refs, \@gaah);
			} else {
				error_line ($q, "Search failed: '$search_for' is not a valid IP address");
				return undef;
			}
		} elsif ($whoisdatatype eq "FQDN") {
			if ($hostdb->is_valid_fqdn ($search_for)) {
				@host_refs = $hostdb->findhostbyname ($search_for);
			} else {
				error_line ($q, "Search failed: '$search_for' is not a valid FQDN");
				return undef;
			}
		} elsif ($whoisdatatype eq "MAC") {
			my $t = $search_for;
			if ($hostdb->clean_mac_address ($t)) {
				$search_for = $t;
				my $host = $hostdb->findhostbymac ($search_for);
				my @gaah;
				push (@gaah, $host);
				push (@host_refs, \@gaah);
			} else {
				error_line ($q, "Search failed: '$search_for' is not a valid MAC address");
				return undef;
			}
		} elsif ($whoisdatatype eq "ID") {
			if ($search_for =~ /^\d+$/) { 
				my $host = $hostdb->findhostbyid ($search_for);
				my @gaah;
				push (@gaah, $host);
				push (@host_refs, \@gaah);
			} else {
				error_line ($q, "Search failed: '$search_for' is not a valid ID");
				return undef;
			}
		} else {
			error_line ($q, "Search failed: don't recognize whois datatype '$whoisdatatype'");
			return undef;
		}

		if (@host_refs) {
			if ($#host_refs == 0) {
				# only one host (may still be multiple host records), show detailed information
				my $host_ref = @host_refs[0];
				foreach my $host (@$host_ref) {
					$q->print ("<tr><th COLSPAN='2' ALIGN='left'>Host :</th></tr>");
					$q->print ("<tr><td COLSPAN='2'>&nbsp;</td></tr>\n");
		
					print_host_info ($q, $host);

					$q->print ($table_blank_line);
		
					my $subnet = $hostdb->findsubnetclosestmatch ($host->ip ());
		
					if ($subnet) {
						print_subnet_info ($q, $subnet);
					} else {
						error_line ($q, "Search failed: could not find subnet in database");
						return undef;
					}
					$q->print ($table_blank_line);	
				}

				$q->print ($table_hr_line);
			} else {
				# more than one host record, show brief information
				foreach my $host_ref (@host_refs) {
					foreach my $host (@$host_ref) {
						# HTML
						my $ip = $host->ip ();
						my $id = $host->id ();
						my $me = $q->state_url ();

						$ip = "<a href='$me&whoisdatatype=ID&whoisdata=$id'>$ip</a>";
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

				$q->print ($table_hr_line);
			}

			return 1;
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
	my $host = shift;
	
	return undef if (! defined ($host));

	# HTML
	my $me = $q->state_url ();
	my $id = $host->id ();
	$id = "<a href='$me&whoisdatatype=ID&whoisdata=$id'>$id</a>";
	my $parent = $host->partof ()?$host->partof ():'-';
	$parent = "<a href='$me&whoisdatatype=ID&whoisdata=$parent'>$parent</a>";
	my $ip = $host->ip ();
	my $mac = $host->mac_address ();
	my $hostname = $host->hostname ();
	my $user = $host->user ();
	my $owner = $host->owner ();
	
	$q->print (<<EOH);
	   <tr>
		<td>ID</td>
		<td>$id</td>
	   </tr>	
	   <tr>
		<td>Parent</td>
		<td>$parent</td>
	   </tr>
	   <tr>
		<td ALIGN='center'>---</td>
		<td>&nbsp;</td>
	   </tr>
	   <tr>
		<td>IP address</td>
		<td><strong>$ip</strong></td>
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
		<td>User</td>
		<td>$user</td>
	   </tr>	
	   <tr>
		<td>Owner</td>
		<td>$owner</td>
	   </tr>	
EOH

	return 1;
}

sub print_subnet_info
{
	my $q = shift;
	my $subnet = shift;
	
	return undef if (! defined ($subnet));
	
	# HTML
	my $s = $subnet->subnet ();
	my $netmask = $subnet->netmask ();
	my $desc = $subnet->description ();
	
	if ($showsubnet_path) {
		my $sid_url = "_sucgi_sid=" . $q->getSID ();
		$s = "<a href='" . $showsubnet_path . "&subnet=$s" . "'>$s</a>";
	}
	
	$q->print (<<EOH);
		<tr>
		   <td><strong>Subnet</td>
		   <td>$s</td>
		</tr>
		<tr>
		   <td>Netmask</td>
		   <td>$netmask</td>
		</tr>
		   <td>Description</td>
		   <td>$desc</td>
		</tr>
EOH

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
