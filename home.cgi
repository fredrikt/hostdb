#!/usr/local/bin/perl -w
#
# $Id$
#

use strict;
use HOSTDB;
use SUCGI;
use SAM2;

my $table_blank_line = "<tr><td COLSPAN='3'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='3'><hr></td></tr>\n";
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

my $q = SUCGI->new ($sucgi_ini);
my %links = $hostdb->html_links ($q);

my $dhcp_signal_directory = $hostdbini->val('signals','dhcp_directory') if ($hostdbini->val('signals','dhcp_directory'));
my $dns_signal_directory = $hostdbini->val('signals','dns_directory') if ($hostdbini->val('signals','dns_directory'));

$q->begin (title => "HOSTDB home");
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
push (@links, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='600'>
		$table_blank_line
		<tr>
			<td COLSPAN='2' ALIGN='center'><h3>HOSTDB: Home</h3></td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

my ($subnets_ref, $zones_ref) = home_form ($q, $hostdb, $remote_user, $is_admin);

if (defined ($q->param ('action') and $q->param ('action') eq 'Activate changes')) {
	request_reload ($dhcp_signal_directory, $dns_signal_directory,
			$subnets_ref, $zones_ref, $q, $remote_user);
}

$q->print (<<EOH);
	</table>
EOH

$q->end ();


sub home_form
{
	my $q = shift;
	my $hostdb = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	
	# HTML 
        my $state_field = $q->state_field ();
	my $me = $q->state_url ();
	my $reload = $q->submit ('action', 'Activate changes');
	my $user = $q->submit ('foo', 'Pretend to be') . "&nbsp;" . $q->textfield ('user');

	$user = '&nbsp;' if (! $is_admin);
	
	$q->print ($table_hr_line);
	
	if ($is_admin and defined ($q->param ('user')) and $q->param ('user')) {
		$remote_user = $q->param('user');
		$is_admin = $hostdb->auth->is_admin ($remote_user);
	}
	
	my @zones = print_zones ($q, $hostdb, $remote_user, $is_admin);

	$q->print ($table_hr_line);
	
	my @subnets = print_subnets ($q, $hostdb, $remote_user, $is_admin);

	$q->print ($table_hr_line);

	my $user_if_any = '';
	if (defined ($q->param ('user')) and $q->param ('user')) {
		$user_if_any = "<input TYPE='hidden' NAME='user' VALUE='" . $q->param ('user') . "'>";
	}

	$q->print (<<EOH);
		<tr>
		  <td>
		    <form ACTION='$me' METHOD='post'>
		      $user_if_any
		      $reload
		    </form>
		  </td>
		  $empty_td
		  <td>
		    <form ACTION='$me' METHOD='post'>
		      $user
		    </form>
		  </td>
		</tr>
		$table_blank_line
EOH

	return (\@subnets, \@zones);
}

sub print_zones
{
	my $q = shift;
	my $hostdb = shift;
	my $remote_user = shift;
	my $is_admin = shift;

	my @res;
		
	$q->print (<<EOH);
		<tr>
		  <td COLSPAN='3'>
		  	<h3><strong>DNS</strong></h3>
		  </td>
		</tr>
		$table_blank_line
		<tr>
		  <th ALIGN='left'>Name</th>
		  <th ALIGN='left'>SOA serial</th>
		  $empty_td
		</tr>
EOH

	my $zone;
	my @zone_list = $hostdb->findallzones ();
	
	foreach $zone (@zone_list) {
		#if (! $is_admin) {
		#	next if (! defined ($zone) or ! $hostdb->auth->is_allowed_write ($zone, $remote_user));
		#}
		next if (! defined ($zone) or ! $hostdb->auth->is_owner ($zone, $remote_user));

		# interpolation
		my $zone_name = $zone->zonename ();
		my $serial = $zone->serial ();
		my $id = $zone->id();
		
		my @option_list;
		if ($is_admin and $links{modifyzone}) {
			push (@option_list, "[<a HREF='$links{modifyzone};id=$id'>edit</a>]");
		}

		my $options = join (' ', @option_list);

		my $zone_link = $zone_name;
		$zone_link = "<a HREF='$links{whois};whoisdatatype=zone;whoisdata=$zone_name'>$zone_name</a>" if ($links{whois});

		$q->print (<<EOH);
			<tr>
			  <td NOWRAP>
			    $zone_link&nbsp;
			  </td>
			  <td>
			    $serial
			  </td>
			  <td ALIGN='right'>
			    $options
			  </td>
			</tr>
EOH
		push (@res, $zone_name);
	}

	if (! @zone_list) {
		$q->print (<<EOH);
			<tr>
			  <td COLSPAN='3'>
				&nbsp;&nbsp;<font COLOR='red'><strong>No zones</strong></font>
			  </td>
			<tr>
EOH
	}

	$q->print ($table_blank_line);
	
	return (@res);
}

sub print_subnets
{
	my $q = shift;
	my $hostdb = shift;
	my $remote_user = shift;
	my $is_admin = shift;
	
	my @res;
	
	$q->print (<<EOH);
		<tr>
		  <td COLSPAN='3'>
		  	<h3><strong>DHCP</strong></h3>
		  </td>
		</tr>
		$table_blank_line
		<tr>
		  <th ALIGN='left'>Subnet</th>
		  <th ALIGN='left'>Description</th>
		  $empty_td
		</tr>
EOH

	my $subnet;
	my @subnet_list = $hostdb->findallsubnets ();
	
	foreach $subnet (@subnet_list) {
		#if (! $is_admin) {
		#	next if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user));
		#}
		next if (! defined ($subnet) or ! $hostdb->auth->is_owner ($subnet, $remote_user));

		# interpolation
		my $subnet_name = $subnet->subnet ();
		my $description = $q->escapeHTML ($subnet->description ()?$subnet->description ():'no description');
		my $id = $subnet->id();
		
		if (length ($description) > 30) {
			$description = substr ($description, 0, 30) . "...";
		}

		my @option_list;
		if ($is_admin and $links{modifysubnet}) {
			push (@option_list, "[<a HREF='$links{modifysubnet};id=$id'>edit</a>]");
		}

		my $options = join (' ', @option_list);

		my $subnet_link = $subnet_name;
		if ($links{showsubnet}) {
			$subnet_link = "<a HREF='$links{showsubnet};subnet=$subnet_name'>$subnet_name</a>";
		}

		$q->print (<<EOH);
			<tr>
			  <td NOWRAP>
			    $subnet_link&nbsp;
			  </td>
			  <td NOWRAP>
			    $description&nbsp;
			  </td>
			  <td ALIGN='right'>
			    $options
			  </td>
			</tr>
EOH
		push (@res, $subnet_name);
	}

	if (! @subnet_list) {
		$q->print (<<EOH);
			<tr>
			  <td COLSPAN='3'>
				&nbsp;&nbsp;<font COLOR='red'><strong>No subnets</strong></font>
			  </td>
			<tr>
EOH
	}
	
	$q->print ($table_blank_line);
	
	return (@res);
}

sub request_reload
{
	my $dhcp_signal_directory = shift;
	my $dns_signal_directory = shift;
	my $subnets_ref = shift;
	my $zones_ref = shift;
	my $q = shift;
	my $remote_user = shift;
	
	my $sam;

	if (! $dhcp_signal_directory) {
		error_line ($q, "Can't request reconfiguration, DHCP message spool directory not set");
		return undef;
	}
	if (! $dns_signal_directory) {
		error_line ($q, "Can't request reconfiguration, DNS message spool directory not set");
		return undef;
	}
		
	if (! -d $dhcp_signal_directory) {
		error_line ($q, "Can't request reconfiguration, DHCP message spool directory '$dhcp_signal_directory' does not exist");
		return undef;
	}
	if (! -d $dns_signal_directory) {
		error_line ($q, "Can't request reconfiguration, DNS message spool directory '$dns_signal_directory' does not exist");
		return undef;
	}
		
	$sam = SAM2->new (directory => $dhcp_signal_directory, name => 'home.cgi');
	if (! defined ($sam)) {
		error_line ($q, 'Could not create SAM object (directory $dhcp_signal_directory)');
		return 0;
	}
	
	$sam->send ({msg => join (',', @$subnets_ref)}, 'configure');
	# or error_line ($q, "WARNING: Message might not have been sent (directory $dhcp_signal_directory)");
	$sam = undef;
	
	$sam = SAM2->new (directory => $dns_signal_directory, name => 'home.cgi');
	if (! defined ($sam)) {
		error_line ($q, "Could not create SAM object (directory $dns_signal_directory)");
		return 0;
	}
	
	$sam->send ({msg => join (',', @$zones_ref)}, 'configure');
	# or error_line ($q, "WARNING: Message might not have been sent (directory $dns_signal_directory)");
	$sam = undef;
	
	my $time = localtime ();

	$q->print (<<EOH);
		<tr>
		  <td COLSPAN='3'>
		    <font COLOR='green' SIZE='2'><strong>
		      $time: All subnets and zones above scheduled for reconfiguration
		    </strong></font>
		  </td>
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
		<td COLSPAN='3'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
	my $i = localtime () . " home.cgi[$$]";
	warn ("$i: $error\n");
}
