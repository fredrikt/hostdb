#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to modify/create zone objects
#

use strict;
use HOSTDB;

my $table_cols = 3;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Modify Zone', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, \$me);
## end generic initialization

my %zone_defaults;
$zone_defaults{default_ttl} = $hostdbini->val ('zone', 'default_zone_ttl');
$zone_defaults{soa_ttl} = $hostdbini->val ('zone', 'default_soa_ttl');
$zone_defaults{soa_mname} = $hostdbini->val ('zone', 'default_soa_mname');
$zone_defaults{soa_rname} = $hostdbini->val ('zone', 'default_soa_rname');
$zone_defaults{soa_refresh} = $hostdbini->val ('zone', 'default_soa_refresh');
$zone_defaults{soa_retry} = $hostdbini->val ('zone', 'default_soa_retry');
$zone_defaults{soa_expiry} = $hostdbini->val ('zone', 'default_soa_expiry');
$zone_defaults{soa_minimum} = $hostdbini->val ('zone', 'default_soa_minimum');

if (! $hostdb->auth->is_admin ($remote_user)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not authorized to change zones.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: User '$remote_user' denied\n");
}

my $zone;

my $id = $q->param('id');
if (defined ($id) and $id ne '') {
	$zone = get_zone ($hostdb, $id);
}
# else {
#	$zone = $hostdb->create_zone ();
#	if (defined ($zone)) {
#		# set some defaults
#		$zone->profilelist ('default');
#	}
#}

if (! defined ($zone)) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No zone found (hostdb error: $hostdb->{error})</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not get/create zone (hostdb error: $hostdb->{error})");
}


## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@l, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});
HOSTDB::StdCGI::print_cgi_header ($q, 'Modify Zone', $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

	$q->print (<<EOH);
		<form ACTION='$me' METHOD='post'>
		<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
			<!-- table width disposition tds -->
				<tr>
					<td WIDTH='25%'>&nbsp;</td>
					<td WIDTH='25%'>&nbsp;</td>
					<td WIDTH='25%'>&nbsp;</td>
					<td WIDTH='25%'>&nbsp;</td>
				</tr>
EOH

my $action = lc ($q->param('action'));
$action = 'search' unless $action;

if ($action eq 'commit') {
    if (modify_zone ($hostdb, $zone, \%zone_defaults, $q, $remote_user)) {
	my $i = localtime () . " modifyzone.cgi[$$]";
	eval
	{
	    $zone->commit ();
	};
	$id = $zone->id () if (! defined ($id) and defined ($zone));
	if ($@) {
	    error_line ($q, "Could not commit changes: $@");
	    warn ("$i Changes to zone with id '$id' could not be committed ($@)\n");
	} else {
	    warn ("$i Changes to zone with id '$id' committed successfully\n");
	}
    }
    $id = $zone->id () if (! defined ($id) and defined ($zone));
    $zone = get_zone ($hostdb, $id); # read-back
} elsif ($action eq 'search') {
    # call modify_zone but don't commit () afterwards to get
    # stuff supplied to us as CGI parameters
    # set on the zone before we call host_form () below.
    modify_zone ($hostdb, $zone, \%zone_defaults, $q, $remote_user);
} else {
    error_line ($q, 'Unknown action');
    $zone = undef;
}


if (defined ($zone)) {
    zone_form ($q, $zone, \%zone_defaults, $remote_user);
}

END:
$q->print (<<EOH);
	</table>
    </form>
EOH

$q->end();


sub modify_zone
{
    my $hostdb = shift;
    my $zone = shift;
    my $zone_defaults_ref = shift;
    my $q = shift;
    my $remote_user = shift;
    
    my (@changelog, @warning);
	
    eval {
	die ("No zone object") unless ($zone);
	
	$zone->_set_error ('');		
	
	my $identify_str = "id:'" . ($zone->id () || 'no id') . "' zone:'" . ($zone->zonename () || 'no zonename') . "'";
	
	# this is a hash and not an array to provide a better framework
	my %changer = ('delegated'		=> 'delegated',
		       'default_ttl'		=> 'default_ttl',
		       'ttl'			=> 'ttl',
		       'mname'			=> 'mname',
		       'rname'			=> 'rname',
		       'refresh'		=> 'refresh',
		       'retry'			=> 'retry',
		       'expiry'			=> 'expiry',
		       'minimum'		=> 'minimum',
		       'owner'			=> 'owner'
		       );
	
	foreach my $name (keys %changer) {
	    my $new_val = $q->param ($name);
	    if (defined ($new_val)) {
		my $func = $changer{$name};
		my $old_val = $zone->$func () || '';
		
		if ($name ne 'delegated') {
		    $new_val = 'NULL' if ($new_val eq '');
		}				
		if ($new_val ne $old_val) {
		    if ($old_val) {
			push (@changelog, "Changed '$name' from '$old_val' to '$new_val'");
		    } else {
			push (@changelog, "Set '$name' to '$new_val'");
		    }
		    $zone->$func ($new_val) or die ("Failed to set zone attribute: '$name' - error was '$zone->{error}'\n");
		}
	    }
	}
	
	if (@changelog) {
	    my $i = localtime () . " modifyzone.cgi[$$]";
	    warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) made the following changes to zone -- $identify_str :\n$i ",
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

sub get_zone
{
    my $hostdb = shift;
    my $search_for = shift;
    
    return $hostdb->findzonebyid ($search_for);
}

sub zone_form
{
    my $q = shift;
    my $zone = shift;
    my $zone_defaults_ref = shift;
    my $remote_user = shift;
    
    my $zonename = $zone->zonename ();
    
    my ($id, $delegated, $default_ttl, $ttl, $mname, $rname, $refresh,
	$retry, $expiry, $minimum, $owner);
	
    my %yesno_labels = ('Y' => 'Yes',
			'N' => 'No');
    
    # HTML 
    my $state_field = $q->state_field ();
    my $commit = $q->submit (-name=>'action', -value=>'Commit',-class=>'button');
    
    my $me = $q->state_url ();
    
    $id = $zone->id ();
    $delegated = $q->popup_menu (-name => 'delegated',
				 -values => ['Y', 'N'],
				 -labels => \%yesno_labels,
				 -default => $zone->delegated ());
    $default_ttl = $q->textfield (-name => 'default_ttl',
				  -default => $zone->default_ttl () || '',
				  -size => 10);
    $ttl = $q->textfield (-name => 'ttl',
			  -default => $zone->ttl () || '',
			  -size => 10);
    $mname = $q->textfield (-name => 'mname',
			    -default => $zone->mname () || '',
			    -size => 10);
    $rname = $q->textfield (-name => 'rname',
			    -default => $zone->rname () || '',
			    -size => 10);
    $refresh = $q->textfield (-name => 'refresh',
			      -default => $zone->refresh () || '',
			      -size => 10);
    $retry = $q->textfield (-name => 'retry',
			    -default => $zone->retry () || '',
			    -size => 10);
    $expiry = $q->textfield (-name => 'expiry',
			     -default => $zone->expiry () || '',
			     -size => 10);
    $minimum = $q->textfield (-name => 'minimum',
			      -default => $zone->minimum () || '',
			      -size => 10);
    $owner = $q->textfield ('owner', $zone->owner () || $remote_user);
    
    my $required = "<font COLOR='red'>*</font>";

    my $delete = "[delete]";
    $delete = "[<a HREF='$links{deletezone};id=$id'>delete</a>]" if (defined ($id) and $links{deletezone});
    
    my $id_if_any = '';
    $id_if_any = "<input TYPE='hidden' NAME='id' VALUE='$id'>" if (defined ($id) and ($id ne ''));
    
    my $zone_link;
    
    if (defined ($id)) {
	$zone_link = "<a HREF='$links{whois};whoisdatatype=zone;whoisdata=$zonename'>$zonename</a>" if ($links{whois});
    } else {
	$zone_link = "not in database";
    }
    
    $q->print (<<EOH);
		$state_field
                $id_if_any
		<tr>
			<td>Zone</td>
			<td>$zone_link</td>
			$empty_td
		</tr>	
		<tr>
			<td ALIGN='center' COLSPAN='2'>---</td>
			<td>Defaults</td>
		</tr>
		<tr>
			<td>Delegated</td>
			<td>$delegated</td>
			$empty_td
		</tr>	
		<tr>
			<td>Default TTL</td>
			<td>$default_ttl</td>
			<td>($zone_defaults_ref->{default_ttl})</td>
		</tr>	
		<tr>
			<td>Owner</td>
			<td>$owner</td>
			$empty_td
		</tr>	
		<tr>
			<td>SOA TTL</td>
			<td>$ttl</td>
			<td>($zone_defaults_ref->{soa_ttl})</td>
		</tr>	
		<tr>
			<td>SOA mname</td>
			<td>$mname</td>
			<td>($zone_defaults_ref->{soa_mname})</td>
		</tr>	
		<tr>
			<td>SOA rname</td>
			<td>$rname</td>
			<td>($zone_defaults_ref->{soa_rname})</td>
		</tr>	
		<tr>
			<td>SOA refresh</td>
			<td>$refresh</td>
			<td>($zone_defaults_ref->{soa_refresh})</td>
		</tr>	
		<tr>
			<td>SOA retry</td>
			<td>$retry</td>
			<td>($zone_defaults_ref->{soa_retry})</td>
		</tr>	
		<tr>
			<td>SOA expiry</td>
			<td>$expiry</td>
			<td>($zone_defaults_ref->{soa_expiry})</td>
		</tr>	
		<tr>
			<td>SOA minimum</td>
			<td>$minimum</td>
			<td>($zone_defaults_ref->{soa_minimum})</td>
		</tr>	
		
		<tr>
			<td ALIGN='left'>$commit</td>
			<td COLSPAN='2' ALIGN='right'>$delete</td>
		</tr>
		$table_blank_line

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
		<td COLSPAN='$table_cols'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
    my $i = localtime () . " modifyzone.cgi[$$]";
    warn ("$i: $error\n");
}

