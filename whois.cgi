#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to search for different things in the database
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";
my $empty_td = "<td>&nbsp;</td>\n";

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

my $q = SUCGI2->new ($sucgi_ini,'hostdb');
my %links = $hostdb->html_links ($q);

my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');

$q->begin (title => "Whois");
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

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td COLSPAN='3' ALIGN='center'><h3>HOSTDB: Search</h3></td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

whois_form ($q);

$q->print ($table_hr_line);


perform_search ($hostdb, $q, $remote_user, $is_admin, $static_flag_days, $dynamic_flag_days);

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
        my $popup = $q->popup_menu (-name => 'whoisdatatype', -values => ['Guess', 'IP', 'FQDN', 'MAC', 'ID', 'Zone', 'Subnet'], -default => 'Guess');
	my $datafield = $q->textfield ('whoisdata');
	my $submit = $q->submit ('Search');

	$q->print (<<EOH);
		<tr>
		   <td COLSPAN='4' ALIGN='center'>
			<form ACTION='$me' METHOD='post'>
				$state_field
				Search for &nbsp;
				$popup &nbsp;
				$datafield &nbsp;
				$submit
			</form>
		   </td>
		</tr>
		$table_blank_line
EOH
}

sub perform_search
{
	my $hostdb = shift;
	my $q = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	my $static_flag_days = shift;
	my $dynamic_flag_days = shift;

	if ($q->param ('whoisdata')) {
		my $search_for = $q->param ('whoisdata');
		my $whoisdatatype = $q->param ('whoisdatatype');

		if (lc ($whoisdatatype) eq 'guess') {
			# check if it is a subnet - findhost () is uncapable of that
			$whoisdatatype = 'subnet' if ($hostdb->is_valid_subnet ($search_for));
		}

		my @host_refs;
		if (lc ($whoisdatatype) eq 'zone') {
			if ($hostdb->is_valid_domainname ($search_for)) {
				my $zone = $hostdb->findzonebyname ($search_for);

				if (defined ($zone)) {
					my $zonename = $zone->zonename ();
				
					# do access control
					if (! $is_admin) {
						if (! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
							error_line ($q, "You do not have sufficient access to zone '$zonename'");
							my $i = localtime () . " modifyhost.cgi[$$]";
							warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) tried to list zone '$zonename'\n"); 
							return 0;
						}
					}

					print_zone_info ($q, $hostdb, $zone, $is_admin);

					@host_refs = $hostdb->findhostbyzone ($search_for);
				} else {
					error_line ($q, "No such zone: '$search_for'");
				}
			} else {
				error_line ($q, "'$search_for' is not a valid domainname");
			}
		} elsif (lc ($whoisdatatype) eq 'subnet') {
			if ($hostdb->is_valid_subnet ($search_for)) {
				my $is_admin = $hostdb->auth->is_admin ($remote_user);

				my @subnets = $hostdb->findsubnetlongerprefix ($search_for);
				foreach my $subnet ($hostdb->findsubnetlongerprefix ($search_for)) {
					print_brief_subnet ($hostdb, $q, $subnet, $remote_user, $is_admin);
				}
			} else {
				error_line ($q, "'$search_for' is not a valid subnet");	
			}
			
			return undef;
		} else {
			@host_refs = $hostdb->findhost ($whoisdatatype, $search_for);
		}
		if ($hostdb->{error}) {
			error_line ($q, $hostdb->{error});
			return undef;
		}
		
		if (@host_refs) {
			if (1 == @host_refs) {
				# only one host, show detailed information
				foreach my $host (@host_refs) {
					$q->print ("<tr><th COLSPAN='4' ALIGN='left'>Host :</th></tr>");
		
					print_host_info ($q, $hostdb, $remote_user, $host);
				}
			} else {
				# more than one host record, show brief information

				$q->print (<<EOH);
					<tr>
					   <th ALIGN='left'>IP</th>
					   <th ALIGN='left'>Hostname</th>
					   <th ALIGN='left'>Mac address</th>
					   <th ALIGN='center'>Last used</th>
					</tr>
EOH
				foreach my $host (@host_refs) {
					print_brief_host_info ($q, $host, $static_flag_days, $dynamic_flag_days);
				}
			}

			#$q->print ($table_hr_line);

			return 1;
		} else {
			error_line ($q, "No match, searched for '$search_for' of type '$whoisdatatype'");
			
			if (lc ($whoisdatatype) ne 'zone') {
				if ($hostdb->is_valid_domainname ($search_for)) {
					my $me = $q->state_url ();
					$q->print (<<EOH);
						$empty_td
						<tr><td>
						Maybe you intended to
						<a HREF='$me;whoisdatatype=zone;whoisdata=$search_for'>search for a zone</a>
						called '$search_for'? I can't guess if it is a zonename
						or a hostname.
						</td></tr>
EOH
				}
			}
		}

		return 0;
	} else {
		$q->print ("<!-- no whoisdata, not searching -->\n");
		return undef;
	}
}

