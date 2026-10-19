# 2016 client research tools (DriftCity Dev Ed)

Tools used in session 27 to compare the 2011 client (`Client US/DriftCityUS.exe`) with the 2016 one
(`DriftCity Dev Ed/DriftCity.exe`, not packed). Findings: `docs/EMULATOR_NOTES.md`, session 27, and
`docs/HANDOVER.md` (the 2016 port plan). Run everything in a scratch work folder:

```sh
X="Client US/DriftCityUS.exe"; D="DriftCity Dev Ed/DriftCity.exe"
dd if="$X" of=text.bin bs=1 skip=$((0x400)) count=$((0x4c5c00))      # 2011 .text -> 0x401000
objdump -D -b binary -m i386 -M intel --adjust-vma=0x401000 text.bin > text.dis
dd if="$D" of=dev.bin bs=1 skip=$((0x400)) count=$((0x540a00))       # 2016 first section -> 0x401000
objdump -D -b binary -m i386 -M intel --adjust-vma=0x401000 dev.bin > dev.dis
python3 fidx.py                       # function index of both -> f2011.pkl, f2016.pkl
```

- `disr.py START END [file.dis]`: a range of a disassembly (default text.dis).
- `fdiff.py A2011 A2016`: two functions side by side, only the differing instructions (addresses masked).
- `fmap.py A2011 ...`: the 2016 twin of a 2011 function (by instruction shape) and the instructions that differ only
  in their numbers (field offsets): the main tool for finding moved fields.
- `fieldmap2.py GETTER2011 [maxoff]`: over every 2011 caller of a getter, the [eax+X] -> [eax+Y] changes right after
  the call (e.g. `fieldmap2.py 708110 0x11b` mapped XiStrCharInfo, `707b10 0x40` the car record).
- `compare_sizes.py`: handler sizes of every message type in both exes (needs handlers_2011.json: the 2011 registrations
  `push handler; push type; mov ecx, esi; call 0x806590`, and handlers_2016.json: the 2016 ones, which carry names:
  `push "Cmd_X"; push handler; push type`).
- The 2016 flag table: a flat image of the 2016 exe (sections at their addresses from 0x400000) through
  `Server2008/tools/dev/flagtable.py img` -> `dcemu/data/flags_2016_raw.tsv` (needs capstone).
