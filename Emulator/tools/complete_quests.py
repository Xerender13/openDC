"""Finish story missions for a character that is not in the game: each quest is marked rewarded and its
reward given as the game service does it (quests.quest_reward: exp and level, Mito, reward items,
PLAYMODE 'QUEST'). By default the five Rookie Missions; --battle-tutorial also marks the battle
tutorial as cleared (PLAYMODE 'BATTLETUTORIAL', what the client's 0x104 does).

usage (from Emulator/): .venv/bin/python -m tools.complete_quests NAME [--count 5] [--battle-tutorial]
The character must be offline (kick it first: -m tools.gmctl kick NAME): the game keeps a loaded
character in memory and would not see the change.
"""
import argparse
import asyncio
import os

from dcemu.__main__ import HERE, load_config
from dcemu.native import context
from dcemu.native.data import Tables
from dcemu.native.db import Database
from dcemu.native.game import player, quests
from dcemu.native.game.items import add_money, new_item
from dcemu.native.game.progress import add_exp, play_mode
from dcemu.native.game.session import inc_play_mode


async def run(name, count, battle_tutorial):
    p = await player.load(name)
    if not p:
        raise SystemExit(f'no character {name!r}')
    c, t = p.char, context.data
    for table_idx, row in enumerate(t.quests[:count]):
        k = quests.find(p, table_idx)
        if k is not None and p.quests[k][1] == quests.REWARDED:
            print(f'{row[0]} {row[10]}: already done')
            continue
        if k is None:
            p.quests.append((table_idx, quests.REWARDED, 0, 0))
        else:
            p.quests[k] = (table_idx, quests.REWARDED, p.quests[k][2], p.quests[k][3])
        await quests.save(p, table_idx)
        exp, money = quests._n(row, 75), quests._n(row, 76)
        await add_exp(c, exp)
        if money:
            await add_money(c, money)
        await play_mode(c, 'QUEST', exp=exp, money=money)
        items = []
        for col in quests.REWARD_ITEM_COLS:
            iid = row[col].strip() if col < len(row) else ''
            info = t.item_info(t.item_index[iid]) if iid in t.item_index else None
            if info:
                items.append((await new_item(p, info, 1)).item_id)
        print(f'{row[0]} {row[10]}: +{exp} exp, +{money} Mito, items {items}')
    if battle_tutorial and not c.flags & player.BATTLE_TUTORIAL_DONE:
        await inc_play_mode(c, 'BATTLETUTORIAL', 1, 1)
        print('battle tutorial marked as cleared')
    print(f'{c.name}: level {c.level}, {c.exp} exp, {c.mito} Mito')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('name')
    ap.add_argument('--count', type=int, default=5, help='how many quests from the start of the story (5 = the Rookie Missions)')
    ap.add_argument('--battle-tutorial', action='store_true')
    ap.add_argument('-c', '--config', default=os.path.join(HERE, 'emulator.ini'))
    a = ap.parse_args()
    cp = load_config(a.config)
    d, n = cp['database'], cp['native']
    context.db = Database(d['host'], int(d['port']), d['user'], d['password'], d['name'], int(d['server_id']))
    context.data = Tables(os.path.join(HERE, n['data']), os.path.join(HERE, n['server_data']), os.path.join(HERE, n['admin_list']))
    asyncio.run(run(a.name, a.count, a.battle_tutorial))


if __name__ == '__main__':
    main()
