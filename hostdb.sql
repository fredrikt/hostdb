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
        user VARCHAR(255),
        partof INT,
        reverse ENUM('Y', 'N') DEFAULT 'N',
        client_id VARCHAR(255),
        options MEDIUMBLOB,
        PRIMARY KEY (id)
);

CREATE TABLE zone (
        name VARCHAR(255) NOT NULL,
        serial INT NOT NULL,
        owner VARCHAR(255),
        PRIMARY KEY (name)
);

# this is an EXAMPLE grant command, you need to replace $database, $user, example.org and $password
GRANT select, insert, update, delete ON $database.* TO "$user"@"%.example.org" IDENTIFIED BY '$password';
