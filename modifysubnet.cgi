#!/usr/local/bin/perl -w
#
# $Id$
#
# cgi-script to modify/create subnet objects
#

use strict;
use HOSTDB;

my $table_cols = 4;

## Generic Stockholm university HOSTDB CGI initialization
my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables ($table_cols);
my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);
my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('Modify Subnet', $debug);
my (%links, $is_admin, $is_helpdesk, $me);
HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, $me);
## end generic initialization

my %colors = load_colors ($hostdbini);

if (! $hostdb->auth->is_admin ($remote_user)) {
    $q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not authorized to change subnets.</strong></font></ul>\n\n");
    $q->end ();
    die ("$0: User '$remote_user' denied\n");
}

my $subnet;

my $id = $q->param('id');
if (defined ($id) and $id ne '') {
    $subnet = get_subnet ($hostdb, $id);
}
# else {
#	$subnet = $hostdb->create_subnet ();
#	if (defined ($subnet)) {
#		# set some defaults
#		$subnet->profilelist ('default');
#	}
#}

if (! defined ($subnet)) {
    $q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>No subnet found (hostdb error: $hostdb->{error})</strong></font></ul>\n\n");
    $q->end ();
    die ("$0: Could not get/create subnet (hostdb error: $hostdb->{error})");
}

## Generic Stockholm university HOSTDB CGI header
my (@l);
push (@l, "[<a HREF='$links{home}'>home</a>]") if ($links{home});
push (@l, "[<a HREF='$links{whois}'>whois</a>]") if ($links{whois});
HOSTDB::StdCGI::print_cgi_header ($q, 'Modify Subnet', $is_admin, $is_helpdesk, \%links, \@l);
## end generic header

$q->print ("\t\t<form ACTION='$me' METHOD='post'>\n" .
	   "\t\t\t<table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>\n");

my $action = lc ($q->param('action'));
$action = 'search' unless $action;

if ($action eq 'commit') {
    if (modify_subnet ($hostdb, $subnet, $q, \%colors, $remote_user)) {
	my $i = localtime () . " modifysubnet.cgi[$$]";
	eval
	{
	    $subnet->commit ();
	};
	$id = $subnet->id () if (! defined ($id) and defined ($subnet));
	if ($@) {
	    error_line ($q, "Could not commit changes: $@");
	    warn ("$i Changes to subnet with id '$id' could not be committed ($@)\n");
	} else {
	    warn ("$i Changes to subnet with id '$id' committed successfully\n");
	}
    }
    $id = $subnet->id () if (! defined ($id) and defined ($subnet));
    $subnet = get_subnet ($hostdb, $id); # read-back
} elsif ($action eq 'search') {
    # call modify_subnet but don't commit () afterwards to get
    # stuff supplied to us as CGI parameters
    # set on the subnet before we call subnet_form () below.
    modify_subnet ($hostdb, $subnet, $q, $remote_user);
} else {
    error_line ($q, 'Unknown action');
    $subnet = undef;
}


if (defined ($subnet)) {
    subnet_form ($q, $subnet, \%colors, $remote_user);
}

END:
$q->print (<<EOH);
	</table></form>
EOH

$q->end();


