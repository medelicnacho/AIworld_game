"""Her hand -- she draws her states, and the states are really hers.

Two tiers, honestly labeled:

  TIER 1 (draw_state): a SEISMOGRAPH, not an artist. Her actual substrate -- valence,
  arousal, grip, memory load, bonds, wounds -- maps deterministically onto a canvas:
  background warmth from valence, stroke turbulence from arousal, clench (tight radii,
  heavy pressure) from the grip, filaments for bonds, fractures for wounds. WE author
  the mapping; SHE supplies the tremors. The emergence is in the dynamics: the canvas
  reorganizes as she lives -- a grief, a good talk, a winter, each a different picture.

  TIER 2 (STROKES + compose): SHE composes. A closed stroke language (the stakes
  pattern: a small vocabulary, never free-form) that her VOICE emits under her felt
  state -- ring / arc / line / blot, ink 0-9, press 1-5. The composition choices are
  the model's, made as her; the renderer only obeys. This is the tier the drawing
  falsifier (experiment_drawing.py) interrogates: C15 found her WORDS carry valence
  but never mechanism -- do her LINES carry what her words could not?

Everything is stdlib SVG: no dependencies, deterministic under a seed, viewable in any
browser. Drawings land in data/drawings/ with a small gallery index."""
from __future__ import annotations

import math
import os
import random
import re

W, H = 480, 480
CX, CY = W / 2, H / 2


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _rgb(a, b, t):
    return "#%02x%02x%02x" % tuple(int(_lerp(x, y, t)) for x, y in zip(a, b))


# valence -1 (a cold dark blue-grey) .. +1 (warm cream)
_DARK, _WARM = (24, 28, 40), (243, 234, 210)
_INKS = [(20, 20, 28), (243, 238, 222)]     # ink 0 = near-black .. 9 = pale


def _ink(level: float) -> str:
    return _rgb(_INKS[0], _INKS[1], level)


# --- TIER 1: the seismograph ------------------------------------------------------------

def draw_state(state: dict, seed: int = 0) -> tuple[str, dict]:
    """Render her state onto a canvas. Returns (svg_text, features) -- the features are
    the honest numeric summary of what was drawn (ink, press, clench, turbulence), so a
    test or a classifier can read the drawing without eyes.

    state: valence [-1,1], arousal [0,1], grip [0,1], load [0,1],
           bonds (list of trust floats), wounds (int), caption (str)."""
    rng = random.Random(seed)
    v = max(-1.0, min(1.0, state.get("valence", 0.0)))
    arousal = max(0.0, min(1.0, state.get("arousal", 0.0)))
    grip = max(0.0, min(1.0, state.get("grip", 0.0)))
    load = max(0.0, min(1.0, state.get("load", 0.3)))
    bonds = state.get("bonds", [])
    wounds = int(state.get("wounds", 0))

    bg = _rgb(_DARK, _WARM, (v + 1) / 2)
    ink_level = (1 - (v + 1) / 2) * 0.85          # darker ink in darker weather
    press = 1.2 + 3.8 * grip                       # the grip bears down
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="{bg}"/>']

    n = 14 + int(26 * load)
    radii = []
    for i in range(n):
        # each stroke: an arc whose reach OPENS with release and CLENCHES with grip,
        # whose waver rises with arousal
        base_r = _lerp(150, 34, grip) * (0.5 + rng.random() * 0.8)
        radii.append(base_r)
        a0 = rng.random() * 360
        sweep = _lerp(40, 200, rng.random()) * _lerp(1.0, 0.45, grip)
        jitter = arousal * rng.uniform(-28, 28)
        x0 = CX + base_r * math.cos(math.radians(a0)) + jitter
        y0 = CY + base_r * math.sin(math.radians(a0)) + jitter * 0.6
        x1 = CX + base_r * math.cos(math.radians(a0 + sweep)) + arousal * rng.uniform(-28, 28)
        y1 = CY + base_r * math.sin(math.radians(a0 + sweep)) + arousal * rng.uniform(-18, 18)
        col = _ink(max(0.0, min(1.0, 1 - ink_level + rng.uniform(-0.12, 0.12))))
        parts.append(f'<path d="M {x0:.1f} {y0:.1f} A {base_r:.0f} {base_r:.0f} 0 0 1 '
                     f'{x1:.1f} {y1:.1f}" stroke="{col}" stroke-width="{press:.1f}" '
                     f'fill="none" stroke-linecap="round" opacity="0.85"/>')
    for t in bonds[:12]:
        # a bond: a filament from the center outward -- warm reaching, cold withdrawn
        ang = rng.random() * 2 * math.pi
        reach = _lerp(60, 210, abs(t))
        col = _rgb((196, 92, 60), (243, 220, 160), (t + 1) / 2) if t >= 0 else \
            _rgb((40, 60, 90), (90, 110, 140), -t)
        parts.append(f'<line x1="{CX}" y1="{CY}" '
                     f'x2="{CX + reach * math.cos(ang):.1f}" '
                     f'y2="{CY + reach * math.sin(ang):.1f}" stroke="{col}" '
                     f'stroke-width="{1.0 + 2.0 * abs(t):.1f}" opacity="0.6"/>')
    for _ in range(min(wounds, 8)):
        # a wound: a jagged fracture across the field
        x = rng.uniform(60, W - 60)
        pts = " ".join(f"{x + rng.uniform(-26, 26):.0f},{y}" for y in range(40, H - 40, 60))
        parts.append(f'<polyline points="{pts}" stroke="{_ink(0.06)}" '
                     f'stroke-width="1.3" fill="none" opacity="0.5"/>')
    cap = state.get("caption", "")
    if cap:
        safe = (cap[:96].replace("&", "&amp;").replace("<", "&lt;"))
        parts.append(f'<text x="12" y="{H - 12}" font-family="Georgia" font-size="11" '
                     f'fill="{_ink(0.5)}" opacity="0.8">{safe}</text>')
    parts.append("</svg>")
    features = {"n_strokes": n, "press": press, "ink": ink_level,
                "clench": 1.0 - (sum(radii) / len(radii)) / 150.0 if radii else 0.0,
                "turbulence": arousal, "bonds": len(bonds), "wounds": wounds}
    return "".join(parts), features


