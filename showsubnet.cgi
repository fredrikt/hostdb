#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to show information about subnets
#

use strict;
use Config::IniFiles;
use HOSTDB;

my $table_cols = 4;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Subnet details', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, $me);
## end generic initialization

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

## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@l, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});
HOSTDB::StdCGI::print_cgi_header ($q, "Subnet $subnetname", $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

my $static_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
my $dynamic_flag_days = $hostdbini->val ('subnet', 'static_flag_days');
list_subnet ($hostdb, $q, $subnet, $remote_user, $is_admin, $is_helpdesk, $static_flag_days, $dynamic_flag_days);

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
		<table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='100%'>
	        <!-- table width disposition tds -->
		<tr>
			<td WIDTH='25%'>&nbsp;</td>
			<td WIDTH='25%'>&nbsp;</td>
			<td WIDTH='25%'>&nbsp;</td>
			<td WIDTH='25%'>&nbsp;</td>
		</tr>

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
			<td>&nbsp;&nbsp;<b>IP</b></td>
			<td>&nbsp;<b>Hostname</b></th>
			<td>&nbsp;<b>MAC address</b></td>
			<td>&nbsp;<b>Last used&nbsp;</b></td>
		</tr>
EOH
    for $i (1 .. $subnet->addresses () - 2) {
	my $ip = $hostdb->ntoa ($subnet->n_netaddr () + $i);
	my @thesehosts = get_hosts_with_ip ($ip, @hosts);
	if (! @thesehosts) {
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
		print_hostaliases (\@o, $host);
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

    $q->print (join ("\n", @o), $table_blank_line, "\n\n\t</table>\n");

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
		   <td>$hostname</td>
		   <td>$mac</td>
		   <td NOWRAP>${ts_font}${mac_ts}${ts_font_end}</td>
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
    my $a_partof = $a->partof () || 0;
    if ($a_partof == $b->id ()) {
	return 1;
    }

    my $b_partof = $b->partof () || 0;
    if ($b_partof == $a->id ()) {
	return -1;
    }

    return $a->id () <=> $b->id ();
}

sub print_hostaliases
{
    my $o = shift;
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

	push (@$o, <<EOH);
                <tr>
                   <td ALIGN='center'>alias</td>
                   <td COLSPAN='3'>$alias_link $a_dnsstatus</td>
                </tr>

EOH
    }

    return 1;
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
