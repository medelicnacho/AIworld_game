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
MURMUR_VOICE_CHANCE = 0.6   # fraction of murmur events actually voiced (the rest are silent thought)
MURMUR_VOLUME = 0.12        # the murmur is a faint background hum, well under the clear LLM speech
# the murmur is voiced from a PRE-SYNTHESIZED, cached pool (live drift is too varied
# to synthesize on the fly fast enough). The live drift still feeds thought + bubbles.
MURMUR_TEXTS = list(THE_DEVOUT.scripture) + list(THE_PATH.scripture) + [
    "the cold takes everything", "the light returns slowly",
    "nothing holds for long now", "we are not alone here",
]

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
    return VOICES.get(sid.split(".")[0].split("~")[0], DEFAULT_VOICE)


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
                emergent: bool = False, spawn: bool = False) -> tuple[World, dict]:
    if backend == "ollama":
        llm = OllamaLLM(model="gemma3:4b")
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
                  breed_enabled=breed, pop_cap=pop_cap, murmur_enabled=murmur)
    world.llm = llm   # the collective consciousness speaks through it
    rng = __import__("random").Random(move_seed)
    colours = {}
    # procedural genesis: the LLM authors six distinct souls up front (slow on a
    # real model -- one call each); their generated inner-voice seeds the Markov.
    # Each is anchored to a DIFFERENT preoccupation so they don't converge.
    chars = None
    if spawn:
        concepts = rng.sample(genesis.SEED_CONCEPTS, len(CAST))
        chars = [genesis.generate_character(llm, rng, concepts[i]) for i in range(len(CAST))]
        genesis.dedupe_names(chars, rng)        # the model over-uses a few names
    for i, (cid, name, temp, faith) in enumerate(CAST):
        # start them in a loose central knot so the split is an emergence, not a setup
        pos = (W / 2 + rng.uniform(-70, 70), H / 2 + rng.uniform(-70, 70))
        # STAGGERED lifespans so souls die of old age one at a time (a graced one
        # leaves an heir, a fallen one doesn't) instead of all at once -- born at
        # the same tick with one shared lifespan, they vanished in a single instant.
        # --no-aging makes them effectively immortal for uninterrupted war-watching.
        life = 10**9 if no_aging else rng.randint(6000, 15000)   # ~10..25 min at 10Hz
        if spawn:
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
    args = ap.parse_args()
    room = args.room
    murmur_on = not args.no_murmur   # the ambient murmur plays in BOTH modes by default
    # EMERGENT is the default now. --collective restores the old faith-mind debate;
    # --individual is the faith cast speaking per-agent. --raw is an orthogonal
    # modifier (works with the default emergent world too). --spawn implies an
    # emergent world built from procedurally-generated souls.
    collective = args.collective
    emergent = (not args.collective and not args.individual) or args.spawn

    # spawn wants births (each one a fresh generated self), so breeding is on for
    # it; plain emergent keeps a fixed cast.
    breed = not args.no_breed and (args.spawn or not emergent)
    world, colours = build_world(args.llm, no_aging=args.no_aging, breed=breed,
                                 pop_cap=args.pop_cap, murmur=murmur_on,
                                 emergent=emergent, spawn=args.spawn)
    if args.raw or args.concept:             # the subconscious speaks (raw) or is interpreted (concept)
        for a in world.agents:
            a.raw_speech = args.raw
            a.concept_speech = args.concept and not args.raw   # raw wins if both given
    names = {a.id: a.name for a in world.agents}   # generated names in spawn mode
    names["user"] = "You"
    for fid, relig in RELIGION_OBJ.items():          # the faith minds show by name
        names[f"mind:{fid}"] = relig.name
    last_line: dict[str, tuple[str, float]] = {}      # speaker_id -> (text, when)
    transcript: deque = deque(maxlen=14)              # VISIBLE chat (drip-fed in slow mode)
    pending: deque = deque(maxlen=80)                 # firehose buffer waiting to be shown

    tts = make_tts(enabled=not args.mute)             # Piper voices (or NullTTS)
    speech_q: queue.Queue = queue.Queue(maxsize=8)   # the clear LLM voice (always played)
    murmur_pool: dict = {}   # voice-key -> [cached clips in that voice], filled in background

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
        # voice the murmuring agent's subconscious in ITS OWN voice (a random
        # cached clip for that agent's voice), overlapping and quiet. The live
        # drift still feeds thought + shows in the bubble; this is the ambient sound.
        if not murmur_on:
            return
        sid, _frag = payload
        base = sid.split(".")[0].split("~")[0]   # child voices follow their lineage
        clips = murmur_pool.get(base)
        if clips and random.random() < MURMUR_VOICE_CHANCE:
            random.choice(clips).play()
    world.bus.subscribe("murmur", on_murmur)

    def voice_line(sid, text, overlap=False, volume=1.0):
        """Queue a CLEAR (LLM / deliberate) line for the priority speech queue.
        overlap=True plays without waiting (room); overlap=False is one-at-a-time."""
        if not text.strip(". "):
            return
        try:
            speech_q.put_nowait((_voice_for(sid), text, overlap, volume))
        except queue.Full:
            pass

    # pre_init BEFORE pygame.init() so the mixer comes up with a roomy buffer (a
    # busy CPU running the LLM can't then starve playback into scratchiness).
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

    def murmur_pool_loop():   # synthesize each agent's murmur clips ONCE, in the background
        if not (murmur_on and voice_via_mixer):
            return
        # text-outer, voice-inner: after the first line, EVERY voice already has a
        # clip, so all voices are heard early instead of one model at a time
        for txt in MURMUR_TEXTS:
            for cid, voice in VOICES.items():
                if not running.is_set():
                    return
                fd, path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    tts.synth_to(txt, voice, path)
                    clip = pygame.mixer.Sound(path)   # its own Sound, its own volume
                    clip.set_volume(MURMUR_VOLUME)
                    murmur_pool.setdefault(cid, []).append(clip)
                except Exception as exc:  # noqa: BLE001
                    print("[murmur] synth failed:", exc, file=sys.stderr)
                finally:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    def genesis_loop():   # spawn mode: mint a fresh self for every soul that is born
        genesised = {a.id for a in world.agents}
        while running.is_set():
            newborns = [a for a in list(world.agents) if a.id not in genesised]
            for a in newborns:
                genesised.add(a.id)
                ch = genesis.generate_character(world.llm, random.Random())  # off the sim
                with world.lock:
                    genesis.seed_agent(a, ch, tick=world.tick, fresh=True)
                    names[a.id] = a.name
                colours[a.id] = CAMP_GREY
                print(f"+++ a new soul wakes: {a.name} (line {a.id})", flush=True)
            time.sleep(1.5)

    loops = [animate_loop, advance_loop, speech_loop, tts_loop, murmur_pool_loop]
    if args.spawn:
        loops.append(genesis_loop)
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
            if camps:
                shout = "  ".join(
                    f"[{flags.get(frozenset(g), '?')}] " + "+".join(names.get(c, c) for c in g)
                    for g in camps)
                print(f"~~ emergent camps: {shout}", flush=True)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running.clear()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_s:
                slow_mode = not slow_mode   # toggle slow mode live
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
        pygame.display.flip()
        clock.tick(60)

    running.clear()
    pygame.quit()


if __name__ == "__main__":
    main()
