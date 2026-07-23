# GEAR.md — the stat & equipment redesign

*Researched 2026-07-23 against WoW Classic (vanilla 1.12). The goal is to replace our pile of
ad-hoc multipliers (`0.9^armor`, `tanh` speed, `sqrt` dash, uncapped `1+gearDmg`) with ONE
consistent, familiar model where **gear shows plain additive numbers** and the diminishing
returns live in the FORMULAS, not in the stats. Sources at the bottom.*

## 0. The one insight that pays for everything

**WoW gear shows raw numbers (+20 Stamina, +15 Haste), but the game converts them through
diminishing-returns formulas.** The player reads clean, addable numbers; balance stays sane
automatically; and no stat needs a hand-tuned cap because the *formula* is the cap.

This single idea answers every request at once:
- "numbers, not times" → stats are flat integers you add across your gear
- "diminishing returns" (asked for on armour, speed, dash already) → built into each formula
- "level requirement so you can't grind low bosses to be OP" → the armour/AP formulas make
  low-level numbers worthless at depth *on their own*, and `reqLevel` finishes the job
- "MMO health" → Stamina→HP is the exact lever, on both the player and the mobs

The three DR hacks we already shipped (armour `0.9^n`, speed `tanh`, dash `sqrt`) were all
reinventing this. They collapse into the model below.

## 1. The stat model (all additive integers on gear)

### Primary attributes (WoW's four, re-pointed at THIS game — decided 2026-07-23)
| attribute | what it does here | formula |
|---|---|---|
| **Strength** | GLOBAL damage — gun, grenade AND spells | `+STR_DMG% per point` into the global bucket |
| **Agility** | movement SPEED and DASH distance | feeds the speed input and the dash, like Lighten/Vault do |
| **Stamina** | health, the MMO way | `maxHP = 100 + STAM_HP × stamina` (`STAM_HP≈8`) |
| **Armor** | damage reduction | `DR = armor / (armor + ARMOR_K + ARMOR_PER_TIER × attackerTier)` — DR built in, worth less at depth |

**Every piece of gear also carries Armor**, like WoW — a chestpiece is Armor + attributes,
boots are Armor + attributes, and total mitigation is the sum across your kit. Strength
replaces WoW's melee "attack power": there is no melee here, so STR just means "you hit
harder with everything."

### Damage buckets (the four you asked for, additive %)
Final damage of any hit = `base × levelMult × (1 + globalDmg + typeDmg)`:
- **Global Damage** — every source (Strength pours into this bucket)
- **Gun Damage** — guns only · **Spell Damage** — abilities only · **Grenade Damage** — grenade only

So "Agility + damage" gear = Agility + Global (more overall damage AND speed); "spell +
global" = Spell + Global; a gun piece rolls Gun Damage. Every piece is a bundle of these plus
its Armor.

### Secondary (rating → % via `rating / (rating + K)`, DR baked in)
| stat | what it does |
|---|---|
| **Attack Speed** | gun fire rate |
| **Haste** | ability cooldowns + heal channel |
| **Reload** | reload time |

Every secondary uses the same shape: `pct = rating / (rating + STAT_K)`, so the first points
are strong, later points diminish, and it can never reach 100%. One helper, `ratingPct()`,
serves all — the same way `ringPressure()` serves the difficulty ramp.

### Weapons — DONE (2026-07-23)
The Weapon slot shipped ahead of the rest: `WEAPONS` in config, a generalised `gun.js` that
runs any of them, mouse-wheel switching, and the smith selling them (`once`, so you own not
stack). Rifle (starter) · Scattergun (9 pellets, short, pump) · Longshot (one-shot, huge
damage, map-range, semi) · Ripper (low damage, huge belt). Guns ride `dmgMult` today; they
move onto Gun Damage + Global in the damage step.

