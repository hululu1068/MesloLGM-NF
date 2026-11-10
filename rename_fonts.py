#!/usr/bin/env python3
"""把 font-patcher 的输出 (MesloLGxNerdFont-*.ttf) 改名为 "MesloLGx NF" 命名风格。

用法: rename_fonts.py <输入目录> <输出目录> <家族名, 如 "MesloLGM NF">
"""
import sys, glob, os
from fontTools.ttLib import TTFont

STYLES = {"Regular": "Regular", "Bold": "Bold", "Italic": "Italic", "BoldItalic": "Bold Italic"}

def main(src, dst, family):
    os.makedirs(dst, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, "*NerdFont-*.ttf")))
    if not files:
        sys.exit(f"在 {src} 里没有找到 *NerdFont-*.ttf")
    ps_family = family.replace(" ", "-")            # MesloLGM-NF
    file_family = family.replace(" ", "_")          # MesloLGM_NF
    for f in files:
        key = os.path.basename(f).rsplit("-", 1)[1][:-4]   # Regular / Bold / Italic / BoldItalic
        style = STYLES[key]
        t = TTFont(f)
        # 上游 Meslo 的 post.isFixedPitch 是 0, 系统会把它当比例字体, 等宽字体列表里看不到;
        # panose.bProportion 已经是 9 (等宽), 这里补上声明。
        t["post"].isFixedPitch = 1
        n = t["name"]
        for nid in (16, 17, 21, 22):                         # 去掉扩展家族名, 按 RIBBI 四种样式归组
            n.removeNames(nameID=nid)
        for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
            n.setName(family, 1, pid, eid, lid)
            n.setName(style, 2, pid, eid, lid)
            n.setName(f"{family} {style};Nerd Fonts 3.5.1", 3, pid, eid, lid)
            n.setName(f"{family} {style}", 4, pid, eid, lid)
            n.setName(f"{ps_family}-{style.replace(' ', '-')}", 6, pid, eid, lid)
        out = os.path.join(dst, f"{file_family}_{style.replace(' ', '_')}.ttf")
        t.save(out)
        print("  ->", out)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
