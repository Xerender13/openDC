package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func setupTables(t *testing.T, sumOf string) (dir, x string) {
	euRules = true
	t.Cleanup(func() { euRules = false })
	dir = t.TempDir()
	x = filepath.Join(dir, "Patch", "Patch.000")
	if err := os.MkdirAll(filepath.Dir(x), 0o755); err != nil {
		t.Fatal(err)
	}
	os.WriteFile(x, []byte("us tables"), 0o644)
	os.WriteFile(x+".eu", []byte("eu tables"), 0o644)
	s := sha256.Sum256([]byte(sumOf))
	os.WriteFile(filepath.Join(dir, manifestName), []byte("; EU copies\nPatch/Patch.000\t"+hex.EncodeToString(s[:])+"\n"), 0o644)
	return dir, x
}

func read(t *testing.T, p string) string {
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func TestSwapAndRestore(t *testing.T) {
	dir, x := setupTables(t, "us tables")
	if note := applyEUTables(dir); !strings.HasPrefix(note, "client tables: Patch") {
		t.Fatalf("apply: %s", note)
	}
	if read(t, x) != "eu tables" || read(t, x+".us") != "us tables" {
		t.Fatal("EU copy not in place")
	}
	// a second start (a crash left the EU copy in place) puts the US file back first, then swaps again
	if note := applyEUTables(dir); !strings.HasPrefix(note, "client tables: Patch") || read(t, x+".us") != "us tables" {
		t.Fatalf("second apply: %s", note)
	}
	if n := restoreTables(dir); n != 1 || read(t, x) != "us tables" {
		t.Fatalf("restore: %d, %q", n, read(t, x))
	}
	if _, err := os.Stat(x + ".us"); err == nil {
		t.Fatal(".us left behind")
	}
}

func TestStaleCopyNotUsed(t *testing.T) {
	dir, x := setupTables(t, "older us tables")
	if note := applyEUTables(dir); !strings.Contains(note, "changed since") {
		t.Fatalf("stale: %s", note)
	}
	if read(t, x) != "us tables" {
		t.Fatal("stale copy swapped in")
	}
}

func TestNoManifest(t *testing.T) {
	if note := applyEUTables(t.TempDir()); !strings.HasPrefix(note, "client tables: original") {
		t.Fatal(note)
	}
}

func TestNationSendPatch(t *testing.T) {
	euRules, kph = true, false
	defer func() { euRules, kph = false, false }()
	p := nationSendPatch()
	if len(p) != len(nationSendOrig2011) || len(p) != len(nationSendOrig2016) || p[0] != 0x68 ||
		binary.LittleEndian.Uint32(p[1:5]) != 8 || p[5] != 0x90 {
		t.Fatalf("% x", p)
	}
	euRules, kph = false, true
	if v := binary.LittleEndian.Uint32(nationSendPatch()[1:5]); v != 0x10001 {
		t.Fatalf("US + km/h: %#x", v)
	}
	// the 2011 / 2016 code differs only in the call targets
	if p := nationSendOrig2016; p[5] != 0x83 || p[25] != 0x50 {
		t.Fatal("2016 pattern")
	}
}

func TestVariants(t *testing.T) {
	defer func() { euRules, kph = false, false }()
	e := manifestEntry{"Patch/Patch.006", "x", []string{"eu", "kph"}}
	cases := []struct {
		eu, k bool
		want  string
	}{{false, false, ""}, {true, false, "eu"}, {false, true, "kph"}, {true, true, "eu.kph"}}
	for _, c := range cases {
		euRules, kph = c.eu, c.k
		if got := variant(e); got != c.want {
			t.Fatalf("%v %v: %q", c.eu, c.k, got)
		}
	}
	euRules, kph = true, true
	if got := variant(manifestEntry{"Data_US/gameui/game.nui", "x", []string{"kph"}}); got != "kph" {
		t.Fatal(got)
	}
}

func TestUnitPatchesInExes(t *testing.T) {
	for _, c := range []struct {
		path string
		is16 bool
	}{{"../Client US/DriftCityUS.exe", false}, {"../DriftCity Dev Ed/DriftCity.exe", true}} {
		if _, err := os.Stat(c.path); err != nil {
			t.Skip("no client here")
		}
		if !unitsInFile(c.path, c.is16) || !nationSendInFile(c.path, c.is16) {
			t.Fatalf("%s: original bytes not found", c.path)
		}
	}
}
