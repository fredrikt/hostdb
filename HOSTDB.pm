# $Id$
#

package HOSTDB;

use strict;
use DBI;
use vars qw($VERSION @ISA @EXPORT @EXPORT_OK);

require Exporter;
require AutoLoader;


@ISA = qw(Exporter);
# Items to export into callers namespace by default. Note: do not export
# names by default without a very good reason. Use EXPORT_OK instead.
# Do not simply export all your public functions/methods/constants.
@EXPORT = qw(
	
);
$VERSION = '0.01';

sub _debug_print;
sub _set_error;

# Preloaded methods go here.

# Autoload methods go after =cut, and are processed by the autosplit program.


=head1 NAME

HOSTDB - Perl extension to access host database.

=head1 SYNOPSIS

  use HOSTDB;


=head1 DESCRIPTION

The host database contains DNS and DHCP type host info, use this perl module
to access the data.

=head1 EXPORT

None.

=head1 METHODS

=cut



sub new
{
	my $self = shift;
	my $class = ref $self || $self;
	my %me = @_;
	my $this = bless \%me,$class;
	$this->init ($self);
	$this;
}

sub init
{
	my $self = shift;

	warn ("IN TOP LEVEL HOSTDB init()\n");
}


=head2 clean_hostname

	if (! $hostdb->clean_hostname ($hostname)) {
		print ("given hostname was invalid: $hostdb->{error}\n");
	} else {
		print ("new hostname: $hostname\n");
	}

	This function modified the variable passed to it, like chomp().

	It converts the hostname to lower case, strips any trailing dots
	and finally returns the result of valid_fqdn ($new_hostname).

=cut
sub clean_hostname
{
	my $self = shift;
	#my $new = lc ($_[0]);	# lowercase
	my $new = $_[0];	# don't lowercase for now, start doing this in the
				# future and also bulk change everything in database
	my $valid;

	$new =~ s/\.+$//o;	# strip trailing dots

	$valid = $self->valid_fqdn ("$new");
	
	if ($valid and ($new ne $_[0])) {
		$self->_debug_print ("changed '$_[0]' into '$new'");
		$_[0] = $new;
	}

	return $valid;
}


=head2 valid_fqdn

	$is_valid = $hostdb->valid_fqdn ($hostname);

	Checks with some regexps if $hostname is a valid FQDN host name.

