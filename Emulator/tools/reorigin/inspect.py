"""Read-only Origin feasibility inventory; requires a separately UPX-unpacked research copy.

python -m tools.reorigin.inspect --client '/home/deck/Drift City Origin/Client' \
  --unpacked /tmp/dcemu-origin-research/origin-unpacked.exe --out /tmp/origin-inventory.json
Does not launch the client, contact game servers, unpack executables, or change client files.
Packet names/IDs alone do not establish payload compatibility. Archive indexing is streamed
and bounded: never feed Origin archives to the old default-key reader before selecting its key.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

from tools import agt, port2016


class Image:
    def __init__(self, path):
        self.path, self.data = path, path.read_bytes()
        b = self.data
        pe = struct.unpack_from('<I', b, 0x3c)[0]
        if b[pe:pe+4] != b'PE\0\0':
            raise ValueError('expected a PE image')
        self.timestamp = struct.unpack_from('<I', b, pe+8)[0]
        opt = pe+24
        self.base = struct.unpack_from('<I', b, opt+28)[0]
        count = struct.unpack_from('<H', b, pe+6)[0]
        size = struct.unpack_from('<H', b, pe+20)[0]
        self.sections = []
        for i in range(count):
            at = opt+size+i*40
            name = b[at:at+8].rstrip(b'\0').decode('ascii', errors='replace')
            _, rva, raw_size, raw_at = struct.unpack_from('<4I', b, at+8)
            self.sections.append((name, self.base+rva, raw_at, raw_size))

    def offset(self, addr):
        for _, va, off, size in self.sections:
            if va <= addr < va+size:
                return addr-va+off
        return None

    def cstring(self, addr):
        off = self.offset(addr)
        if off is None:
            return ''
        end = self.data.find(b'\0', off, off+160)
        return self.data[off:end].decode('ascii', errors='replace') if end >= 0 else ''

    def handlers(self):
        text = next(s for s in self.sections if s[0] == '.text')
        _, va, off, size = text
        result = {}
        pattern = rb'\x68(.{4})\x68(.{4})(\x6a.|\x68....)\x8b\xce\xe8(.{4})'
        for m in re.finditer(pattern, self.data[off:off+size], re.S):
            name, handler = struct.unpack('<II', m[1]+m[2])
            name = self.cstring(name)
            if not name.startswith('Cmd_'):
                continue
            kind = int.from_bytes(m[3][1:], 'little')
            if hex(kind) in result:
                raise ValueError(f'duplicate registration: {kind:#x}')
            result[hex(kind)] = {'name': name, 'handler': hex(handler),
                                 'registration': hex(va+m.start())}
        return result


def archive_tables(client, image):
    # Bind the key to readable bytes from this supplied binary rather than changing agt.KEY globally.
    hits = list(re.finditer(re.escape(agt.KEY[:16]), image.data))
    if len(hits) != 1:
        raise ValueError('archive key anchor is not unique')
    key = image.data[hits[0].start():hits[0].start()+len(agt.KEY)]

    def decode(data, offset):
        return bytes(x ^ key[(offset+i) % len(key)] for i, x in enumerate(data))

    entries, counts = {}, {}
    sources = [(client/'Data/World/data.agt', 'data\\world\\'),
               (client/'Data/Init.agt', 'data\\')]
    sources += [(p, '') for p in sorted((client/'Patch').glob('patch.0*'))]
    for path, prefix in sources:
        with path.open('rb') as f:
            header = f.read(32)
            if header[:8] != b'NayaPack':
                raise ValueError(f'bad pack header: {path.name}')
            count = struct.unpack_from('<I', header, 16)[0]
            if count > 10000:
                raise ValueError('unexpected archive entry count')
            for _ in range(count):
                pos = f.tell()
                hp, chunks, size, length = struct.unpack('<4i', decode(f.read(16), pos))
                if not (0 < length < 512 and 0 <= hp < path.stat().st_size
                        and 0 <= chunks < 100000 and 0 <= size < 512*1024*1024):
                    raise ValueError(f'invalid archive index: {path.name} at {pos:#x}')
                pos = f.tell()
                name = (prefix+decode(f.read(length), pos).decode('latin1')).lower()
                entries.pop(name, None)  # newest effective source, including duplicate paths
                entries[name] = (path, hp, chunks, size)
            counts[str(path.relative_to(client))] = count
    names = ('VehicleList.xlt', 'VehicleUpgrade.xlt', 'ItemClient.tdf', 'UseItemClient.tdf',
             'GlobalContent.xlt', 'License.xlt', 'Assist_Client.tdf', 'QuestClient.tdf')
    tables = {}
    for name in names:
        hits = [e for e in entries if e.rsplit('\\', 1)[-1] == name.lower()]
        if not hits:
            tables[name] = {'missing': True}
            continue
        path, hp, chunks, size = entries[hits[-1]]
        with path.open('rb') as f:
            f.seek(hp)
            lengths = struct.unpack('<'+str(chunks)+'H', decode(f.read(chunks*2), hp))
            data = bytearray()
            for length in lengths:
                pos = f.tell()
                data += zlib.decompressobj().decompress(decode(f.read(length), pos))
            data = bytes(data[:size])
        if len(data) != size:
            raise ValueError(f'incomplete table: {name}')
        rows = ([s.split('\t') for s in port2016.xlt_lines(data)] if name.endswith('.xlt')
                else port2016._tdf_rows(data))
        tables[name] = {'source': str(path.relative_to(client)), 'bytes': len(data),
                        'rows': len(rows), 'column_counts': dict(Counter(len(r) for r in rows))}
    return {'key_file_offset': hex(image.data.find(key)),
            'key_changes_from_legacy': [{'offset': i, 'legacy': a, 'origin': b}
                                        for i, (a, b) in enumerate(zip(agt.KEY, key)) if a != b],
            'archive_entries': counts, 'tables': tables}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--unpacked', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    image = Image(args.unpacked)
    handlers = image.handlers()
    legacy_path = Path(__file__).resolve().parents[1]/'re2016/handlers_2016.json'
    legacy = json.loads(legacy_path.read_text())
    shared = handlers.keys() & legacy.keys()
    result = {'original_sha256': hashlib.sha256((args.client/'driftcity.exe').read_bytes()).hexdigest(),
              'unpacked_sha256': hashlib.sha256(image.data).hexdigest(),
              'pe_timestamp': image.timestamp, 'sections': image.sections, 'handlers': handlers,
              'shared_with_2016': len(shared), 'missing_2016': sorted(legacy.keys()-handlers.keys()),
              'new_handlers': {k: handlers[k] for k in handlers.keys()-legacy.keys()},
              'renamed_handlers': [k for k in shared if handlers[k]['name'] != legacy[k][1]],
              'data': archive_tables(args.client, image)}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)+'\n')
    print(f'{len(handlers)} named handlers; {len(shared)} shared with 2016; inventory: {args.out}')


if __name__ == '__main__':
    main()
