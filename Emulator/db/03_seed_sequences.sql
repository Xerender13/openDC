-- The id counters (character, message, image, event, item ...). The server only increments
-- them: an empty table gives every new sticker, image and item id 0 or -2.
IF NOT EXISTS (SELECT * FROM SKID_SEQUENCE_TB)
INSERT INTO SKID_SEQUENCE_TB (CHARACTER_SQ1, MSG_SQ1, IMAGE_SQ1, EVENT_SQ1, ITEM_SQ1, PREVENT_SQ1, LOG_SQ1)
VALUES (100000, 1, 100000, 1, 100000, 100000, 100)
GO
-- The server's row (emulator.ini [database] server_id = 100): SERVERPTICK is the hour clock set parts expire by
-- (setparts.current_tick advances it from LASTDATE); without the row it stays 0 and set parts never expire.
IF NOT EXISTS (SELECT * FROM SKID_SERVER_TB WHERE SERVERID = 100)
INSERT INTO SKID_SERVER_TB (SERVERID, SNAME, SERVERPTICK) VALUES (100, ' ', 0)
GO
