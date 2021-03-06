#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to search for different things in the database
#

use strict;
use HOSTDB;

my $table_cols = 5;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Whois', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, \$me);
## end generic initialization

## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
HOSTDB::StdCGI::print_cgi_header ($q, 'Search', $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

whois_form ($q, $table_cols);

my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
perform_search ($hostdb, $q, $remote_user, $is_admin, $is_helpdesk, $static_flag_days, $dynamic_flag_days, $table_cols);

$q->end ();


sub whois_form
{
    my $q = shift;
    my $table_cols = shift;

    my @popup_values = ('Guess', 'IP', 'FQDN', 'MAC', 'ID', 'Zone', 'Subnet', 'AliasID');

    my $popup_value = '';
    my $whoisdata;

    $whoisdata = $q->param ('whoisdata') || $q->param ('data') || '';
    my $t = $q->param ('whoisdatatype') || $q->param ('datatype') || $q->param ('type') || '';
    my $in = lc ($t);
    # since we have multiple possible form parameter names, and the input may have mixed
    # case we must do some work to find out which value of the popup that should be pre-selected
    foreach $t (@popup_values) {
	if (lc ($t) eq $in) {
	    $popup_value = $t;
	    last;
	}
    }
    # default to the first entry in @popup_values
    $popup_value = $popup_values[0] if (! $popup_value);

    # HTML
    my $state_field = $q->state_field ();
    my $me = $q->state_url ();
    my $popup = $q->popup_menu (-name => 'whoisdatatype', -values => [@popup_values], -default => $popup_value);
    my $datafield = $q->textfield ('whoisdata', $whoisdata);
    my $submit = $q->submit (-name => 'Search', -class => 'button');

    $q->print (<<EOH);
    	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
		<tr>
		   <td COLSPAN='$table_cols' ALIGN='center'>
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
	</table>
EOH
    return 1;
}

sub perform_search
{
    my $hostdb = shift;
    my $q = shift;
    my $remote_user = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $static_flag_days = shift;
    my $dynamic_flag_days = shift;
    my $table_cols = shift;

    my $whoisdata = $q->param ('whoisdata') || $q->param ('data') || '';
    if ($whoisdata) {
	$q->print (<<EOH);
		<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
			<!-- table width disposition tds -->
				<tr>
					<td WIDTH='20%'>&nbsp;</td>
					<td WIDTH='20%'>&nbsp;</td>
					<td WIDTH='20%'>&nbsp;</td>
					<td WIDTH='20%'>&nbsp;</td>
					<td WIDTH='20%'>&nbsp;</td>
				</tr>
EOH

	my $search_for = lc ($whoisdata);
	my $t = $q->param ('whoisdatatype') || $q->param ('datatype') || $q->param ('type') || '';
	my $whoisdatatype = lc ($t);

	$search_for =~ s/^\s*(\S+)\s*$/$1/o;	# trim spaces

	if ($whoisdatatype eq 'guess') {
	    # check if it is a subnet - findhost () is uncapable of that
	    $whoisdatatype = 'subnet' if ($hostdb->is_valid_subnet ($search_for));
	}

	my @host_refs;
	if ($whoisdatatype eq 'zone') {
	    if ($hostdb->is_valid_domainname ($search_for)) {
		my $zone = $hostdb->findzonebyname ($search_for);

		if (defined ($zone)) {
		    my $zonename = $zone->zonename ();

		    # do access control
		    if (! $is_admin and ! $is_helpdesk) {
			if (! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
			    error_line ($q, "You do not have sufficient access to zone '$zonename'");
			    my $i = localtime () . " modifyhost.cgi[$$]";
			    warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) tried to list zone '$zonename'\n");
			    return 0;
			}
		    }

		    @host_refs = $hostdb->findhostbyzone ($search_for);

		    my $hostdbini = $hostdb->inifile ();
		    my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
		    my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');

		    print_zone_info ($q, $hostdb, $zone, \@host_refs,
				     $static_flag_days, $dynamic_flag_days,
				     $is_admin, $is_helpdesk, $table_cols);
		} else {
		    error_line ($q, "No such zone: '$search_for'");
		}
	    } else {
		error_line ($q, "'$search_for' is not a valid domainname");
	    }
	} elsif ($whoisdatatype eq 'subnet') {
	    if ($hostdb->is_valid_ip ($search_for)) {
		# user has not entered a subnet size, default to /24
		$search_for .= '/24';
	    }

	    if ($hostdb->is_valid_subnet ($search_for)) {
		my @subnets = $hostdb->findsubnetlongerprefix ($search_for);
		foreach my $subnet ($hostdb->findsubnetlongerprefix ($search_for)) {
		    print_brief_subnet ($hostdb, $q, $subnet, $remote_user, $is_admin, $is_helpdesk);
		}
	    } else {
		error_line ($q, "'$search_for' is not a valid subnet");
	    }

	    return undef;
	} elsif ($whoisdatatype eq 'aliasid') {
	    if ($search_for !~ /^\d+$/) {
		error_line ($q, "Invalid alias ID : '$search_for'");
	    } else {
		my $alias = $hostdb->findhostaliasbyid ($search_for);
		print_alias ($hostdb, $q, $alias, $remote_user, $is_admin, $is_helpdesk);

		$q->print ("$table_blank_line");
	    }
	} else {
	    if (is_wildcard ($search_for)) {
		if (! $is_admin and ! $is_helpdesk) {
		    error_line ($q, "You are not permitted to search using wildcards");
		    warn ("You are not permitted to search using wildcards");
		    return undef;
		}

		@host_refs = $hostdb->findhostbywildcardname ($search_for);
	    } else {
		@host_refs = $hostdb->findhost ($whoisdatatype, $search_for);
	    }
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

		    print_host_info ($q, $hostdb, $host, $remote_user, $is_admin, $is_helpdesk, $table_cols);
		}
	    } else {
		# more than one host record, show brief information

		$q->print (<<EOH);
					<tr>
					   <th ALIGN='left'>&nbsp;&nbsp;IP</td>
					   <th ALIGN='left'>&nbsp;Hostname</td>
					   <th ALIGN='left'>&nbsp;MAC address</td>
					   <th ALIGN='left'>&nbsp;Last used</td>
					   <th ALIGN='left'>&nbsp;Comment</th>
					</tr>
EOH
		foreach my $host (@host_refs) {
		    print_brief_host_info ($q, $hostdb, $host, $static_flag_days, $dynamic_flag_days);
		    print_brief_host_aliases ($q, $host);
		}
	    }

	    #$q->print ($table_hr_line);
	    $q->print ("\n\t\t</table>\n");
	    return 1;
	} else {
	    if ($whoisdatatype eq 'aliasid') {
		# placeholder
		$q->print ("\n");
	    } elsif ($whoisdatatype eq 'zone') {
		if ($search_for !~ /\.in-addr\.arpa$/) {
		    $q->print (<<EOH);
						<tr>
						  <td COLSPAN='$table_cols'>No hosts found in zone '$search_for'</td>
						</tr>
EOH
		}
	    } else {
		error_line ($q, "No match, searched for '$search_for' of type '$whoisdatatype'");

		if ($hostdb->is_valid_domainname ($search_for)) {
		    my $me = $q->state_url ();
		    $q->print (<<EOH);
						$empty_td
						<tr><td COLSPAN='$table_cols'>
						Maybe you intended to
						<a HREF='$me;whoisdatatype=zone;whoisdata=$search_for'>search for a zone</a>
						called '$search_for'? I can\'t guess if it is a zonename
						or a hostname.
						</td></tr>
EOH
		}
	    }
	}

	$q->print ("\n\t\t</table>\n");
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
    my $hosts_ref = shift;
    my $static_flag_days = shift;
    my $dynamic_flag_days = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $table_cols = shift;

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

    # Statistics
    my $static_hosts = 0;
    my $static_in_use = 0;
    my $dynamic_in_use = 0;
    my $dynamic_hosts = 0;

    foreach my $host (@$hosts_ref) {
	my $h_u_t = $host->unix_mac_address_ts ();

	if ($host->dhcpmode () eq 'DYNAMIC') {
	    $dynamic_hosts++;
	    $dynamic_in_use++ if (defined ($h_u_t) and
				  (time () - $h_u_t) < ($dynamic_flag_days * 86400));
	} else {
	    $static_hosts++;
	    $static_in_use++ if (defined ($h_u_t) and
				 (time () - $h_u_t) < ($static_flag_days * 86400));
	}
    }

    my $num_hosts = $static_hosts + $dynamic_hosts;
    my $static_percent = int (safe_div ($static_hosts, $num_hosts) * 100);
    my $dynamic_percent = int (safe_div ($dynamic_hosts, $num_hosts) * 100);
    my $static_usage_percent = int (safe_div ($static_in_use, $static_hosts) * 100);
    my $dynamic_usage_percent = int (safe_div ($dynamic_in_use, $dynamic_hosts) * 100);
    my $addresses_needed = $static_in_use + $dynamic_hosts;

    # HTML
    $zonename = $zone->zonename ();
    $id = $zone->id ();
    $delegated = $zone->delegated ();
    $serial = $zone->serial () || 'NULL';
    $mname = $zone->mname () || 'default';
    $rname = $zone->rname () || 'default';
    $refresh = $zone->refresh () || 'default';
    $retry = $zone->retry () || 'default';
    $expiry = $zone->expiry () || 'default';
    $minimum = $zone->minimum () || 'default';
    $owner = $zone->owner ();

    if ($zone->default_ttl ()) {
	$default_ttl = $zone->default_ttl () . " seconds";
    } else {
	$default_ttl = 'default';
    }
    if ($zone->ttl ()) {
	$ttl = $zone->ttl () . " seconds";
    } else {
	$ttl = 'default';
    }

    my $modifyzone_link = '';
    if ($is_admin) {
	$modifyzone_link = "[<a HREF='$links{modifyzone};id=$id'>edit</a>]" if ($links{modifyzone});
    }

    if ($delegated eq 'N') {
	$delegated = 'No';
    } elsif ($delegated eq 'Y') {
	$delegated = '<font COLOR=\'red\'>Yes</font>';
    }

    # for interpolation
    my $table_cols_1 = $table_cols - 1;
    my $table_cols_2 = $table_cols - 2;
    my $table_cols_3 = $table_cols - 3;
    my $table_cols_4 = $table_cols - 4;

    $q->print (<<EOH);
		<tr>
			<th ALIGN='left'>Zone</th>
			<th ALIGN='left'>$zonename</td>
			<td COLSPAN='$table_cols_2'>$modifyzone_link&nbsp;</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;Delegated</td>
			<td COLSPAN='$table_cols_1'>$delegated</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;Owner</td>
			<td COLSPAN='$table_cols_1'>$owner</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;Default TTL</td>
			<td>$default_ttl</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{default_ttl})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;SOA ttl</td>
			<td>$ttl</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_ttl})</td>
		</tr>
		<tr>
			<th ALIGN='left' COLSPAN='$table_cols'>SOA parameters</strong></th>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;serial</td>
			<td>$serial</td>
			<td>-</td>
			<td COLSPAN='$table_cols_1'>&nbsp;</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;mname</td>
			<td>$mname</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_mname})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;rname</td>
			<td>$rname</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_rname})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;refresh</td>
			<td>$refresh</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_refresh})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;retry</td>
			<td>$retry</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_retry})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;expiry</td>
			<td>$expiry</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_expiry})</td>
		</tr>
		<tr>
			<td>&nbsp;&nbsp;minimum</td>
			<td>$minimum</td>
			<td COLSPAN='$table_cols_3'>($zone_defaults{soa_minimum})</td>
		</tr>

		<tr>
			<th ALIGN='left' COLSPAN='$table_cols'>Zone hosts statistics</strong></th>
		</tr>
		<tr>
		   <td>Hosts</td>
		   <td COLSPAN='$table_cols_2'>$num_hosts</td>
		</tr>
		<tr>
		   <td>Static hosts</td>
		   <td>$static_hosts ($static_percent%)</td>
		   <td>in use</td>
		   <td COLSPAN='$table_cols_4'>$static_in_use/$static_hosts ($static_usage_percent%)</td>
		</tr>
		<tr>
		   <td>Dynamic hosts</td>
		   <td>$dynamic_hosts ($dynamic_percent%)</td>
		   <td>in use</td>
		   <td COLSPAN='$table_cols_4'>$dynamic_in_use/$dynamic_hosts ($dynamic_usage_percent%)</td>
		</tr>

		$table_blank_line

		<tr>
		   <td COLSPAN='2'>Addresses needed</td>
		   <td COLSPAN='$table_cols_2'>$static_in_use + $dynamic_hosts = $addresses_needed</td>
		</tr>
		$table_hr_line