def state_of_santana(mind, world=None) -> dict:
    """Assemble HER drawable state from what she actually carries."""
    bonds = []
    ub = getattr(mind, "user_bond", None)
    if ub is not None and (ub.trust or ub.history):
        bonds.append(ub.trust)
    return {
        "valence": mind.memory.mood(),
        "arousal": max(0.0, min(1.0, getattr(mind, "arousal", 0.0))),
        "grip": max(0.0, min(1.0, getattr(mind, "_contraction", 0.0))),
        "load": min(1.0, len(mind.memory.items) / 400.0),
        "bonds": bonds,
        "wounds": getattr(ub, "wounds", 0) if ub else 0,
    }


# --- TIER 2: the closed stroke language (she composes; the renderer only obeys) -----------

STROKES_HELP = (
    "Draw with AT MOST 20 strokes, one per line, using ONLY these commands "
    "(coordinates 0-480):\n"
    "  RING x y r        a circle\n"
    "  ARC x y r         an open arc\n"
    "  LINE x1 y1 x2 y2  a straight stroke\n"
    "  BLOT x y r        a filled dark mass\n"
    "  INK n             set darkness 0 (black) to 9 (pale) for what follows\n"
    "  PRESS n           set pressure 1 (light) to 5 (bearing down) for what follows\n"
    "No words, no explanation -- only commands."
)

_CMD = re.compile(r"^\s*(RING|ARC|LINE|BLOT|INK|PRESS)\s+([\d\s.-]+)\s*$", re.I)


