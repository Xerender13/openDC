"""Item rewards for completing deliveries and patrols: Emulator/server_data/delivery_rewards.txt and Emulator/server_data/patrol_rewards.txt
(user, 2026-10-14: a table per kind, every job for every medal and every patrol, with an item count; the client's
tables have no item rewards for either, the 2008 server's delivery item groups were server-side only).

Both files are tab separated, '#' starts a comment; read again whenever a file changes (no restart needed).
  delivery_rewards.txt: job (ArbeitClient id, a_00001.., or * = every job), medal (gold / silver / bronze / none,
      or * = every medal), item, count, then text columns that are not read (the job's title)
  patrol_rewards.txt: patrol (Instant_Client TableIdx, or * = every patrol), item, count, then text columns
An item is an inventory item id (ItemClient / UseItemClient: parts, usable items); '-' or count 0 = nothing. Several
lines for the same job / medal or patrol give several items. tools/reward_tables.py writes the files with a line
for every job x medal and every patrol (keeping the lines that have an item).
"""
import os

from .. import context

ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
DELIVERY_FILE = os.path.normpath(os.path.join(ROOT, 'server_data', 'delivery_rewards.txt'))
PATROL_FILE = os.path.normpath(os.path.join(ROOT, 'server_data', 'patrol_rewards.txt'))
MEDAL_NAMES = ('gold', 'silver', 'bronze', 'none')      # jobs.MEDALS order
_cache = {}                                             # path -> (mtime, rows)


def read_rows(path, keys):
    """The lines of a reward file with an item: [(key..., item id, count)] (cached until the file changes)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    rows = []
    try:
        for n, line in enumerate(open(path, encoding='utf-8'), 1):
            f = [x.strip() for x in line.split('#')[0].rstrip('\r\n').split('\t')]
            if len(f) < keys + 2 or not f[0]:
                continue
            item, count = f[keys], f[keys + 1]
            if item in ('', '-') or not count.lstrip('-').isdigit() or int(count) <= 0:
                continue
            if context.data and item not in context.data.item_index:
                print(f'rewards: {path}:{n}: unknown item {item!r} (ItemClient / UseItemClient id)', flush=True)
                continue
            rows.append((*f[:keys], item, int(count)))
    except (OSError, UnicodeDecodeError) as e:
        print(f'rewards: {path}: {e}', flush=True)
    _cache[path] = (mtime, rows)
    return rows


def delivery_rewards(job_id, medal):
    """[(item id, count)] for a job (ArbeitClient id) and a jobs.MEDALS index."""
    name = MEDAL_NAMES[medal]
    return [(item, count) for job, m, item, count in read_rows(DELIVERY_FILE, 2)
            if job in ('*', job_id) and m.lower() in ('*', name)]


def patrol_rewards(table_idx):
    """[(item id, count)] for a patrol (Instant_Client TableIdx)."""
    return [(item, count) for patrol, item, count in read_rows(PATROL_FILE, 1) if patrol in ('*', str(table_idx))]


async def give(p, rewards):
    """Gives the items -> (Gains with the changed inventory items, [(ItemInfo, count)] given)."""
    from .driftuse import Gains, give_item
    t, gains, given = context.data, Gains(), []
    for item, count in rewards:
        if item not in t.item_index:
            continue
        await give_item(p, item, count, gains)
        given.append((t.item_info(t.item_index[item]), count))
    return gains, given
