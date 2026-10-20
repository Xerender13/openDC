package main

// NayaPack (.agt) reading, for the files the launcher needs from a packed client (Emulator/tools/agt.py has the
// format; Emulator/tools/pack_client.py packs the 2016 client): every byte after the 32-byte header is XORed with
// naya by its file position; header +16 = the entry count; each entry (i32 data position, i32 chunk count, i32 size,
// i32 name length, name) points to u16 chunk lengths and the zlib chunks (16 KiB each when unpacked).

import (
	"bytes"
	"compress/zlib"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"strings"
)

var naya = []byte{0x01, 0x05, 0x06, 0x02, 0x04, 0x03, 0x07, 0x08, 0x01, 0x05, 0x06, 0x0F, 0x04, 0x03, 0x07, 0x0C,
	0x31, 0x85, 0x76, 0x39, 0x34, 0x3D, 0x30, 0xE8, 0x67, 0x36, 0x36, 0x32, 0x3E, 0x33, 0x34, 0x3B,
	0x11, 0x15, 0x16, 0x16, 0x14, 0x13, 0x1D, 0x18, 0x11, 0x03, 0x06, 0x0C, 0x04, 0x03, 0x06, 0x08,
	0x2E, 0x55, 0x26, 0x23, 0x2A, 0x23, 0x2E, 0x28, 0x21, 0x21, 0x26, 0x27, 0x2E, 0x00, 0x2D, 0x2D,
	0xCF, 0xA5, 0x06, 0x02, 0x04, 0x0F, 0x07, 0x18, 0xE1, 0x15, 0x36, 0x18, 0x60, 0x13, 0x1A, 0x19,
	0x11, 0x15, 0x16, 0x10, 0x12, 0x13, 0x17, 0x38, 0xF1, 0x25}

// packEntry: the unpacked entry name (any case) of the pack at path.
func packEntry(path, name string) ([]byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(raw) < 32 || string(raw[:8]) != "NayaPack" {
		return nil, fmt.Errorf("%s: not a NayaPack file", path)
	}
	for i := 32; i < len(raw); i++ {
		raw[i] ^= naya[i%len(naya)]
	}
	n, pos := int(int32(binary.LittleEndian.Uint32(raw[16:]))), 32
	for k := 0; k < n && pos+16 <= len(raw); k++ {
		at := int(binary.LittleEndian.Uint32(raw[pos:]))
		chunks := int(binary.LittleEndian.Uint32(raw[pos+4:]))
		size := int(binary.LittleEndian.Uint32(raw[pos+8:]))
		nlen := int(binary.LittleEndian.Uint32(raw[pos+12:]))
		pos += 16
		if pos+nlen > len(raw) {
			break
		}
		entry := string(raw[pos : pos+nlen])
		pos += nlen
		if !strings.EqualFold(entry, name) {
			continue
		}
		var out bytes.Buffer
		data := at + 2*chunks
		for c := 0; c < chunks && data <= len(raw); c++ {
			l := int(binary.LittleEndian.Uint16(raw[at+2*c:]))
			if data+l > len(raw) {
				break
			}
			if zr, err := zlib.NewReader(bytes.NewReader(raw[data : data+l])); err == nil {
				io.Copy(&out, zr) // lenient, as agt.py: a short last chunk may not be a complete stream
			}
			data += l
		}
		b := out.Bytes()
		if len(b) > size {
			b = b[:size]
		}
		return b, nil
	}
	return nil, fmt.Errorf("%s: no entry %s", path, name)
}
