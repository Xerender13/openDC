-- The 2008 server's stored procedures the emulator calls, as PostgreSQL functions (session 42). Same names in lower
-- case; the SQL Server OUTPUT parameter is the return value. Applied after the tables.

-- A new car for a character: its next car id (NEXTCAR + 1; NUMCAR + 1), or -1 when the character does not exist.
CREATE OR REPLACE FUNCTION pc_skid_createcar(serverid_in numeric, cid_in numeric, cname_in varchar, cartype_in numeric,
    carcolor_in numeric, cargrade_in numeric, auctioncnt_in numeric, mitron_in numeric, km_in numeric)
RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE carid numeric;
BEGIN
  UPDATE skid_character_tb SET nextcar = nextcar + 1, numcar = numcar + 1
    WHERE serverid = serverid_in AND cid = cid_in RETURNING nextcar INTO carid;
  IF coalesce(carid, 0) > 0 THEN
    INSERT INTO skid_car_tb(serverid, cid, cname, carid, cartype, color, nupgrade, auctioncnt, mitron, km, rating)
      VALUES (serverid_in, cid_in, cname_in, carid, cartype_in, carcolor_in, cargrade_in, auctioncnt_in, mitron_in,
              km_in, 5000);
    RETURN carid;
  END IF;
  RETURN -1;
END $$;

-- A new inventory item; the character's PARTINVENIDX follows it.
CREATE OR REPLACE FUNCTION pc_skid_insertitem(serverid_in numeric, cid_in numeric, cname_in varchar, gid_in numeric,
    carid_in numeric, invenidx_in numeric, itemid_in varchar, stacknum_in numeric, random_in numeric, state_in numeric,
    upgrade_in numeric, belonging_in numeric, assista_in varchar, assistb_in varchar, ctime_in numeric)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO skid_item_tb(serverid, cid, cname, gid, carid, invenidx, itemid, stacknum, nrandom, state, nupgrade,
                           belonging, assist_a, assist_b, ctime)
    VALUES (serverid_in, cid_in, cname_in, gid_in, carid_in, invenidx_in, itemid_in, stacknum_in, random_in, state_in,
            upgrade_in, belonging_in, assista_in, assistb_in, ctime_in);
  UPDATE skid_character_tb SET partinvenidx = invenidx_in WHERE serverid = serverid_in AND cid = cid_in;
END $$;
