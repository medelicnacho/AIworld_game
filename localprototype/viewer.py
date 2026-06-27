"""A god's-eye 2D viewer: watch the social dynamics become territory.

The world is headless; this just subscribes to its event bus and draws. Each
agent is a body that drifts under social forces (toward kin, away from foes), so
the factions the affinity ledger forms become visible spatial clusters. Green
lines are bonds (kinship), red are enmities. Body colour is temperament (cold
blue .. warm orange), ring brightness is grace, and the last thing each agent
said floats beside it.

Two voices, shown apart: the LLM SPEECH (what an agent says out loud) scrolls in
the side chat; the Markov SUBCONSCIOUS drift (what's churning in its mind) floats
as a dim thought bubble above its head. Default backend is the real local model
so the chat is genuine speech; --llm mock is the fast nonsense stand-in.

    python viewer.py                 # real gemma3:4b speech in the chat
    python viewer.py --llm mock      # fast placeholder (movement demo, no real talk)
    python viewer.py --step-ms 120   # slow the world down to read along
"""

from __future__ import annotations

import argparse
import math
import os
import queue
import random
import sys
import tempfile
import threading
import time
from collections import deque

import pygame

from agent import genesis
from agent.agent import Agent
from agent.religion import THE_DEVOUT, THE_PATH
from services import factions
from services.llm import MockLLM, OllamaLLM
from services.tts import Voice, make_tts
from world.sim import World

W, H = 980, 680
BG = (16, 18, 24)

_HERE = os.path.dirname(os.path.abspath(__file__))
# Quiet looping background music: the two tracks play one after another, forever.
MUSIC = ["Solitude_at_Dawn.mp3", "Beneath_A_Watching_Sky.mp3"]
MUSIC_VOLUME = 0.15   # under the voices
MUSIC_END = pygame.USEREVENT + 1
MURMUR_VOICE_CHANCE = 0.85  # fraction of murmur events actually voiced (the rest are silent thought)
MURMUR_VOLUME = 0.15        # the murmur is a faint background hum, well under the clear LLM speech
MURMUR_MIN_GAP = 1.4        # min seconds between NEW-fragment syntheses (cached repeats are
                           # unthrottled). Piper is CPU-bound; too low starves the LLM -> stall
# the murmur voices each soul's ACTUAL live Markov drift (the text in its bubble),
# synthesized on demand and cached -- not a fixed pool of canned lines.

# Two faiths, mixed ACROSS temperaments so religion -- not mood -- is the faction
# line: each church has both bright and dark souls. (id, name, temperament, faith)
CAST = [
    ("river", "River", -0.55, "devout"),
    ("ash",   "Ash",   -0.6,  "path"),
    ("mire",  "Mire",  -0.5,  "devout"),
    ("lark",  "Lark",   0.6,  "path"),
    ("wren",  "Wren",   0.55, "devout"),
    ("sol",   "Sol",    0.5,  "path"),
]
RELIGION_OBJ = {"devout": THE_DEVOUT, "path": THE_PATH}
RELIGION_COLOUR = {"devout": (230, 200, 90), "path": (90, 205, 200)}   # gold vs teal
# emergent mode: a camp gets one of these as it forms; loners stay grey
CAMP_PALETTE = [(230, 120, 110), (110, 200, 230), (170, 220, 120),
                (220, 180, 100), (200, 130, 220), (120, 220, 190)]
CAMP_GREY = (150, 150, 160)
EAGER_FOUNDERS = 2          # author this many souls before the world starts; stream the rest in live

# A genuinely distinct Piper voice (its own model) per agent -- six different
# people, three churches' worth of timbres across British/American, male/female.
VOICES = {
    "river": Voice("en_GB-alan-medium.onnx", length_scale=1.18),                  # calm British male
    "ash":   Voice("en_US-ryan-medium.onnx", length_scale=1.08),                  # dry American male
    "mire":  Voice("en_GB-northern_english_male-medium.onnx", length_scale=1.20), # bleak Northern male
    "lark":  Voice("en_US-amy-medium.onnx",  length_scale=0.95),                  # quick, bright female
    "wren":  Voice("en_GB-cori-medium.onnx", length_scale=1.05),                  # warm British female
    "sol":   Voice("en_US-joe-medium.onnx",  length_scale=0.95),                  # open American male
}
DEFAULT_VOICE = Voice("en_US-kristin-medium.onnx")   # for any soul without a mapped voice

# the two collective MINDS speak in their own grave, distinct voices
COLLECTIVE_VOICES = {
    "devout": Voice("en_US-lessac-medium.onnx", length_scale=1.0),
    "path":   Voice("en_GB-cori-medium.onnx",   length_scale=1.0),
}


def _voice_for(sid):
    """The Piper voice for a speaker. A faith's mind ('mind:devout') gets its own
    voice; agents and their children ('river~7'/'river.1') use the lineage voice."""
    if sid.startswith("mind:"):
        return COLLECTIVE_VOICES.get(sid.split(":", 1)[1], DEFAULT_VOICE)
    base = sid.split(".")[0].split("~")[0]
    v = VOICES.get(base)
    if v is not None:
        return v
    # reborn streams ('stream:N') and any unmapped id: spread across the voice pool
    pool = list(VOICES.values()) + [DEFAULT_VOICE]
    return pool[hash(sid) % len(pool)]


