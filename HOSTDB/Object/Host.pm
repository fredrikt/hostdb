# $Id$

use strict;
use HOSTDB::Object;

package HOSTDB::Object::Host;
@HOSTDB::Object::Host::ISA = qw(HOSTDB::Object);


=head1 NAME

HOSTDB::Object::Host - Host objects.

=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw);

  my $host;
  if ($create_new) {
	$host = $hostdb->create_host ();
  } else {
	$host = $hostdb->findhostbyname ($searchfor);
  }


=head1 DESCRIPTION

Host object routines. A host object has the following attributes :

  id			- unique identifier (numeric, database assigned)
  dhcpmode		- static or dynamic DHCP
  dhcpstatus		- generate DHCP config for this host or not
  mac_address		- ethernet controller hardware address
  dnsmode		- A and PTR record, or just A record and no PTR
  dnsstatus		- generate DNS config for this host or not
  hostname		- hostname
  dnszone		- DNS zone name
  manual_dnszone	- whether or not to automatically update dnszone
  ip			- ip
  n_ip			- ip in network order numerical format
  owner			- HOSTDB::Auth identifier that may modify this host
  ttl			- DNS TTL to use for this host
  comment		- a comment field
  partof		- a reference to another host object's id
  mac_address_ts	- a timestamp showing when this host was last seen on the network
  unix_mac_address_ts	- mac_address_ts expressed as a UNIX timestamp
  profile		- what profile this host has - currently only what DHCP
			  config file it should be written to

Supposed FAQ:

Q: Why dhcpstatus and dnsstatus?
A: The idea with having dhcpstatus and dnsstatus in addition to dhcpmode and dnsmode is
to be able to temporarily disable DHCP/DNS config generation without losing the original
settings.

Q: Why n_ip?
A: Yes, it is redundantly stored information, but it makes finding all hosts in a given
subnet etcetera incredibly much easier (in MySQL).

Q: Why owner?
A: We have had loose ideas of granting 'owner' rights to modify the host object, but
now it seems more like a good way to indicate who is responsible for a host and who
to talk to before modifying/deleting a host.

Q: Why partof?
A: Database modelling were very much simplified with this 'one host object per network
interface' idea. Without that, MAC addresses and hostnames and IP addresses would have
had to live in separate tables and selecting/updating/deleting would have been much
harder to program and HOSTDB would have been much more complex.
A frontend can still hide all 'sub-hosts' and show addresses and such in any way it
whishes.


=head1 EXPORT

None.

=head1 METHODS

=cut



