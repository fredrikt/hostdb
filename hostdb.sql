# $Id$
#
# The tables associated with hosts and DNS zone generation
#

CREATE TABLE config (
        id INT AUTO_INCREMENT NOT NULL,
        mac CHAR(17),
        hostname VARCHAR(255) NOT NULL,
        ip CHAR(15) NOT NULL,
        owner VARCHAR(255) NOT NULL,
        ttl INT,
        user VARCHAR(255),
        partof INT,
        reverse ENUM('Y', 'N') DEFAULT 'N',
        client_id VARCHAR(255),
        options MEDIUMBLOB,
        PRIMARY KEY (id)
);

CREATE TABLE zone (
        zonename VARCHAR(255) NOT NULL,
        serial INT NOT NULL,
	refresh INT,
	retry INT,
	expiry INT,
	minimum INT,
        owner VARCHAR(255),
        PRIMARY KEY (zonename)
);

CREATE TABLE subnet (
	netaddr	CHAR(20) NOT NULL,
	slashnotation TINYINT UNSIGNED NOT NULL,
	subnet CHAR(20) NOT NULL,
	description VARCHAR(255),
	short_description VARCHAR(255),
	n_netaddr INT NOT NULL,
	n_netmask INT NOT NULL,
	htmlcolor CHAR(20),
	dhcpconfig MEDIUMBLOB,
	PRIMARY KEY (netaddr)
);

# this is an EXAMPLE grant command, you need to replace $database, $user, example.org and $password
GRANT select, insert, update, delete ON $database.* TO "$user"@"%.example.org" IDENTIFIED BY '$password';

# don't forget...
flush privileges;
