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

	# XXX delete both host attributes and host object in a database transaction

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




=head2 dhcpmode

	Set DHCP mode for this host. This can be either DYNAMIC or STATIC.


	# set property
	$host->dhcpmode ("STATIC");

	print ("This is a dynamic entry\n") if ($host->dhcpmode () eq "DYNAMIC");


=cut
sub dhcpmode
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue eq 'DYNAMIC' or $newvalue eq 'STATIC') {
			$self->{dhcpmode} = $newvalue;
		} else {
			$self->_set_error ("Invalid dhcpmode '$newvalue'");
			return 0;
		}

		return 1;
	}

	return ($self->{dhcpmode});
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

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue eq 'ENABLED' or $newvalue eq 'DISABLED') {
			$self->{dhcpstatus} = $newvalue;
		} else {
			$self->_set_error ("Invalid dhcpstatus '$newvalue'");
			return 0;
		}

		return 1;
	}

	return ($self->{dhcpstatus});
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

	if (@_) {
		my $newvalue = shift;
		if ($newvalue eq 'NULL') {
			$self->{mac} = undef;
			return 1;
		}
		return 0 if (! $self->clean_mac_address ($newvalue));
		$self->{mac} = $newvalue;

		return 1;
	}

	return ($self->{mac});
}


=head2 dnsmode

	Set DHCP mode for this host. This can be either A_AND_PTR or A.
	'A_AND_PTR' is for regular hosts, it will generate both A and PTR
	DNS records. 'A' is to just generate an A record and no PTR.


	# set property
	$host->dnsmode ("A");

	print ("This is an alias\n") if ($host->dnsmode () eq "A");


=cut
sub dnsmode
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue eq 'A_AND_PTR' or $newvalue eq 'A') {
			$self->{dnsmode} = $newvalue;
		} else {
			$self->_set_error ("Invalid dnsmode '$newvalue'");
			return 0;
		}

		return 1;
	}

	return ($self->{dnsmode});
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

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue eq 'ENABLED' or $newvalue eq 'DISABLED') {
			$self->{dnsstatus} = $newvalue;
		} else {
			$self->_set_error ("Invalid dnsstatus '$newvalue'");
			return 0;
		}

		return 1;
	}

	return ($self->{dnsstatus});
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

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq 'NULL') {
			$self->{hostname} = undef;
			return 1;
		}
	
		if (! $self->clean_hostname ($newvalue)) {
			$self->_set_error ("Invalid hostname '$newvalue'");
			return 0;
		}
		$self->{hostname} = $newvalue;

		return 1;
	}

	return ($self->{hostname});
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

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq 'NULL') {
			$self->{dnszone} = undef;
			return 1;
		}
	
		if (! $self->clean_domainname ($newvalue)) {
			$self->_set_error ("Invalid dnszone '$newvalue'");
			return 0;
		}
		$self->{dnszone} = $newvalue;

		return 1;
	}

	return ($self->{dnszone});
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

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue =~ /^y/oi) {
			$self->{manual_dnszone} = 'Y';
		} elsif ($newvalue =~ /^n/oi) {
			$self->{manual_dnszone} = 'N';
		} else {
			$self->_set_error ("Invalid manual_dnszone '$newvalue'");
			return 0;
		}
		
		return 1;
	}

	return ($self->{manual_dnszone});
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


=cut
sub n_ip
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by ip()");
		return undef;
	}

	return ($self->{n_ip});
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

	if (@_) {
		my $newvalue = lc (shift);

		if ($newvalue eq 'null') {
			$self->{ttl} = undef;
		} else {
			if (! $self->is_valid_nameserver_time ($newvalue)) {
				$self->_set_error ("Invalid TTL time value '$newvalue'");
				return 0;
			}
			$self->{ttl} = $self->_nameserver_time_to_seconds ($newvalue);
		}

		return 1;
	}

	return ($self->{ttl});
}


=head2 profile

	XXX

=cut
sub profile
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq 'NULL') {
			$self->{profile} = 'default';
		} else {
			if (! $self->is_valid_profilename ($newvalue)) {
				$self->_set_error ("Invalid profile name '$newvalue'");
				return undef;
			}
			$self->{profile} = $newvalue;
		}

		return 1;
	}

	return ($self->{profile});
}


=head2 comment

	Get or set this hosts comment. Just an informative field.

	print ("Old comment: " . $host->comment ());
	$host->comment ($new_comment) or warn ("Failed setting value\n");


=cut
sub comment
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if (length ($newvalue) > 255) {
			$self->_set_error ('Comment too long (max 255 chars)');
			return 0;
		}

		$self->{comment} = $newvalue;
	
		return 1;
	}

	return ($self->{comment});
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
		my %newlist;
		foreach my $tt (@_) {
			my $t = $tt;
			# remove spaces around commas
			$t =~ s/\s*,\s*/,/o;
			
			foreach my $newvalue (split (',', $t)) {
				if (! $self->is_valid_username ($newvalue)) {
					$self->_set_error ("Invalid owner list member '$newvalue'");
					return 0;
				}
				$newlist{$newvalue} = 1;
			}
		}

		my $newvalue = join (',', sort keys %newlist);

		if (length ($newvalue) > 255) {
			$self->_set_error ('Owner too long (max 255 chars)');
		}

		$self->{owner} = $newvalue;
		
		return 1;
	}

	return ($self->{owner});
}


=head2 id

	Get object database ID number. This is read only.

=cut
sub id
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("id is read only");
		return 0;
	}

	return ($self->{id});
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

	if (@_) {
		my $newvalue = shift;
	
		if (! defined ($newvalue) or $newvalue eq 'NULL') {
			$self->{partof} = undef;
			return 1;
		}

		if ((int($newvalue) == 0) and ($newvalue !~ /^0+$/)) {
			$self->_set_error ("Invalid partof");
			return 0;
		}

		if (int($newvalue) != 0 and (int($newvalue) == int($self->{id}))) {
			$self->_set_error ("Host cannot be partof itself");
			return 0;
		}

		$self->{partof} = int($newvalue);

		return 1;
	}

	return ($self->{partof});
}


=head2 mac_address_ts

	Get or set the MAC address timestamp field of this host object.
	This is intended to be a timestamp of what the time was when this
	hosts IP was seen using this MAC address on the network. This is
	good because it let's network administrators see what IP addresses
	are actually being used and not.

	Valid formats for setting are: yyyy-mm-dd hh:mm:ss
				       NOW
				       unixtime:nnnnnnnnnn

=cut
sub mac_address_ts
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		my $fmtvalue = $self->_format_datetime ($newvalue);
		if (defined ($fmtvalue)) {
			if ($fmtvalue eq 'NULL') {
				$self->{mac_address_ts} = undef;
			} else {
				$self->{mac_address_ts} = $fmtvalue;
			}

			return 1;
		} else {
			$self->_set_error ("Invalid mac_address timestamp format");
			return 0;
		}

		return 1;
	}

	return ($self->{mac_address_ts});
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

	if (@_) {
		$self->_set_error ("unix_mac_address_ts is read only");
		return 0;
	}

	return ($self->{unix_mac_address_ts});
}


=head1 PACKAGE HOSTDB::DB::Object::Host PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.




1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
