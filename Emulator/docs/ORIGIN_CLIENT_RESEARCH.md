# Origin / Skid Rush: deferred feasibility notes

**Deferred by user, 2026-10-19.** Finish 2011 client support first, then full 2016 support.
Do not start an Origin implementation or divert active gameplay work to this port.

Read-only research target: `/home/deck/Drift City Origin/Client/driftcity.exe`.
Original SHA-256: `1c3c151bfe36914697ec7ebdf1d1a4de92477f364325a433a21f1f1bcaba917a`.
32-bit PE, reported PE timestamp2024-07-03 (not proof of a release date). UPX-packed.
A research copy was unpacked only under `/tmp/dcemu-origin-research/`; original untouched.
Unpacked SHA-256: `081151f12735f3090b190b0604361ed4e4a5debf000920ecf928f37b81d8e634`.
UPX5.2.1 downloaded from the [official release](https://github.com/upx/upx/releases/tag/v5.2.1);
archive SHA-256 verified against the release. No game executable was launched for this research.

Observed:
- 534 named S>C handler registrations; **all 514 from Dev Ed2016 retained at the same IDs/names**, plus20.
  This establishes shared protocol ancestry, not wire compatibility.
- Origin LoadCharAck0x534f20: car count@0x167, cars@0x16b with stride0x32;
  character record therefore0x15d versus2016 0x141 (+28). Packet size0x16b+n*0x32.
- Car remains50 bytes. ItemListAck0x528320 uses100-byte records versus96 (+4);
  ItemModList0x528360 uses104-byte entries versus100.
- StatUpdate0x518cc0 reads bonus@0x8e and returns0xba, implying140-byte stats
  versus112 (+28); enchant bonus remains44 bytes.
- GameSetting0x531f70 consumes106 bytes (96 flag bytes), AuthAck0x516bd0 consumes78,
  JoinChannelAck0x51a2b0 consumes58, MyPositionAck0x51ea60 consumes31,
  CompleteApprenticeAck0x534390 consumes80: same sizes as2016.
  EXP handler0x5209d0 retains three64-bit counters and consumes32 bytes.
- Main.Apprentice, Main.PasserBy and Main.MainButtonAdvanced retain their known Main bits
  in the reflected table at0x45b1c0..0x45b2e8; full flags still need comparison.
- Archives retain NayaPack. Embedded90-byte key at unpacked file0x661590 changes only byte16,
  from0x31 to0x6c. Streaming inventory with this key validated base Init/data and patch000..010;
  VehicleList/Upgrade, ItemClient, UseItemClient, License, Assist and Quest tables decoded.
  **Do not use the current default-key reader on Origin:** wrong lengths can cause huge allocations.
  Future adaptation needs per-client keys and index bounds checks, including city traffic packs.
- Extra handlers cover attendance, content quests/limits/buffs, recipe results, match/quick-battle and
  Arbeit rankings. Existing game concepts and engine imports remain recognizable.
- Unpacked image still has .themida/.boot/.SCY sections and XIGNCODE strings; their active role is unknown.
  Existing user logs reach GameCreate/UI under Proton. That is not proof emulator login will work.

Assessment (inference): feasible as another optional build profile after2016; not a flag-only change.
Data decoding is a small known change. Initial auth/lobby is a manageable first milestone because many
packets remain shared. Full gameplay is a substantial port: larger records propagate through other-player,
room, inventory, stats and reward packets. Unknowns include actual handshake/cipher mode, all C>S sizes,
redirect/launch checks, protection behavior and new feature persistence. No reliable completion date yet.

Reproducible, read-only inventory: `tools/reorigin/inspect.py`; output `origin_inventory.json` records
hashes, registry sites, names/IDs and table inventory. It requires a separately unpacked copy. No Origin
server profile, listener, database, config switch or support claim was added.

REA original-file evidence: file headers `ev_fb09ea4d2fb3c2e14cb352da63ce4a24e9bb9e47caf5dbc682e8a31729f2b5d1`,
section headers `ev_ae23ff53d22f155e493c46e67ed1dbea752b6ffec191d7cb62d71108645d2b28`.
Focused GNU objdump ranges and registry/archive byte parsing supplied remaining static evidence.
The research copy and disassembly in /tmp are disposable; recreate them if needed. No runtime compatibility
or complete packet-size census was established. Preserve this note for later, then return to2011/2016 work.
