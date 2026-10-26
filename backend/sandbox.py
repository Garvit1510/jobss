"""Isolated execution for untrusted candidate code (Accenture Round 4).

Layers (all applied in the forked child before exec):
  chroot into a minimal read-only jail (no /app, /proc, /root, /etc secrets, no backend env)
  per-program unprivileged uid from a pool (61001-61008), no supplementary groups
  rlimits: CPU, address space (Python/C++), file size, open files, process count
  seccomp (libseccomp, NO_NEW_PRIVS): socket(), io_uring, ptrace, bpf, mount/namespace, keyring and module syscalls -> EPERM
It is still a shared-kernel jail, not a container/VM. `verify()` proves the properties with live escape probes;
candidate code is refused (fail closed) unless the jail is built and every probe passed.
"""
import asyncio
import ctypes
import json
import logging
import os
import shutil
import subprocess

try:
    import resource
except ImportError:
    resource = None

log = logging.getLogger("sandbox")
JAIL = os.environ.get("SANDBOX_JAIL_DIR", "")
BUILD_VERSION = "jail-v1"
UIDS = list(range(61001, 61009))
DENY = ["socket", "io_uring_setup", "io_uring_enter", "io_uring_register", "ptrace", "process_vm_readv", "process_vm_writev", "bpf", "perf_event_open",
        "keyctl", "add_key", "request_key", "mount", "umount2", "pivot_root", "chroot", "unshare", "setns", "kexec_load", "init_module", "finit_module",
        "delete_module", "swapon", "swapoff", "reboot", "userfaultfd", "open_by_handle_at", "name_to_handle_at", "fanotify_init", "quotactl"]
_LOCK = asyncio.Lock()
STATE = {"built": False, "verified": False, "checks": [], "error": None, "verified_at": None}

try:
    _SC = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    _SC.seccomp_init.restype = ctypes.c_void_p
    _SC.seccomp_init.argtypes = [ctypes.c_uint32]
    _SC.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    _SC.seccomp_load.argtypes = [ctypes.c_void_p]
    _SC.seccomp_syscall_resolve_name.restype = ctypes.c_int
    _NRS = [n for n in (_SC.seccomp_syscall_resolve_name(s.encode()) for s in DENY) if n >= 0]
except OSError:
    _SC, _NRS = None, []
_libc = ctypes.CDLL(None, use_errno=True) if os.name != "nt" else None


class Unavailable(Exception):
    pass


def ready():
    return bool(JAIL) and STATE["built"] and STATE["verified"]


# ---------------- child-side setup ----------------
def preexec(uid, inner_cwd, cpu, mem_bytes, nproc=64):
    if resource is None or os.name == "nt":
        raise Unavailable("The isolated code sandbox requires Linux.")

    def fn():
        os.setsid()
        os.chroot(JAIL)
        os.chdir(inner_cwd)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if mem_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)
        if _libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            os._exit(121)
        ctx = _SC.seccomp_init(0x7FFF0000)  # default allow
        for nr in _NRS:
            _SC.seccomp_rule_add(ctx, 0x00050000 | 1, nr, 0)  # ERRNO(EPERM)
        if _SC.seccomp_load(ctx) != 0:
            os._exit(122)
    return fn


def new_workdir(uid):
    import tempfile
    host = tempfile.mkdtemp(prefix="r_", dir=os.path.join(JAIL, "work"))
    os.chown(host, uid, uid)
    os.chmod(host, 0o700)
    return host, "/work/" + os.path.basename(host)


# ---------------- jail build ----------------
BINS = ["/usr/bin/python3.11", "/usr/bin/node", "/usr/bin/g++", "/usr/bin/gcc", "/usr/bin/as", "/usr/bin/ld", "/usr/bin/ld.bfd",
        "/usr/lib/jvm/java-17-openjdk-arm64/bin/java", "/usr/lib/jvm/java-17-openjdk-arm64/bin/javac", "/usr/bin/sh", "/usr/bin/dash"]