sub modify_subnet
{
    my $hostdb = shift;
    my $subnet = shift;
    my $q = shift;
    my $colors_ref = shift;
    my $remote_user = shift;

    my (@changelog, @warning);

    eval {
	die ("No subnet object") unless ($subnet);

	$subnet->_set_error ('');

	my $identify_str = "id:'" . ($subnet->id () || 'no id') . "' subnet:'" . ($subnet->subnet () || 'no subnet') . "'";

	# this is a hash and not an array to provide a better framework
	my %changer = ('description'		=> 'description',
		       'short_description'	=> 'short_description',
		       'htmlcolor'		=> 'htmlcolor',
		       'owner'			=> 'owner',
		       'profilelist'		=> 'profilelist'
		       );

	foreach my $name (keys %changer) {
	    my $new_val = $q->param ($name);
	    if (defined ($new_val)) {
		my $func = $changer{$name};
		my $old_val = $subnet->$func () || '';

		if ($name eq 'htmlcolor') {
		    if (! defined ($colors_ref->{$new_val})) {
			die ("Color '$new_val' not in colorlist");
		    }
		}

		if ($new_val ne $old_val) {
		    if ($old_val) {
			push (@changelog, "Changed '$name' from '$old_val' to '$new_val'");
		    } else {
			push (@changelog, "Set '$name' to '$new_val'");
		    }
		    $subnet->$func ($new_val) or die ("Failed to set subnet attribute: '$name' - error was '$subnet->{error}'\n");
		}
	    }
	}

	if (@changelog) {
	    my $i = localtime () . " modifysubnet.cgi[$$]";
	    warn ("$i User '$remote_user' (from $ENV{REMOTE_ADDR}) made the following changes to subnet -- $identify_str :\n$i ",
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

sub get_subnet
{
    my $hostdb = shift;
    my $search_for = shift;

    return $hostdb->findsubnetbyid ($search_for);
}


sub subnet_form
{
    my $q = shift;
    my $subnet = shift;
    my $colors_ref = shift;
    my $remote_user = shift;

    my $subnet_name = $subnet->subnet ();

    my ($id, $description, $short_description, $htmlcolor, $owner,
	$profilelist);


    # HTML
    my $state_field = $q->state_field ();
    my $commit = $q->submit (-name=>'action', -value=>'Commit', -class=>'button');

    my $me = $q->state_url ();
    $id = $subnet->id ();
    $description = $q->textfield (-name => 'description',
				  -default => $subnet->description () || '',
				  -size => 85,
				  -maxlength => 255);
    $short_description = $q->textfield (-name => 'short_description',
					-default => $subnet->short_description () || '',
					-size => 85,
					-maxlength => 255);
    $htmlcolor = $q->popup_menu (-name => 'htmlcolor',
				 -values => [sort keys %{$colors_ref}],
				 -default => $subnet->htmlcolor ());
    $owner = $q->textfield ('owner', $subnet->owner () || $remote_user);
    $profilelist = $q->textfield (-name => 'profilelist',
				  -default => $subnet->profilelist () || '',
				  -size => 85,
				  -maxlength => 255);

    my $empty_td = '<td>&nbsp;</td>';

    my $required = "<font COLOR='red'>*</font>";

    my $delete = "[delete]";
    $delete = "[<a HREF='$links{deletesubnet};id=$id'>delete</a>]" if (defined ($id) and $links{deletesubnet});

    my $id_if_any = '';
    $id_if_any = "<input TYPE='hidden' NAME='id' VALUE='$id'>" if (defined ($id) and ($id ne ''));

    my $subnet_link = $subnet_name;

    if (defined ($id)) {
	$subnet_link = "<a HREF='$links{showsubnet};subnet=$subnet_name'>$subnet_name</a>" if ($links{showsubnet});
    } else {
	$subnet_link = "not in database";
    }

    $q->print (<<EOH);
	        <!-- table width disposition tds -->
		<tr>
			<td WIDTH='25%'>&nbsp;</td>
			<td COLSPAN='3' WIDTH='75%'>&nbsp;</td>
		</tr>

		$state_field
                $id_if_any
		<tr>
			<td>Subnet</td>
			<td>$subnet_link</td>
			$empty_td
			$empty_td
		</tr>

		$table_blank_line

		<tr>
			<td>Short description</td>
			<td COLSPAN='3'>$short_description</td>
		</tr>
		<tr>
			<td>Description</td>
			<td COLSPAN='3'>$description</td>
		</tr>
		<tr>
			<td>Color</td>
			<td>$htmlcolor</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td>Profiles</td>
			<td COLSPAN='3'>$profilelist</td>
		</tr>
		<tr>
			<td>Owner $required</td>
			<td>$owner</td>
			$empty_td
			$empty_td
		</tr>
		<tr>
			<td COLSPAN='2' ALIGN='left'>$commit</td>
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
		<td COLSPAN='4'>
		   <font COLOR='red'>
			<strong>$error</strong>
		   </font>
		</td>
	   </tr>
EOH
    my $i = localtime () . " modifysubnet.cgi[$$]";
    warn ("$i: $error\n");
}

sub load_colors
{
    my $hostdbini = shift;
    my %res;

    my @colors = $hostdbini->Parameters ('subnet_colors');

    my $t;
    foreach $t (@colors) {
	$res{$t} = $hostdbini->val ('subnet_colors', $t);
    }

    # make RED the default so that a non-specified color is obvious
    $res{default} = "#ff0000" if (! defined ($res{default}));

    return %res;
}
