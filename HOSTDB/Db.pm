# $Id$

use HOSTDB;
use Config::IniFiles;
use strict;

package HOSTDB::DB;
@HOSTDB::DB::ISA = qw(HOSTDB);


=head1 NAME

HOSTDB::Db - Database access routines.

=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw);

  or
  
  my $hostdb = HOSTDB::DB->new (ini => $inifile);

  or

  my $hostdb = HOSTDB::DB->new (inifilename => $filename);


=head1 DESCRIPTION

Database access routines.


=head1 EXPORT

None.

=head1 METHODS

=cut


sub init
{
	my $self = shift;

	if (defined ($self->{inifile})) {
		$self->{ini} = Config::IniFiles->new (-file => $self->{inifile});
			
		unless (defined ($self->{ini})) {
			die ("Could not create HOSTDB object, config file '$self->{inifile}");
		}
	}
		
	if (defined ($self->{ini})) {
		# db settings
		$self->{dsn} = $self->{ini}->val ('db', 'dsn') unless (defined ($self->{dsn}));
		$self->{db} = $self->{ini}->val ('db', 'database') unless (defined ($self->{db}));
		$self->{user} = $self->{ini}->val ('db', 'user') unless (defined ($self->{user}));
		$self->{password} = $self->{ini}->val ('db', 'password') unless (defined ($self->{password}));

		# other misc settings
		$self->{auth_ldap_server} = $self->{ini}->val ('auth', 'ldap_server') unless (defined ($self->{auth_ldap_server}));
		$self->{auth_admins} = $self->{ini}->val ('auth', 'admins') unless (defined ($self->{auth_admins}));
		unless (defined ($self->{dont_authorize})) {
			my $v = $self->{ini}->val ('auth', 'dont_authorize') || '';
			$self->{auth_disabled} = 'DISABLED' if ($v eq 'YES');
		}
	}

	if (defined ($self->{dsn})) {
		$self->{_dbh} = DBI->connect ($self->{dsn}, $self->{user}, $self->{password}) or die "$DBI::errstr";

		my $SELECT_host = "SELECT *, UNIX_TIMESTAMP(mac_address_ts) AS unix_mac_address_ts FROM $self->{db}.host";
		$self->{_hostbyid} =		$self->{_dbh}->prepare ("$SELECT_host WHERE id = ? ORDER BY id")			or die "$DBI::errstr";
		$self->{_hostbypartof} =	$self->{_dbh}->prepare ("$SELECT_host WHERE partof = ? ORDER BY id")			or die "$DBI::errstr";
		$self->{_hostbymac} =		$self->{_dbh}->prepare ("$SELECT_host WHERE mac = ? ORDER BY mac")			or die "$DBI::errstr";
		$self->{_hostbyname} =		$self->{_dbh}->prepare ("$SELECT_host WHERE hostname = ? ORDER BY hostname")		or die "$DBI::errstr";
		$self->{_hostbyzone} =		$self->{_dbh}->prepare ("$SELECT_host WHERE dnszone = ? ORDER BY hostname")		or die "$DBI::errstr";
		$self->{_hostbywildcardname} =	$self->{_dbh}->prepare ("$SELECT_host WHERE hostname LIKE ? ORDER BY hostname")		or die "$DBI::errstr";
		$self->{_hostbyip} =		$self->{_dbh}->prepare ("$SELECT_host WHERE ip = ? ORDER BY n_ip")			or die "$DBI::errstr";
		$self->{_hostbyiprange} =	$self->{_dbh}->prepare ("$SELECT_host WHERE n_ip >= ? AND n_ip <= ? ORDER BY n_ip")	or die "$DBI::errstr";
		$self->{_allhosts} =		$self->{_dbh}->prepare ("$SELECT_host ORDER BY id")					or die "$DBI::errstr";

		my $SELECT_zone = "SELECT * FROM $self->{db}.zone";
		$self->{_zonebyname} =		$self->{_dbh}->prepare ("$SELECT_zone WHERE zonename = ? ORDER BY zonename")		or die "$DBI::errstr";
		$self->{_allzones} =		$self->{_dbh}->prepare ("$SELECT_zone ORDER BY zonename")				or die "$DBI::errstr";

		my $SELECT_subnet = "SELECT * FROM $self->{db}.subnet";
		$self->{_subnet} =			$self->{_dbh}->prepare ("$SELECT_subnet WHERE netaddr = ? AND slashnotation = ? ORDER BY n_netaddr")	or die "$DBI::errstr";
		$self->{_subnet_longer_prefix} =	$self->{_dbh}->prepare ("$SELECT_subnet WHERE n_netaddr >= ? AND n_netaddr <= ? ORDER BY n_netaddr")	or die "$DBI::errstr";
		$self->{_subnet_closest_match} =	$self->{_dbh}->prepare ("$SELECT_subnet WHERE n_netaddr <= ? AND n_broadcast >= ? ORDER BY n_netaddr DESC LIMIT 1")		or die "$DBI::errstr";
	} else {
		$self->_debug_print ("DSN not provided, not connecting to database.");
	}

	$self->user (getpwuid("$<"));

	# create an HOSTDB::Auth to be used for authorization
	$self->{auth} = $self->create_auth (authorization => $self->{auth_disabled});
	$self->auth->ldap_server ($self->{auth_ldap_server}) if (defined ($self->{auth_ldap_server}));
	$self->auth->admin_list (split (',', $self->{auth_admins})) if (defined ($self->{auth_admins}));
	$self->{auth_ldap_server} = undef;
	$self->{auth_admins} = undef;
	$self->{auth_disabled} = undef;

	return 1;
}

