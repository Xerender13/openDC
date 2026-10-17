// DriftCityLauncher starts the 2011 Drift City client (DriftCity.exe, GamesCampus build of 2011-10-27,
// ASProtect; or DriftCityEU.exe, the same build unpacked and set to an EU nation by Emulator/tools/eu_client.py)
// against a server of our choice. It lives in the client folder, next to the exe ([client] exe), and
// reads DriftCityLauncher.ini there (written with the defaults when missing).
//
// What it does (found in the client's unpacked image; the Python original is
// Server2008/tools/dev/run_us2011.py):
//   - the client only runs when started by the launcher: `DriftCity.exe /runsw <token>`, token =
//     md5(str(t - t % 300000)) in hex with t = the millisecond tick count (GetTickCount)
//   - the login server address is hard-coded per nation in 16-byte slots 0x8daa14..0x8daad4 (US, nation 1:
//     208.80.248.47 live / 208.80.248.215 alpha at 0x8daaa4 / 0x8daab4; EU, nations 7-10: 62.146.191.136 /
//     .135 at 0x8daa14 / 0x8daa24; client 0x538ff0); once the client has unpacked itself, the launcher
//     writes the configured address over every slot
//   - the build has no GameGuard files, but nation 1 creates the GameGuard object: at 0x4e114b the client
//     switches on its nation class; the launcher puts a hardware breakpoint there (a debug register, no
//     code change: ASProtect checks the code) and moves the thread to 0x4e1191, the branch that creates the
//     object whose checks all succeed
//   - item icons on pick-up: the client draws the items received (combo / traffic drops, patrol prizes) as fading
//     32x32 icons ([ui+0x3c0], client 0x6669a0) only while bit 4 of the network object's flag word
//     [[0x973e40]+0x2b4] is set; nothing in the US build sets it. The launcher sets it while the client runs
//     (keepPatches; [client] item_icons = 0 turns it off)
//   - the delivery cargo model: with the ADV HUD (main_ui_type 1) its camera is moved into the Delivery Service
//     box on the right (keepPatches / fixCargo)
//   - drift items on the car in the inventory's Visual Item tab: the tab has 19 fixed slots, one per category
//     (client 0x70edd0, byte table 0x70eedc); category 41 (PassiveAssist, equippable here) has none, so it never
//     showed. Once logged in the launcher gives it slot 13, the rental car slot (categories 30 / 31, never on a
//     normal car); the car model (0x536840) and the stat sums ignore category 41 ([client] passive_slot)
//   - windowed mode (fullscreen takes no input under Proton): goption.ini Fullscreen=false and
//     HKLM\SOFTWARE\DriftCity EnableWindowMode = 1
//
// Linux: runs the client with Proton (or Wine) and patches it with ptrace (launch_linux.go). Windows: no
// debugger (ASProtect hangs under one); memory writes and the GameGuard object's vtable (launch_windows.go).
package main

import (
	"bufio"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	ggSwitch   = 0x4e114b // the nation switch that creates the protection object
	noGGBranch = 0x4e1191 // the branch for nation class 0: the object whose checks all succeed
	ggObject   = 0x94d168 // the protection object pointer
	ggVtable   = 0x8d0d34 // vtable of the GameGuard object
	noGGVtable = 0x8d0d7c // vtable of the object whose checks succeed
	addrLive   = 0x8daaa4 // the US live server's slot: unpacked once it holds liveAddress
	addrFirst  = 0x8daa14 // the server address slots of all nations (16 bytes each, client 0x538ff0)
	addrLast   = 0x8daad4
	netObject  = 0x973e40 // the network object pointer (client 0x536360)
	netVtable  = 0x8cddd0
	netFlags   = 0x2b4 // its flag word; bit 4 = show item icons on pick-up
	itemIcons  = 4
	// the category -> Visual Item slot byte table (client 0x70edd0: byte [0x70eedc + category - 1] picks the case;
	// 20 = no slot, 13 = slot 13, the one of category 30): the byte of category 41 (PassiveAssist)
	passiveSlotByte = 0x70eedc + 41 - 1
	noSlotCase      = 20
	rentalSlotCase  = 13
)

// Patches are data writes into the running client, checked every second (ASProtect checks the code, not data).
type Patches struct {
	icons bool // [client] item_icons: the item icon bit
	cargo bool // ADV HUD (main_ui_type 1): the delivery cargo model in the Delivery Service box on the right
	slot  bool // [client] passive_slot: PassiveAssist items on the car get a Visual Item tab slot
}

