# $Id$

use HOSTDB;

package HOSTDB::Object;
@HOSTDB::Object::ISA = qw(HOSTDB);

=head1 NAME

HOSTDB::Object - Object super class. Inherits from HOSTDB but provides an empty init ().


=head1 SYNOPSIS

  use HOSTDB;

  my $hostdb = HOSTDB::DB->new (dsn => $dsn, db => $db, user = $user,
				password => $pw, debug = $debug);

=head1 DESCRIPTION

Nothing here for now.


=head1 EXPORT

None.

=head1 METHODS

None.


=cut



sub init
{


}

1;
__END__

=head1 AUTHOR

Fredrik Thulin <ft@it.su.se>, Stockholm University

=head1 SEE ALSO

L<HOSTDB>


=cut
