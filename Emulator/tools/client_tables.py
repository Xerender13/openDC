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
        for path, prefix in sources:
            if not os.path.exists(path):
                continue
            raw, entries = agt.index(path)
            for e in entries:
                full = prefix + e[0]
                self.files[full.lower()] = (os.path.relpath(path, root), raw, e)
        # Dev Ed ships empty archive stubs plus loose Init / World/Data tables. As the engine (NiFile::NiFile asks the
        # packs first, fopen only for what they lack: tools/pack_client.py), a loose file counts only when no archive
        # has it; patch packs take precedence over both.
        for parts in (('Data', 'Init'), ('Data', 'World', 'Data'),
                      ('Data_US', 'Init'), ('Data_US', 'World', 'Data')):
            path = self._directory(*parts)
            if path is None:
                continue
            for folder, dirs, files in os.walk(path):
                dirs.sort()
                for name in sorted(files):
                    if name.lower().endswith(('.xlt', '.tdf')):
                        relative = os.path.relpath(os.path.join(folder, name), root)
                        full = relative.replace(os.sep, '\\')
                        self.files.setdefault(full.lower(), (relative, None, (full,)))
        patch_dir = self._directory('Patch')
        if patch_dir:
            for name in sorted(os.listdir(patch_dir)):
                if not name.lower().startswith('patch.0'):
                    continue
                path = os.path.join(patch_dir, name)
                raw, entries = agt.index(path)
                for e in entries:
                    self.files[e[0].lower()] = (os.path.relpath(path, root), raw, e)

    def _directory(self, *parts):
        path = self.root
        for part in parts:
            if not os.path.isdir(path):
                return None
            found = next((n for n in sorted(os.listdir(path)) if n.lower() == part.lower()), None)
            if found is None:
                return None
            path = os.path.join(path, found)
        return path if os.path.isdir(path) else None

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
        return self.read_path(p)

    def read_path(self, path):
        source, raw, entry = self.files[path.lower()]
        if raw is None:
            with open(os.path.join(self.root, source), 'rb') as f:
                return f.read()
        return agt.extract(raw, entry)


def main():
    c = Client(sys.argv[1])
    for n in sys.argv[2:] or ['ItemClient.tdf', 'UseItemClient.tdf', 'Assist_Client.tdf', 'VehicleList.xlt']:
        print(n, '->', *c.source(n))


if __name__ == '__main__':
    main()