def temperament_colour(t: float) -> tuple[int, int, int]:
    """Cold (blue) at -1 .. warm (orange) at +1."""
    x = (t + 1.0) / 2.0
    cold = (70, 130, 220)
    warm = (240, 150, 60)
    return tuple(int(cold[i] + (warm[i] - cold[i]) * x) for i in range(3))


# Stage 2 emergent mode: distinct starting leanings in WORD-space (not faith
# labels). Souls begin spread across these themes; who clusters with whom, and
# what banner each camp ends up rallying around, is left to the dynamics.
EMERGENT_SEEDS = [
    "the tide rises and the deep water remembers everything",
    "stone holds the weight of every age without complaint",
    "light breaks over the hills and the dawn forgives",
    "the machine hums beneath all our days and nights",
    "roots run deep and the old forest keeps its silence",
    "fire moves through everything that is ending",
]


def build_world(backend: str, move_seed: int = 0, move: bool = True,
                no_aging: bool = False, breed: bool = False,
                pop_cap: int = 24, murmur: bool = False,
                emergent: bool = False, spawn: bool = False,
                rebirth: bool = False, start: int | None = None,
                model: str = "gemma3:4b") -> tuple[World, dict]:
    if backend == "ollama":
        llm = OllamaLLM(model=model)
        if not llm.available():   # don't go silently mute if Ollama isn't running
            print("[viewer] Ollama not reachable -> falling back to mock speech.")
            llm = MockLLM(seed=7)
    else:
        llm = MockLLM(seed=7)
    # `move=False` keeps everyone in earshot for one shared conversation (used by
    # the terminal chat); the viewer leaves it on so factions take territory.
    world = World(events_enabled=False, move_enabled=move,
                  hearing_range=240.0 if move else 10_000.0,
                  bounds=(W, H), move_seed=move_seed,
                  breed_enabled=breed, pop_cap=pop_cap, murmur_enabled=murmur,
                  rebirth_enabled=rebirth)
    world.llm = llm   # the collective consciousness speaks through it
    if rebirth:
        # Wheel regime tuned so factions PERSIST across the rebirth wheel rather
        # than dissolving each time a body dies. experiment_regime (gemma3:1b) found
        # the 'combo' arm was the ONLY one whose modularity survived turnover:
        #   reborn_prebond -- the key, scale-independent lever: a reborn stream is
        #     born already bonded into the opinion-camp its vasana carried, so it
        #     joins the faction instantly instead of re-bonding from zero;
        #   vasana_noise   -- lower keeps the carried lean sharp through the bardo;
        #   bardo_ticks    -- shorter returns streams before the live cohort thins.
        # (Plain rebirth without these collapsed live --world's modularity to ~0 --
        # the churn outran affinity; see experiment_churn.)
        world.reborn_prebond = 0.5
        world.vasana_noise = 0.04
        world.bardo_ticks = (8, 20)
    rng = __import__("random").Random(move_seed)
    colours = {}
    # procedural genesis: the LLM authors six distinct souls up front (slow on a
    # real model -- one call each); their generated inner-voice seeds the Markov.
    # Each is anchored to a DIFFERENT preoccupation so they don't converge.
    # the founding cast: `start` of the named slots (e.g. just 2 -- a founding pair
    # that then reproduces up to the population cap)
    cast = CAST[:start] if start else CAST
    world._pending_founders = []   # souls authored AFTER startup, streamed in live
    chars = None
    if spawn:
        concepts = rng.sample(genesis.SEED_CONCEPTS, len(cast))
        # author only the first couple eagerly so the window comes alive fast; the
        # rest stream in on a background thread (founder_stream, set up by main)
        eager = min(EAGER_FOUNDERS, len(cast))
        chars = [genesis.generate_character(llm, rng, concepts[i]) for i in range(eager)]
        genesis.dedupe_names(chars, rng)        # the model over-uses a few names
    for i, (cid, name, temp, faith) in enumerate(cast):
        # start them in a loose central knot so the split is an emergence, not a setup
        pos = (W / 2 + rng.uniform(-70, 70), H / 2 + rng.uniform(-70, 70))
        # STAGGERED lifespans so souls die of old age one at a time (a graced one
        # leaves an heir, a fallen one doesn't) instead of all at once -- born at
        # the same tick with one shared lifespan, they vanished in a single instant.
        # --no-aging makes them effectively immortal for uninterrupted war-watching.
        # rebirth turns the wheel, but SLOWLY: souls must live long enough to make
        # each other tea, bond, and let a stable warm town form before death->bardo->
        # rebirth turns it over. (Short lives churned a revolving door of brief
        # strangers -- warmth never compounded and the cohort stayed fragmented.)
        life = (10**9 if no_aging
                else rng.randint(5000, 12000) if rebirth  # ~8-20 min, then death->bardo->rebirth
                else rng.randint(6000, 15000))            # ~10-25 min
        if spawn:
            if i >= len(chars):
                # not authored yet -> defer this founder to the streaming thread
                world._pending_founders.append((cid, pos, life, concepts[i]))
                continue
            # a procedurally-authored soul: keep cid (for its distinct voice) but
            # the name/disposition/subconscious all come from genesis. Emergent
            # bonding, so factions form from these random selves.
            a = Agent(cid, cid.capitalize(), pos, "", [], llm,
                      seed=hash(cid) % 9999, lifespan=life, religion=None)
            genesis.seed_agent(a, chars[i])
            colours[cid] = CAMP_GREY
        elif emergent:
            # No faith: a free voice whose stance lives in language and evolves.
            a = Agent(cid, name, pos, f"You are {name}, a wandering soul who speaks "
                      "your own mind.", list(EMERGENT_SEEDS), llm,
                      seed=hash(cid) % 9999, temperament=temp, style="",
                      lifespan=life, religion=None)
            a.seed_opinion_text(EMERGENT_SEEDS[i % len(EMERGENT_SEEDS)])
            a.seed_stance(random.Random(rng.randrange(2 ** 31)))  # signed stance -> drives the social graph
            colours[cid] = CAMP_GREY   # uncoloured: the camps aren't known yet
        else:
            relig = RELIGION_OBJ[faith]
            a = Agent(cid, name, pos, f"You are {name}, of {relig.name}.", [], llm,
                      seed=hash(cid) % 9999, temperament=temp,
                      style="", lifespan=life, religion=relig)
            colours[cid] = RELIGION_COLOUR[faith]
        world.add(a)
    return world, colours


