# $Id$
#

package HOSTDB;

use strict;
use DBI;
use Socket;
use vars qw($VERSION @ISA @EXPORT @EXPORT_OK);

use HOSTDB::Db;
use HOSTDB::Auth;
use HOSTDB::StdCGI;
use HOSTDB::Object::Host;
use HOSTDB::Object::HostAttribute;
use HOSTDB::Object::HostAlias;
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

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw);

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
	$this->{error} = '';
	$this;
}


sub init
{
	my $self = shift;
}


=head2 get_inifile

	my $hostdbini = Config::IniFiles->new (-file => HOSTDB::get_inifile ());

	The reason to use HOSTDB::get_inifile () instead of 
	$hostdb->get_inifile () is that you probably don\'t have a HOSTDB
	object yet.

=cut
sub get_inifile
{
    my $which = shift;
    my $fn;

    if (defined ($which)) {
	$which = lc ($which);
	if ($which eq 'jevent') {
	    if ($ENV{'HOSTDB_JEVENT_INIFILE'}) {
		$fn = $ENV{'HOSTDB_JEVENT_INIFILE'};
	    } else {
		$fn = '/etc/hostdb-jevent.ini';
	    }
	} else {
	    die ("$0: Unknown INI-file requested ('$which')");
	}
    } else {
	if ($ENV{'HOSTDB_INIFILE'}) {
	    $fn = $ENV{'HOSTDB_INIFILE'};
	} else {
	    $fn = '/etc/hostdb.ini';
	}
    }

    if (! -f $fn) {
	die ("$0: Config-file '$fn' does not exist");
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
	my $new = lc ($_[0]);	# lowercase
	my $valid;

	return 0 unless $new;

	$new =~ s/\.+$//o;	# strip trailing dots
	$new =~ s/^\s*(\S+)\s*$/$1/o;	# trim spaces

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

	return 0 unless $new;

	$new =~ s/\.+$//o;	# strip trailing dots
	$new =~ s/^\s*(\S+)\s*$/$1/o;	# trim spaces

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

	return 0 unless $hostname;

	# do NOT clean_hostname() because that function actually uses this one

	# check first and last part separately
	my @hostname_parts = split (/\./, $hostname);
	my $illegal_chars;

	# XXX is 'su.se' a valid FQDN if such an A record exists? For now we don't
	# call it valid. Go check some RFC or something.
	if ($#hostname_parts < 2) {
		$self->_debug_print ("hostname '$hostname' is incomplete");
		return 0;
	}

	if ($hostname =~ /\.\./) {
		$self->_debug_print ("hostname '$hostname' has empty label(s) (double dots)");
		return 0;
	}

	# first part (hostname) may NOT begin with a digit and may NOT
	# contain an underscore and may NOT be digits-only
	if ($hostname !~ /^[a-zA-Z0-9]/o) {
		$self->_debug_print ("hostname '$hostname' does not begin with an alphabetic character (a-zA-Z0-9)");
		return 0;
	}
	$illegal_chars = $hostname_parts[0];
	$illegal_chars =~ s/[a-zA-Z0-9\-]//og;
	if ($illegal_chars) {
		$self->_debug_print ("hostname part '$hostname_parts[0]' of FQDN '$hostname' contains illegal characters ($illegal_chars)");
		return 0;
	}
	if ($hostname_parts[0] =~ /^[0-9]+$/o) {
		$self->_debug_print ("First part of hostname '$hostname_parts[0]' may not be digits-only");
		return 0;
	}

	# check TLD, only letters and between 2 and 6 chars long
	# 2 is for 'se', 6 is 'museum'
	if ($hostname_parts[$#hostname_parts] !~ /^[a-zA-Z]{2,6}$/o) {
		$self->_debug_print ("TLD part '$hostname_parts[$#hostname_parts]' of FQDN '$hostname' is invalid (should be 2-6 characters and only alphabetic)");
		return 0;
	}

	# check it all, a bit more relaxed than above (underscores allowed
	# for example).	
	$illegal_chars = $hostname;
	$illegal_chars =~ s/[a-zA-Z0-9\._-]//og;
	if ($illegal_chars) {
		$self->_debug_print ("'$hostname' has illegal characters in it ($illegal_chars)");
		return 0;
	}

	$self->_debug_print ("'$hostname' is a valid FQDN");

	return 1;
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
		return 0;
	}

	if ($domainname =~ /\.\./) {
		$self->_debug_print ("domainname '$domainname' has empty label(s) (double dots)");
		return 0;
	}

	# XXX 4711.com is a valid domainname, this is really to not treat invalid
	# hostnames (4711.example.org) as valid domain names. should be fixed, but
	# I can't think of a really good solution right now. patches welcome.
	if ($domainname !~ /\.arpa$/ and
	    $domainname !~ /\.e164\.sunet\.se$/ and
	    $domainname_parts[0] =~ /^[0-9]+$/o) {
		$self->_debug_print ("First part of domainname '$domainname_parts[0]' may not be digits-only (in HOSTDB)");
		return 0;
	}

	# XXX is_valid.example.com is a valid domainname, but not a valid hostname.
	# this is really to avoid that clean_hostname treats that as a valid hostname,
	# since it might be a domain name. should be fixed, but I can't think of a
	# really good solution right now. patches welcome.
	if ($domainname_parts[0] =~ /_/o) {
		$self->_debug_print ("First part of domainname '$domainname_parts[0]' may not contain underscore (in HOSTDB)");
		return 0;
	}


	# check TLD, only letters and between 2 and 6 chars long
	# 2 is for 'se', 6 is 'museum'
	if ($domainname_parts[$#domainname_parts] !~ /^[a-zA-Z]{2,6}$/o) {
		$self->_debug_print ("TLD part '$domainname_parts[$#domainname_parts]' of domain name '$domainname' is invalid (should be 2-6 characters and only alphabetic)");
		return 0;
	}

	# check it all, a bit more relaxed than above (underscores allowed
	# for example).	
	my $illegal_chars = $domainname;
	$illegal_chars =~ s/[a-zA-Z0-9\._-]//og;
	# what is left are illegal chars
	if ($illegal_chars) {
		$self->_debug_print ("'$domainname' has illegal characters in it ($illegal_chars)");
		return 0;
	}

	$self->_debug_print ("'$domainname' is a valid domainname");
	return 1;
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
	$new =~ s/^\s*(\S+)\s*$/$1/o;	# trim spaces
	
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

	$valid = $self->is_valid_mac_address ($new);
	
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
		$self->_debug_print ("'$mac' is valid");
		return 1;
	}

	$self->_debug_print ("Invalid mac address '$mac'");
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

	if ($ip =~ /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/o) {
		my @ip = ($1, $2, $3, $4);

		return 1 if ($ip eq "0.0.0.0");
		
		if ($self->aton ($ip) > 0) {
			$self->_debug_print ("'$ip' is a valid IP");
			return 1;
		}
	}

	$self->_debug_print ("ip '$ip' is NOT a valid IP");

	return 0;
}


=head2 is_valid_profilename

	$is_valid = $hostdb->is_valid_profilename ($new_profile);

	Checks with some regexps if $new_profile is a valid host profile name.


=cut
sub is_valid_profilename
{
	my $self = shift;
	my $profilename = shift;

	my $illegal_chars = $profilename;
	$illegal_chars =~ s/[a-zA-Z0-9\._-]//og;
	# what is left are illegal chars
	if ($illegal_chars) {
		$self->_debug_print ("'$profilename' has illegal characters in it ($illegal_chars)");
		return 0;
	}

	$self->_debug_print ("'$profilename' is a valid profile name");
	return 1;
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


=head2 is_valid_htmlcolor

	XXX


=cut
sub is_valid_htmlcolor
{
	my $self = shift;
	my $in = shift;
	
	if ($in =~ /^#[0-9a-f]{6,6}$/i or $in =~ /^\w{1,25}$/) {
		$self->_debug_print ("$in is a valid htmlcolor");
		return 1 
	}

	$self->_debug_print ("$in is NOT a valid htmlcolor");
	return 0;
}


=head2 is_valid_username

	Checks that a single username is syntactically reasonable.


=cut
sub is_valid_username
{
	my $self = shift;
	my $in = lc (shift);
	
	if ($in =~ /^[a-z0-9_\.-]{1,20}$/) {
		$self->_debug_print ("$in is a valid username");
		return 1 
	}

	$self->_debug_print ("$in is NOT a valid username");
	return 0;
}


=head2 is_valid_nameserver_time

	Checks if the specified value is either a positive integer
	or a BIND9 syntax parseable value like 1w2d3h4m5s. Can also
	check that the result is within a specified range.

	my $valid = $hostdb->is_valid_nameserver_time ("1d");
	
	or (will return false)
	
	my $min = 5;
	my $max = 86400;	# 1 day
	my $valid = $hostdb->is_valid_nameserver_time ("1d1s", $min, $max);


=cut
sub is_valid_nameserver_time
{
	my $self = shift;
	my $in = lc (shift);
	my $min = shift;
	my $max = shift;	

	if ($in =~ /^0+$/ or ($in =~ /^\d+$/ and int ($in) > 0)) {
		$self->_debug_print ("$in is a valid nameserver time (all numeric)");
	
		if (defined ($min) and int ($in) < $min) {
			$self->_debug_print ("$in is less than specified minimum '$min'");
			return 0;
		}
		if (defined ($max) and int ($in) > $max) {
			$self->_debug_print ("$in is greater than specified maximum '$max'");
			return 0;
		}

		return 1;
	}

	my $seconds = $self->_nameserver_time_to_seconds ($in);

	if ($seconds > 0) {
		if (defined ($min) and $seconds < $min) {
			$self->_debug_print ("$in ($seconds seconds) is less than specified minimum '$min'");
			return 0;
		}
		if (defined ($max) and $seconds > $max) {
			$self->_debug_print ("$in ($seconds seconds) is greater than specified maximum '$max'");
			return 0;
		}

		$self->_debug_print ("$in is a valid nameserver time ($seconds seconds)");
		return 1;
	}

	$self->_debug_print ("$in is NOT a valid nameserver time ($seconds)");
	return 0;
}


=head2 html_links

	%links = $hostdb->html_links ($q);

	Fetches a bunch of links from the inifile of $hostdb.
	$q is a SUCGI object you have created.


=cut
sub html_links
{
	my $self = shift;
	my $q = shift;

	my $ini = $self->inifile ();
	my  %res;

	if (defined ($ini)) {
		foreach my $name ('showsubnet', 'deletehost', 'whois', 'home', 'netplan',
				  'modifyzone', 'modifysubnet', 'modifyhost', 'hostattributes',
				  'hostalias', 'deletehostalias') {
			if ($ini->val ('subnet', "${name}_uri")) {
				my $l = $ini->val ('subnet', "${name}_uri");
				if ($l =~ /\.html$/) {
					$res{$name} = $l;
				} else {
					$res{$name} = $q->state_url ($l);
				}
			}
		}
	}
	
	return %res;
}


=head2 unique_id

    Return a list of objects with unique id\'s. Should only be used on
    a list of the same type of objects, where id\'s are supposed to be
    unique.

    @uniqye_objects = HOSTDB::unique_id (@list_of_objects);


=cut
sub unique_id
{
    my %seen;
    my @in = @_;

    my @res;
    foreach my $o (@in) {
	my $id = $o->id ();
	if (defined ($id)) {
	    next if ($seen{$id});
	    push (@res, $o);
	    $seen{$id} = 1;
	}
    }

    return @res;
}


=head2 dump

	$hostdb->dump();
	
	Dumps all variables of the $hostdb object. Only for debugging.


=cut
sub dump
{
	my $self = shift;

	foreach my $k (sort keys %{$self}) {
		printf "%-20s %s\n", $k, defined($self->{$k})?$self->{$k}:"NULL";
	}
}



############################
# HOSTDB private functions #
############################


=head1 PRIVATE FUNCTIONS

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

	if (! defined ($_[0])) {
		$self->{error} = '';
	} else {
		$self->{error} = join (" ", @error);
		$self->_debug_print ("ERROR: $self->{error}");
	}

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


=head2 _nameserver_time_to_seconds

	$self->_nameserver_time_to_seconds ("1w2d3h4m5s");

	Returns number of seconds.

=cut
sub _nameserver_time_to_seconds
{
	my $self = shift;
	my $in = shift;

	# check for BIND9 time like 1w2d3h4m5s
	my $seconds = 0;
	if ($in =~ /^(\d+)w(.*)$/) {
		$seconds += int ($1) * (86400 * 7);
		$in = $2;
	}
	if ($in =~ /^(\d+)d(.*)$/) {
		$seconds += int ($1) * 86400;
		$in = $2;
	}
	if ($in =~ /^(\d+)h(.*)$/) {
		$seconds += int ($1) * 3600;
		$in = $2;
	}
	if ($in =~ /^(\d+)m(.*)$/) {
		$seconds += int ($1) * 60;
		$in = $2;
	}
	if ($in =~ /^\d+(s*)$/) {
		$seconds += int ($in);
		$in = '';
	}
	
	return -1 if ($in);

	return $seconds;
}


=head2 _format_datetime

	$self->_format_datetime ($string);

	Valid formats for setting are: yyyy-mm-dd hh:mm:ss
				       NOW
				       unixtime:nnnnnnnnnn

	Returns time in yyyy-mm-dd hh:mm:ss format. Suitable for
	mysql DATETIME columns.


=cut
sub _format_datetime
{
	my $self = shift;
	my $in = shift;

	if ($in =~ /^\d{2,4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}$/o) {
		return ($in);
	} elsif ($in eq "NOW" or $in eq "NOW()") {
		return ($self->_unixtime_to_datetime (time ()));
	} elsif ($in =~ /^unixtime:(\d+)$/oi) {
		return ($self->_unixtime_to_datetime ($1));
	} elsif ($in eq 'NULL') {
		return ('NULL');
	}

	return undef;
}

=head2 _unixtime_to_datetime

	Convert a unix time stamp to localtime () format yyyy-mm-dd hh:mm:ss

	$now_as_string = $self->_unixtime_to_datetime (time ());


=cut
sub _unixtime_to_datetime
{
	my $self = shift;
	my $time = shift;

	my ($sec, $min, $hour, $mday, $mon, $year, $yday, $isdst) = localtime ($time);
	
	$year += 1900;	# yes, this is Y2K safe (why do you even bother? this was written
			# in the year of 2002)
	$mon++;
	
	return (sprintf ("%.4d-%.2d-%.2d %.2d:%.2d:%.2d",
		$year, $mon, $mday, $hour, $min, $sec));
}



1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB::Db>,
L<HOSTDB::Host>, L<HOSTDB::Zone>, L<HOSTDB::Subnet>


=cut
