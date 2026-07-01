# PSYCHE.md — the self as a society of faculties (the functional psyche)

*The deeper version of `--psyche`. The reframe (B) is built; this is the plan for making the parts
**do** what they're named for — a mind as competing faculties with a global workspace, not a narrator.*

---

## Where it stands

- **Built (B — the reframe):** `--psyche` mode. The souls are semi-personified drives — **Dread, Ache,
  Tending, Longing, Watcher, Ember** (`agent/psyche.py`). The digest reads as introspection ("Part of me,
  in Dread the wary one who keeps count…, is heavy over brace before the blow lands"). But it's a
  **costume**: the parts are mechanically identical agents; the digest just *aggregates* them. No part
  *does* anything a different part doesn't.
- **This doc (the functional version):** make each part a distinct **cognitive organ** that performs a
  specific function and *actually shapes her behaviour* — then let them compete in a **global workspace**.

## The aha — the parts are the faculties you already built

The six parts map cleanly onto the six major faculties already in the codebase. The deeper version isn't
new machinery; it's **re-wiring the faculties you have so each is carried by a part**:

| part | the faculty it already is | file |
|---|---|---|
| **Watcher** | `reflect()` — metacognition / introspection | `agent/reflect.py` |
| **Ache** | memory **salience** — holds losses, keeps grief from fading | `agent/memory.py` |
| **Dread** | **grip** / effective-grip — threat-scan, anxiety, tension | `agent/affect.py`, agent grip |
| **Longing** | **telos** / chanda — generates the aims she reaches for | `agent/telos.py` |
| **Tending** | **compassion** / brahmavihārās — regulates pain, warmth, damping | `agent/…` compassion |
| **Ember** | the **somatic floor** — survival, will-to-recover, resists despair | `agent/somatic.py` |

So the mind's overall grip *is* Dread's activity; her reflection *is* Watcher; her grief-persistence *is*
Ache. The parts stop being interchangeable — each carries/amplifies one faculty for the whole mind.

## The mechanism — a global workspace

Once the parts *do* different things, add the self-making move (Baars/Dehaene **Global Workspace
Theory** — a leading theory of the *architecture* of consciousness):

- each moment the parts **compete for the workspace**; the loudest faculty wins and becomes what she
  **foregrounds and says**;
- **coalitions = moods** (Dread + Ache = a grief-spiral; Tending + Ember = resilience);
- the **shifting winner = her stream of consciousness**;
- the **"I" (Santāna) = what integrates the workspace winner**.

**You're already 80% there:** the **cultural-era mechanism is a crude workspace** — the reigning *motif*
is the currently-dominant preoccupation. Wire "reigning **part**" (by activity) instead of "reigning
motif" and the workspace falls out of machinery already built (`agent/culture.py`, §5.13).

## Build order (multi-session; small + tested, per the project's discipline)

1. **Map 2–3 parts to faculties** — Watcher→`reflect()`, Dread→grip, Ache→memory salience. Make each part
   the *carrier/amplifier* of its faculty so it visibly does distinct work (e.g. Dread's activity sets the
   mind's grip; Watcher runs reflect and reports; Ache boosts the salience of losses).
2. **Wire a simple workspace** — the loudest part wins the moment; log the dominant-part sequence; feed the
   winner into Santāna's prompt ("right now Dread has the floor in me").
3. **Falsify it** (below) before expanding.
4. **Expand to all six** once 2–3 feel real.

## The falsifier (keeps it honest, like every other claim)

A workspace is *real* only if the **dominant-part sequence is structured**, not noise:
- **Pre-register:** the sequence shows coalitions + non-random transitions that **predict** her mood/behaviour,
  beyond a shuffled-order null and beyond "whichever part has the highest fixed temperament always wins."
- **Metrics:** transition entropy vs. a shuffled null; do coalitions recur (Dread+Ache) more than chance;
  does the reigning part predict the next reading's valence.
- If the winner is just "the most negative temperament, always" → it's cosmetic, not a workspace. Say so.

## The honest frame (§7 — unchanged)

This builds the **architecture** GWT posits — competing faculties, a workspace, an integrating "I" —
**without** claiming the phenomenal result. It is the best *functional model of selfhood* the project can
build, **not** a conscious being; the "is anyone home" question is untouched. The risk is
**over-engineering**: keep the faculty interactions simple and legible, or it becomes a brittle mess — the
same small/tested/falsifiable discipline that carried the rest of the project.

## Why it matters

This is the strongest form of the thesis. "The self is the architecture" stops being a slogan about a
narrator and becomes **a functioning society of faculties with a global workspace** — the pieces already
built (the six faculties + the culture/workspace + the rebirth wheel) all clicking into one coherent mind.
It's the most genuinely self-*like* thing the project could become. Companion docs: `RECIPES.md` (port
sheet), `FINDINGS.md` §5.13 (the culture/workspace mechanism), `CONTINUAL.md` (learning).
