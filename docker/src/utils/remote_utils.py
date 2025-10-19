import os
import platform
import subprocess
import sys

def _is_remote_windows() -> bool:
    # Primary: RDP / Terminal Services
    try:
        import ctypes
        SM_REMOTESESSION = 0x1000
        if ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION):
            return True
    except Exception:
        pass

    # Fallback: common env heuristic
    sess = os.environ.get("SESSIONNAME", "")
    if sess.upper().startswith("RDP") or "RDP" in sess.upper():
        return True
    return False

def _parent_commands_posix(pid: int):
    """Yield process command names up the tree using 'ps' (works on Linux & macOS)."""
    seen = set()
    while pid and pid not in seen:
        seen.add(pid)
        try:
            # 'comm' is just the executable name; 'ppid' to move upward.
            out = subprocess.check_output(["ps", "-o", "comm=,ppid=", "-p", str(pid)], text=True).strip()
            if not out:
                break
            # Example line: "sshd  1234"
            parts = out.split()
            comm = parts[0]
            ppid = int(parts[-1]) if parts[-1].isdigit() else 0
            yield comm
            pid = ppid
        except Exception:
            break

def _is_remote_posix() -> bool:
    # Fast path: SSH-specific environment variables
    for key in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"):
        if os.environ.get(key):
            return True

    # Parent process heuristic: came from sshd
    try:
        pid = os.getpid()
        for comm in _parent_commands_posix(pid):
            name = comm.lower()
            # Common sshd command names: 'sshd', 'sshd:', 'sshd-child', etc.
            if name.startswith("sshd"):
                return True
    except Exception:
        pass

    # Optional: 'who -m' (or 'who am i') shows a remote host if present
    for cmd in (["who", "-m"], ["who", "am", "i"]):
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            # Typical formats:
            #  user pts/0 2025-10-05 12:34 (203.0.113.7)
            #  user console  Oct  5 12:34
            if "(" in out and ")" in out:
                return True
        except Exception:
            pass

    # Not obviously remote
    return False

def is_remote_session() -> bool:
    """True if this Python process looks like a remote session (SSH/RDP), else False."""
    system = platform.system()
    
    if system == "Windows":
        return _is_remote_windows()
    else:
        return _is_remote_posix()