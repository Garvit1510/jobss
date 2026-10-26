# JobLens AI — Round 4 code sandbox: current state and deployment requirement

## What is implemented in this pod (backend/sandbox.py)
Accenture Round 4 candidate code (DSA Python/JS/C++/Java, SQL judge, jsdom frontend judge) runs ONLY in a jail; there is no fallback:
- chroot jail at `SANDBOX_JAIL_DIR` (/opt/jl_jail, ~640 MB, rebuilt automatically at backend start; contains only interpreters/compilers,
  their libraries, jsdom). No /app, /proc, /root, /etc secrets, no .env, no DB credentials. Read-only except a per-run work dir.
- per-program uid from pool 61001-61008, no groups; env = PATH/HOME/LANG only.
- seccomp (libseccomp + NO_NEW_PRIVS): socket(), io_uring, ptrace, process_vm_*, bpf, perf_event_open, keyring, mount/umount, chroot,
  unshare/setns, module, kexec, reboot, userfaultfd, handle syscalls -> EPERM. No inbound or outbound network of any kind.
- rlimits: CPU, address space 256 MB (Python/C++; Node/Java via heap flags), file size 8 MB, 64 fds, 64 processes, no core dumps.
  Wall-clock timeout kills the process group; all processes of the uid are killed after each program.
- Verification: 23 live probes on startup, on every Release Readiness check and before publish. Any failure => runner closed (HTTP 503).
- Other companies' OA flows and /api/code/* still use the legacy runner (not modified per instructions) — legacy runner has NO network isolation.

## Why this is still a release blocker
The jail shares the kernel and network namespace with the application (seccomp blocks socket creation, but a kernel exploit would
escape). This pod cannot do better: `unshare` (any namespace, incl. user namespaces) is denied, no CAP_SYS_ADMIN/NET_ADMIN,
no Docker/gVisor/KVM, no cgroup delegation (no hard memory/disk quotas).

## Required infrastructure (to clear the blocker)
A separate runner service, NOT in the app container:
- Container/VM with `--network none` (or Kubernetes NetworkPolicy deny-all ingress+egress), gVisor (`runtimeClassName: gvisor`) or
  Firecracker/Kata; read-only root fs, tmpfs work dir with size quota, cgroup limits (memory 512 MB, pids 64, cpu 1), non-root,
  no service-account token (`automountServiceAccountToken: false`), no env secrets.
- Image: python3.11, node 18+ with jsdom, g++ 12, OpenJDK 17, sqlite3.
- Interface (drop-in for code_runner.Program): `POST /run {lang, code, compile: bool, inputs: [stdin...], limits}` -> `[{status, stdout, stderr, time_ms}]`;
  the app reaches it over an internal-only Service with a shared token; the runner can reach nothing.
  Off-the-shelf alternative: self-hosted Judge0 (isolate) with network disabled.
- Then: set `SANDBOX_REMOTE_URL` + token in backend/.env, implement the HTTP client branch in code_runner.Program, verify the same 23 probes
  against the remote runner, and only then set `CODE_SANDBOX_ISOLATED=true`. Publish requires both the live probes and that flag.
