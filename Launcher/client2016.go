package main

// The 2016 client (DriftCity Dev Ed: DriftCity.exe of 2016-02-16, or Emulator/tools/client2016.py's
// DriftCity2016Test.exe). It is not packed and has no GameGuard object: a community patch already removed both and
// made the login address function 0x54f6b0 always use the US slot (NOPs at 0x54f72e / 0x54f741: it reads
// Data/init/network.txt, then overwrites the result with the slot). The launcher writes, before 0x54f6b0 runs:
//   - the server address over that slot, 0x957760 (16 bytes, "127.0.0.1" in the exe)
//   - the auth port: 0x54f6bf is `mov word [0x9bc374], 11005`; its immediate (0x54f6c6) and the word itself
//     ([server] port; the 2016 emulator listens on 11105, emulator.ini [2016])
//   - the guided tutorial byte: 0x5ca8ed `cmp eax, 4` (GlobalContent ApprenticeFlowType) -> `cmp eax, 1`, the
//     same byte tools/tutorial_flow.py changes in the test exe. Table and byte must agree: mode 1 with the original
//     byte opens the Battle Zone window as soon as the training car is in Driver Dome (0x5ca914) ([client]
//     guided_tutorial = auto: from GlobalContent.xlt, packed or loose)
// Linux: the image is mapped long before its code runs (Wine loads ~30 DLLs first): the launcher polls the new
// process's memory until the port instruction is there, then writes. Windows: the client is started suspended.
// The 2011 memory patches (item icons, cargo camera, Visual Item slot) have other addresses in 2016: not applied.

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"
)

const (
	slot2016     = 0x957760
	portCode2016 = 0x54f6bf // mov word [0x9bc374], imm16 (66 c7 05 74 c3 9b 00 imm16)
	portData2016 = 0x9bc374
	guided2016   = 0x5ca8ed // cmp eax, 4 / 1 (83 f8 xx); jne 0x5ca914 (75 22)
	authPort     = 11005
)

var portPrefix2016 = []byte{0x66, 0xc7, 0x05, 0x74, 0xc3, 0x9b, 0x00}

// client2016: the client exe is the 2016 build (main).
var client2016 bool

// fileOffset2016: the exe file offset of a 2016 address (.text at file 0x400 -> 0x401000, the second section at
// file 0x540e00 -> 0x942000).
func fileOffset2016(addr uint32) int64 {
	if addr >= 0x942000 {
		return int64(addr) - 0x942000 + 0x540e00
	}
	return int64(addr) - 0x401000 + 0x400
}

// is2016: the exe's PE time stamp is 2016 or later. -> also an error when it is, but not the build we know.
func is2016(path string) (bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return false, nil
	}
	defer f.Close()
	head := make([]byte, 0x400)
	if n, _ := f.ReadAt(head, 0); n < 0x100 {
		return false, nil
	}
	pe := binary.LittleEndian.Uint32(head[0x3c:])
	if pe+12 > uint32(len(head)) {
		return false, nil
	}
	if time.Unix(int64(binary.LittleEndian.Uint32(head[pe+8:])), 0).UTC().Year() < 2016 {
		return false, nil
	}
	code := make([]byte, len(portPrefix2016))
	cmp := make([]byte, 5)
	f.ReadAt(code, fileOffset2016(portCode2016))
	f.ReadAt(cmp, fileOffset2016(guided2016))
	if !bytes.Equal(code, portPrefix2016) || cmp[0] != 0x83 || cmp[1] != 0xf8 || cmp[3] != 0x75 || cmp[4] != 0x22 {
		return true, fmt.Errorf("%s is a 2016 client, but not the Dev Ed build of 2016-02-16 this launcher knows", path)
	}
	return true, nil
}

// apprenticeFlow: GlobalContent ApprenticeFlowType (Value_US) of the 2016 table as the client reads it: the copy in
// Data/Localize.agt first (NiFile asks the packs first; Emulator/tools/pack_client.py), else the loose file; or 0.
func apprenticeFlow(dir string) int {
	b, err := packEntry(filepath.Join(dir, "Data", "Localize.agt"), `Localize\GlobalContent.xlt`)
	if err != nil {
		b, err = os.ReadFile(filepath.Join(dir, "Data", "Localize", "GlobalContent.xlt"))
	}
	if err != nil || len(b) < 2 {
		return 0
	}
	u := make([]uint16, len(b)/2)
	for i := range u {
		u[i] = binary.LittleEndian.Uint16(b[2*i:])
	}
	lines := strings.Split(string(utf16.Decode(u)), "\r\n")
	if len(lines) < 3 {
		return 0
	}
	col := -1
	for i, h := range strings.Split(lines[2], "\t") {
		if h == "Value_US" {
			col = i
		}
	}
	for _, l := range lines {
		c := strings.Split(l, "\t")
		if col >= 0 && len(c) > col && len(c) > 3 && c[3] == "ApprenticeFlowType" {
			n, _ := strconv.Atoi(strings.TrimSpace(c[col]))
			return n
		}
	}
	return 0
}

// writes2016: the memory writes of the settings: address -> bytes.
type write2016 struct {
	addr uint32
	b    []byte
	what string
}

func writes2016(dir, ip string, cfg Config) ([]write2016, error) {
	port, err := strconv.Atoi(cfg.get("server.port", strconv.Itoa(authPort)))
	if err != nil || port < 1 || port > 65535 {
		return nil, fmt.Errorf("[server] port %q: a port number is needed", cfg.get("server.port", ""))
	}
	slot := make([]byte, 16)
	copy(slot, ip)
	p := binary.LittleEndian.AppendUint16(nil, uint16(port))
	out := []write2016{{slot2016, slot, "address " + ip}, {portCode2016 + 7, p, ""},
		{portData2016, p, fmt.Sprintf("port %d", port)}}
	mode := 4
	switch cfg.get("client.guided_tutorial", "auto") {
	case "1":
		mode = 1
	case "0":
	default:
		if apprenticeFlow(dir) == 1 {
			mode = 1
		}
	}
	return append(out, write2016{guided2016 + 2, []byte{byte(mode)},
		map[bool]string{true: "guided tutorial", false: "tutorial as shipped"}[mode == 1]}), nil
}

// apply2016 writes once the image is mapped (the port instruction is readable). -> what was written, or nil while
// the image is not there yet; ok false when the process is gone.
func apply2016(ws []write2016, read func(uint32, int) []byte, write func(uint32, []byte) bool) (done []string, ok bool) {
	code := read(portCode2016, len(portPrefix2016))
	if code == nil {
		return nil, false
	}
	if !bytes.Equal(code, portPrefix2016) {
		return nil, true
	}
	for _, w := range ws {
		if !write(w.addr, w.b) || !bytes.Equal(read(w.addr, len(w.b)), w.b) {
			done = append(done, fmt.Sprintf("FAILED %#x", w.addr))
		} else if w.what != "" {
			done = append(done, w.what)
		}
	}
	return done, true
}

// patch2016Poll: apply2016 as soon as the image is mapped (at most 90 s). -> what was done
func patch2016Poll(ws []write2016, read func(uint32, int) []byte, write func(uint32, []byte) bool) []string {
	t0 := time.Now()
	for time.Since(t0) < 90*time.Second {
		done, ok := apply2016(ws, read, write)
		if !ok {
			return []string{"process gone"}
		}
		if done != nil {
			return append(done, fmt.Sprintf("@%.3fs", time.Since(t0).Seconds()))
		}
		time.Sleep(time.Millisecond)
	}
	return []string{"timeout"}
}
