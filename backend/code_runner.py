import asyncio
import os
import re
import shutil
import tempfile
import subprocess
import time

import sandbox

try:
    import resource
except ImportError:
    resource = None

LANGS = {"python": "Python", "javascript": "JavaScript", "cpp": "C++", "java": "Java"}
TIME_LIMIT = {"python": 5.0, "javascript": 5.0, "cpp": 2.0, "java": 4.0}
MEM_BYTES = 256 * 1024 * 1024
OUT_CAP = 64 * 1024
NOBODY = 65534
NPROC = 256
JDK = "/usr/lib/jvm/java-17-openjdk-arm64"
_sem = asyncio.Semaphore(4)
_PY = next((p for p in ("/usr/local/bin/python3", "/usr/bin/python3") if os.path.exists(p)), shutil.which("python3"))
_NODE = shutil.which("node") or "node"
_GPP = shutil.which("g++") or "g++"
_JCLASS = re.compile(r"public\s+(?:final\s+)?class\s+([A-Za-z_]\w*)")


def norm_lang(lang):
    l = (lang or "").strip().lower()
    return {"python": "python", "py": "python", "python3": "python", "javascript": "javascript", "js": "javascript", "node": "javascript",
            "c++": "cpp", "cpp": "cpp", "c++17": "cpp", "java": "java"}.get(l)


def available(lang):
    return lang != "java" or bool(shutil.which("javac") and shutil.which("java"))


def _limits(mem=True, cpu=10):
    def fn():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (NPROC, NPROC))  # per-uid cap for nobody: blocks fork bombs
        if mem:
            resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
        if os.geteuid() == 0:
            os.setgid(NOBODY)
            os.setuid(NOBODY)
    return fn


async def _exec(cmd, cwd, stdin="", timeout=5.0, mem=True, iso=None):
    """iso=(uid, inner_cwd): run inside the sandbox jail (chroot + seccomp + pool uid); cwd is then applied after chroot."""
    if os.name == "nt" and not iso:
        raise sandbox.Unavailable("Code execution requires the Linux sandbox and is disabled on Windows.")
    if iso:
        env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        if "/jvm/" in cmd[0]:  # no /proc in the jail, so $ORIGIN rpath can't resolve
            env["LD_LIBRARY_PATH"] = f"{JDK}/lib:{JDK}/lib/server"
        pre, cwd = sandbox.preexec(iso[0], iso[1], int(timeout) + 1, MEM_BYTES if mem else 0), None
    else:
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": cwd, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        pre = _limits(mem, int(timeout) + 1)
    p = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE, preexec_fn=pre)
    t0 = time.monotonic()
    try:
        out, err = await asyncio.wait_for(p.communicate(stdin.encode()), timeout)
        status = None
    except asyncio.TimeoutError:
        try:
            os.killpg(p.pid, 9)
        except ProcessLookupError:
            pass
        out, err = await p.communicate()
        status = "Time Limit Exceeded"
    ms = round((time.monotonic() - t0) * 1000)
    err_s = err[:OUT_CAP].decode(errors="replace")
    if not status and p.returncode:
        status = "Memory Limit Exceeded" if "MemoryError" in err_s or "bad_alloc" in err_s or "heap out of memory" in err_s or "OutOfMemoryError" in err_s else "Runtime Error"
    return {"status": status, "stdout": out[:OUT_CAP].decode(errors="replace"), "stderr": err_s[-2000:], "time_ms": ms, "code": p.returncode}


_UID_POOL = None


def _pool():
    global _UID_POOL
    if _UID_POOL is None:
        _UID_POOL = asyncio.Queue()
        for u in sandbox.UIDS:
            _UID_POOL.put_nowait(u)
    return _UID_POOL


