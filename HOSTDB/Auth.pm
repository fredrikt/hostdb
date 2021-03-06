# $Id$

use HOSTDB;
use Config::IniFiles;
use strict;
use Net::LDAP;

package HOSTDB::Auth;
@HOSTDB::Auth::ISA = qw(HOSTDB);


=head1 NAME

HOSTDB::Auth - Access control functions.

=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (ini => $inifile);

  my $subnet = get subnet
  
  if ($hostdb->auth->is_allowed_write ($subnet, $ENV{REMOTE_USER})) {
  	# is ok
  } else {
  	die ("You do not have write permissions to subnet '" . $subnet->subnet () . "'\n");
  }


=head1 DESCRIPTION

Database access routines.


=head1 EXPORT

None.

=head1 METHODS

=cut


sub init
{
	my $self = shift;

	$self->_debug_print ("Creating AUTH object");

	return 1;
}

sub DESTROY
{
	my $self = shift;
	
	if (defined ($self->{ldap})) {
		$self->_debug_print ("Calling LDAP-unbind on $self->{ldap}");
		$self->{ldap}->unbind ();
	} else {
		$self->_debug_print ("No LDAP connection has been made, nothing to destroy");
	}
}


####################
# PUBLIC FUNCTIONS #
####################


=head1 PUBLIC FUNCTIONS


=head2 is_owner

	Takes a candidate and any object that has a owner () function as argument.
	Checks for the candidate in what is returned by the owner () function. If
	an LDAP server is supplied in the config file, then all elements of the
	lists are looked up in LDAP so that you can have groups in LDAP that are
	allowed to access HOSTDB objects.

	$is_allowed = $hostdb->auth->is_allowed_write ($host, $user);


=cut
sub is_owner
{
	my $self = shift;
	my $o = shift;
	my $candidate = shift;

	$self->_debug_print ("Checking if '$candidate' owns object '$o'");

	if (defined ($self->{authorization}) and $self->{authorization} eq 'DISABLED') {
		$self->_debug_print ("Authorization DISABLED (through configuration)");
		return 1;
	}

	my $owner = $o->owner ();

	$self->_debug_print ("Owner of object is '$owner'");

	$self->_debug_print ("Object has no owner, returning undef"), return undef unless ($owner);

	return 1 if $self->_is_in_list ($candidate, "object owner", split (',', $owner));
	return 1 if $self->_is_in_list ($candidate, "LDAP object owner", $self->_ldap_explode (split (',', $owner)));

	return 0;
}


=head2 is_admin

	Works like is_allowed_write but only checks if a user is in the admin-list.


=cut
sub is_admin
{
	my $self = shift;
	my $candidate = shift;

	$self->_debug_print ("Checking if '$candidate' is an HOSTDB admin");

	if (defined ($self->{authorization}) and $self->{authorization} eq 'DISABLED') {
		$self->_debug_print ("Authorization DISABLED (through configuration)");
		return 1;
	}

	return 1 if $self->_is_in_list ($candidate, "admin", $self->admin_list ());
	return 1 if $self->_is_in_list ($candidate, "LDAP admin", $self->_ldap_explode ($self->admin_list ()));

	return 0;
}


=head2 is_helpdesk

	Works like is_allowed_write but only checks if a user is in the helpdesk-list.


=cut
sub is_helpdesk
{
	my $self = shift;
	my $candidate = shift;

	$self->_debug_print ("Checking if '$candidate' is in HOSTDB helpdesk list");

	if (defined ($self->{authorization}) and $self->{authorization} eq 'DISABLED') {
		$self->_debug_print ("Authorization DISABLED (through configuration)");
		return 1;
	}

	return 1 if $self->_is_in_list ($candidate, "helpdesk", $self->helpdesk_list ());
	return 1 if $self->_is_in_list ($candidate, "LDAP helpdesk", $self->_ldap_explode ($self->helpdesk_list ()));

	return 0;
}


=head2 is_allowed_write

	Takes a candidate and any object that has a owner () function as argument.
	Checks for the candidate in what is returned by the owner () function and
	in the admins-variable from the config file. If an LDAP server is supplied
	in the config file, then all elements of the lists are looked up in LDAP
	so that you can have groups in LDAP that are allowed to edit HOSTDB objects.

	$is_allowed = $hostdb->auth->is_allowed_write ($host, $user);


=cut
sub is_allowed_write
{
	my $self = shift;
	my $o = shift;
	my $candidate = shift;

	$self->_debug_print ("Checking if '$candidate' may write to object '$o'");

	if (defined ($self->{authorization}) and $self->{authorization} eq 'DISABLED') {
		$self->_debug_print ("Authorization DISABLED (through configuration)");
		return 1;
	}

	if (! defined ($o)) {
		$self->_debug_print ("Object is undefined, denying write access for '$candidate'");
		return 0;
	}

	my $owner = $o->owner ();

	$self->_debug_print ("Owner of object is '$owner'");

	$self->_debug_print ("Object has no owner, returning undef"), return undef unless ($owner);

	return 1 if $self->is_admin ($candidate);
	return 1 if $self->is_owner ($o, $candidate);

	return 0;
}


