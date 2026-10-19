"""Server-wide wire version; identical login packets cannot identify the client build.

2016 layouts were measured in DriftCity Dev Ed (2016-02-16); see HANDOVER.md.
Nation/publisher rules remain independent of this setting. A listener serves one build.
"""
from dataclasses import dataclass

from . import context


@dataclass(frozen=True)
class Layout:
    year: int
    character: int
    car: int
    item: int
    stats: int
    bonus: int
    flags: int


LAYOUTS = {
    2011: Layout(2011, 0x11b, 0x31, 0x5c, 0x68, 0x28, 0x58),
    2016: Layout(2016, 0x141, 0x32, 0x60, 0x70, 0x2c, 0x60),
}


def layout(year=None):
    return LAYOUTS[context.client_version if year is None else year]


def configure(section):
    value = section.get('version', '2011').strip()
    if value not in ('2011', '2016'):
        raise ValueError(f'[client] version: expected 2011 or 2016, got {value!r}')
    cap = int(section.get('max_level_2016', '100'))
    if not 1 <= cap <= 1023:
        raise ValueError('[client] max_level_2016 must be between 1 and 1023')
    context.client_version = int(value)
    context.max_level_2016 = cap


def is_2016():
    return context.client_version == 2016


def max_level():
    return context.max_level_2016 if is_2016() else 200


def flag_table():
    from ..handlers.game import FLAGS_2011_TABLE, _flag_table
    global _flags_2016
    if not is_2016():
        return FLAGS_2011_TABLE
    if _flags_2016 is None:
        _flags_2016 = _flag_table('flags_2016.tsv')
    return _flags_2016


_flags_2016 = None


def pack_flags(named):
    """Pack named switches using the selected build; leave unsupported switches zero."""
    import struct
    table = flag_table()
    out = bytearray(layout().flags)
    for name, value in named.items():
        if name not in table:
            continue
        off, shift, width = table[name]
        mask = ((1 << width) - 1) << shift
        old, = struct.unpack_from('<I', out, off)
        struct.pack_into('<I', out, off, (old & ~mask) | ((value << shift) & mask))
    return bytes(out)
