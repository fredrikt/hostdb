#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to modify/create host objects
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";

my $debug = 0;
if (defined($ARGV[0]) and $ARGV[0] eq "-d") {
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
$q->begin (title => 'Modify/Add Host');

my $t = $hostdbini->val ('modifyhost', 'readwrite_attributes') || 'ALL';
$t =~ s/\s+//og;
my @readwrite_attributes = split (',', $t);

my $hostdb = eval {
	HOSTDB::DB->new (ini => $hostdbini, debug => $debug);
};

if ($@) {
	my $e = $@;
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>Could not create HOSTDB object: $e</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not create HOSTDB object: '$e'");
}

my $me = $q->state_url ();
my %links = $hostdb->html_links ($q);

my $remote_user = $q->user();
unless ($remote_user) {
        $q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
        $q->end ();
        die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");
}
my $is_admin = $hostdb->auth->is_admin ($remote_user);
my $is_helpdesk = $hostdb->auth->is_helpdesk ($remote_user);


my $host;

my $id = $q->param('id');
if (defined ($id) and $id ne '') {
	$host = get_host ($hostdb, 'ID', $id);
} else {
	$host = $hostdb->create_host ();
	if (defined ($host)) {
		# set some defaults
		$host->profile ('default');
		$host->manual_dnszone ('N');
		$host->dnsmode ('A_AND_PTR');
		$host->dnsstatus ('ENABLED');
	}
}

if (! defined ($host)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host found and none could be created (hostdb error: $hostdb->{error})</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not get/create host (hostdb error: $hostdb->{error})");
}



my (@links, @admin_links);
push (@admin_links, "[<a HREF='$links{netplan}'>netplan</a>]") if ($links{netplan});
push (@links, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@links, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}


$q->print (<<EOH);
	<form ACTION='$me' METHOD='post'>
	<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td COLSPAN='3' ALIGN='center'>
				<h3>HOSTDB: Add/Modify Host</h3>
			</td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

my $action = lc ($q->param('action'));
$action = 'search' unless $action;

if ($action eq 'commit') {
	if (modify_host ($hostdb, $host, $q, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes)) {
		my $i = localtime () . " modifyhost.cgi[$$]";
		eval
		{
			$host->commit ();
		};
		$id = $host->id () if (! defined ($id) and defined ($host));
		if ($@) {
			error_line ($q, "Could not commit changes: $@");
			warn ("$i Changes to host with id '$id' could not be committed ($@)\n");
		} else {			
			warn ("$i Changes to host with id '$id' committed successfully\n");
		}
	}
	$id = $host->id () if (! defined ($id) and defined ($host));
	$host = get_host ($hostdb, 'ID', $id) if ($id);	# read-back
} elsif	($action eq 'search') {
	# call modify_host but don't commit () afterwards to get
	# ip and other stuff supplied to us as CGI parameters
	# set on the host before we call host_form () below.
	modify_host ($hostdb, $host, $q, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes);
} else {
	error_line ($q, 'Unknown action');
	$host = undef;
}


if (defined ($host)) {
	host_form ($q, $host, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes);
}

END:
$q->print (<<EOH);
	</table></form>
EOH

$q->end();


sub modify_host
{
	my $hostdb = shift;
	my $host = shift;
	my $q = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my $readwrite_attributes = shift;
	
	my (@changelog, @warning);
	
	eval {
		die ("No host object") unless ($host);
		
		$host->_set_error ('');		

		# get subnet
		my $subnet = $hostdb->findsubnetbyip ($host->ip () || $q->param ('ip'));

		# get zone
		my $zone = $hostdb->findzonebyhostname ($host->hostname ());

		# check that user is allowed to edit both current zone and subnet

		if (! $is_admin and ! $is_helpdesk) {
			if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
				die ("You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
			}

			# if there is no zone, only base desicion on subnet rights
			if (defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
				die ("You do not have sufficient access to zone '" . $zone->zone () . "'");
			}
		}

		my $identify_str = "id:'" . ($host->id () || 'no id') . "' hostname:'" . ($host->hostname () || 'no hostname') . "' ip:'" . ($host->ip () || 'no ip') . "'";

		# this is a hash and not an array to provide a better framework
		my %changer = ('dhcpmode' =>	'dhcpmode',
			       'dhcpstatus' =>	'dhcpstatus',
			       'mac_address' =>	'mac_address',
			       'dnsmode' =>	'dnsmode',
			       'dnsstatus' =>	'dnsstatus',
			       'hostname' =>	'hostname',
			       'owner' =>	'owner',
			       'ttl' =>		'ttl',
			       'comment' =>	'comment',
			       'partof' =>	'partof',
			       'ip' =>		'ip',
			       'profile' =>	'profile'
			      );

		# check which fields we should allow changes to
		foreach my $t (keys %changer) {
			delete($changer{$t}) if (! check_readwrite ($t, $readwrite_attributes, $remote_user, $is_admin, $is_helpdesk));
		}
			      
		foreach my $name (keys %changer) {
			my $new_val = $q->param ($name);
			if (defined ($new_val)) {
				my $func = $changer{$name};
				next unless ($func);
				my $old_val = $host->$func () || '';

				if ($new_val ne $old_val) {
				
					# do special stuff for some attributes
					
					if ($name eq 'ip') {
						# changing IP, check that user has enough permissions for the _new_ subnet too
						my $ip = $q->param ('ip');

						my $t_host = $hostdb->findhostbyip ($ip);
						if (defined ($t_host)) {
							my $t_id = $t_host->id () ;
							my $t_hostname = $t_host->hostname ();
							die "Another host object (ID $t_id, hostname '$t_hostname') currently have the IP '$ip'\n";
						}
				
						my $new_subnet = $hostdb->findsubnetbyip ($ip);
				
						die ("Invalid new IP address '$ip': no subnet for that IP found in database") if (! defined ($new_subnet));
				
						if (! $is_admin and ! $is_helpdesk and
						    ! $hostdb->auth->is_allowed_write ($new_subnet, $remote_user)) {
							die ("You do not have sufficient access to the new IP's subnet '" . 
							     $new_subnet->subnet () . "'");
						}
					} elsif ($name eq 'hostname') {
						# changing hostname, check that user has enough permissions for the _new_ zone too
						my $hostname = $q->param ('hostname');

						die "Invalid hostname '$hostname'\n" if (! $hostdb->clean_hostname ($hostname));

						my $t_host = $hostdb->findhostbyname ($hostname);
						if (defined ($t_host)) {
							my $t_id = $t_host->id ();
							my $t_ip = $t_host->ip ();
							die "Another host object (ID $t_id, IP $t_ip) currently have the hostname '$hostname'\n";
						}
				
						my $new_zone = $hostdb->findzonebyhostname ($hostname);
				
						if (defined ($new_zone)) {
							if (! $is_admin and ! $is_helpdesk and
							    ! $hostdb->auth->is_allowed_write ($new_zone, $remote_user)) {
								die ("You do not have sufficient access to the new hostnames zone '" . 
								     $new_zone->zonename () . "'");
							}

							if ($host->manual_dnszone () ne 'Y') {
								$host->dnszone ($new_zone->zonename ());
							} else {
								if ($host->dnszone () ne $new_zone->zonename ()) {
									push (@warning, "Not changing DNS zone, but hostname " .
									      "indicates it should be changed from '" .
									      $host->dnszone () . "' to '" . 
									      $new_zone->zonename () . "'");
								}
							}
						} else {
							push (@warning, "No DNS zone for hostname '$hostname' found in database");
						}
					} elsif ($name eq 'partof') {
						# changing partof, look it up using hostdb->findhost so that
						# a hostname or IP address can be used instead of just ID's
					
						my $parentid = $q->param ('partof');
						
						if ($parentid) {
							my @host_refs = $hostdb->findhost ('guess', $parentid);
						
							my $host_count = $#host_refs + 1;
							die ("Parent host not found") if ($host_count < 1);
							die ("Lookup of parent returned more than one ($host_count) hosts") if ($host_count > 1);
						
							$new_val = $host_refs[0]->id ();
						} else {
							$new_val = 0;
						}
					} elsif ($name eq 'mac_address') {
						# check if a host with the same mac address exists in the
						# very same subnet (a mobile host for example may exist
						# in multiple subnets, but only once per subnet)
						
						my $mac = $q->param ('mac_address');
						if ($mac) {
						
							die "Invalid MAC address '$mac'\n" if (! $hostdb->clean_mac_address ($mac));

							my @host_refs = $hostdb->findhostbymac ($mac);

							foreach my $t_host (@host_refs) {
								next if (! defined ($t_host));

								# skip if it is the same host object as we
								# are currently modifying. should not happen
								# since we only get here if $new_val not
								# equals $old_val...
								next if ($t_host->id () eq $host->id ());
								
								# ok, go find t_host's subnet and check if
								# it is the same as the host we're modifyings...
								my $t_subnet = $hostdb->findsubnetbyip ($t_host->ip ());
								my $t_id = $t_host->id ();
								my $t_subnetname;
								$t_subnetname = $t_subnet->subnet () if (defined ($t_subnet));
								
								if ($t_subnetname and $t_subnet->subnet () eq $subnet->subnet ()) {
									my $t_ip = $t_host->ip ();
									my $t_hostname = $t_host->hostname ();
									die ("Another host object (ID $t_id, IP $t_ip, hostname '$t_hostname') on the same subnet ($t_subnetname) has the same MAC address\n");
								} else {
									my $t;
									$t = " (on subnet $t_subnetname)" if ($t_subnetname);
									
									push (@warning, "Another host${t} object (ID $t_id) has that MAC address\n");
								}
							}
						} else {
							$new_val = 'NULL';
						}
					} elsif ($name eq 'ttl') {
						if ($new_val and $new_val ne 'NULL') {
							if (! $hostdb->is_valid_nameserver_time ($new_val)) {
								die ("Invalid DNS TTL '$new_val'\n");
							}
							if (! $hostdb->is_valid_nameserver_time ($new_val, 10, 604800)) {
								die ("DNS TTL out of range (minimum 10 seconds, maximum 7 days)\n");
							}
						} else {
							$new_val = 'NULL';
						}
	 				}
			
					$host->$func ($new_val) or die ("Failed to set host attribute: '$name' - error was '$host->{error}'\n");
					my $readback = $host->$func ();
					if (defined ($readback)) {
						$readback = "'$readback'";
					} else {
						$readback = 'undef';
					}
					if (defined ($old_val) and $old_val) {
						push (@changelog, "Changed '$name' from '$old_val' to '$new_val' (read-back: $readback)");
					} else {
						push (@changelog, "Set '$name' to '$new_val' (read-back: $readback)");
					}
				}
			}
		}

		if (! $host->hostname () and $host->dnsstatus () eq 'ENABLED') {
			die ("Hostname cannot be NULL when dnsstatus is ENABLED\n");
		}

		if (@changelog) {
			my $i = localtime () . " modifyhost.cgi[$$]";
			warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) made the following changes to host -- $identify_str :\n$i ",
			      join ("\n$i ", @changelog), "\n");
		}	      
	};
	
	if ($@) {
		chomp ($@);
		error_line ($q, $@ . "\n");
		return 0;
	}
	
	if (@warning) {
		foreach my $t (@warning) {
			error_line ($q, "Warning: $t");
		}
	}
	
	return 1;
}

