# $Id$
#

package HOSTDB;

use strict;
use DBI;
use Socket;
use vars qw($VERSION @ISA @EXPORT @EXPORT_OK);

use HOSTDB::Db;
use HOSTDB::Object::Host;
use HOSTDB::Object::Zone;
use HOSTDB::Object::Subnet;

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

The host database contains DNS, subnet and DHCP type host info, use this perl module
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

=head2 get_inifile

	my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());

	The reason to use HOSTDB::get_inifile () instead of 
	$hostdb->get_inifile () is that you probably don't have a HOSTDB
	object yet.

=cut
sub get_inifile
{
	my $fn = "/etc/hostdb.ini";

	if (! -f $fn) {
		die ("$0: Config-file $fn does not exist");
	}

	return ($fn);
}

=head2 clean_hostname

	if (! $hostdb->clean_hostname ($hostname)) {
		print ("given hostname was invalid: $hostdb->{error}\n");
	} else {
		print ("new hostname: $hostname\n");
	}

	This function modified the variable passed to it, like chomp().

	It converts the hostname to lower case, strips any trailing dots
	and finally returns the result of is_valid_fqdn ($new_hostname).

=cut
sub clean_hostname
{
	my $self = shift;
	#my $new = lc ($_[0]);	# lowercase
	my $new = $_[0];	# don't lowercase for now, start doing this in the
				# future and also bulk change everything in database
	my $valid;

	$new =~ s/\.+$//o;	# strip trailing dots

	$valid = $self->is_valid_fqdn ($new) || $self->is_valid_domainname ($new);

	if ($valid and ($new ne $_[0])) {
		$self->_debug_print ("changed '$_[0]' into '$new'");
		$_[0] = $new;
	}

	return ($valid);
}


=head2 clean_domainname

	if (! $hostdb->clean_domainname ($zonename)) {
		print ("given zonename was invalid: $hostdb->{error}\n");
	} else {
		print ("new zonename: $zonename\n");
	}

	This function modified the variable passed to it, like chomp().

	It converts the zonename to lower case, strips any trailing dots
	and finally returns the result of is_valid_domainname ($new_zonename).

=cut
sub clean_domainname
{
	my $self = shift;
	my $new = lc ($_[0]);	# lowercase
	my $valid;

	$new =~ s/\.+$//o;	# strip trailing dots

	$valid = $self->is_valid_domainname ("$new");
	
	if ($valid and ($new ne $_[0])) {
		$self->_debug_print ("changed '$_[0]' into '$new'");
		$_[0] = $new;
	}

	return ($valid);
}


=head2 is_valid_fqdn

	$is_valid = $hostdb->is_valid_fqdn ($hostname);

	Checks with some regexps if $hostname is a valid FQDN host name.