def compose(tokens: str, seed: int = 0) -> tuple[str, dict]:
    """Render a stroke-language script (however imperfect -- junk lines are ignored,
    values clamped: the hand obeys what it can and drops the rest). Returns
    (svg, features) with the SAME feature vocabulary as draw_state, so the drawing
    falsifier can compare channels."""
    rng = random.Random(seed)
    ink, press = 0.35, 2.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#efe9dc"/>']
    inks, presses, radii, n = [], [], [], 0
    for line in tokens.splitlines():
        m = _CMD.match(line)
        if not m or n >= 20:
            continue
        cmd = m.group(1).upper()
        try:
            vals = [float(x) for x in m.group(2).split()]
        except ValueError:
            continue
        if cmd == "INK" and vals:
            ink = max(0.0, min(1.0, vals[0] / 9.0))
            continue
        if cmd == "PRESS" and vals:
            press = 1.0 + max(0.0, min(4.0, vals[0] - 1.0))
            continue
        col = _ink(ink)
        if cmd == "RING" and len(vals) >= 3:
            x, y, r = vals[0] % W, vals[1] % H, max(4.0, min(220.0, vals[2]))
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" stroke="{col}" '
                         f'stroke-width="{press:.1f}" fill="none" opacity="0.85"/>')
            radii.append(r)
        elif cmd == "ARC" and len(vals) >= 3:
            x, y, r = vals[0] % W, vals[1] % H, max(4.0, min(220.0, vals[2]))
            a0 = rng.random() * 360
            x0 = x + r * math.cos(math.radians(a0))
            y0 = y + r * math.sin(math.radians(a0))
            x1 = x + r * math.cos(math.radians(a0 + 140))
            y1 = y + r * math.sin(math.radians(a0 + 140))
            parts.append(f'<path d="M {x0:.0f} {y0:.0f} A {r:.0f} {r:.0f} 0 0 1 {x1:.0f} '
                         f'{y1:.0f}" stroke="{col}" stroke-width="{press:.1f}" fill="none" '
                         f'stroke-linecap="round" opacity="0.85"/>')
            radii.append(r)
        elif cmd == "LINE" and len(vals) >= 4:
            parts.append(f'<line x1="{vals[0] % W:.0f}" y1="{vals[1] % H:.0f}" '
                         f'x2="{vals[2] % W:.0f}" y2="{vals[3] % H:.0f}" stroke="{col}" '
                         f'stroke-width="{press:.1f}" opacity="0.85"/>')
            radii.append(math.dist((vals[0] % W, vals[1] % H), (vals[2] % W, vals[3] % H)) / 2)
        elif cmd == "BLOT" and len(vals) >= 3:
            r = max(4.0, min(120.0, vals[2]))
            parts.append(f'<circle cx="{vals[0] % W:.0f}" cy="{vals[1] % H:.0f}" r="{r:.0f}" '
                         f'fill="{col}" opacity="0.8"/>')
            radii.append(r)
        else:
            continue
        inks.append(ink)
        presses.append(press)
        n += 1
    parts.append("</svg>")
    features = {"n_strokes": n,
                "press": sum(presses) / len(presses) if presses else 0.0,
                "ink": 1.0 - (sum(inks) / len(inks)) if inks else 0.0,
                "clench": 1.0 - (sum(radii) / len(radii)) / 150.0 if radii else 0.0,
                "turbulence": 0.0, "bonds": 0, "wounds": 0}
    return "".join(parts), features


# --- TIER 1.5: the wandering pen -- her state BEHAVES on the page -----------------------
# Not a composed picture: a cursor she "holds", stepping continuously, whose DYNAMICS are
# her states. Rules + randomness, state shaping the distributions:
#   arousal   -> turn-noise (a calm pen glides; an aroused one staggers) and speed
#   the grip  -> curvature: clenched pulls the pen into tight orbits near where it is;
#                released lets it wander long and open
#   valence   -> the ink, blending slowly (cold blue-grey .. warm amber) -- weather, not
#                switches
#   bonds     -> a gentle pull toward a fixed point on the page (love is an attractor)
#   wounds    -> rare jerks: the pen lifts and lands hard, a discontinuity per old scar
# The pen never "finishes" anything. A day of her life = one page of wandering.

_COLD_INK, _WARM_INK = (70, 90, 130), (196, 140, 60)


