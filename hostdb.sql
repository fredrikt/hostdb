# $Id$
#
# The tables associated with hosts and DNS zone generation
#

CREATE TABLE host (
	id INT AUTO_INCREMENT NOT NULL,
	dynamic ENUM('Y', 'N') DEFAULT 'N',
	mac CHAR(17),
	hostname VARCHAR(255) NOT NULL,
	ip CHAR(15) NOT NULL,
	n_ip INT UNSIGNED NOT NULL,
	owner VARCHAR(255) NOT NULL,
	ttl INT,
	user VARCHAR(255),
	partof INT,
	reverse ENUM('Y', 'N') DEFAULT 'N',
	last_modified TIMESTAMP,
	mac_address_ts TIMESTAMP,
	client_id VARCHAR(255),
	options MEDIUMBLOB,
	PRIMARY KEY (id)
);

CREATE TABLE zone (
	zonename VARCHAR(255) NOT NULL,
	delegated ENUM ('Y', 'N') NOT NULL DEFAULT 'N',
	default_ttl INT,
	ttl INT,
	serial INT NOT NULL,
	mname VARCHAR(255),
	rname VARCHAR(255),
	refresh INT,
	retry INT,
	expiry INT,
	minimum INT,
	owner VARCHAR(255),
	PRIMARY KEY (zonename)
);

# the use of unsigned int for n_netaddr and n_netmask is not enough for IPv6.
# ipver in this table is only to think ahead - don't think this database and
# scripts associated with it works with IPv6.
CREATE TABLE subnet (
	id INT AUTO_INCREMENT NOT NULL,
	ipver TINYINT UNSIGNED NOT NULL,
	netaddr	CHAR(20) NOT NULL,
	slashnotation TINYINT UNSIGNED NOT NULL,
	netmask CHAR(20) NOT NULL,
	broadcast CHAR(20) NOT NULL,
	addresses INT NOT NULL,
	description VARCHAR(255),
	short_description VARCHAR(255),
	n_netaddr INT UNSIGNED NOT NULL,
	n_netmask INT UNSIGNED NOT NULL,
	n_broadcast INT UNSIGNED NOT NULL,
	htmlcolor CHAR(20),
	dhcpconfig MEDIUMBLOB,
	PRIMARY KEY (id)
);

# this is an EXAMPLE grant command, you need to replace $database, $user, example.org and $password
GRANT select, insert, update, delete ON $database.* TO "$user"@"%.example.org" IDENTIFIED BY '$password';

# don't forget...
flush privileges;
