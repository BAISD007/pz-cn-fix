#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pz-cn-fix - apply the Simplified-Chinese text patch to a Project Zomboid Build 42 install.

The script only ever touches the translation tables of the copy on *your* machine:
it appends our own translated entries (data/*.tsv) to

    media/lua/shared/Translate/CN/UI_CN.txt
    media/lua/shared/Translate/CN/IG_UI_CN.txt

Originals are backed up first. No game content is bundled with this project.

    python apply_cn_patch.py                 # patch in place (recommended)
    python apply_cn_patch.py --mod           # also build a local mod copy
    python apply_cn_patch.py --verify        # only report coverage
    python apply_cn_patch.py --restore       # undo, from the backup
    python apply_cn_patch.py --game "D:\\...\\ProjectZomboid"
"""
import argparse
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (find_game, zomboid_user_dir, text_dir, KEY, load_entries)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

MOD_NAME = "PZChinesePatch"
TARGETS = {"UI": "UI_CN.txt", "IGUI": "IG_UI_CN.txt"}
BACKUP_ROOT = os.path.join(zomboid_user_dir(), "pz-cn-fix", "backup")


def route(key):
    if key.startswith("UI_"):
        return "UI"
    if key.startswith("IGUI_"):
        return "IGUI"
    return None


def read_keys(path):
    s = set()
    for ln in open(path, encoding="utf-8-sig", errors="replace"):
        m = KEY.match(ln)
        if m and not m.group(1).startswith("--"):
            s.add(m.group(1))
    return s


def patch_file(path, entries, backup_root, dry=False):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    nl = "\r\n" if b"\r\n" in raw[:4000] else "\n"
    lines = raw.decode("utf-8-sig").split("\n")

    have = read_keys(path)
    todo = {k: v for k, v in entries.items() if k not in have}
    if not todo:
        return 0
    if not dry:
        os.makedirs(backup_root, exist_ok=True)
        bak = os.path.join(backup_root, os.path.basename(path))
        if not os.path.exists(bak):
            shutil.copy2(path, bak)

    last = max(i for i, l in enumerate(lines) if l.strip() == "}")
    block = ["    -- ==== pz-cn-fix: Build 42 additions (community translation) ===="]
    for k in sorted(todo):
        block.append('    %s = "%s",' % (k, todo[k].replace('"', '\\"')))
    lines[last:last] = block

    if not dry:
        with open(path, "wb") as f:
            if bom:
                f.write(b"\xef\xbb\xbf")
            f.write(nl.join(lines).encode("utf-8"))
    return len(todo)


def build_mod(game, trans):
    mod_dir = os.path.join(zomboid_user_dir(), "mods", MOD_NAME)
    dst = os.path.join(mod_dir, "media", "lua", "shared", "Translate", "CN")
    os.makedirs(dst, exist_ok=True)
    for fn in ("UI_CN.txt", "IG_UI_CN.txt"):
        src = os.path.join(trans, "CN", fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst, fn))
    with open(os.path.join(mod_dir, "mod.info"), "w", encoding="utf-8", newline="\n") as f:
        f.write("name=Chinese Localization Patch (Simplified)\n"
                "id=%s\n"
                "modversion=1.1.0\n"
                "description=Community Simplified-Chinese text completion for Build 42. "
                "Adds UI/IGUI entries the shipped 41.78 translation never covered. "
                "Text only - safe to add or remove at any time.\n" % MOD_NAME)
    return mod_dir


def main():
    ap = argparse.ArgumentParser(description="Project Zomboid Build 42 Simplified-Chinese text patch")
    ap.add_argument("--game", help="Project Zomboid install directory")
    ap.add_argument("--mod", action="store_true", help="also build a local mod copy")
    ap.add_argument("--restore", action="store_true", help="restore the backed-up originals")
    ap.add_argument("--verify", action="store_true", help="only report coverage")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    game = find_game(args.game)
    if not game:
        print("ERROR: Project Zomboid not found. Pass it explicitly:\n"
              '  python apply_cn_patch.py --game "D:\\Steam\\steamapps\\common\\ProjectZomboid"\n'
              "or set the PZ_GAME environment variable.", file=sys.stderr)
        return 2
    trans = text_dir(game)
    print("game :", game)
    print("texts:", trans)

    if args.restore:
        n = 0
        for fn in TARGETS.values():
            src = os.path.join(BACKUP_ROOT, fn)
            dst = os.path.join(trans, "CN", fn)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                n += 1
                print("  restored", fn)
        print("restored %d file(s). If a Steam update overwrote them, use 'Verify integrity' instead." % n)
        return 0

    # ---- load our data, routed per target file
    per_target = {k: {} for k in TARGETS}
    for p in sorted(glob.glob(os.path.join(DATA, "*.tsv"))):
        for ln in open(p, encoding="utf-8"):
            ln = ln.rstrip("\r\n")
            if not ln or ln.startswith("#") or "\t" not in ln:
                continue
            k, v = ln.split("\t", 1)
            t = route(k)
            if t:
                per_target[t][k] = v

    en = {}
    for p in glob.glob(os.path.join(trans, "EN", "*.txt")):
        en.update(load_entries(p))

    # ---- verify mode
    if args.verify:
        for t, fn in TARGETS.items():
            path = os.path.join(trans, "CN", fn)
            have = read_keys(path)
            want = {k: v for k, v in per_target[t].items() if k in en}
            miss = [k for k in want if k not in have]
            print(f"  {fn:<14} our entries {len(want):>4}  applied {len(want)-len(miss):>4}  missing {len(miss)}")
        return 0

    # ---- patch
    total = bad = 0
    for t, fn in TARGETS.items():
        path = os.path.join(trans, "CN", fn)
        if not os.path.isfile(path):
            print("  !! not found:", path, file=sys.stderr)
            bad += 1
            continue
        entries = {k: v for k, v in per_target[t].items() if k in en}
        unknown = [k for k in per_target[t] if k not in en]
        n = patch_file(path, entries, BACKUP_ROOT, args.dry_run)
        have = read_keys(path)
        miss = [k for k in entries if k not in have]
        print(f"  {fn:<14} added {n:>4}   total our entries in file {len(entries)-len(miss)}/{len(entries)}"
              + (f"   (skipped {len(unknown)} unknown keys)" if unknown else ""))
        total += n
    print(f"added {total} entries total. Backups: {BACKUP_ROOT}")

    if args.mod:
        print("mod  :", build_mod(game, trans))
        print("       enable it in the in-game MODS screen (or for a save: Load Game -> Choose Mods)")
    else:
        print("restart the game - the tables are read at startup (no mod needs enabling)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
