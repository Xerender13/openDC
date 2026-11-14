package main

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func setupTables(t *testing.T, sumOf string) (dir, x string) {
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
	if note := applyEUTables(dir); !strings.HasPrefix(note, "client tables: EU") {
		t.Fatalf("apply: %s", note)
	}
	if read(t, x) != "eu tables" || read(t, x+".us") != "us tables" {
		t.Fatal("EU copy not in place")
	}
	// a second start (a crash left the EU copy in place) puts the US file back first, then swaps again
	if note := applyEUTables(dir); !strings.HasPrefix(note, "client tables: EU") || read(t, x+".us") != "us tables" {
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
	if note := applyEUTables(t.TempDir()); !strings.HasPrefix(note, "client tables: US") {
		t.Fatal(note)
	}
}

func TestNationSendPatch(t *testing.T) {
	p := nationSendPatch()
	if len(p) != len(nationSendOrig2011) || len(p) != len(nationSendOrig2016) || p[0] != 0x6a || p[1] != 8 || p[2] != 0x90 {
		t.Fatalf("% x", p)
	}
	// the 2011 / 2016 code differs only in the call targets
	if p := nationSendOrig2016; p[5] != 0x83 || p[25] != 0x50 {
		t.Fatal("2016 pattern")
	}
}
