import asyncio
import ctypes
import ctypes.wintypes as W
import hashlib
import json
import logging
import mimetypes
import os
import queue
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
import webbrowser
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

PORT = 47123
HOSTS = ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT)
ORIGINS = ["http://" + h for h in HOSTS] + ["https://desktopsetup.github.io"]
OPEN_URL = "https://desktopsetup.github.io/XD2Joy-Webtool/"
WEB = Path(__file__).resolve().parent / "web"
PAGE = "XD2Joy Web-tool.html"

MOUSE_S = 0.008
KEEP_S = 0.05
STOP_HOLD_S = 1.0
HOOK_LOST_S = 0.1

TAKE = True


_said = queue.SimpleQueue()
_sayer = []
_sayer_lock = threading.Lock()


def say(text):
    with _sayer_lock:
        if not _sayer:
            t = threading.Thread(target=_say_loop, daemon=True)
            t.start()
            _sayer.append(t)
    _said.put(text)


def _say_loop():
    while True:
        text = _said.get()
        try:
            print(text, flush=True)
        except Exception:
            pass


KEY_NAMES = {0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab", 0x2C: "Space",
             0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]", 0x31: "\\", 0x33: ";", 0x34: "'",
             0x35: "`", 0x36: ",", 0x37: ".", 0x38: "/", 0x39: "Caps Lock",
             0x46: "Print Screen", 0x47: "Scroll Lock", 0x48: "Pause", 0x49: "Insert",
             0x4A: "Home", 0x4B: "Page Up", 0x4C: "Delete", 0x4D: "End", 0x4E: "Page Down",
             0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up", 0x53: "Num Lock",
             0x54: "Keypad /", 0x55: "Keypad *", 0x56: "Keypad -", 0x57: "Keypad +",
             0x58: "Keypad Enter", 0x63: "Keypad .", 0x64: "102nd key", 0x65: "Menu"}
for _i in range(26):
    KEY_NAMES[0x04 + _i] = chr(ord("A") + _i)
for _i in range(9):
    KEY_NAMES[0x1E + _i] = str(_i + 1)
    KEY_NAMES[0x59 + _i] = "Keypad %d" % (_i + 1)
KEY_NAMES[0x27] = "0"
KEY_NAMES[0x62] = "Keypad 0"
for _i in range(12):
    KEY_NAMES[0x3A + _i] = "F%d" % (_i + 1)
    KEY_NAMES[0x68 + _i] = "F%d" % (_i + 13)
MOD_NAMES = ((0x01, "Ctrl"), (0x02, "Shift"), (0x04, "Alt"), (0x08, "Win"), (0x10, "Right Ctrl"),
             (0x20, "Right Shift"), (0x40, "Right Alt"), (0x80, "Right Win"))


def key_name(code):
    return KEY_NAMES.get(code, "key 0x%02X" % code)


def keys_text(mods, keys):
    names = [n for bit, n in MOD_NAMES if mods & bit] + [key_name(k) for k in keys if k]
    return "+".join(names) if names else "none"


SC = {0x01: 0x29, 0x0C: 0x2D, 0x0D: 0x2E, 0x0E: 0x2A, 0x0F: 0x2B, 0x1A: 0x2F,
      0x1B: 0x30, 0x1C: 0x28, 0x27: 0x33, 0x28: 0x34, 0x29: 0x35, 0x2B: 0x31,
      0x33: 0x36, 0x34: 0x37, 0x35: 0x38, 0x37: 0x55, 0x39: 0x2C, 0x3A: 0x39,
      0x46: 0x47, 0x47: 0x5F, 0x48: 0x60, 0x49: 0x61, 0x4A: 0x56, 0x4B: 0x5C,
      0x4C: 0x5D, 0x4D: 0x5E, 0x4E: 0x57, 0x4F: 0x59, 0x50: 0x5A, 0x51: 0x5B,
      0x52: 0x62, 0x53: 0x63, 0x56: 0x64, 0x57: 0x44, 0x58: 0x45, 0x59: 0x67,
      0x70: 0x88, 0x73: 0x87, 0x76: 0x73, 0x79: 0x8A, 0x7B: 0x8B, 0x7D: 0x89,
      0x7E: 0x85}
for _i, _u in enumerate((0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27)):
    SC[0x02 + _i] = _u
for _sc, _u in zip(range(0x10, 0x1A), (0x14, 0x1A, 0x08, 0x15, 0x17, 0x1C, 0x18, 0x0C, 0x12, 0x13)):
    SC[_sc] = _u
for _sc, _u in zip(range(0x1E, 0x27), (0x04, 0x16, 0x07, 0x09, 0x0A, 0x0B, 0x0D, 0x0E, 0x0F)):
    SC[_sc] = _u
for _sc, _u in zip(range(0x2C, 0x33), (0x1D, 0x1B, 0x06, 0x19, 0x05, 0x11, 0x10)):
    SC[_sc] = _u
for _i in range(10):
    SC[0x3B + _i] = 0x3A + _i
for _i in range(11):
    SC[0x64 + _i] = 0x68 + _i
SC[0x54] = 0x46
SC_E0 = {0x1C: 0x58, 0x35: 0x54, 0x37: 0x46, 0x46: 0x48, 0x47: 0x4A, 0x48: 0x52,
         0x49: 0x4B, 0x4B: 0x50, 0x4D: 0x4F, 0x4F: 0x4D, 0x50: 0x51, 0x51: 0x4E,
         0x52: 0x49, 0x53: 0x4C, 0x5D: 0x65}
MODS = {(0x1D, False): 0x01, (0x2A, False): 0x02, (0x38, False): 0x04, (0x5B, True): 0x08,
        (0x1D, True): 0x10, (0x36, False): 0x20, (0x38, True): 0x40, (0x5C, True): 0x80}
STOP_KEY = 0x18


def key_usage(make, flags, vkey):
    e0 = bool(flags & 2)
    if vkey == 0xFF:
        return None
    if vkey == 0x13:
        return ("key", 0x48)
    if vkey == 0x90:
        return ("key", 0x53)
    if flags & 4:
        return None
    bit = MODS.get((make, e0))
    if bit:
        return ("mod", bit)
    usage = (SC_E0 if e0 else SC).get(make)
    return ("key", usage) if usage else None


