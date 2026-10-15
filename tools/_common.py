# -*- coding: utf-8 -*-
"""Shared helpers: locate a Project Zomboid install, parse .fnt files."""
import glob
import os
import re
import string
import sys

ENTRY = re.compile(r'^\s*([^=\s][^=]*?)\s*=\s*"(.*)"\s*,?\s*$')
KEY = re.compile(r'^\s*([^=\s][^=]*?)\s*=')

EXE = "ProjectZomboid64.exe"


def zomboid_user_dir():
    """%USERPROFILE%\\Zomboid  (mods, saves, options.ini live here)"""
    return os.path.join(os.path.expanduser("~"), "Zomboid")


def _cache_file():
    return os.path.join(zomboid_user_dir(), "pz-cn-fix", "game.txt")


def _ok(path):
    return bool(path) and os.path.isfile(os.path.join(path, EXE))


def remember_game(path):
    try:
        p = _cache_file()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(os.path.abspath(path))
    except OSError:
        pass


def _cached():
    try:
        with open(_cache_file(), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _steam_libraries():
    """Steam install dirs from the registry + libraryfolders.vdf."""
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            roots.append(winreg.QueryValueEx(k, name)[0])
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    for env in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"):
        base = os.environ.get(env)
        if base:
            roots.append(os.path.join(base, "Steam"))

    libs = []
    for r in roots:
        libs.append(r)
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            txt = open(vdf, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                libs.append(m.group(1).replace("\\\\", "\\"))
    return libs


def _from_logs():
    """The game logs absolute paths under its own media/ folder - read them back."""
    zdir = zomboid_user_dir()
    files = [os.path.join(zdir, "console.txt")]
    logd = os.path.join(zdir, "Logs")
    if os.path.isdir(logd):
        found = []
        for root, _, fs in os.walk(logd):
            for f in fs:
                if f.endswith(".txt"):
                    p = os.path.join(root, f)
                    try:
                        found.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
        found.sort(reverse=True)
        files += [p for _, p in found[:8]]
    pat = re.compile(r'([A-Za-z]:[\\/][^\r\n"\'<>|]*?)[\\/]media[\\/]')
    for p in files:
        try:
            txt = open(p, encoding="utf-8", errors="replace").read(600000)
        except OSError:
            continue
        for m in pat.finditer(txt):
            cand = m.group(1).replace("/", "\\")
            if _ok(cand):
                return cand
    return None


def _scan_drives(max_depth=4, cap_per_drive=40000):
    """Bounded breadth-first search for ProjectZomboid64.exe (non-Steam installs)."""
    skip = {"windows", "$recycle.bin", "system volume information", "programdata",
            "appdata", "perflogs", "$windows.~bt", "$windows.~ws", "node_modules",
            ".git", ".cache", "temp", "tmp", "recovery", "msocache", "intel"}
    for letter in string.ascii_uppercase:
        root = letter + ":\\"
        if not os.path.isdir(root):
            continue
        if _ok(root):
            return root
        visited = 0
        level = [root]
        for _ in range(max_depth):
            if not level:
                break
            nxt, over = [], False
            for base in level:
                if over:
                    break
                try:
                    entries = list(os.scandir(base))
                except OSError:
                    continue
                for e in entries:
                    visited += 1
                    if visited > cap_per_drive:      # give up on this drive only
                        over = True
                        break
                    try:
                        if not e.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if e.name.lower() in skip or e.name.startswith("."):
                        continue
                    if _ok(e.path):
                        return e.path
                    nxt.append(e.path)
            level = nxt
    return None


def find_game(explicit=None, scan=True, quiet=False):
    """Return the Project Zomboid install dir, or None. Caches a successful hit."""
    def note(*a):
        if not quiet:
            print(*a, file=sys.stderr)

    if explicit:
        if _ok(explicit):
            remember_game(explicit)
            return os.path.abspath(explicit)
        sys.exit("not a Project Zomboid install (no %s): %s" % (EXE, explicit))

    if os.environ.get("PZ_GAME") and _ok(os.environ["PZ_GAME"]):
        return os.path.abspath(os.environ["PZ_GAME"])

    c = _cached()
    if _ok(c):
        return os.path.abspath(c)

    cands = [os.path.join(lib, "steamapps", "common", "ProjectZomboid") for lib in _steam_libraries()]
    for d in string.ascii_uppercase:
        cands += [f"{d}:\\ProjectZomboid", f"{d}:\\Games\\ProjectZomboid",
                  f"{d}:\\Steam\\steamapps\\common\\ProjectZomboid",
                  f"{d}:\\SteamLibrary\\steamapps\\common\\ProjectZomboid"]
    seen = set()
    for c in cands:
        c = os.path.abspath(c)
        if c in seen:
            continue
        seen.add(c)
        if _ok(c):
            remember_game(c)
            return c

    if scan:
        note("Looking for Project Zomboid in the game's own logs...")
        hit = _from_logs()
        if hit:
            note("found in logs:", hit)
            remember_game(hit)
            return os.path.abspath(hit)
        note("Not in the logs - scanning drives (this can take a few seconds)...")
        hit = _scan_drives()
        if hit:
            note("found on disk:", hit)
            remember_game(hit)
            return os.path.abspath(hit)
    return None


def text_dir(game):
    return os.path.join(game, "media", "lua", "shared", "Translate")


def fonts_dir(game):
    return os.path.join(game, "media", "fonts")


def parse_fnt(path):
    """-> (info_line, common_dict, page_lines, {codepoint: field_dict})"""
    info, common, pages, chars = "", {}, [], {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s.startswith("info "):
                info = s
            elif s.startswith("common "):
                for kv in s.split()[1:]:
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        common[k] = v
            elif s.startswith("page "):
                pages.append(s)
            elif s.startswith("char "):
                d = {}
                for kv in s.split()[1:]:
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        d[k] = v
                if "id" in d:
                    chars[int(d["id"])] = d
    return info, common, pages, chars


def load_translation_keys(path):
    s = set()
    try:
        for ln in open(path, encoding="utf-8-sig", errors="replace"):
            m = KEY.match(ln)
            if m and not m.group(1).startswith("--"):
                s.add(m.group(1))
    except OSError:
        pass
    return s


def load_entries(path):
    d = {}
    for ln in open(path, encoding="utf-8-sig", errors="replace"):
        m = ENTRY.match(ln.rstrip("\r\n"))
        if m:
            d.setdefault(m.group(1), m.group(2))
    return d


def all_language_entries(trans_dir, lang):
    d = {}
    for p in glob.glob(os.path.join(trans_dir, lang, "*.txt")):
        d.update(load_entries(p))
    return d
