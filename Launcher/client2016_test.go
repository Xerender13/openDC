package main

import (
	"bytes"
	"testing"
)

func TestRaceRecharge2016(t *testing.T) {
	writes, err := writes2016(t.TempDir(), "127.0.0.1", Config{"client.guided_tutorial": "0"})
	if err != nil {
		t.Fatal(err)
	}
	for _, patch := range writes {
		if patch.addr != raceRecharge2016 {
			continue
		}
		for _, matches := range []bool{true, false} {
			original := bytes.Clone(patch.orig)
			if !matches {
				original[0] ^= 0xff
			}
			memory := map[uint32][]byte{portCode2016: portPrefix2016, patch.addr: original}
			read := func(addr uint32, _ int) []byte { return memory[addr] }
			write := func(addr uint32, data []byte) bool { memory[addr] = data; return true }
			apply2016([]write2016{patch}, read, write)
			want := original
			if matches {
				want = patch.b
			}
			if got := memory[patch.addr]; !bytes.Equal(got, want) {
				t.Errorf("original bytes match = %v, got %x, want %x", matches, got, want)
			}
		}
		return
	}
	t.Fatal("2016 launch omits the race recharge patch")
}