class Engine:
    def __init__(self, emit):
        self.emit = emit
        self.lock = threading.Lock()
        self.run = False
        self.slots = {"L": self._new_slot("L"), "R": self._new_slot("R")}
        self.pick = {"k": None, "m": None}
        self.detect = None
        self.moved = {}
        self.who = None
        self.stop = (STOP_KEY, 0)
        self.kbmode = False
        self.hiding = False
        self.mhiding = False
        self.mkept = False
        self.mkept_ids = set()
        self.taken = frozenset()
        self.on_hide = None
        self.recent = {"k": None, "m": None}
        self.rmoved = {}
        self.names = {}
        self._clear()

    @staticmethod
    def _new_slot(side):
        return {"side": side, "id": None, "kind": None, "twin": None,
                "mods": 0, "keys": [], "dx": 0, "dy": 0, "wheel": 0, "wacc": 0,
                "btn": 0, "btn_sent": 0, "k_at": 0.0, "m_at": 0.0}

    def _order(self):
        return [self.slots["L"], self.slots["R"]]

    def _slot_for(self, group, kind):
        if not group:
            return None
        for s in self._order():
            if s["id"] == group and s["kind"] == kind:
                return s
        if group in self.taken:
            for s in self._order():
                if s["twin"] == group:
                    return s
        return None

    def _ids(self, kind):
        return {s["id"] for s in self._order() if s["id"] and s["kind"] == kind}

    def name(self, group):
        return '"%s"' % self.names[group] if group in self.names else (group or "none")

    def _clear(self):
        self.wmods = 0
        self.stop_at = 0.0
        for s in self._order():
            s.update(mods=0, keys=[], dx=0, dy=0, wheel=0, wacc=0, btn=0, btn_sent=0,
                     k_at=0.0, m_at=0.0)

    def _kline(self, s, now):
        s["k_at"] = now
        return (s["side"], "k %02X" % s["mods"] + "".join(" %02X" % k for k in s["keys"][:6]))

    def _mline(self, s, now, keep=False):
        if not (s["dx"] or s["dy"] or s["wheel"] or keep or s["btn"] != s["btn_sent"]):
            return None
        dx = max(-32768, min(32767, s["dx"]))
        dy = max(-32768, min(32767, s["dy"]))
        line = "m %d %d %d %d" % (dx, dy, s["wheel"], s["btn"])
        s["dx"] = s["dy"] = s["wheel"] = 0
        s["btn_sent"] = s["btn"]
        s["m_at"] = now
        return (s["side"], line)

    def _send(self, lines, extra=None):
        lines = [x for x in lines if x]
        if lines:
            self.emit({"t": "l", "s": [[side, text] for side, text in lines]})
        if extra:
            self.emit(extra)

    def _release(self):
        out = []
        for s in self._order():
            if not s["id"]:
                continue
            if s["kind"] == "k" or s["mods"] or s["keys"]:
                out.append((s["side"], "k"))
            if s["kind"] == "m" or s["btn"] or s["btn_sent"] or s["dx"] or s["dy"]:
                out.append((s["side"], "m 0 0 0 0"))
        self._clear()
        return out

    def _hide_check(self):
        calls = []
        with self.lock:
            if not self.run:
                self.mkept = False
                self.mkept_ids = set()
            base = self.run and not self.kbmode
            ks = self._ids("k")
            ms = self._ids("m")
            want = bool(base and ks and not ks <= self.taken)
            if want != self.hiding:
                self.hiding = want
                calls.append(("k", want))
            if base and ms:
                self.mkept_ids |= ms
            cur = ms or self.mkept_ids
            want = bool(base and cur)
            if want:
                self.mkept = True
            if want and cur <= self.taken:
                want = False
            if want != self.mhiding:
                self.mhiding = want
                calls.append(("m", want))
        if self.on_hide:
            for kind, on in calls:
                self.on_hide(kind, on)

    def set_run(self, on):
        with self.lock:
            if on == self.run:
                return
            self.run = on
            self.who = None
            out = self._release() if not on else []
            if on:
                self._clear()
        self._send(out)
        say("Sending to the Switch (hold %s to stop)" % self._stop_name() if on else "Stopped sending")
        self._hide_check()

    def set_picks(self, sides):
        want = {}
        for side in ("L", "R"):
            d = sides.get(side) or {}
            gid = d.get("id") or None
            kind = d.get("kind")
            kind = kind if kind in ("k", "m") else None
            want[side] = (gid, kind) if (gid and kind) else (None, None)
        with self.lock:
            if all(want[s] == (self.slots[s]["id"], self.slots[s]["kind"]) for s in ("L", "R")):
                return
            was = {s: (self.slots[s]["id"], self.slots[s]["kind"]) for s in ("L", "R")}
            out = self._release() if self.run else []
            for side in ("L", "R"):
                gid, kind = want[side]
                self.slots[side]["id"], self.slots[side]["kind"] = gid, kind
                self.slots[side]["twin"] = (("m" if kind == "k" else "k") + gid[1:]) if gid else None
            ks = [s["id"] for s in self._order() if s["id"] and s["kind"] == "k"]
            ms = [s["id"] for s in self._order() if s["id"] and s["kind"] == "m"]
            self.pick = {"k": ks[0] if ks else None, "m": ms[0] if ms else None}
        self._send(out)
        for side in ("L", "R"):
            if want[side] != was[side]:
                gid, kind = want[side]
                say("%s Joy-Con: %s" % ("Left" if side == "L" else "Right",
                                        "%s %s" % ("keyboard" if kind == "k" else "mouse", self.name(gid))
                                        if gid else "no device from this PC"))
        self._hide_check()

    def set_pick(self, k, m):
        self.set_picks({"L": {"id": k, "kind": "k"}, "R": {"id": m, "kind": "m"}})

    def set_kbmode(self, on):
        with self.lock:
            self.kbmode = bool(on)
        self._hide_check()

    def set_taken(self, groups):
        out = []
        with self.lock:
            groups = frozenset(groups)
            if groups == self.taken:
                return
            new = groups - self.taken
            self.taken = groups
            now = time.perf_counter()
            if self.run:
                for s in self._order():
                    if not s["id"] or s["id"] not in new:
                        continue
                    if s["mods"] or s["keys"]:
                        s["mods"] = 0
                        s["keys"] = []
                        out.append(self._kline(s, now))
                    if s["btn"]:
                        s["btn"] = 0
                        out.append(self._mline(s, now, keep=True))
        self._send(out)
        self._hide_check()

    def sends(self, kind, group):
        if not group or not self.run or self.kbmode:
            return False
        if self._slot_for(group, kind):
            return True
        return bool(kind == "m" and self.mkept and group in self.mkept_ids)

    def set_stop(self, code, mods):
        with self.lock:
            self.stop = (code, mods) if code else (STOP_KEY, 0)
            self.stop_at = 0.0

    def _is_stop(self, code, up, mods):
        if not self.stop or code != self.stop[0]:
            return False
        if up:
            return bool(self.stop_at)
        return (mods & self.stop[1]) == self.stop[1]

    def set_detect(self, kind):
        with self.lock:
            self.detect = kind if kind in ("k", "m", "a") else None
            self.moved = {}

    def _found(self, kind, group):
        self.detect = None
        self.moved = {}
        return {"t": "detected", "kind": kind, "id": group}

    def _recent(self):
        return {"t": "recent", "k": self.recent["k"], "m": self.recent["m"]}

    def key(self, group, make, flags, vkey, now):
        self.use_key(group, key_usage(make, flags, vkey), bool(flags & 1), now)

    def use_key(self, group, usage, up, now):
        found = None
        recent = None
        out = []
        with self.lock:
            if self.detect in ("k", "a") and group and not up and usage:
                found = self._found("k", group)
            if group and not up and usage and group != self.recent["k"]:
                self.recent["k"] = group
                recent = self._recent()
            s = self._slot_for(group, "k")
            if self.run and s and usage:
                kind, code = usage
                if kind == "mod":
                    mods = (s["mods"] & ~code) if up else (s["mods"] | code)
                    if mods != s["mods"]:
                        s["mods"] = mods
                        out.append(self._kline(s, now))
                else:
                    if self._is_stop(code, up, s["mods"]):
                        if not up and not self.stop_at:
                            self.stop_at = now
                        elif up and self.stop_at:
                            self.stop_at = 0.0
                    if up:
                        if code in s["keys"]:
                            s["keys"].remove(code)
                            out.append(self._kline(s, now))
                    elif code not in s["keys"]:
                        s["keys"].append(code)
                        out.append(self._kline(s, now))
            elif self.run and group and not self._ids("k") and usage:
                kind, code = usage
                if kind == "mod":
                    self.wmods = (self.wmods & ~code) if up else (self.wmods | code)
                elif code == self.stop[0]:
                    if up:
                        self.stop_at = 0.0
                    elif not self.stop_at and (self.wmods & self.stop[1]) == self.stop[1]:
                        self.stop_at = now
        if recent:
            self.emit(recent)
        self._send(out, found)

    def _stop_name(self):
        return keys_text(self.stop[1], [self.stop[0]])

    def mouse(self, group, flags, bflags, bdata, dx, dy, now, more=None):
        found = None
        who = None
        recent = None
        out = []
        rel = not (flags & 1)
        with self.lock:
            if self.detect in ("m", "a") and group:
                seen = self.moved.get(group, 0) + (abs(dx) + abs(dy) if rel else 0)
                self.moved[group] = seen
                if seen >= 40 or bflags & 0x0155 or more:
                    found = self._found("m", group)
            if group and group != self.recent["m"]:
                seen = self.rmoved.get(group, 0) + (abs(dx) + abs(dy) if rel else 0)
                self.rmoved[group] = seen
                if seen >= 10 or bflags & 0x0155 or more:
                    self.recent["m"] = group
                    self.rmoved = {}
                    recent = self._recent()
            s = self._slot_for(group, "m")
            if self.run and group and ((rel and (dx or dy)) or bflags or more):
                w = "p" if s else "o"
                if w != self.who:
                    self.who = w
                    who = {"t": "who", "m": w}
            if self.run and s:
                if rel:
                    s["dx"] += dx
                    s["dy"] += dy
                btn = s["btn"]
                for i, bit in enumerate((0x01, 0x02, 0x04, 0x08, 0x10)):
                    if bflags & (1 << (2 * i)):
                        btn |= bit
                    if bflags & (2 << (2 * i)):
                        btn &= ~bit
                if more is not None:
                    btn = (btn & 0x1F) | (more & 0xE0)
                s["btn"] = btn
                if bflags & 0x0400:
                    s["wacc"] += bdata
                    while abs(s["wacc"]) >= 120:
                        step = 1 if s["wacc"] > 0 else -1
                        s["wheel"] += step
                        s["wacc"] -= 120 * step
                if s["btn"] != s["btn_sent"] or s["wheel"] or now - s["m_at"] >= MOUSE_S:
                    out.append(self._mline(s, now))
        if recent:
            self.emit(recent)
        if who:
            self.emit(who)
        self._send(out, found)

    def tick(self, now):
        out = []
        stopped = None
        with self.lock:
            if not self.run:
                return
            if self.stop_at and now - self.stop_at >= STOP_HOLD_S:
                self.run = False
                out = self._release()
                stopped = {"t": "stopped"}
            else:
                for s in self._order():
                    if s["id"] and (s["dx"] or s["dy"]) and now - s["m_at"] >= MOUSE_S:
                        out.append(self._mline(s, now))
                for s in self._order():
                    if s["id"] and (s["mods"] or s["keys"]) and now - s["k_at"] >= KEEP_S:
                        out.append(self._kline(s, now))
                for s in self._order():
                    if s["id"] and s["btn"] and now - s["m_at"] >= KEEP_S:
                        out.append(self._mline(s, now, keep=True))
        self._send(out, stopped)
        if stopped:
            say("Stopped sending (the stop key %s was held)" % self._stop_name())
            self._hide_check()


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid")
cfgmgr = ctypes.WinDLL("cfgmgr32")

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
WM_INPUT = 0x00FF
WM_INPUT_DEVICE_CHANGE = 0x00FE
RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000
HWND_MESSAGE = W.HWND(-3)
INVALID_HANDLE = ctypes.c_void_p(-1).value
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLKHF_UP = 0x80
LLMHF_INJECTED = 0x01
WM_HIDE = 0x8001
WM_RESCAN = 0x8002
SM_SWAPBUTTON = 23
MOUSE_UP = {0x0202: "L", 0x0205: "R", 0x0208: "M", 0x020C: "X"}


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", W.USHORT), ("usUsage", W.USHORT),
                ("dwFlags", W.DWORD), ("hwndTarget", W.HWND)]


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", W.HANDLE), ("dwType", W.DWORD)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", W.DWORD), ("dwSize", W.DWORD),
                ("hDevice", W.HANDLE), ("wParam", W.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", W.USHORT), ("_pad", W.USHORT),
                ("usButtonFlags", W.USHORT), ("usButtonData", ctypes.c_short),
                ("ulRawButtons", W.ULONG), ("lLastX", W.LONG), ("lLastY", W.LONG),
                ("ulExtraInformation", W.ULONG)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", W.USHORT), ("Flags", W.USHORT), ("Reserved", W.USHORT),
                ("VKey", W.USHORT), ("Message", W.UINT), ("ExtraInformation", W.ULONG)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", W.DWORD), ("scanCode", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", W.POINT), ("mouseData", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, W.WPARAM, W.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", W.UINT), ("style", W.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", W.HINSTANCE), ("hIcon", W.HICON), ("hCursor", W.HANDLE),
                ("hbrBackground", W.HBRUSH), ("lpszMenuName", W.LPCWSTR),
                ("lpszClassName", W.LPCWSTR), ("hIconSm", W.HICON)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", W.ULONG)]


CONTAINER_ID = DEVPROPKEY(GUID(0x8C7ED206, 0x3F8A, 0x4827,
                               (ctypes.c_ubyte * 8)(0xB3, 0xAB, 0xAE, 0x9E, 0x1F, 0xAE, 0xFC, 0x6C)), 2)

user32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = W.ATOM
user32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND,
                                   W.HMENU, W.HINSTANCE, W.LPVOID]
user32.CreateWindowExW.restype = W.HWND
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), W.UINT, W.UINT]
user32.RegisterRawInputDevices.restype = W.BOOL
user32.GetRawInputData.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT), W.UINT]
user32.GetRawInputData.restype = W.UINT
user32.GetRawInputDeviceList.argtypes = [W.LPVOID, ctypes.POINTER(W.UINT), W.UINT]
user32.GetRawInputDeviceList.restype = W.UINT
user32.GetRawInputDeviceInfoW.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT)]
user32.GetRawInputDeviceInfoW.restype = W.UINT
user32.GetMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
user32.GetMessageW.restype = W.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(W.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(W.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
user32.SetWindowsHookExW.restype = W.HHOOK
user32.UnhookWindowsHookEx.argtypes = [W.HHOOK]
user32.UnhookWindowsHookEx.restype = W.BOOL
user32.CallNextHookEx.argtypes = [W.HHOOK, ctypes.c_int, W.WPARAM, W.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.PostMessageW.restype = W.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SetTimer.argtypes = [W.HWND, ctypes.c_size_t, W.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [W.HWND, ctypes.c_size_t]
user32.KillTimer.restype = W.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
kernel32.GetModuleHandleW.argtypes = [W.LPCWSTR]
kernel32.GetModuleHandleW.restype = W.HMODULE
kernel32.GetTickCount.argtypes = []
kernel32.GetTickCount.restype = W.DWORD
kernel32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE]
kernel32.CreateFileW.restype = W.HANDLE
kernel32.CloseHandle.argtypes = [W.HANDLE]
hid.HidD_GetProductString.argtypes = [W.HANDLE, W.LPVOID, W.ULONG]
hid.HidD_GetProductString.restype = W.BOOLEAN
cfgmgr.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(W.DWORD), W.LPCWSTR, W.ULONG]
cfgmgr.CM_Locate_DevNodeW.restype = W.DWORD
cfgmgr.CM_Get_DevNode_PropertyW.argtypes = [W.DWORD, ctypes.POINTER(DEVPROPKEY),
                                            ctypes.POINTER(W.ULONG), W.LPVOID,
                                            ctypes.POINTER(W.ULONG), W.ULONG]
cfgmgr.CM_Get_DevNode_PropertyW.restype = W.DWORD


def device_path(handle):
    size = W.UINT(0)
    user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, None, ctypes.byref(size))
    if not size.value:
        return ""
    buf = ctypes.create_unicode_buffer(size.value + 1)
    user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, buf, ctypes.byref(size))
    return buf.value


def product_name(path):
    h = kernel32.CreateFileW(path, 0, 3, None, 3, 0, None)
    if not h or h == INVALID_HANDLE:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(128)
        if hid.HidD_GetProductString(h, buf, ctypes.sizeof(buf)):
            return buf.value.strip()
        return ""
    finally:
        kernel32.CloseHandle(h)


def container_of(path):
    p = path[4:] if path.startswith("\\\\?\\") else path
    cut = p.rfind("#{")
    inst = (p[:cut] if cut > 0 else p).replace("#", "\\")
    node = W.DWORD(0)
    if cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), inst, 0) != 0:
        return ""
    kind = W.ULONG(0)
    buf = (ctypes.c_ubyte * 16)()
    size = W.ULONG(16)
    if cfgmgr.CM_Get_DevNode_PropertyW(node, ctypes.byref(CONTAINER_ID), ctypes.byref(kind),
                                       buf, ctypes.byref(size), 0) != 0:
        return ""
    return bytes(buf).hex()