EOH
    return 1;
}

sub print_brief_host_info
{
    my $q = shift;
    my $hostdb = shift;
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
    my $comment = get_formatted_comment ($host);

    my $parent_link = '';
    my $partof = $host->partof ();
    if (defined ($partof) and $partof > 0) {
	# find parent hostname
	my $parent = $hostdb->findhostbyid ($partof);
	if ($parent) {
	    my $h = $parent->hostname () || '';
	    $parent_link = "(<a HREF='$me;whoisdatatype=ID;whoisdata=$id'>$h</a>)&nbsp;";
	}
    }

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
		   <td>$hostname&nbsp;$parent_link</td>
		   <td>$mac&nbsp;</td>
		   <td NOWRAP>${ts_font}${mac_ts}${ts_font_end}&nbsp;</td>
		   <td NOWRAP>${comment}</td>
		</tr>
EOH

    return 1;
}

sub print_brief_host_aliases
{
    my $q = shift;
    my $host = shift;

    my @aliases = $host->init_aliases ();

    foreach my $a (@aliases) {
        my $aliasname = $a->aliasname ();
        my $id = $a->id ();
        my $alias_link = "<a HREF='$links{whois};type=aliasid;data=$id'>$aliasname</a>";
        my $a_dnsstatus = $a->dnsstatus ();

        if ($a_dnsstatus eq 'ENABLED') {
            $a_dnsstatus = '';
        } else {
            $a_dnsstatus = "&nbsp;(dns <font color='red'><strong>DISABLED</strong></font>)";
        }

        $q->print (<<EOH);
                <tr>
                   <td ALIGN='center'>alias</td>
                   <td COLSPAN='3'>$alias_link $a_dnsstatus</td>
		   <td>&nbsp;</td>
                </tr>

EOH
}

    return 1;
}

