# $Id$

use strict;
use HOSTDB::Object;

package HOSTDB::Object::Subnet;
@HOSTDB::Object::Subnet::ISA = qw(HOSTDB::Object);

=head1 NAME

HOSTDB::Object::Subnet - Subnet objects.

=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw);

  my $subnet;
  if ($create_new) {
	$subnet = $hostdb->create_subnet ();
  } else {
	$subnet = $hostdb->findsubnet ($searchfor);
  }


=head1 DESCRIPTION

Subnet object routines. A subnet object has the following attributes :

  id			- unique identifier (numeric, database assigned)
  ipver			- IP version (NOTE: only '4' is supported for now!)
  netaddr		- the network address of the subnet
  slashnotation		- the size of the subnet in slash notation
  netmask		- the size of the subnet as a netmask
  broadcast		- the broadcast address for this subnet
  addresses		- the size of the subnet in number of addresses
  description		- well, description
  short_description	- used where a long description might not fit (netplan)
  n_netaddr		- the network address in network order numerical format
  n_netmask		- the netmask in network order numerical format
  n_broadcast		- the broadcast address in network order numerical format
  htmlcolor		- this subnet's color in the graphic netplan
  dhcpconfig		- a BLOB containing free-format DHCP config for this subnet
  owner			- HOSTDB::Auth identifier that may modify hosts in this subnet
  profilelist		- a comma-separated list of profiles for this subnet


Supposed FAQ :

Q: Why ipver if only IPv4 is supported?
A: To make it one step easier to add IPv6 support. Patches welcome.

Q: Why store size/other attributes in so many formats?
A: To Keep It Simple. It makes selecting and building frontends a whole lot easier,
and all attributes are updated at once (from this code) - they can't end up
unsynchronized.

Q: My broadcast address is not the last address of my subnet!?!?
A: Get real.


=head1 EXPORT

None.

=head1 METHODS

=cut