def scan_devices():
    n = W.UINT(0)
    user32.GetRawInputDeviceList(None, ctypes.byref(n), ctypes.sizeof(RAWINPUTDEVICELIST))
    arr = (RAWINPUTDEVICELIST * max(n.value, 1))()
    got = user32.GetRawInputDeviceList(arr, ctypes.byref(n), ctypes.sizeof(RAWINPUTDEVICELIST))
    if got == 0xFFFFFFFF:
        got = 0
    handles, groups, parts, boots, roots = {}, {}, {}, {}, {}
    for d in arr[:got]:
        if d.dwType not in (RIM_TYPEMOUSE, RIM_TYPEKEYBOARD):
            continue
        path = device_path(d.hDevice)
        low = path.lower()
        if not path or "vid_2fe3" in low or "rdp_" in low or low.startswith("\\\\?\\root#"):
            continue
        kind = "k" if d.dwType == RIM_TYPEKEYBOARD else "m"
        group = kind + hashlib.sha1((container_of(path) or low).encode()).hexdigest()[:10]
        handles[d.hDevice] = (kind, group)
        parts[group] = parts.get(group, 0) + 1
        boots.setdefault(group[1:], set()).update(boot_kinds(path_instance(path), roots))
        g = groups.setdefault(group, {"id": group, "kind": kind, "name": "", "vp": ""})
        if not g["name"]:
            g["name"] = product_name(path)
        if not g["vp"] and "vid_" in low and "pid_" in low:
            i = low.index("vid_")
            j = low.find("pid_", i)
            if j > 0:
                g["vp"] = (low[i + 4:i + 8] + ":" + low[j + 4:j + 8]).upper()
    seen = {}
    for g in groups.values():
        other = ("m" if g["kind"] == "k" else "k") + g["id"][1:]
        mine, theirs = parts[g["id"]], parts.get(other, 0)
        g["main"] = mine > theirs or (mine == theirs and boots.get(g["id"][1:]) == {g["kind"]})
        if not g["name"]:
            g["name"] = ("Keyboard" if g["kind"] == "k" else "Mouse") + (" " + g["vp"] if g["vp"] else "")
        key = (g["kind"], g["name"])
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            g["name"] += " (%d)" % seen[key]
    return handles, sorted(groups.values(), key=lambda g: (g["kind"], g["name"].lower()))


def device_labels(devices):
    parts = {}
    for d in devices:
        parts.setdefault(d["id"][1:], []).append(d)
    out = {}
    for key, ds in parts.items():
        main = [d for d in ds if d.get("main")]
        d = main[0] if len(main) == 1 else ds[0]
        if len(main) == 1 or len(ds) == 1:
            out[key] = ("keyboard" if d["kind"] == "k" else "mouse", d["name"])
        else:
            out[key] = ("keyboard and mouse", d["name"])
    return out


class RawInput(threading.Thread):
    def __init__(self, engine, on_devices):
        super().__init__(daemon=True)
        self.engine = engine
        self.on_devices = on_devices
        self.handles = {}
        self.unknown = set()
        self.ready = threading.Event()
        self.error = None
        self._proc = WNDPROC(self._wndproc)
        self.hwnd = None
        self.hook = None
        self.os_down = set()
        self._hook_proc = HOOKPROC(self._key_hook)
        self.mhook = None
        self.os_btn = set()
        self._mhook_proc = HOOKPROC(self._mouse_hook)
        self.hook_at = 0.0
        self.mhook_at = 0.0
        self.list_lock = threading.Lock()
        self.keep = frozenset()
        self.cache = {}
        self.parts = {}
        self.group_of = {}

    def poke(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_RESCAN, 0, 0)

    def keep_listed(self, groups):
        groups = frozenset(groups)
        with self.list_lock:
            if groups == self.keep:
                return
            self.keep = groups
        self.poke()

    def parts_of(self, groups):
        with self.list_lock:
            return sorted(set().union(*[self.parts.get(g, set()) for g in groups]))

    def group_for(self, inst):
        with self.list_lock:
            return self.group_of.get(inst)

    def _listed(self, devices):
        parts, group_of = {}, {}
        for h, (kind, group) in self.handles.items():
            inst = path_instance(device_path(h))
            if not inst:
                continue
            group_of[inst] = group
            parent = dev_prop(inst, KEY_PARENT)
            if isinstance(parent, str) and parent.upper().startswith("USB\\"):
                parts.setdefault(group, set()).add(parent.upper())
        with self.list_lock:
            for g in self.keep:
                if g in parts:
                    for u in self.parts.get(g, ()):
                        if u not in parts[g] and dev_state(u) != "not there":
                            parts[g].add(u)
                elif g in self.parts:
                    parts[g] = self.parts[g]
            self.parts = parts
            self.group_of.update(group_of)
            here = {d["id"] for d in devices}
            for d in devices:
                self.cache[d["id"]] = d
            extra = [self.cache[g] for g in self.keep - here if g in self.cache and
                     any(dev_state(u) != "not there" for u in self.parts.get(g, ()))]
        if extra:
            devices = sorted(devices + extra, key=lambda g: (g["kind"], g["name"].lower()))
        return devices

    def hide(self, kind, on):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_HIDE, (1 if on else 0) | (2 if kind == "m" else 0), 0)

    def _keys_down(self):
        return {vk for vk in range(8, 255) if user32.GetAsyncKeyState(vk) & 0x8000}

    def _buttons_down(self):
        swap = bool(user32.GetSystemMetrics(SM_SWAPBUTTON))
        down = set()
        for vk, name in ((1, "L"), (2, "R"), (4, "M"), (5, "X1"), (6, "X2")):
            if user32.GetAsyncKeyState(vk) & 0x8000:
                down.add({"L": "R", "R": "L"}.get(name, name) if swap else name)
        return down

    def _hide(self, on):
        if on and not self.hook:
            self.os_down = self._keys_down()
            self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
            self.hook_at = time.perf_counter()
            if not self.hook:
                say("Couldn't keep the keys from Windows (error %d)" % ctypes.get_last_error())
        elif not on and self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = None

    def _hide_mouse(self, on):
        if on and not self.mhook:
            self.os_btn = self._buttons_down()
            self.mhook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mhook_proc, None, 0)
            self.mhook_at = time.perf_counter()
            if not self.mhook:
                say("Couldn't keep the mouse from Windows (error %d)" % ctypes.get_last_error())
        elif not on and self.mhook:
            user32.UnhookWindowsHookEx(self.mhook)
            self.mhook = None

    def _lost(self, kind, now):
        if kind == "k":
            new = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
            if not new:
                return
            old, self.hook, self.hook_at = self.hook, new, now
            user32.UnhookWindowsHookEx(old)
            self.os_down = self._keys_down()
        else:
            new = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mhook_proc, None, 0)
            if not new:
                return
            old, self.mhook, self.mhook_at = self.mhook, new, now
            user32.UnhookWindowsHookEx(old)
            self.os_btn = self._buttons_down()

    def _mouse_pass(self, msg, mouse_data):
        name = MOUSE_UP.get(msg)
        if name == "X":
            name = "X%d" % ((mouse_data >> 16) & 0xFFFF)
        if name and name in self.os_btn:
            self.os_btn.discard(name)
            return True
        return False

    def _mouse_hook(self, code, wparam, lparam):
        self.mhook_at = time.perf_counter()
        if code == 0 and self.mhook and self.engine.mhiding:
            m = MSLLHOOKSTRUCT.from_address(lparam)
            if not m.flags & LLMHF_INJECTED and not self._mouse_pass(wparam, m.mouseData):
                return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _key_hook(self, code, wparam, lparam):
        self.hook_at = time.perf_counter()
        if code == 0 and self.hook and self.engine.hiding:
            k = KBDLLHOOKSTRUCT.from_address(lparam)
            mine = not (k.flags & LLKHF_INJECTED)
            if mine:
                up = bool(k.flags & LLKHF_UP)
                if up and k.vkCode in self.os_down:
                    self.os_down.discard(k.vkCode)
                else:
                    flags = (1 if up else 0) | (2 if k.flags & LLKHF_EXTENDED else 0)
                    self.engine.key(self.engine.pick["k"], k.scanCode, flags, k.vkCode,
                                    time.perf_counter())
                    return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def rescan(self):
        self.handles, devices = scan_devices()
        self.unknown = set()
        self.on_devices(self._listed(devices))

    def _group(self, handle, kind):
        hit = self.handles.get(handle)
        if hit is None and handle and handle not in self.unknown:
            self.rescan()
            hit = self.handles.get(handle)
            if hit is None:
                self.unknown.add(handle)
        return hit[1] if hit and hit[0] == kind else None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            self._input(lparam)
        elif msg == WM_INPUT_DEVICE_CHANGE:
            self.rescan()
        elif msg == WM_HIDE:
            if wparam & 2:
                self._hide_mouse(bool(wparam & 1))
            else:
                self._hide(bool(wparam & 1))
        elif msg == WM_RESCAN:
            self.rescan()
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _input(self, lparam):
        size = W.UINT(0)
        head = ctypes.sizeof(RAWINPUTHEADER)
        user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), head)
        if not size.value:
            return
        buf = (ctypes.c_ubyte * size.value)()
        if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), head) != size.value:
            return
        hdr = RAWINPUTHEADER.from_buffer(buf)
        now = time.perf_counter()
        if hdr.dwType == RIM_TYPEMOUSE:
            m = RAWMOUSE.from_buffer(buf, head)
            if (self.mhook and self.engine.mhiding and bool(hdr.hDevice)
                    and (m.lLastX or m.lLastY or m.usButtonFlags) and now - self.mhook_at > HOOK_LOST_S):
                self._lost("m", now)
            self.engine.mouse(self._group(hdr.hDevice, "m"), m.usFlags, m.usButtonFlags,
                              m.usButtonData, m.lLastX, m.lLastY, now)
        elif hdr.dwType == RIM_TYPEKEYBOARD:
            k = RAWKEYBOARD.from_buffer(buf, head)
            mine = bool(hdr.hDevice) and k.VKey != 0xFF
            if self.hook and self.engine.hiding and mine and now - self.hook_at > HOOK_LOST_S:
                self._lost("k", now)
            self.engine.key(self._group(hdr.hDevice, "k"), k.MakeCode, k.Flags, k.VKey, now)

    def run(self):
        try:
            inst = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._proc,
                             hInstance=inst, lpszClassName="XD2JoyHelperInput")
            if not user32.RegisterClassExW(ctypes.byref(wc)):
                raise OSError("RegisterClassEx failed (%d)" % ctypes.get_last_error())
            hwnd = user32.CreateWindowExW(0, "XD2JoyHelperInput", "", 0, 0, 0, 0, 0,
                                          HWND_MESSAGE, None, inst, None)
            if not hwnd:
                raise OSError("CreateWindowEx failed (%d)" % ctypes.get_last_error())
            self.hwnd = hwnd
            devs = (RAWINPUTDEVICE * 2)(
                RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK | RIDEV_DEVNOTIFY, hwnd),
                RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK | RIDEV_DEVNOTIFY, hwnd))
            if not user32.RegisterRawInputDevices(devs, 2, ctypes.sizeof(RAWINPUTDEVICE)):
                raise OSError("RegisterRawInputDevices failed (%d)" % ctypes.get_last_error())
            self.rescan()
        except Exception as e:
            self.error = e
            self.ready.set()
            return
        self.ready.set()
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


