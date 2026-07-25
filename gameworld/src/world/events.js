// THE DEED FEED — what happened, told as something a townsperson could repeat.
//
// This is the lab's event bus (world/events.py, DESIGN.md §4.1) arriving in the game, and
// it closes the gap the whole voice layer had: the shooter and the town ran side by side
// without touching. You could sack a camp, fell a boss, come home bleeding — and the town
// talked about seed phrases. Everything it knew about you, you TYPED. From here, deeds
// flow as utterance-shaped entries — the universal currency — and the town's ears drink
// from the same pipe everything else will.
//
// THE SHAPE IS THE DESIGN: every entry is already in TOWNSFOLK LANGUAGE ("a vale camp
// burned, two rings out"), never in game-speak ("SACK_EVENT ring=2 faction=1"), because
// every planned consumer speaks language: the town's gossip (now), the factions' war-cry
// corpora (next), the night's consolidation when sleep arrives. Translating at the source
// means no consumer ever needs a translation table.
//
// CURSORS, not consumption: readers keep their own place with since(), so three systems
// can drink the same events without stealing them from each other. The feed itself is
// deliberately TRANSIENT — undelivered news dies with the page, because news goes stale;
// what a town has already heard lives in its heard[] memory, which persists and decays
// on its own schedule.

const CAP = 64;

export class EventFeed {
  constructor() {
    this.events = [];      // { id, text, weight }
    this.nextId = 1;
  }

  /** Something happened. `text` in townsfolk language; `weight` is how loudly it will
   *  sit in whatever memory receives it (heard-scale: ~1.2 murmur-worthy, ~2.2 a boss). */
  push(text, weight = 1.4) {
    this.events.push({ id: this.nextId++, text, weight });
    if (this.events.length > CAP) this.events.splice(0, this.events.length - CAP);
  }

  /** Everything after `cursor`, and the new cursor. Each reader holds its own. */
  since(cursor = 0) {
    const events = this.events.filter((e) => e.id > cursor);
    return { events, cursor: events.length ? events[events.length - 1].id : cursor };
  }
}

/** The one feed. Systems import the instance, not the class — one world, one history. */
export const deeds = new EventFeed();
