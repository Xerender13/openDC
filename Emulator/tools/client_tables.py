"""The 2011 client's effective tables: what the US client (nation 1) actually loads.

The client reads Data_US\\... (the US overlay) before Data\\..., and the patch packs
(Patch\\Patch.000-010) replace files of the archives. Archive entries are stored relative to the
archive, patch entries with the full path; both are mapped to full paths here:
    Data\\World\\data.agt   Data\\X.tdf   -> Data\\World\\Data\\X.tdf
    Data\\Init.agt         Init\\X.xlt   -> Data\\Init\\X.xlt
    Data_US\\World.agt     World\\data\\X -> Data_US\\World\\data\\X
    Data_US\\Init_us.agt   Init\\X.xlt   -> Data_US\\Init\\X.xlt
For a table name the newest US version wins (a patch over the archive), else the newest base one.

usage: client_tables.py <client dir> [name...]     list where each table comes from
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agt  # noqa: E402

PACKS = [  # (archive, prefix added to its entry names), lowest priority first
    ('Data/World/data.agt', 'Data\\World\\'),
    ('Data/Init.agt', 'Data\\'),
    ('Data_US/World.agt', 'Data_US\\'),
    ('Data_US/Init_us.agt', 'Data_US\\'),
]


class Client:
    def __init__(self, root):
        self.root = root
        self.files = {}           # lower-case full path -> (source, archive raw, entry)
        sources = [(os.path.join(root, a), p) for a, p in PACKS]
        patch_dir = os.path.join(root, 'Patch')
        if os.path.isdir(patch_dir):
            sources += [(os.path.join(patch_dir, f), '') for f in sorted(os.listdir(patch_dir))
                        if f.lower().startswith('patch.0')]
        for path, prefix in sources:
            if not os.path.exists(path):
                continue
            raw, entries = agt.index(path)
            for e in entries:
                full = prefix + e[0]
                self.files[full.lower()] = (os.path.relpath(path, root), raw, e)

    def find(self, name):
        """Full path of the effective version of a table (file name, any case), or None."""
        name = name.lower()
        hits = [p for p in self.files if p.rsplit('\\', 1)[-1] == name]
        us = [p for p in hits if p.startswith('data_us\\')]
        for group in (us, [p for p in hits if p not in us]):
            if group:
                # the latest source wins: patches are added after the archives, in order
                return max(group, key=lambda p: list(self.files).index(p))
        return None

    def source(self, name):
        p = self.find(name)
        return (p, self.files[p][0]) if p else (None, None)

    def read(self, name):
        p = self.find(name)
        if not p:
            raise FileNotFoundError(name)
        _, raw, entry = self.files[p]
        return agt.extract(raw, entry)


def main():
    c = Client(sys.argv[1])
    for n in sys.argv[2:] or ['ItemClient.tdf', 'UseItemClient.tdf', 'Assist_Client.tdf', 'VehicleList.xlt']:
        print(n, '->', *c.source(n))


if __name__ == '__main__':
    main()
