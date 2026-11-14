package main

// EU rules on the US client ([client] rules = eu, or --eu; user 2026-11-14: one US client for both rule sets, the
// EU client retired). Two parts:
//
//   - the server learns the rules from the client's nation message 0x7cf (Emulator/dcemu/native/nation.py). The
//     login code sends it only for the EU nations: 2011 0x538a9f / 2016 0x54f0ad
//         call GetNation; cmp eax, 7; jl skip; call GetNation; cmp eax, 10; jg skip; call GetNation; push eax
//         mov ecx, esi; call SendNation (2011 0x7feaf0 / 2016 0x862a30)
//     The launcher writes `push 8` + 24 NOPs over those 26 bytes in memory: the client sends nation 8 (EU eng)
//     after its login and stays nation 1 everywhere else (US data, texts, token, server slots). The exe on disk is
//     unchanged. The 2011 ASProtect DriftCity.exe checks its code, so EU rules need the unpacked DriftCityUS.exe
//     (Emulator/tools/eu_client.py us); the launcher checks the bytes in the exe file first.
//   - the client's own tables (part tooltips "Required Grade", battle zone / channel battle limits; with units = kph
//     the unit texts, assist texts, HUD label and dial picture): copies of the files that hold them per setting
//     combination, X.eu / X.kph / X.eu.kph, made by `python -m tools.eu_rules build` with the manifest
//     ClientModes.txt (path, sha256 of X when the copies were made, the settings that change X; the older
//     EURules.txt has no third column = eu). Start: X -> X.us, the matching copy to X; when the client is gone (and
//     at every start, after a crash) X.us goes back to X. A stale copy (X changed since) is not used.
//
// Speed unit ([client] units = kph, or --kph; user 2026-11-14: km/h without changing the region): a nation-1 client
// converts to miles only for display, at seven 2-byte branches per build (Emulator/docs/neo_work/SPEED_UNITS.md,
// all bytes checked in both exes); the launcher writes the metric branch there. The server learns the unit from bit
// 16 of the 0x7cf value (the same login patch, `push imm32`), for the speed caps it sends.

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const (
	nationSend2011 = 0x538a9f
	nationSend2016 = 0x54f0ad
	euNationCode   = 8 // EU eng
	usNationCode   = 1
	kphFlag        = 0x10000 // bit 16 of the 0x7cf value: the client shows km/h (Emulator nation.py)
	manifestName   = "ClientModes.txt"
	oldManifest    = "EURules.txt" // eu only
)

// unitPatch: a 2-byte branch that picks miles for nation 1, and its metric version.
type unitPatch struct {
	addr      uint32
	orig, kph []byte
}

// unitPatches2011 / 2016: F2 / info window distance x3, race HUD "To Goal", the miles() helper (record list, car
// stats), the HUD speed integer, the quest window distance (SPEED_UNITS.md sections 2 and 3).
var unitPatches2011 = []unitPatch{
	{0x56fbbd, []byte{0x74, 0x20}, []byte{0x90, 0x90}}, {0x570bb2, []byte{0x74, 0x20}, []byte{0x90, 0x90}},
	{0x5c00f4, []byte{0x74, 0x20}, []byte{0x90, 0x90}}, {0x5ae3e6, []byte{0x74, 0x7f}, []byte{0x90, 0x90}},
	{0x47e82c, []byte{0x75, 0x06}, []byte{0xeb, 0x06}}, {0x4923b0, []byte{0x75, 0x27}, []byte{0xeb, 0x27}},
	{0x6cb7e6, []byte{0x75, 0x13}, []byte{0xeb, 0x13}},
}
var unitPatches2016 = []unitPatch{
	{0x58dac3, []byte{0x74, 0x20}, []byte{0x90, 0x90}}, {0x58f332, []byte{0x74, 0x20}, []byte{0x90, 0x90}},
	{0x5e98bc, []byte{0x74, 0x20}, []byte{0x90, 0x90}}, {0x5d6f46, []byte{0x74, 0x7f}, []byte{0x90, 0x90}},
	{0x48823c, []byte{0x75, 0x06}, []byte{0xeb, 0x06}}, {0x49c0ec, []byte{0x75, 0x27}, []byte{0xeb, 0x27}},
	{0x7238c7, []byte{0x75, 0x13}, []byte{0xeb, 0x13}},
}

