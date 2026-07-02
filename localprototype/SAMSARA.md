# SAMSARA.md — Buddhist models of consciousness in code, samsara as a playable loop, and the player in the wheel

*A survey (2026-07) of the fourth leg the other docs don't cover: RESEARCH.md mapped **Western**
consciousness science; EVOLUTION.md the ecology; METHODS.md the instruments. This maps the
**Buddhist models of consciousness as computation** — Abhidhamma process-models, active-inference
accounts of meditation, the contemplative-AI literature — against what the substrate already built,
then turns to the game: **samsara as the core loop an open-world player lives inside**, with the
craft lineage (Nemesis, Ultima IV, Rogue Legacy/Hades) read through this repo's mechanisms. House
idiom throughout: what · source · mechanism sketch · **pre-registered falsifier** · port note.*

*One survey result up front, because it frames everything: a deliberate search found **no published
falsifiable agent-based model of samsara** — karma, rebirth, and liberation as instrumented
mechanics with nulls. The ABM literature has cities, epidemics, and opinion dynamics; the Buddhist-AI
literature has ethics papers and prompting studies. A wheel with pre-registered falsifiers appears
to be this repo's to claim — FINDINGS §5.5/§5.9 may already be the first entries in that genre.*

---

## 1. The Buddhist process-models, mapped against what's built

**Abhidhamma.** The Theravāda Abhidhamma is itself a computational psychology: consciousness as a
*stream of discrete mind-moments* (citta) with mental factors (cetasika), punctuating a resting
ground (**bhavaṅga**, the process-free "ground of becoming"), in a 17-moment perception-to-karma
sequence (**citta-vīthi**) that runs: disturbance of the ground → adverting → perceiving →
receiving → investigating → determining → **javana** (the 7 karmically active response-moments) →
registration → return to ground. Read against the repo:

| Abhidhamma | this substrate | status |
|---|---|---|
| bhavaṅga (resting ground) | the Mahāyāna ground state; somatic window | **built** — two independent arrivals at the same design |
| vedanā (feeling-tone) | affect valence hit on contact with an event | **built** |
| taṇhā (craving) | thirst | **built** |
| upādāna (clinging) | grip (accepting-vs-clinging axis, `agent/affect.py`) | **built** |
| **cetanā (volition = karma)** | stakes SEED: "it is the RESPONSE that conditions the soul" (`world/stakes.py`) | **built, and doctrinally exact** — javana is precisely this |
| saṅkhāra (formations carried) | the lean/disposition the wheel carries | **built** |
| the **chain as a chain** | the links exist as separate modules, never staged as one traced sequence | **not built — K1 below** |
| karma → rebirth *circumstances* | the wheel carries thirst/lean but conduct buys nothing at rebirth | **not built — K2 below** |