=cut
sub is_valid_fqdn
{
	my $self = shift;
	my $hostname = shift;

	# do NOT clean_hostname() because that function actually uses this one

	# check first and last part separately
	my @hostname_parts = split (/\./, $hostname);
	my $illegal_chars;

	# XXX is 'su.se' a valid FQDN if such an A record exists? For now we don't
	# call it valid. Go check some RFC or something.
	if ($#hostname_parts < 2) {
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


=head2 is_valid_domainname

	$is_valid = $hostdb->is_valid_domainname ($zonename);

	Checks with some regexps if $zonename is a valid domain name.
	This is nearly the same thing as is_valid_fqdn but a bit more relaxed.

=cut
sub is_valid_domainname
{
	my $self = shift;
	my $domainname = shift;

	# do NOT clean_domainname() because that function actually uses this one

	my @domainname_parts = split (/\./, $domainname);

	if ($#domainname_parts < 1) {
		$self->_debug_print ("domainname '$domainname' is incomplete");
		goto ERROR;
	}

	# check TLD, only letters and between 2 and 6 chars long
	# 2 is for 'se', 6 is 'museum'
	if ($domainname_parts[$#domainname_parts] !~ /^[a-zA-Z]{2,6}$/o) {
		$self->_debug_print ("TLD part '$domainname_parts[$#domainname_parts]' of domain name '$domainname' is invalid (should be 2-6 characters and only alphabetic)");
		goto ERROR;
	}

	# check it all, a bit more relaxed than above (underscores allowed
	# for example).	
	my $illegal_chars = $domainname;
	$illegal_chars =~ s/[a-zA-Z0-9\._-]//og;
	# what is left are illegal chars
	if ($illegal_chars) {
		$self->_debug_print ("'$domainname' has illegal characters in it ($illegal_chars)");
		goto ERROR;
	}

	return 1;
ERROR:
	$self->_set_error ("'$domainname' is not a valid domain name");
	return 0;
}


=head2 clean_mac_address

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

	$valid = $self->is_valid_mac_address ("$new");
	
	if ($valid and ($new ne $_[0])) {
		$self->_debug_print ("changed '$_[0]' into '$new'");
		$_[0] = $new;
	}

	return ($valid);
}

=head2 is_valid_mac_address

	print("valid\n") if ($hostdb->is_valid_mac_address($mac);
	
	Checks if $mac is a mac address formatted exactly like this: 00:02:b3:9a:89:df
	
	To make other variants of mac addresses be formatted like the one above, use

	$hostdb->clean_mac_address ($mac);

=cut
sub is_valid_mac_address
{
	my $self = shift;
	my $mac = shift;

	if ($mac =~ /^[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}:[\da-f]{2,2}$/o) {
		return 1;
	}

	$self->_set_error ("Invalid mac address");
	return 0;
}


=head2 is_valid_subnet

	if (! $hostdb->is_valid_subnet ("130.237.0.0/16")) {
		die ("The world is going under, 130.237.0.0/16 " .
		     "is no longer a valid subnet!\n");
	}

	Check if a subnet is valid.


=cut
sub is_valid_subnet
{
	my $self = shift;
	my $subnet = shift;
	
	$self->_debug_print ("subnet '$subnet'");

	#if ($subnet !~ /^$IP_REGEXP\/$SLASH_REGEXP^/) {
	if ($subnet !~ /^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/(\d{1,2})$/) {
		$self->_debug_print ("invalid subnet '$subnet'");
		return 0;
	}
	
	my $netaddr = $1;
	my $slash = $2;

	if (! $self->aton ($netaddr)) {
		$self->_debug_print ("invalid netaddr '$netaddr'");
		return 0;
	}

	# XXX is /32 really a valid subnet? isn't that a host?	
	if ($slash < 0 or $slash > 32) {
		$self->_debug_print ("invalid slash '$slash'");
		return 0;
	}
	
	if ($self->get_netaddr ($subnet) ne $netaddr) {
		$self->_set_error ("$subnet is invalid (there are bits in $netaddr outside of mask " .
			$self->slashtonetmask ($slash) . ")");

		$self->_debug_print ("invalid subnet $subnet - netaddr different from calculated (" .
			$self->get_netaddr ($subnet) . ")");

		return 0;
	}

	$self->_debug_print ("$subnet is valid");

	return 1;
}


=head2 is_valid_ip

	die ("Invalid IP '$user_input'\n") if (! $hostdb->is_valid_ip ($user_input));

	Do some checking to determine if this is a valid IP address or not.
	

=cut
sub is_valid_ip
{
	my $self = shift;
	my $ip = shift;
	
	# XXX this routine needs some serious thought... it is not
	# exactly self explanatory and even I don't remember the reasoning
	# any more

	$self->_debug_print ("ip '$ip'");

	if ($ip =~ /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/o) {
		my @ip = ($1, $2, $3, $4);

		return 1 if ($ip eq "0.0.0.0");
		
		if ($self->aton ($ip) > 0) {
			$self->_debug_print ("is a valid IP");
			return 1;
		}
	}

	return 0;
}


=head2 aton

	$n_ip = $hostdb->ntoa($ip);

	Returns the IP address in binary data representation.
	Just a wrapper for inet_aton().


=cut
sub aton
{
	my $self = shift;
	my $val = shift;

	return (unpack ('N', Socket::inet_aton ($val)));
}


=head2 ntoa

	$ip = $hostdb->ntoa($n_ip);

	Returns the IP address in ascii representation.
	Just a wrapper for inet_ntoa().


=cut
sub ntoa
{
	my $self = shift;
	my $val = shift;
	
	return (Socket::inet_ntoa (pack ('N', $val)));
}


=head2 slashtonetmask

	$netmask = $hostdb->slashtonetmask("26");

	Returns the slash notation for the specified netmask
	(255.255.255.192 in the example)


=cut
sub slashtonetmask
{
	my $self = shift;
	my $slash = shift;

	if ($slash < 0 or $slash > 32) {
		$self->_set_error ("slash '$slash' invalid for IPv4"); # and IPv6 don't use netmasks
		return undef;
	}

	return ("0.0.0.0") if ($slash == 0);
	return ("255.255.255.255") if ($slash == 32);
	
	return ($self->ntoa (-(1 << (32 - $slash))));
}


=head2 netmasktoslash

	$slashnotation = $hostdb->netmasktoslash("255.255.255.192");

	Returns the slash notation for the specified netmask
	(26 in the example)


=cut
sub netmasktoslash
{
	my $self = shift;
	my $netmask = $self->aton(shift);

	my $slash = 0;

	my $t;
	for $t (0..3) {
		my $o = ($netmask >> ($t * 8)) & 0xff;
		
		while ($o) {
			$slash++ if ($o & 1);
			
			$o = $o >> 1;
		}
	}

	return ($slash);
}

=head2 get_num_addresses

	$slash = 24;
	$numhosts = $hostdb->get_num_addresses ($slash);
	
	Returns the number of addresses in a network of size $slash
	(255 in the example)


=cut
sub get_num_addresses
{
	my $self = shift;
	my $slash = shift;
	
	# XXX make unsigned
	return (int (1 << (32 - $slash)));
}


=head2 get_netaddr

	$netaddr = $hostdb->get_netaddr ("192.168.100.4/24");

	Returns the net address of the IP and subnet you specified
	(192.168.100.0 in the example)


=cut
sub get_netaddr
{
	my $self = shift;
	my $subnet = shift;
	
	my ($netaddr, $slash) = split('/', $subnet);
	
	return ($self->ntoa ($self->aton ($netaddr) & $self->aton ($self->slashtonetmask ($slash))));

}


=head2 get_broadcast

	$broadcast = $hostdb->get_broadcast ("192.168.100.4/24");

	Returns the broadcast address of the IP and subnet you specified
	(192.168.100.255 in the example)


=cut
sub get_broadcast
{
	my $self = shift;
	my $subnet = shift;
	
	my ($netaddr, $slash) = split('/', $subnet);
	
	return ($self->ntoa ($self->aton ($self->get_netaddr ($subnet)) + $self->get_num_addresses ($slash) - 1));
}


=head2 dump

	$hostdb->dump();
	
	Dumps all variables of the $hostdb object. Only for debugging.

=cut
sub dump
{
	my $self = shift;

	foreach my $k (sort keys %{$self}) {
		printf "%-20s %s\n",$k,$self->{$k};
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



1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO
~
L<perl>.

=cut
