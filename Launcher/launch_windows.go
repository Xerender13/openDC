//go:build windows && 386

package main

// Windows: no debugger (ASProtect stops unpacking under one: tried, the client hung). The client is started
// normally; the launcher opens it for memory access and polls: once it has unpacked, the address slots are
// overwritten, and once the protection object exists, a GameGuard object gets the vtable of the object whose
// checks all succeed (the Linux launcher's fallback; tested under Proton: the client runs). The client may
// restart itself: every new DriftCity.exe process is patched the same way.

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const lineEnd = "\r\n"

var (
	kernel32                     = syscall.NewLazyDLL("kernel32.dll")
	advapi32                     = syscall.NewLazyDLL("advapi32.dll")
	procCreateProcessW           = kernel32.NewProc("CreateProcessW")
	procOpenProcess              = kernel32.NewProc("OpenProcess")
	procReadProcessMemory        = kernel32.NewProc("ReadProcessMemory")
	procWriteProcessMemory       = kernel32.NewProc("WriteProcessMemory")
	procGetExitCodeProcess       = kernel32.NewProc("GetExitCodeProcess")
	procGetTickCount             = kernel32.NewProc("GetTickCount")
	procCloseHandle              = kernel32.NewProc("CloseHandle")
	procCreateToolhelp32Snapshot = kernel32.NewProc("CreateToolhelp32Snapshot")
	procProcess32FirstW          = kernel32.NewProc("Process32FirstW")
	procProcess32NextW           = kernel32.NewProc("Process32NextW")
	procRegCreateKeyExW          = advapi32.NewProc("RegCreateKeyExW")
	procRegSetValueExW           = advapi32.NewProc("RegSetValueExW")
	procRegCloseKey              = advapi32.NewProc("RegCloseKey")
)

const (
	processAccess    = 0x0400 | 0x0010 | 0x0020 | 0x0008 // QUERY_INFORMATION, VM_READ, VM_WRITE, VM_OPERATION
	stillActive      = 259
	th32csSnapProcess = 0x2
	hkeyLocalMachine = 0x80000002
	keyWow6432       = 0x0200
	keySetValue      = 0x0002
	regDword         = 4
)

type startupInfo struct {
	Cb                                       uint32
	_, Desktop, Title                        *uint16
	X, Y, XSize, YSize, XCount, YCount, Fill uint32
	Flags                                    uint32
	ShowWindow, _                            uint16
	_                                        *byte
	StdIn, StdOut, StdErr                    syscall.Handle
}

type processInfo struct {
	Process, Thread     syscall.Handle
	ProcessID, ThreadID uint32
}

type processEntry struct { // PROCESSENTRY32W
	Size, Usage, ProcessID   uint32
	DefaultHeapID            uintptr
	ModuleID, Threads        uint32
	ParentProcessID          uint32
	PriClassBase             int32
	Flags                    uint32
	ExeFile                  [260]uint16
}

func pause() {
	fmt.Println("Press Enter to close.")
	bufio.NewReader(os.Stdin).ReadString('\n')
}

func tickCount() uint64 {
	r, _, _ := procGetTickCount.Call()
	return uint64(uint32(r))
}

func closeHandle(h syscall.Handle) {
	if h != 0 {
		procCloseHandle.Call(uintptr(h))
	}
}

func readMem(h syscall.Handle, addr uint32, n int) []byte {
	b := make([]byte, n)
	var got uintptr
	r, _, _ := procReadProcessMemory.Call(uintptr(h), uintptr(addr), uintptr(unsafe.Pointer(&b[0])), uintptr(n), uintptr(unsafe.Pointer(&got)))
	if r == 0 || int(got) != n {
		return nil
	}
	return b
}

func writeMem(h syscall.Handle, addr uint32, b []byte) bool {
	var got uintptr
	r, _, _ := procWriteProcessMemory.Call(uintptr(h), uintptr(addr), uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)), uintptr(unsafe.Pointer(&got)))
	return r != 0
}

func alive(h syscall.Handle) bool {
	var code uint32
	r, _, _ := procGetExitCodeProcess.Call(uintptr(h), uintptr(unsafe.Pointer(&code)))
	return r != 0 && code == stillActive
}

// clientPids: the running DriftCity.exe processes.
func clientPids() map[uint32]bool {
	out := map[uint32]bool{}
	snap, _, _ := procCreateToolhelp32Snapshot.Call(th32csSnapProcess, 0)
	if snap == uintptr(syscall.InvalidHandle) {
		return out
	}
	defer procCloseHandle.Call(snap)
	var e processEntry
	e.Size = uint32(unsafe.Sizeof(e))
	for r, _, _ := procProcess32FirstW.Call(snap, uintptr(unsafe.Pointer(&e))); r != 0; r, _, _ = procProcess32NextW.Call(snap, uintptr(unsafe.Pointer(&e))) {
		if strings.EqualFold(syscall.UTF16ToString(e.ExeFile[:]), "DriftCity.exe") {
			out[e.ProcessID] = true
		}
	}
	return out
}

