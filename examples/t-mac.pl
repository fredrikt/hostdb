#!/usr/bin/perl
#
# $Id$
#
# script to test the clean_mac_address() function of HOSTDB.
#

use strict;
#use lib 'blib/lib';
use HOSTDB;

my @M = @ARGV;

if ($#M == -1) {
	print ("Using default mac address '2:b39a:89dF'.\n");
	push (@M, "2:b39a:89dF");
}

foreach my $mac (sort @M) {
	my $valid = HOSTDB::clean_mac_address($mac);

	print ("MAC address $mac is " . ($valid == 1 ? "":"NOT ") . "valid\n");
}