sub init
{
	my $self = shift;
	my $hostdb = $self->{hostdb};


	if (! defined ($self->{netaddr}) and defined ($self->{subnet})) {
		$self->subnet ($self->{subnet});
	} else {
		$hostdb->_debug_print ("creating object (IPv$self->{ipver} subnet '$self->{netaddr}/$self->{slashnotation}')");
	}
	
	if ($hostdb->{_dbh}) {
		$self->{_new_subnet} = $hostdb->{_dbh}->prepare ("INSERT INTO $hostdb->{db}.subnet " .
			"(ipver, netaddr, slashnotation, netmask, broadcast, addresses, description, " .
			"short_description, n_netaddr, n_netmask, n_broadcast, htmlcolor, dhcpconfig, " .
			"owner, profilelist) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
			or die "$DBI::errstr";
		$self->{_update_subnet} = $hostdb->{_dbh}->prepare ("UPDATE $hostdb->{db}.subnet SET " .
			"ipver = ?, netaddr = ?, slashnotation = ?, netmask = ?, broadcast = ?, " .
			"addresses = ?, " .
			"description = ?, short_description = ?, n_netaddr = ?, n_netmask = ?, " .
			"n_broadcast = ?, htmlcolor = ?, dhcpconfig = ?, owner = ?, profilelist = ? WHERE id = ?")
			or die "$DBI::errstr";
		$self->{_delete_subnet} = $hostdb->{_dbh}->prepare ("DELETE FROM $hostdb->{db}.subnet WHERE id = ?")
			or die "$DBI::errstr";
	} else {
		$hostdb->_debug_print ("NOT preparing database stuff (since my HOSTDB has no DBH)");
	}

	return 1;
}

=head1 PACKAGE HOSTDB::Object::Subnet


=head2 commit

	$subnet->commit () or die ("Could not commit subnet object: $subnet->{error}\n");

	Commit this subnet object to database. Works on new subnet objects as well
	as updated ones.


=cut
sub commit
{
	my $self = shift;

	# fields in database order
	my @db_values = ($self->ipver (),
			 $self->netaddr (),
			 $self->slashnotation (),
			 $self->netmask (),
			 $self->broadcast (),
			 $self->addresses (),
			 $self->description (),
			 $self->short_description (),
			 $self->n_netaddr (),
			 $self->n_netmask (),
			 $self->n_broadcast (),
			 $self->htmlcolor (),
			 $self->dhcpconfig (),
			 $self->owner (),
			 $self->profilelist ()
			);

	my $sth;
	if (defined ($self->{id})) {
		$sth = $self->{_update_subnet};
		$sth->execute (@db_values, $self->id ()) or die "$DBI::errstr";
		
		# XXX check number of rows affected?

		$sth->finish();
	} else {
		# this is a new entry, first check that it does not overlap
		# with something already in the database

		my $hostdb = $self->{hostdb};
		my @subnets = $hostdb->findsubnetlongerprefix ($self->subnet ());
		
		if ($#subnets != -1) {
			my ($t, @names);
			
			foreach $t (@subnets) {
				push (@names, $t->subnet ());
			}
			
			$self->_set_error ($self->subnet () . " overlaps with subnet(s) " .
					   join (", ", @names));
					   
			return 0;
		}

		$sth = $self->{_new_subnet};
		$sth->execute (@db_values) or die "$DBI::errstr";

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

	return 0 if ($check ne "YES");

	my $sth;
	if (defined ($self->{id})) {
		$sth = $self->{_delete_subnet};
		$sth->execute ($self->id ()) or die "$DBI::errstr";
		
		# XXX check number of rows affected?

		$sth->finish();
	} else {
		$self->_set_error ("Subnet not in database");
		return 0;
	}

	return 1;
}


=head2 subnet

	Get or set this subnets address and size. This is the way to
	update all the following attributes :

		subnet
		netaddr
		slashnotation
		n_netaddr
		netmask
		n_netmask
		addresses
		broadcast
		n_broadcast

	printf "Old subnet address: %s (netmask %s)\n",
		$subnet->subnet (), $subnet->netmask ();
	$subnet->subnet ($new_subnet) or warn ("Failed setting value\n");


=cut
sub subnet
{
	my $self = shift;

	if (@_) {
		my $subnet = shift;

		$self->_debug_print ("setting subnet '$subnet'");

		if (! $self->is_valid_subnet ($subnet)) {
			$self->_set_error ("Invalid subnet '$subnet'");
			return 0;
		}
	
		my ($netaddr, $slash) = split ('/', $subnet);

		$self->{netaddr} = $netaddr;
		$self->{slashnotation} = $slash;

		# All these are redundantly stored. Some people I'm sure
		# calls it database bloat, poor design etcetera but I call
		# it simpler querys, less code (except here), less bugs.
		# In one word - better.
		$self->{n_netaddr} = $self->aton ($netaddr);
		$self->{netmask} = $self->slashtonetmask ($slash);
		$self->{n_netmask} = $self->aton ($self->slashtonetmask ($slash));
		$self->{addresses} = $self->get_num_addresses ($slash);
		$self->{broadcast} = $self->get_broadcast ($subnet);
		$self->{n_broadcast} = $self->aton ($self->{broadcast});

		return 1;
	}
	
	return ($self->netaddr () . "/" . $self->slashnotation ());
}


=head2 id

	Read only function (database supplied object identifier).


=cut
sub id
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('id is a read-only function, it is a database auto increment');
		return undef;
	}

	return ($self->{id});
}


=head2 ipver

	Not yet documented, saving that for a rainy day.


=cut
sub ipver
{
	my $self = shift;

	if (@_) {
		my $newvalue = int (shift);
	
		if ($newvalue != 4 && $newvalue != 6) {
			$self->_set_error ("IP version " . $self->ipver () . " invalid (let's keep to 4 or 6 please)");
			return 0;
		}
		
		$self->{ipver} = $newvalue;
		
		return 1;
	}

	return ($self->{ipver});
}


=head2 netaddr

	Read only function, see 'subnet' above.
	
	printf "Network address: %s\n", $subnet->netaddr ();


=cut
sub netaddr
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('netaddr is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{netaddr});
}


=head2 slashnotation

	Read only function, see 'subnet' above.
	
	printf "Slash notation: %s\n", $subnet->slashnotation ();


=cut
sub slashnotation
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('slashnotation is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{slashnotation});
}


=head2 netmask

	Read only function, see 'subnet' above.
	
	printf "Netmask: %s\n", $subnet->netmask ();


=cut
sub netmask
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('netmask is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{netmask});
}


=head2 broadcast

	Read only function, see 'subnet' above.
	
	printf "Broadcast: %s\n", $subnet->broadcast ();


=cut
sub broadcast
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('broadcast is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{broadcast});
}


=head2 addresses

	Read only function, see 'subnet' above.
	
	printf "Number of addresses in subnet: %d\n", $subnet->addresses ();


=cut
sub addresses
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('addresses is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{addresses});
}


=head2 description

	Get or set subnet description.

	printf "Old description: %s\n", $subnet->description ();
	$subnet->description ($new_desc) or warn ("Failed setting value\n");


