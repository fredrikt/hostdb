#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to modify/create host alias objects
#

use strict;
use HOSTDB;
use SUCGI2;

my $table_blank_line = "<tr><td COLSPAN='4'>&nbsp;</td></tr>\n";
my $table_hr_line = "<tr><td COLSPAN='4'><hr></td></tr>\n";

my $debug = 0;
if (defined($ARGV[0]) and $ARGV[0] eq '-d') {
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
$q->begin (title => 'Modify/Add Host alias');

my @readwrite_attributes = ('aliasname', 'comment', 'dnsstatus', 'ttl');

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
# First try to find a host using the HTML form parameter 'hostid', if supplied.
my $hostid = $q->param('hostid');
if (defined ($hostid) and int ($hostid) > 0) {
    $host = get_host_using_id ($hostdb, $hostid, $q);
}

my $alias;
my $id = $q->param('id');
if (defined ($id) and $id ne '') {
    $alias = $hostdb->findhostaliasbyid ($id);
    if ($alias) {
	# An hostalias was found. Find the corresponding host too. Overrides any host
	# we located using the hostid HTML form parameter above.
	$hostid = $alias->hostid ();
	$host = get_host_using_id ($hostdb, $hostid, $q);
    }
} else {
    if (! $host) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No hostid supplied - can't create new hostalias.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: No hostid supplied - can't create new hostalias.");
    }
    $alias = $host->create_hostalias ();
    # set some defaults
    $alias->dnsstatus ('ENABLED');
}


