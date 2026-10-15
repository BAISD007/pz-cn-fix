#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pz-cn-fix - rebuild the Project Zomboid Build 42 Chinese bitmap fonts.

Why: the shipped Chinese interface font is a pre-baked bitmap atlas generated from a
*Traditional* Chinese character set. Simplified-only characters used by the CN text
(显 单 戏 当 键 纹 础 击 创 组 ...) are simply absent, so the game draws nothing for them.

What: re-bakes the same 15 atlases (Small/Medium/Large x top-level + CN/1x..4x) from a
full Simplified font (Noto Sans SC by default), keeping the original lineHeight / base /
advance so the UI layout does not shift, and writes them in the exact same format
(AngelCode BMFont text .fnt + 512x512 palette PNG with a per-index tRNS alpha table).

    python build_cn_fonts.py                    # generate into <game>/_pzcnfix_out
    python build_cn_fonts.py --install          # ... and copy into media/fonts (backs up)
    python build_cn_fonts.py --mod              # ... and build a local mod copy
    python build_cn_fonts.py --restore          # restore the backed-up originals
    python build_cn_fonts.py --only 2x/zomboidMedium   # quick single-font test
    python build_cn_fonts.py --source-font "C:\\Windows\\Fonts\\MiSans-Regular.otf"

No game content is bundled: the original .fnt files are only *read* for layout numbers.
"""
import argparse
import glob
import os
import shutil
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import find_game, zomboid_user_dir, fonts_dir, text_dir, parse_fnt

PAGE, SPACING = 512, 1
REF_SIZE = 40
MOD_NAME = "PZChineseFontPatch"
BACKUP_ROOT = os.path.join(zomboid_user_dir(), "pz-cn-fix", "backup", "fonts")

SOURCE_FONTS = [
    r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf",
    r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf",
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\MiSans-Regular.otf",
    r"C:\Windows\Fonts\msyh.ttc",
]

RANGES = [
    (0x0020, 0x007E),   # ASCII
    (0x00A0, 0x00FF),   # latin-1
    (0x2000, 0x206F),   # general punctuation
    (0x2100, 0x214F),   # letterlike
    (0x2190, 0x21FF),   # arrows
    (0x2200, 0x22FF),   # math
    (0x2460, 0x24FF),   # enclosed alphanumerics
    (0x25A0, 0x25FF),   # geometric shapes
    (0x2600, 0x26FF),   # misc symbols
    (0x3000, 0x303F),   # CJK punctuation
    (0x4E00, 0x9FFF),   # CJK unified ideographs  <-- the actual fix
    (0xFE30, 0xFE4F),   # CJK compatibility forms
    (0xFF00, 0xFFEF),   # fullwidth / halfwidth forms
]


def all_targets():
    t = [("", "zomboidSmallChinese"), ("", "zomboidMediumChinese"), ("", "zomboidLargeChinese")]
    for s in ("1x", "2x", "3x", "4x"):
        for n in ("Small", "Medium", "Large"):
            t.append(("CN/" + s, "zomboid%sChinese" % n))
    return t


def orig_path(fdir, rel, name):
    return os.path.join(fdir, rel, name + ".fnt") if rel else os.path.join(fdir, name + ".fnt")


def page_pad(pages):
    import re
    m = re.search(r'file="(.*?)(\d+)\.png"', pages[0])
    return 1 if len(m.group(2)) == 1 else 2


def pick_source(explicit):
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit("source font not found: " + explicit)
        return explicit
    for p in SOURCE_FONTS:
        if os.path.isfile(p):
            return p
    hits = glob.glob(r"C:\Windows\Fonts\*Noto*SC*.otf") + glob.glob(r"C:\Windows\Fonts\*Noto*SC*.ttf")
    if hits:
        return hits[0]
    sys.exit("no CJK source font found. Install Noto Sans SC, or pass --source-font <path to .otf/.ttf>")


def ink_bytes(font, ch):
    x0, y0, x1, y1 = font.getbbox(ch)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return (0, 0, 0, 0), b""
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((-x0, -y0), ch, font=font, fill=255)
    return (w, h), im.tobytes()


def build_charset(fdir, trans, log):
    """Everything the original font had + the full CJK basic block + our text needs."""
    info, common, pages, chars = parse_fnt(orig_path(fdir, "CN/1x", "zomboidSmallChinese"))
    cps = set()
    for a, b in RANGES:
        cps |= set(range(a, b + 1))
    cps |= set(chars.keys())
    for lang in ("CN", "CH"):
        for p in glob.glob(os.path.join(trans, lang, "*.txt")):
            for ch in open(p, encoding="utf-8-sig", errors="replace").read():
                o = ord(ch)
                if 0x2000 <= o <= 0xFFEF or 0x4E00 <= o <= 0x9FFF:
                    cps.add(o)
    log("charset candidates: %d (original font had %d)" % (len(cps), len(chars)))
    return sorted(cps)


def render_target(src, fdir, out_dir, rel, name, keep, log):
    info, common, pages, chars = parse_fnt(orig_path(fdir, rel, name))
    line_h, base = int(common["lineHeight"]), int(common["base"])
    pad = page_pad(pages)

    target_adv = int(chars[0x4E2D]["xadvance"])
    size = target_adv
    for trial in (target_adv, target_adv - 1, target_adv + 1, target_adv - 2, target_adv + 2):
        f = ImageFont.truetype(src, trial)
        if round(f.getlength(chr(0x4E2D))) == target_adv:
            size = trial
            break
    font = ImageFont.truetype(src, size)
    ascent, descent = font.getmetrics()
    yshift = base - ascent

    metrics = {}
    for cp in keep:
        ch = chr(cp)
        x0, y0, x1, y1 = font.getbbox(ch)
        w, h = max(x1 - x0, 0), max(y1 - y0, 0)
        xa = round(font.getlength(ch))
        if w <= 0 or h <= 0:
            metrics[cp] = (0, 0, 1, 1, base, xa)
        else:
            metrics[cp] = (x0, y0, w, h, y0 + yshift, xa)

    order = sorted(keep, key=lambda c: (-metrics[c][3], -metrics[c][2], c))
    placed, rendered = {}, []
    cur = Image.new("L", (PAGE, PAGE), 0)
    draw = ImageDraw.Draw(cur)
    x = y = rowh = 0
    for cp in order:
        m = metrics[cp]
        w, h = m[2], m[3]
        cw, chh = w + SPACING, h + SPACING
        if x + cw > PAGE:
            x, y, rowh = 0, y + rowh, 0
        if y + chh > PAGE:
            rendered.append(cur)
            cur = Image.new("L", (PAGE, PAGE), 0)
            draw = ImageDraw.Draw(cur)
            x = y = rowh = 0
        placed[cp] = (x, y, len(rendered))
        draw.text((x - m[0], y - m[1]), chr(cp), font=font, fill=255)
        x += cw
        rowh = max(rowh, chh)
    rendered.append(cur)

    d = os.path.join(out_dir, rel) if rel else out_dir
    os.makedirs(d, exist_ok=True)
    for i, pg in enumerate(rendered):                    # palette PNG + tRNS, like vanilla
        pc = pg.copy()
        pc.putpalette([255, 255, 255] * 256)
        pc.info["transparency"] = bytes(range(256))
        pc.save(os.path.join(d, "%s_%0*d.png" % (name, pad, i)), format="PNG", compress_level=9)

    lines = [info,
             "common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=%d packed=0 "
             "alphaChnl=0 redChnl=4 greenChnl=4 blueChnl=4" % (line_h, base, PAGE, PAGE, len(rendered))]
    for i in range(len(rendered)):
        lines.append('page id=%d file="%s_%0*d.png"' % (i, name, pad, i))
    lines.append("chars count=%d" % len(keep))
    for cp in sorted(keep):
        x0, y0, w, h, yog, xa = metrics[cp]
        px, py, pp = placed[cp]
        lines.append("char id=%d x=%-4d y=%-4d width=%-4d height=%-4d xoffset=%-4d "
                     "yoffset=%-4d xadvance=%-4d page=%-2d chnl=15" % (cp, px, py, w, h, x0, yog, xa, pp))
    with open(os.path.join(d, name + ".fnt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return dict(rel=rel, name=name, chars=len(keep), pages=len(rendered), size=size,
                lineHeight=line_h, base=base)


def backup_originals(fdir, targets, log):
    n = 0
    for rel, name in targets:
        src = orig_path(fdir, rel, name)
        if not os.path.isfile(src):
            continue
        d = os.path.join(BACKUP_ROOT, rel) if rel else BACKUP_ROOT
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, name + ".fnt")
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            n += 1
        for ln in parse_fnt(src)[2]:
            fn = ln.split('file="')[1].rstrip('"')
            s = os.path.join(os.path.dirname(src), fn)
            t = os.path.join(d, fn)
            if os.path.isfile(s) and not os.path.exists(t):
                shutil.copy2(s, t)
                n += 1
    log("backed up %d original files -> %s" % (n, BACKUP_ROOT))


def file_list(d, name):
    return [f for f in os.listdir(d) if f.startswith(name + ".") or f.startswith(name + "_")]


def install(out_dir, fdir, targets, log):
    n = 0
    for rel, name in targets:
        srcd = os.path.join(out_dir, rel) if rel else out_dir
        dstd = os.path.join(fdir, rel) if rel else fdir
        os.makedirs(dstd, exist_ok=True)
        for fn in file_list(srcd, name):
            shutil.copy2(os.path.join(srcd, fn), os.path.join(dstd, fn))
            n += 1
    log("installed %d files into media/fonts" % n)


def build_mod(out_dir, targets, log):
    mod_dir = os.path.join(zomboid_user_dir(), "mods", MOD_NAME)
    for rel, name in targets:
        srcd = os.path.join(out_dir, rel) if rel else out_dir
        dstd = os.path.join(mod_dir, "media", "fonts", rel) if rel else os.path.join(mod_dir, "media", "fonts")
        os.makedirs(dstd, exist_ok=True)
        for fn in file_list(srcd, name):
            shutil.copy2(os.path.join(srcd, fn), os.path.join(dstd, fn))
    with open(os.path.join(mod_dir, "mod.info"), "w", encoding="utf-8", newline="\n") as f:
        f.write("name=Chinese Font Patch (Simplified Cyrillic-free atlas rebuild)\n"
                "id=%s\n"
                "modversion=1.1.0\n"
                "description=Rebuilt Chinese bitmap font for Build 42 - restores the simplified "
                "characters missing from the vanilla atlas. Client-side, text/UI only.\n" % MOD_NAME)
    log("mod -> " + mod_dir)


def restore(fdir, log):
    n = 0
    for root, _, files in os.walk(BACKUP_ROOT):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(root, BACKUP_ROOT)
            d = fdir if rel == "." else os.path.join(fdir, rel)
            os.makedirs(d, exist_ok=True)
            shutil.copy2(src, os.path.join(d, fn))
            n += 1
    log("restored %d original font files into media/fonts" % n)


def main():
    ap = argparse.ArgumentParser(description="Rebuild the Project Zomboid Build 42 Chinese bitmap fonts")
    ap.add_argument("--game")
    ap.add_argument("--out", help="output directory (default <game>/_pzcnfix_out)")
    ap.add_argument("--source-font", help="path to a .otf/.ttf with full Simplified coverage")
    ap.add_argument("--install", action="store_true", help="copy the result into media/fonts (backs up first)")
    ap.add_argument("--mod", action="store_true", help="also build a local mod copy")
    ap.add_argument("--restore", action="store_true", help="restore the backed-up originals")
    ap.add_argument("--only", help="substring filter, e.g. '2x/zomboidMedium' (quick test)")
    args = ap.parse_args()

    t0 = time.time()
    def log(*a):
        print("[%5.1fs]" % (time.time() - t0), *a, flush=True)

    game = find_game(args.game)
    if not game:
        sys.exit("Project Zomboid not found. Pass --game <install dir> or set PZ_GAME.")
    fdir, trans = fonts_dir(game), text_dir(game)
    log("game :", game)
    log("fonts:", fdir)

    if args.restore:
        restore(fdir, log)
        return 0

    src = pick_source(args.source_font)
    log("source font:", src)

    targets = all_targets()
    if args.only:
        targets = [t for t in targets if args.only.lower() in ("%s/%s" % t).lower()]
        if not targets:
            sys.exit("--only matched nothing")

    ref = ImageFont.truetype(src, REF_SIZE)
    notdef = ink_bytes(ref, "\uE000")
    cps = build_charset(fdir, trans, log)
    keep, dropped = [], 0
    for cp in cps:
        if cp in (0x20, 0xA0, 0x3000):
            keep.append(cp)
            continue
        if ink_bytes(ref, chr(cp)) != notdef:
            keep.append(cp)
        else:
            dropped += 1
    log("rendering %d glyphs per atlas (%d codepoints unsupported by the source font)" % (len(keep), dropped))

    out_dir = args.out or os.path.join(game, "_pzcnfix_out")
    for rel, name in targets:
        r = render_target(src, fdir, out_dir, rel, name, keep, log)
        log("  %-6s %-24s em=%2d  lineHeight=%2d base=%2d  chars=%d pages=%d"
            % (rel or "top", name, r["size"], r["lineHeight"], r["base"], r["chars"], r["pages"]))
    log("output:", out_dir)

    if args.install:
        backup_originals(fdir, targets, log)
        install(out_dir, fdir, targets, log)
        log("restart the game - atlases are loaded at startup")
    if args.mod:
        build_mod(out_dir, targets, log)
    if not (args.install or args.mod):
        log("nothing installed. re-run with --install (in place) and/or --mod")
    return 0


if __name__ == "__main__":
    sys.exit(main())
