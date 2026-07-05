# BRIDGE.md — a living town inside a browser game

*(Companion to `PORT.md`. PORT is the long-term contract for a full in-engine port; the
BRIDGE is the way to build gameplay against the real, running Python substrate **today**
— and its protocol doubles as the API spec the eventual port must honour.)*

## The shape

The towns run as they always have (the persistent runners). The same little server that
serves the cockpit also speaks the bridge: **Server-Sent Events out, JSON POSTs in**,
CORS open, zero dependencies on either side. A browser game is a *renderer and an action
layer* over a town that is genuinely living.

```
your JS/TS game  ──(EventSource)──▶  every speech/birth/death, live
                 ◀──(fetch POST)──   deeds, promises, chat — landing on REAL mechanisms
```

## Ten lines to a living town

```html
<script src="http://127.0.0.1:8766/bridge.js"></script>
<script>
  const town = new TownBridge("http://127.0.0.1:8766");
  town.onEvent(e => render(e));                    // speech (with real hearers), deaths, births
  const s = await town.state();                     // souls: positions, moods, bonds, stage
  await town.deed("kindness", someSoulId);          // witnessed by everyone in earshot
  await town.pledge(soulId, "I will bring what you need", 300);
  await town.fulfill(soulId);                       // ...or let the clock break your word
  const army = await town.muster("player", 0.4);    // join/refuse/oppose + speakable reasons
  const chat = await town.say(soulId, "hello");     // clear-voiced chat, remembered
</script>
```

Try it live right now: **`http://127.0.0.1:8766/bridge/demo`**.

## The protocol

| Route | Method | What |
|---|---|---|
| `/bridge/events` | GET (SSE) | `{kind:"speak", who, text, to:[hearer ids]}` · `{kind:"death"|"birth", who}` · `{kind:"heartbeat", tick, souls, season, night}` every ~2s |
| `/bridge/state` | GET | full snapshot: souls `{id,name,x,y,mood,stage,asleep,bonds,drift}`, season/hour, her vitals |
| `/bridge/soul?id=` | GET | one soul's insides: mood/wellbeing/stores bars, genome dials, bonds with wounds, last memories **with provenance tags**, its grown mind's raw stirring |
| `/bridge/muster?leader=&danger=` | GET | the armies screen: join/refuse/oppose lists + a speakable reason per soul |
| `/bridge/act` | POST | see below — the only ways a game may touch the town |
| `/say` | POST | `{text, target: soul_id}` → clear-voiced reply; lands in the soul's real memory and bond |

### `/bridge/act` — actions land on validated mechanisms only

```jsonc
{"kind": "deed",    "act": "kindness"|"meanness", "near": "s12"}  // witnessed by earshot
{"kind": "pledge",  "to": "s12", "text": "...", "due_ticks": 300} // a word given
{"kind": "fulfill", "to": "s12"}                                  // a word kept
```

- **deed** → `agent/witness.py` (verdict 5/5×4): everyone present shifts its expectation
  of the actor, some will *tell* it, and the telling gossips to souls who never saw it.
  `near` limits witnesses to earshot of that soul; omit it and the deed is public.
- **pledge/fulfill** → `agent/pledge.py` (§5.20): kept words warm a town slowly; a broken
  one is *always* a betrayal, and the wound gossips.
- There is deliberately no generic "set state" call. If a game needs a new verb, it gets
  a new **validated** road first — that's the whole point of this repo.

Actor identity: pass `actor`/`actor_name` to play as someone other than `"player"`.
Reputation, bonds, wounds, and muster all key on that id.

## What the game can build from this, today

- **Reputation gameplay**: be kind near the well, watch `/bridge/events` carry the
  gossip, watch `soul()` inspectors turn warm — or plant your cruelty and watch an
  innocent's name darken two rings away.
- **Recruitment**: `muster()` *is* the army screen — with reasons you can print over
  heads ("she stands with you — their trust runs deep"; "he is too worn for this").
  Loyalty has a measured price: one season of kept words ≠ soldiers; two might.
- **A living backdrop**: weather fronts of mood (measured real — FINDINGS §5.24),
  neighbourhoods that self-organise (§5.26), legends that outlive their witnesses.

## Deployment honesty

Prototyping/LAN: run the town, point the game at `127.0.0.1:8766`, done. A **shipped**
browser game needs either (a) the Python substrate hosted server-side — one town serving
visiting players is the natural shape of this world anyway — or (b) the full JS port,
which must pass the replication gate in `PORT.md` before it earns features. The bridge
forecloses neither; it makes the collaboration real now, and every route above is a line
in the eventual port's spec.