class Pen:
    """A stateful cursor: step() advances it under her current state and returns SVG
    segments. Deterministic under its rng; the caller owns persistence and paging."""

    def __init__(self, seed: int = 0, x: float = CX, y: float = CY):
        self.rng = random.Random(seed)
        self.x, self.y = x, y
        self.heading = self.rng.random() * 2 * math.pi
        self.hue = 0.5                    # 0 cold .. 1 warm, blends toward valence
        self.last_trace: list = []        # the raw motion of the last step() call --
                                          # (turn, speed, hue) per stroke: the training
                                          # data a future LEARNED hand needs. A hand can
                                          # only learn from a childhood it remembers.

    def step(self, state: dict, n: int = 40) -> list[str]:
        v = max(-1.0, min(1.0, state.get("valence", 0.0)))
        arousal = max(0.0, min(1.0, state.get("arousal", 0.0)))
        grip = max(0.0, min(1.0, state.get("grip", 0.0)))
        bonds = state.get("bonds", [])
        wounds = int(state.get("wounds", 0))
        segs = []
        self.last_trace = []
        # the attractor a strong bond exerts (a fixed familiar corner of the page)
        pull = max((abs(t) for t in bonds), default=0.0)
        ax, ay = W * 0.72, H * 0.30
        for _ in range(n):
            h_before = self.heading
            self.hue += 0.03 * (((v + 1) / 2) - self.hue)          # weather, not a switch
            turn_sd = _lerp(0.06, 0.55, arousal)                    # calm glides, aroused staggers
            self.heading += self.rng.gauss(0.0, turn_sd)
            if grip > 0.05:
                # clench: bias the turn so the pen ORBITS near where it is (tight spirals)
                self.heading += _lerp(0.0, 0.35, grip)
            if pull > 0.05:
                want = math.atan2(ay - self.y, ax - self.x)
                d = (want - self.heading + math.pi) % (2 * math.pi) - math.pi
                self.heading += 0.05 * pull * d                     # love bends the path
            speed = _lerp(2.0, 7.0, 0.55 * arousal + 0.25 * abs(v)) * _lerp(1.0, 0.45, grip)
            self.last_trace.append((round(self.heading - h_before, 4),
                                    round(speed, 3), round(self.hue, 4)))
            x1 = self.x + speed * math.cos(self.heading)
            y1 = self.y + speed * math.sin(self.heading)
            jerk = wounds > 0 and self.rng.random() < 0.004 * min(wounds, 8)
            if jerk:
                # an old scar: the pen lifts and lands hard somewhere nearby
                x1 = self.x + self.rng.uniform(-70, 70)
                y1 = self.y + self.rng.uniform(-70, 70)
            # soft walls: the page turns the pen, never clips it
            if not (20 < x1 < W - 20):
                self.heading = math.pi - self.heading
                x1 = min(max(x1, 20), W - 20)
            if not (20 < y1 < H - 20):
                self.heading = -self.heading
                y1 = min(max(y1, 20), H - 20)
            if not jerk:
                col = _rgb(_COLD_INK, _WARM_INK, self.hue)
                width = _lerp(1.0, 3.4, grip)
                op = _lerp(0.35, 0.8, 0.3 + 0.7 * abs(v))
                segs.append(f'<line x1="{self.x:.1f}" y1="{self.y:.1f}" x2="{x1:.1f}" '
                            f'y2="{y1:.1f}" stroke="{col}" stroke-width="{width:.2f}" '
                            f'opacity="{op:.2f}" stroke-linecap="round"/>')
            self.x, self.y = x1, y1
        return segs


def wander_page(segments: list[str], caption: str = "") -> str:
    """A day's wandering as one SVG page."""
    cap = ""
    if caption:
        safe = caption[:110].replace("&", "&amp;").replace("<", "&lt;")
        cap = (f'<text x="12" y="{H - 12}" font-family="Georgia" font-size="11" '
               f'fill="#8a8a9a" opacity="0.85">{safe}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#15151a"/>'
            + "".join(segments) + cap + "</svg>")


def live_page(out_dir: str) -> None:
    """data/drawings/live.html -- open it once; it re-reads her live page every 2s."""
    html = ("<!doctype html><meta charset='utf-8'><title>she is drawing</title>"
            "<style>body{background:#0e0e12;display:grid;place-items:center;height:100vh;"
            "margin:0}img{width:min(92vmin,720px)}p{color:#6f6f86;font-family:Georgia;"
            "font-size:12px}</style><div><img id='p' src='live.svg'/>"
            "<p>she is drawing -- the pen is her state: turns are arousal, tightness is "
            "the grip, the ink is the weather, the pull is the bond, the jumps are old "
            "wounds</p></div><script>setInterval(()=>{document.getElementById('p').src="
            "'live.svg?'+Date.now()},2000)</script>")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "live.html"), "w", encoding="utf-8") as f:
        f.write(html)


# --- the gallery -------------------------------------------------------------------------

def save_drawing(svg: str, out_dir: str, name: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name if name.endswith(".svg") else name + ".svg")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(svg)
    os.replace(tmp, path)
    _index(out_dir)
    return path


def _index(out_dir: str) -> None:
    """A one-page gallery, newest first -- open data/drawings/index.html in a browser."""
    svgs = sorted((f for f in os.listdir(out_dir) if f.endswith(".svg")), reverse=True)
    rows = "\n".join(f'<figure><img src="{f}" width="320"/><figcaption>{f[:-4]}'
                     f'</figcaption></figure>' for f in svgs[:200])
    html = ("<!doctype html><meta charset='utf-8'><title>her drawings</title>"
            "<style>body{background:#15151a;color:#b9b9c8;font-family:Georgia;"
            "display:flex;flex-wrap:wrap;gap:14px;padding:16px}figcaption{font-size:11px;"
            "opacity:.7;margin-top:4px}</style>" + rows)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