sub print_host_info
{
    my $q = shift;
    my $hostdb = shift;
    my $host = shift;
    my $remote_user = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $table_cols = shift;

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

    # for interpolation
    my $table_cols_1 = $table_cols - 1;
    my $table_cols_2 = $table_cols - 2;
    my $table_cols_3 = $table_cols - 3;
    my $table_cols_4 = $table_cols - 4;

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

    if (! $is_admin and ! $is_helpdesk) {
	$authorized = 0 if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user));

	# if there is no zone, only base decision on subnet rights
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


    my $hostattributes_link = '';
    if ($is_admin or $is_helpdesk) {
	my @attrs = $host->init_attributes ();
	my $numattrs = scalar @attrs;

	if ($numattrs > 0) {
	    if ($links{hostattributes}) {
		$hostattributes_link = "[<a HREF='$links{hostattributes};id=$id'>attributes</a>]";
	    } else {
		$hostattributes_link = "[$numattrs attributes but no path to hostattributes.cgi]";
	    }
	} else {
	    $hostattributes_link = "[no attributes]";
	}
    }

    my $add_alias_link = '';
    if ($links{hostalias}) {
	$add_alias_link = $authorized?"[<a HREF='$links{hostalias};hostid=$id'>add alias</a>]":'<!-- not authorized to modify -->';
    }

    my $aliases_tr = '';
    my @hostaliases = $host->init_aliases ();
    if (@hostaliases) {
	my @a;
	foreach my $alias (@hostaliases) {
	    my $a_id = $alias->id ();
	    my $a_name = $alias->aliasname ();
	    my $a_dnsstatus = html_color_disabled ($alias->dnsstatus ());

	    if ($a_dnsstatus eq 'Enabled') {
		$a_dnsstatus = '';
	    } else {
		$a_dnsstatus = "&nbsp;(dns $a_dnsstatus)";
	    }
	    push (@a, "<a HREF='$me;type=aliasid;data=$a_id'>$a_name</a>$a_dnsstatus");
	}
	my $aliases = join (", ", @a);
	$aliases_tr =
	    "\t<tr>\n" .
	    "\t\t$empty_td\n" .
	    "\t\t<td>Aliases</td>\n" .
	    "\t\t<td COLSPAN='$table_cols_3'>$aliases</td>\n" .
	    "\t</tr>";
    }

    # format some things...

    $dhcpstatus = html_color_disabled ($dhcpstatus);
    $dnsstatus = html_color_disabled ($dnsstatus);

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
		<td NOWRAP>$id&nbsp;$modify_link $hostattributes_link $add_alias_link</td>
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
	my $comment = get_formatted_comment ($host);

	$q->print (<<EOH);
			<tr>
				$empty_td
				<td>Child</td>
				<td>$child</td>
				<td COLSPAN='$table_cols_4'>$comment</td>
			</tr>