class Program:
    """Prepared program in a temp dir; compile once, run many inputs.
    isolated=True: runs in the sandbox jail and FAILS CLOSED (sandbox.Unavailable) unless the jail is built and verified."""

    def __init__(self, lang, code, isolated=False, _verifying=False):
        self.lang, self.code, self.dir, self.cmd = lang, code, None, None
        self.isolated, self._verifying, self.uid, self.iso = isolated, _verifying, None, None

    async def __aenter__(self):
        if self.isolated:
            if not (sandbox.ready() or (self._verifying and sandbox.STATE["built"])):
                raise sandbox.Unavailable("Secure code runner unavailable")
            self.uid = await _pool().get()
            self.dir, inner = sandbox.new_workdir(self.uid)
            self.iso = (self.uid, inner)
            py, node, java, base = "/usr/bin/python3.11", "/usr/bin/node", "/usr/lib/jvm/java-17-openjdk-arm64/bin/java", inner
        else:
            self.dir = tempfile.mkdtemp(prefix="jl_run_")
            os.chmod(self.dir, 0o777)
            py, node, java, base = _PY, _NODE, shutil.which("java") or "java", self.dir
        if self.lang == "python":
            path = "main.py"
            self.cmd = [py, "-I", os.path.join(base, path)]
        elif self.lang == "javascript":
            path = "main.js"
            self.cmd = [node, "--max-old-space-size=256", "--stack-size=8000", os.path.join(base, path)]
        elif self.lang == "java":
            m = _JCLASS.search(self.code)
            self.jclass = m.group(1) if m else "Main"
            path = f"{self.jclass}.java"
            self.cmd = [java, "-Xmx256m", "-Xss64m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData", "-cp", base, self.jclass]
        else:
            path = "main.cpp"
            self.cmd = [os.path.join(base, "main")]
        with open(os.path.join(self.dir, path), "w") as f:
            f.write(self.code)
        os.chmod(os.path.join(self.dir, path), 0o644)
        return self

    async def compile(self):
        if self.lang == "java":
            javac = "/usr/lib/jvm/java-17-openjdk-arm64/bin/javac" if self.iso else shutil.which("javac") or "javac"
            r = await _exec([javac, "-J-Xmx512m", "-J-XX:-UsePerfData", "-encoding", "UTF-8", f"{self.jclass}.java"], self.dir, timeout=30, mem=False, iso=self.iso)
            return None if r["code"] == 0 and not r["status"] else (r["stderr"] or r["status"] or "Compilation failed")[-3000:]
        if self.lang != "cpp":
            return None
        r = await _exec(["/usr/bin/g++" if self.iso else _GPP, "-O2", "-std=c++17", "-o", "main", "main.cpp"], self.dir, timeout=20, mem=False, iso=self.iso)
        return None if r["code"] == 0 and not r["status"] else (r["stderr"] or r["status"] or "Compilation failed")[-3000:]

    async def run(self, stdin, timeout=None):
        async with _sem:
            return await _exec(self.cmd, self.dir, stdin, timeout or TIME_LIMIT[self.lang], mem=self.lang not in ("javascript", "java"), iso=self.iso)

    async def __aexit__(self, *a):
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
        if self.uid:
            if self.isolated:
                await asyncio.to_thread(subprocess.run, ["pkill", "-9", "-u", str(self.uid)], capture_output=True)
            _pool().put_nowait(self.uid)


_NUM = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


def same_output(got, expected):
    a, b = got.split(), expected.split()
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        if _NUM.match(x) and _NUM.match(y) and ("." in x or "." in y):
            if abs(float(x) - float(y)) <= 1e-6 * max(1.0, abs(float(y))):
                continue
        if x.lower() in ("true", "false") and x.lower() == y.lower():
            continue
        return False
    return True


_HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE_PATHS = [(os.path.join(_HERE, ".env"), 0o600), (os.path.join(_HERE, "..", "memory"), 0o700), (os.path.join(_HERE, "..", "auth_testing.md"), 0o600),
                 (os.path.join(_HERE, "..", ".git"), 0o700), ("/var/log/supervisor", 0o700)]


def harden():
    """Keep secrets/credentials/logs unreadable for the unprivileged runner uid."""
    for path, mode in PRIVATE_PATHS:
        if os.path.exists(path):
            try:
                os.chmod(path, mode)
            except OSError:
                pass


def sandbox_isolated():
    """Operator confirmation that a kernel-isolated (container/VM) runner is deployed. Never sufficient on its own: callers also require sandbox.ready()."""
    return os.environ.get("CODE_SANDBOX_ISOLATED") == "true"


PROBE = r"""
import socket, json
def can_connect(host, port):
    try:
        socket.create_connection((host, port), timeout=2).close(); return True
    except OSError:
        return False
def can_read(p):
    try:
        open(p).read(1); return True
    except OSError:
        return False
print(json.dumps({"internet": can_connect("1.1.1.1", 443), "app_server": can_connect("127.0.0.1", 8001), "local_mongo": can_connect("127.0.0.1", 27017),
                  "reads_env": can_read(%r), "reads_credentials": can_read(%r)}))
"""


async def probe():
    """Runs a harmless script through the real runner to report what candidate code can reach."""
    import json
    code = PROBE % (os.path.join(_HERE, ".env"), os.path.join(_HERE, "..", "memory", "test_credentials.md"))
    async with Program("python", code) as prog:
        r = await prog.run("", timeout=10)
    try:
        return json.loads(r["stdout"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": r["status"] or r["stderr"][-300:]}


harden()
