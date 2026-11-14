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
//   - the client's own tables (part tooltips "Required Grade", battle zone / channel battle limits): EU copies of
//     the files that hold them, X.eu, made by `python -m tools.eu_rules build` with the manifest EURules.txt (path,
//     sha256 of X when X.eu was made). EU mode: X -> X.us, X.eu copied to X; when the client is gone (and at every
//     start, after a crash) X.us goes back to X. A stale copy (X changed since) is not used.

import (
	"bufio"
	"bytes"
	"crypto/sha256"
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
	manifestName   = "EURules.txt"
)

var (
	nationSendOrig2011 = []byte{0xe8, 0xbc, 0x08, 0xfb, 0xff, 0x83, 0xf8, 0x07, 0x7c, 0x17, 0xe8, 0xb2, 0x08, 0xfb, 0xff,
		0x83, 0xf8, 0x0a, 0x7f, 0x0d, 0xe8, 0xa8, 0x08, 0xfb, 0xff, 0x50}
	nationSendOrig2016 = []byte{0xe8, 0x7e, 0xa9, 0xfa, 0xff, 0x83, 0xf8, 0x07, 0x7c, 0x17, 0xe8, 0x74, 0xa9, 0xfa, 0xff,
		0x83, 0xf8, 0x0a, 0x7f, 0x0d, 0xe8, 0x6a, 0xa9, 0xfa, 0xff, 0x50}
)

// euRules: the client is started with EU rules (main).
var euRules bool

// nationSendPatch: `push 8` then NOPs, as long as the original.
func nationSendPatch() []byte {
	b := bytes.Repeat([]byte{0x90}, len(nationSendOrig2011))
	b[0], b[1] = 0x6a, euNationCode
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
		return "EU rules (nation 8 at login): already there"
	case !bytes.Equal(cur, nationSendOrig2011):
		return fmt.Sprintf("EU rules: FAILED, unknown code at %#x", nationSend2011)
	case !write(nationSend2011, p) || !bytes.Equal(read(nationSend2011, len(p)), p):
		return "EU rules: FAILED to write"
	}
	return "EU rules (nation 8 at login)"
}

type manifestEntry struct{ path, sum string }

func readManifest(dir string) ([]manifestEntry, error) {
	f, err := os.Open(filepath.Join(dir, manifestName))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []manifestEntry
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, ";") {
			continue
		}
		if p, s, ok := strings.Cut(line, "\t"); ok {
			out = append(out, manifestEntry{filepath.FromSlash(strings.TrimSpace(p)), strings.TrimSpace(s)})
		}
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

// applyEUTables swaps the EU copies in. -> a note for the log; nothing is swapped when any copy is missing or stale.
func applyEUTables(dir string) string {
	if n := restoreTables(dir); n > 0 {
		logf("US tables put back first: %d files (a previous EU start did not end cleanly)", n)
	}
	entries, err := readManifest(dir)
	if err != nil || len(entries) == 0 {
		return "client tables: US (no " + manifestName + ": run `python -m tools.eu_rules build` in Emulator/)"
	}
	for _, e := range entries {
		x := filepath.Join(dir, e.path)
		sum, err := fileSum(x)
		if err != nil {
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		if sum != e.sum {
			return fmt.Sprintf("client tables: US (%s changed since its EU copy was made: run `python -m tools.eu_rules build`)", e.path)
		}
		if _, err := os.Stat(x + ".eu"); err != nil {
			return fmt.Sprintf("client tables: US (%s.eu missing: run `python -m tools.eu_rules build`)", e.path)
		}
	}
	var done []string
	for _, e := range entries {
		x := filepath.Join(dir, e.path)
		if err := os.Rename(x, x+".us"); err != nil {
			restoreTables(dir)
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		if err := copyFile(x+".eu", x); err != nil {
			restoreTables(dir)
			return fmt.Sprintf("client tables: US (%s: %v)", e.path, err)
		}
		done = append(done, e.path)
	}
	return "client tables: EU (" + strings.Join(done, ", ") + ")"
}