_SOUND_CACHE: dict = {}        # (voice model, text) -> pygame Sound, so repeated
_SOUND_CACHE_MAX = 300        # murmur fragments replay instantly without re-synth


def _voice_sound(tts, voice, text):
    """A pygame Sound for this line, synthesized once and cached. The Markov
    murmur repeats the same fragments constantly, so caching turns it from a
    synthesis-bound trickle into instant overlapping replay."""
    key = (voice.model, text)
    snd = _SOUND_CACHE.get(key)
    if snd is None:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            tts.synth_to(text, voice, path)
            snd = pygame.mixer.Sound(path)   # loads the audio fully into memory
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if len(_SOUND_CACHE) >= _SOUND_CACHE_MAX:
            _SOUND_CACHE.pop(next(iter(_SOUND_CACHE)))   # drop an old one
        _SOUND_CACHE[key] = snd
    return snd


def _play_voice_via_mixer(tts, voice, text, running, wait=True, volume=1.0) -> None:
    """Play a line through pygame's mixer (same audio client as the music -- no
    per-line subprocess, no crackle). wait=True blocks until it finishes (synced,
    one-at-a-time); wait=False returns at once so lines OVERLAP like a room."""
    snd = _voice_sound(tts, voice, text)
    snd.set_volume(volume)               # murmur plays quieter than clear speech
    if wait:
        # the deliberate, one-at-a-time voice: play on the RESERVED channel 0 so a
        # storm of murmurs can never leave it without a channel (which would drop
        # the line silently). Channel.play always returns the channel.
        chan = pygame.mixer.Channel(0)
        chan.play(snd)
    else:
        chan = snd.play()                # overlapping (room): any free channel
    while wait and chan is not None and chan.get_busy() and running.is_set():
        time.sleep(0.03)


def _thought_bubble(screen, font, text, cx, base_y) -> None:
    """A dim little box floating above an agent showing its Markov subconscious
    drift -- its THINKING, kept separate from the LLM SPEECH in the side chat."""
    if not text:
        return
    surf = font.render(text, True, (140, 140, 155))
    w, h = surf.get_size()
    pad = 4
    box = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    box.fill((28, 30, 38, 190))
    bx, by = cx - (w + pad * 2) // 2, base_y - h - pad * 2 - 20
    screen.blit(box, (bx, by))
    screen.blit(surf, (bx + pad, by + pad))


def draw_hud(screen, font, small, world, hud) -> None:
    """A live metrics panel, top-left: the dynamics quantified as you watch -- not
    the controlled experiments (those are separate, multi-run A/Bs), but the same
    numbers, read off the running world. Toggle with [h]; dump full stats with [m]."""
    if not hud.get("show", True):
        return
    agents = list(world.agents)
    grace = sum(a.grace for a in agents) / len(agents) if agents else 0.0
    rows = [
        ("THE DATA REALM", (235, 235, 245)),
        (f"tick {world.tick}   souls {len(agents)}", (200, 200, 210)),
        (f"births {hud['births']}   deaths {hud['deaths']}   in bardo {len(world._bardo)}",
         (200, 200, 210)),
        (f"camps {hud['camps']}   modularity {hud['modularity']:+.2f}", (170, 220, 170)),
        (f"avg grace {grace:.2f}", (220, 210, 160)),
    ]
    banners = hud.get("banners", [])
    if banners:
        rows.append(("banners: " + ", ".join(b for b in banners if b)[:46], (200, 180, 220)))
    w = max(font.size(t)[0] for t, _ in rows) + 16
    h = len(rows) * 18 + 10
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((22, 24, 32, 205))
    screen.blit(panel, (8, 8))
    for i, (text, col) in enumerate(rows):
        screen.blit((font if i == 0 else small).render(text, True, col), (16, 14 + i * 18))