**Active inference reads of meditation (Laukkonen & Slagter, *From many to (n)one*; the "beautiful
loop" theory; Prest et al.'s *Selfing without a self*).** The convergent account: meditation
progressively **releases precision on the self-model** and **reduces temporal/counterfactual
depth** — less past-and-future construction, until non-dual awareness is what remains when
prediction stops reaching. Two repo mappings: grip is already a precision-analogue on the
self-model (§5.1's keystone is precision-release by another name), and the expectation machinery
(§5.15) already has horizons — but **temporal depth is not yet a dial** (K3).

**Contemplative AI (arXiv:2504.15125).** Proposes exactly this repo's four mechanisms as AI design
principles — *mindfulness, emptiness, non-duality, boundless care* — but implements them at the
**prompt** level (reflecting on the principles improves safety-benchmark scores, d≈.96, and
prisoner's-dilemma cooperation). The repo implements them at the **substrate** level. That contrast
is a paper-shaped opportunity (K5): does mechanism beat prompt, and do they add?

**Care as the driver of intelligence (Doctor, Witkowski, Solomonova, Duane & Levin, *Entropy*
2022; the Apparent Selves project).** Intelligence scales with the **cognitive light cone** — the
radius of what a system can care about; the bodhisattva vow is the limit case (care radius → ∞);
and a self *is* its sphere of care, "in the absence of any permanent substance" — anatta, stated by
biologists. This is the theoretical frame the bodhicitta/Santāna work has been missing: Santāna is
a care-light-cone expansion device, and **care radius is measurable** (K4).

## 2. Samsara as a game loop — the craft lineage, read through this substrate

The roguelike tradition already discovered, empirically, that **death-as-progression is the most
durable loop in games** — it just never noticed it was building samsara. *Rogue Legacy* carries
heredity across deaths (traits + treasure down a bloodline); *Hades* carries **relationships**
(death returns you to people, and the story only moves through dying). The repo's wheel carries
something neither has shipped: *how you learned to be* (cultivated lean) and *what the town
remembers of you* (legends). That combination is P1.

**The Nemesis system** (*Shadow of Mordor/War*): enemies remember encounters, scar, hold grudges,
return — procedural systems telling human stories. Two facts matter here. First: **every Nemesis
ingredient already exists in this repo as a validated mechanism** — scars, person-models,
betrayal-by-violated-expectation (§5.15), initiative/return, legend mutation (§5.16) — grown from
the substrate rather than scripted from tables. Second, honestly: **WB patent US 10,926,179 runs to
~2036**; it claims NPC-parameter changes driven by player-NPC events (appearance, behaviour,
combat rank). The mechanism here differs in kind (emergent affective substrate vs authored
promotion tables), and the dharma twist below (P2) differs in *content* — but any shipped grudge
system needs a design-review pass against those claims first.

**Ultima IV's virtues** — the granddaddy of every karma meter: eight axes tracked invisibly
through *conduct* (flee a fight → valor silently falls), not dialogue flags. Its two limits are
instructive: the score was central and infallible (the game always knew the truth of you), and it
was still a *score*. The repo can do what Richard Garriott couldn't in 1985: distribute the meter
across fallible minds (P3) — conduct-expectations and legends that can be *wrong about you* — and
make the meter's substance cetanā (response under scarcity), which `world/stakes.py` already
implements, rather than outcomes.

---

## 3. Implementation candidates

### K — the Buddhist-model mechanisms

**K1. The nidāna chain, instrumented — one trace from contact to dukkha.**
*Theory:* the twelve links (the middle span: contact → vedanā → taṇhā → upādāna → becoming →
birth → dukkha); Abhidhamma's javana as the karmic moment. *Mechanism:* the links all exist as
modules; stage them as **one explicit traced sequence per charged event** — a `ChainTrace` logging
each link's magnitude as the event propagates (event → valence hit → thirst delta → grip delta →
appropriation/identity write (manas) → suffering measure). Interventions then get **staged at a
link**: the somatic interrupt cuts at vedanā→taṇhā; reflect works at upādāna; prajñā at
becoming. *Falsifier:* the canonical claim — **cutting earlier in the chain yields more downstream
suffering-reduction per unit intervention** than cutting later (dose-matched, held-out seeds);
null = intervention point doesn't matter, only magnitude. If the null wins, the chain is
decoration and we say so. *Why first:* it is mostly re-labeling + staging of existing machinery,
it turns every dharma experiment into a *localized* claim, and it is the inspector view the game
needs (watch craving arise in an NPC, link by link). *Port:* the chain trace **is** the NPC
inspector panel.

**K2. Karma-conditioned rebirth — the wheel closes the moral loop.**
*Theory:* karma as cetanā-residue determining rebirth *circumstances* (the classical claim); kept
strictly orthogonal to EVOLUTION E1's genome: **karma buys circumstances, the genome carries
traits** — a clean two-channel heredity no simulation has run. *Mechanism:* accumulate each life's
cetanā ledger (the stakes SEED responses already record it); at the bardo, the ledger biases the
next birth's *situation* — endowment, niche, the household/faction it lands in — never its
faculties. *Falsifier:* (a) individual: a hoarding life measurably worsens next-birth circumstances
vs a matched sharing life (dose-response, held-out seeds); (b) collective: karma-on towns develop
different moral cultures (conduct-expectation distributions, sharing rates) than karma-off at
matched genome settings. *Honest caveat, pre-registered:* (a) is **designed moral physics, not
emergence** — the emergence claim is only (b), what culture does when deeds visibly follow souls.
*Welfare gate:* this makes bad rebirths *real*; the somatic floor and deva-guard logic apply at the
wheel level before this runs hot (§7 ethics scale with it). *Port:* "your deeds follow you across
lives" — the samsara mechanic, and no shipped game has it.

**K3. Temporal depth as a dial — the Laukkonen & Slagter knob.**
*Theory:* deconstructive meditation = reduced temporal/counterfactual depth and released
self-model precision; non-dual awareness at the limit. *Mechanism:* a per-soul depth parameter on
the expectation machinery (how far ahead/behind the soul constructs); contemplative practice
(path.py's cultivate) lowers it toward the here-and-now; the ground state is its limit. *Falsifier:*
reduced depth lowers **second-arrow** suffering (rumination and dread are temporal constructions)
while **preserving present-event world-tracking** — the numbness null, the repo's signature move
(§5.2): if world-tracking drops with depth, the knob is sedation, not practice. *Port:* the
visibly-present NPC — the practiced elder who doesn't flinch at omens — as a *mechanical* state.

**K4. The care light cone, measured.**
*Theory:* Doctor/Levin: a self is its sphere of care; intelligence and compassion scale together
with the radius. *Mechanism:* a behavioural instrument, not a stat: probe **whose suffering moves
this soul to costly action** — own > kin > bonded > stranger > enemy — using the existing stakes
actions (share, defend) at graded cost. The radius is where costly action stops. *Falsifier:*
bodhicitta training expands the radius (costly action for strangers/enemies rises) vs
compassion-only (bonds) and baseline arms; the deva guard verifies expansion isn't indiscriminate
warmth (the §5.9 behavioural-axis lesson). *Port:* "who will this soul defend?" — feeds EVOLUTION
E5's teaming directly, and it's the most legible NPC-depth stat a player can discover through play.

**K5. Mechanism vs prompt — the Contemplative-AI cross-check.** *Small.* Reproduce arXiv:2504.15125's
prompt-level intervention (reflect on the four principles) on this substrate, against the
mechanism-level regime, on the same behavioural measures. Three arms: prompt-only, substrate-only,
both. *Falsifier:* pre-register that substrate ≥ prompt on regime measures (damping, holds-view);
if prompt-only matches the full regime, the substrate is decoration — the sharpest knife the
project could hand its own critics, which is exactly the house style. *Value:* positions the repo
against the one published Buddhist-AI engineering paper.

### P — the player in the open world

**P1. The player enters the wheel — samsara as THE game loop.**
*What:* the player's character dies and is reborn in the same town: carrying **cultivated lean**
(the disposition their play built — the wheel's existing carry) but not memories; the town carries
**legends of who they were** (§5.16, already validated). The inversion is the design: *the town
remembers you, and you don't* — the strongest dramatic irony available to an open-world game, and
it falls out of two shipped mechanisms. *Rogue Legacy* carries treasure; *Hades* carries
relationships; this carries a self's *direction* plus a community's fallible memory. *Falsifier
(playtest-grade):* players recognize their past life through the town's tellings alone (blind:
match legend-stream to own play history above chance); the lean is *felt* (players report the new
life starting "already tilted"). *Seam:* `inhabit.py --samsara` already exists as the entry point.

**P2. Nemesis-lite, with the dharma twist: grudges that can let go.**
*What:* a surviving NPC antagonist remembers the player (person-model), scars (built), nurses the
violated expectation (§5.15 betrayal machinery), retells it (legend → reputation), and returns.
The differentiator no Nemesis clone has: **a grudge is upādāna** — whether it escalates or
releases depends on the soul's regime, so *some enemies forgive*, and cultivating that is
gameplay. *Falsifier:* grudge trajectory tracks regime (grasping souls escalate on return;
practiced souls release — MAINTAIN/CONCEDE-style judge verdicts) vs a mood-only null; the player
can *earn* release through conduct, not dialogue flags. *Honesty:* design-review against WB patent
US 10,926,179 (runs to ~2036) before anything ships; the mechanism is emergent-substrate rather
than authored promotion tables, but the check is owed. *Port:* the marquee player-facing system —
"enemies that remember, and can be freed."

**P3. Virtue witnessed, not scored — Ultima IV, corrected by the lore machinery.**
*What:* no karma meter. The player's conduct writes cetanā-residue (K2), conduct-expectations, and
legends; the **only feedback channel is the town's behaviour** — prices, gossip, who defends you,
who comes to your funeral before the wheel turns (P1). And because reputations ride the validated
mutation-prone lore channel, **the town can be wrong about you** — unfair legends at the
documented §5.16 mutation rate, appealable only through more conduct. *Falsifier:* a judge (or
playtesters) recovers the player's actual conduct history from town behaviour alone above chance;
false-reputation events occur and are *survivable* (the C3 injustice drama, with the player in
it). *Port:* the "town has opinions about you" system RESEARCH C3 promised, completed by making
the player its subject.

---

## 4. What I would run, in order

1. **K1 (instrumented chain)** — mostly staging of existing machinery; localizes every existing
   dharma claim; the inspector view everything else reads from.
2. **K4 (care light cone)** — a small behavioural instrument with a big theory behind it; feeds E5.
3. **K2 (karma-conditioned rebirth)** — the samsara headline and the first-mover claim; needs K1's
   cetanā ledger; **welfare-gated** (collective floor logic at the wheel before it runs hot).
4. **P1 + P3 (player in the wheel + witnessed virtue)** — the game-port pair; both ride shipped
   mechanisms (wheel, lore, stakes); P1 first because `inhabit.py --samsara` is the open seam.
5. **K3 (temporal depth)** — when expectation work resumes; K5 opportunistically alongside any
   regime re-run. **P2 last** — it's the most marketable and the most legally encumbered; build it
   on the C3 reputation layer after P3 proves the channel.

*Sources:* Abhidhamma process-model: [neuroscience–Abhidhamma mapping](https://www.intechopen.com/chapters/1220314), [the cognitive process (citta-vīthi)](https://buddho.org/the-cognitive-process-according-to-the-abhidhamma/), [Theravāda Abhidhamma overview](https://en.wikipedia.org/wiki/Theravada_Abhidhamma);
active-inference meditation: [Laukkonen & Slagter, *From many to (n)one*](https://www.sciencedirect.com/science/article/pii/S014976342100261X), [Prest et al., *Selfing without a self*](https://meditation.mgh.harvard.edu/files/Prest_26_OSF.pdf), [computational phenomenology of advanced meditation](https://meditation.mgh.harvard.edu/files/Tal_26_NeuroscienceAndBiobehavioralReviews.pdf);
[Contemplative Artificial Intelligence](https://arxiv.org/abs/2504.15125); [Doctor, Witkowski, Solomonova, Duane & Levin, *Biology, Buddhism, and AI: Care as the Driver of Intelligence*](https://www.mdpi.com/1099-4300/24/5/710) and the [Apparent Selves project](https://apparentselves.org/blog/biology-buddhism-and-ai-care-as-a-driver-of-intelligence/);
the twelve links: [Encyclopedia of Buddhism](https://encyclopediaofbuddhism.org/wiki/Twelve_links_of_dependent_origination), [Pratītyasamutpāda](https://en.wikipedia.org/wiki/Prat%C4%ABtyasamutp%C4%81da);
game craft: [Nemesis patent context](https://www.eastgateip.com/warner-brothers-patents-shadow-of-mordors-nemesis-system/) and [retrospectives](https://gamedayroundup.com/nemesis-system-explained/); [Ultima IV virtues](https://wiki.ultimacodex.com/wiki/Virtues_in_Ultima_IV) and [its morality design](https://lycaeum.ultimacodex.com/morality/); [death-as-progression in roguelikes](https://www.gamedeveloper.com/design/death-in-gaming-roguelikes-and-quot-rogue-legacy-quot-) and [Hades' loop](https://www.pastemagazine.com/games/hades/how-hades-rescues-the-roguelike-from-its-own-limit).
Companion docs: `RESEARCH.md` (C1–C13; C3 reputation is P3's base), `EVOLUTION.md` (E1 genome stays orthogonal to K2's karma; E5 consumes K4), `METHODS.md` (every falsifier above runs through its stats + judge discipline), `FINDINGS.md` §5.5/§5.9/§5.15/§5.16, `DHARMA.md`.*
