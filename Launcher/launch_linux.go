//go:build linux

package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const lineEnd = "\n"

// ptrace needs every request from the thread that attached: the whole launcher runs on the main thread.
func init() { runtime.LockOSThread() }

func pause() {}

var debug = os.Getenv("DRIFTCITY_DEBUG") != ""

const (
	ptracePokeUser    = 6
	ptraceGetRegs     = 12
	ptraceSetRegs     = 13
	ptraceCont        = 7
	ptraceDetach      = 17
	ptraceGetEventMsg = 0x4201
	ptraceSeize       = 0x4206
	ptraceInterrupt   = 0x4207
	ptraceOTraceClone = 8
	eventClone        = 3
	eventStop         = 0x80
	debugReg          = 848 // offsetof(struct user, u_debugreg), x86_64
	wAll              = 0x40000000
	prSetChildSubreaper = 36
)

func ptrace(req int, tid int, addr, data uintptr) error {
	_, _, e := syscall.RawSyscall6(syscall.SYS_PTRACE, uintptr(req), uintptr(tid), addr, data, 0, 0)
	if e != 0 {
		return e
	}
	return nil
}

func tickCount() uint64 { // GetTickCount under Wine: CLOCK_MONOTONIC in milliseconds
	var ts syscall.Timespec
	syscall.Syscall(syscall.SYS_CLOCK_GETTIME, 1, uintptr(unsafe.Pointer(&ts)), 0)
	return uint64(ts.Sec)*1000 + uint64(ts.Nsec)/1000000
}

func expand(p string) string {
	if strings.HasPrefix(p, "~/") {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, p[2:])
	}
	return p
}

// findProton: the configured script, else the newest "Proton N.M" in the Steam library.
func findProton(cfg Config) (string, error) {
	if p := cfg.get("linux.proton", ""); p != "" {
		return expand(p), nil
	}
	steam := expand(cfg.get("linux.steam", "~/.local/share/Steam"))
	matches, _ := filepath.Glob(filepath.Join(steam, "steamapps", "common", "Proton *", "proton"))
	type cand struct {
		path string
		ver  []int
	}
	var cs []cand
	for _, m := range matches {
		name := filepath.Base(filepath.Dir(m))
		var ver []int
		for _, f := range strings.FieldsFunc(strings.TrimPrefix(name, "Proton "), func(r rune) bool { return r == '.' || r == ' ' }) {
			n, err := strconv.Atoi(f)
			if err != nil {
				break
			}
			ver = append(ver, n)
		}
		if len(ver) > 0 && !strings.Contains(name, "Beta") {
			cs = append(cs, cand{m, ver})
		}
	}
	if len(cs) == 0 {
		return "", fmt.Errorf("no Proton found in %s/steamapps/common (install one in Steam, or set [linux] proton / runner = wine in DriftCityLauncher.ini)", steam)
	}
	sort.Slice(cs, func(i, j int) bool {
		a, b := cs[i].ver, cs[j].ver
		for k := 0; k < len(a) && k < len(b); k++ {
			if a[k] != b[k] {
				return a[k] > b[k]
			}
		}
		return len(a) > len(b)
	})
	return cs[0].path, nil
}

type runner struct {
	cmd []string // the program that runs a Windows program, e.g. [proton run]
	env []string
}

func (r runner) command(dir string, args ...string) *exec.Cmd {
	c := exec.Command(r.cmd[0], append(append([]string{}, r.cmd[1:]...), args...)...)
	c.Dir, c.Env = dir, r.env
	return c
}

