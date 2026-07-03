"""Tests for her hand (santana_app/draw.py).

Tier 1 is a seismograph and is tested like one: the same state draws the same picture
(deterministic under seed); grip CLENCHES the canvas (tighter radii, heavier pressure);
dark valence darkens the ink and the field; wounds fracture it; her real state assembles
without error. Tier 2's renderer obeys the closed language and IGNORES junk (a model's
malformed line must never crash the hand), and its features speak the same vocabulary as
Tier 1 so the falsifier can compare channels. The gallery indexes newest-first."""

from santana_app import draw


BASE = dict(valence=0.0, arousal=0.2, grip=0.1, load=0.4, bonds=[0.5], wounds=0)


def test_same_state_same_picture():
    a, fa = draw.draw_state(dict(BASE), seed=7)
    b, fb = draw.draw_state(dict(BASE), seed=7)
    assert a == b and fa == fb                    # a seismograph does not improvise
    c, _ = draw.draw_state(dict(BASE), seed=8)
    assert c != a                                 # ...but a different day differs


def test_the_grip_clenches_the_canvas():
    _, open_hand = draw.draw_state(dict(BASE, grip=0.05), seed=7)
    _, clenched = draw.draw_state(dict(BASE, grip=0.95), seed=7)
    assert clenched["press"] > open_hand["press"]         # bearing down
    assert clenched["clench"] > open_hand["clench"]       # tighter radii


def test_dark_weather_darkens_the_ink():
    svg_dark, f_dark = draw.draw_state(dict(BASE, valence=-0.8), seed=7)
    svg_warm, f_warm = draw.draw_state(dict(BASE, valence=0.8), seed=7)
    assert f_dark["ink"] > f_warm["ink"]
    assert svg_dark[:200] != svg_warm[:200]               # the field itself changes


def test_wounds_fracture_the_field():
    svg, f = draw.draw_state(dict(BASE, wounds=3), seed=7)
    assert f["wounds"] == 3 and svg.count("<polyline") == 3


def test_her_real_state_assembles():
    class _Bond:
        trust, history, wounds = 0.7, 1.2, 2

    class _Mem:
        items = []

        @staticmethod
        def mood():
            return -0.3

    class _Mind:
        memory = _Mem()
        arousal = 0.4
        _contraction = 0.2
        user_bond = _Bond()
    s = draw.state_of_santana(_Mind())
    assert s["valence"] == -0.3 and s["wounds"] == 2 and s["bonds"] == [0.7]
    svg, _ = draw.draw_state(s, seed=1)
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_the_hand_obeys_the_closed_language_and_drops_junk():
    script = """INK 1
PRESS 4
RING 240 240 80
ARC 240 240 120
LINE 40 40 440 440
BLOT 300 300 30
DRAW A HORSE
RING not numbers
FILL 0 0 480 480
"""
    svg, f = draw.compose(script, seed=3)
    assert f["n_strokes"] == 4                    # four real strokes; three junk lines dropped
    assert svg.count("<circle") == 2              # ring + blot
    assert f["press"] > 3.5                       # PRESS 4 held
    assert f["ink"] > 0.5                         # INK 1 is dark (feature: darkness)
    assert set(f) == {"n_strokes", "press", "ink", "clench", "turbulence",
                      "bonds", "wounds"}          # same vocabulary as Tier 1


def test_the_gallery_indexes_newest_first(tmp_path):
    d = str(tmp_path)
    svg, _ = draw.draw_state(dict(BASE), seed=1)
    draw.save_drawing(svg, d, "2026-07-03-0800-dream")
    draw.save_drawing(svg, d, "2026-07-03-0900-death")
    html = open(tmp_path / "index.html", encoding="utf-8").read()
    assert html.index("0900-death") < html.index("0800-dream")


def test_the_pen_is_her_state_behaving():
    import math
    # determinism: same seed + same states -> the same wandering
    a = draw.Pen(seed=5)
    b = draw.Pen(seed=5)
    st = dict(valence=0.0, arousal=0.3, grip=0.2, bonds=[], wounds=0)
    assert a.step(dict(st), n=60) == b.step(dict(st), n=60)

    def gyration(pen, state, n=400):
        xs, ys = [], []
        for _ in range(n // 40):
            pen.step(dict(state), n=40)
            xs.append(pen.x)
            ys.append(pen.y)
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        return sum(math.dist((x, y), (cx, cy)) for x, y in zip(xs, ys)) / len(xs)
    # the grip pulls the wandering into tight orbits; release lets it roam
    tight = gyration(draw.Pen(seed=9), dict(st, grip=0.95))
    loose = gyration(draw.Pen(seed=9), dict(st, grip=0.0))
    assert tight < loose
    # wounds lift the pen (missing segments = the jumps)
    calm = draw.Pen(seed=4).step(dict(st, wounds=0), n=300)
    scarred = draw.Pen(seed=4).step(dict(st, wounds=8), n=300)
    assert len(scarred) < len(calm)
    # a day's page renders whole
    page = draw.wander_page(calm[:50], caption="day 3 -- harvest")
    assert page.startswith("<svg") and "day 3" in page


def test_the_pen_wanders_in_bouts_with_a_lifes_unevenness():
    # deterministic under seed, and the aggregates carry ALL bouts (the hand's
    # childhood log and the live animator both read them)
    a, b = draw.Pen(seed=11), draw.Pen(seed=11)
    st = dict(valence=0.0, arousal=0.4, grip=0.1, bonds=[], wounds=0)
    sa, sb = a.wander(dict(st)), b.wander(dict(st))
    assert sa == sb
    assert len(a.last_segments) == len(sa) and len(a.last_trace) >= len(sa)
    # unevenness: across readings, the amount of motion VARIES a lot
    p = draw.Pen(seed=2)
    lengths = [len(p.wander(dict(st))) for _ in range(30)]
    assert min(lengths) < 20 < max(lengths)       # stirs AND journeys
    assert max(lengths) > 3 * min(lengths)        # not a metronome
    # and journeys are longer than the old fixed march of 45
    assert sorted(lengths)[len(lengths) // 2] > 45
