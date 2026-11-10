#!/usr/bin/env python3
"""给 Meslo Nerd Font 合并中文字形 (来自 Noto Sans Mono CJK SC, SIL OFL 1.1)。

用法:
  add_cjk.py <Meslo.ttf> <等宽中文字体.otf/.ttf> <输出.ttf> [--charset gbk|gb2312] [--scale 1.0 | --fit]

规则:
  * 汉字/全角标点占 2 个单元格 (2 x 1233), 半角字形占 1 个单元格; 水平居中。
  * 字形按 em 比例换算到 Meslo 的 upm, 基线不变; 默认 --scale 1.0 (保持字体自身的字号比例)。
    --fit 则自动缩放, 使全角字形恰好等于 2 个单元格宽 (1.0 em 的字体放大约 1.2 倍; 1.2 em 的字体几乎不变)。
  * 半角/全角按字形宽度相对 em 自动判断 (< 0.8 em 为半角), 同时适用于 0.5/1.0 em 与 0.6/1.2 em 两类字体。
  * 只添加 Meslo 里没有的码位, 不会覆盖原有字形 (含 Nerd Font 图标)。
  * 斜体: 读取 Meslo 的 post.italicAngle, 对汉字做相同角度的倾斜 (CJK 字体本身没有斜体)。
  * CFF 三次曲线用 cu2qu 转为 TrueType 二次曲线。
"""
import sys, math, argparse
from fontTools.ttLib import TTFont
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Transform

EXTRA_RANGES = [
    (0x3000, 0x303F),   # CJK 符号和标点
    (0x3040, 0x30FF),   # 平假名 / 片假名
    (0x3100, 0x312F),   # 注音符号
    (0x31C0, 0x31EF),   # CJK 笔画
    (0x3200, 0x32FF),   # 带圈 CJK 字母和月份
    (0xFF00, 0xFFEF),   # 半角及全角形式
    (0x2E80, 0x2FDF),   # CJK 部首补充 / 康熙部首
]

def codec_chars(codec):
    """某个国标编码能表示的全部 BMP 字符"""
    out = set()
    for hi in range(0x81, 0xFF):
        for lo in range(0x40, 0xFF):
            try:
                s = bytes([hi, lo]).decode(codec)
            except UnicodeDecodeError:
                continue
            if len(s) == 1 and ord(s) <= 0xFFFF:
                out.add(ord(s))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("meslo"); ap.add_argument("cjk"); ap.add_argument("out")
    ap.add_argument("--charset", default="gbk", choices=["gbk", "gb2312"])
    ap.add_argument("--scale", type=float, default=1.0, help="汉字相对 em 的缩放 (默认 1.0)")
    ap.add_argument("--fit", action="store_true", help="自动缩放, 使全角字形宽度恰好等于 2 个单元格")
    a = ap.parse_args()

    base = TTFont(a.meslo)
    cjk = TTFont(a.cjk)
    upm = base["head"].unitsPerEm
    cell = base["hmtx"]["A"][0]                       # 单元格宽 (1233)
    cjk_upm = cjk["head"].unitsPerEm
    cjk_hmtx = cjk["hmtx"]
    cjk_cmap = cjk.getBestCmap()
    if a.fit:                                          # 以 "中" 的宽度为准, 铺满 2 个单元格
        ref = cjk_hmtx[cjk_cmap[0x4E2D]][0] * upm / cjk_upm
        scale = 2 * cell / ref
    else:
        scale = a.scale
    k = upm / cjk_upm * scale                         # 字形缩放倍数
    angle = -base["post"].italicAngle                 # 斜体角度 (Meslo Italic = 11)
    tan = math.tan(math.radians(angle)) if angle else 0.0
    cjk_os2 = cjk["OS/2"]                             # 倾斜以字形框垂直中心为轴, 避免整体横移
    ymid = (cjk_os2.sTypoAscender + cjk_os2.sTypoDescender) / 2 * k
    reverse = "glyf" not in cjk                       # CFF 外轮廓为逆时针, 需反转; TrueType 源已是顺时针
    print(f"  源字体 upm={cjk_upm}, 全角宽={cjk_hmtx[cjk_cmap[0x4E2D]][0]/cjk_upm:.3f} em, 缩放={scale:.3f}")

    base_cmap = base.getBestCmap()
    cjk_gs = cjk.getGlyphSet()

    want = codec_chars(a.charset)
    for lo, hi in EXTRA_RANGES:
        want.update(range(lo, hi + 1))
    want = sorted(c for c in want if c in cjk_cmap and c not in base_cmap)

    glyf, hmtx = base["glyf"], base["hmtx"]
    order = list(base.getGlyphOrder())
    existing = set(order)
    unicode_tables = [t for t in base["cmap"].tables if t.isUnicode()]

    added = 0
    for cp in want:
        src = cjk_cmap[cp]
        adv_src = cjk_hmtx[src][0]
        cells = 1 if adv_src < 0.8 * cjk_upm else 2
        adv = cells * cell
        dx = (adv - adv_src * k) / 2                  # 水平居中
        name = f"uni{cp:04X}"
        if name in existing:
            name += ".cjk"
        # y' = k*y ; x' = k*x + dx + (y' - ymid)*tan   (倾斜只改变 x)
        tr = Transform(k, 0, k * tan, k, dx - ymid * tan, 0)
        pen = TTGlyphPen(None)
        cjk_gs[src].draw(TransformPen(Cu2QuPen(pen, max_err=1.0, reverse_direction=reverse), tr))
        g = pen.glyph()
        order.append(name); existing.add(name)
        glyf.glyphs[name] = g
        g.recalcBounds(glyf)
        hmtx.metrics[name] = (adv, getattr(g, "xMin", 0))
        for t in unicode_tables:
            t.cmap[cp] = name
        added += 1

    base.setGlyphOrder(order)
    glyf.glyphOrder = order

    # OS/2: Unicode 范围 / 代码页 (简体 936, 繁体 950, 日文 932)
    os2 = base["OS/2"]
    os2.recalcUnicodeRanges(base)
    os2.ulCodePageRange1 |= (1 << 17) | (1 << 18) | (1 << 20)

    # 名称表: 追加来源与许可说明 (OFL 要求保留版权/许可声明)
    note_c = " Includes glyphs derived from Noto Sans Mono CJK SC, (c) 2014-2021 Adobe."
    note_l = " CJK glyphs: Noto Sans Mono CJK SC, SIL Open Font License 1.1 (https://openfontlicense.org)."
    nm = base["name"]
    for nid, note in ((0, note_c), (13, note_l)):
        recs = [r for r in nm.names if r.nameID == nid]
        for r in recs:
            if note.strip() not in r.toUnicode():
                r.string = r.toUnicode() + note
        if not recs:                                  # Meslo 原本没有许可字段 (ID 13) 时新建
            for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
                nm.setName(note.strip(), nid, pid, eid, lid)
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):  # 许可 URL (ID 14)
        if not any(r.nameID == 14 for r in nm.names):
            nm.setName("https://openfontlicense.org", 14, pid, eid, lid)

    base.save(a.out)
    print(f"  添加 {added} 个字形 -> {a.out}  (总字形 {len(order)})")
    if len(order) > 65535:
        sys.exit("字形数超过 65535")

if __name__ == "__main__":
    main()
