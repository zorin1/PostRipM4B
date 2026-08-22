"""Cross-platform sleep/shutdown helpers for the batch "When done" feature.

Mirrors the approach HandBrake uses per platform:
- Windows: powrprof SetSuspendState (sleep) and shutdown.exe (power off)
- macOS:   AppleScript via osascript through System Events
- Linux:   logind over D-Bus (CanSuspend/CanPowerOff capability checks)
"""

import ctypes
import shutil
import subprocess
import sys

LOGIND_DEST = "org.freedesktop.login1"
LOGIND_PATH = "/org/freedesktop/login1"
LOGIND_IFACE = "org.freedesktop.login1.Manager"


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None


def _logind_call(method, args=None):
    """Call a logind D-Bus method using busctl or dbus-send; returns stdout or None."""
    if args:
        busctl_args = ["busctl", "call", "--system", LOGIND_DEST, LOGIND_PATH,
                       LOGIND_IFACE, method] + args
    else:
        busctl_args = ["busctl", "call", "--system", LOGIND_DEST, LOGIND_PATH,
                       LOGIND_IFACE, method]
    result = _run(busctl_args)
    if result is not None and result.returncode == 0:
        return result.stdout

    dbus_send_args = ["dbus-send", "--system", "--print-reply",
                      f"--dest={LOGIND_DEST}", LOGIND_PATH,
                      f"{LOGIND_IFACE}.{method}"]
    if args:
        dbus_send_args += args
    result = _run(dbus_send_args)
    if result is not None and result.returncode == 0:
        return result.stdout
    return None


def _can_logind(method):
    """Check a logind Can* method reports 'yes'."""
    out = _logind_call(method)
    return bool(out) and "yes" in out


def can_sleep():
    """Return True if sleeping the system is supported."""
    if sys.platform == "win32" or sys.platform == "darwin":
        return True
    return _can_logind("CanSuspend")


def can_shutdown():
    """Return True if shutting down the system is supported."""
    if sys.platform == "win32" or sys.platform == "darwin":
        return True
    return _can_logind("CanPowerOff")


def sleep_system():
    """Put the computer to sleep. Returns (success, error_message)."""
    try:
        if sys.platform == "win32":
            ok = ctypes.windll.powrprof.SetSuspendState(False, False, False)
            if not ok:
                return False, "SetSuspendState failed (error %s)" % ctypes.GetLastError()
            return True, ""
        if sys.platform == "darwin":
            result = _run(["osascript", "-e", 'tell application "System Events" to sleep'])
            if result is None or result.returncode != 0:
                err = result.stderr.strip() if result else "osascript not found"
                return False, f"Sleep failed: {err}"
            return True, ""

        out = _logind_call("Suspend", ["b", "true"])
        if out is None:
            return False, "Could not suspend via logind (D-Bus call failed)"
        return True, ""
    except Exception as e:
        return False, str(e)


def shutdown_system(delay_seconds=60):
    """Shut the computer down after an optional delay. Returns (success, error_message)."""
    try:
        if sys.platform == "win32":
            result = _run(["shutdown", "/s", "/t", str(delay_seconds)])
            if result is None or result.returncode != 0:
                err = result.stderr.strip() if result else "shutdown.exe not found"
                return False, f"Shutdown failed: {err}"
            return True, ""
        if sys.platform == "darwin":
            result = _run(["osascript", "-e", 'tell application "System Events" to shut down'])
            if result is None or result.returncode != 0:
                err = result.stderr.strip() if result else "osascript not found"
                return False, f"Shutdown failed: {err}"
            return True, ""

        out = _logind_call("PowerOff", ["b", "true"])
        if out is None:
            return False, "Could not power off via logind (D-Bus call failed)"
        return True, ""
    except Exception as e:
        return False, str(e)


def cancel_shutdown():
    """Best-effort cancel of a pending Windows timed shutdown."""
    if sys.platform == "win32":
        _run(["shutdown", "/a"])