// patch one client process. -> what was done
func patch(h syscall.Handle, ip string) []string {
	var done []string
	t0 := time.Now()
	note := func(s string) { done = append(done, fmt.Sprintf("%s @%.2fs", s, time.Since(t0).Seconds())) }
	address := false
	for time.Since(t0) < 90*time.Second {
		if !alive(h) {
			return append(done, "process gone")
		}
		if !address {
			if b := readMem(h, addrLive, 13); b != nil && bytes.Equal(b, liveAddress) {
				writeMem(h, addrLive, addressBytes(ip))
				writeMem(h, addrAlpha, addressBytes(ip))
				address = true
				note("address")
			}
		} else if ob := readMem(h, ggObject, 4); ob != nil && binary.LittleEndian.Uint32(ob) != 0 {
			obj := binary.LittleEndian.Uint32(ob)
			if vt := readMem(h, obj, 4); vt != nil {
				switch v := binary.LittleEndian.Uint32(vt); v {
				case ggVtable:
					writeMem(h, obj, binary.LittleEndian.AppendUint32(nil, noGGVtable))
					note("GameGuard object replaced")
				default:
					note(fmt.Sprintf("protection object vtable %#x", v))
				}
				return done
			}
		}
		time.Sleep(time.Millisecond)
	}
	return append(done, "timeout")
}

func setWindowed(on bool) {
	var key syscall.Handle
	name, _ := syscall.UTF16PtrFromString(`SOFTWARE\DriftCity`)
	r, _, _ := procRegCreateKeyExW.Call(hkeyLocalMachine, uintptr(unsafe.Pointer(name)), 0, 0, 0,
		keySetValue|keyWow6432, 0, uintptr(unsafe.Pointer(&key)), 0)
	if r != 0 {
		logf("display: cannot write HKLM\\SOFTWARE\\DriftCity (run the launcher once as administrator); only goption.ini is set")
		return
	}
	defer procRegCloseKey.Call(uintptr(key))
	v, _ := syscall.UTF16PtrFromString("EnableWindowMode")
	val := uint32(0)
	if on {
		val = 1
	}
	procRegSetValueExW.Call(uintptr(key), uintptr(unsafe.Pointer(v)), 0, regDword, uintptr(unsafe.Pointer(&val)), 4)
}

func launch(dir, ip string, cfg Config) error {
	windowed := displayWindowed(cfg, false)
	setOptions(dir, windowed, cfg.get("client.main_ui_type", "1"))
	logf("display: %s", map[bool]string{true: "windowed", false: "fullscreen"}[windowed])
	setWindowed(windowed)
	old := clientPids()
	tok := token(tickCount())
	logf("token %s", tok)
	cmdline, _ := syscall.UTF16PtrFromString(fmt.Sprintf(`"%s\DriftCity.exe" /runsw %s`, dir, tok))
	wdir, _ := syscall.UTF16PtrFromString(dir)
	var si startupInfo
	si.Cb = uint32(unsafe.Sizeof(si))
	var pi processInfo
	r, _, e := procCreateProcessW.Call(0, uintptr(unsafe.Pointer(cmdline)), 0, 0, 0, 0, 0,
		uintptr(unsafe.Pointer(wdir)), uintptr(unsafe.Pointer(&si)), uintptr(unsafe.Pointer(&pi)))
	if r == 0 {
		return fmt.Errorf("starting DriftCity.exe: %v", e)
	}
	closeHandle(pi.Thread)
	seen := map[uint32]bool{pi.ProcessID: true}
	logf("client pid %d", pi.ProcessID)
	logf("patched: %s", strings.Join(patch(pi.Process, ip), ", "))
	patches := patchesFor(cfg)
	icons := patches.icons || patches.cargo || patches.slot
	if icons {
		go keepPatches(int(pi.ProcessID), patches, winRead(pi.Process), winWrite(pi.Process))
	}
	// the client may restart itself: patch new instances while one runs
	running := func() bool { // a client started by us is still running
		for pid := range clientPids() {
			if !old[pid] {
				return true
			}
		}
		return alive(pi.Process)
	}
	for running() {
		for pid := range clientPids() {
			if old[pid] || seen[pid] {
				continue
			}
			seen[pid] = true
			h, _, _ := procOpenProcess.Call(processAccess, 0, uintptr(pid))
			if h == 0 {
				continue
			}
			logf("client pid %d", pid)
			logf("patched: %s", strings.Join(patch(syscall.Handle(h), ip), ", "))
			if icons {
				go func(pid uint32, h syscall.Handle) {
					keepPatches(int(pid), patches, winRead(h), winWrite(h))
					closeHandle(h)
				}(pid, syscall.Handle(h))
			} else {
				closeHandle(syscall.Handle(h))
			}
		}
		time.Sleep(20 * time.Millisecond)
	}
	closeHandle(pi.Process)
	logf("done")
	return nil
}

// winRead / winWrite access a client's memory through its process handle; winRead returns nil once it has exited.
func winRead(h syscall.Handle) func(uint32, int) []byte {
	return func(addr uint32, n int) []byte {
		if !alive(h) {
			return nil
		}
		if b := readMem(h, addr, n); b != nil {
			return b
		}
		return make([]byte, n) // not mapped yet: zeros
	}
}

func winWrite(h syscall.Handle) func(uint32, []byte) bool {
	return func(addr uint32, b []byte) bool { return writeMem(h, addr, b) }
}