const (
	hudRoot   = 0x948844 // [[root]+0x100] = the HUD object
	cargoCam  = 0x114    // HUD + 0x114: the camera of the delivery cargo model (vtable camVtable)
	camVtable = 0x8c9c48
	viewport  = 0x114 // camera + 0x114: NiRect<float> left, right, top, bottom (screen fractions)
	screenW   = 0x94d444
	screenH   = 0x94d448
)

// keepPatches applies the patches to a running client and keeps them applied (checked every second) until the
// process is gone. read / write access the client's memory; read returns nil once the process is gone.
//
// Cargo: the client makes the cargo camera once with a fixed viewport x 4..176, y 27..149 (client 0x6d221a), the
// classic HUD's box; the 2011 ADV HUD's box (game.nui dialog 700000, control 700004) is right-anchored at x
// 849..1009, y 105..225 of 1024 x 768, so the model was drawn top left (user, 2026-10-14). The viewport is moved
// there while it still has the classic values.
func keepPatches(pid int, p Patches, read func(addr uint32, n int) []byte, write func(addr uint32, b []byte) bool) {
	iconsOn, cargoOn, slotOn := false, false, false
	for {
		root := read(hudRoot, 4)
		if root == nil {
			return
		}
		if p.icons {
			if obj := le32(read(netObject, 4)); obj != 0 {
				if vt := read(obj, 4); vt != nil && le32(vt) == netVtable {
					if f := read(obj+netFlags, 4); f != nil && le32(f)&itemIcons == 0 {
						v := le32(f) | itemIcons
						if write(obj+netFlags, u32bytes(v)) && !iconsOn {
							logf("client pid %d: item icons on", pid)
							iconsOn = true
						}
					}
				}
			}
		}
		// the slot byte is in the code section: written only once logged in (the network object exists), long
		// after ASProtect's code check at start (a code write then gave "Error: 45"), and only over the original
		if p.slot && !slotOn {
			if obj := le32(read(netObject, 4)); obj != 0 && le32(read(obj, 4)) == netVtable {
				if b := read(passiveSlotByte, 1); len(b) == 1 && b[0] == noSlotCase {
					if write(passiveSlotByte, []byte{rentalSlotCase}) {
						logf("client pid %d: PassiveAssist items get a Visual Item slot", pid)
						slotOn = true
					}
				} else if len(b) == 1 && b[0] == rentalSlotCase {
					slotOn = true
				}
			}
		}
		if p.cargo {
			if fixCargo(read, write) && !cargoOn {
				logf("client pid %d: delivery cargo model moved into the Delivery Service box", pid)
				cargoOn = true
			}
		}
		time.Sleep(time.Second)
	}
}

// fixCargo moves the cargo camera's viewport to the ADV HUD box. -> true when it wrote.
func fixCargo(read func(addr uint32, n int) []byte, write func(addr uint32, b []byte) bool) bool {
	hud := le32(read(le32(read(hudRoot, 4))+0x100, 4))
	if hud == 0 {
		return false
	}
	cam := le32(read(hud+cargoCam, 4))
	if cam == 0 || le32(read(cam, 4)) != camVtable {
		return false
	}
	w, h := float32(le32(read(screenW, 4))), float32(le32(read(screenH, 4)))
	if w < 320 || h < 240 {
		return false
	}
	vp := read(cam+viewport, 16)
	left := math.Float32frombits(le32(vp))
	if left*w > 8 { // not the classic box (already moved, or a layout we do not know)
		return false
	}
	out := make([]byte, 0, 16)
	for _, v := range []float32{(w - 175) / w, (w - 15) / w, 1 - 105/h, 1 - 225/h} {
		out = append(out, u32bytes(math.Float32bits(v))...)
	}
	return write(cam+viewport, out)
}

func u32bytes(v uint32) []byte { return []byte{byte(v), byte(v >> 8), byte(v >> 16), byte(v >> 24)} }

func le32(b []byte) uint32 {
	if len(b) < 4 {
		return 0
	}
	return uint32(b[0]) | uint32(b[1])<<8 | uint32(b[2])<<16 | uint32(b[3])<<24
}

// patchesFor: the patches the settings ask for.
func patchesFor(cfg Config) Patches {
	return Patches{icons: cfg.get("client.item_icons", "1") != "0", cargo: cfg.get("client.main_ui_type", "1") == "1",
		slot: cfg.get("client.passive_slot", "1") != "0"}
}

var liveAddress = []byte("208.80.248.47")

// clientExe: the client program ([client] exe), set by main.
var clientExe = "DriftCity.exe"