sub print_zone_info
{
	my $q = shift;
	my $hostdb = shift;
	my $zone = shift;
	my $is_admin = shift;

	my ($zonename, $id, $delegated, $default_ttl, $serial, $ttl, $mname, $rname,
	    $refresh, $retry, $expiry, $minimum, $owner);

	my $hostdbini = $hostdb->inifile ();

	my %zone_defaults;
	$zone_defaults{default_ttl} = $hostdbini->val ('zone', 'default_zone_ttl') || 'no default set';
	$zone_defaults{soa_ttl} = $hostdbini->val ('zone', 'default_soa_ttl') || 'no default set';
	$zone_defaults{soa_mname} = $hostdbini->val ('zone', 'default_soa_mname') || 'no default set';
	$zone_defaults{soa_rname} = $hostdbini->val ('zone', 'default_soa_rname') || 'no default set';
	$zone_defaults{soa_refresh} = $hostdbini->val ('zone', 'default_soa_refresh') || 'no default set';
	$zone_defaults{soa_retry} = $hostdbini->val ('zone', 'default_soa_retry') || 'no default set';
	$zone_defaults{soa_expiry} = $hostdbini->val ('zone', 'default_soa_expiry') || 'no default set';
	$zone_defaults{soa_minimum} = $hostdbini->val ('zone', 'default_soa_minimum') || 'no default set';
	
	# HTML
	$zonename = $zone->zonename ();
	$id = $zone->id ();
	$delegated = $zone->delegated ();
	$default_ttl = $zone->default_ttl () || 'default';
	$serial = $zone->serial () || 'NULL';
	$ttl = $zone->ttl () || 'default';
	$mname = $zone->mname () || 'default';
	$rname = $zone->rname () || 'default';
	$refresh = $zone->refresh () || 'default';
	$retry = $zone->retry () || 'default';
	$expiry = $zone->expiry () || 'default';
	$minimum = $zone->minimum () || 'default';
	$owner = $zone->owner ();
	
	my $modifyzone_link = '';
	if ($is_admin) {
		$modifyzone_link = "[<a HREF='$links{modifyzone};id=$id'>edit</a>]" if ($links{modifyzone});
	}
	
	if ($delegated eq 'N') {
		$delegated = 'No';
	} elsif ($delegated eq 'Y') {
		$delegated = '<font COLOR=\'red\'>Yes</font>';
	}
	
	$q->print (<<EOH);
		<tr>
			<td><strong>Zone</strong></td>
			<td><strong>$zonename</strong></td>
			<td>$modifyzone_link&nbsp;</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;Delegated</td>
			<td>$delegated</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;Default TTL</td>
			<td>$default_ttl seconds</td>
			<td>($zone_defaults{default_ttl})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;SOA ttl</td>
			<td>$ttl</td>
			<td>($zone_defaults{soa_ttl})</td>
			$empty_td
		</tr>
		<tr>
			<td><strong>SOA parameters</strong></td>
			$empty_td
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;serial</td>
			<td>$serial</td>
			<td>-</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;mname</td>
			<td>$mname</td>
			<td>($zone_defaults{soa_mname})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;rname</td>
			<td>$rname</td>
			<td>($zone_defaults{soa_rname})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;refresh</td>
			<td>$refresh</td>
			<td>($zone_defaults{soa_refresh})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;retry</td>
			<td>$retry</td>
			<td>($zone_defaults{soa_retry})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;expiry</td>
			<td>$expiry</td>
			<td>($zone_defaults{soa_expiry})</td>
			$empty_td
		</tr>
		<tr>
			<td>&nbsp;&nbsp;minimum</td>
			<td>$minimum</td>
			<td>($zone_defaults{soa_minimum})</td>
			$empty_td
		</tr>
		
		$table_hr_line
	
EOH
	return 1;
}