=cut
sub valid_fqdn
{
	my $self = shift;
	my $hostname = shift;

	# do NOT clean_hostname() because that function actually uses this one

	# check first and last part separately
	my @hostname_parts = split (/\./, $hostname);
	my $illegal_chars;

	if ($#hostname_parts < 1) {
		$self->_debug_print ("hostname '$hostname' is incomplete");
		goto ERROR;
	}

	# first part (hostname) may NOT begin with a digit and may NOT
	# contain an underscore
	if ($hostname !~ /^[a-zA-Z0-9]/o) {
		$self->_debug_print ("hostname '$hostname' does not begin with an alphabetic character (a-zA-Z)");
		goto ERROR;
	}
	$illegal_chars = $hostname_parts[0];
	$illegal_chars =~ s/[a-zA-Z0-9\-]//og;
	if ($illegal_chars) {
		$self->_debug_print ("hostname part '$hostname_parts[0]' of FQDN '$hostname' contains illegal characters ($illegal_chars)");
		goto ERROR;
	}

	# check TLD, only letters and between 2 and 6 chars long
	# 2 is for 'se', 6 is 'museum'
	if ($hostname_parts[$#hostname_parts] !~ /^[a-zA-Z]{2,6}$/o) {
		$self->_debug_print ("TLD part '$hostname_parts[$#hostname_parts]' of FQDN '$hostname' is invalid (should be 2-6 characters and only alphabetic)");
		goto ERROR;
	}

	# check it all, a bit more relaxed than above (underscores allowed
	# for example).	
	$illegal_chars = $hostname;
	$illegal_chars =~ s/[a-zA-Z0-9\._-]//og;
	if ($illegal_chars) {
		$self->_debug_print ("'$hostname' has illegal characters in it ($illegal_chars)");
		goto ERROR;
	}

	return 1;
ERROR:
	$self->_set_error ("'$hostname' is not a valid FQDN");
	return 0;
}


=head2 clean_mac

	if (! $hostdb->clean_mac_address ($mac_address)) {
		print ("given mac address was invalid: $hostdb->{error}\n");
	} else {
		print ("new mac address: $mac_address\n");
	}

	This function modified the variable passed to it, like chomp().

	Accept a mac-address in any of these formats :

	00:2:b3:9a:89:df
	0002.b39a.89df

	and turn it into :

	00:02:b3:9a:89:df
	

=cut
sub clean_mac_address
{
	my $self = shift;
	my $new = lc ($_[0]);
	my @elements;
	my $valid;

	$new =~ s/[\.\-]/:/og;	# replace dots and dashes with colons
	
	if ($new =~ /^([\da-f]+):([\da-f]+):([\da-f]+)$/o) {
		# handle 0002.b39a.89df
		foreach my $tuple (hex ($1), hex ($2), hex ($3)) {
			push (@elements,
				sprintf ("%.2x:%.2x", ($tuple >> 8) & 0xff, $tuple & 0xff));
		}
		$new = join(":", @elements);
	} elsif ($new =~ /^([\da-f]{1,2}):([\da-f]{1,2}):([\da-f]{1,2}):([\da-f]{1,2}):([\da-f]{1,2}):([\da-f]{1,2})$/o) {
		# handle 00:2:b3:9a:89:df
		$new = sprintf("%.2x:%.2x:%.2x:%.2x:%.2x:%.2x", hex ($1), hex ($2), hex ($3), hex ($4), hex ($5), hex ($6));
	}

	$valid = $self->valid_mac_address ("$new");
	
	if ($valid and ($new ne $_[0])) {
		$self->_debug_print ("changed '$_[0]' into '$new'");
		$_[0] = $new;
	}

	return $valid;
}

=head2 valid_mac_address

	print("valid\n") if ($hostdb->valid_mac_address($mac);
	
	Checks if $mac is a mac address formatted exactly like this: 00:02:b3:9a:89:df
	
	To make other variants of mac addresses be formatted like the one above, use

	$hostdb->clean_mac_address ($mac);

=cut
sub valid_mac_address
{
	my $self = shift;
	my $mac = shift;

	if ($mac =~ /^[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}$/o) {
		return 1;
	}

	$self->_set_error ("Invalid mac address");
	return 0;
}


=head2 dump

	$hostdb->dump();
	
	Dumps all variables of the $hostdb object. Only for debugging.

=cut
sub dump
{
	my $self = shift;

	foreach my $k (sort keys %{$self}) {
		printf "%-20s:%s\n",$k,$self->{$k};
	}
}



####################################
# package HOSTDB private functions #
####################################


=head1 PACKAGE HOSTDB PRIVATE FUNCTIONS

	These functions should NEVER be called by a program using this class,
	but are documented here as well just for the sake of documentation.


=head2 _set_error

	$self->_set_error ("operation foo failed: bar");

	Sets internal error string.

=cut
sub _set_error
{
	my $self = shift;
	my @error = @_;

	$self->{error} = join (" ", @error);

	return undef;
}


=head2 _debug_print

	$self->_debug_print ("foo", "bar");

	Prints debug messages if $self->{debug} is true.

=cut
sub _debug_print
{
	my $self = shift;
	my @msg = @_;
	
	return if (! $self->{debug});

	my ($pack, $file, $line, $subname, $hasargs, $wantarray) = caller (1);
	if ($#msg > 0) {
		# multi line, print nice
		warn ("$subname() DEBUG START:\n	", join("\n	", @msg), "\nDEBUG END\n");
	} else {
		warn ("$subname() DEBUG: $msg[0]\n");
	}

	return undef;
}



##################################################################

package HOSTDB::DB;
@HOSTDB::DB::ISA = qw(HOSTDB);


sub init
{
	my $self = shift;

	$self->{_dbh} = DBI->connect ($self->{dsn}, $self->{user}, $self->{password}) or die "$DBI::errstr";

	$self->{_hostbyid} =		$self->{_dbh}->prepare ("SELECT * FROM $self->{db}.config WHERE id = ? ORDER BY id") or die "$DBI::errstr";
	$self->{_hostbypartof} =	$self->{_dbh}->prepare ("SELECT * FROM $self->{db}.config WHERE partof = ? ORDER BY id") or die "$DBI::errstr";
	$self->{_hostbymac} =		$self->{_dbh}->prepare ("SELECT * FROM $self->{db}.config WHERE mac = ? ORDER BY mac") or die "$DBI::errstr";
	$self->{_hostbyname} =		$self->{_dbh}->prepare ("SELECT * FROM $self->{db}.config WHERE hostname = ? ORDER BY hostname") or die "$DBI::errstr";
	$self->{_hostbyip} =		$self->{_dbh}->prepare ("SELECT * FROM $self->{db}.config WHERE ip = ? ORDER BY ip") or die "$DBI::errstr";

	#$self->{_hostbyip} =	$self->{_dbh}->prepare ("SELECT * FROM $self->{hostdb}->{db}.config WHERE ip = ? ORDER BY ip") 
	#	or die "$DBI::errstr";
	
	$self->set_user (getpwuid("$<"));
}

sub DESTROY
{
	my $self = shift;

	$self->{_dbh}->disconnect();
}


=head2 set_user

	$hostdb->set_user("foo");

	Set username to use in logging to 'foo' - default is UNIX username.

=cut
sub set_user
{
	my $self = shift;
	my $user = shift;

	$self->_debug_print ("Changing username from '$self->{localuser}' to $user");

	$self->{localuser} = $user;
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
	$o->init($self);
	
	return $o;
}


=head2 findhostbyname

	foreach my $matching_host_ref ($hostdb->findhostbyname ($searchhost)) {
		foreach my $host (@$matching_host_ref) {
			print ("$host->{hostname}	$host->{ip}\n");
		}
	}

	Returns a list of references to lists of host objects matching the search.

	This might sound complicated, but is needed if two hosts match the search :

	HOST1	IP 1.2.3.4	HOSTNAME min.it.su.se.

	HOST2	IP 2.3.4.5	HOSTNAME foo.it.su.se.
		IP 3.4.5.6	HOSTNAME min.it.su.se.

=cut
sub findhostbyname
{
	my $self = shift;
	my @res;

	$self->_debug_print ("Find host with name '$_[0]'");
	
	foreach my $host ($self->_find (_hostbyname => 'HOSTDB::Object::Host', $_[0])) {
		my @hostparts;
		my $superhost = $host;

		if ($host->{partof}) {
			$superhost = $self->findhostbyid ($host->{partof});
		}
		push (@hostparts, $superhost);
		
		# go look for more parts of this host
		foreach my $hostpart ($self->findhostbypartof ($superhost->{id})) {
			push (@hostparts, $hostpart);
		}
		
		push (@res, \@hostparts);
		$self->_debug_print ("Host " . ($#res + 1) . " in result set consists of " . ($#hostparts + 1) . " entrys");
	}
	
	# return all matching hosts
	$self->_debug_print ("Returning " . $#res + 1 . " references to hosts");
	return @res;
}


=head2 findhostbyip

	foreach my $host ($hostdb->findhostbyip ($searchhost)) {
		print ("$host->{ip}	$host->{hostname}\n");
	}

=cut
sub findhostbyip
{
	my $self = shift;

	$self->_debug_print ("Find host with IP '$_[0]'");
	
	$self->_find(_hostbyip => 'HOSTDB::Object::Host', $_[0]);
}

=head2 findhostbyid

	$host = $hostdb->findhostbyid ($id);
	
=cut
sub findhostbyid
{
	my $self = shift;

	$self->_debug_print ("Find host with id '$_[0]'");
	
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



########################################
# package HOSTDB::DB private functions #
########################################


=head1 PACKAGE HOSTDB::DB PRIVATE FUNCTIONS

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

	$sth->execute(@_) or die "$DBI::errstr";

	$self->_debug_print ("Got " . $sth->rows . " entry(s) when querying for '$_[0]' ($class)\n");

	my (@retval,$hr);
	while ($hr = $sth->fetchrow_hashref()) {
		my $o = bless $hr,$class;
		foreach my $k (keys %{$hr}) {
			# strip leading and trailing white space on all keys
			$hr->{$k} =~ s/^\s*(.*?)\s*$/$1/;
		}
		$o->init($self);
		push(@retval,$o);
	}
	$sth->finish();
	wantarray ? @retval : $retval[0];
}





##################################################################

package HOSTDB::Object;
@HOSTDB::Object::ISA = qw(HOSTDB);

sub init
{


}

##################################################################

package HOSTDB::Object::Host;
@HOSTDB::Object::Host::ISA = qw(HOSTDB::Object);

sub init
{
	my $self = shift;
	my $hostdb = shift;

	$hostdb->_debug_print ("creating object");

	if ($hostdb->{_dbh}) {
		$self->{_new_host} = $hostdb->{_dbh}->prepare ("INSERT INTO $hostdb->{db}.config (mac, hostname, ip, ttl, user, partof, reverse) VALUES (?, ?, ?, ?, ?, ?, ?)")
			or die "$DBI::errstr";
		$self->{_update_host} = $hostdb->{_dbh}->prepare ("UPDATE $hostdb->{db}.config SET mac = ?, hostname = ?, ip = ?, ttl = ?, user = ?, partof = ?, reverse = ? WHERE id = ?")
			or die "$DBI::errstr";

		$self->{_get_last_id} = $hostdb->{_dbh}->prepare ("SELECT LAST_INSERT_ID()")
			or die "$DBI::errstr";
	}
}

sub check_valid_ip
{
	my $self = shift;
	my $ip = shift;
	
	$self->_debug_print ("foo");

	return 1;
}

sub set_mac_address
{
	my $self = shift;
	my $mac = shift;
	
	return 0 if (! $self->clean_mac_address ($mac));

	$self->{mac} = $mac;
}

sub set_hostname
{
	my $self = shift;
	my $hostname = shift;
	
	return 0 if (! $self->clean_hostname ($hostname));

	$self->{hostname} = $hostname;
	
	return 1;
}

sub set_ip
{
	my $self = shift;
	my $ip = shift;
	
	return 0 if (! $self->check_valid_ip ($ip));

	# XXX CHECK IP
	# check if IP is
	#
	# 127.0.0.0/8
	# 0.0.0.0/8
	# 255.0.0.0/8
	# 172.16.0.0/12
	# 224.0.0.0/4
	#
	# and ideally the assigned test networks too
	#
	# (10.0.0.0/8 is IP telephones and 192.168.0.0/16 is used)
	#
		
	$self->{ip} = $ip;
	
	return 1;
}

sub set_ttl
{
	my $self = shift;
	my $ttl = shift;

	if ($ttl eq "NULL") {
		$self->{ttl} = "NULL";
	} else {
		$self->{ttl} = int ($ttl);
	}

	return 1;
}

sub set_user
{
	my $self = shift;
	my $user = shift;

	$self->{user} = $user;
	
	return 1;
}

sub set_partof
{
	my $self = shift;
	my $partof = shift;
	
	if ((int($partof) == 0) and ($partof ne "0")) {
		$self->set_error ("Invalid partof");
		return 0;
	}
	$self->{partof} = int($partof);

	return 1;
}

sub set_reverse
{
	my $self = shift;
	my $reverse = shift;
	
	if ($reverse =~ /^y/i or $reverse == 1) {
		$self->{reverse} = "Y";
	} elsif ($reverse =~ /^n/i or $reverse == 1) {
		$self->{reverse} = "N";
	} else {
		$self->set_error ("Invalid reverse format");
		return 0;
	}

	return 1;
}

sub commit
{
	my $self = shift;
	my $hostdb = shift;

	# if not explicitly told anything else, set reverse to Yes if
	# this is a primary host object (not partof another)
	$self->set_reverse ("Y") if (! defined ($self->{partof}) and ! defined ($self->{reverse}));

	# if TTL is 0, set it to NULL to use default TTL
	$self->{ttl} = "NULL" if (defined ($self->{ttl}) and $self->{ttl} <= 0);

	my $sth;
	if (defined ($self->{id}) and $self->{id} >= 0) {
		$sth = $self->{_update_host};
		$sth->execute ($self->{mac}, $self->{hostname}, $self->{ip},
			       $self->{ttl}, $self->{user}, $self->{partof},
			       $self->{reverse}, $self->{id})
			or die "$DBI::errstr";
		
		$sth->finish();
	} else {
		# this is a new entry

		$sth = $self->{_new_host};
		$sth->execute ($self->{mac}, $self->{hostname}, $self->{ip},
			       $self->{ttl}, $self->{user}, $self->{partof},
			       $self->{reverse})
			or die "$DBI::errstr";

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


package HOSTDB;

1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO
~
L<perl>.

=cut