USB_CLASS = "{88BAE032-5A81-49F0-BC3D-A4FF138216D6}"
TAKE_IFACE = "{259B6469-CCA5-5D0F-96D9-65FF4B7CDF83}"
WINUSB_INF = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "INF", "winusb.inf")
TAKE_WAIT_S = 120
INJECTED = 0x58443241
AXES = ((0x01, 0x30), (0x01, 0x31), (0x01, 0x38), (0x0C, 0x238))

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
newdev = ctypes.WinDLL("newdev", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
winusb = ctypes.WinDLL("winusb", use_last_error=True)
ole32 = ctypes.WinDLL("ole32")

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
ERROR_CANCELLED = 1223
HIDP_SUCCESS = 0x00110000
SPDIT_CLASSDRIVER = 1
SPDIT_COMPATDRIVER = 2
DI_ENUMSINGLEINF = 0x00010000
DI_FLAGSEX_ALLOWEXCLUDEDDRVS = 0x00000800
DIIDFLAG_NOFINISHINSTALLUI = 2
DIF_REMOVE = 5
SPDRP_CLASSGUID = 0x08
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 1
REG_MULTI_SZ = 7
SEE_MASK_NOCLOSEPROCESS = 0x40
SEE_MASK_NOASYNC = 0x100
SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002
QS_ALLINPUT = 0x04FF
PM_REMOVE = 1
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016


def _guid(text):
    u = uuid.UUID(text)
    return GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


GUID_HID = _guid("4d1e55b2-f16f-11cf-88cb-001111000030")
GUID_TAKE = _guid(TAKE_IFACE)
KEY_PARENT = DEVPROPKEY(_guid("4340a6c5-93fa-4706-972c-7b648008a5a7"), 8)
KEY_CHILDREN = DEVPROPKEY(_guid("4340a6c5-93fa-4706-972c-7b648008a5a7"), 9)
KEY_SERVICE = DEVPROPKEY(_guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 6)
KEY_INF = DEVPROPKEY(_guid("a8b865dd-2e3d-4094-ad97-e593a70c75d6"), 5)
KEY_COMPAT = DEVPROPKEY(_guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 4)


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("ClassGuid", GUID), ("DevInst", W.DWORD),
                ("Reserved", ctypes.c_size_t)]


class SP_DEVINSTALL_PARAMS_W(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("Flags", W.DWORD), ("FlagsEx", W.DWORD),
                ("hwndParent", W.HWND), ("InstallMsgHandler", ctypes.c_void_p),
                ("InstallMsgHandlerContext", ctypes.c_void_p), ("FileQueue", ctypes.c_void_p),
                ("ClassInstallReserved", ctypes.c_size_t), ("Reserved", W.DWORD),
                ("DriverPath", W.WCHAR * 260)]


class SP_DRVINFO_DATA_V2_W(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("DriverType", W.DWORD), ("Reserved", ctypes.c_size_t),
                ("Description", W.WCHAR * 256), ("MfgName", W.WCHAR * 256),
                ("ProviderName", W.WCHAR * 256), ("DriverDate", W.FILETIME),
                ("DriverVersion", ctypes.c_ulonglong)]


class SP_DRVINFO_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("InfDate", W.FILETIME), ("CompatIDsOffset", W.DWORD),
                ("CompatIDsLength", W.DWORD), ("Reserved", ctypes.c_size_t),
                ("SectionName", W.WCHAR * 256), ("InfFileName", W.WCHAR * 260),
                ("DrvDescription", W.WCHAR * 256), ("HardwareID", W.WCHAR * 1)]


class SP_DRVINSTALL_PARAMS(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("Rank", W.DWORD), ("Flags", W.DWORD),
                ("PrivateData", ctypes.c_size_t), ("Reserved", W.DWORD)]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD), ("hEvent", W.HANDLE)]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("fMask", W.ULONG), ("hwnd", W.HWND), ("lpVerb", W.LPCWSTR),
                ("lpFile", W.LPCWSTR), ("lpParameters", W.LPCWSTR), ("lpDirectory", W.LPCWSTR),
                ("nShow", ctypes.c_int), ("hInstApp", W.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", W.LPCWSTR), ("hkeyClass", W.HKEY), ("dwHotKey", W.DWORD),
                ("hIcon", W.HANDLE), ("hProcess", W.HANDLE)]


class USB_INTERFACE_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("bLength", ctypes.c_ubyte), ("bDescriptorType", ctypes.c_ubyte),
                ("bInterfaceNumber", ctypes.c_ubyte), ("bAlternateSetting", ctypes.c_ubyte),
                ("bNumEndpoints", ctypes.c_ubyte), ("bInterfaceClass", ctypes.c_ubyte),
                ("bInterfaceSubClass", ctypes.c_ubyte), ("bInterfaceProtocol", ctypes.c_ubyte),
                ("iInterface", ctypes.c_ubyte)]


class WINUSB_PIPE_INFORMATION(ctypes.Structure):
    _fields_ = [("PipeType", ctypes.c_int), ("PipeId", ctypes.c_ubyte),
                ("MaximumPacketSize", W.USHORT), ("Interval", ctypes.c_ubyte)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT), ("InputReportByteLength", W.USHORT),
                ("OutputReportByteLength", W.USHORT), ("FeatureReportByteLength", W.USHORT),
                ("Reserved", W.USHORT * 17), ("NumberLinkCollectionNodes", W.USHORT),
                ("NumberInputButtonCaps", W.USHORT), ("NumberInputValueCaps", W.USHORT),
                ("NumberInputDataIndices", W.USHORT), ("NumberOutputButtonCaps", W.USHORT),
                ("NumberOutputValueCaps", W.USHORT), ("NumberOutputDataIndices", W.USHORT),
                ("NumberFeatureButtonCaps", W.USHORT), ("NumberFeatureValueCaps", W.USHORT),
                ("NumberFeatureDataIndices", W.USHORT)]


class HIDP_BUTTON_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", W.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", W.USHORT), ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT),
                ("LinkUsagePage", W.USHORT), ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("ReportCount", W.USHORT), ("Reserved2", W.USHORT), ("Reserved", W.ULONG * 9),
                ("UsageMin", W.USHORT), ("UsageMax", W.USHORT), ("StringMin", W.USHORT),
                ("StringMax", W.USHORT), ("DesignatorMin", W.USHORT), ("DesignatorMax", W.USHORT),
                ("DataIndexMin", W.USHORT), ("DataIndexMax", W.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", W.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", W.USHORT), ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT),
                ("LinkUsagePage", W.USHORT), ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte), ("BitSize", W.USHORT),
                ("ReportCount", W.USHORT), ("Reserved2", W.USHORT * 5), ("UnitsExp", W.ULONG),
                ("Units", W.ULONG), ("LogicalMin", W.LONG), ("LogicalMax", W.LONG),
                ("PhysicalMin", W.LONG), ("PhysicalMax", W.LONG),
                ("UsageMin", W.USHORT), ("UsageMax", W.USHORT), ("StringMin", W.USHORT),
                ("StringMax", W.USHORT), ("DesignatorMin", W.USHORT), ("DesignatorMax", W.USHORT),
                ("DataIndexMin", W.USHORT), ("DataIndexMax", W.USHORT)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD), ("time", W.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT_U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", W.DWORD), ("u", _INPUT_U)]


HDI = ctypes.c_void_p
PDEV = ctypes.POINTER(SP_DEVINFO_DATA)
PDRV = ctypes.POINTER(SP_DRVINFO_DATA_V2_W)
setupapi.SetupDiCreateDeviceInfoList.argtypes = [ctypes.c_void_p, W.HWND]
setupapi.SetupDiCreateDeviceInfoList.restype = HDI
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [HDI]
setupapi.SetupDiOpenDeviceInfoW.argtypes = [HDI, W.LPCWSTR, W.HWND, W.DWORD, PDEV]
setupapi.SetupDiOpenDeviceInfoW.restype = W.BOOL
setupapi.SetupDiGetDeviceInstallParamsW.argtypes = [HDI, PDEV, ctypes.POINTER(SP_DEVINSTALL_PARAMS_W)]
setupapi.SetupDiGetDeviceInstallParamsW.restype = W.BOOL
setupapi.SetupDiSetDeviceInstallParamsW.argtypes = [HDI, PDEV, ctypes.POINTER(SP_DEVINSTALL_PARAMS_W)]
setupapi.SetupDiSetDeviceInstallParamsW.restype = W.BOOL
setupapi.SetupDiBuildDriverInfoList.argtypes = [HDI, PDEV, W.DWORD]
setupapi.SetupDiBuildDriverInfoList.restype = W.BOOL
setupapi.SetupDiEnumDriverInfoW.argtypes = [HDI, PDEV, W.DWORD, W.DWORD, PDRV]
setupapi.SetupDiEnumDriverInfoW.restype = W.BOOL
setupapi.SetupDiGetDriverInfoDetailW.argtypes = [HDI, PDEV, PDRV, ctypes.c_void_p, W.DWORD,
                                                 ctypes.POINTER(W.DWORD)]
setupapi.SetupDiGetDriverInfoDetailW.restype = W.BOOL
setupapi.SetupDiGetDriverInstallParamsW.argtypes = [HDI, PDEV, PDRV, ctypes.POINTER(SP_DRVINSTALL_PARAMS)]
setupapi.SetupDiGetDriverInstallParamsW.restype = W.BOOL
setupapi.SetupDiSetDeviceRegistryPropertyW.argtypes = [HDI, PDEV, W.DWORD, ctypes.c_void_p, W.DWORD]
setupapi.SetupDiSetDeviceRegistryPropertyW.restype = W.BOOL
setupapi.SetupDiCreateDevRegKeyW.argtypes = [HDI, PDEV, W.DWORD, W.DWORD, W.DWORD, ctypes.c_void_p,
                                             W.LPCWSTR]
setupapi.SetupDiCreateDevRegKeyW.restype = ctypes.c_void_p
setupapi.SetupDiCallClassInstaller.argtypes = [W.DWORD, HDI, PDEV]
setupapi.SetupDiCallClassInstaller.restype = W.BOOL
newdev.DiInstallDevice.argtypes = [W.HWND, HDI, PDEV, PDRV, W.DWORD, ctypes.POINTER(W.BOOL)]
newdev.DiInstallDevice.restype = W.BOOL
advapi32.RegSetValueExW.argtypes = [ctypes.c_void_p, W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD]
advapi32.RegSetValueExW.restype = W.LONG
advapi32.RegDeleteValueW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
advapi32.RegDeleteValueW.restype = W.LONG
advapi32.RegCloseKey.argtypes = [ctypes.c_void_p]
advapi32.RegCloseKey.restype = W.LONG
shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = W.BOOL
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, W.DWORD]
ole32.CoInitializeEx.restype = ctypes.c_long
cfgmgr.CM_Get_DevNode_Status.argtypes = [ctypes.POINTER(W.ULONG), ctypes.POINTER(W.ULONG), W.DWORD, W.ULONG]
cfgmgr.CM_Get_DevNode_Status.restype = W.DWORD
cfgmgr.CM_Get_Device_Interface_List_SizeW.argtypes = [ctypes.POINTER(W.ULONG), ctypes.POINTER(GUID),
                                                      W.LPCWSTR, W.ULONG]
cfgmgr.CM_Get_Device_Interface_List_SizeW.restype = W.DWORD
cfgmgr.CM_Get_Device_Interface_ListW.argtypes = [ctypes.POINTER(GUID), W.LPCWSTR, ctypes.c_void_p,
                                                 W.ULONG, W.ULONG]
cfgmgr.CM_Get_Device_Interface_ListW.restype = W.DWORD
hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = W.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = W.BOOLEAN
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetButtonCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_BUTTON_CAPS), ctypes.POINTER(W.USHORT),
                                   ctypes.c_void_p]
hid.HidP_GetButtonCaps.restype = ctypes.c_long
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(W.USHORT),
                                  ctypes.c_void_p]
hid.HidP_GetValueCaps.restype = ctypes.c_long
hid.HidP_MaxUsageListLength.argtypes = [ctypes.c_int, W.USHORT, ctypes.c_void_p]
hid.HidP_MaxUsageListLength.restype = W.ULONG
hid.HidP_GetUsages.argtypes = [ctypes.c_int, W.USHORT, W.USHORT, ctypes.POINTER(W.USHORT),
                               ctypes.POINTER(W.ULONG), ctypes.c_void_p, ctypes.c_void_p, W.ULONG]
hid.HidP_GetUsages.restype = ctypes.c_long
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, W.USHORT, W.USHORT, W.USHORT, ctypes.POINTER(W.ULONG),
                                   ctypes.c_void_p, ctypes.c_void_p, W.ULONG]