sub init
{
	my $self = shift;
	my $hostdb = $self->{hostdb};

	$self->_debug_print ("creating object");

	if ($hostdb->{_dbh}) {
		$self->{_new_host} = $hostdb->{_dbh}->prepare ("INSERT INTO $hostdb->{db}.host (dhcpmode, dhcpstatus, mac, dnsmode, dnsstatus, hostname, dnszone, manual_dnszone, ip, n_ip, owner, ttl, comment, partof, mac_address_ts, profile) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
			or die "$DBI::errstr";
		$self->{_update_host} = $hostdb->{_dbh}->prepare ("UPDATE $hostdb->{db}.host SET dhcpmode = ?, dhcpstatus = ?, mac = ?, dnsmode = ?, dnsstatus = ?, hostname = ?, dnszone = ?, manual_dnszone = ?, ip = ?, n_ip = ?, owner = ?, ttl = ?, comment = ?, partof = ?, mac_address_ts = ?, profile = ? WHERE id = ?")
			or die "$DBI::errstr";
		$self->{_delete_host} = $hostdb->{_dbh}->prepare ("DELETE FROM $hostdb->{db}.host WHERE id = ?")
			or die "$DBI::errstr";

		$self->{_get_last_id} = $hostdb->{_dbh}->prepare ("SELECT LAST_INSERT_ID()")
			or die "$DBI::errstr";
	} else {
		$hostdb->_debug_print ("NOT preparing database stuff");
	}
	
	return 1;
}

=head1 PACKAGE HOSTDB::Object::Host


=head2 commit

	$host->commit () or die ("Could not commit host object: $host->{error}\n");

	Commit this host object to database. Works on new host objects as well
	as updated ones.


=cut
sub commit
{
	my $self = shift;

	# fields in database order
	my @db_values = ($self->dhcpmode (),
			 $self->dhcpstatus (),
			 $self->mac_address (),
			 $self->dnsmode (),
			 $self->dnsstatus (),
			 $self->hostname (),
			 $self->dnszone (),
			 $self->manual_dnszone (),
			 $self->ip (),
			 $self->n_ip (),
			 $self->owner (),
			 $self->ttl (),
			 $self->comment (),
			 $self->partof (),
			 $self->mac_address_ts (),
			 $self->profile ()
			);
	my $sth;
	if (defined ($self->id ()) and $self->id () >= 0) {
		$sth = $self->{_update_host};
		$sth->execute (@db_values, $self->id ())
			or die "$DBI::errstr\n";
		
		# XXX check number of rows affected?

		$sth->finish();
	} else {
		# this is a new entry

		$sth = $self->{_new_host};
		$sth->execute (@db_values) or die "$DBI::errstr";

		$sth->finish ();

		# fill in $self->{id}
		$sth = $self->{_get_last_id};
		$sth->execute () or die "$DBI::errstr";
		my @t = $sth->fetchrow_array ();
		$self->{id} = $t[0];
		$sth->finish ();
	}

	return 1;
}


=head2 delete

	Not yet documented, saving that for a rainy day.


=cut
sub delete
{
	my $self = shift;
	my $check = shift;

	if (! defined ($check) or $check ne "YES") {
		$self->_set_error ("Delete function invoked with incorrect magic cookie");
		return 0;
	}

	# XXX delete both host attributes, aliases and host object in a database transaction

	my @attributes = $self->init_attributes ();
	foreach my $attr (@attributes) {
		my $fail = 0;
		$attr->delete ($check) or $fail = 1;
		if ($fail) {
			my $attrid = $attr->id ();
			my $attrerror = $attr->{error};
			$self->_set_error ("Failed deleting a host attribute (id $attrid) - $attrerror");
			return 0;
		}
	}

	my @aliases = $self->init_aliases ();
	foreach my $alias (@aliases) {
		my $fail = 0;
		$alias->delete ($check) or $fail = 1;
		if ($fail) {
			my $aliasid = $alias->id ();
			my $aliaserror = $alias->{error};
			$self->_set_error ("Failed deleting a host alias (id $aliasid) - $aliaserror");
			return 0;
		}
	}
	
	if (defined ($self->{id})) {
		my $sth = $self->{_delete_host};
		$sth->execute ($self->id ()) or die "$DBI::errstr";
		
		my $rowcount = $sth->rows ();

		$sth->finish();
		
		if ($rowcount != 1) {
			$self->_set_error ("Delete operation of host with id '$self->{id}' did not affect the expected number of database rows ($rowcount, not 1)");
			return 0;
		}
	} else {
		$self->_set_error ('Host not in database');
		return 0;
	}

	return 1;
}

=head2 init_attributes

	Loads the hosts attributes from the database.

	# set property
	$n = $host->init_attributes ();

	print ("The host has $n attributes\n");


=cut
sub init_attributes
{
	my $self = shift;

	if (defined ($self->{id})) {
		$self->_debug_print ("Find all host attributes with hostid '$self->{id}'");

		@{$self->{attributes}} = $self->{hostdb}->findhostattributesbyhostid ($self->{id});
	} else {
		$self->_set_error ('Host not in database');
		return 0;
	}

	wantarray ? @{$self->{attributes}} : 1;
}


=head2 init_aliases

	Loads the hosts aliases from the database.

	# set property
	$n = $host->init_aliases ();

	print ("The host has $n aliases\n");


=cut
sub init_aliases
{
	my $self = shift;

	if (defined ($self->{id})) {
		$self->_debug_print ("Find all host aliases with hostid '$self->{id}'");

		@{$self->{aliases}} = $self->{hostdb}->findhostaliasesbyhostid ($self->{id});
	} else {
		$self->_set_error ('Host not in database');
		return 0;
	}

	wantarray ? @{$self->{aliases}} : 1;
}


=head2 get_attribute

	Locate a specific attribute in this hosts attribute-list. Make sure
	you have called $host->init_attributes () before using this!

	Blah

=cut
sub get_attribute
{
	my $self = shift;
	my $attribute = shift;
	my $section = shift;

	my @res;

	foreach my $attr (@{$self->{attributes}}) {
		if ($attr->key () eq $attribute and
		    $attr->section () eq $section) {
			push (@res, $attr);
		}
	}

	wantarray ? @res : $res[0];
}


=head2 create_hostattribute

	$attr = $hostdb->create_hostattribute();

	Gets you a brand new HOSTDB::Object::HostAttribute object.


=cut
sub create_hostattribute
{
	my $self = shift;
	
	my $o = bless {},"HOSTDB::Object::HostAttribute";
	$o->{hostdb} = $self->{hostdb};
	$o->{debug} = $self->{debug};
	$o->{hostid} = $self->{id};
	$self->_set_error ($o->{error}), return undef if (! $o->init());
	
	return ($o);
}


=head2 create_hostalias

	$alias = $hostdb->create_hostalias();

	Gets you a brand new HOSTDB::Object::HostAlias object.


=cut
sub create_hostalias
{
	my $self = shift;
	
	my $o = bless {},'HOSTDB::Object::HostAlias';
	$o->{hostdb} = $self->{hostdb};
	$o->{debug} = $self->{debug};
	$o->{hostid} = $self->{id};
	$self->_set_error ($o->{error}), return undef if (! $o->init ());
	
	return ($o);
}




=head2 dhcpmode

    Set DHCP mode for this host. This can be either DYNAMIC or STATIC.


	# set property
	$host->dhcpmode ("STATIC");

	print ("This is a dynamic entry\n") if ($host->dhcpmode () eq "DYNAMIC");


=cut
sub dhcpmode
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&_validate_dhcpmode, @_);
}


