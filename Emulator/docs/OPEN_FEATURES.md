# What the 2016 client can do that the emulator does not (2026-11-13)

Inventory of the gaps between the 2016 client (`DriftCity Dev Ed/DriftCity.exe`) and `dcemu/`. Re-run the checks
below after big changes; the lists are only as good as the last verification.

## How this was measured

- **Client side.** The 2016 exe's handler registrations (`push handler; push type; mov ecx,esi; call 0x86b800`) give
  the S>C messages it can display: **496 types**. The `mov WORD PTR [reg],type` sends give the C>S requests it can
  send: **481 types** (a few false positives: some of those writes are not senders).
- **Emulator side.** `dcemu.handlers._handlers` after `handlers.load()`: **343 C>S handlers** registered. Frame types
  built anywhere in `dcemu/`: **331**.
- **Ground truth.** `logs/2016/*.msgs.txt` records every message the client actually sent that no handler claimed
  (`-- no handler for 0xNNNN on this local service`).

So a raw set difference is noisy (many of the 481 sends belong to features neither build runs, and some registrations
are missed by the address scan). The lists below are the ones verified against the code.

## Requests the client really sent and we ignored (from the logs)

| Type | Times | Shape | Guess |
|---|---|---|---|
| `0x0f4d` | 23 294 | 4 bytes, constant `0x111a` | 2016 only, sent about once a second with a constant id — a keep-alive / session tick. Wrapper `0x866270`, one u32. |
| `0x0e8d` | 89 | 4 bytes, `0.0` | Sent right after login; the wrapper `0x867b70` writes a **float** at +2. Also exists in the 2011 client. |
| `0x02d5` | 42 (2016) / 70 (2011) | 12 bytes, 3 u32 | Both builds; wrapper `0x8655c0` takes three dwords (+2 / +6 / +0xa) and picks an object by an index. |
| `0x0fc1` | 3 | — | 2016 only. |
| `0x0fb4` | 1 | — | 2016 only. |
| `0x0777` | 1 | — | DCGP range (0x776-0x778). |

The 2011 build additionally shows `0x01b5` (43×, the 2008 server answers "Wrong Command: 437"), `0x02c8`, `0x021b`,
`0x0214`, `0x00a4`, `0x0057`.

## Features not implemented (verified: no handler and no sender in `dcemu/`)

| Feature | Messages | Notes |
|---|---|---|
| **DCGP** | `0x776`, `0x777`, `0x778` | Championship GP mode. |
| **World Laptime** | `0x3c0`, `0xf51`-`0xf5e` | Lap-time ranking; 14 S>C types. |
| **Honor ranking** | `0xfae`-`0xfb2` | `0xfae` -> `0xfaf` list, `0xfb0` -> `0xfb1` by name, `0xfb2` error (texts 12217-12220). The `0xc4` entry layout is still unknown. |
| **Neo HUS combat** | `0xef3`, `0xf4e`, `0xf50`, `0xfc0` | Neo City HUS enemies. |
| **Neo repair (parts)** | `0x4c4` -> `0x4c5` | No Neo part durability is kept, so the repair cannot be applied. |
| **NeoChapterBonusMission** | `0xef5` -> `0xef6` | Neo chapters are not modelled. |
| **PvpCollisionDamage** | `0xfbd` -> `0xfbe` | f32 damage; needs char flag `0x20` at `+0x2a4` and game mode 8. |
| **GMEventRush** | `0xfc3` | GM event. |
| **Rank pages** | `0xfa2`-`0xfa5` | Only `0xfa0`/`0xfa1` (character info) exist; the ranking pages and their `0xc4` entries are not built. |
| **Crew contribution rank tab** | `0xcee`/`0xcef`, `0xcf0`/`0xcf2` | The client never sends these in any log, and the tab renders "is feature is currently unavailable" — the real gate is still unidentified. |

## Changed in size but never built (from the timeline audit)

`0x22b` (#555), `0xaa` DormantEvent (6 -> 94), `0x1c5` StatEnchantRes (154 -> 166), `0x1d3` RoomNotifyChange
(236 -> 240), `0x241` ReplaceCarAck (68 -> 72), `0x69` RentCarAck, `0x5d5` GetCarAck, `0x6af` AuctionCarBuyAck
(+1 car record). The timeline gives names and sizes only, not field layouts.

## Done since the session-40 list (do not re-report these)

Mission Battle (`0x3b7`, `0x3b8`-`0x3bd`), crew research / boards (`0xce7`, `0xce9`), crew apply ack `0x36e`,
WhisperDeny `0xfb3`, offline character info `0x29e`/`0x29f`, Valentine chocolate `0xfba`, player trade `0x1f4`-`0x203`,
password joins `0x1d8`/`0x1dd`, crew Acceptance page (`0x357` act `0x3f4` + `0x36f`), car limit and the Origin /
Skid Rush car port.

## Reproducing

```sh
cd Emulator
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'.')
from dcemu import handlers, protocol
handlers.load()
print(len({t for (s,d,t) in handlers._handlers if d==protocol.C2S}), "C>S handlers")
PY
grep -h "no handler for" logs/2016/*.msgs.txt | sed 's/.*for \(0x[0-9a-f]*\).*/\1/' | sort | uniq -c | sort -rn
```