### The armour curve, concretely
`DR = armor / (armor + 300 + 60 × tier)` (our tiers are smaller than WoW's 60 levels):
- 150 armour vs tier 0 → 33% · vs tier 5 → 20% · vs tier 8 → 16%
- Same number, worth roughly HALF as much eight rings out. That is the anti-grind engine
  before `reqLevel` ever fires: ring-1 armour cannot carry you to ring 8.

## 2. Equipment: SLOTS, not stacks (the big change)

Today the shop sells **permanent stacking upgrades** (buy Sharpen forever). That is what lets
you grind a low boss into godhood, and it is the opposite of the WoW model. The redesign:

**A small set of gear SLOTS, one item each. A better item REPLACES the one in its slot.**

Proposed slots (kept few on purpose — this is a shooter, not a paperdoll):
| slot | primary stats it favours |
|---|---|
| **Weapon** | Power, Attack Speed |
| **Armor** | Armor, Stamina |
| **Trinket** | Spell Power, Haste |
| **Boots** | Move Speed, Stamina |

Four slots, each holding one item, is enough for meaningful choices without an inventory
screen becoming the game. (The four ability slots stay exactly as they are — abilities are
not gear.)

## 3. Item level & the level requirement

Every item carries two numbers:
- **ilvl** — how strong its stats roll. Scales with the ring it comes from.
- **reqLevel** — you cannot buy OR equip it below this. Shown greyed-out with "requires L{n}".

The anti-grind loop, self-closing:
```
   item power  ∝  ilvl
   ilvl available  ∝  ring (vendor stock + boss drops)
   surviving a ring  ∝  your level + current gear
   your level  ∝  killing things, which needs gear, which needs ring…
```
Grinding ring-1 bosses only ever drops ring-1 ilvl gear — capped in power and made near
worthless at depth by the armour/Power formulas. To get stronger gear you must go deeper; to
survive deeper you must already be leveled. Power and depth stay welded together. `reqLevel`
is the hard backstop; the formulas are the soft one that makes it feel earned rather than
arbitrary.

## 4. Vendors & drops, in the new model

- **Vendors** stock the gear band of their ring, at matching reqLevels. A city vendor stocks
  one band higher (the reward for reaching the city). No more infinite stacking buys — you
  buy an *upgrade* for a slot, and the old piece is sold back for part of its cost.
- **Boss relics BECOME gear** — same "walk over to claim", but a drop is now an equippable
  piece with ilvl, reqLevel, and rolled stats (the affix-style roller we already wrote in
  `relics.js` becomes the stat roller). A drop you can't use yet reads "requires L{n}" and
  waits, which is itself a reason to keep leveling.
- **Regular mobs drop gear too, rarely** — a small per-kill chance (order of ~1–2%, higher
  for elites, scaled by ring) to drop a piece of that ring's ilvl band. This is the MMO
  trickle that makes *any* kill worth a glance at the ground, without competing with bosses:
  boss drops are guaranteed and roll higher, mob drops are a rare bonus that mostly rolls
  common/low but occasionally surprises. Same roller, lower ilvl and worse rarity odds. It
  respects the guard dead-zone and the anti-farm rules exactly like points do — a guard kill
  or a kill you didn't earn drops nothing.

## 5. MMO health, both sides

- **Player HP** = `100 + 8 × Stamina`. Bare = 100; a stamina-geared deep build = several
  hundred. Health becomes a gear decision, not a constant.
- **Mob HP** goes up substantially and counts come down — the tier-0 pass (85 HP, 44 mobs)
  is the first step. Target feel: a normal mob is a 2–4 second fight, an elite ~+40% HP and
  damage (WoW's outdoor-elite guideline, nudged up), a rare/champion more. Fewer, meatier,
  readable — MMO pacing instead of bullet-hell.

## 6. Slices — each done when its gate is answered in PLAY, not when it compiles

### G1 — the stat spine ⏱ ~2 days
`ratingPct()` + the armour formula + Stamina→HP + Power/SpellPower coefficients. Port the
EXISTING stats onto it (armour number instead of `0.9^n`, etc.) with the shop unchanged.
- **Gate:** every current effect still works, now driven by integer stats through the formulas.

### G2 — equipment slots ⏱ ~4 days
Four slots, equip/replace, a simple paperdoll on the pause screen. Shop sells slot items.
- **Gate:** buying a better Weapon visibly swaps the old one out; no stacking remains.

### G3 — ilvl + reqLevel gating ⏱ ~2 days
Items carry ilvl/reqLevel; vendors gate stock; equip refuses under-level.
- **Gate:** you cannot equip a ring-5 drop at level 3, and grinding ring-1 stops making you
  stronger.

### G4 — boss drops as gear ⏱ ~2 days
`relics.js` roller emits equippable pieces with stats/ilvl/reqLevel.
- **Gate:** a boss kill drops a piece you either equip now or level toward.

### G5 — the MMO-health rebalance ⏱ ~3 days
Mob HP up, counts down, elite/rare bands, per-mob TTK to 2–4s. Retune the ramps against the
new baselines.
- **Gate:** a fight is a *fight* — a few seconds, readable — not a click that deletes a mob
  or a wall you empty a magazine into.

### G6 — first-level tuning ✅ (started)
Tier 0 at 44 mobs / 85 HP each. Folds into G5's final numbers.
- **Gate:** a brand-new player clears the Commons without being overwhelmed.

Sources:
[Vanilla armor & DR formula](https://wowpedia.fandom.com/wiki/Armor) ·
[Damage reduction formula](https://wowwiki-archive.fandom.com/wiki/Damage_reduction) ·
[Attack power (AP/14)](https://vanilla-wow-archive.fandom.com/wiki/Attack_power) ·
[Attributes: Stamina→HP, Int→Mana](https://vanilla-wow-archive.fandom.com/wiki/Attributes) ·
[Primary & secondary stats overview](https://blizzardwatch.com/2019/06/17/wow-classic-primary-secondary-stats-attributes/) ·
[Elite creature (~+30% outdoor guideline)](https://vanilla-wow-archive.fandom.com/wiki/Elite_creature) ·
[Stats & attributes (Wowhead)](https://www.wowhead.com/classic/guide/classic-wow-stats-and-attributes-overview)