hid.HidP_GetUsageValue.restype = ctypes.c_long
winusb.WinUsb_Initialize.argtypes = [W.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
winusb.WinUsb_Initialize.restype = W.BOOL
winusb.WinUsb_Free.argtypes = [ctypes.c_void_p]
winusb.WinUsb_Free.restype = W.BOOL
winusb.WinUsb_QueryInterfaceSettings.argtypes = [ctypes.c_void_p, ctypes.c_ubyte,
                                                 ctypes.POINTER(USB_INTERFACE_DESCRIPTOR)]
winusb.WinUsb_QueryInterfaceSettings.restype = W.BOOL
winusb.WinUsb_QueryPipe.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_ubyte,
                                    ctypes.POINTER(WINUSB_PIPE_INFORMATION)]
winusb.WinUsb_QueryPipe.restype = W.BOOL
winusb.WinUsb_ReadPipe.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_void_p, W.ULONG,
                                   ctypes.POINTER(W.ULONG), ctypes.POINTER(OVERLAPPED)]
winusb.WinUsb_ReadPipe.restype = W.BOOL
winusb.WinUsb_GetOverlappedResult.argtypes = [ctypes.c_void_p, ctypes.POINTER(OVERLAPPED),
                                              ctypes.POINTER(W.DWORD), W.BOOL]
winusb.WinUsb_GetOverlappedResult.restype = W.BOOL
winusb.WinUsb_AbortPipe.argtypes = [ctypes.c_void_p, ctypes.c_ubyte]
winusb.WinUsb_AbortPipe.restype = W.BOOL
kernel32.CreateEventW.argtypes = [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR]
kernel32.CreateEventW.restype = W.HANDLE
kernel32.OpenEventW.argtypes = [W.DWORD, W.BOOL, W.LPCWSTR]
kernel32.OpenEventW.restype = W.HANDLE
kernel32.SetEvent.argtypes = [W.HANDLE]
kernel32.SetEvent.restype = W.BOOL
kernel32.ResetEvent.argtypes = [W.HANDLE]
kernel32.ResetEvent.restype = W.BOOL
kernel32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel32.OpenProcess.restype = W.HANDLE
kernel32.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
kernel32.WaitForSingleObject.restype = W.DWORD
kernel32.WaitForMultipleObjects.argtypes = [W.DWORD, ctypes.POINTER(W.HANDLE), W.BOOL, W.DWORD]
CONSOLE_HANDLER = ctypes.WINFUNCTYPE(W.BOOL, W.DWORD)
kernel32.SetConsoleCtrlHandler.argtypes = [CONSOLE_HANDLER, W.BOOL]
CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT = 0, 1, 2
CLOSE_S = 4.0
kernel32.WaitForMultipleObjects.restype = W.DWORD
user32.MsgWaitForMultipleObjects.argtypes = [W.DWORD, ctypes.POINTER(W.HANDLE), W.BOOL, W.DWORD, W.DWORD]
user32.MsgWaitForMultipleObjects.restype = W.DWORD
user32.PeekMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
user32.PeekMessageW.restype = W.BOOL
user32.SendInput.argtypes = [W.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = W.UINT
user32.SystemParametersInfoW.argtypes = [W.UINT, W.UINT, ctypes.c_void_p, W.UINT]
user32.SystemParametersInfoW.restype = W.BOOL


def dev_prop(inst, key):
    node = W.DWORD(0)
    if cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), inst, 0) != 0:
        return None
    kind = W.ULONG(0)
    size = W.ULONG(0)
    cfgmgr.CM_Get_DevNode_PropertyW(node, ctypes.byref(key), ctypes.byref(kind), None, ctypes.byref(size), 0)
    if not size.value:
        return ""
    buf = (ctypes.c_ubyte * size.value)()
    if cfgmgr.CM_Get_DevNode_PropertyW(node, ctypes.byref(key), ctypes.byref(kind), buf,
                                       ctypes.byref(size), 0) != 0:
        return ""
    if kind.value == 0x12:
        return ctypes.wstring_at(ctypes.addressof(buf))
    if kind.value == 0x2012:
        return [s for s in ctypes.wstring_at(ctypes.addressof(buf), size.value // 2).split("\0") if s]
    return bytes(buf).hex()


def path_instance(path):
    p = path[4:] if path.startswith("\\\\?\\") else path
    cut = p.rfind("#{")
    return (p[:cut] if cut > 0 else p).replace("#", "\\").upper()


def boot_kinds(inst, cache):
    parent = dev_prop(inst, KEY_PARENT)
    if not isinstance(parent, str) or not parent.upper().startswith("USB\\"):
        return set()
    parent = root = parent.upper()
    if "&MI_" in parent:
        up = dev_prop(parent, KEY_PARENT)
        if isinstance(up, str) and up.upper().startswith("USB\\"):
            root = up.upper()
    if root not in cache:
        kids = dev_prop(root, KEY_CHILDREN) if root != parent else None
        kinds = set()
        for u in ([k.upper() for k in kids] if isinstance(kids, list) and kids else [parent]):
            ids = dev_prop(u, KEY_COMPAT)
            ids = [i.upper() for i in ids] if isinstance(ids, list) else []
            if r"USB\CLASS_03&SUBCLASS_01&PROT_01" in ids:
                kinds.add("k")
            if r"USB\CLASS_03&SUBCLASS_01&PROT_02" in ids:
                kinds.add("m")
        cache[root] = kinds
    return cache[root]


def dev_state(inst):
    node = W.DWORD(0)
    if cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), inst, 0) != 0:
        return "not there"
    st = W.ULONG(0)
    problem = W.ULONG(0)
    if cfgmgr.CM_Get_DevNode_Status(ctypes.byref(st), ctypes.byref(problem), node, 0) != 0:
        return "unknown"
    if st.value & 0x400:
        return "problem %d" % problem.value
    return "started" if st.value & 0x8 else "not started"


def dev_driver(inst):
    return {"inf": dev_prop(inst, KEY_INF), "service": dev_prop(inst, KEY_SERVICE), "state": dev_state(inst)}


def iface_paths(guid, inst=None):
    size = W.ULONG(0)
    if cfgmgr.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), ctypes.byref(guid), inst, 0) != 0:
        return []
    if size.value <= 1:
        return []
    buf = ctypes.create_unicode_buffer(size.value)
    if cfgmgr.CM_Get_Device_Interface_ListW(ctypes.byref(guid), inst, buf, size.value, 0) != 0:
        return []
    return [p for p in ctypes.wstring_at(ctypes.addressof(buf), size.value).split("\0") if p]


def _err():
    e = ctypes.get_last_error() & 0xFFFFFFFF
    return "error %d" % e if e < 0x10000 else "error 0x%08X" % e


def _open_dev(inst):
    hdi = setupapi.SetupDiCreateDeviceInfoList(None, None)
    if not hdi or hdi == INVALID_HANDLE:
        raise OSError("SetupAPI wouldn't start (%s)" % _err())
    dev = SP_DEVINFO_DATA()
    dev.cbSize = ctypes.sizeof(dev)
    if not setupapi.SetupDiOpenDeviceInfoW(hdi, inst, None, 0, ctypes.byref(dev)):
        err = _err()
        setupapi.SetupDiDestroyDeviceInfoList(hdi)
        raise OSError("Windows has no such device (%s)" % err)
    return hdi, dev


def _driver_nodes(hdi, dev, kind, inf=None):
    p = SP_DEVINSTALL_PARAMS_W()
    p.cbSize = ctypes.sizeof(p)
    if setupapi.SetupDiGetDeviceInstallParamsW(hdi, ctypes.byref(dev), ctypes.byref(p)):
        p.FlagsEx |= DI_FLAGSEX_ALLOWEXCLUDEDDRVS
        if inf:
            p.Flags |= DI_ENUMSINGLEINF
            p.DriverPath = inf
        setupapi.SetupDiSetDeviceInstallParamsW(hdi, ctypes.byref(dev), ctypes.byref(p))
    if not setupapi.SetupDiBuildDriverInfoList(hdi, ctypes.byref(dev), kind):
        raise OSError("couldn't list its drivers (%s)" % _err())
    out = []
    i = 0
    while True:
        drv = SP_DRVINFO_DATA_V2_W()
        drv.cbSize = ctypes.sizeof(drv)
        if not setupapi.SetupDiEnumDriverInfoW(hdi, ctypes.byref(dev), kind, i, ctypes.byref(drv)):
            return out
        i += 1
        buf = ctypes.create_string_buffer(16384)
        det = SP_DRVINFO_DETAIL_DATA_W.from_buffer(buf)
        det.cbSize = ctypes.sizeof(SP_DRVINFO_DETAIL_DATA_W)
        need = W.DWORD(0)
        name = section = ""
        if setupapi.SetupDiGetDriverInfoDetailW(hdi, ctypes.byref(dev), ctypes.byref(drv), buf,
                                                ctypes.sizeof(buf), ctypes.byref(need)):
            name = Path(det.InfFileName).name.lower()
            section = det.SectionName
        ip = SP_DRVINSTALL_PARAMS()
        ip.cbSize = ctypes.sizeof(ip)
        rank = ip.Rank if setupapi.SetupDiGetDriverInstallParamsW(
            hdi, ctypes.byref(dev), ctypes.byref(drv), ctypes.byref(ip)) else 0xFFFFFFFF
        out.append((drv, name, section, rank))


def _set_iface(hdi, dev, on):
    key = setupapi.SetupDiCreateDevRegKeyW(hdi, ctypes.byref(dev), DICS_FLAG_GLOBAL, 0, DIREG_DEV, None, None)
    if not key or key == INVALID_HANDLE:
        if on:
            raise OSError("couldn't open its settings (%s)" % _err())
        return
    try:
        if on:
            data = ctypes.create_unicode_buffer(TAKE_IFACE + "\0")
            err = advapi32.RegSetValueExW(key, "DeviceInterfaceGUIDs", 0, REG_MULTI_SZ, data, ctypes.sizeof(data))
            if err:
                raise OSError("couldn't write its interface id (error %d)" % err)
        else:
            advapi32.RegDeleteValueW(key, "DeviceInterfaceGUIDs")
    finally:
        advapi32.RegCloseKey(key)


def _install(hdi, dev, drv):
    reboot = W.BOOL(0)
    t0 = time.perf_counter()
    ok = newdev.DiInstallDevice(None, hdi, ctypes.byref(dev), ctypes.byref(drv),
                                DIIDFLAG_NOFINISHINSTALLUI, ctypes.byref(reboot))
    err = _err()
    return {"ok": bool(ok), "error": None if ok else err,
            "ms": round((time.perf_counter() - t0) * 1000), "reboot": bool(reboot.value)}


def set_driver(inst, mode):
    res = {"before": dev_driver(inst)}
    hdi = None
    try:
        hdi, dev = _open_dev(inst)
        if mode == "usb":
            _set_iface(hdi, dev, True)
            cls = ctypes.create_unicode_buffer(USB_CLASS)
            if not setupapi.SetupDiSetDeviceRegistryPropertyW(hdi, ctypes.byref(dev), SPDRP_CLASSGUID, cls,
                                                              (len(USB_CLASS) + 1) * 2):
                raise OSError("couldn't make it a USB device (%s)" % _err())
            setupapi.SetupDiDestroyDeviceInfoList(hdi)
            hdi = None
            hdi, dev = _open_dev(inst)
            pick = [x for x in _driver_nodes(hdi, dev, SPDIT_CLASSDRIVER, WINUSB_INF)
                    if x[1] == "winusb.inf" and x[2].upper() == "WINUSB"]
            if not pick:
                raise OSError("Windows offers no WinUSB for it")
            res.update(_install(hdi, dev, pick[0][0]))
        elif res["before"]["state"] == "not there":
            ok = setupapi.SetupDiCallClassInstaller(DIF_REMOVE, hdi, ctypes.byref(dev))
            res.update(ok=bool(ok), error=None if ok else _err(), forgot=True)
        else:
            nodes = _driver_nodes(hdi, dev, SPDIT_COMPATDRIVER)
            if not nodes:
                raise OSError("Windows has no driver for it")
            best = min(nodes, key=lambda x: x[3])
            res["chose"] = "%s [%s]" % (best[1], best[2])
            res.update(_install(hdi, dev, best[0]))
            _set_iface(hdi, dev, False)
    except OSError as e:
        res.update(ok=False, error=str(e))
    finally:
        if hdi:
            setupapi.SetupDiDestroyDeviceInfoList(hdi)
    res["after"] = dev_driver(inst)
    return res