// kph: the client shows km/h ([client] units = kph, set by main).
var kph bool

// sendsNation: the launcher makes the client send 0x7cf (EU rules or km/h).
func sendsNation() bool { return euRules || kph }

// nationValue: the 0x7cf value: the rules' nation, bit 16 for km/h.
func nationValue() uint32 {
	v := uint32(usNationCode)
	if euRules {
		v = euNationCode
	}
	if kph {
		v |= kphFlag
	}
	return v
}

var (
	nationSendOrig2011 = []byte{0xe8, 0xbc, 0x08, 0xfb, 0xff, 0x83, 0xf8, 0x07, 0x7c, 0x17, 0xe8, 0xb2, 0x08, 0xfb, 0xff,
		0x83, 0xf8, 0x0a, 0x7f, 0x0d, 0xe8, 0xa8, 0x08, 0xfb, 0xff, 0x50}
	nationSendOrig2016 = []byte{0xe8, 0x7e, 0xa9, 0xfa, 0xff, 0x83, 0xf8, 0x07, 0x7c, 0x17, 0xe8, 0x74, 0xa9, 0xfa, 0xff,
		0x83, 0xf8, 0x0a, 0x7f, 0x0d, 0xe8, 0x6a, 0xa9, 0xfa, 0xff, 0x50}
)

// euRules: the client is started with EU rules (main).
var euRules bool

// nationSendPatch: `push nationValue()` (68 imm32) then NOPs, as long as the original.
func nationSendPatch() []byte {
	b := bytes.Repeat([]byte{0x90}, len(nationSendOrig2011))
	b[0] = 0x68
	binary.LittleEndian.PutUint32(b[1:5], nationValue())
	return b
}

// nationSendInFile: the exe file holds the original login code (2011: false for the ASProtect DriftCity.exe).
func nationSendInFile(path string, is2016 bool) bool {
	f, err := os.Open(path)
	if err != nil {
		return false
	}
	defer f.Close()
	at, orig := int64(nationSend2011)-0x401000+0x400, nationSendOrig2011
	if is2016 {
		at, orig = fileOffset2016(nationSend2016), nationSendOrig2016
	}
	b := make([]byte, len(orig))
	if n, _ := f.ReadAt(b, at); n != len(b) {
		return false
	}
	return bytes.Equal(b, orig)
}

// writeNationSend2011 writes the 2011 patch into a running client. -> what was done, for the log.
func writeNationSend2011(read func(uint32, int) []byte, write func(uint32, []byte) bool) string {
	p := nationSendPatch()
	cur := read(nationSend2011, len(p))
	switch {
	case bytes.Equal(cur, p):
		return fmt.Sprintf("nation %#x at login: already there", nationValue())
	case !bytes.Equal(cur, nationSendOrig2011):
		return fmt.Sprintf("nation at login: FAILED, unknown code at %#x", nationSend2011)
	case !write(nationSend2011, p) || !bytes.Equal(read(nationSend2011, len(p)), p):
		return "nation at login: FAILED to write"
	}
	return fmt.Sprintf("nation %#x at login", nationValue())
}

// writeUnits2011 writes the km/h branches into a running 2011 client. -> what was done, for the log.
func writeUnits2011(read func(uint32, int) []byte, write func(uint32, []byte) bool) string {
	n := 0
	for _, u := range unitPatches2011 {
		cur := read(u.addr, len(u.orig))
		switch {
		case bytes.Equal(cur, u.kph):
			n++
		case !bytes.Equal(cur, u.orig):
			return fmt.Sprintf("km/h: FAILED, unknown code at %#x", u.addr)
		case write(u.addr, u.kph) && bytes.Equal(read(u.addr, len(u.kph)), u.kph):
			n++
		default:
			return fmt.Sprintf("km/h: FAILED to write %#x", u.addr)
		}
	}
	return fmt.Sprintf("km/h (%d branches)", n)
}

