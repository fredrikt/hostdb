# $Id$

use HOSTDB::Object;

package HOSTDB::Object::Subnet;
@HOSTDB::Object::Subnet::ISA = qw(HOSTDB::Object);

sub init
{
	my $self = shift;
	my $hostdb = $self->{hostdb};

	if (! defined ($self->{subnet})) {
		# subnet not defined, this can be because our caller is the _find function
		if (defined ($self->{netaddr}) and
		    defined ($self->{slashnotation})) {
		
			$self->{subnet} = "$self->{netaddr}/$self->{slashnotation}";

			# XXX ugly hack
			$self->{in_db} = 1;
		}
	} else {
		# XXX ugly hack
		$self->{in_db} = 0;
	}
	
	$hostdb->_debug_print ("creating object (IPv$self->{ipver} subnet '$self->{subnet}')");

	return undef if (! $self->subnet ($self->{subnet}));
	delete ($self->{subnet});	# the info is kept in $self->{netaddr} and $self->{slashnotation}
	
	if ($hostdb->{_dbh}) {
		$self->{_new_subnet} = $hostdb->{_dbh}->prepare ("INSERT INTO $hostdb->{db}.subnet " .
			"(ipver, netaddr, slashnotation, netmask, broadcast, addresses, description, " .
			"short_description, n_netaddr, n_netmask, n_broadcast, htmlcolor, dhcpconfig) " .
			"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
			or die "$DBI::errstr";
		$self->{_update_subnet} = $hostdb->{_dbh}->prepare ("UPDATE $hostdb->{db}.subnet SET " .
			"ipver = ?, netaddr = ?, slashnotation = ?, netmask = ?, broadcast = ?, " .
			"addresses = ?, " .
			"description = ?, short_description = ?, n_netaddr = ?, n_netmask = ?, " .
			"n_broadcast = ?, htmlcolor = ?, dhcpconfig = ? WHERE id = ?")
			or die "$DBI::errstr";
		$self->{_delete} = $hostdb->{_dbh}->prepare ("DELETE FROM $hostdb->{db}.subnet WHERE id = ?");
	} else {
		$hostdb->_debug_print ("NOT preparing database stuff");
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
			 $self->dhcpconfig ()
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

sub delete
{
	my $self = shift;
	my $check = shift;

	return 0 if ($check ne "YES");

	my $sth;
	if (defined ($self->{id})) {
		$sth = $self->{_delete};
		$sth->execute ($self->id ()) or die "$DBI::errstr";
		
		# XXX check number of rows affected?

		$sth->finish();
	} else {
		$self->_set_error ("Subnet not in database");
		return 0;
	}

	return 1;
}

sub subnet
{
	my $self = shift;

	if (@_) {
		my $subnet = shift;

		$self->_debug_print ("setting subnet '$subnet'");

		return undef if (! $self->is_valid_subnet ($subnet));
	
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

sub id
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it is a database auto increment");
		return undef;
	}

	return ($self->{id});
}

sub ipver
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue != 4 && $newvalue && 6) {
			$self->_set_error ("IP version " . $self->ipver () . " invalid (let's keep to 4 or 6 please)");
			return 0;
		}
		
		$self->{ipver} = $newvalue;
		
		return 1;
	}

	return ($self->{ipver});
}

sub netaddr
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{netaddr});
}

sub slashnotation
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{slashnotation});
}

sub netmask
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{netmask});
}

sub broadcast
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{broadcast});
}

sub addresses
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{addresses});
}

sub description
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		$self->{description} = $newvalue;
		
		return 1;
	}

	return ($self->{description});
}

sub short_description
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		$self->{short_description} = $newvalue;
		
		return 1;
	}

	return ($self->{short_description});
}

sub n_netaddr
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{n_netaddr});
}

sub n_netmask
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{n_netmask});
}

sub n_broadcast
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("this is a read-only function, it gets set by subnet()");
		return undef;
	}

	return ($self->{n_broadcast});
}

sub htmlcolor
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		$self->{htmlcolor} = $newvalue;
		
		return 1;
	}

	return ($self->{htmlcolor});
}

sub dhcpconfig
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		$self->{dhcpconfig} = $newvalue;
		
		return 1;
	}

	return ($self->{dhcpconfig});
}


