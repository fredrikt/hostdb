# $Id$

use strict;
use HOSTDB;

package HOSTDB::Object;
@HOSTDB::Object::ISA = qw(HOSTDB);

=head1 NAME

HOSTDB::Object - Object super class. Inherits from HOSTDB but provides an empty init ().


=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw, debug = $debug);

=head1 DESCRIPTION

Nothing here for now.


=head1 EXPORT

None.

=head1 METHODS

None.


=cut



sub init
{


}

=head1 HOSTDB OBJECTS INTERNAL EXPORTS


These functions should NEVER be called by anything except HOSTDB Object modules.


=head2 _set_or_get_attribute

    _set_or_get_attribute is a generic set/get routine. can be handled a
    validator reference.

    sub my_validate
    {
	my $self = shift;
	my $key = shift;
	my $in = shift;
	if ($in eq 'foo') {
	    return ("Can't set '$key' to '$in'");
	}
	return 0;
    }

    sub attribute
    {
	my $self = shift;
	# my_validate will make sure we never set attribute to 'foo'
	$self->_set_or_get_attribute ('attribute', \&my_validate, @_);
    }


=cut
sub _set_or_get_attribute
{
    my $self = shift;
    my $key = shift;
    my $validator_ref = shift;

    if (! $key) {
	# find out caller functions name ($subname) and use that as attribute name if none was given
	my ($pack, $file, $line, $subname, $hasargs, $wantarray) = caller (1);
	if ($subname =~ /.*:([^:]+?)$/) {
	    # $subname is something like HOSTDB::Object::HostAlias::aliasname, get
	    # what is after the last colon.
	    $key = $1;
	} else {
	    die ("$0: _set_or_get_attribute () can't figure out attribute name");
	}
    }

    if (@_) {
	# set
	my $newvalue = shift;
	my $saved_value = $newvalue;

	if ($validator_ref) {
	    my $res = &$validator_ref ($self, $key, $newvalue);
	    if ($res) {
		$self->_set_error ("Can't set attribute '$key' to '$saved_value' : $res");
		return 0;
	    }
	}

	if ($newvalue ne $saved_value) {
	    # just debug outputting
	    my $a = $newvalue || 'undef';
	    my $b = $saved_value || 'undef';
	    $self->_debug_print ("Setting attribute '$key' to $a (was: $b)");
	} else {
	    my $a = $newvalue || 'undef';
	    $self->_debug_print ("Setting attribute '$key' to $a");
	}

	$self->{$key} = $newvalue;
	
	return 1;
    }

    # get
    return ($self->{$key});
}


=head1 VALIDATOR FUNCTIONS

    A set of generic validator functions


=head2 _validate_read_only

    Always fail


=cut
sub _validate_read_only
{
    my $self = shift;
    my $key = shift;
    return ("'$key' is read only");
}


=head2 _validate_clean_hostname_or_null

    Check that input is a valid hostname, or 'NULL'.


=cut
sub _validate_clean_hostname_or_null
{
    my $self = shift;
    my $key = shift;
    my $newvalue = $_[0];

    if (uc ($newvalue) eq 'NULL') {
	$_[0] = undef;
    } elsif (! $self->clean_hostname ($_[0])) {
	return ("Invalid hostname");
    }

    return 0;
}


=head2 _validate_clean_hostname

    Check that input is a valid hostname.


=cut
sub _validate_clean_hostname
{
    my $self = shift;
    my $key = shift;
    my $newvalue = $_[0];

    if (! $self->clean_hostname ($_[0])) {
	return ("Invalid hostname");
    }

    return 0;
}

=head2 _validate_ttl

    Check that input is a valid TTL. That means it is either a number of seconds, or a string
    of the format that BIND9 understands (e.g. 1w2d3h4m5s).


=cut
sub _validate_ttl
{
    my $self = shift;
    my $key = shift;
    my $newvalue = lc ($_[0]);

    if ($newvalue eq 'null') {
	$_[0] = undef;
    } elsif (! $self->is_valid_nameserver_time ($newvalue)) {
	return ("Invalid TTL time value");
    }

    $_[0] = $self->_nameserver_time_to_seconds ($newvalue);

    return 0;
}


=head2 _validate_clean_domainname_or_null

    Check that input is a valid domainname, or 'NULL'.


=cut
sub _validate_clean_domainname_or_null
{
    my $self = shift;
    my $key = shift;
    my $newvalue = $_[0];

    if (uc ($newvalue) eq 'NULL') {
	$_[0] = undef;
    } elsif (! $self->clean_domainname ($_[0])) {
	return ("Invalid domainname");
    }

    return 0;
}

=head2 _validate_clean_domainname

    Check that input is a valid domainname.


=cut
sub _validate_clean_domainname
{
    my $self = shift;
    my $key = shift;
    my $newvalue = $_[0];

    if (! $self->clean_domainname ($_[0])) {
	return ("Invalid domainname");
    }

    return 0;
}

=head2 _validate_enabled_or_disabled

    Check that input is either 'ENABLED' or 'DISABLED'.


=cut
sub _validate_enabled_or_disabled
{
    my $self = shift;
    my $key = shift;
    my $newvalue = uc ($_[0]);

    if ($newvalue ne 'ENABLED' and $newvalue ne 'DISABLED') {
	return ("Value is neither ENABLED nor DISABLED");
    }

    # write back to $_[0] if our uc () changed the value
    $_[0] = $newvalue if ($newvalue ne $_[0]);

    return 0;
}

=head2 _validate_string_comment

    Check that a comment is not exceedingly long.


=cut
sub _validate_string_comment
{
    my $self = shift;
    my $key = shift;
    my $newvalue = shift;

    if (length ($newvalue) > 255) {
	return ("Too long (max 255 chars)");
    }

    return 0;
}


=head2 _validate_datetime

    Check that input is a valid "datetime". Uses HOSTDB::_format_datetime ().


=cut
sub _validate_datetime
{
    my $self = shift;
    my $key = shift;
    my $newvalue = $_[0];

    my $fmtvalue = $self->_format_datetime ($newvalue);
    if (defined ($fmtvalue)) {
	if ($fmtvalue eq 'NULL') {
	    $_[0] = undef;
	} else {
	    $_[0] = $fmtvalue;
	}
    } else {
	return ("Invalid datetime");
    }

    return 0;
}


1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