// unitsInFile: the exe file holds the original unit branches (2011: false for the ASProtect DriftCity.exe).
func unitsInFile(path string, is2016 bool) bool {
	f, err := os.Open(path)
	if err != nil {
		return false
	}
	defer f.Close()
	list := unitPatches2011
	if is2016 {
		list = unitPatches2016
	}
	for _, u := range list {
		at := int64(u.addr) - 0x401000 + 0x400
		if is2016 {
			at = fileOffset2016(u.addr)
		}
		b := make([]byte, len(u.orig))
		if n, _ := f.ReadAt(b, at); n != len(b) || !bytes.Equal(b, u.orig) {
			return false
		}
	}
	return true
}

type manifestEntry struct {
	path, sum string
	modes     []string // the settings that change this file: eu, kph (in this order)
}

func readManifest(dir string) ([]manifestEntry, error) {
	f, err := os.Open(filepath.Join(dir, manifestName))
	if err != nil {
		if f, err = os.Open(filepath.Join(dir, oldManifest)); err != nil {
			return nil, err
		}
	}
	defer f.Close()
	var out []manifestEntry
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, ";") {
			continue
		}
		cols := strings.Split(line, "\t")
		if len(cols) < 2 {
			continue
		}
		modes := []string{"eu"}
		if len(cols) > 2 {
			modes = nil
			for _, m := range strings.Split(cols[2], ",") {
				if m = strings.TrimSpace(m); m != "" {
					modes = append(modes, m)
				}
			}
		}
		out = append(out, manifestEntry{filepath.FromSlash(strings.TrimSpace(cols[0])), strings.TrimSpace(cols[1]), modes})
	}
	return out, sc.Err()
}

func fileSum(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".new"
	out, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		os.Remove(tmp)
		return err
	}
	if err := out.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, dst)
}

// restoreTables puts every X.us of the manifest back to X (the US tables). -> how many.
func restoreTables(dir string) int {
	entries, err := readManifest(dir)
	if err != nil {
		return 0
	}
	n := 0
	for _, e := range entries {
		x := filepath.Join(dir, e.path)
		if _, err := os.Stat(x + ".us"); err != nil {
			continue
		}
		if err := os.Rename(x+".us", x); err != nil {
			logf("warning: %s.us could not be put back: %v", e.path, err)
			continue
		}
		n++
	}
	return n
}

// variant: the copy of a manifest file for the chosen settings ("eu", "kph", "eu.kph"), "" = the original.
func variant(e manifestEntry) string {
	var parts []string
	for _, m := range e.modes {
		if (m == "eu" && euRules) || (m == "kph" && kph) {
			parts = append(parts, m)
		}
	}
	return strings.Join(parts, ".")
}

// applyEUTables swaps in the copies the settings ask for. -> a note for the log; nothing is swapped when any copy
// is missing or stale.
func applyEUTables(dir string) string {
	if n := restoreTables(dir); n > 0 {
		logf("original tables put back first: %d files (a previous start did not end cleanly)", n)
	}
	entries, err := readManifest(dir)
	if err != nil || len(entries) == 0 {
		return "client tables: original (no " + manifestName + ": run `python -m tools.eu_rules build` in Emulator/)"
	}
	var want []manifestEntry
	for _, e := range entries {
		if variant(e) != "" {
			want = append(want, e)
		}
	}
	if len(want) == 0 {
		return "client tables: original (no copies for these settings)"
	}
	for _, e := range want {
		x := filepath.Join(dir, e.path)
		sum, err := fileSum(x)
		if err != nil {
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		if sum != e.sum {
			return fmt.Sprintf("client tables: US (%s changed since its EU copy was made: run `python -m tools.eu_rules build`)", e.path)
		}
		if _, err := os.Stat(x + "." + variant(e)); err != nil {
			return fmt.Sprintf("client tables: US (%s.%s missing: run `python -m tools.eu_rules build`)", e.path, variant(e))
		}
	}
	var done []string
	for _, e := range want {
		x := filepath.Join(dir, e.path)
		if err := os.Rename(x, x+".us"); err != nil {
			restoreTables(dir)
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		if err := copyFile(x+"."+variant(e), x); err != nil {
			restoreTables(dir)
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		done = append(done, e.path+" ("+variant(e)+")")
	}
	return "client tables: " + strings.Join(done, ", ")
}