=head2 ldap_server

	Gets or sets the LDAP auth server.
	
	XXX example


=cut
sub ldap_server
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		$self->{ldap_server} = $newvalue;

		my $ldap = Net::LDAP->new ($newvalue);
		if (! defined ($ldap)) {
			$self->_set_error ("Could not connect to LDAP server '$newvalue'");
			return undef;
		}
		$self->{ldap} = $ldap;

		return 1;
	}

	return ($self->{ldap_server});
}


=head2 admin_list

	A list of users with rights to do whatever they please.


=cut
sub admin_list
{
	my $self = shift;

	if (defined ($_[0])) {
		my @newvalue = @_;

		$self->{admins} = \@newvalue;
		return 1;
	}

	return (wantarray ? @{$self->{admins}} : join (",", @{$self->{admins}}));
}


=head2 helpdesk_list

	A list of users with rights to look at all objects, typically.


=cut
sub helpdesk_list
{
	my $self = shift;

	if (defined ($_[0])) {
		my @newvalue = @_;

		$self->{helpdesk} = \@newvalue;
		return 1;
	}

	return (wantarray ? @{$self->{helpdesk}} : join (",", @{$self->{helpdesk}}));
}



#####################
# PRIVATE FUNCTIONS #
#####################


=head1 PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.


=head2 _is_in_list

	Check if first argument matches exactly an item in the following list.

	@l = ('foo', 'ft', 'bar');
	if ($self->_is_in_list ('ft', "test-list", @list)) {
		print ("Yes, it was.\n");
	}

=cut
sub _is_in_list
{
	my $self = shift;
	my $q = shift;
	my $listname = shift;
	my @l = @_;

	return 0 unless defined ($q);
	return 0 unless (defined ($l[0]));

	if (grep (/^$q$/, @l)) {
		$self->_debug_print ("Token '$q' found in '$listname' list");
	
		return 1;
	}
	
	$self->_debug_print ("Token '$q' NOT found in '$listname' list (@l)");
	return 0;
}


=head2 _ldap_explode

	Takes an array of <mumble> and looks them up in LDAP. First as uid\'s and
	then as cn\'s. Returns all uid\'s the LDAP search yielded.

	$self->_ldap_search ('ft', 'it-sysadm');
	
	The above would return 'ft' (a uid) and all members of the group 'it-sysadm'.


=cut

sub _ldap_explode
{
	my $self = shift;
	my @in = @_;
	my @out;

	return undef unless (@in);
	
	$self->_debug_print ("LDAP explode @in");
	
	$self->_set_error ('');

	my $ldap = $self->{ldap};
	if (! defined ($ldap)) {
		my $ldap_server = $self->ldap_server ();	
	
		if (! defined ($ldap_server)) {
			$self->_debug_print ("No LDAP server defined, skipping LDAP search\n");
			return undef;
		}
	}
	
	foreach my $token (@in) {
		my ($res, @t, $e, %uid);

                if ($self->{_token_cache}->{$token}) {
		   push (@out, @{$self->{_token_cache}->{$token}});
                   next;
                }
		
		# do search for uids with name $token
		$res = $ldap->search (filter => "uid=$token");
		$res->code && warn $res->error, "\n";

		# loop through responses, collect uids (should be only one)
		foreach $e ($res->all_entries ()) {
			my $u = $e->get_value ('uid');
			$uid{lc($u)}++;
			#$self->_debug_print ("Found UID '" . lc($u) . "'");
		}

		# search for groups with name $token
		$res = $ldap->search (filter => "(&(cn=$token)(objectclass=groupofuniquenames))");
		$res->code && warn $res->error, "\n";

		# loop through responses, collect uids (should be only one)
		foreach $e ($res->all_entries ()) {
			foreach my $u ($e->get_value ('uniquemember')) {
				if ($u =~ /^uid=(.+?),/) {
					$uid{lc($1)}++;
					#$self->_debug_print ("Found group unique member '" . lc($u) . "'");
				} else {
					$self->_debug_print ("Strange LDAP result: $u\n");
				}
			}
		}

		@t = sort keys %uid;
		push (@out, @t);
                $self->{_token_cache}->{$token} = \@t;

		$self->_debug_print ("LDAP exploding of '$token' resulted in '@t'");
	}

	#warn ("LDAP explode @in RESULT @out\n");
	return @out;	                
}


1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