// cursorLibs: the client is 32-bit and Wine draws its colour cursors (Data/GameUI/cursor/*.cur) with libXcursor;
// without a 32-bit libXcursor (SteamOS has none in /usr/lib32, nor libXrender) Wine falls back to two-colour
// cursors: the pale hand instead of the blue glove (user, 2026-10-14; Drift City Remastered, started by Steam inside
// the Steam Linux Runtime, which has them, showed the glove). When the host lacks it, the two libraries of the
// installed Steam Linux Runtime (sniper) are linked into <prefix>/lib32 for LD_LIBRARY_PATH. -> that folder or "".
func cursorLibs(cfg Config, prefix string) string {
	for _, d := range []string{"/usr/lib32", "/usr/lib/i386-linux-gnu", "/lib/i386-linux-gnu"} {
		if _, err := os.Stat(filepath.Join(d, "libXcursor.so.1")); err == nil {
			return ""
		}
	}
	steam := expand(cfg.get("linux.steam", "~/.local/share/Steam"))
	dirs, _ := filepath.Glob(filepath.Join(steam, "steamapps", "common", "SteamLinuxRuntime_sniper", "*", "files",
		"lib", "i386-linux-gnu"))
	sort.Strings(dirs)
	src, dst := "", filepath.Join(prefix, "lib32")
	for i := len(dirs) - 1; i >= 0 && src == ""; i-- {
		if m, _ := filepath.Glob(filepath.Join(dirs[i], "libXcursor.so.1*")); len(m) > 0 {
			src = dirs[i]
		}
	}
	if src == "" {
		logf("no 32-bit libXcursor (host or Steam Linux Runtime sniper): the mouse cursor stays two-colour")
		return ""
	}
	_ = os.MkdirAll(dst, 0o755)
	for _, lib := range []string{"libXcursor.so.1", "libXrender.so.1"} {
		m, _ := filepath.Glob(filepath.Join(src, lib+"*")) // the runtime has only the versioned file (.so.1.0.2)
		if len(m) == 0 {
			logf("cursor libraries: no %s in %s", lib, src)
			return ""
		}
		sort.Strings(m)
		target, err := filepath.EvalSymlinks(m[len(m)-1])
		if err != nil {
			logf("cursor libraries: %v", err)
			return ""
		}
		link := filepath.Join(dst, lib)
		_ = os.Remove(link)
		if err := os.Symlink(target, link); err != nil {
			logf("cursor libraries: %v", err)
			return ""
		}
	}
	logf("32-bit cursor libraries from %s", src)
	return dst
}

func makeRunner(cfg Config) (runner, error) {
	prefix := expand(cfg.get("linux.prefix", "~/.local/share/drift2011-pfx"))
	env := append(os.Environ(), "WINEDEBUG="+envOr("DRIFTCITY_WINEDEBUG", "err+seh,+msgbox"))
	if libs := cursorLibs(cfg, prefix); libs != "" {
		env = setEnv(env, "LD_LIBRARY_PATH", strings.Trim(libs+":"+os.Getenv("LD_LIBRARY_PATH"), ":"))
	}
	if cfg.get("linux.runner", "proton") == "wine" {
		pfx := filepath.Join(prefix, "pfx")
		_ = os.MkdirAll(pfx, 0o755)
		return runner{[]string{cfg.get("linux.wine", "wine")}, append(env, "WINEPREFIX="+pfx)}, nil
	}
	proton, err := findProton(cfg)
	if err != nil {
		return runner{}, err
	}
	_ = os.MkdirAll(prefix, 0o755)
	logf("Proton %s, prefix %s", proton, prefix)
	return runner{[]string{proton, "run"}, append(env,
		"STEAM_COMPAT_CLIENT_INSTALL_PATH="+expand(cfg.get("linux.steam", "~/.local/share/Steam")),
		"STEAM_COMPAT_DATA_PATH="+prefix)}, nil
}

