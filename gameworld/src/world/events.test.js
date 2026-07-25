// Tripwires for the deed feed — the pipe every voice consumer drinks from.

import { test } from "node:test";
import assert from "node:assert/strict";
import { EventFeed, deeds } from "./events.js";
import { TownVoice } from "../town/voice.js";

test("cursors: two readers drink the same history without stealing from each other", () => {
  const f = new EventFeed();
  f.push("a camp burned", 2);
  f.push("a beast fell", 2.2);
  const a = f.since(0), b = f.since(0);
  assert.equal(a.events.length, 2);
  assert.equal(b.events.length, 2, "reading is not consuming");
  const a2 = f.since(a.cursor);
  assert.equal(a2.events.length, 0, "a reader never re-hears its own past");
  f.push("the wanderer swore to Iron", 2);
  assert.equal(f.since(a.cursor).events.length, 1, "...but hears what is new");
});

test("the cap forgets the oldest — news goes stale, it does not accumulate", () => {
  const f = new EventFeed();
  for (let i = 0; i < 200; i++) f.push(`event ${i}`);
  assert.ok(f.events.length <= 64);
  assert.equal(f.events[f.events.length - 1].text, "event 199");
});

test("deeds reach the town's ears: news lands in heard[] at its own weight", () => {
  const tv = new TownVoice({ state: "offline", info: null }, { list: [] }, {}, null);
  tv.newsCursor = deeds.since(0).cursor;          // start past anything other tests pushed
  deeds.push("the wanderer sacked a vale camp out in the Reach", 2.0);
  deeds.push("the wanderer felled a great beast out in the Fallows", 2.2);
  tv.catchUpOnNews();
  const texts = tv.heard.map((h) => h.text);
  assert.ok(texts.includes("the wanderer sacked a vale camp out in the Reach"));
  assert.ok(texts.includes("the wanderer felled a great beast out in the Fallows"));
  assert.equal(tv.heard.find((h) => h.text.includes("beast")).weight, 2.2,
    "a boss outranks gossip in the memory");
  assert.equal(tv.news, "the wanderer felled a great beast out in the Fallows",
    "the freshest deed becomes the standing topic");
  assert.equal(tv.newsSlots, 2, "...for the next couple of murmurs");
  // And catching up twice never re-hears the same news.
  const n = tv.heard.length;
  tv.catchUpOnNews();
  assert.equal(tv.heard.length, n);
});