def _write_json(path, data):
    try:
        Path(path).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _take_ids(ids):
    return [dict(id=i, **set_driver(i, "usb")) for i in ids]


def _give_back_ids(ids):
    return [dict(id=i, **set_driver(i, "back")) for i in ids]


def keeper_serve(pid, cmd_name, done_name, prefix):
    cmd_file, res_file = prefix + ".cmd", prefix + ".res"
    proc = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not proc:
        return 0
    cmd_ev = kernel32.OpenEventW(SYNCHRONIZE, False, cmd_name)
    done_ev = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, done_name)
    taken = set()
    order = []

    def give_all():
        if taken:
            first = [i for i in order if i in taken]
            _give_back_ids(first + sorted(taken - set(first)))
            taken.clear()

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_QUERYENDSESSION:
            return 1
        if msg == WM_ENDSESSION and wparam:
            give_all()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc_cb = WNDPROC(wndproc)
    inst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=proc_cb, hInstance=inst,
                     lpszClassName="XD2JoyKeeper")
    user32.RegisterClassExW(ctypes.byref(wc))
    user32.CreateWindowExW(0, "XD2JoyKeeper", "XD2Joy keeper", 0, 0, 0, 0, 0, None, None, inst, None)
    hs = (W.HANDLE * 2)(proc, cmd_ev)
    msg = W.MSG()
    while True:
        r = user32.MsgWaitForMultipleObjects(2, hs, False, 0xFFFFFFFF, QS_ALLINPUT)
        if r == 0 or r == 0xFFFFFFFF:
            break
        if r == 1:
            try:
                cmd = json.loads(Path(cmd_file).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cmd = None
            if cmd:
                if isinstance(cmd.get("order"), list):
                    order[:] = [i for i in cmd["order"] if isinstance(i, str)]
                res = {"seq": cmd.get("seq")}
                give = [i for i in cmd.get("give", []) if i in taken]
                if give:
                    res["back"] = _give_back_ids(give)
                    taken.difference_update(give)
                take = [i for i in cmd.get("take", []) if i not in taken]
                if take:
                    res["took"] = _take_ids(take)
                    for one in res["took"]:
                        if one.get("ok"):
                            taken.add(one["id"])
                _write_json(res_file, res)
                kernel32.SetEvent(done_ev)
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    give_all()
    kernel32.CloseHandle(proc)
    for f in (cmd_file, res_file):
        try:
            os.remove(f)
        except OSError:
            pass
    return 0


def keeper_main(args):
    if len(args) >= 5 and args[0] == "serve":
        try:
            return keeper_serve(int(args[1]), args[2], args[3], args[4])
        except ValueError:
            return 2
    if len(args) >= 2 and args[0] == "giveback":
        _write_json(args[1], {"back": _give_back_ids(args[2:])})
        return 0
    return 2


def keeper_command(args):
    params = " ".join('"%s"' % a for a in args)
    if getattr(sys, "frozen", False):
        return sys.executable, "--keeper " + params
    return sys.executable, '"%s" --keeper %s' % (Path(__file__).resolve(), params)


def run_keeper(args):
    ole32.CoInitializeEx(None, 0x6)
    file, params = keeper_command(args)
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    sei.lpVerb = "runas"
    sei.lpFile = file
    sei.lpParameters = params
    sei.lpDirectory = str(Path(file).parent)
    sei.nShow = 0
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        return None, ("Windows said no" if err == ERROR_CANCELLED else
                      "Windows couldn't start it (error %d)" % err)
    return sei.hProcess, None


class Collection:
    def __init__(self, n, inst, group, ppd):
        self.n = n
        self.inst = inst
        self.group = group
        self.ppd = ppd
        caps = HIDP_CAPS()
        hid.HidP_GetCaps(ppd, ctypes.byref(caps))
        self.top = (caps.UsagePage, caps.Usage)
        self.kind = ("k" if self.top in ((0x01, 0x06), (0x01, 0x07)) else
                     "m" if self.top in ((0x01, 0x01), (0x01, 0x02)) else
                     "c" if self.top == (0x0C, 0x01) else None)
        self.inlen = caps.InputReportByteLength
        rids = set()
        self.axes = {}
        n = W.USHORT(caps.NumberInputButtonCaps)
        if n.value:
            bc = (HIDP_BUTTON_CAPS * n.value)()
            if hid.HidP_GetButtonCaps(0, bc, ctypes.byref(n), ppd) == HIDP_SUCCESS:
                rids.update(b.ReportID for b in bc[:n.value])
        n = W.USHORT(caps.NumberInputValueCaps)
        if n.value:
            vc = (HIDP_VALUE_CAPS * n.value)()
            if hid.HidP_GetValueCaps(0, vc, ctypes.byref(n), ppd) == HIDP_SUCCESS:
                for v in vc[:n.value]:
                    rids.add(v.ReportID)
                    last = v.UsageMax if v.IsRange else v.UsageMin
                    for page, usage in AXES:
                        if v.UsagePage == page and v.UsageMin <= usage <= last:
                            self.axes.setdefault((page, usage), (v.BitSize, v.LogicalMin, bool(v.IsAbsolute)))
        if self.kind == "m" and self.axes.get((0x01, 0x30), (0, 0, False))[2]:
            self.kind = None
        self.rids = rids or {0}
        self.maxu = {p: hid.HidP_MaxUsageListLength(0, p, ppd) for p in (0x07, 0x09, 0x0C)}

    def usages(self, page, buf):
        n = self.maxu.get(page, 0)
        if not n:
            return None
        ul = (W.USHORT * n)()
        got = W.ULONG(n)
        if hid.HidP_GetUsages(0, page, 0, ul, ctypes.byref(got), self.ppd, buf, self.inlen) != HIDP_SUCCESS:
            return None
        return set(ul[:got.value])

    def value(self, page, usage, buf):
        if (page, usage) not in self.axes:
            return 0
        v = W.ULONG(0)
        if hid.HidP_GetUsageValue(0, page, 0, usage, ctypes.byref(v), self.ppd, buf, self.inlen) != HIDP_SUCCESS:
            return 0
        bits, low, _ = self.axes[(page, usage)]
        x = v.value
        if low < 0 and 0 < bits < 32 and x >= 1 << (bits - 1):
            x -= 1 << bits
        return x

    def free(self):
        if self.ppd:
            hid.HidD_FreePreparsedData(self.ppd)
            self.ppd = None


class UsbPart:
    def __init__(self, inst, cols):
        self.inst = inst
        self.cols = cols
        self.ids = any(r for c in cols for r in c.rids)
        self.by_rid = {}
        for c in cols:
            for r in c.rids:
                self.by_rid.setdefault(r, c)

    def groups(self):
        return {c.group for c in self.cols if c.group}

    def decode(self, rep):
        rid = rep[0] if self.ids and rep else 0
        c = self.by_rid.get(rid)
        if c is None or c.kind is None or not c.inlen or not c.ppd:
            return None
        data = (rep if self.ids else b"\0" + rep)[:c.inlen].ljust(c.inlen, b"\0")
        return c, ctypes.create_string_buffer(data, c.inlen)

    def free(self):
        for c in self.cols:
            c.free()


def usb_part(inst, group_for):
    cols = []
    kids = dev_prop(inst, KEY_CHILDREN)
    for child in (kids if isinstance(kids, list) else []):
        child = child.upper()
        paths = iface_paths(GUID_HID, child)
        if not paths:
            continue
        h = kernel32.CreateFileW(paths[0], 0, 3, None, 3, 0, None)
        if not h or h == INVALID_HANDLE:
            continue
        ppd = ctypes.c_void_p()
        got = hid.HidD_GetPreparsedData(h, ctypes.byref(ppd))
        kernel32.CloseHandle(h)
        if got:
            cols.append(Collection(len(cols), child, group_for(child), ppd))
    return UsbPart(inst, cols)


USAGE_SC = {}
for _sc, _u in SC.items():
    USAGE_SC.setdefault(_u, (_sc, False))
for _sc, _u in SC_E0.items():
    USAGE_SC.setdefault(_u, (_sc, True))
for (_sc, _e0), _bit in MODS.items():
    USAGE_SC[0xE0 + _bit.bit_length() - 1] = (_sc, _e0)
USAGE_SC.setdefault(0x32, (0x2B, False))
USAGE_VK = {0x48: (0x13, 0), 0x53: (0x90, 1)}
MEDIA_VK = {0xE9: 0xAF, 0xEA: 0xAE, 0xE2: 0xAD, 0xCD: 0xB3, 0xB5: 0xB0, 0xB6: 0xB1, 0xB7: 0xB2}
MOUSE_PRESS = {1: (0x0002, 0), 2: (0x0008, 0), 3: (0x0020, 0), 4: (0x0080, 1), 5: (0x0080, 2)}
MOUSE_FREE = {1: (0x0004, 0), 2: (0x0010, 0), 3: (0x0040, 0), 4: (0x0100, 1), 5: (0x0100, 2)}


def is_mod(u):
    return 0xE0 <= u <= 0xE7


def key_of(u):
    return ("mod", 1 << (u - 0xE0)) if is_mod(u) else ("key", u)


def _send_input(items):
    if items:
        arr = (INPUT * len(items))(*items)
        user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))


def pc_key(u, up):
    i = INPUT(type=1)
    if u in USAGE_SC:
        sc, e0 = USAGE_SC[u]
        i.u.ki.wScan = sc
        i.u.ki.dwFlags = 0x0008 | (0x0001 if e0 else 0) | (0x0002 if up else 0)
    elif u in USAGE_VK:
        vk, ext = USAGE_VK[u]
        i.u.ki.wVk = vk
        i.u.ki.dwFlags = (0x0001 if ext else 0) | (0x0002 if up else 0)
    else:
        return
    i.u.ki.dwExtraInfo = INJECTED
    _send_input([i])


def pc_media(u, up):
    i = INPUT(type=1)
    i.u.ki.wVk = MEDIA_VK[u]
    i.u.ki.dwFlags = 0x0001 | (0x0002 if up else 0)
    i.u.ki.dwExtraInfo = INJECTED
    _send_input([i])


def pc_mouse(dx, dy, wheel, hwheel, press, free):
    items = []

    def add(x, y, data, flags):
        i = INPUT(type=0)
        i.u.mi.dx, i.u.mi.dy, i.u.mi.mouseData, i.u.mi.dwFlags = x, y, data & 0xFFFFFFFF, flags
        i.u.mi.dwExtraInfo = INJECTED
        items.append(i)

    if dx or dy:
        add(dx, dy, 0, 0x0001)
    for b in press:
        add(0, 0, MOUSE_PRESS[b][1], MOUSE_PRESS[b][0])
    for b in free:
        add(0, 0, MOUSE_FREE[b][1], MOUSE_FREE[b][0])
    if wheel:
        add(0, 0, 120 * wheel, 0x0800)
    if hwheel:
        add(0, 0, 120 * hwheel, 0x1000)
    _send_input(items)


def typematic():
    delay = W.UINT(1)
    speed = W.DWORD(31)
    user32.SystemParametersInfoW(0x0016, 0, ctypes.byref(delay), 0)
    user32.SystemParametersInfoW(0x000A, 0, ctypes.byref(speed), 0)
    return 0.25 * (min(delay.value, 3) + 1), 1.0 / (2.5 + 27.5 * min(speed.value, 31) / 31)