TREES = ["/usr/lib/python3.11", "/usr/lib/gcc", "/usr/libexec/gcc", "/usr/include", "/usr/lib/jvm/java-17-openjdk-arm64", "/etc/java-17-openjdk"]
LIBGLOBS = ["crt1.o", "crti.o", "crtn.o", "Scrt1.o", "gcrt1.o", "rcrt1.o", "libc.so", "libc.a", "libc_nonshared.a", "libm.so", "libm.a", "libm-2*",
            "libmvec*", "libpthread*", "libdl*", "librt*", "libstdc++*", "libgcc_s*", "ld-linux*"]
SKIP = ("/site-packages", "/dist-packages", "/test/", "/tests/", "/idlelib", "/tkinter", "/ensurepip", "/__pycache__", "/demo", "/man/", "/src.zip")


def _copy(src, root, seen):
    if src in seen or not os.path.lexists(src):
        return
    seen.add(src)
    dst = root + src
    parent = os.path.dirname(src)
    if parent != "/" and os.path.islink(parent):
        _copy(parent, root, seen)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        t = os.readlink(src)
        if not os.path.lexists(dst):
            os.symlink(t, dst)
        _copy(os.path.normpath(os.path.join(os.path.dirname(src), t)), root, seen)
    elif os.path.isfile(src):
        shutil.copy2(src, dst)
        os.chmod(dst, os.stat(src).st_mode & 0o755)


def _ldd(paths):
    out = set()
    for p in paths:
        try:
            r = subprocess.run(["ldd", p], capture_output=True, text=True, timeout=20)
        except Exception:
            continue
        for line in r.stdout.splitlines():
            parts = line.split("=>")[-1].strip().split(" ")
            if parts and parts[0].startswith("/"):
                out.add(parts[0])
    return out


