"""Overlay key-press badges onto the base recording from `vhs demo/demo.tape`.

hop's shortcuts (n, Enter, q, arrows, c) produce no on-screen echo, so a silent
GIF hides *which* key drove each change. VHS has no keycast, so we bake the
badges in afterwards with ffmpeg's drawtext/drawbox filters.

Each badge is a translucent HUD pill holding a light "keycap" for the key, an
arrow, and the action it triggers: [ n ] -> new branch. Layout is done in pixels
by character width, which is exact because the font is monospaced.

The badge windows below are measured against the tape's deterministic Sleep
budget (see demo/PLAYBOOK.md). If you change a Sleep in demo.tape, re-measure by
building a timestamped contact sheet of the base GIF, e.g.:

    ffmpeg -i demo/demo.gif -vf "fps=2,drawtext=text='%{pts\\:hms}':x=6:y=6:\
fontcolor=yellow:box=1,scale=360:-1,tile=6x10" sheet.png

Run from the repo root, after vhs:  uv run python demo/keycaps.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

GIF = Path("demo/demo.gif")

# (key, action, start_s, end_s) — one badge per hop key press, in storyline order.
BADGES: list[tuple[str, str, float, float]] = [
    ("n", "new branch", 3.2, 4.6),
    ("Enter", "create", 6.7, 8.2),
    ("q", "quit", 9.1, 10.3),
    ("↓", "move down", 24.1, 25.4),
    ("c", "checkout", 25.7, 27.2),
    ("q", "quit", 27.6, 28.9),
]

# --- keycap HUD look (tokyo-night-ish palette) ---
F = 30  # font size, px
CW = F * 0.602  # DejaVu Sans Mono advance width per glyph
SEP = "→"
SEP_DY = round(F * 0.16)  # the arrow's glyph centre sits high; nudge it down onto the text
KP, KVP = 14, 8  # keycap inner padding (x, y)
GAP = 16  # gap between keycap / arrow / action
BPX, BPY = 22, 12  # pill inner padding (x, y)
KEYCAP_H = F + 2 * KVP
BAR_H = KEYCAP_H + 2 * BPY
BOTTOM_MARGIN = 64

BAR_BG = "0x1a1b26@0.85"
ACCENT = "0x7aa2f7"  # pill border + arrow
KEYCAP_BG = "0xe8e8ec"
KEYCAP_EDGE = "0x11121a"
ACTION_FG = "0xc0caf5"

_FONT_DIRS = [
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/TTF"),
    Path("/Library/Fonts"),
]


def _fonts() -> tuple[str, str]:
    for d in _FONT_DIRS:
        regular, bold = d / "DejaVuSansMono.ttf", d / "DejaVuSansMono-Bold.ttf"
        if regular.exists() and bold.exists():
            return str(regular), str(bold)
    raise SystemExit("DejaVu Sans Mono not found; edit _FONT_DIRS in keycaps.py")


def _badge(regular: str, bold: str, key: str, action: str, s: float, e: float) -> list[str]:
    keycap_w = len(key) * CW + 2 * KP
    sep_w = len(SEP) * CW
    action_w = len(action) * CW
    bar_w = round(keycap_w + GAP + sep_w + GAP + action_w + 2 * BPX, 1)

    # x anchors: drawbox uses iw, drawtext uses w — same frame width, so aligned.
    bar_l_box = f"(iw-{bar_w})/2"
    bar_l_txt = f"(w-{bar_w})/2"
    keycap_l = round(BPX, 1)
    key_l = round(BPX + KP, 1)
    sep_l = round(BPX + keycap_w + GAP, 1)
    action_l = round(BPX + keycap_w + GAP + sep_w + GAP, 1)

    # y anchors, measured up from the frame bottom.
    bar_t_box = f"ih-{BAR_H}-{BOTTOM_MARGIN}"
    keycap_t = f"ih-{BAR_H}-{BOTTOM_MARGIN}+{(BAR_H - KEYCAP_H) // 2}"
    text_y = f"h-{BAR_H}-{BOTTOM_MARGIN}+{(BAR_H - F) // 2}"
    sep_y = f"h-{BAR_H}-{BOTTOM_MARGIN}+{(BAR_H - F) // 2 + SEP_DY}"
    en = f"enable='between(t,{s},{e})'"

    return [
        f"drawbox=x={bar_l_box}:y={bar_t_box}:w={bar_w}:h={BAR_H}:color={BAR_BG}:t=fill:{en}",
        f"drawbox=x={bar_l_box}:y={bar_t_box}:w={bar_w}:h={BAR_H}:color={ACCENT}@0.95:t=2:{en}",
        f"drawbox=x={bar_l_box}+{keycap_l}:y={keycap_t}:w={keycap_w}:h={KEYCAP_H}:color={KEYCAP_BG}:t=fill:{en}",
        f"drawbox=x={bar_l_box}+{keycap_l}:y={keycap_t}:w={keycap_w}:h={KEYCAP_H}:color={KEYCAP_EDGE}:t=2:{en}",
        f"drawtext=fontfile={bold}:text={key}:fontsize={F}:fontcolor={KEYCAP_EDGE}:x={bar_l_txt}+{key_l}:y={text_y}:{en}",
        f"drawtext=fontfile={regular}:text={SEP}:fontsize={F}:fontcolor={ACCENT}:x={bar_l_txt}+{sep_l}:y={sep_y}:{en}",
        f"drawtext=fontfile={bold}:text={action}:fontsize={F}:fontcolor={ACTION_FG}:x={bar_l_txt}+{action_l}:y={text_y}:{en}",
    ]


def main() -> None:
    if not GIF.exists():
        raise SystemExit(f"{GIF} not found — run `vhs demo/demo.tape` first")

    regular, bold = _fonts()
    overlays = ",".join(f for badge in BADGES for f in _badge(regular, bold, *badge))
    # palettegen/paletteuse keeps the re-encoded GIF crisp and small.
    filtergraph = (
        f"[0:v]{overlays},split[s0][s1];"
        "[s0]palettegen=stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=3[v]"
    )

    tmp = GIF.with_suffix(".tmp.gif")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(GIF),
            "-filter_complex",
            filtergraph,
            "-map",
            "[v]",
            "-loop",
            "0",
            str(tmp),
        ],
        check=True,
    )
    shutil.move(str(tmp), str(GIF))
    print(f"Overlaid {len(BADGES)} key badges onto {GIF}", file=sys.stderr)


if __name__ == "__main__":
    main()