sub get_host
{
	my $hostdb = shift;
	my $datatype = shift;
	my $search_for = shift;
	my @host_refs;

	@host_refs = $hostdb->findhost ($datatype, $search_for);

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


sub create_datafield
{
	my $host = shift;
	my $attribute = shift;
	my $q = shift;
	my $func = shift;
	my $readwrite_attributes = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my %paramhash = @_;
	
	my $curr = $host->$attribute () || '';
	
	if (check_readwrite ($attribute, $readwrite_attributes, $remote_user, $is_admin, $is_helpdesk)) {
		if (defined (%paramhash)) {
			return ($q->$func (-name => $attribute, -default => $curr, %paramhash));
		} else {
			return ($q->$func (-name => $attribute, -default => $curr));
		}
	} else {
		return ("$curr (read only)");
	}
}

sub host_form
{
	my $q = shift;
	my $host = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my $readwrite_attributes = shift;
	
	my ($id, $partof, $ip, $mac_address, $hostname, $comment, $owner, 
	    $dnsmode, $dnsstatus, $dhcpmode, $dhcpstatus, $subnet,
	    $profile, $dnszone, $ttl);
	
	my $h_subnet = $hostdb->findsubnetbyip ($host->ip ());

	if (defined ($h_subnet)) {
		$subnet = $h_subnet->subnet ();

		if ($links{showsubnet}) {
			$subnet = "<a HREF='$links{showsubnet};subnet=$subnet'>$subnet</a>";
		}
	} else {
		$subnet = "not in database";
	}
		

	# HTML 
        my $state_field = $q->state_field ();
	my $commit = $q->submit ('action', 'Commit');

	my %dnsmode_labels = ('A_AND_PTR' => "Both 'A' and 'PTR'",
			      'A'	  => "Only 'A'");
	my %enabled_labels = ('ENABLED'	  => 'Enabled',
			      'DISABLED'  => 'Disabled');
	my %dhcpmode_labels = ('STATIC'	  => 'Static',
			       'DYNAMIC'  => 'Dynamic');
			      
	my $me = $q->state_url ();
	my @profiles = split (',', $h_subnet->profilelist ());
		
	$id = $host->id ();
	$dnszone = $host->dnszone () || '';

	my @fielddata = ($readwrite_attributes, $remote_user, $is_admin, $is_helpdesk);
	$partof =	create_datafield ($host, 'partof',	$q, 'textfield', @fielddata);
	$ip =		create_datafield ($host, 'ip',		$q, 'textfield', @fielddata);
	$mac_address =	create_datafield ($host, 'mac_address',	$q, 'textfield', @fielddata);
	$hostname =	create_datafield ($host, 'hostname',	$q, 'textfield', @fielddata);
	$ttl =		create_datafield ($host, 'ttl',		$q, 'textfield', @fielddata);
	$comment =	create_datafield ($host, 'comment',	$q, 'textfield', @fielddata,
					  -size => 45, -maxlength => 255);
	$owner =	create_datafield ($host, 'owner',	$q, 'textfield', @fielddata);
	$dnsmode =	create_datafield ($host, 'dnsmode', 	$q, 'popup_menu', @fielddata,
					   -values => ['A_AND_PTR', 'A'],
					   -labels => \%dnsmode_labels);
	$dnsstatus =	create_datafield ($host, 'dnsstatus', 	$q, 'popup_menu', @fielddata,
					     -values => ['ENABLED', 'DISABLED'],
					     -labels => \%enabled_labels);
	$dhcpmode =	create_datafield ($host, 'dhcpmode', 	$q, 'popup_menu', @fielddata,
					    -values => ['STATIC', 'DYNAMIC'],
					    -labels => \%dhcpmode_labels);
	$dhcpstatus =	create_datafield ($host, 'dhcpstatus', 	$q, 'popup_menu', @fielddata,
					      -values => ['ENABLED', 'DISABLED'],
					      -labels => \%enabled_labels);
	$profile =	create_datafield ($host, 'profile', 	$q, 'popup_menu', @fielddata,
					   -values => \@profiles);

	$dnsmode = $dnsmode_labels{$dnsmode} || $dnsmode;
	$dnsstatus = $enabled_labels{$dnsstatus} || $dnsstatus;

	my $empty_td = '<td>&nbsp;</td>';
	
	my $required = "<font COLOR='red'>*</font>";

	my $delete = "[delete]";
	$delete = "[<a HREF='$links{deletehost};id=$id'>delete</a>]" if (defined ($id) and $links{deletehost});

	my $id_if_any = '';
	$id_if_any = "<input TYPE='hidden' NAME='id' VALUE='$id'>" if (defined ($id) and ($id ne ''));

	my $host_id = $id;

	if (defined ($id)) {
		$host_id = "<a HREF='$links{whois};whoisdatatype=id;whoisdata=$id'>$id</a>" if ($links{whois});
	} else {
		$host_id = "not in database";
	}
	
	$q->print (<<EOH);
		$state_field
                $id_if_any
		<tr>
			<td>ID</td>
			<td>$host_id</td>
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
			<td>DNS zone</td>
			<td>$dnszone</td>
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
			<td>Comment</td>
			<td COLSPAN='3'>$comment</td>
		</tr>	
		<tr>
			<td>Owner $required</td>
			<td>$owner</td>
			$empty_td
			$empty_td
		</tr>	

		$table_blank_line

		<tr>
			<td><strong>DNS</strong></td>
			<td>$dnsstatus</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>IP address $required</td>
			<td><strong>$ip</strong></td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>Hostname $required</td>
			<td><strong>$hostname</strong></td>
			$empty_td
			$empty_td
		</tr>

		<tr>
			<td>DNS mode</td>
			<td>$dnsmode</td>
			<td>&nbsp;&nbsp;TTL</td>
			<td>$ttl</td>
		</tr>

		$table_blank_line

		<tr>
			<td><strong>DHCP</strong></td>
			<td>$dhcpstatus</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>MAC Address</td>
			<td>$mac_address</td>
			$empty_td
			$empty_td
		</tr>
			<td>DHCP mode</td>
			<td>$dhcpmode</td>
			<td>&nbsp;&nbsp;Profile</td>
			<td>$profile</td>
		</tr>
		<tr>
			<td COLSPAN='2' ALIGN='left'>$commit</td>
			<td COLSPAN='2' ALIGN='right'>$delete</td>
		</tr>
		
		$table_blank_line

EOH

	return 1;
}

sub check_readwrite
{
	my $attribute = shift;
	my $list_ref = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	
	my @l = @$list_ref;
	
	if ($attribute eq 'dnsstatus') {
		return 0 if (! $is_admin and ! $is_helpdesk);
	}
	
	if ($attribute eq 'dnsmode') {
		return 0 if (! $is_admin and ! $is_helpdesk);
	}
	
	return 1 if (defined ($l[0]) and $l[0] eq 'ALL');
	
	if (! grep (/^$attribute$/, @l)) {
		return 1;
	}

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
	my $i = localtime () . " modifyhost.cgi[$$]";
	warn ("$i: $error\n");
}