=head2 dhcpstatus

    Set DHCP status for this host. This can be either ENABLED or DISABLED.
    This effectively controls wheter to generate any DHCP config for this
    host or not.

	# set property
	$host->dhcpstatus ("DISABLED");

	if ($host->dhcpstatus () eq "DISABLED") {
		print ("Will not generate any DHCP config for this host \n");
	}


=cut
sub dhcpstatus
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_enabled_or_disabled, @_);
}


=head2 mac_address

    Get or set this hosts MAC address (hardware address).
    Uses clean_mac_address () on supplied value.

	print ("Old MAC address: " . $host->mac_address ());
	$host->mac_address ($new_mac) or warn ("Failed setting value\n");


=cut
sub mac_address
{
    my $self = shift;
    $self->_set_or_get_attribute ('mac', \&_validate_mac_address, @_);
}


=head2 dnsmode

    Set DNS mode for this host. This can be either A_AND_PTR or A.
    'A_AND_PTR' is for regular hosts, it will generate both A and PTR
    DNS records. 'A' is to just generate an A record and no PTR.


	# set property
	$host->dnsmode ("A");

	print ("This is an alias\n") if ($host->dnsmode () eq "A");


=cut
sub dnsmode
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&_validate_dnsmode, @_);
}


=head2 dnsstatus

    Set DNS status for this host. This can be either ENABLED or DISABLED.
    This effectively controls wheter to generate any DNS config for this
    host or not.

	# set property
	$host->dnsstatus ("DISABLED");

	if ($host->dnsstatus () eq "DISABLED") {
		print ("Will not generate any DNS config for this host \n");
	}


