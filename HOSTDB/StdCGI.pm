# $Id$
#
# Some Stockholm university CGI common functions. Probably
# of little use for someone else...
#

use HOSTDB;
use SUCGI2;
use Config::IniFiles;
use strict;

package HOSTDB::StdCGI;
@HOSTDB::Auth::ISA = qw(HOSTDB);


=head1 NAME

HOSTDB::StdCGI - Common code for Stockholm university HOSTDB CGI's

=head1 SYNOPSIS

    foo


=head1 DESCRIPTION

Just common code


=head1 EXPORT

None.

=head1 METHODS

=cut


sub init
{
	return 1;
}


####################
# PUBLIC FUNCTIONS #
####################


=head1 PUBLIC FUNCTIONS


=head2 parse_debug_arg

    Checks if -d is specified.

	my $debug = HOSTDB::StdCGI::parse_debug_arg (@ARGV);

=cut
sub parse_debug_arg
{
    my @A = @_;

    if (defined ($A[0]) and ($A[0] eq "-d")) {
	shift (@A);
	return 1;
    }

    return 0;
}


=head2 get_hostdb_and_sucgi

    Get hostdb, hostdbini and q handles as well as the remote user.


    my ($hostdbini, $hostdb, $q, $remote_user) = HOSTDB::StdCGI::get_hostdb_and_sucgi ('CGI title', $debug);


=cut
sub get_hostdb_and_sucgi
{
    my $title = shift;
    my $debug = shift;

    my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());
    my $sucgi_ini;
    my $sucgi_ini_fn = $hostdbini->val ('sucgi', 'cfgfile');
    if (defined ($sucgi_ini_fn) and -f $sucgi_ini_fn) {
	$sucgi_ini = Config::IniFiles->new (-file => $sucgi_ini_fn);
    } else {
	warn ("SUCGI config-file not defined or not found ('$sucgi_ini_fn')");
    }
    my $q = SUCGI2->new ($sucgi_ini, 'hostdb');
    $q->begin (title => $title);

    my $remote_user = $q->user();
    unless ($remote_user) {
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>You are not logged in.</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Invalid REMOTE_USER environment variable '$ENV{REMOTE_USER}'");
    }

    my $hostdb = eval {
	HOSTDB::DB->new (ini => $hostdbini, debug => $debug);
      };
    
    if ($@) {
	my $e = $@;
	$q->print ("&nbsp;<p><ul><font COLOR='red' SIZE='3'><strong>Could not create HOSTDB object: $e</strong></font></ul>\n\n");
	$q->end ();
	die ("$0: Could not create HOSTDB object: '$e'");
    }

    return ($hostdbini, $hostdb, $q, $remote_user);
}
    

=head2 get_table_variables

    Get some table HTML variables. Takes number of columns as argument.

	my ($table_blank_line, $table_hr_line, $empty_td) = HOSTDB::StdCGI::get_table_variables (4);

=cut
sub get_table_variables
{
    my $cols = shift;

    my $table_blank_line = "<tr><td COLSPAN='$cols'>&nbsp;</td></tr>\n";
    my $table_hr_line = "<tr><td COLSPAN='$cols'><hr></td></tr>\n";
    my $empty_td = "<td>&nbsp;</td>\n";

    return ($table_blank_line, $table_hr_line, $empty_td);
}

sub print_cgi_header
{
    my $q = shift;
    my $title = shift;
    my $is_admin = shift;
    my $is_helpdesk = shift;
    my $htmllinks_ref = shift;
    my $links_ref = shift;

    my %htmllinks = %{$htmllinks_ref};

    my (@admin_links);
    push (@admin_links, "[<a HREF='$htmllinks{netplan}'>netplan</a>]") if (($is_admin or $is_helpdesk) and $htmllinks{netplan});

    # make links
    my $l = '';
    if (@$links_ref or @admin_links) {
	$l = join(' ', @$links_ref, @admin_links);
    }

    $q->print (<<EOH);
        <table BORDER='0' CELLPADDING='0' CELLSPACING='0' WIDTH='100%'>
                <tr>
			<td COLSPAN='4'>&nbsp;</td>
		</tr>

                <tr>
                        <td ALIGN='center' WIDTH='75%'>
				<h3>HOSTDB: $title</h3>
			</td>
                        <td ALIGN='right' WIDTH='25%'>
				$l
			</td>
                </tr>
		
	</table>
EOH

    return 1;
}


=head2 get_cgi_common_variables

    Get some commonly used variables.

	HOSTDB::StdCGI::get_cgi_common_variables ($q, $hostdb, $remote_user, \%links, \$is_admin, \$is_helpdesk, \$me);


=cut
sub get_cgi_common_variables
{
    my $q = shift;
    my $hostdb = shift;
    my $remote_user = shift;
    my $links_ref = shift;
    my $is_admin_ref = shift;
    my $is_helpdesk_ref = shift;
    my $me_ref = shift;

    if (defined ($links_ref)) {
	%{$links_ref} = $hostdb->html_links ($q);
    }
    if (defined ($is_admin_ref)) {
	$$is_admin_ref = $hostdb->auth->is_admin ($remote_user);
    }
    if (defined ($is_helpdesk_ref)) {
	$$is_helpdesk_ref = $hostdb->auth->is_helpdesk ($remote_user);
    }
    if (defined ($me_ref)) {
	$$me_ref = $q->state_url ();
    }

    return 1;
}

#####################
# PRIVATE FUNCTIONS #
#####################


=head1 PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.


1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