def _is_elf(p):
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def build():
    """Serialised across processes with a file lock (two concurrent builds would corrupt the jail)."""
    import fcntl
    with open(JAIL + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        _build()


def _build():
    import glob
    tmp = JAIL + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for l, t in (("bin", "usr/bin"), ("lib", "usr/lib"), ("sbin", "usr/sbin")):
        os.makedirs(os.path.join(tmp, t), exist_ok=True)
        os.symlink(t, os.path.join(tmp, l))
    seen, elves = set(), set()
    for b in BINS:
        _copy(b, tmp, seen)
        elves.add(os.path.realpath(b))
    for tree in TREES:
        for dp, dns, fns in os.walk(tree):
            if any(s in dp + "/" for s in SKIP):
                continue
            for fn in fns + [d for d in dns if os.path.islink(os.path.join(dp, d))]:
                p = os.path.join(dp, fn)
                if any(s in p for s in SKIP):
                    continue
                _copy(p, tmp, seen)
                if (fn.endswith(".so") or ".so." in fn or os.access(p, os.X_OK)) and os.path.isfile(p) and _is_elf(p):
                    elves.add(os.path.realpath(p))
    for g in LIBGLOBS:
        for p in glob.glob("/usr/lib/aarch64-linux-gnu/" + g) + glob.glob("/usr/lib/" + g):
            _copy(p, tmp, seen)
    for _ in range(3):  # transitive closure of shared libraries
        new = _ldd(sorted(elves)) - seen
        if not new:
            break
        for p in new:
            _copy(p, tmp, seen)
            elves.add(os.path.realpath(p))
    _copy("/etc/ld.so.cache", tmp, seen)
    with open(os.path.join(tmp, "etc/passwd"), "w") as f:
        f.write("root:x:0:0::/:/bin/false\n" + "".join(f"run{u}:x:{u}:{u}::/tmp:/bin/false\n" for u in UIDS))
    with open(os.path.join(tmp, "etc/group"), "w") as f:
        f.write("root:x:0:\n" + "".join(f"run{u}:x:{u}:\n" for u in UIDS))
    os.makedirs(os.path.join(tmp, "dev"))
    for name, mj, mn in (("null", 1, 3), ("zero", 1, 5), ("random", 1, 8), ("urandom", 1, 9)):
        os.mknod(os.path.join(tmp, "dev", name), 0o20666, os.makedev(mj, mn))
        os.chmod(os.path.join(tmp, "dev", name), 0o666)
    wj = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webjudge", "node_modules")
    if os.path.isdir(wj):
        shutil.copytree(wj, os.path.join(tmp, "webjudge", "node_modules"), symlinks=True)
    for d, mode in (("tmp", 0o1777), ("work", 0o711)):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
        os.chmod(os.path.join(tmp, d), mode)
    for dp, dns, fns in os.walk(tmp):  # nothing in the jail is writable by the runner uids except /tmp and per-run dirs
        for n in dns + fns:
            p = os.path.join(dp, n)
            if not os.path.islink(p) and p not in (os.path.join(tmp, "tmp"),) and "/dev/" not in p:
                os.chmod(p, os.stat(p).st_mode & ~0o022)
    os.chown(tmp, 0, 0)
    os.chmod(tmp, 0o755)
    with open(os.path.join(tmp, ".built"), "w") as f:
        f.write(BUILD_VERSION)
    shutil.rmtree(JAIL, ignore_errors=True)
    os.rename(tmp, JAIL)


def _built():
    try:
        with open(os.path.join(JAIL, ".built")) as f:
            return f.read().strip() == BUILD_VERSION
    except OSError:
        return False


# ---------------- verification (live escape probes) ----------------
PY_PROBE = r"""
import os, socket, json, sys
r = {}
def tryf(k, f):
    try:
        f(); r[k] = True
    except Exception as e:
        r[k] = False
tryf("inet_socket", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
tryf("unix_socket", lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
tryf("reads_app", lambda: os.listdir("/app"))
tryf("reads_proc", lambda: os.listdir("/proc"))
tryf("reads_root", lambda: os.listdir("/root"))
tryf("writes_usr", lambda: open("/usr/x", "w"))
tryf("writes_work", lambda: open("ok.txt", "w").write("x"))
tryf("chroot_escape", lambda: os.chroot("/tmp"))
r["root_entries"] = sorted(os.listdir("/"))
r["env_keys"] = sorted(os.environ)
r["uid"] = os.getuid()
n = 0
try:
    for _ in range(200):
        if os.fork() == 0:
            import time; time.sleep(2); os._exit(0)
        n += 1
except OSError:
    pass
r["forks"] = n
print(json.dumps(r))
"""
JS_PROBE = "const net=require('net');const s=net.connect(443,'1.1.1.1');s.on('connect',()=>{console.log('CONNECTED');process.exit(0)});s.on('error',e=>{console.log('BLOCKED '+e.code);process.exit(0)});setTimeout(()=>{console.log('TIMEOUT');process.exit(0)},3000);"
CPP_PROBE = "#include <sys/socket.h>\n#include <cstdio>\nint main(){int s=socket(AF_INET,SOCK_STREAM,0);printf(\"%d\\n\", s);return 0;}\n"
JAVA_PROBE = "public class Main{public static void main(String[] a){try{new java.net.Socket(\"1.1.1.1\",443);System.out.println(\"CONNECTED\");}catch(Exception e){System.out.println(\"BLOCKED\");}}}"


async def verify():
    import code_runner as cr
    import judges
    checks = []

    def ok(name, passed, detail=""):
        checks.append({"check": name, "passed": bool(passed), "detail": str(detail)[:300]})

    async def run(lang, code, stdin=""):
        async with cr.Program(lang, code, isolated=True, _verifying=True) as p:
            err = await p.compile()
            if err:
                return {"status": "Compilation Error", "stdout": "", "stderr": err}
            return await p.run(stdin)

    r = await run("python", PY_PROBE)
    try:
        d = json.loads(r["stdout"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        d = None
        ok("python probe ran", False, r.get("stderr") or r.get("status"))
    if d:
        ok("network: AF_INET socket() denied", not d["inet_socket"])
        ok("network: AF_UNIX socket() denied", not d["unix_socket"])
        ok("filesystem: /app not visible", not d["reads_app"])
        ok("filesystem: /proc not visible", not d["reads_proc"])
        ok("filesystem: /root not visible", not d["reads_root"])
        ok("filesystem: jail read-only outside work dir", not d["writes_usr"])
        ok("filesystem: own work dir writable", d["writes_work"])
        ok("no chroot escape", not d["chroot_escape"])
        ok("root contains only jail entries", set(d["root_entries"]) <= {"bin", "lib", "sbin", "usr", "etc", "dev", "tmp", "work", "webjudge", ".built"}, d["root_entries"])
        ok("environment has no secrets", set(d["env_keys"]) <= {"PATH", "HOME", "LANG", "PYTHONDONTWRITEBYTECODE", "LC_CTYPE"}, d["env_keys"])
        ok("runs as unprivileged pool uid", d["uid"] in UIDS, d["uid"])
        ok("process-count limit enforced", d["forks"] < 200, f"{d['forks']} forks before limit")
    r = await run("javascript", JS_PROBE)
    ok("network: Node.js connect blocked", "BLOCKED" in r["stdout"], r["stdout"] or r["stderr"])
    r = await run("cpp", CPP_PROBE)
    ok("network: raw socket syscall from C++ denied", r["stdout"].strip() == "-1", r["stdout"] or r["stderr"])
    r = await run("java", JAVA_PROBE)
    ok("network: Java socket blocked", "BLOCKED" in r["stdout"], r["stdout"] or r["stderr"][-200:])
    r = await run("python", "import time\nwhile True: pass\n")
    ok("CPU/time limit kills runaway code", r["status"] == "Time Limit Exceeded", r["status"])
    r = await run("python", "x = bytearray(600 * 1024 * 1024)\nprint('allocated')\n")
    ok("memory limit enforced (Python)", "allocated" not in r["stdout"], r["status"])
    for lang, code, want in (("python", "print(int(input())*2)", "42"), ("javascript", "console.log(require('fs').readFileSync(0,'utf8').trim()*2)", "42"),
                             ("cpp", "#include <iostream>\nint main(){int x;std::cin>>x;std::cout<<x*2;}", "42"),
                             ("java", "import java.util.*;public class Main{public static void main(String[] a){System.out.println(new Scanner(System.in).nextInt()*2);}}", "42")):
        r = await run(lang, code, "21")
        ok(f"language works: {lang}", r["stdout"].strip() == want, r["stdout"] or r["stderr"][-200:])
    s = await judges.run_sql("SELECT a*2 AS b FROM t", ["CREATE TABLE t(a INT); INSERT INTO t VALUES (21);"], isolated=True, _verifying=True)
    ok("SQL judge works", s and s[0].get("rows") == [[42]], s)
    w = await judges.run_web("<div id='x'></div>", "", "document.getElementById('x').textContent='hi';", [{"id": "t1", "script": "return document.getElementById('x').textContent==='hi';"}], isolated=True, _verifying=True)
    ok("JavaScript frontend (jsdom) judge works", w and w[0].get("passed"), w)
    return checks


async def init(rebuilt=False):
    """Build (if needed) then verify. Any failure leaves the runner closed."""
    from datetime import datetime, timezone
    if not JAIL:
        STATE.update(error="SANDBOX_JAIL_DIR not configured", built=False, verified=False)
        return STATE
    if _SC is None:
        STATE.update(error="libseccomp not available", built=False, verified=False)
        return STATE
    if _LOCK.locked() and not rebuilt:
        async with _LOCK:
            return STATE
    try:
        if not rebuilt:
            await _LOCK.acquire()
        if not _built():
            STATE["verified"] = False
            await asyncio.to_thread(build)
        STATE["built"] = _built()
        checks = await verify()
        if not all(c["passed"] for c in checks) and not rebuilt:  # stale jail (e.g. built before webjudge existed): rebuild once
            STATE["verified"] = False
            await asyncio.to_thread(build)
            return await init(rebuilt=True)
        STATE.update(checks=checks, verified=all(c["passed"] for c in checks), error=None if all(c["passed"] for c in checks) else "verification failed",
                     verified_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        log.exception("sandbox init failed")
        STATE.update(verified=False, error=f"{type(e).__name__}: {e}"[:300])
    finally:
        if not rebuilt and _LOCK.locked():
            _LOCK.release()
    return STATE