EOH
    }

    $q->print (<<EOH);
	   $aliases_tr

	   $table_blank_line

	   <tr>
		<th ALIGN='left' COLSPAN='$table_cols'>DNS</th>
	   </tr>
	   <tr>
		$empty_td
		<td>IP address</td>
		<td COLSPAN='$table_cols_3'><strong>$ip</strong></td>
	   </tr>
	   <tr>
		$empty_td
		<td>Hostname</td>
		<td COLSPAN='$table_cols_3'><strong>$hostname</strong></td>
	   </tr>
	   <tr>
		$empty_td
		<td>Zone</td>
		<td COLSPAN='$table_cols_3'>$zone_link</td>
	   </tr>
	   <tr>
		$empty_td
		<td>TTL</td>
		<td COLSPAN='$table_cols_3'>$ttl</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Mode</td>
	   	<td COLSPAN='$table_cols_3'>$dnsmode</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Status</td>
	   	<td COLSPAN='$table_cols_3'>$dnsstatus</td>
	   </tr>


	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='$table_cols'>DHCP</th>
	   </tr>
	   <tr>
		$empty_td
		<td>MAC Address</td>
		<td COLSPAN='$table_cols_3'>$mac</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Mode</td>
	   	<td COLSPAN='$table_cols_3'>$dhcpmode</td>
	   </tr>
	   <tr>
		$empty_td
	   	<td>Status</td>
	   	<td COLSPAN='$table_cols_3'>$dhcpstatus</td>
	   </tr>


	   $table_blank_line
	   <tr>
		<th ALIGN='left' COLSPAN='$table_cols'>General</th>
	   </tr>
	   <tr>
		$empty_td
		<td>Profile</td>
		<td COLSPAN='$table_cols_3'><strong>$profile</strong></td>
	   </tr>
	   <tr>
		$empty_td
		<td>Comment</td>
		<td COLSPAN='$table_cols_3'>$comment</td>
	   </tr>
	   <tr>
		$empty_td
		<td>Owner</td>
		<td COLSPAN='$table_cols_3'>$owner</td>
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
			   <td COLSPAN='$table_cols_2'>$s</td>
			</tr>
			<tr>
			   $empty_td
			   <td>Netmask</td>
			   <td COLSPAN='$table_cols_3'>$netmask</td>
			</tr>
			<tr>
			   $empty_td
			   <td>Description</td>
			   <td COLSPAN='$table_cols_3'>$desc</td>
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
    my $is_helpdesk = shift;

    # HTML
    my $id = $subnet->id ();

    my $subnet_link = $subnet->subnet ();
    if ($is_admin or $is_helpdesk or
	$hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
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

sub print_alias
{
    my $hostdb = shift;
    my $q = shift;
    my $alias = shift;
    my $remote_user = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;

    error_line ($q, 'No alias found'), return undef unless ($alias);

    my $me = $q->state_url ();

    # HTML interpolation
    my $aliasname = $alias->aliasname ();
    my $id = $alias->id ();
    my $hostid = $alias->hostid ();
    my $comment = $alias->comment () || '';
    my $ttl = $alias->ttl () || 'default';
    my $dnsstatus = html_color_disabled ($alias->dnsstatus ());

    my $hostname = 'NOT FOUND';
    my $hostlink = '';
    my $zone;
    my $host = $hostdb->findhostbyid ($hostid);
    if ($host) {
	$hostname = $host->hostname ();
	$hostlink = "<a HREF='$me;type=ID;data=$hostid'>$hostname</a>";

	# get zone of host
	$zone = $hostdb->findzonebyhostname ($host->hostname ());
    }

    # check that user is allowed to edit both current zone and subnet

    my $authorized = 1;

    if (! $is_admin and ! $is_helpdesk) {
        # if there is no zone, disallow editing
        $authorized = 0 if (! defined ($zone) or ! $hostdb->auth->is_allowed_write ($zone, $remote_user));
    }

    my $modify_link = '<!-- hostalias cgi not defined -->';
    $modify_link = $authorized?"[<a HREF='$links{hostalias};id=$id'>modify</a>]":'<!-- not authorized to modify -->' if (defined ($links{hostalias}));
    my $delete_link = '<!-- deletehostalias cgi not defined -->';
    $delete_link = $authorized?"[<a HREF='$links{deletehostalias};id=$id'>delete</a>]":'<!-- not authorized to delete -->' if (defined ($links{deletehostalias}));


    $q->print (<<EOH);
    			<tr><th COLSPAN='3' ALIGN='left'>Alias (CNAME) :</th></tr>
                        <tr>
			   $empty_td
                           <th ALIGN='left'>Aliasname</th>
                           <td>$aliasname</td>
                        </tr>
			<tr>
			   $empty_td
			   <td>ID</td>
			   <td>$id&nbsp;&nbsp;&nbsp;$modify_link&nbsp;$delete_link</td>
			</td>
                        <tr>
                           $empty_td
                           <td>DNS TTL</td>
                           <td>$ttl</td>
                        </tr>
                        <tr>
                           $empty_td
                           <td>DNS status</td>
                           <td>$dnsstatus</td>
                        </tr>


			$table_blank_line
                        <tr>
                           $empty_td
                           <td>Comment</td>
                           <td>$comment</td>
                        </tr>

			$table_blank_line
			<tr>
			   $empty_td
			   <th ALIGN='left'>Hostname</th>
			   <td>$hostlink</td>
			</tr>
EOH

}

sub safe_div
{
    my $a = shift;
    my $b = shift;

    return ($a / $b) if ($a != 0 and $b != 0);

    return 0;
}

sub is_wildcard
{
    my $in = shift;

    return 1 if ($in =~ /%/);
    return 1 if ($in =~ /\*/);

    return 0;
}

sub html_color_disabled
{
    my $val = shift;

    if ($val ne 'ENABLED') {
	return ("<font COLOR='red'><strong>$val</strong></font>");
    } else {
	return ("Enabled");
    }
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

sub get_formatted_comment
{
    my $host = shift;

    my $comment = $host->comment () || '&nbsp;';

    $comment = '' if ($comment eq 'dns-import');
    if (length ($comment) > 17) {
	if (length ($comment) <= 20) {
	    $comment = substr ($comment, 0, 20);
	} else {
	    $comment = substr ($comment, 0, 17) . '...';
	}
    }

    return $comment;
}
