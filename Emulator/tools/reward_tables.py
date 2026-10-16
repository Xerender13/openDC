"""Write Emulator/server_data/delivery_rewards.txt and Emulator/server_data/patrol_rewards.txt with a line for every delivery job x medal
and every patrol of the client's tables (ArbeitClient.tdf, Instant_Client.tdf), keeping the lines that already
name an item (and lines for '*'). The emulator reads the files itself (dcemu/native/game/rewards.py).

usage: python3 -m tools.reward_tables      (from Emulator/; run again after the client's tables change)
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from dcemu.native.data import Tables                                    # noqa: E402
from dcemu.native.game.instant import PATROL_TYPES                       # noqa: E402
from dcemu.native.game.rewards import DELIVERY_FILE, MEDAL_NAMES, PATROL_FILE  # noqa: E402

DELIVERY_HEAD = """\
# Item rewards for completing a delivery job, by medal (read by the emulator whenever this file changes).
#
# Columns (tab separated; '#' starts a comment):
#   job     ArbeitClient id (a_00001 ..), or * = every job
#   medal   gold / silver / bronze / none (slower than bronze), or * = every medal
#   item    an inventory item id (ItemClient / UseItemClient: parts, usable items; see the item catalog);
#           - = nothing
#   count   how many
#   the rest is not read (the job's title, its medal time limit in seconds)
# Add a line (copy one) to give more than one item. The delivery result shows the first item's name and icon;
# the others go to the inventory without a notice (the client's result message has room for one item).
# Example: a_00001	gold	i_n_00003	1	Pizza Delivery
# Written by tools/reward_tables.py (which keeps the lines that name an item).
#
# job	medal	item	count	title	time limit (s)
"""

PATROL_HEAD = """\
# Item rewards for completing a patrol (read by the emulator whenever this file changes).
#
# Columns (tab separated; '#' starts a comment):
#   patrol  Instant_Client row (TableIdx), or * = every patrol
#   item    an inventory item id (ItemClient / UseItemClient: parts, usable items; see the item catalog);
#           - = nothing
#   count   how many
#   the rest is not read (type, level range, posts to patrol, the giver's post)
# Add a line (copy one) to give more than one item. The patrol result lists up to 3 items (each shown once,
# whatever the count); more still go to the inventory.
# Example: 5	i_n_00003	1	move	4-1000	50	post_1st_00052
# Written by tools/reward_tables.py (which keeps the lines that name an item).
#
# patrol	item	count	type	levels	posts	giver's post
"""


def kept(path, keys):
    """The lines of an existing file that name an item: {key tuple: [lines]}."""
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.startswith('#'):
                continue
            f = line.rstrip('\r\n').split('\t')
            if len(f) > keys + 1 and f[keys].strip() not in ('', '-'):
                out.setdefault(tuple(x.strip() for x in f[:keys]), []).append(line.rstrip('\r\n'))
    return out


def main():
    t = Tables(os.path.join(HERE, 'server_data'), os.path.join(HERE, 'server_data', 'tables'))
    old = kept(DELIVERY_FILE, 2)
    lines = [v for k, vs in old.items() if '*' in k for v in vs]
    for r in t.jobs:
        for m, name in enumerate(MEDAL_NAMES):
            limit = r[30 + 3 * m].strip() if m < 3 and len(r) > 30 + 3 * m else ''
            lines += old.get((r[0], name)) or [f'{r[0]}\t{name}\t-\t0\t{r[4].strip()}\t{limit}']
    open(DELIVERY_FILE, 'w', encoding='utf-8').write(DELIVERY_HEAD + '\n'.join(lines) + '\n')
    print(f'{DELIVERY_FILE}: {len(t.jobs)} jobs x {len(MEDAL_NAMES)} medals')

    old = kept(PATROL_FILE, 1)
    lines = [v for k, vs in old.items() if '*' in k for v in vs]
    n = 0
    for i, r in enumerate(t.instants):
        if len(r) > 17 and r[10] in PATROL_TYPES:
            n += 1
            lines += old.get((str(i),)) or [f'{i}\t-\t0\t{r[10]}\t{r[1]}-{r[2]}\t{r[16]}\t{r[17]}']
    open(PATROL_FILE, 'w', encoding='utf-8').write(PATROL_HEAD + '\n'.join(lines) + '\n')
    print(f'{PATROL_FILE}: {n} patrols')


if __name__ == '__main__':
    main()
