#!/usr/bin/env bash
# 重新生成 "旧版图标尺寸" 的 Meslo Nerd Font, 并可选合并中文字形
#
# 用法:  ./build.sh [M|S|L] [输出目录]        默认: M  ./dist
#   M -> MesloLGM NF (中等行高)   S -> MesloLGS NF (小行高)   L -> MesloLGL NF (大行高)
#
# 可选环境变量:
#   FAMILY="家族名"            默认 "MesloLG<变体> NF"
#   CJK=1|0                    是否同时生成含中文的版本 (默认 1, 输出到 <输出目录>/sc)
#   CJK_FAMILY="家族名"        中文版家族名, 默认 "<FAMILY> SC"
#   CJK_CHARSET=gbk|gb2312     汉字范围, 默认 gbk (约 2.1 万字, 每个样式约 11 MB); gb2312 约 5.5 MB
#
# 依赖: git, patch, curl, python3, fontforge + python3-fontforge, fonttools
#   Debian/Ubuntu: sudo apt install git patch curl fontforge python3-fontforge && pip install fonttools
set -euo pipefail

VARIANT="${1:-M}"
case "$VARIANT" in M|S|L) ;; *) echo "变体必须是 M、S 或 L"; exit 1 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(mkdir -p "${2:-$HERE/dist}" && cd "${2:-$HERE/dist}" && pwd)"
FAMILY="${FAMILY:-MesloLG${VARIANT} NF}"
CJK="${CJK:-1}"
CJK_FAMILY="${CJK_FAMILY:-$FAMILY SC}"
CJK_CHARSET="${CJK_CHARSET:-gbk}"
NF_TAG="v3.5.1"                       # Nerd Fonts 固定版本, 保证补丁可复现
NOTO_TAG="Sans2.004"                  # Noto CJK 固定版本
WORK="$HERE/.work"

# ---- 依赖检查 ----
for c in git patch python3; do command -v "$c" >/dev/null || { echo "缺少命令: $c"; exit 1; }; done
[ "$CJK" = 1 ] && { command -v curl >/dev/null || { echo "缺少命令: curl"; exit 1; }; }
python3 -c "import fontforge" 2>/dev/null || { echo "python3 找不到 fontforge 模块 (apt install fontforge python3-fontforge)"; exit 1; }
python3 -c "import fontTools" 2>/dev/null || { echo "缺少 fonttools (pip install fonttools)"; exit 1; }

# ---- 1. 稀疏克隆官方仓库 (只拉必需文件) ----
mkdir -p "$WORK"
if [ ! -d "$WORK/nerd-fonts" ]; then
  git clone --depth 1 --branch "$NF_TAG" --filter=blob:none --sparse \
      https://github.com/ryanoasis/nerd-fonts.git "$WORK/nerd-fonts"
fi
cd "$WORK/nerd-fonts"
git sparse-checkout set --no-cone /font-patcher /src/glyphs "/src/unpatched-fonts/Meslo/$VARIANT" /bin/scripts

# ---- 2. 应用补丁 (每次先还原, 保证幂等) ----
git checkout -- font-patcher
patch -p1 < "$HERE/patch/legacy-icon-size.patch"

# ---- 3. 生成四个样式 ----
RAW="$WORK/raw-$VARIANT"; rm -rf "$RAW"; mkdir -p "$RAW"
for s in Regular Bold Italic "Bold Italic"; do
  python3 font-patcher "src/unpatched-fonts/Meslo/$VARIANT/Meslo LG $VARIANT $s for Powerline.ttf" \
      --complete --no-progressbars -q --outputdir "$RAW"
done

# ---- 4. 改名并输出 (无中文版) ----
python3 "$HERE/rename_fonts.py" "$RAW" "$OUT" "$FAMILY"

# ---- 5. 合并中文 (可选) ----
if [ "$CJK" = 1 ]; then
  declare -A SHA=(
    [Regular]=ec04cc376b34887cedbdf84074e2e226ed2761eeabdcb9173fc1dd7bfd153ef7
    [Bold]=a452fedfc0619e43e080b7b861ce34cbd3ec4fbcea495bf8c402a5a02a5dcbdc )
  mkdir -p "$WORK/noto"
  for w in Regular Bold; do
    f="$WORK/noto/NotoSansMonoCJKsc-$w.otf"
    if [ ! -f "$f" ]; then
      curl -fSL -o "$f" "https://raw.githubusercontent.com/notofonts/noto-cjk/$NOTO_TAG/Sans/Mono/NotoSansMonoCJKsc-$w.otf"
    fi
    echo "${SHA[$w]}  $f" | sha256sum -c --quiet - || { echo "Noto $w 校验失败, 请删除 $f 后重试"; exit 1; }
  done

  TMP="$WORK/named-$VARIANT"; rm -rf "$TMP"
  python3 "$HERE/rename_fonts.py" "$RAW" "$TMP" "$CJK_FAMILY" >/dev/null
  mkdir -p "$OUT/sc"
  for f in "$TMP"/*.ttf; do
    case "$f" in *Bold*) w=Bold ;; *) w=Regular ;; esac     # 斜体沿用直体汉字, 由脚本按字体的斜体角度倾斜
    python3 "$HERE/add_cjk.py" "$f" "$WORK/noto/NotoSansMonoCJKsc-$w.otf" "$OUT/sc/$(basename "$f")" --charset "$CJK_CHARSET"
  done
  echo "中文版: $OUT/sc  (家族名: $CJK_FAMILY, 字符集: $CJK_CHARSET)"
fi
echo "完成: $OUT  (家族名: $FAMILY)"