=cut
sub dnsstatus
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_enabled_or_disabled, @_);
}


=head2 hostname

    Get or set this hosts hostname.
    Uses clean_hostname () on supplied value.

	print ("Old hostname: " . $host->hostname ());
	$host->hostname ($new_hostname) or warn ("Failed setting value\n");


=cut
sub hostname
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_clean_hostname, @_);
}


=head2 dnszone

    Get or set this hosts DNS zonename.
    Uses clean_domainname () on supplied value.

	print ("Old zonename: " . $host->dnszone ());
	$host->dnszone ($new_zonename) or warn ("Failed setting value\n");


=cut
sub dnszone
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_clean_domainname, @_);
}


=head2 manual_dnszone

    If this is 'Y' (the default), operations that change the hostname
    or change zones will automatically update this objects dnszone.
    Glue records could be obtained through setting this to 'N' and setting
    dnszone to the parent zone.

    XXX example


=cut
sub manual_dnszone
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_y_or_n, @_);
}


=head2 ip

    Get or set this hosts IP address. This function also updates the
    numerical IP address field n_ip.

	print ("Old IP: " . $host->ip ());
	$host->ip ($new_ip) or warn ("Failed setting value\n");


=cut
sub ip
{
    my $self = shift;

    if (@_) {
	my $newvalue = shift;
		
	if (! $self->is_valid_ip ($newvalue)) {
	    $self->_set_error ("Invalid IP address '$newvalue'");
	    return 0;
	}

	$self->{ip} = $newvalue;
	
	# redundantly stored, but this enables us to do much simpler
	# database querys (for hosts in ranges of IPs etc.)
	$self->{n_ip} = $self->aton ($newvalue);
	
	return 1;
    }
    
    return ($self->{ip});
}


=head2 n_ip

    Read only function that returns this hosts IP address in host order.
    Use the ip() function to set this value.


=cut
sub n_ip
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_read_only, @_);
}


=head2 ttl

    Get or set this hosts DNS records TTL value. This should be
    either a number of seconds, or something that
    is_valid_nameserver_time () validates (the default function
    validates things parseable by BIND9, such as 1d or 1w2d3h4m5s).

    If you want to use the default TTL value, set to "NULL".

	print ("Old ttl: " . $host->ttl ());
	$host->ttl ($new_ttl) or warn ("Failed setting value\n");


=cut
sub ttl
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_nameserver_time_or_null, @_);
}


=head2 profile

	XXX

=cut
sub profile
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&_validate_profile, @_);
}


=head2 comment

    Get or set this hosts comment. Just an informative field.

	print ("Old comment: " . $host->comment ());
	$host->comment ($new_comment) or warn ("Failed setting comment\n");


=cut
sub comment
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_string_comment, @_);
}


=head2 owner

	Get or set this hosts owner. The thoughts for having a owner is
	to control who can update this object. This is however not
	implemented for host objects yet.
	Owner can either be a single username or a comma-separated
	list of usernames.

	printf "Old owner: %s\n", $host->owner ();
	$host->owner ($new_owner) or warn ("Failed setting value\n");


=cut
sub owner
{
    my $self = shift;

    if (@_) {
	my $l = join (',', @_);
	$self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_list_of_usernames, $l);
    } else {
	# get
	$self->_set_or_get_attribute ();
    }
}


=head2 id

	Get object database ID number. This is read only.

=cut
sub id
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_read_only, @_);
}


=head2 partof

    Get or set which other host object this host object is to be
    considered a part of. A host with multiple network interface
    cards (meaning multiple MAC addresses and possibly multiple
    DNS records) will have a primary host id object and one or
    more other host objects which has partof () set to the primary
    host objects id ().

	print ("Old partof: " . $host->partof ());
	$parent = $hostdb->findhostbyname ("server.example.com");
	die ("Failed fetching parent host object\n") unless ($parent);
	$host->partof ($parent->id ()) or warn ("Failed setting value\n");