def draw_world(screen, world, colours, last_line, font, small, backend,
               transcript=None, names=None, slow_mode=False, queued=0) -> None:
    """Render one frame: bonds/enmities as lines, then the bodies, then a
    scrolling conversation log. Shared by the live loop and the offscreen
    snapshot harness so what you test is what you see.
    """
    screen.fill(BG)
    agents = list(world.agents)   # snapshot

    # 1) bonds and enmities as lines between bodies
    for a in agents:
        for b in agents:
            if a.id >= b.id:
                continue
            aff = (a.feels_about(b.id) + b.feels_about(a.id)) / 2.0
            if abs(aff) < 0.12:
                continue
            ax, ay = a.position
            bx, by = b.position
            # open war (accreted grievance) draws thick + bright red over the rest;
            # a LAUNDERED relationship (relabelled evil/blasphemer, not yet war)
            # draws orange -- the moment doctrine turns a fellow into an enemy.
            at_war = a.is_at_war_with(b.id) or b.is_at_war_with(a.id)
            laundered = (a.relationship.get(b.id) in ("evil", "blasphemer")
                         or b.relationship.get(a.id) in ("evil", "blasphemer"))
            if at_war:
                pygame.draw.line(screen, (235, 40, 40), (ax, ay), (bx, by), 3)
            elif laundered:
                pygame.draw.line(screen, (240, 140, 30), (ax, ay), (bx, by), 2)  # orange: relabelled
            elif aff > 0:
                col = (40, int(90 + 120 * min(aff, 1)), 60)    # green kinship
                pygame.draw.line(screen, col, (ax, ay), (bx, by), 1)
            else:
                col = (int(120 + 100 * min(-aff, 1)), 40, 50)  # red enmity
                pygame.draw.line(screen, col, (ax, ay), (bx, by), 1)

    # 2) the bodies
    for a in agents:
        x, y = a.position
        # colour by faith so children (not in the initial colour map) show their church
        base = RELIGION_COLOUR.get(getattr(a, "religion", ""), colours.get(a.id, (200, 200, 200)))
        g = getattr(a, "grace", 1.0)            # grace ring: brighter with grace
        pygame.draw.circle(screen, (int(60 + 160 * g),) * 3, (int(x), int(y)), 16, 2)
        r = 8 + int(4 * g)
        pygame.draw.circle(screen, base, (int(x), int(y)), r)
        screen.blit(small.render(a.name, True, (210, 210, 215)), (x + 14, y - 8))
        # the Markov subconscious drifts ABOVE the head as a thought; the LLM
        # speech goes to the side chat -- thinking and talking, kept apart.
        thoughts = a.thought.current(1)
        if thoughts:
            _thought_bubble(screen, small, thoughts[0][:40], int(x), int(y))

    # 3) the conversation log: who is saying what, scrolling up the left edge
    if transcript:
        names = names or {}
        n = len(transcript)
        for i, (sid, txt) in enumerate(transcript):
            who = names.get(sid, sid)
            fade = 90 + int(150 * (i + 1) / n)              # newer lines brighter
            line = small.render(f"{who}: {txt[:120]}", True, (fade, fade, min(fade + 20, 255)))
            screen.blit(line, (14, H - 18 * (n - i) - 14))

    slow = f"SLOW MODE ({queued} queued)" if slow_mode else "slow mode off"
    hud = (f"tick {world.tick}   agents {len(agents)}   backend {backend}   "
           f"chat: {slow}   [s] toggle  [esc] quit")
    screen.blit(font.render(hud, True, (150, 150, 160)), (12, 12))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma3:4b",
                    help="ollama model for speech, e.g. dolphin-mistral (less "
                         "sycophantic -> souls disagree). any model in `ollama list`")
    ap.add_argument("--llm", default="ollama", choices=["mock", "ollama"],
                    help="ollama = real LLM speech in the side chat; mock = fast nonsense")
    ap.add_argument("--step-ms", type=int, default=100,
                    help="subconscious heartbeat interval (ms): memory/thought/urge rate")
    ap.add_argument("--chat-delay", type=float, default=0.5,
                    help="slow-mode: seconds between chat lines appearing")
    ap.add_argument("--mute", action="store_true", help="no Piper voices (text only)")
    ap.add_argument("--no-music", action="store_true", help="no background music")
    ap.add_argument("--no-aging", action="store_true",
                    help="souls never die of old age (watch the war uninterrupted)")
    ap.add_argument("--no-breed", action="store_true",
                    help="no living reproduction (fixed cast of six)")
    ap.add_argument("--pop-cap", type=int, default=24, help="max living souls")
    ap.add_argument("--start", type=int, default=None,
                    help="number of FOUNDING souls (default: the full cast of 6). "
                         "e.g. --spawn --start 2 begins with a pair that reproduces "
                         "up to --pop-cap")
    ap.add_argument("--room", action="store_true",
                    help="the clear LLM voices overlap and the chat scrolls freely")
    ap.add_argument("--no-murmur", action="store_true",
                    help="no ambient subconscious murmur under the speech")
    ap.add_argument("--collective", action="store_true",
                    help="the old experience: no emergent factions, one LLM 'mind' "
                         "voice per RELIGION debating (was the default)")
    ap.add_argument("--individual", action="store_true",
                    help="the faith cast, each agent speaking for itself")
    ap.add_argument("--emergent", action="store_true",
                    help="(now the DEFAULT) no faiths -- factions form from evolving "
                         "opinion, each speaks its camp's banner, reported as it emerges")
    ap.add_argument("--raw", action="store_true",
                    help="raw mind: the LLM voices each agent's Markov subconscious "
                         "directly -- no persona/instructions, the drift IS the prompt")
    ap.add_argument("--spawn", action="store_true",
                    help="procedural genesis: the LLM authors six random souls at "
                         "load (their voice seeds the Markov) and a fresh self for "
                         "each one born. No authored cast; factions still emerge")
    ap.add_argument("--concept", action="store_true",
                    help="conceptual mind: the LLM INTERPRETS each agent's Markov "
                         "drift into its underlying meaning and speaks that -- "
                         "coherent like speech, yet still from the subconscious")
    ap.add_argument("--rebirth", action="store_true",
                    help="samsara: procedural souls, but at death the SELF dissolves "
                         "into a bardo and only its vasana ripens into a new, "
                         "identity-less stream -- no author, no self transmitted")
    ap.add_argument("--world", action="store_true",
                    help="THE FULL EMBODIED WORLD: every compatible piece at once -- "
                         "procedurally-authored souls with life-stories, emergent "
                         "factions naming their own banners, the conceptual mind "
                         "(coherent speech from the subconscious), and the "
                         "death->bardo->rebirth wheel. A preset for --rebirth --concept.")
    args = ap.parse_args()
    # plain `viewer.py` with no mode chosen starts the FULL embodied world; pick any
    # mode flag (or --emergent for the lighter fixed-cast emergent) to opt out.
    if not (args.collective or args.individual or args.spawn or args.rebirth
            or args.raw or args.concept or args.emergent or args.world):
        args.world = True
    if args.world:               # the flagship: stack the complementary features
        args.rebirth = True      # procedural souls + the samsaric wheel
        args.concept = True       # the Markov-driven coherent voice
    # --start N: a founding population that GROWS by reproduction. Growth means
    # living breeding (spawn), which overrides the population-conserving rebirth
    # wheel; keep the procedural souls and the coherent voice.
    start = None
    if args.start is not None:
        start = max(1, min(args.start, len(CAST)))
        args.spawn, args.rebirth, args.concept = True, False, True
    room = args.room
    murmur_on = not args.no_murmur   # the ambient murmur plays in BOTH modes by default
    # EMERGENT is the default now. --collective restores the old faith-mind debate;
    # --individual is the faith cast speaking per-agent. --raw is an orthogonal
    # modifier. --spawn / --rebirth build an emergent world from procedural souls;
    # --rebirth additionally turns the death->bardo->rebirth wheel.
    collective = args.collective
    spawn_cast = args.spawn or args.rebirth   # procedural initial population
    emergent = (not args.collective and not args.individual) or spawn_cast

    # --spawn births fresh authored selves (genesis_loop); --rebirth conserves the
    # population through the bardo instead (World handles it, no living breeding).
    breed = not args.no_breed and (args.spawn or not emergent) and not args.rebirth

    # Open the WINDOW first -- procedural genesis can take ~a minute (six LLM
    # calls), and without this the user stares at a bare terminal until it's done,
    # thinking nothing happened. Show a loading screen, THEN author the souls.
    try:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
    except pygame.error:
        pass
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Data Realm — god view")
    font = pygame.font.SysFont("dejavusans", 14)
    small = pygame.font.SysFont("dejavusans", 12)
    clock = pygame.time.Clock()
    # Author the world on a BACKGROUND thread so the window stays RESPONSIVE during
    # the slow genesis (six LLM calls, ~a minute) -- otherwise the main thread is
    # blocked and the OS flags the window "not responding". An animated loading
    # screen runs in the foreground until the souls are ready.
    _built: dict = {}

    def _build():
        try:
            _built["wc"] = build_world(args.llm, model=args.model,
                                       no_aging=args.no_aging, breed=breed,
                                       pop_cap=args.pop_cap, murmur=murmur_on,
                                       emergent=emergent, spawn=spawn_cast,
                                       rebirth=args.rebirth, start=start)
        except Exception as exc:  # noqa: BLE001
            _built["err"] = exc

    builder = threading.Thread(target=_build, daemon=True)
    builder.start()
    frame = 0
    while builder.is_alive():
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                return
        screen.fill(BG)
        label = (("summoning the first souls of the Data Realm" + "." * (frame // 8 % 4))
                 if spawn_cast else "waking the world…")
        msg = font.render(label, True, (200, 200, 210))
        screen.blit(msg, (W // 2 - msg.get_width() // 2, H // 2))
        pygame.display.flip()
        clock.tick(30)
        frame += 1
    builder.join()
    if "err" in _built:
        print("[viewer] world build failed:", _built["err"], file=sys.stderr)
        pygame.quit()
        return
    world, colours = _built["wc"]
    def apply_speech_mode(a):
        # the chosen voice (raw / concept) must follow onto EVERY soul, including
        # those born or reborn mid-run, or the world drifts back to plain persona
        # as the cast turns over (the bug that made --world incoherent over time)
        a.raw_speech = args.raw
        a.concept_speech = args.concept and not args.raw   # raw wins if both given
    if args.raw or args.concept:
        for a in world.agents:
            apply_speech_mode(a)
    names = {a.id: a.name for a in world.agents}   # generated names in spawn mode
    names["user"] = "You"
    for fid, relig in RELIGION_OBJ.items():          # the faith minds show by name
        names[f"mind:{fid}"] = relig.name
    last_line: dict[str, tuple[str, float]] = {}      # speaker_id -> (text, when)
    transcript: deque = deque(maxlen=14)              # VISIBLE chat (drip-fed in slow mode)
    pending: deque = deque(maxlen=80)                 # firehose buffer waiting to be shown

    tts = make_tts(enabled=not args.mute)             # Piper voices (or NullTTS)
    speech_q: queue.Queue = queue.Queue(maxsize=8)   # the clear LLM voice (always played)
    murmur_q: queue.Queue = queue.Queue(maxsize=24)  # the ACTUAL drift fragments to murmur

    def on_utterance(u):
        last_line[u.speaker_id] = (u.text, time.time())
        names.setdefault(u.speaker_id, u.speaker_id)  # heirs inherit a fallback name
        who = names.get(u.speaker_id, u.speaker_id)   # also echo the LLM speech to the terminal
        to = f" -> {names.get(u.addressed_to, u.addressed_to)}" if u.addressed_to else ""
        print(f"t{u.tick:>4} {who}{to}: {u.text}", flush=True)
        if room:
            # the room: chat scrolls freely and the clear LLM voice ALWAYS plays,
            # overlapping (it doesn't wait its turn) over the murmur under-layer
            transcript.append((u.speaker_id, u.text))
            voice_line(u.speaker_id, u.text, overlap=True)
        else:
            # synced mode: buffer the line; it's voiced when released into the chat
            pending.append((u.speaker_id, u.text))

    world.bus.subscribe("utterance", on_utterance)

    def on_murmur(payload):
        # Voice the agent's ACTUAL live drift fragment -- the very text floating in
        # its thought bubble -- in its own voice, quietly. (It used to play random
        # clips from a fixed pool of religion scripture, which had nothing to do
        # with the soul; that's why it was repetitive and "praised the Creator".)
        if not (murmur_on and voice_via_mixer):
            return
        sid, frag = payload
        if not frag or random.random() > MURMUR_VOICE_CHANCE:
            return
        try:
            murmur_q.put_nowait((_voice_for(sid), frag))   # synth/play on its own thread
        except queue.Full:
            pass
    world.bus.subscribe("murmur", on_murmur)

    def on_dissolution(sid):
        print(f"... {names.get(sid, sid)} dissolves into the bardo ...", flush=True)

    def on_rebirth(sid):
        # a new identity-less stream has condensed out of the bardo; register it
        a = next((x for x in world.agents if x.id == sid), None)
        if a is not None:
            names[sid] = a.name
            colours[sid] = CAMP_GREY
            apply_speech_mode(a)          # the reborn stream speaks in the world's voice too
            print(f"... a stream re-coalesces from the residue: {a.name} ...", flush=True)
    world.bus.subscribe("dissolution", on_dissolution)
    world.bus.subscribe("rebirth", on_rebirth)

    # live metrics for the HUD: cheap counters off the bus, plus camp/modularity
    # snapshots refreshed in the banner block. [h] toggles the panel, [m] dumps all.
    hud = {"births": 0, "deaths": 0, "modularity": 0.0, "camps": 0, "banners": [], "show": True}
    world.bus.subscribe("birth", lambda _s: hud.__setitem__("births", hud["births"] + 1))
    world.bus.subscribe("rebirth", lambda _s: hud.__setitem__("births", hud["births"] + 1))
    world.bus.subscribe("death", lambda _s: hud.__setitem__("deaths", hud["deaths"] + 1))

    def voice_line(sid, text, overlap=False, volume=1.0):
        """Queue a CLEAR (LLM / deliberate) line for the priority speech queue.
        overlap=True plays without waiting (room); overlap=False is one-at-a-time."""
        if not text.strip(". "):
            return
        try:
            speech_q.put_nowait((_voice_for(sid), text, overlap, volume))
        except queue.Full:
            pass

    # (the window, mixer pre_init, fonts and clock were created up front, before
    # genesis, so a loading screen could show during the slow authoring.)

    # ONE audio client for both music and voices. The voices used to shell out to
    # pw-play once per line, opening/closing a PipeWire stream each time, which
    # crackled the music stream -- so we synthesize and play them through this
    # same mixer instead (pre_init above gave it a roomy buffer). Piper WAVs are
    # 22050Hz mono; pygame resamples them to the mixer rate on load.
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init()
        except pygame.error as exc:
            print("[audio] mixer init failed:", exc, file=sys.stderr)
    # voices go through the mixer when Piper is available; else fall back to its
    # own player (NullTTS is a no-op when muted/unavailable)
    voice_via_mixer = (not args.mute and pygame.mixer.get_init() is not None
                       and tts.__class__.__name__ == "PiperTTS")
    if pygame.mixer.get_init():
        # Plenty of channels so many murmurs can overlap, AND reserve the FIRST
        # one for the clear LLM voice. Without the reservation a flurry of murmurs
        # could occupy every channel exactly when a deliberate line tries to play,
        # and snd.play() would return None -> the line is silently dropped (that
        # was the intermittent 'sometimes no TTS' on the LLM speech).
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(1)        # channel 0 belongs to the clear voice

    # quiet looping background music: play the first track, queue the second, and
    # re-queue the next on each track-end so the two cycle one after another forever
    tracks = [os.path.join(_HERE, m) for m in MUSIC
              if not args.no_music and os.path.exists(os.path.join(_HERE, m))]
    track_idx = 0
    if tracks and pygame.mixer.get_init():
        try:
            pygame.mixer.music.set_volume(MUSIC_VOLUME)
            pygame.mixer.music.load(tracks[0])
            pygame.mixer.music.play()
            pygame.mixer.music.set_endevent(MUSIC_END)
            if len(tracks) > 1:
                pygame.mixer.music.queue(tracks[1])
                track_idx = 1   # the last track we queued
        except pygame.error as exc:   # no audio device etc. -- run on in silence
            print("[music] could not start:", exc, file=sys.stderr)
            tracks = []

    # advance the world on its own thread so slow LLM turns don't freeze drawing
    running = threading.Event()
    running.set()

    def animate_loop():   # ~30Hz: smooth movement, never waits on the model
        while running.is_set():
            try:
                world.animate()
            except Exception as exc:  # noqa: BLE001 -- a viewer must never die
                print("[animate] failed:", exc, file=sys.stderr)
            time.sleep(0.033)

    def advance_loop():   # the subconscious heartbeat: memory, thought churn, urge
        while running.is_set():
            try:
                world.advance()
            except Exception as exc:  # noqa: BLE001
                print("[advance] failed:", exc, file=sys.stderr)
            time.sleep(args.step_ms / 1000.0)

    def speech_loop():    # the slow LLM turns, on their own thread
        faith_i = 0
        while running.is_set():
            try:
                if collective:
                    # round-robin the faith minds: each integrates its neurons and
                    # speaks, so the two collective consciousnesses debate
                    fids = world.faith_ids()
                    if fids:
                        world.collective_speak(fids[faith_i % len(fids)])
                        faith_i += 1
                    else:
                        time.sleep(0.1)
                else:
                    world.speak_turn()   # each agent speaks for itself
            except Exception as exc:  # noqa: BLE001
                print("[speech] failed:", exc, file=sys.stderr)
            time.sleep(0.05)

    def tts_loop():   # the clear LLM voice (always played; one synth thread)
        while running.is_set():
            try:
                voice, text, overlap, volume = speech_q.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                if voice_via_mixer:
                    _play_voice_via_mixer(tts, voice, text, running,
                                          wait=not overlap, volume=volume)
                else:
                    tts.speak(text, voice)   # NullTTS no-op, or Piper's own player
            except Exception as exc:  # noqa: BLE001 -- a bad voice must not kill audio
                print("[tts] play failed:", exc, file=sys.stderr)
            finally:
                speech_q.task_done()   # marks audio done -> unblocks the next synced chat line

    def murmur_synth_loop():   # voice the agents' ACTUAL drift fragments, on demand
        if not (murmur_on and voice_via_mixer):
            return
        last = 0.0
        while running.is_set():
            try:
                voice, frag = murmur_q.get(timeout=0.3)
            except queue.Empty:
                continue
            # THROTTLE: Piper synthesis is CPU-bound; left unbounded it starves the
            # (also CPU-bound) local LLM and stalls speech into a timeout. Skip
            # murmurs that arrive too soon -- cached repeats are cheap, but a NEW
            # fragment's synth must not crowd the model.
            key = (voice.model, frag)
            if key not in _SOUND_CACHE and time.time() - last < MURMUR_MIN_GAP:
                continue
            last = time.time()
            try:
                snd = _voice_sound(tts, voice, frag)  # caches by (voice, text)
                chan = snd.play()                     # auto-allocated channel
                if chan is not None:
                    chan.set_volume(MURMUR_VOLUME)    # per-channel, so the clear voice is untouched
            except Exception as exc:  # noqa: BLE001 -- a bad murmur must not kill audio
                print("[murmur] synth failed:", exc, file=sys.stderr)

    def genesis_loop():   # spawn mode: mint a fresh self for every soul that is born
        genesised = {a.id for a in world.agents}
        while running.is_set():
            newborns = [a for a in list(world.agents) if a.id not in genesised]
            for a in newborns:
                genesised.add(a.id)
                ch = genesis.generate_character(world.llm, random.Random())  # off the sim
                with world.lock:
                    # the model over-uses a few names ("Silas", "Corvus"); keep the
                    # newborn distinct from every soul currently alive
                    genesis.dedupe_names([ch], random.Random(),
                                         taken={x.name for x in world.agents})
                    genesis.seed_agent(a, ch, tick=world.tick, fresh=True)
                    names[a.id] = a.name
                    apply_speech_mode(a)      # the newborn speaks in the world's voice too
                colours[a.id] = CAMP_GREY
                print(f"+++ a new soul wakes: {a.name} (line {a.id})", flush=True)
            time.sleep(1.5)

    def founder_stream():   # streaming genesis: wake the remaining founders one by one
        for (cid, pos, life, concept) in list(getattr(world, "_pending_founders", [])):
            if not running.is_set():
                return
            ch = genesis.generate_character(world.llm, random.Random(), concept)  # off the sim
            a = Agent(cid, cid.capitalize(), pos, "", [], world.llm,
                      seed=hash(cid) % 9999, lifespan=life, religion=None)
            with world.lock:
                genesis.dedupe_names([ch], random.Random(), taken={x.name for x in world.agents})
                genesis.seed_agent(a, ch)
                apply_speech_mode(a)
                names[cid] = a.name
                colours[cid] = CAMP_GREY
                world.add(a)
            print(f"+++ a founding soul wakes: {a.name}", flush=True)
            time.sleep(4)   # pace genesis so it doesn't crowd the LLM's speech turns

    loops = [animate_loop, advance_loop, speech_loop, tts_loop, murmur_synth_loop]
    if args.spawn:
        loops.append(genesis_loop)
    if getattr(world, "_pending_founders", None):   # stream the rest of the cast in
        loops.append(founder_stream)
    for loop in loops:
        threading.Thread(target=loop, daemon=True).start()

    slow_mode = True            # like a livestream chat: on by default when it floods
    last_release = 0.0
    last_banner = 0.0
    while running.is_set():
        # Stage 2: every few seconds, read the emergent camps off the affinity
        # graph and the banner word each has rallied around -- the factions naming
        # themselves, live, from nothing assigned.
        if emergent and time.time() - last_banner > 8.0:
            last_banner = time.time()
            # recompute camps AND tag each soul with its camp's banner, so the next
            # thing it says leans toward its faction (update_camps does the stamping)
            camps, flags = world.update_camps()
            # recolour live: each camp keeps a stable colour keyed on its banner
            # word, so as souls join a camp they take on its colour on the map;
            # loners fade back to grey. The split becomes visible, not just audible.
            new_colours = {a.id: CAMP_GREY for a in world.agents}
            for gi, g in enumerate(camps):
                banner = flags.get(frozenset(g), "")
                col = CAMP_PALETTE[(hash(banner) if banner else gi) % len(CAMP_PALETTE)]
                for cid in g:
                    new_colours[cid] = col
            colours.update(new_colours)
            with world.lock:
                hud["modularity"] = factions.modularity(world.agents)
            hud["camps"] = len(camps)
            hud["banners"] = [flags.get(frozenset(g), "?") for g in camps]
            if camps:
                shout = "  ".join(
                    f"[{flags.get(frozenset(g), '?')}] " + "+".join(names.get(c, c) for c in g)
                    for g in camps)
                # modularity in the line so a long run logs whether it climbs/holds
                print(f"~~ t{world.tick} mod {hud['modularity']:+.2f} | {shout}", flush=True)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running.clear()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_s:
                slow_mode = not slow_mode   # toggle slow mode live
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_h:
                hud["show"] = not hud["show"]   # toggle the metrics panel
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_m:
                # dump the full faction metrics to the terminal on demand
                with world.lock:
                    summ = factions.summary(world.agents)
                print("\n--- faction metrics @ tick", world.tick, "---")
                for k, v in summ.items():
                    print(f"   {k}: {v}")
                print(flush=True)
            elif ev.type == MUSIC_END and tracks:
                # a track just ended and the queued one is now playing; queue the
                # next so the two keep alternating forever
                track_idx = (track_idx + 1) % len(tracks)
                pygame.mixer.music.queue(tracks[track_idx])

        # slow mode: release ONE line at a time, and only once the previous line's
        # voice has FINISHED (speech_q.unfinished_tasks == 0) plus a short gap -- so
        # the spoken audio and the side chat advance in lockstep. Off: dump the
        # whole backlog and let the voices queue up behind it.
        now = time.time()
        if not room:   # room mode fills the transcript directly in on_utterance
            if not slow_mode:
                while pending:
                    sid, text = pending.popleft()
                    transcript.append((sid, text))
                    voice_line(sid, text, overlap=False)
            elif (pending and now - last_release >= args.chat_delay
                  and speech_q.unfinished_tasks == 0):
                sid, text = pending.popleft()
                transcript.append((sid, text))
                voice_line(sid, text, overlap=False)   # next release waits on this audio
                last_release = now

        draw_world(screen, world, colours, last_line, font, small, args.llm,
                   transcript=transcript, names=names,
                   slow_mode=(slow_mode and not room), queued=len(pending))
        draw_hud(screen, font, small, world, hud)
        pygame.display.flip()
        clock.tick(60)

    running.clear()
    pygame.quit()


if __name__ == "__main__":
    main()