sub DESTROY
{
	my $self = shift;

	$self->{_dbh}->disconnect() if (defined ($self->{_dbh}));
}


####################
# PUBLIC FUNCTIONS #
####################


=head1 PUBLIC FUNCTIONS


=head2 inifile

	my $inifile = $hostdb->inifile ();
	
	Fetch the Config::IniFiles object that was supplied to the new ()
	function (this is a read only function).
	
=cut
sub inifile
{
	my $self = shift;

	if (defined ($_[0])) {
		$self->_set_error ("inifile () is a read only function");
		
		return undef;
	}
	
	return $self->{ini};
}
	

=head2 user

	$hostdb->user("foo") or die("error");

	Set username to use in logging to 'foo' - default is UNIX username.

	-

	$user = $hostdb->user ();

	Get username used in logging.

	

=cut
sub user
{
	my $self = shift;

	if (@_) {
		my $user = shift;

		if (defined ($self->{localuser})) {
			$self->_debug_print ("Changing username from '$self->{localuser}' to $user");
		} else {
			$self->_debug_print ("Initializing username: $user");
		}
		$self->{localuser} = $user;

		return 1;
	}

	return ($self->{localuser});
}


=head2 auth

	Read only function. Returns the HOSTDB::Auth object created at init ().
	
	XXX write example.

=cut
sub auth
{
	my $self = shift;

	if (@_) {
		$self->_set_error ("auth () is a read-only function");
		return undef;
	}

	return ($self->{auth});
}

=head2 create_host

	$host = $hostdb->create_host();

	Gets you a brand new HOSTDB::Object::Host object.


=cut
sub create_host
{
	my $self = shift;
	
	my $o = bless {},"HOSTDB::Object::Host";
	$o->{hostdb} = $self;
	$o->{debug} = $self->{debug};
	$self->_set_error ($o->{error}), return undef if (! $o->init());
	
	return ($o);
}


=head2 create_zone

	$zone = $hostdb->create_zone();

	Gets you a brand new HOSTDB::Object::Zone object.


=cut
sub create_zone
{
	my $self = shift;
	
	my $o = bless {},"HOSTDB::Object::Zone";
	$o->{hostdb} = $self;
	$o->{debug} = $self->{debug};
	$self->_set_error ($o->{error}), return undef if (! $o->init());
	
	return ($o);
}


=head2 create_subnet

	$subnet = $hostdb->create_subnet(4, "10.1.2.0/24");

	Gets you a brand new HOSTDB::Object::Subnet object.

	The 4 is IPv4. This is just planning ahead, IPv6 is not implemented
	in a number of places.


=cut
sub create_subnet
{
	my $self = shift;
	my $ipver = shift;
	my $subnet = shift;

	my $o = bless {},"HOSTDB::Object::Subnet";
	$o->{hostdb} = $self;
	$o->{ipver} = $ipver;
	$o->{subnet} = $subnet;
	$o->{debug} = $self->{debug};

	$self->_set_error ($o->{error}), return undef if (! $o->init());
	
	return ($o);
}


=head2 create_auth

	$auth = $hostdb->create_auth();

	Gets you a brand new HOSTDB::Auth object.