=cut
sub partof
{
    my $self = shift;
    $self->_set_or_get_attribute (undef, \&_validate_partof, @_);
}


=head2 mac_address_ts

	Get or set the MAC address timestamp field of this host object.
	This is intended to be a timestamp of what the time was when this
	hosts IP was seen using this MAC address on the network. This is
	good because it let\'s network administrators see what IP addresses
	are actually being used and not.

	Valid formats for setting are: yyyy-mm-dd hh:mm:ss
				       NOW
				       unixtime:nnnnnnnnnn

=cut
sub mac_address_ts
{
	my $self = shift;

	$self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_datetime, @_);
}


=head2 unix_mac_address_ts

	unix_mac_address_ts is mac_address_ts but expressed as a UNIX
	timestamp. It is not stored in the database, but calculated at
	the time a host object is fetched from the database. The only
	purpose of this is to make it easier for applications using
	host objects to perform date calculations.

	printf "The host was last seen %i seconds ago.\n",
	       time () - $host->unix_mac_address_ts ();


=cut
sub unix_mac_address_ts
{
	my $self = shift;

	$self->_set_or_get_attribute (undef, \&HOSTDB::Object::_validate_read_only, @_);
}


=head1 PACKAGE HOSTDB::DB::Object::Host PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.


=head2 _validate_dhcpmode

    _set_or_get_attribute validator function for dhcpmode


=cut
sub _validate_dhcpmode
{
    my $self = shift;
    my $key = shift;
    my $newvalue = uc ($_[0]);

    if ($newvalue ne 'STATIC' and $newvalue ne 'DYNAMIC') {
        return ('Value is neither STATIC nor DYNAMIC');
    }

    # write back to $_[0] if our uc () changed the value
    $_[0] = $newvalue if ($newvalue ne $_[0]);

    return 0;
}


=head2 _validate_dnsmode

    _set_or_get_attribute validator function for dnsmode


=cut
sub _validate_dnsmode
{
    my $self = shift;
    my $key = shift;
    my $newvalue = uc ($_[0]);

    if ($newvalue ne 'A_AND_PTR' and $newvalue ne 'A') {
        return ('Value is neither A_AND_PTR nor A');
    }

    # write back to $_[0] if our uc () changed the value
    $_[0] = $newvalue if ($newvalue ne $_[0]);

    return 0;
}


=head2 _validate_mac_address

    _set_or_get_attribute validator function for mac_address


=cut
sub _validate_mac_address
{
    my $self = shift;
    my $key = shift;
    my $newvalue = lc ($_[0]);

    if ($newvalue eq 'null') {
	$_[0] = undef;
    } elsif (! $self->clean_mac_address ($_[0])) {
	return ('Invalid MAC address');
    }

    return 0;
}


=head2 _validate_profile

    _set_or_get_attribute validator function for profile


=cut
sub _validate_profile
{
    my $self = shift;
    my $key = shift;
    my $newvalue = lc ($_[0]);

    if ($newvalue eq 'null') {
	$_[0] = 'default';
    } elsif (! $self->is_valid_profilename ($newvalue)) {
	return ('Invalid profile');
    }

    return 0;
}


=head2 _validate_partof

    _set_or_get_attribute validator function for partof


=cut
sub _validate_partof
{
    my $self = shift;
    my $key = shift;
    my $newvalue = lc ($_[0]);

    if (! defined ($newvalue) or $newvalue eq 'null') {
	$_[0] = undef;
    } elsif ((int ($newvalue) == 0) and ($newvalue !~ /^0+$/)) {
	return ('Invalid partof');
    } elsif (int ($newvalue) != 0 and (int ($newvalue) == int ($self->{id}))) {
	return ('Host cannot be partof itself');
    } else {
	$_[0] = int($newvalue);
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