if (! defined ($alias)) {
    $q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No host alias found and none could be created (hostdb error: $hostdb->{error})</strong></font></ul>\n\n");
    $q->end ();
    die ("$0: Could not get/create host alias (hostdb error: $hostdb->{error})");
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
				<h3>HOSTDB: Add/Modify host alias (CNAME)</h3>
			</td>
			<td ALIGN='right'>$l</td>
		</tr>
		$table_blank_line
EOH

my $action = lc ($q->param('action'));
$action = 'search' unless $action;

if ($action eq 'commit') {
    if (modify_alias ($hostdb, $alias, $host, $q, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes, $action)) {
	my $i = localtime () . " hostalias.cgi[$$]";
	eval
	{
	    $alias->commit ();
	};
	if (! defined ($id) and defined ($alias)) {
	    $id = $alias->id () || '';
	}
	if ($@) {
	    error_line ($q, "Could not commit changes: $@");
	    warn ("$i Changes to hostalias with id '$id' could not be committed ($@)\n");
	} else {
	    warn ("$i Changes to hostalias with id '$id' committed successfully\n");
	}
    }
    $id = $alias->id () if (! defined ($id) and defined ($alias));
    $alias = $hostdb->findhostaliasbyid ($id) if (defined ($id));	# read-back
} elsif	($action eq 'search') {
    # call modify_alias but don't commit () afterwards to get
    # ip and other stuff supplied to us as CGI parameters
    # set on the host before we call host_form () below.
    modify_alias ($hostdb, $alias, $host, $q, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes, $action);
} else {
    error_line ($q, 'Unknown action');
    $alias = undef;
}


if (defined ($alias)) {
    alias_form ($q, $alias, $host, $remote_user, $is_admin, $is_helpdesk, \@readwrite_attributes);
}

END:
$q->print (<<EOH);
	</table></form>
EOH

$q->end();



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

sub modify_alias
{
    my $hostdb = shift;
    my $alias = shift;
    my $host = shift;
    my $q = shift;
    my $remote_user = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $readwrite_attributes = shift;
    my $action = shift;

    my (@changelog, @warning);

    eval {
	die ("No hostalias object") unless ($alias);

	$alias->_set_error ('');

	# get subnet of the aliases host
	my $subnet = $hostdb->findsubnetbyip ($host->ip () || $q->param ('ip'));

	# get zone of the aliases host
	my $zone = $hostdb->findzonebyhostname ($host->hostname ());

	# check that user is allowed to edit both the hosts zone and subnet

	if (! $is_admin and ! $is_helpdesk) {
	    if (! defined ($subnet) or ! $hostdb->auth->is_allowed_write ($subnet, $remote_user)) {
		die ("You do not have sufficient access to subnet '" . $subnet->subnet () . "'");
	    }

	    # if there is no zone, only base decision on subnet rights
	    if (defined ($zone) and ! $hostdb->auth->is_allowed_write ($zone, $remote_user)) {
		die ("You do not have sufficient access to zone '" . $zone->zone () . "'");
	    }
	}

	my $identify_str = "id:'" . ($alias->id () || 'no id') . "' aliasname:'" . ($alias->aliasname () || 'no aliasname') . "'";

	# this is a hash and not an array to provide a better framework
	my %changer = ('dnsstatus' =>	'dnsstatus',
		       'aliasname' =>	'aliasname',
		       'ttl' =>		'ttl',
		       'comment' =>	'comment'
		       );

	# check which fields we should allow changes to
	foreach my $t (keys %changer) {
	    delete($changer{$t}) if (! check_allowed_readwrite ($t, $readwrite_attributes, $remote_user, $is_admin, $is_helpdesk));
	}

	foreach my $name (keys %changer) {
	    my $new_val = $q->param ($name);
	    if (defined ($new_val)) {
		my $func = $changer{$name};
		next unless ($func);
		my $old_val = $alias->$func () || '';

		if ($new_val ne $old_val) {

		    # do special stuff for some attributes

		    if ($name eq 'aliasname') {
			# changing aliasname, check that user has enough permissions for the _new_ zone too
			my $aliasname = $q->param ('aliasname');

			die "Invalid hostname '$aliasname'\n" if (! $hostdb->clean_hostname ($aliasname));

			my $t_host = $hostdb->findhost ('guess', $aliasname);
			if ($t_host) {
			    my $t_id = $t_host->id ();
			    my $t_ip = $t_host->ip ();
			    die "Another host object (ID $t_id, IP $t_ip) currently have the hostname/alias '$aliasname'\n";
			}

			my $new_zone = $hostdb->findzonebyhostname ($aliasname);
			my $new_zonename;
			if (defined ($new_zone)) {
			    $new_zonename = $new_zone->zonename () || 'NULL';
			} else {
			    $new_zonename = 'NULL';
			}

			if (! $is_admin and ! $is_helpdesk and
			    ! $hostdb->auth->is_allowed_write ($new_zone, $remote_user)) {
			    die ("You do not have sufficient access to the new aliasnames zone '$new_zonename'");
			}

			# there is no manual dnszone control on aliases (alias can't be glue),
			# so we always adjust dnszone when aliasname is changed
			$alias->dnszone ($new_zonename);
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

		    $alias->$func ($new_val) or die ("Failed to set host attribute: '$name' - error was '$host->{error}'\n");
		    my $readback = $alias->$func ();
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

	if ($action eq 'commit') {
	    if (@changelog) {
		my $i = localtime () . " hostalias.cgi[$$]";
		warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) made the following changes to host -- $identify_str :\n$i ",
		      join ("\n$i ", @changelog), "\n");
	    }
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
    
    if (check_allowed_readwrite ($attribute, $readwrite_attributes, $remote_user, $is_admin, $is_helpdesk)) {
	if (defined (%paramhash)) {
	    return ($q->$func (-name => $attribute, -default => $curr, %paramhash));
	} else {
	    return ($q->$func (-name => $attribute, -default => $curr));
	}
    } else {
	my $val = $curr;
	$val = 'default' if ($attribute eq 'ttl' and ! $val);
	if (defined ($paramhash{'-labels'})) {
	    # look for label matching the value we are to print
	    # (for example, "Both 'A' and 'PTR'" instead of A_AND_PTR)
	    my %l = %{$paramhash{'-labels'}};
	    if (defined (%l)) {
		$val = $l{$curr} || $curr;
	    }
	}

	return ("$val (read only)");
    }
}

sub alias_form
{
    my $q = shift;
    my $alias = shift;
    my $host = shift;
    my $remote_user = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $readwrite_attributes = shift;

    # HTML
    my $state_field = $q->state_field ();
    my $commit = $q->submit (-name=>'action', -value=>'Commit', -class=>'button');

    my %enabled_labels = ('ENABLED'	=> 'Enabled',
			  'DISABLED'	=> 'Disabled');

    my $me = $q->state_url ();

    my $id = $alias->id ();
    my $hostid = $alias->hostid ();
    my ($aliasname, $comment, $dnsstatus, $ttl);

    my @fielddata = ($readwrite_attributes, $remote_user, $is_admin, $is_helpdesk);
    $aliasname =	create_datafield ($alias, 'aliasname',	$q, 'textfield', @fielddata);
    $ttl =		create_datafield ($alias, 'ttl',	$q, 'textfield', @fielddata);
    $comment =		create_datafield ($alias, 'comment',	$q, 'textfield', @fielddata,
					  -size => 45, -maxlength => 255);
    $dnsstatus =	create_datafield ($alias, 'dnsstatus', 	$q, 'popup_menu', @fielddata,
					  -values => ['ENABLED', 'DISABLED'],
					  -labels => \%enabled_labels);

    $dnsstatus = $enabled_labels{$dnsstatus} || $dnsstatus;

    my $empty_td = '<td>&nbsp;</td>';

    my $required = "<font COLOR='red'>*</font>";

    my $delete = '[delete]';
    $delete = "[<a HREF='$links{deletehostalias};id=$id'>delete</a>]" if (defined ($id) and $links{deletehostalias});

    my $id_if_any = '';
    my $alias_id = 'not in database';
    if (defined ($id) and ($id ne '')) {
	$id_if_any = "<input TYPE='hidden' NAME='id' VALUE='$id'>" if (defined ($id) and ($id ne ''));
	$alias_id = "<a HREF='$links{whois};type=aliasid;data=$id'>$id</a>" if ($links{whois});
    }
    my $hidden_hostid = "<input TYPE='hidden' NAME='hostid' VALUE='$hostid'>";

    my $hostname_link = $host->hostname ();
    $hostname_link = "<a HREF='$links{whois};type=id;data=$hostid'>$hostname_link</a>" if ($links{whois});

    $q->print (<<EOH);
		$state_field
                $id_if_any
		$hidden_hostid
		<tr>
		        <th ALIGN='left'>Host</th>
			$empty_td
			$empty_td
			$empty_td
		</tr>
		<tr>
		        $empty_td
		        <td>Hostname</td>
			<td>$hostname_link</td>
			$empty_td
		</tr>

		<tr>
		        <th ALIGN='left'>Alias</th>
			$empty_td
			$empty_td
			$empty_td
		</tr>
			
		<tr>
			$empty_td
			<td>ID</td>
			<td>$alias_id</td>
			$empty_td
		</tr>
		<tr>
		        $empty_td
			<td>Aliasname $required</td>
			<td>$aliasname</td>
			$empty_td
		</tr>
		<tr>
		        $empty_td
			<td>Comment</td>
			<td COLSPAN='2'>$comment</td>
		</tr>

		$table_blank_line

		<tr>
			<td><strong>DNS</strong></td>
			<td>$dnsstatus</td>
			<td>TTL&nbsp;&nbsp;$ttl</td>
			$empty_td
		</tr>

		$table_blank_line

		<tr>
			<td COLSPAN='2' ALIGN='left'>$commit</td>
			<td COLSPAN='2' ALIGN='right'>$delete</td>
		</tr>

		$table_blank_line

EOH

    return 1;
}

sub check_allowed_readwrite
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

    return 1 if (defined ($l[0]) and $l[0] eq 'ALL');

    if (! grep (/^$attribute$/, @l)) {
	return 0;
    }

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
    my $i = localtime () . " hostalias.cgi[$$]";
    warn ("$i: $error\n");
}
