# $Id$

use HOSTDB::Object;

package HOSTDB::Object::Zone;
@HOSTDB::Object::Zone::ISA = qw(HOSTDB::Object);

sub init
{
	my $self = shift;
	my $hostdb = $self->{hostdb};

	$self->_debug_print ("creating object");

	if ($hostdb->{_dbh}) {
		$self->{_new_zone} = $hostdb->{_dbh}->prepare ("INSERT INTO $hostdb->{db}.zone (zonename, delegated, default_ttl, ttl, mname, rname, serial, refresh, retry, expiry, minimum, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
			or die "$DBI::errstr";
		$self->{_update_zone} = $hostdb->{_dbh}->prepare ("UPDATE $hostdb->{db}.zone SET zonename = ?, delegated = ?, default_ttl = ?, ttl = ?, mname = ?, rname = ?, serial = ?, refresh = ?, retry = ?, expiry = ?, minimum = ?, owner = ? WHERE id = ?")
			or die "$DBI::errstr";
	}

	return 1;
}

=head1 PACKAGE HOSTDB::Object::Zone


=head2 commit

	$zone->commit () or die ("Could not commit zone object: $zone->{error}\n");

	Commit this zone object to database. Works on new zone objects as well
	as updated ones.


=cut
sub commit
{
	my $self = shift;

	# fields in database order
	my @db_values = ($self->zonename (),
			 $self->delegated (),
			 $self->default_ttl (),
			 $self->ttl (),
			 $self->mname (),
			 $self->rname (),
			 $self->serial (),
			 $self->refresh (),
			 $self->retry (),
			 $self->expiry (),
			 $self->minimum (),
			 $self->owner ()
			);

	my $sth;
	if (defined ($self->id ())) {
		$sth = $self->{_update_zone};
		$sth->execute (@db_values, $self->id ())
			or die "$DBI::errstr";
		
		# XXX check number of rows affected?

		$sth->finish();
	} else {
		# this is a new entry

		$sth = $self->{_new_zone};
		$sth->execute (@db_values) or die "$DBI::errstr";

		$sth->finish ();
	}	

	return 1;
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

sub zonename
{
	my $self = shift;

	if (@_) {
		my $zonename = shift;
	
		return 0 if (! $self->clean_domainname ($zonename));
		$self->{zonename} = $zonename;
		
		return 1;
	}

	return ($self->{zonename});
}


=head2 delegated

	Indicate that this is a delegated zone. The reason to have delegated
	zones in your database is that if it is a subzone of one of your
	non-delegated zones you do not want to put host DNS data into your
	non-delegated zone which belongs to the delegated one. Clear? ;)


	# set property
	$zone->delegated ("Y");	# valid values are "Y" (or 1), "N" (or 0)

	# when used to get the value, always returns "Y" or "N" so you
	# can't just do 'if ($zone->delegated ()) ...'
	#
	print ("Zone is delegated\n") if ($zone->delegated () eq "Y");


=cut
sub delegated
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;
	
		if ($newvalue =~ /^y/i or $newvalue == 1) {
			$self->{delegated} = "Y";
		} elsif ($newvalue =~ /^n/i or $newvalue == 0) {
			$self->{delegated} = "N";
		} else {
			$self->set_error ("Invalid delegated format");
			return 0;
		}
		
		return 1;
	}

	return ($self->{delegated});
}

# this is the zone default ttl ($TTL)
sub default_ttl
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{default_ttl} = undef;
		} else {
			$self->{default_ttl} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{default_ttl});
}

sub serial
{
	my $self = shift;
	if (@_) {
		my $newvalue = shift;

		$self->_debug_print ("Setting SOA serial '$newvalue'");

		if ($newvalue eq "NULL") {
			$self->{serial} = undef;
		} else {
			if ($newvalue !~ /^\d{10,10}$/) {
				$self->_set_error("Invalid serial number (should be 10 digits, todays date and two incrementing)");
				return 0;
			}
			$self->{serial} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{serial});
}

sub mname
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{mname} = "NULL";
		} else {
			my $illegal_chars = $newvalue;
			$illegal_chars =~ s/[a-zA-Z0-9\.\-]//og;
			if ($illegal_chars) {
				$self->_set_error ("SOA mname '$newvalue' contains illegal characters ($illegal_chars)");
				return 0;
			}
		}

		$self->{mname} = $newvalue;
		
		return 1;
	}

	return ($self->{mname});
}

sub rname
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{rname} = "NULL";
		} else {
			if ($newvalue =~ /@/) {
				$self->_set_error ("SOA rname ($newvalue) should not contain '\@' signs.");
				return 0;
			}

			my $illegal_chars = $newvalue;
			$illegal_chars =~ s/[a-zA-Z0-9\.\-]//og;
			if ($illegal_chars) {
				$self->_set_error ("SOA rname ($newvalue) contains illegal characters ($illegal_chars)");
				return 0;
			}
		}

		$self->{rname} = $newvalue;
		
		return 1;
	}

	return ($self->{mname});
}

sub refresh
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{refresh} = "NULL";
		} else {
			$self->{refresh} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{refresh});
}

# this is the SOA record itselfs TTL
sub ttl
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{ttl} = "NULL";
		} else {
			$self->{ttl} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{ttl});
}

sub retry
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{retry} = "NULL";
		} else {
			$self->{retry} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{retry});
}

sub expiry
{
	my $self = shift;
	
	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{expiry} = "NULL";
		} else {
			$self->{expiry} = int ($newvalue);
		}
		
		return 1;
	}

	return ($self->{expiry});
}

sub minimum
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		if ($newvalue eq "NULL") {
			$self->{minimum} = "NULL";
		} else {
			$self->{minimum} = int ($newvalue);
		}
		
		return 1;
	}
	
	return ($self->{minimum});
}

sub owner
{
	my $self = shift;

	if (@_) {
		my $newvalue = shift;

		$self->{owner} = $newvalue;
		
		return 1;
	}
		
	return ($self->{owner});
}

