--
-- SFA database schema
--

SET client_encoding = 'UNICODE';

--------------------------------------------------------------------------------
-- Version
--------------------------------------------------------------------------------

-- Database version
CREATE TABLE sfa_db_version (
    version integer NOT NULL,
    subversion integer NOT NULL DEFAULT 0
) WITH OIDS;

-- the migration scripts do not use the major 'version' number
-- so 5.0 sets subversion at 100
-- in case your database misses the site and persons tags feature, 
-- you might wish to first upgrade to 4.3-rc16 before moving to some 5.0
-- or run the up script here
-- http://svn.planet-lab.org/svn/PLCAPI/branches/4.3/migrations/

INSERT INTO sfa_db_version (version, subversion) VALUES (1, 1);

--------------------------------------------------------------------------------
-- Aggregates and store procedures
--------------------------------------------------------------------------------

-- Like MySQL GROUP_CONCAT(), this function aggregates values into a
-- PostgreSQL array.
CREATE AGGREGATE array_accum (
    sfunc = array_append,
    basetype = anyelement,
    stype = anyarray,
    initcond = '{}'
);

-- Valid record types
CREATE TABLE record_types (
       record_type text PRIMARY KEY
) WITH OIDS;
INSERT INTO record_types (record_type) VALUES ('authority');
INSERT INTO record_types (record_type) VALUES ('authority+sa');
INSERT INTO record_types (record_type) VALUES ('authority+am');
INSERT INTO record_types (record_type) VALUES ('authority+sm');
INSERT INTO record_types (record_type) VALUES ('user');
INSERT INTO record_types (record_type) VALUES ('slice');
INSERT INTO record_types (record_type) VALUES ('node');


-- main table 
CREATE TABLE records ( 
    record_id serial PRIMARY KEY , 
    hrn text NOT NULL, 
    authority text NOT NULL, 
    peer_authority text, 
    gid text, 
    type text REFERENCES record_types, 
    pointer integer, 
    date_created timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    last_updated timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX sfa_hrn_ids on records (hrn);
CREATE INDEX sfa_type_ids on records (type);
CREATE INDEX sfa_authority_ids on records (authority);
CREATE INDEX sfa_peer_authority_ids on records (peer_authority);
CREATE INDEX sfa_pointer_ids on records (pointer);
