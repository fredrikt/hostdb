# $Id$
#
# The tables associated with hosts and DNS zone generation
#

CREATE TABLE host (
	id INT AUTO_INCREMENT NOT NULL,
	dhcpmode ENUM ('DYNAMIC', 'STATIC') DEFAULT 'STATIC' NOT NULL,
	dhcpstatus ENUM ('ENABLED', 'DISABLED') DEFAULT 'DISABLED' NOT NULL,
	mac CHAR(17),
	dnsmode ENUM ('A_AND_PTR', 'A') DEFAULT 'A_AND_PTR' NOT NULL,
	dnsstatus ENUM ('ENABLED', 'DISABLED') DEFAULT 'ENABLED' NOT NULL,
	hostname VARCHAR(255),
	dnszone VARCHAR(255),
	manual_dnszone ENUM ('Y', 'N') NOT NULL DEFAULT 'N',
	ip CHAR(15) NOT NULL,
	n_ip INT UNSIGNED NOT NULL,
	owner VARCHAR(255) NOT NULL,
	ttl INT,
	comment VARCHAR(255),
	partof INT,
	mac_address_ts DATETIME,
	client_id VARCHAR(255),
	options MEDIUMBLOB,
	profile VARCHAR(25) DEFAULT 'default' NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE zone (
	id INT AUTO_INCREMENT NOT NULL,
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
	owner VARCHAR(255) NOT NULL,
	PRIMARY KEY (id)
);

# the use of unsigned int for n_netaddr and n_netmask is not enough for IPv6.
# ipver in this table is only to think ahead - don\'t think this database and
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
	owner VARCHAR(255) NOT NULL,
	profilelist VARCHAR(255) DEFAULT 'default' NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE hostattribute (
	id INT AUTO_INCREMENT NOT NULL,
	hostid INT NOT NULL,
	v_key VARCHAR(250) NOT NULL,
	v_section VARCHAR(128) NOT NULL,
	v_type ENUM("string", "int", "blob") NOT NULL,
	v_string VARCHAR(255),
	v_int BIGINT,
	v_blob MEDIUMBLOB,
	lastmodified DATETIME,
	lastupdated DATETIME,
	PRIMARY KEY (id),
	UNIQUE (hostid, v_key, v_section)
);

CREATE TABLE hostalias (
	id INT AUTO_INCREMENT NOT NULL,
	hostid INT NOT NULL,
	hostname VARCHAR(255),
	ttl INT,
	dnszone VARCHAR(255),
	lastmodified DATETIME,
	lastupdated DATETIME,
	comment VARCHAR(255),
	PRIMARY KEY (id)
);


# this is an EXAMPLE grant command, you need to replace $database, $user, example.org and $password
GRANT select, insert, update, delete ON $database.* TO "$user"@"%.example.org" IDENTIFIED BY '$password';

# don\'t forget...
flush privileges;
