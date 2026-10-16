"""Experience, levels and play-mode records, shared by the rewards (quests, part-time jobs, combos, races).

XiCsCharInfo::CalcExperience 0x5d8f80: exp is added, the level follows the exp table (LevelServer.tdf:
data.Tables.exp_bounds), and the character is saved (BS_GameDB::UpdateCharInfo: NLEVEL, NEXP). The
2008 server's Send_LevelUp only tells party members; the player sees the new level in the reward's
level / exp fields (the client plays the level-up when they differ, e.g. 0x410 handler 0x516910).
"""
from .. import context

CHAR_EXP_SQL = "UPDATE SKID_CHARACTER_TB SET NLEVEL=%s, NEXP=%s WHERE SERVERID=%s AND CID=%s"
PLAY_MODE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), TRYCNT=TRYCNT+%s, WINCNT=WINCNT+%s, NEXP=NEXP+%s, GAMEMONEY=GAMEMONEY+%s
  WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),%s,%s,0,0,%s,%s,0,0,%s)"""
MAX_LEVEL = 200


async def add_exp(c, exp):
    """Character c gains exp; its level, exp_base and exp_next follow. -> True if the level went up."""
    t = context.data
    old = c.level
    c.exp += exp
    while c.level < MAX_LEVEL:
        base, nxt = t.exp_bounds(c.level)
        if nxt <= base or c.exp < nxt:
            break
        c.level += 1
    c.exp_base, c.exp_next = t.exp_bounds(c.level)
    db = context.db
    await db.execute(CHAR_EXP_SQL, (c.level, c.exp, db.server_id, c.cid))
    return c.level != old


async def play_mode(c, mode, tries=1, wins=1, exp=0, money=0):
    db = context.db
    await db.execute(PLAY_MODE_SQL, (tries, wins, exp, money, db.server_id, c.cid, mode,
                                     db.server_id, c.cid, c.name, mode, tries, wins, exp, money, c.member))