// writeAddress writes ip over every nation's server slot that holds an IPv4 address. -> the slots written, or 0
// while the client has not unpacked itself yet (the US live slot does not hold its address).
func writeAddress(read func(addr uint32, n int) []byte, write func(addr uint32, b []byte) bool, ip string) int {
	if b := read(addrLive, len(liveAddress)); b == nil || string(b) != string(liveAddress) {
		return 0
	}
	n := 0
	for a := uint32(addrFirst); a <= addrLast; a += 16 {
		slot := read(a, 16)
		if slot == nil {
			return n
		}
		if end := strings.IndexByte(string(slot), 0); end > 0 && validAddress(string(slot[:end])) &&
			write(a, addressBytes(ip)) {
			n++
		}
	}
	return n
}

const defaultIni = `; Settings of DriftCityLauncher (the 2011 Drift City client launcher), next to DriftCity.exe
[server]
; the login server (the emulator's auth port 11005) the client connects to: an IPv4 address, at most 15 characters
address = 127.0.0.1

[client]
; the client program in this folder: DriftCityEU.exe (the European client, see Emulator/tools/eu_client.py) or
; DriftCity.exe (the US client); empty = DriftCityEU.exe when it is there
exe =
; goption.ini MainUIType: 0 = the classic HUD, 1 = the 2011 "ADV" HUD
main_ui_type = 1
; item_icons: 1 = show the items received (combos, traffic items, patrol prizes) as icons on the HUD, 0 = only the
; chat line (the US client has the icons switched off; the launcher switches them on while the client runs)
item_icons = 1
; passive_slot: 1 = PassiveAssist items on a car show in the inventory's Visual Item tab (the client has no slot for
; them; the launcher gives them the rental car slot once logged in), 0 = leave the client as it is
passive_slot = 1
; display: windowed or fullscreen (also on the command line: --windowed / --fullscreen). The client starts in
; fullscreen unless HKLM\SOFTWARE\DriftCity EnableWindowMode is 1; the launcher sets it and goption.ini Fullscreen.
; Under Proton fullscreen has taken no keyboard / mouse input so far: windowed is the default on Linux.
; On Windows writing that registry value needs the launcher run as administrator once.
display = windowed

[linux]
; how the client is run: proton (Steam's Proton) or wine
runner = proton
; Proton's "proton" script; empty = the newest Proton found in the Steam library
proton =
; the Steam folder and the Wine prefix the client uses
steam = ~/.local/share/Steam
prefix = ~/.local/share/drift2011-pfx
; with runner = wine: the wine program
wine = wine
`

// Config holds DriftCityLauncher.ini.
type Config map[string]string // "section.key" -> value

func (c Config) get(key, def string) string {
	if v, ok := c[key]; ok && v != "" {
		return v
	}
	return def
}

func parseIni(r io.Reader, c Config) {
	section := ""
	sc := bufio.NewScanner(r)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if i := strings.IndexAny(line, ";#"); i >= 0 {
			line = strings.TrimSpace(line[:i])
		}
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = strings.ToLower(strings.TrimSpace(line[1 : len(line)-1]))
			continue
		}
		if k, v, ok := strings.Cut(line, "="); ok {
			c[section+"."+strings.ToLower(strings.TrimSpace(k))] = strings.TrimSpace(v)
		}
	}
}

func loadConfig(dir string) (Config, string) {
	path := filepath.Join(dir, "DriftCityLauncher.ini")
	c := Config{}
	parseIni(strings.NewReader(defaultIni), c)
	f, err := os.Open(path)
	if err != nil {
		_ = os.WriteFile(path, []byte(strings.ReplaceAll(defaultIni, "\n", lineEnd)), 0o644)
		return c, path
	}
	defer f.Close()
	parseIni(f, c)
	return c, path
}

func validAddress(ip string) bool {
	parts := strings.Split(ip, ".")
	if len(ip) > 15 || len(parts) != 4 {
		return false
	}
	for _, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 || n > 255 {
			return false
		}
	}
	return true
}

// token is the /runsw argument for the tick count t (milliseconds): md5 of the 5-minute window, written "%d" by
// the US check (client 0x509980), "eu_%d_plz_do_not_hack" by the EU nations' check (0x5095a0).
func token(t uint64, eu bool) string {
	if s := os.Getenv("DRIFTCITY_TOKEN"); s != "" {
		return s
	}
	text := strconv.FormatUint(t-t%300000, 10)
	if eu {
		text = "eu_" + text + "_plz_do_not_hack"
	}
	sum := md5.Sum([]byte(text))
	return hex.EncodeToString(sum[:])
}

