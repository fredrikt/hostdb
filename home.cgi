#!/usr/local/bin/perl -w

eval 'exec /pkg/perl/5.8.6/bin/perl -w -S $0 ${1+"$@"}'
    if 0; # not running under some shell
#
# $Id$
#

use strict;
use HOSTDB;
use SUCGI2;
use Config::IniFiles;
use File::SearchPath qw/ searchpath /;


my $table_blank_line = "<tr><td COLSPAN='3'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='3'><hr></td></tr>\n";
my $empty_td = "<td>&nbsp;</td>\n";

my $debug = 0;
if (defined ($ARGV[0]) and ($ARGV[0] eq "-d")) {
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
$q->begin (title => 'HOSTDB home');

my $hostdb = eval {
	HOSTDB::DB->new (ini => $hostdbini, debug => $debug);
};

if ($@) {
	my $e = $@;
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>Could not create HOSTDB object: $e</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not create HOSTDB object: '$e'");
}

my %links = $hostdb->html_links ($q);

my $remote_user = $q->user(); 
unless ($remote_user) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");
}
my $is_admin = $hostdb->auth->is_admin ($remote_user);
my $is_helpdesk = $hostdb->auth->is_helpdesk ($remote_user);


my (@links, @admin_links);
push (@admin_links, "[<a HREF='$links{netplan}'>netplan</a>]") if ($is_admin and $links{netplan});
push (@links, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});

my $l = '';
if (@links or @admin_links) {
	$l = join(' ', @links, @admin_links);
}

$q->print (<<EOH);
	<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
		$table_blank_line
		<tr>
			<td COLSPAN='2' ALIGN='center'><h3>HOSTDB: Home</h3></td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

my ($subnets_ref, $zones_ref) = home_form ($q, $hostdb, $remote_user, $is_admin, $is_helpdesk);

if (defined ($q->param ('action') and $q->param ('action') eq 'Activate changes')) {
	activate_changes ($hostdb, $q, $hostdbini,
			  $subnets_ref, $zones_ref, $is_admin, $is_helpdesk, $remote_user);
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
	my $is_helpdesk = shift;	

	# HTML 
        my $state_field = $q->state_field ();
	my $me = $q->state_url ();
	my $reload = $q->submit (-name=>'action', -value=>'Activate changes',-class=>'button');
	my $user = '&nbsp';
	
	$user = $q->submit (-name=>'foo', -value=>'Pretend to be',-class=>'button') . "&nbsp;" . $q->textfield ('user') if ($is_admin);
	$reload .= "&nbsp;" . $q->textfield ('activateother') if ($is_admin or $is_helpdesk);

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
		  <td NOWRAP>
		    <form ACTION='$me' METHOD='post'>
		      $user_if_any
		      $reload
		    </form>
		  </td>
		  $empty_td
		  <td NOWRAP>
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

		my $zone_name = $zone->zonename ();
		next if (! $is_admin and $zone_name =~ /\.in-addr\.arpa$/);

		# interpolation
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

sub activate_changes
{
	my $hostdb = shift;
	my $q = shift;
	my $hostdbini = shift;
	my $subnets_ref = shift;
	my $zones_ref = shift;
	my $is_admin = shift;
	my $is_helpdesk = shift;
	my $remote_user = shift;
	
	my $msg = 'All subnets and zones above';
	my $abort = 0;
	
	if ($is_admin or $is_helpdesk) {
		my $activateother = $q->param ('activateother') || '';

		$activateother =~ s/^\s*(\S+)\s*$/$1/o;	# trim spaces

		if ($activateother) {
			if ($hostdb->is_valid_ip ($activateother)) {
				if ($activateother =~ /\.0+$/) {
					# prolly intended subnet /24
					$activateother .= '/24';
				} else {
					error_line ($q, "Cannot activate changes: argument '$activateother' is an IP address, not a subnet");
					return undef;
				}
			}
	
			if ($hostdb->is_valid_subnet ($activateother)) {
				my $s = $hostdb->findsubnet ($activateother);
				if (defined ($s)) {
					my $n = $s->subnet ();	# make sure we get correctly formatted name
					@$subnets_ref = ($n);
					@$zones_ref = ();
					$msg = "Subnet $n";
				} else {
					error_line ($q, "Cannot activate changes: Subnet '$activateother' not found");
					return undef;
				}	
			} elsif ($hostdb->clean_domainname ($activateother)) {
				my $z = $hostdb->findzonebyname ($activateother);
				if (defined ($z)) {
					my $n = $z->zonename ();	# make sure we get correctly formatted name
					@$zones_ref = ($n);
					@$subnets_ref = ();
					$msg = "Zone '$n'";
				} else {
					error_line ($q, "Cannot activate changes: Zone '$activateother' not found");
					return undef;
				}		
			} else {
				error_line ($q, "Cannot activate changes: Argument '$activateother' neither subnet nor domain");
				return undef;
			}
		}
	}

	my $res = request_reload ($hostdbini, $subnets_ref, $zones_ref, $q, $remote_user);
			
	if ($res) {
		my $time = localtime ();

		$q->print (<<EOH);
			<tr>
			  <td COLSPAN='3'>
			    <font COLOR='green' SIZE='2'><strong>
			      $time: $msg scheduled for reconfiguration
			    </strong></font>
			  </td>
			</tr>	
EOH
	} else {
		error_line ($q, "Something failed when activating changes, check logs!");
	}

	return $res;
}

sub request_reload
{
	my $hostdbini = shift;
	my $subnets_ref = shift;
	my $zones_ref = shift;
	my $q = shift;
	my $remote_user = shift;
	
	my $i = localtime () . " home.cgi[$$]";

	# build list of all requested zonenames plus the
	# ones for IPv4 reverse of the subnets from above
	my ($t, %zonenames);
	foreach $t (@$zones_ref) {
	        # don't request reload of delegated zones - that will just generate an error
		# about the zonefile not existing
	        my $z = $hostdb->findzonebyname ($t);
    		next if ($z->delegated () eq 'Y');

		$zonenames{$t} = 1;	
	}
	
	my @zonelist = sort keys %zonenames;

	my $num_zones = scalar @zonelist;
	my $num_subnets = scalar @$subnets_ref;

	if ($num_subnets or $num_zones) {
	    if ($num_subnets) {
		warn ("$i: user '$remote_user' requests reload of the following $num_subnets subnets : " . join (', ', @$subnets_ref) . "\n");
	    }	
	    if ($num_zones) {
		warn ("$i: user '$remote_user' requests reload of the following $num_zones zones : " . join (', ', @zonelist) . "\n");
	    }	

	    my $cmd = get_request_reload_command ($hostdbini);
	    if ($cmd) {
		my @args = ($cmd,
			    '--source',		'home.cgi',
			    '--requestor',	$remote_user
		    );

		system (@args) == 0
		    or die ("Failed executing command '$cmd'");
	    } else {
		warn ("Failed locating a 'request-reload' command, configure one " .
		      "in hostdb.ini [interface] -> request_reload_cmd\n");
		return 0;
	    }
	} else {
	    warn ("Found no zones or subnets to reload");
	    return 0;
	}
	
	return 1;
}

sub get_request_reload_command
{
    my $hostdbini = shift;
    
    my $cmd = $hostdbini->val ('interface', 'request_reload_cmd');

    return $cmd if ($cmd);

    # when not found, look in PATH for hostdb request-reload command.
    $cmd = searchpath('request-reload',
		      env => 'PATH',
		      exe => 1
	);

    if ($cmd) {
	warn ("Requesting reload through $cmd found in PATH.\n");
    }
    
    return $cmd;
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
