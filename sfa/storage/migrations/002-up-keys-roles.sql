----
-- the purpose of this migration is to enrich the proper SFA table 
-- so that the registry can perform reasonably in standalone mode,
-- i.e. without any underlying myplc
-- this is desirable in the perspective of providing a generic framework
-- for non myplc-based testbeds
-- prior to this change, the registry needed to inspect the myplc db in order
-- to retrieve keys and roles, so as to be able to make the right decisions in
-- terms of delivering credentials
----

--------------------------------------------------------------------------------
-- Authentication Keys
--------------------------------------------------------------------------------
-- Valid key types
CREATE TABLE key_types (
    key_type text PRIMARY KEY
) WITH OIDS;
INSERT INTO key_types (key_type) VALUES ('ssh');

-- Authentication keys
CREATE TABLE keys (
    key_id serial PRIMARY KEY,
    key_type text REFERENCES key_types NOT NULL,
    key text NOT NULL
) WITH OIDS;

-- attaching keys to records
CREATE TABLE record_key (
    record_id integer REFERENCES records NOT NULL,
    key_id integer REFERENCES keys PRIMARY KEY
) WITH OIDS;
CREATE INDEX record_key_record_id_idx ON record_key (record_id);

-- get all keys attached to one record
CREATE OR REPLACE VIEW record_keys AS
SELECT record_id,
array_accum(key_id) AS key_ids
FROM record_key
GROUP BY record_id;

-- a synthesis view for records
CREATE OR REPLACE VIEW view_records AS
SELECT
records.record_id,
records.hrn,
records.authority,
records.peer_authority,
records.gid,
records.type,
records.pointer,
records.date_created,
records.last_updated,
COALESCE((SELECT key_ids FROM record_keys WHERE record_keys.record_id = records.record_id), '{}') AS key_ids
FROM records;

------------------------------------------------------------
UPDATE sfa_db_version SET subversion = 2;