// setEnv: env with k=v (replacing an existing k).
func setEnv(env []string, k, v string) []string {
	out := env[:0:0]
	for _, e := range env {
		if !strings.HasPrefix(e, k+"=") {
			out = append(out, e)
		}
	}
	return append(out, k+"="+v)
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

// descendant: pid is a child, grandchild, ... of this launcher (clients of other launchers are left alone).
func descendant(pid int) bool {
	me := os.Getpid()
	for i := 0; i < 64 && pid > 1; i++ {
		st, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
		if err != nil {
			return false
		}
		f := strings.Fields(string(st[bytes.LastIndexByte(st, ')')+1:]))
		if len(f) < 2 {
			return false
		}
		pid, _ = strconv.Atoi(f[1])
		if pid == me {
			return true
		}
	}
	return false
}

// clientPids: the Wine processes running the client (clientExe).
func clientPids() []int {
	var out []int
	ents, _ := os.ReadDir("/proc")
	for _, e := range ents {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		argv, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
		if err != nil {
			continue
		}
		first := strings.ToLower(string(bytes.SplitN(argv, []byte{0}, 2)[0]))
		if strings.HasSuffix(first, strings.ToLower(clientExe)) {
			out = append(out, pid)
		}
	}
	return out
}

// anyClientPids: running Drift City clients of any folder (US, EU or the packed exe), not only clientExe.
func anyClientPids() []int {
	var out []int
	ents, _ := os.ReadDir("/proc")
	for _, e := range ents {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		argv, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
		if err != nil {
			continue
		}
		first := strings.ToLower(string(bytes.SplitN(argv, []byte{0}, 2)[0]))
		for _, exe := range []string{"driftcityus.exe", "driftcityeu.exe", "driftcity.exe", "driftcity2016test.exe"} {
			if strings.HasSuffix(first, exe) {
				out = append(out, pid)
				break
			}
		}
	}
	return out
}

// withoutSteamIDs: env without the variables that make Proton's steam.exe act as a Steam game.
func withoutSteamIDs(env []string) []string {
	out := env[:0:0]
	for _, e := range env {
		k := strings.SplitN(e, "=", 2)[0]
		if k == "SteamAppId" || k == "SteamGameId" || k == "SteamOverlayGameId" || k == "STEAM_COMPAT_APP_ID" {
			continue
		}
		out = append(out, e)
	}
	return out
}

func setBreakpoint(tid int, addr uintptr) {
	if addr != 0 {
		ptrace(ptracePokeUser, tid, debugReg, addr)
	}
	dr7 := uintptr(0)
	if addr != 0 {
		dr7 = 1
	}
	ptrace(ptracePokeUser, tid, debugReg+7*8, dr7)
}

// tracer: a hardware breakpoint on ggSwitch in every thread of one client process.
type tracer struct {
	pid  int
	tids map[int]bool
	hit  bool
}

func newTracer(pid int) *tracer {
	t := &tracer{pid: pid, tids: map[int]bool{}}
	ents, _ := os.ReadDir(fmt.Sprintf("/proc/%d/task", pid))
	for _, e := range ents {
		if tid, err := strconv.Atoi(e.Name()); err == nil {
			t.add(tid)
		}
	}
	return t
}

func (t *tracer) add(tid int) {
	if ptrace(ptraceSeize, tid, 0, ptraceOTraceClone) != nil {
		return
	}
	ptrace(ptraceInterrupt, tid, 0, 0)
	var ws syscall.WaitStatus
	if p, _ := syscall.Wait4(tid, &ws, wAll, nil); p == tid {
		setBreakpoint(tid, ggSwitch)
		ptrace(ptraceCont, tid, 0, 0)
		t.tids[tid] = true
	}
}

// poll handles pending stops; true when the switch was redirected.
func (t *tracer) poll() bool {
	hit := false
	for {
		var ws syscall.WaitStatus
		tid, err := syscall.Wait4(-1, &ws, wAll|syscall.WNOHANG, nil)
		if err != nil || tid <= 0 {
			return hit
		}
		if !ws.Stopped() {
			delete(t.tids, tid)
			continue
		}
		sig, event := ws.StopSignal(), int(ws>>16)
		if debug {
			logf("stop tid %d sig %d event %d", tid, sig, event)
		}
		switch {
		case event == eventClone:
			var msg uintptr
			ptrace(ptraceGetEventMsg, tid, 0, uintptr(unsafe.Pointer(&msg)))
			t.tids[int(msg)] = true
			ptrace(ptraceCont, tid, 0, 0)
		case event == eventStop: // a new thread (or an interrupt): arm it
			if !t.hit {
				setBreakpoint(tid, ggSwitch)
			}
			ptrace(ptraceCont, tid, 0, 0)
		case sig == syscall.SIGTRAP:
			var r [27]uint64 // user_regs_struct (x86_64); rip = [16]
			err := ptrace(ptraceGetRegs, tid, 0, uintptr(unsafe.Pointer(&r[0])))
			if debug {
				logf("SIGTRAP tid %d rip %#x err %v", tid, r[16], err)
			}
			if err == nil && r[16]&0xffffffff == ggSwitch {
				r[16] = noGGBranch
				ptrace(ptraceSetRegs, tid, 0, uintptr(unsafe.Pointer(&r[0])))
				t.hit, hit = true, true
				ptrace(ptraceCont, tid, 0, 0)
			} else {
				ptrace(ptraceCont, tid, 0, uintptr(sig))
			}
		default:
			s := uintptr(sig)
			if sig == syscall.SIGSTOP {
				s = 0
			}
			ptrace(ptraceCont, tid, 0, s)
		}
	}
}

func (t *tracer) detach() {
	for tid := range t.tids {
		if ptrace(ptraceInterrupt, tid, 0, 0) == nil {
			var ws syscall.WaitStatus
			if p, _ := syscall.Wait4(tid, &ws, wAll, nil); p == tid {
				setBreakpoint(tid, 0)
				ptrace(ptraceDetach, tid, 0, 0)
			}
		}
	}
	t.tids = map[int]bool{}
}

// patch writes our address and steers the client past GameGuard. -> what was done
func patch(pid int, ip string) []string {
	var done []string
	t0 := time.Now()
	note := func(s string) { done = append(done, fmt.Sprintf("%s @%.2fs", s, time.Since(t0).Seconds())) }
	tr := newTracer(pid)
	note(fmt.Sprintf("breakpoint set in %d threads", len(tr.tids)))
	defer tr.detach()
	addressDone := false
	read, write := procRead(pid), procWrite(pid)
	for time.Since(t0) < 90*time.Second {
		if tr.poll() {
			note("GameGuard skipped")
		}
		m, err := os.OpenFile(fmt.Sprintf("/proc/%d/mem", pid), os.O_RDWR, 0)
		if err != nil {
			if _, e := os.Stat(fmt.Sprintf("/proc/%d", pid)); e != nil {
				return append(done, "process gone")
			}
			time.Sleep(2 * time.Millisecond)
			continue
		}
		if !addressDone {
			if n := writeAddress(read, write, ip); n > 0 {
				addressDone = true
				note(fmt.Sprintf("address (%d slots)", n))
			}
		}
		if addressDone {
			p := make([]byte, 4)
			if n, _ := m.ReadAt(p, ggObject); n == 4 {
				obj := int64(uint32(p[0]) | uint32(p[1])<<8 | uint32(p[2])<<16 | uint32(p[3])<<24)
				if obj != 0 {
					if n, _ := m.ReadAt(p, obj); n == 4 {
						vt := uint32(p[0]) | uint32(p[1])<<8 | uint32(p[2])<<16 | uint32(p[3])<<24
						if vt == ggVtable {
							v := uint32(noGGVtable)
							m.WriteAt([]byte{byte(v), byte(v >> 8), byte(v >> 16), byte(v >> 24)}, obj)
							note("object vtable swapped (breakpoint missed)")
						} else {
							note(fmt.Sprintf("protection object vtable %#x", vt))
						}
						m.Close()
						return done
					}
				}
			}
		}
		m.Close()
		time.Sleep(2 * time.Millisecond)
	}
	return append(done, "timeout")
}

func launch(dir, ip string, cfg Config) error {
	scope, _ := os.ReadFile("/proc/sys/kernel/yama/ptrace_scope")
	if s := strings.TrimSpace(string(scope)); s != "" && s != "0" && s != "1" {
		return fmt.Errorf("kernel.yama.ptrace_scope is %s: the client cannot be patched in memory. Run: sudo sysctl kernel.yama.ptrace_scope=1", s)
	}
	// the client restarts itself: orphaned client processes come back to us, so we may still trace them
	if _, _, e := syscall.RawSyscall6(syscall.SYS_PRCTL, prSetChildSubreaper, 1, 0, 0, 0, 0); e != 0 {
		logf("warning: could not become a child subreaper; patching may fail")
	}
	var ws []write2016
	if client2016 {
		var err error
		if ws, err = writes2016(dir, ip, cfg); err != nil {
			return err
		}
	}
	r, err := makeRunner(cfg)
	if err != nil {
		return err
	}
	windowed := displayWindowed(cfg, true)
	setOptions(dir, windowed, cfg.get("client.main_ui_type", "1"))
	mode := "0"
	if windowed {
		mode = "1"
	}
	logf("display: %s", map[bool]string{true: "windowed", false: "fullscreen"}[windowed])
	if others := anyClientPids(); len(others) > 0 {
		// a second client: Proton's steam.exe wrapper started with Steam's game ids hangs (before running anything)
		// when the prefix's running session was started outside Steam (user, 2026-10-18: the second launch stuck at
		// this reg add). Without the ids it runs; this client then has no Steam overlay.
		r.env = withoutSteamIDs(r.env)
		logf("client(s) already running %v: starting this one without the Steam game ids", others)
	}
	r.command(dir, "reg", "add", `HKLM\SOFTWARE\DriftCity`, "/v", "EnableWindowMode", "/t", "REG_DWORD",
		"/d", mode, "/f", "/reg:32").Run()
	old := map[int]bool{}
	for _, p := range clientPids() {
		old[p] = true
	}
	if len(old) > 0 {
		logf("ignoring running client(s) %v", old)
	}
	tok := token(tickCount(), clientEU)
	logf("token %s", tok)
	c := r.command(dir, "./"+clientExe, "/runsw", tok)
	if logFile != nil {
		c.Stdout, c.Stderr = logFile, logFile
	}
	if err := c.Start(); err != nil {
		return fmt.Errorf("starting the client: %v", err)
	}
	exited := make(chan error, 1)
	go func() { exited <- c.Wait() }()
	seen := map[int]bool{}
	for {
		select {
		case err := <-exited:
			logf("exit %v", err)
			return nil
		default:
		}
		for _, pid := range clientPids() {
			if !old[pid] && !seen[pid] && descendant(pid) {
				seen[pid] = true
				logf("client pid %d", pid)
				if client2016 {
					logf("patched: %s", strings.Join(patch2016Poll(ws, procRead(pid), procWrite(pid)), ", "))
					continue
				}
				logf("patched: %s", strings.Join(patch(pid, ip), ", "))
				if p := patchesFor(cfg); p.icons || p.cargo || p.slot {
					go keepPatches(pid, p, procRead(pid), procWrite(pid))
				}
			}
		}
		time.Sleep(2 * time.Millisecond)
	}
}

// procRead / procWrite access a client's memory through /proc/PID/mem (we are its ancestor: ptrace_scope 0 or 1).
func procRead(pid int) func(uint32, int) []byte {
	return func(addr uint32, n int) []byte {
		m, err := os.Open(fmt.Sprintf("/proc/%d/mem", pid))
		if err != nil {
			return nil
		}
		defer m.Close()
		b := make([]byte, n)
		if k, _ := m.ReadAt(b, int64(addr)); k != n {
			if _, e := os.Stat(fmt.Sprintf("/proc/%d", pid)); e != nil {
				return nil
			}
			return make([]byte, n) // not mapped yet: zeros
		}
		return b
	}
}

func procWrite(pid int) func(uint32, []byte) bool {
	return func(addr uint32, b []byte) bool {
		m, err := os.OpenFile(fmt.Sprintf("/proc/%d/mem", pid), os.O_RDWR, 0)
		if err != nil {
			return false
		}
		defer m.Close()
		k, _ := m.WriteAt(b, int64(addr))
		return k == len(b)
	}
}