sub print_brief_host_info
{
	my $q = shift;
	my $host = shift;
	my $static_flag_days = shift;
	my $dynamic_flag_days = shift;

	# HTML
	my $ip = $host->ip ();
	my $id = $host->id ();
	my $me = $q->state_url ();
	my $hostname = $host->hostname () || '';
	my $mac = $host->mac_address () || '';
	my $mac_ts = $host->mac_address_ts () || '';

	# split at space to only get date and not time
	$mac_ts = (split (/\s/, $mac_ts))[0] || '';

	$ip = "<a HREF='$me;whoisdatatype=ID;whoisdata=$id'>$ip</a>";
						
	# check when host was last seen active on the network
	my $ts_font = '';
	my $ts_font_end = '';
						
	my $ts_flag_color = '#dd0000'; # bright red
	my $ts_flag_days = $static_flag_days;
						
	my $h_u_t = $host->unix_mac_address_ts ();

	if ($host->dhcpmode () eq 'DYNAMIC') {
		$ts_flag_days = $dynamic_flag_days;
		$mac = 'dynamic';
	}
						
	if (defined ($h_u_t) and
	    (time () - $h_u_t) >= ($ts_flag_days * 86400)) {
		# host has not been seen in active use
		# for $ts_flag_days days
		$ts_font = "<font COLOR='$ts_flag_color'>";
		$ts_font_end = '</font>';
	}


	$q->print (<<EOH);
		<tr>
		   <td>$ip&nbsp;</td>
		   <td>$hostname&nbsp;</td>
		   <td>$mac&nbsp;</td>
		   <td ALIGN='right' NOWRAP>${ts_font}${mac_ts}${ts_font_end}&nbsp;</td>
		</tr>
EOH

	return 1;
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
	my $comment = $host->comment () || 'NULL';
	my $owner = $host->owner ();
	my $dhcpstatus = $host->dhcpstatus ();
	my $dhcpmode = $host->dhcpmode ();
	my $dnsstatus = $host->dnsstatus ();
	my $dnsmode = $host->dnsmode ();
	my $ttl = $host->ttl () || 'default';
	my $profile = $host->profile () || 'default';
	my $dnszone = $host->dnszone () || '';
	my $manual_dnszone = $host->manual_dnszone ();

	my @warning;
	
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
	my $subnet = $hostdb->findsubnetbyip ($host->ip () || $q->param ('ip'));

	# get zone
	my $zone = $hostdb->findzonebyhostname ($host->hostname ());

	# check that user is allowed to edit both current zone and subnet

	my $authorized = 1;

	if (! $hostdb->auth->is_admin ($remote_user)) {
		$authorized = 0 if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user));

		# if there is no zone, only base desicion on subnet rights
		$authorized = 0 if (defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user));
	}

	# check that DNS zone is what it (most probably) should be
	if (defined ($zone) and ($zone->zonename () ne $dnszone)) {
		my $db_z = $zone->zonename ();
		push (@warning, "Host object says DNS zone '$dnszone' but a database check proposes zone '$db_z'. " .
				"If this is not a glue-record something needs to be fixed.");	
	}
	
	if ($manual_dnszone eq 'Y') {
		$manual_dnszone = "<font COLOR='red'>(Manual control)</font>";
	} else {
		$manual_dnszone = '';
	}
	
	my $zone_link;
	if ($dnszone) {
		$zone_link = "<a HREF='$me;whoisdatatype=zone;whoisdata=$dnszone'>$dnszone</a>&nbsp;$manual_dnszone";
	} else {
		$zone_link = "<font COLOR='red'>No zone set</font>&nbsp;$manual_dnszone";
	}
	
	my $modify_link = $authorized?"[<a HREF='$links{modifyhost};id=$id'>modify</a>]":'<!-- not authorized to modify -->';

	# format some things...
	
	if ($dhcpstatus ne 'ENABLED') {
		$dhcpstatus = "<font COLOR='red'><strong>$dhcpstatus</strong></font>";
	} else {
		$dhcpstatus = "Enabled";
	}

	if ($dnsstatus ne 'ENABLED') {
		$dnsstatus = "<font COLOR='red'><strong>$dnsstatus</strong></font>";
	} else {
		$dnsstatus = "Enabled";
	}
	
	if ($dnsmode eq "A_AND_PTR") {
		$dnsmode = "Both forward and reverse";
	} elsif ($dnsmode eq "A") {
		$dnsmode = "<font COLOR='red'>Only forward</font>";
	}

	if ($dhcpmode eq "STATIC") {
		$dhcpmode = "Static";
	} elsif ($dhcpmode eq "DYNAMIC") {
		$dhcpmode = "Dynamic";
	}
	
	$q->print (<<EOH);
	   <tr>
		$empty_td
		<td>ID</td>
		<td>$id&nbsp;$modify_link</td>
	   </tr>	
	   <tr>
		$empty_td
		<td>Parent</td>
		<td>$parent</td>
	   </tr>
