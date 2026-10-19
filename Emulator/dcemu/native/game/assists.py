"""Assist effects the server applies itself (the client applies the driving ones from the item records' slots).

The 2011 client builds the current car's assist set (0x729330: the ten slots of every item on the car, the drift
items on it and the PassiveAssist ones) and applies most kinds to the car by itself: 0x70f970 (stop 1, qstart 2,
criticalcrash 3, untouchable 7, crashsaving 15, overturbo 18, bonusreal 19, bonusdamage 20, driftbooster 22, the
battle / field kinds ..) and the stat sum 0x720650 (bonusspeed 9 / bonusaccel 10 / bonuscrash 11 / bonusboost 12,
and partycrashup 8 / partyspeedup 16 into a second stat group). The kind numbers are the client's assist type list
(UTF-16 names at 0x93da44, 0x74 bytes each; 2008 AssistTypeStrToVar 0x59a3e0 has the same order).
It does nothing with saving 4, gage 5, chance 13, speedup 14 and exp 17: the 2008 server did them
(XiRealMatchStat::CalcAssist 0x59f0e0, from XiRealMatchStat::EnChantUpdate 0x59fe00 over the items on the car:
assist A and B of each, and an option's own assist (item types 6-10, XiStrItem.SetAssist)):
    saving 4   MitronEfficiency += value  (XiCsCharInfo::GetMitronEfficiency 0x5c2030; "Improves mileage by 1%")
    gage 5     MitronCapacity += value    (GetMitronCapacity 0x5c2060: capacity x (100 + bonus) / 100, the current car)
    chance 13  Drop += value              (parts drop chance %)
    speedup 14 AddSpeed += value          (the MPH converts, "Speed Up 6"; sent to the player in 0x2f8's own
                                           XiStrEnChantBonus @0x10, a float in 2011: client 0x489057 adds own +
                                           party AddSpeed x car +0x16c to car +0x928, the top speed (0x47f62b))
    exp 17     Exp += value x 0.01        (exp gained x (1 + Exp))
    partycrashup 8 / partyspeedup 16: the party bonus, every member's summed (BS_Party::EnChantUpdate 0x5d9860)
        and sent to the party as 0x2f9 PartyEnChantUpdate (XiStrEnChantBonus: Speed, Crash, Accel, Boost, AddSpeed
        (long), Drop, Exp, MitronCapacity, MitronEfficiency (float); 2011: 40 bytes, one u32 more, client 0x72a420).
Here: the same kinds from the same sources (convert.option_assist for an option's own assist; the drift items'
assist slots, records.VisualItem.assist_slots) for the car being driven:
  - chance -> licenses.drop_bonus (combo / traffic / chase drops), exp -> items.play_bonus, both in %.
  - speedup -> own_bonus: AddSpeed of the 0x2f8 StatUpdate (login.stat_frames); it was sent as 0 before
    (session 27: MPH converts did nothing).
  - gage / saving -> records.Car.fuel_bonus / mileage_bonus of the current car (Player.apply_paints): the capacity and
    efficiency the server sends (XiStrCarInfo, 0x425, 0x2d4) and keeps to (fuel bought, Mitron items, drive info).
    Efficiency is distance per Mitron (VehicleUpgrade V1 4.0 .. V9 0.2), so saving multiplies it up.
  - party: 0x2f9 to each member with the other members' party assists (field 0 speed, field 1 crash, the client's
    order in 0x720650): the 2011 client already counts its own (0x728700 / 0x720650), so they are left out *(guess)*.
"""
import struct
from collections import defaultdict

from .. import context

SERVER_KINDS = ('saving', 'gage', 'chance', 'exp', 'speedup', 'partyspeedup', 'partycrashup')
PASSIVE_CATEGORIES = (40, 41)        # drift items whose assist slots count in any state (client 0x72961f)

_by_index = None


def by_index():
    """Assist_Client.tdf row + 1 (the record slots' numbers) -> (kind, value)."""
    global _by_index
    if _by_index is None:
        from .convert import assists
        _by_index = {i: (kind, value) for i, kind, value in assists().values()}
    return _by_index


def car_assists(p):
    """-> [(kind, value)] of every assist on the car being driven (0x729330's sources)."""
    car = p.car
    if car is None:
        return []
    from .convert import assist_index, option_assist
    from .items import active
    t, rows, out = context.data, by_index(), []
    for it in p.items:
        if it.car_id != car.car_id or (it.state & 0xffff) != 1 or it.item_id.startswith('dock_'):
            continue
        for aid in (it.assist_a, it.assist_b, option_assist(it)):
            a = rows.get(assist_index(aid))
            if a:
                out.append(a)
    for v in p.vsitems:
        vis = t.visuals.get(v.table_idx)
        on_car = v.state == 1 and v.car_id == car.car_id
        if not vis or not active(v) or not (on_car or vis.category in PASSIVE_CATEGORIES):
            continue
        slots = struct.unpack_from('<10I', v.assist_slots(), 8)
        out += [rows[s] for s in slots if s in rows]
    return out


def totals(p):
    """-> {kind: summed value} of the server-side kinds on the car being driven."""
    out = defaultdict(float)
    for kind, value in car_assists(p):
        if kind in SERVER_KINDS:
            out[kind] += value
    return out


def own_bonus(p):
    """The player's own XiStrEnChantBonus for 0x2f8: AddSpeed = the car's speedup assists (see the module text)."""
    from .records import enchant_bonus
    return enchant_bonus(totals(p)['speedup'])


def party_bonus(session):
    """0x2f9 PartyEnChantUpdate for one member: the other members' partyspeedup / partycrashup (see the module text)."""
    from .records import BONUS_2011
    from .social import party_of
    speed = crash = 0.0
    party = party_of(session)
    for s in (party.members if party else ()):
        q = s.state.get('player')
        if s is session or not q:
            continue
        got = totals(q)
        speed, crash = speed + got['partyspeedup'], crash + got['partycrashup']
    return struct.pack('<ii', int(speed), int(crash)).ljust(BONUS_2011, b'\0')


def send_party(members):
    """0x2f9 to these party members (another member's car or items changed, a member joined or left)."""
    from ...wire import Frame
    from .login import send
    for s in members:
        if s.state.get('player'):
            send(s, Frame(0x2f9, party_bonus(s)))