class _Pipe:
    def __init__(self, part):
        self.part = part
        self.inst = part.inst
        self.h = None
        self.wh = None
        self.ev = None
        self.pending = False

    def open(self):
        paths = iface_paths(GUID_TAKE, self.inst)
        if not paths:
            return False
        h = kernel32.CreateFileW(paths[0], GENERIC_READ | GENERIC_WRITE, 3, None, 3, FILE_FLAG_OVERLAPPED, None)
        if not h or h == INVALID_HANDLE:
            return False
        self.h = h
        wh = ctypes.c_void_p()
        if not winusb.WinUsb_Initialize(h, ctypes.byref(wh)):
            return False
        self.wh = wh
        ifd = USB_INTERFACE_DESCRIPTOR()
        if not winusb.WinUsb_QueryInterfaceSettings(wh, 0, ctypes.byref(ifd)):
            return False
        self.pipe = None
        for k in range(ifd.bNumEndpoints):
            pi = WINUSB_PIPE_INFORMATION()
            if winusb.WinUsb_QueryPipe(wh, 0, k, ctypes.byref(pi)) and pi.PipeType == 3 and pi.PipeId & 0x80:
                self.pipe = pi.PipeId
                self.size = pi.MaximumPacketSize
                break
        if self.pipe is None:
            return False
        self.buf = ctypes.create_string_buffer(self.size)
        self.ev = kernel32.CreateEventW(None, True, False, None)
        self.ov = OVERLAPPED()
        self.ov.hEvent = self.ev
        return self.read()

    def read(self):
        kernel32.ResetEvent(self.ev)
        self.pending = True
        if not winusb.WinUsb_ReadPipe(self.wh, self.pipe, self.buf, self.size, None, ctypes.byref(self.ov)):
            err = ctypes.get_last_error()
            if err != ERROR_IO_PENDING:
                self.pending = False
                return False
        return True

    def done(self):
        self.pending = False
        n = W.DWORD(0)
        if not winusb.WinUsb_GetOverlappedResult(self.wh, ctypes.byref(self.ov), ctypes.byref(n), False):
            return None
        return self.buf.raw[:n.value]

    def close(self):
        if self.wh:
            if self.pending:
                winusb.WinUsb_AbortPipe(self.wh, self.pipe)
                n = W.DWORD(0)
                winusb.WinUsb_GetOverlappedResult(self.wh, ctypes.byref(self.ov), ctypes.byref(n), True)
                self.pending = False
            winusb.WinUsb_Free(self.wh)
            self.wh = None
        if self.h:
            kernel32.CloseHandle(self.h)
            self.h = None
        if self.ev:
            kernel32.CloseHandle(self.ev)
            self.ev = None