// euNation: the nation (7-10) an exe changed by Emulator/tools/eu_client.py sets in the options constructor
// (0x4e4106: push N; pop eax; ...; mov al, 1), or 0 for the original code (nation 1, US).
func euNation(path string) int {
	b, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	tail := []byte{0x58, 0x88, 0x9e, 0x68, 0x01, 0x00, 0x00, 0x89, 0x86, 0x6c, 0x01, 0x00, 0x00, 0xa3, 0x80, 0xd8,
		0x94, 0x00, 0xb0, 0x01}
	for i := 2; i+len(tail) <= len(b); i++ {
		if b[i] == 0x58 && b[i-2] == 0x6a && string(b[i:i+len(tail)]) == string(tail) && b[i-1] >= 7 && b[i-1] <= 10 {
			return int(b[i-1])
		}
	}
	return 0
}

// clientEU: the client is set to an EU nation (main).
var clientEU bool

// setOptions writes goption.ini: Fullscreen (when windowed) and MainUIType.
func setOptions(clientDir string, windowed bool, mainUI string) {
	p := filepath.Join(clientDir, "Data", "Init", "goption.ini")
	b, err := os.ReadFile(p)
	if err != nil {
		logf("goption.ini: %v", err)
		return
	}
	b = regexp.MustCompile(`Fullscreen=(true|false)`).ReplaceAll(b, []byte("Fullscreen="+strconv.FormatBool(!windowed)))
	if mainUI == "0" || mainUI == "1" {
		b = regexp.MustCompile(`MainUIType=\d`).ReplaceAll(b, []byte("MainUIType="+mainUI))
	}
	if err := os.WriteFile(p, b, 0o644); err != nil {
		logf("goption.ini: %v", err)
	}
}

// displayWindowed: [client] display (windowed / fullscreen; older inis: windowed = 1 / 0 / auto).
func displayWindowed(c Config, def bool) bool {
	switch strings.ToLower(c.get("client.display", "")) {
	case "windowed", "window":
		return true
	case "fullscreen", "full":
		return false
	}
	switch c.get("client.windowed", "auto") {
	case "1":
		return true
	case "0":
		return false
	}
	return def
}

// addressBytes is the new address as written over each 16-byte slot.
func addressBytes(ip string) []byte {
	b := make([]byte, 15)
	copy(b, ip)
	return b
}

var logFile *os.File

func logf(format string, a ...any) {
	line := fmt.Sprintf("%s %s", time.Now().Format("15:04:05.000"), fmt.Sprintf(format, a...))
	fmt.Println(line)
	if logFile != nil {
		fmt.Fprint(logFile, line+lineEnd)
	}
}

func main() {
	exe, err := os.Executable()
	if err != nil {
		fail("cannot find the launcher's folder: %v", err)
	}
	dir := filepath.Dir(exe)
	if _, err := os.Stat(filepath.Join(dir, "DriftCity.exe")); err != nil {
		if wd, _ := os.Getwd(); wd != "" {
			if _, err2 := os.Stat(filepath.Join(wd, "DriftCity.exe")); err2 == nil {
				dir = wd
			}
		}
	}
	logFile, _ = os.Create(filepath.Join(dir, "DriftCityLauncher.log"))
	cfg, iniPath := loadConfig(dir)
	clientExe = cfg.get("client.exe", "")
	if clientExe == "" {
		clientExe = "DriftCity.exe"
		if _, err := os.Stat(filepath.Join(dir, "DriftCityEU.exe")); err == nil {
			clientExe = "DriftCityEU.exe"
		}
	}
	if _, err := os.Stat(filepath.Join(dir, clientExe)); err != nil {
		fail("%s is not in %s: put the launcher into the client folder (or set [client] exe in %s)", clientExe, dir, iniPath)
	}
	ip := cfg.get("server.address", "127.0.0.1")
	for _, a := range os.Args[1:] {
		switch strings.ToLower(a) {
		case "--windowed", "-windowed", "/windowed":
			cfg["client.display"] = "windowed"
		case "--fullscreen", "-fullscreen", "/fullscreen":
			cfg["client.display"] = "fullscreen"
		default:
			ip = a
		}
	}
	if !validAddress(ip) {
		fail("server address %q: an IPv4 address (at most 15 characters) is needed (%s)", ip, iniPath)
	}
	if n := euNation(filepath.Join(dir, clientExe)); n != 0 {
		clientEU = true
		logf("client %s (EU, nation %d), server %s", filepath.Join(dir, clientExe), n, ip)
	} else {
		logf("client %s, server %s", filepath.Join(dir, clientExe), ip)
	}
	if err := launch(dir, ip, cfg); err != nil {
		fail("%v", err)
	}
}

func fail(format string, a ...any) {
	logf("error: "+format, a...)
	pause()
	os.Exit(1)
}