=cut
sub create_auth
{
	my $self = shift;
	
	my $o = bless {}, "HOSTDB::Auth";
	$o->{ini} = $self->{ini};
	$o->{debug} = $self->{debug};
	$self->_set_error ($o->{error}), return undef if (! $o->init());
	
	return ($o);
}


=head2 findhostbyname

	foreach my $host ($hostdb->findhostbyname ($searchhost)) {
		printf ("%-5s %-20s %s\n", $host->id (), $host->ip (), $host->hostname ());
	}


=cut
sub findhostbyname
{
	my $self = shift;
	my @res;

	$self->_debug_print ("Find host with name '$_[0]'");
	
	if (! $self->is_valid_fqdn ($_[0]) and ! $self->is_valid_domainname ($_[0])) {
		$self->_set_error ("findhostbyname: '$_[0]' is not a valid FQDN or domain name");
		return undef;
	}
	
	$self->_find(_hostbyname => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbyzone

	foreach my $host ($hostdb->findhostbyzone ($zone)) {
		printf ("%-5s %-20s %s\n", $host->id (), $host->hostname (), $host->zone);
	}


=cut
sub findhostbyzone
{
	my $self = shift;
	my @res;

	$self->_debug_print ("Find host with zone '$_[0]'");
	
	if (! $self->is_valid_domainname ($_[0])) {
		$self->_set_error ("findhostbyname: '$_[0]' is not a valid domain name");
		return undef;
	}
	
	$self->_find(_hostbyzone => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbyip

	foreach my $host ($hostdb->findhostbyip ($searchhost)) {
		printf ("%-20s %s\n", $host->ip (), $host->hostname ());
	}


=cut
sub findhostbyip
{
	my $self = shift;

	$self->_debug_print ("Find host with IP '$_[0]'");
	
	if (! $self->is_valid_ip ($_[0])) {
		$self->_set_error ("findhostbyip: '$_[0]' is not a valid IP address");
		return undef;
	}
	
	$self->_find(_hostbyip => 'HOSTDB::Object::Host', $_[0]);
}

=head2 findhostbywildcardname

	foreach my $host ($hostdb->findhostbywildcardname ($searchhost)) {
		printf ("%-20s %s\n", $host->ip (), $host->hostname ());
	}


=cut
sub findhostbywildcardname
{
	my $self = shift;

	$self->_debug_print ("Find host with hostname LIKE '$_[0]'");
	
	$self->_find(_hostbywildcardname => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbymac

	foreach my $host ($hostdb->findhostbymac ($searchhost)) {
		printf ("%-20s %-20s %s\n", $host->mac(), $host->ip (),
			$host->hostname ());
	}


=cut
sub findhostbymac
{
	my $self = shift;

	$self->_debug_print ("Find host with MAC address '$_[0]'");
	
	if (! $self->is_valid_mac_address ($_[0])) {
		$self->_set_error ("findhostbymac: '$_[0]' is not a valid MAC address");
		return undef;
	}
	
	$self->_find(_hostbymac => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbyid

	$host = $hostdb->findhostbyid ($id);
	print ($host->hostname ());


=cut
sub findhostbyid
{
	my $self = shift;

	$self->_debug_print ("Find host with id '$_[0]'");
	
	if ($_[0] !~ /^\d+$/) {
		$self->_set_error ("findhostbyid: '$_[0]' is not a valid ID");
		return undef;
	}
	
	$self->_find(_hostbyid => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbypartof

	blah


=cut
sub findhostbypartof
{
	my $self = shift;

	$self->_debug_print ("Find host partof '$_[0]'");
	
	$self->_find(_hostbypartof => 'HOSTDB::Object::Host', $_[0]);
}


=head2 findhostbyiprange

	@hosts = $hostdb->findhostbyiprange ($subnet->netaddr (), $subnet->broadcast ());

	Returns all hosts in a subnet


=cut
sub findhostbyiprange
{
	my $self = shift;

	$self->_debug_print ("Find host by IP range '$_[0]' -> '$_[1]'");
	
	if (! $self->is_valid_ip ($_[0])) {
		$self->_set_error ("findhostbyiprange: start-ip '$_[0]' is not a valid IP adress");
		return undef;
	}
	
	if (! $self->is_valid_ip ($_[1])) {
		$self->_set_error ("findhostbyiprange: stop-ip '$_[1]' is not a valid IP adress");
		return undef;
	}
	
	$self->_find(_hostbyiprange => 'HOSTDB::Object::Host',
			$self->aton ($_[0]), $self->aton ($_[1]));
}


=head2 findallhosts

	@hosts = $hostdb->findallhosts ();


=cut
sub findallhosts
{
	my $self = shift;

	$self->_debug_print ("Find all hosts");
	
	$self->_find(_allhosts => 'HOSTDB::Object::Host');
}


=head2 findhost

	Tries to find one or more host objects, with or without a clearly defined
	datatype for the search criteria.

	@hosts = $hostdb->findhost ("guess", $user_input);

	or

	@hosts = $hostdb->findhost ("IP", $ip);

	Valid datatypes (not case sensitive) are :
		Guess
		IP
		FQDN
		MAC
		ZONE

	Note that 'Guess' can't recognize a zone (it looks for FQDN).

=cut
sub findhost
{
	my $self = shift;
	my $datatype = lc (shift);
	my $search_for = shift;

	$self->_set_error ('');
	
	if ($datatype eq "guess" or ! $datatype) {
		my $t = $search_for;
		if ($self->clean_mac_address ($t)) {
			$search_for = $t;
			$datatype = 'mac';
		} elsif ($search_for =~ /^[+-]*(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.in-addr\.arpa\.*$/i) {
			$datatype = 'ip';
			$search_for = "$4.$3.$2.$1";
		} elsif ($self->is_valid_ip ($search_for)) {
			$datatype = 'ip';
		} elsif ($self->clean_hostname ($t)) {
			$datatype = 'fqdn';
			$search_for = $t;
		} elsif ($search_for =~ /^\d+$/) { 
			$datatype = 'id';
		} else {
			$self->_set_error ("findhost () search failed: could not guess data type of '$search_for'");
			return undef;
		}
	}

	my @host_refs;
			
	if ($datatype eq 'ip') {
		if ($self->is_valid_ip ($search_for)) {
			@host_refs = $self->findhostbyip ($search_for);
		} else {
			$self->_set_error ("findhost () search failed: '$search_for' is not a valid IP address");
			return undef;
		}
	} elsif ($datatype eq 'fqdn') {
		my $t = $search_for;
		if ($self->clean_hostname ($t)) {
			$search_for = $t;
			@host_refs = $self->findhostbyname ($search_for);
		} else {
			$self->_set_error ("findhost () search failed: '$search_for' is not a valid FQDN");
			return undef;
		}
	} elsif ($datatype eq 'mac') {
		my $t = $search_for;
		if ($self->clean_mac_address ($t)) {
			$search_for = $t;
			@host_refs = $self->findhostbymac ($search_for);
		} else {
			$self->_set_error ("findhost () search failed: '$search_for' is not a valid MAC address");
			return undef;
		}
	} elsif ($datatype eq 'id') {
		if ($search_for =~ /^\d+$/) { 
			@host_refs = $self->findhostbyid ($search_for);
		} else {
			$self->_set_error ("findhost () search failed: '$search_for' is not a valid ID");
			return undef;
		}
	} else {
		$self->_set_error ("findhost () search failed: don't recognize whois datatype '$datatype'");
		return undef;
	}
	
	return @host_refs;
}


=head2 findzonebyname

	$zone = $hostdb->findzonebyname ($zonename);


=cut
sub findzonebyname
{
	my $self = shift;

	$self->_debug_print ("Find zone with name '$_[0]'");
	
	$self->_find(_zonebyname => 'HOSTDB::Object::Zone', $_[0]);
}


=head2 findallzones

	@zones = $hostdb->findallzones ();


=cut
sub findallzones
{
	my $self = shift;

	$self->_debug_print ("Find all zones");
	
	$self->_find(_allzones => 'HOSTDB::Object::Zone');
}


=head2 findzonebyhostname

	Finds the zone for the specified hostname.

	$zone = $hostdb->findzonebyhostname ('min.it.su.se');


=cut
sub findzonebyhostname
{
	my $self = shift;
	my $hostname = shift;

	my $checkzone = $hostname;

	return undef if (! $self->clean_hostname ($hostname));

	while ($checkzone) {
		my $zone = $self->findzonebyname ($checkzone);
		if (defined ($zone)) {
			# we have a match
			$self->_debug_print ("Hostname $hostname belongs to zone $checkzone");
			return $zone;
		}

		last if (index ($checkzone, '.') == -1);

		# strip up to and including the first dot (min.it.su.se -> it.su.se)
		$checkzone =~ s/^.+?\.(.*)/$1/;
	}

	$self->_debug_print ("No zone found for hostname '$hostname'");
	return undef;

}


=head2 findzonenamebyhostname

	This is another variant of findzonebyhostname (). The
	difference is that this function does not fetch data from
	the database, but just provides the logic. You provide
	the hostname and zonenames.


	foreach my $zone ($hostdb->findallzones ()) {
		push (@all_zonenames, $zone->zonename ());
	} 
	printf "Host %s belongs to zone %s\n", $hostname,
		$hostdb->findzonenamebyhostname ($hostname, @all_zonenames);


=cut
sub findzonenamebyhostname
{
	my $self = shift;
	my $hostname = shift;
	my @all_zones = @_;

	my $checkzone = $hostname;

	return undef if (! $self->clean_hostname ($hostname));

	while ($checkzone) {
		if (grep (/^$checkzone$/, @all_zones)) {
			# we have a match
			$self->_debug_print ("Hostname $hostname belongs to zone $checkzone");
			return $checkzone;
		}

		last if (index ($checkzone, '.') == -1);

		# strip up to and including the first dot (min.it.su.se -> it.su.se)
		$checkzone =~ s/^.+?\.(.*)/$1/;
	}

	$self->_debug_print ("No zonename found for hostname '$hostname' in list supplied to findzonenamebyhostname ()");
	return undef;
}


=head2 findsubnet

	$subnet = $hostdb->findsubnet("192.168.1.1/24");

	Finds a subnet exactly matching what you asked for.


=cut
sub findsubnet
{
	my $self = shift;

	$self->_debug_print ("Find subnet '$_[0]'");

	my ($netaddr, $slash) = split('/', $_[0]);

	$self->_find(_subnet => 'HOSTDB::Object::Subnet', $netaddr, $slash);
}


=head2 findsubnetclosestmatch

	$subnet = $hostdb->findsubnetclosestmatch("192.168.1.1");

	Finds the most specific subnet for the IP you supplied


=cut
sub findsubnetclosestmatch
{
	my $self = shift;

	$self->_debug_print ("Find subnet for IP '$_[0]'");

	$self->_find(_subnet_closest_match => 'HOSTDB::Object::Subnet',
		     $self->aton ($_[0]), $self->aton ($_[0]));
}


=head2 findsubnetlongerprefix

	$subnet = $hostdb->findsubnetlongerprefix("130.237.0.0/16");

	Finds all subnets inside the supernet you supply


=cut
sub findsubnetlongerprefix
{
	my $self = shift;
	my $supernet = shift;

	$self->_debug_print ("Find all subnets inside '$supernet'");

	my ($netaddr, $slash) = split('/', $supernet);
	my $broadcast = $self->get_broadcast ($supernet);

	$self->_find(_subnet_longer_prefix => 'HOSTDB::Object::Subnet',
		$self->aton ($netaddr), $self->aton ($broadcast));
}


#####################
# PRIVATE FUNCTIONS #
#####################


=head1 PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.


=head2 _find

	$self->_find(_hostbyname => 'HOSTDB::Object::Host', 'min.it.su.se');

	Executes the pre-prepared SQL query _hostbyname, returns one or many
	HOSTDB::Object::Host object.

	If in scalar context, returns just the first record - otherwise an array.	

=cut
sub _find
{
	my $self = shift;
	my $key = shift;
	my $class = shift;
	my $sth = $self->{$key};

	unless (defined ($sth)) {
		die ("SQL statement undefined, have you provied a DSN?\n");
	}
	
	$sth->execute(@_) or die "$DBI::errstr";

	if (defined ($self->{debug}) and $self->{debug} > 0) {
		my @t;
		
		# make list of query arguments suitable for debugging
		my $t2;
		foreach $t2 (@_) {
			push (@t, "'$t2'");
		}
		
		$self->_debug_print ("Got " . $sth->rows . " entry(s) when querying for " .
			join(", ", @t) . " ($class)\n");
	}

	my (@retval,$hr);
	while ($hr = $sth->fetchrow_hashref()) {
		my $o = bless $hr,$class;
		foreach my $k (keys %{$hr}) {
			# strip leading and trailing white space on all keys
			$hr->{$k} =~ s/^\s*(.*?)\s*$/$1/ if (defined ($hr->{$k}));
		}
		$o->{hostdb} = $self;
		$o->{debug} = $self->{debug};
		$o->init();
		push(@retval,$o);
	}
	$sth->finish();
	wantarray ? @retval : $retval[0];
}




1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