class UsbInput(threading.Thread):
    def __init__(self, engine):
        super().__init__(daemon=True)
        self.engine = engine
        self.cond = threading.Condition()
        self.want = {}
        self.open = {}
        self.retry = {}
        self.wake = kernel32.CreateEventW(None, False, False, None)
        self.kheld = {}
        self.mheld = {}
        self.cheld = {}
        self.kdown = {}
        self.mdown = {}
        self.kpc = {}
        self.mpc = {}
        self.rep = {}
        self.delay, self.period = typematic()
        self.on_change = None

    def set_parts(self, parts):
        with self.cond:
            self.want = dict(parts)
        kernel32.SetEvent(self.wake)

    def wait_open(self, ids, secs):
        end = time.perf_counter() + secs
        with self.cond:
            while True:
                have = set(self.open)
                if (have >= ids if ids else not have) or time.perf_counter() >= end:
                    return have & ids if ids else have
                self.cond.wait(max(0.01, end - time.perf_counter()))

    def wait_closed(self, ids, secs):
        end = time.perf_counter() + secs
        with self.cond:
            while set(self.open) & set(ids):
                if time.perf_counter() >= end:
                    return False
                self.cond.wait(max(0.01, end - time.perf_counter()))
            return True

    def run(self):
        check = 0.0
        while True:
            now = time.perf_counter()
            if now >= check:
                self._reconcile(now)
                check = now + 0.5
            pipes = list(self.open.values())
            arr = (W.HANDLE * (1 + len(pipes)))(self.wake, *[p.ev for p in pipes])
            wait = max(0.0, check - now)
            for _, at in self.rep.values():
                wait = min(wait, max(0.0, at - now))
            w = kernel32.WaitForMultipleObjects(len(arr), arr, False, int(wait * 1000))
            now = time.perf_counter()
            if w == 0:
                check = 0.0
            elif 1 <= w <= len(pipes):
                p = pipes[w - 1]
                rep = p.done()
                if rep is not None:
                    self._report(p.part, rep, now)
                if rep is None or not p.read():
                    self._drop(p, now)
            self._for_switch()
            self._repeat(now)

    def _reconcile(self, now):
        with self.cond:
            want = dict(self.want)
        for p in [p for i, p in self.open.items() if i not in want]:
            self._drop(p, now)
        opened = False
        for inst, part in want.items():
            if inst in self.open or now < self.retry.get(inst, 0):
                continue
            p = _Pipe(part)
            if p.open():
                with self.cond:
                    self.open[inst] = p
                opened = True
            else:
                p.close()
                self.retry[inst] = now + 0.5
        if opened:
            with self.cond:
                self.cond.notify_all()
            self._changed()

    def _changed(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def _drop(self, p, now):
        p.close()
        with self.cond:
            if self.open.get(p.inst) is p:
                del self.open[p.inst]
            self.cond.notify_all()
        self.retry[p.inst] = now + 0.5
        ks, ms = set(), set()
        for c in p.part.cols:
            key = (p.inst, c.n)
            if key in self.kheld:
                ks.add(self.kheld.pop(key)[0])
            if key in self.mheld:
                ms.add(self.mheld.pop(key)[0])
            for u in sorted(self.cheld.pop(key, ())):
                pc_media(u, True)
        for g in ks:
            self._keys(g, now)
        for g in ms:
            self._buttons(g, now, 0, 0, 0, 0)
        self._changed()

    def _report(self, part, rep, now):
        hit = part.decode(rep)
        if not hit:
            return
        c, buf = hit
        key = (part.inst, c.n)
        if c.kind == "k":
            keys = c.usages(0x07, buf)
            if keys is not None:
                self.kheld[key] = (c.group, {u for u in keys if u > 3})
                self._keys(c.group, now)
        elif c.kind == "m":
            btn = c.usages(0x09, buf)
            if btn is not None:
                self.mheld[key] = (c.group, {b for b in btn if 1 <= b <= 8})
            self._buttons(c.group, now, c.value(0x01, 0x30, buf), c.value(0x01, 0x31, buf),
                          c.value(0x01, 0x38, buf), c.value(0x0C, 0x238, buf))
        elif c.kind == "c":
            keys = c.usages(0x0C, buf)
            if keys is not None:
                held = {u for u in keys if u in MEDIA_VK}
                was = self.cheld.get(key, set())
                self.cheld[key] = held
                for u in sorted(was - held):
                    pc_media(u, True)
                for u in sorted(held - was):
                    pc_media(u, False)

    def _keys(self, group, now):
        down = set()
        for g, keys in self.kheld.values():
            if g == group:
                down |= keys
        was = self.kdown.get(group, set())
        if down == was:
            return
        self.kdown[group] = down
        pc = not self.engine.sends("k", group)
        held = self.kpc.setdefault(group, set())
        for u in sorted(was - down, key=lambda u: (is_mod(u), u)):
            self.engine.use_key(group, key_of(u), True, now)
            if u in held:
                held.discard(u)
                pc_key(u, True)
                if self.rep.get(group, (0,))[0] == u:
                    del self.rep[group]
        for u in sorted(down - was, key=lambda u: (not is_mod(u), u)):
            self.engine.use_key(group, key_of(u), False, now)
            if pc:
                held.add(u)
                pc_key(u, False)
                if not is_mod(u):
                    self.rep[group] = [u, now + self.delay]

    def _buttons(self, group, now, dx, dy, wheel, hwheel):
        down = set()
        for g, btn in self.mheld.values():
            if g == group:
                down |= btn
        was = self.mdown.get(group, set())
        self.mdown[group] = down
        flags = 0
        for b in down - was:
            if b <= 5:
                flags |= 1 << (2 * (b - 1))
        for b in was - down:
            if b <= 5:
                flags |= 2 << (2 * (b - 1))
        more = sum(1 << (b - 1) for b in down if b > 5)
        if wheel:
            flags |= 0x0400
        elif hwheel:
            flags |= 0x0800
        if flags or dx or dy or any(b > 5 for b in down ^ was):
            self.engine.mouse(group, 0, flags, 120 * (wheel or hwheel), dx, dy, now, more=more)
        if not self.engine.sends("m", group):
            held = self.mpc.setdefault(group, set())
            press = sorted(b for b in down - was if b <= 5)
            free = sorted(b for b in was - down if b in held)
            held.update(press)
            held.difference_update(free)
            if dx or dy or wheel or hwheel or press or free:
                pc_mouse(dx, dy, wheel, hwheel, press, free)

    def _for_switch(self):
        for g, held in self.kpc.items():
            if held and self.engine.sends("k", g):
                for u in sorted(held, key=lambda u: (is_mod(u), u)):
                    pc_key(u, True)
                held.clear()
                self.rep.pop(g, None)
        for g, held in self.mpc.items():
            if held and self.engine.sends("m", g):
                pc_mouse(0, 0, 0, 0, [], sorted(held))
                held.clear()

    def _repeat(self, now):
        for g, r in list(self.rep.items()):
            if now < r[1]:
                continue
            if r[0] in self.kpc.get(g, ()) and not self.engine.sends("k", g):
                pc_key(r[0], False)
                r[1] = now + self.period
            else:
                del self.rep[g]


class Taker:
    def __init__(self, engine, raw, usb, emit):
        self.engine = engine
        self.raw = raw
        self.usb = usb
        self.emit = emit
        self.lock = threading.Lock()
        self.busy = False
        self.again = False
        self.keeper = None
        self.declined = False
        self.taken_parts = {}
        self.taken_groups = set()
        self.attempted = set()
        self.refused = set()
        self.kinds = {}
        self.closing = False

    def update(self):
        if not TAKE:
            return
        with self.lock:
            if self.closing:
                return
            if self.busy:
                self.again = True
                return
            self.busy = True
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        try:
            self._sync()
        except Exception as e:
            say("Couldn't take the devices from Windows (%s)" % e)
        finally:
            with self.lock:
                self.busy = False
                again, self.again = self.again, False
            if again:
                self.update()

    def _sync(self):
        if not self.declined:
            self._take_new()
        self._refresh()

    def _parts(self, g):
        here = set(self.raw.parts_of([g]))
        here.update(u for u, p in self.taken_parts.items()
                    if g in p.groups() and dev_state(u) != "not there")
        return here

    def _carries(self, u, g):
        if u not in self.kinds:
            p = self.taken_parts.get(u) or usb_part(u, self.raw.group_for)
            kinds = {(c.group, c.kind) for c in p.cols}
            if u not in self.taken_parts:
                p.free()
            if not any(grp for grp, _ in kinds):
                return False
            self.kinds[u] = kinds
        return (g, g[:1]) in self.kinds[u]

    def _needed(self, g):
        return {u for u in self._parts(g) if self._carries(u, g)}

    def _is_taken(self, g):
        return bool(self._needed(g) & set(self.taken_parts))

    def _listed_groups(self):
        return self.attempted | {g for p in self.taken_parts.values() for g in p.groups()}

    def _refresh(self):
        listed = self._listed_groups()
        self.taken_groups = {g for g in listed if self._is_taken(g)}
        self.engine.set_taken(self.taken_groups)
        self.raw.keep_listed(listed)

    def _take_new(self):
        e = self.engine
        need = [g for g in (e.pick["k"], e.pick["m"]) if g and self._parts(g) and not self._is_taken(g)]
        if not need:
            return
        parts = {}
        for g in need:
            for u in sorted(self._needed(g)):
                if u in self.refused or u in self.taken_parts or u in parts:
                    continue
                p = usb_part(u, self.raw.group_for)
                if p.cols:
                    parts[u] = p
                else:
                    self.refused.add(u)
        if not parts:
            return
        if not self._ensure_keeper():
            for p in parts.values():
                p.free()
            return
        self.attempted.update(need)
        self.raw.keep_listed(self._listed_groups() | {g for p in parts.values() for g in p.groups()})
        res = self._command(take=sorted(parts), give=[], order=self._close_order({**self.taken_parts, **parts}))
        if res is None:
            for p in parts.values():
                p.free()
            self._keeper_lost()
            return
        ok = {r["id"] for r in res.get("took", []) if r.get("ok") and not r.get("reboot")}
        held = sorted(r["id"] for r in res.get("took", []) if r.get("ok") and r.get("reboot"))
        if held:
            self._command(take=[], give=held)
        new = {}
        for u, p in parts.items():
            if u in ok:
                new[u] = p
            else:
                p.free()
                self.refused.add(u)
        if new:
            self.usb.set_parts({**self.taken_parts, **new})
            dead = sorted(set(new) - self.usb.wait_open(set(new), 5.0))
            if dead:
                self._command(take=[], give=dead)
                for u in dead:
                    new.pop(u).free()
                    self.refused.add(u)
                self.usb.set_parts({**self.taken_parts, **new})
            self.taken_parts.update(new)
        got = [g for g in need if self._is_taken(g)]
        missed = [g for g in need if not self._is_taken(g)]
        if got:
            names = " and ".join(self.engine.name(g) for g in got)
            say("Took %s from Windows: while sending, %s to the Switch only"
                % (names, "it goes" if len(got) == 1 else "they go"))
        if missed:
            say("%s stays with Windows: while sending, every keyboard and mouse goes to the Switch"
                % " and ".join(self.engine.name(g) for g in missed))

    def _ensure_keeper(self):
        if self.keeper:
            if kernel32.WaitForSingleObject(self.keeper["proc"], 0) == 0x00000102:
                return True
            self._keeper_lost()
        if self.declined:
            return False
        tag = "%d-%d" % (os.getpid(), int(time.time()))
        prefix = str(Path(tempfile.gettempdir()) / ("xd2joy_keeper_%s" % tag))
        cmd_name, done_name = "Local\\XD2JoyCmd-" + tag, "Local\\XD2JoyDone-" + tag
        cmd_ev = kernel32.CreateEventW(None, False, False, cmd_name)
        done_ev = kernel32.CreateEventW(None, False, False, done_name)
        say("Asking Windows for permission to take the picked devices (once per run)")
        proc, why = run_keeper(["serve", str(os.getpid()), cmd_name, done_name, prefix])
        if not proc:
            kernel32.CloseHandle(cmd_ev)
            kernel32.CloseHandle(done_ev)
            self.declined = (why == "Windows said no")
            say("%s: while sending, every keyboard and mouse goes to the Switch" % why)
            return False
        self.keeper = {"proc": proc, "cmd_ev": cmd_ev, "done_ev": done_ev, "prefix": prefix, "seq": 0}
        return True

    def _command(self, take, give, order=None):
        k = self.keeper
        k["seq"] += 1
        seq = k["seq"]
        cmd = {"seq": seq, "take": take, "give": give}
        if order is not None:
            cmd["order"] = order
        _write_json(k["prefix"] + ".cmd", cmd)
        kernel32.SetEvent(k["cmd_ev"])
        arr = (W.HANDLE * 2)(k["done_ev"], k["proc"])
        if kernel32.WaitForMultipleObjects(2, arr, False, TAKE_WAIT_S * 1000) != 0:
            return None
        try:
            res = json.loads(Path(k["prefix"] + ".res").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return res if res.get("seq") == seq else None

    def _close_order(self, parts=None):
        parts = self.taken_parts if parts is None else parts
        used = [self.engine.recent.get("m"), self.engine.recent.get("k")]

        def rank(u):
            groups = {c.group for c in parts[u].cols if c.group}
            for i, g in enumerate(used):
                if g and g in groups:
                    return i
            if any(g[:1] == "m" for g in groups & self.attempted):
                return 2
            return 3 if any(g[:1] == "m" for g in groups) else 4
        return sorted(parts, key=lambda u: (rank(u), u))

    def close(self, budget=CLOSE_S):
        end = time.perf_counter() + budget
        with self.lock:
            self.closing = True
        while time.perf_counter() < end:
            with self.lock:
                if not self.busy:
                    break
            time.sleep(0.02)
        if not self.keeper or not self.taken_parts:
            return
        order = self._close_order()
        say("Giving the devices back to Windows")
        for i, u in enumerate(order):
            if time.perf_counter() >= end:
                break
            p = self.taken_parts.pop(u)
            self.usb.set_parts(self.taken_parts)
            self.usb.wait_closed({u}, 0.5)
            res = self._command(take=[], give=[u], order=order[i + 1:])
            p.free()
            if res is None:
                break

    def _keeper_lost(self):
        k, self.keeper = self.keeper, None
        if k:
            for h in ("proc", "cmd_ev", "done_ev"):
                kernel32.CloseHandle(k[h])
        self.engine.set_taken(())
        self.usb.set_parts({})
        self.usb.wait_open(set(), 3.0)
        for p in self.taken_parts.values():
            p.free()
        self.taken_parts = {}
        self.taken_groups = set()
        self.attempted = set()
        self.raw.keep_listed(())

    def stranded(self):
        end = time.perf_counter() + 5
        while True:
            ids = sorted({path_instance(p) for p in iface_paths(GUID_TAKE)})
            if not ids or time.perf_counter() > end:
                break
            time.sleep(0.5)
        if not ids:
            return
        say("A device from an earlier run is still taken: giving it back to Windows (Windows asks first)")
        out = Path(tempfile.gettempdir()) / ("xd2joy_back_%d.json" % os.getpid())
        proc, why = run_keeper(["giveback", str(out)] + ids)
        if not proc:
            say("Couldn't give it back (%s). Restart XD2Joy Wired to try again." % why)
            return
        kernel32.WaitForSingleObject(proc, 60000)
        kernel32.CloseHandle(proc)
        try:
            out.unlink()
        except OSError:
            pass


def ticker(engine):
    while True:
        time.sleep(0.002)
        engine.tick(time.perf_counter())


def plain(status, text):
    body = text.encode()
    return Response(status, "OK" if status == 200 else "Error",
                    Headers([("Content-Type", "text/plain; charset=utf-8"),
                             ("Content-Length", str(len(body))), ("Cache-Control", "no-store")]),
                    body)


TYPES = {".html": "text/html; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml",
         ".woff2": "font/woff2", ".json": "application/json", ".txt": "text/plain; charset=utf-8"}


def serve_file(connection, request):
    if request.headers.get("Host", "") not in HOSTS:
        return plain(403, "Forbidden\n")
    path = urllib.parse.urlsplit(request.path).path
    if path == "/ws":
        return None
    rel = PAGE if path == "/" else urllib.parse.unquote(path.lstrip("/"))
    f = (WEB / rel).resolve()
    if WEB not in f.parents or not f.is_file() or ".bak" in f.name:
        return plain(404, "Not found\n")
    body = f.read_bytes()
    kind = TYPES.get(f.suffix.lower()) or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    return Response(200, "OK", Headers([("Content-Type", kind), ("Content-Length", str(len(body))),
                                        ("Cache-Control", "no-store")]), body)


class Helper:
    def __init__(self, loop):
        self.loop = loop
        self.queue = None
        self.ws = None
        self.devices = []
        self.listed = False
        self.engine = Engine(self.emit)
        self.raw = RawInput(self.engine, self.set_devices)
        self.engine.on_hide = self.raw.hide
        self.usb = UsbInput(self.engine)
        self.taker = Taker(self.engine, self.raw, self.usb, self.emit)
        self.usb.on_change = self._usb_changed

    def close(self):
        if getattr(self, "closed", False):
            return
        self.closed = True
        self.engine.set_run(False)
        self.emit({"t": "stopped"})
        self.taker.close()

    def _usb_changed(self):
        self.raw.poke()
        self.taker.update()

    def emit(self, msg):
        self.loop.call_soon_threadsafe(self._put, json.dumps(msg))

    def _put(self, text):
        if self.queue is not None:
            self.queue.put_nowait(text)

    def set_devices(self, devices):
        self.taker.update()
        if devices == self.devices:
            return
        was = device_labels(self.devices)
        self.devices = devices
        self.engine.names = {d["id"]: d["name"] for d in devices}
        if self.listed:
            now = device_labels(devices)
            for key in sorted(set(now) - set(was), key=lambda k: now[k][1].lower()):
                say('%s connected: "%s"' % (now[key][0].capitalize(), now[key][1]))
            for key in sorted(set(was) - set(now), key=lambda k: was[k][1].lower()):
                say('%s disconnected: "%s"' % (was[key][0].capitalize(), was[key][1]))
        self.emit({"t": "devices", "list": devices, "recent": dict(self.engine.recent)})

    def list_devices(self):
        self.listed = True
        labels = sorted(device_labels(self.devices).values(), key=lambda x: (x[0], x[1].lower()))
        say("Keyboards and mice on this PC:" if labels else "No keyboard or mouse found on this PC")
        for kind, name in labels:
            say('  %s "%s"' % (kind.capitalize(), name))

    async def handler(self, ws):
        if self.ws is not None:
            await self.ws.close()
        queue = asyncio.Queue()
        self.ws, self.queue = ws, queue
        say("Web tool connected")
        queue.put_nowait(json.dumps({"t": "devices", "list": self.devices,
                                     "recent": dict(self.engine.recent)}))

        async def pump():
            while True:
                await ws.send(await queue.get())

        sender = asyncio.create_task(pump())
        try:
            async for text in ws:
                try:
                    msg = json.loads(text)
                except ValueError:
                    continue
                kind = msg.get("t")
                if kind == "pick":
                    sides = msg.get("sides")
                    if isinstance(sides, dict):
                        self.engine.set_picks({s: (sides.get(s) or {}) for s in ("L", "R")})
                    else:
                        self.engine.set_pick(msg.get("k") or None, msg.get("m") or None)
                    self.taker.update()
                elif kind == "run":
                    self.engine.set_run(bool(msg.get("on")))
                    self.taker.update()
                elif kind == "detect":
                    want = msg.get("kind") or None
                    self.engine.set_detect(want)
                elif kind == "kbmode":
                    on = bool(msg.get("on"))
                    self.engine.set_kbmode(on)
                elif kind == "stopkey":
                    try:
                        code = int(msg.get("code") or 0) & 0xFF
                        mods = int(msg.get("mods") or 0) & 0xFF
                    except (TypeError, ValueError):
                        continue
                    self.engine.set_stop(code, mods)
        except Exception:
            pass
        finally:
            sender.cancel()
            if self.ws is ws:
                self.ws = self.queue = None
                say("Web tool disconnected")
                self.engine.set_run(False)
                self.engine.set_detect(None)


async def main():
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    helper = Helper(asyncio.get_running_loop())
    helper.raw.start()
    helper.raw.ready.wait()
    if helper.raw.error:
        print("Couldn't read the keyboards and mice: %s" % helper.raw.error)
        return 1
    threading.Thread(target=ticker, args=(helper.engine,), daemon=True).start()
    if TAKE:
        helper.usb.start()
        threading.Thread(target=helper.taker.stranded, daemon=True).start()
    try:
        server = await serve(helper.handler, "127.0.0.1", PORT, origins=ORIGINS,
                             process_request=serve_file, max_size=1 << 16)
    except OSError:
        print("Port %d is busy. Is XD2Joy Wired already running?" % PORT)
        return 1
    def on_console(event):
        if event in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT):
            try:
                helper.close()
            except Exception as e:
                say("Couldn't give the devices back before closing (%s): they go back once it has ended" % e)
        return False
    helper.on_console = CONSOLE_HANDLER(on_console)
    kernel32.SetConsoleCtrlHandler(helper.on_console, True)
    say("XD2Joy Wired is running. Web tool: %s (Ctrl+C quits)" % OPEN_URL)
    helper.list_devices()
    webbrowser.open(OPEN_URL)
    async with server:
        await server.serve_forever()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--keeper":
        sys.exit(keeper_main(sys.argv[2:]))
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
