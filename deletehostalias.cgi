#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to delete host alias objects
#

use strict;
use HOSTDB;

my $table_cols = 3;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Delete Host alias', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, \$me);
## end generic initialization

my ($alias, $hostid, $host);
my $id = $q->param('id');
if (defined ($id) and $id ne '') {
    $alias = $hostdb->findhostaliasbyid ($id);
    if ($alias) {
	# An hostalias was found. Find the corresponding host too. Overrides any host
	# we located using the hostid HTML form parameter above.
	$hostid = $alias->hostid ();
	$host = get_host_using_id ($hostdb, $hostid, $q);
	$id = $alias->id (); # read back wins over html parameters
    }
}

if (! defined ($alias)) {
    $q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host alias found and none could be created (hostdb error: $hostdb->{error})</strong></font></ul>\n\n");
    $q->end ();
    die ("$0: Could not get/create host alias (hostdb error: $hostdb->{error})");
}

## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@l, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});
HOSTDB::StdCGI::print_cgi_header ($q, 'Delete host alias (CNAME)', $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

$q->print (<<EOH);
        <form ACTION='$me' METHOD='post'>
	<input TYPE='hidden' NAME='id' VALUE='$id'>
        <table BORDER='0' CELLPADDING='0' CELLSPACING='3' WIDTH='100%'>
                <!-- table width disposition tds -->
                <tr>
		    <td WIDTH='33%'>&nbsp;</td>
		    <td WIDTH='33%'>&nbsp;</td>
		    <td WIDTH='33%'>&nbsp;</td>
		</td>

EOH

my $action = $q->param('action');
$action = 'Search' unless $action;

if ($action eq 'Delete') {
    my $ip = $host->ip ();
    my $hostname = $host->hostname () || 'undef';
    my $hostid = $host->id ();

    # get subnet
    my $subnet = $hostdb->findsubnetbyip ($host->ip ());

    # get zone
    my $zone = $hostdb->findzonebyhostname ($host->hostname ());

    # check that user is allowed to edit both zone and subnet
    my $authorized = 1;

    if (! $is_admin) {
	if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
	    error_line ($q, "You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
	    $authorized = 0;
	}
	
	# if there is no zone, only base desicion on subnet rights
	if ($authorized and defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
	    error_line ($q, "You do not have sufficient access to zone '" . $zone->zone () . "'");
	    $authorized = 0;
	}
    }
    
    if ($authorized) {
	my $identify_str = "id:'" . ($alias->id () || 'no id') . "' aliasname:'" . ($alias->aliasname () || 'no aliasname') . " (alias to host id $hostid ($hostname))'";

	if (delete_hostalias ($hostdb, $alias, $q)) {
	    my $i = localtime () . " deletehostalias.cgi[$$]";
	    warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) deleted the following host alias -- $identify_str\n");
	    
	    my @links;
	    
	    $q->print (<<EOH);
					<tr>
						<td COLSPAN='2'><strong><font COLOR='red'>Host alias (CNAME) deleted</font></strong></td>
					</tr>
EOH
	    if (defined ($subnet) and $links{showsubnet}) {
		my $s = $subnet->subnet ();
		my $link = "<a HREF='$links{showsubnet};subnet=$s'>Show subnet</a>";
		push (@links, "<tr><td COLSPAN='2'>&nbsp;&nbsp;[$link $s]<br></td></tr>\n");
	    }

	    if ($links{modifyhost}) {
		$ip = "Host <a HREF='$links{whois};type=id;data=$hostid'>$hostname</a>";
		push (@links, "<tr><td COLSPAN='2'>&nbsp;&nbsp;[$ip]</td></tr>\n");
	    }
	    
	    if (@links) {
		$q->print (<<EOH);
		
					$table_blank_line

					<tr>
						<td COLSPAN='2'><strong>Courtesy links :</td>
					</tr>
					@links
EOH
	    }
	} else {
	    error_line ($q, "Delete failed: $host->{error}");
	}
    }
} else {
    print_alias ($hostdb, $q, $alias);
    delete_form ($q, $host);
}

if ($@) {
    error_line($q, "$@\n");
}

$q->print (<<EOH);
	</table>
EOH

$q->end();


sub delete_hostalias
{
    my $hostdb = shift;
    my $alias = shift;
    my $q = shift;

    if ($q->param ('_hostdb.deletehostalias') ne 'yes') {
	error_line ($q, "Delete without verification not supported, don't try to trick me.");
	return undef;
    }

    eval {
	die ('No hostalias object') unless ($alias);

	$alias->delete ('YES') or die ($alias->{error});
    };
    if ($@) {
	chomp ($@);
	error_line ($q, "Failed to delete hostalias: $@");
	return 0;
    }

    return 1;
}

sub delete_form
{
    my $q = shift;
    my $alias = shift;

    # HTML
    my $state_field = $q->state_field ();
    my $delete = $q->submit (-name=>'action', -value=>'Delete',-class=>'button');
    my $me = $q->state_url ();
    my $id = $alias->id ();

    $q->print (<<EOH);
		<tr>
			<td COLSPAN='2' ALIGN='right'>
				<font COLOR='red'>
					<strong>
						Are you SURE you want to delete this host alias (CNAME)?
					</strong>
				</font>
			</td>
			<td ALIGN='left'>
			   <form ACTION='$me' METHOD='post'>
				$state_field
		                <input TYPE='hidden' NAME='id' VALUE='$id'>
				<input TYPE='hidden' NAME='_hostdb.deletehostalias' VALUE='yes'>
				$delete
			   </form>
			</td>
		</tr>

		$table_blank_line
EOH

    return 1;
}

sub print_alias
{
    my $hostdb = shift;
    my $q = shift;
    my $alias = shift;

    error_line ($q, 'No alias found'), return undef unless ($alias);

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
	$hostlink = "<a HREF='$links{whois};type=ID;data=$hostid'>$hostname</a>" if (defined ($links{whois}));
    }

    $q->print (<<EOH);
                        <tr>
                           <th ALIGN='left'>Aliasname</th>
                           <td>$aliasname</td>
			   $empty_td
                        </tr>
			<tr>
			   <td>ID</td>
			   <td>$id</td>
			   $empty_td
			</td>
                        <tr>
                           <td>DNS TTL</td>
                           <td>$ttl</td>
                           $empty_td
                        </tr>
                        <tr>
                           <td>DNS status</td>
                           <td>$dnsstatus</td>
                           $empty_td
                        </tr>
			

			$table_blank_line
                        <tr>
                           <td>Comment</td>
                           <td>$comment</td>
                           $empty_td
                        </tr>

			$table_blank_line
			<tr>
			   <th ALIGN='left'>Hostname</th>
			   <td>$hostlink</td>
			   $empty_td
			</tr>
EOH
    return 1;
}

sub get_host_using_id
{
    my $hostdb = shift;
    my $id = shift;
    my $q = shift;

    $host = $hostdb->findhostbyid ($id);
    if (! $host) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host with host id '$id' found.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: No host with id '$id' found.");
    }

    return $host;
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
    my $i = localtime () . " deletehostalias.cgi[$$]";
    warn ("$i: $error\n");
}