EOH

	foreach my $t_warn (@warning) {
		error_line ($q, $t_warn);
	}

	my $t_host;
	foreach $t_host ($hostdb->findhostbypartof ($id)) {
		my $child = $t_host->id ()?$t_host->id ():'-';
		my $child_name = $t_host->hostname ();
		$child = "<a HREF='$me;whoisdatatype=ID;whoisdata=$child'>$child</a>&nbsp;($child_name)";
		
		$q->print (<<EOH);
			<tr>
				$empty_td
				<td>Child</td>
				<td>$child</td>
			</tr>
EOH
	}

	$q->print (<<EOH);
	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='4'>DNS</th>
	   </tr>
	   <tr>
		$empty_td
		<td>IP address</td>
		<td><strong>$ip</strong></td>
	   </tr>	
	   <tr>
		$empty_td
		<td>Hostname</td>
		<td><strong>$hostname</strong></td>
	   </tr>	
	   <tr>
		$empty_td
		<td>Zone</td>
		<td>$zone_link</td>
	   </tr>	
	   <tr>
		$empty_td
		<td>TTL</td>
		<td>$ttl seconds</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Mode</td>
	   	<td>$dnsmode</td>
	   </tr>	
	   <tr>
		$empty_td
	   	<td>Status</td>
	   	<td>$dnsstatus</td>
	   </tr>	


	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='4'>DHCP</th>
	   </tr>
	   <tr>
		$empty_td
		<td>MAC Address</td>
		<td>$mac</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Mode</td>
	   	<td>$dhcpmode</td>
	   </tr>	
	   <tr>
		$empty_td
	   	<td>Status</td>
	   	<td>$dhcpstatus</td>
	   </tr>	
	   	

	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='4'>General</th>
	   </tr>
	   <tr>
		$empty_td
		<td>Profile</td>
		<td><strong>$profile</strong></td>
	   </tr>	
	   <tr>
		$empty_td
		<td>Comment</td>
		<td>$comment</td>
	   </tr>	
	   <tr>
		$empty_td
		<td>Owner</td>
		<td>$owner</td>
	   </tr>	
	   
	   $table_blank_line
EOH
	if ($subnet) {
		# HTML
		my $s = $subnet->subnet ();
		my $netmask = $subnet->netmask ();
		my $desc = $subnet->description ();
	
		$s = "<a HREF='$links{showsubnet};subnet=$s'>$s</a>" if ($links{showsubnet});
	
		$q->print (<<EOH);
			<tr>
			   <th ALIGN='left'>Subnet</th>
			   <td>$s</td>
			    $empty_td
			</tr>
			<tr>
			   $empty_td
			   <td>Netmask</td>
			   <td>$netmask</td>
			</tr>
			<tr>
			   $empty_td
			   <td>Description</td>
			   <td>$desc</td>
			</tr>
EOH

	} else {
		error_line ($q, "Search failed: could not find subnet in database");
	}
	
	$q->print ($table_blank_line);	

	return 1;
}

sub print_brief_subnet
{
	my $hostdb = shift;
	my $q = shift;
	my $subnet = shift;
	my $remote_user = shift;
	my $is_admin = shift;

	# HTML
	my $id = $subnet->id ();

	my $subnet_link = $subnet->subnet ();
	if ($is_admin or $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
		$subnet_link = "<a HREF='$links{showsubnet};id=$id'>" . $subnet->subnet () . "</a>" if ($links{showsubnet});
	}

	my $h_desc = $q->escapeHTML ($subnet->description ()?$subnet->description ():'no description');

	$q->print (<<EOH);
		<tr>
			<td>$subnet_link</td>
			<td COLSPAN='3'>$h_desc</td>
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
	my $i = localtime () . " whois.cgi[$$]";
	warn ("$i: $error\n");
}