=cut
sub description
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if (length ($newvalue) > 255) {
			$self->_set_error ('Description too long (max 255 chars)');
			return 0;
		}

		$self->{description} = $newvalue;
		
		return 1;
	}

	return ($self->{description});
}


=head2 short_description

	Get or set subnet short description.

	printf "Old short description: %s\n", $subnet->description ();
	$subnet->description ($new_short_desc) or warn ("Failed setting value\n");


=cut
sub short_description
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if (length ($newvalue) > 255) {
			$self->_set_error ('Short description too long (max 255 chars)');
			return 0;
		}

		$self->{short_description} = $newvalue;
		
		return 1;
	}

	return ($self->{short_description});
}


=head2 n_netaddr

	Read only function, see 'subnet' above.
	
	printf "Network address %s (numerically: %d)\n",
		$hostdb->ntoa ($subnet->n_netaddr ()),
		$subnet->n_netaddr ();


=cut
sub n_netaddr
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('n_netaddr is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{n_netaddr});
}


=head2 n_netmask

	Read only function, see 'subnet' above.
	
	printf "Netmask %s (numerically: %d)\n",
		$hostdb->ntoa ($subnet->n_netmask ()),
		$subnet->n_netmask ();


=cut
sub n_netmask
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('n_netmask is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{n_netmask});
}


=head2 n_broadcast

	Read only function, see 'subnet' above.
	
	printf "Broadcast %s (numerically: %d)\n",
		$hostdb->ntoa ($subnet->n_broadcast ()),
		$subnet->n_broadcast ();


=cut
sub n_broadcast
{
	my $self = shift;

	if (@_) {
		$self->_set_error ('n_broadcast is a read-only function, it gets set by subnet()');
		return undef;
	}

	return ($self->{n_broadcast});
}


=head2 htmlcolor

	Get or set htmlcolor. The database itself does not care what format you use.
	Use either HTML format like #ff0000 for red, or put 'red' in the database
	and put mappings of red -> #ff0000 in your hostdb.ini (section subnet_colors).

	printf "Old htmlcolor: %s\n", $subnet->htmlcolor ();
	$subnet->htmlcolor ($new_color) or warn ("Failed setting value\n");


=cut
sub htmlcolor
{
	my $self = shift;

	if (@_) {
		my $newvalue = lc (shift);
	
		if (! $self->is_valid_htmlcolor ($newvalue)) {
			$self->_set_error ("Invalid htmlcolor '$newvalue'");
			return 0;
		}
		
		$self->{htmlcolor} = $newvalue;
		
		return 1;
	}

	return ($self->{htmlcolor});
}


=head2 dhcpconfig

	Get or set dhcpconfig.

	printf "Old DHCP config: %s\n", $subnet->dhcpconfig ();
	$subnet->dhcpconfig ($dhcpcfg) or warn ("Failed setting value\n");


=cut
sub dhcpconfig
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if (length ($newvalue) > 4096) {
			$self->_set_error ('dhcpconfig too long (max 4096 chars)');
			return 0;
		}
		
		$self->{dhcpconfig} = $newvalue;
		
		return 1;
	}

	return ($self->{dhcpconfig});
}


=head2 owner

	Get or set owner. Owner can either be a single username or a
	comma-separated list of usernames.

	printf "Old owner: %s\n", $subnet->owner ();
	$subnet->owner ($new_owner) or warn ("Failed setting value\n");


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


=head2 profilelist

	Get or set list of profiles for this subnet. List should be comma-separated,
	'default' is implicit.

	printf "List: %s\n", $subnet->profilelist ();
	$subnet->profilelist ($new_list) or warn ("Failed setting value\n");


=cut
sub profilelist
{
	my $self = shift;

	if (@_) {
		my %newlist;
		foreach my $tt (@_) {
			my $t = $tt;
			# remove spaces around commas
			$t =~ s/\s*,\s*/,/o;
			
			foreach my $newvalue (split (',', $t)) {
				if (! $self->is_valid_profilename ($newvalue)) {
					$self->_set_error ("Invalid profilelist member '$newvalue'");
					return 0;
				}
				$newlist{$newvalue} = 1;
			}
		}
		$newlist{default} = 1;

		my $newvalue = join (',', sort keys %newlist);

		if (length ($newvalue) > 255) {
			$self->_set_error ('profilelist too long (max 255 chars)');
		}

		$self->{profilelist} = $newvalue;
		
		return 1;
	}

	return ($self->{profilelist});
}





1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
