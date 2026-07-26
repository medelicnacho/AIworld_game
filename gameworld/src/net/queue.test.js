// Tripwires for the voice queue — the scheduler that replaced five hand-rolled
// coordination mechanisms across three files. Every rule here was a bug first.

import { test } from "node:test";
import assert from "node:assert/strict";
import { VoiceQueue, PRIORITY } from "./queue.js";

/** A request that resolves when you tell it to, and records if it was aborted. */
function deferred(value = "done") {
  const d = { aborted: false };
  d.run = (signal) => new Promise((res) => {
    d.finish = () => res(value);
    signal?.addEventListener("abort", () => { d.aborted = true; });
  });
  return d;
}
const tick = () => new Promise((r) => setTimeout(r, 0));

test("one in flight: a second request of equal rank waits its turn", async () => {
  const q = new VoiceQueue();
  const a = deferred("a"), b = deferred("b");
  const pa = q.request({ priority: PRIORITY.ambient, tag: "a", run: a.run });
  const pb = q.request({ priority: PRIORITY.ambient, tag: "b", run: b.run });
  await tick();
  assert.ok(!b.finish, "the second request has not started");
  a.finish(); assert.equal(await pa, "a");
  await tick();
  assert.ok(b.finish, "and starts only when the first is done");
  b.finish(); assert.equal(await pb, "b");
});

test("a chat PREEMPTS a bake — the wedge, the mute town and the starvation, in one rule", async () => {
  const q = new VoiceQueue();
  const bake = deferred("bake"), chat = deferred("chat");
  const pBake = q.request({ priority: PRIORITY.bake, tag: "bake", run: bake.run });
  await tick();
  const pChat = q.request({ priority: PRIORITY.chat, tag: "chat", run: chat.run });
  await tick();
  assert.ok(bake.aborted, "the bake's signal is aborted so the thread frees");
  assert.equal(await pBake, null, "and its caller is told it got nothing");
  chat.finish();
  assert.equal(await pChat, "chat", "the player's reply goes through immediately");
});

test("a preempted result arriving LATE is discarded, never spoken", async () => {
  // This is the "she mumbled her queued line at me while I waited" bug, as a rule.
  const q = new VoiceQueue();
  const slow = deferred("stale"), chat = deferred("fresh");
  const pSlow = q.request({ priority: PRIORITY.ambient, tag: "ambient", run: slow.run });
  await tick();
  q.request({ priority: PRIORITY.chat, tag: "chat", run: chat.run });
  await tick();
  slow.finish();                       // the server finished anyway, after the preempt
  assert.equal(await pSlow, null, "a stale line resolves null and is never played");
});

test("lower priority never preempts: a bake cannot interrupt a person", async () => {
  const q = new VoiceQueue();
  const chat = deferred("chat"), bake = deferred("bake");
  const pChat = q.request({ priority: PRIORITY.chat, tag: "chat", run: chat.run });
  await tick();
  q.request({ priority: PRIORITY.bake, tag: "bake", run: bake.run });
  await tick();
  assert.ok(!chat.aborted, "the player's request is untouched");
  chat.finish();
  assert.equal(await pChat, "chat");
});

test("the backlog is bounded — the least important waiter is dropped, not banked", async () => {
  const q = new VoiceQueue();
  const held = deferred("held");
  q.request({ priority: PRIORITY.chat, tag: "held", run: held.run });
  await tick();
  const drops = [];
  for (let i = 0; i < 6; i++) {
    drops.push(q.request({ priority: PRIORITY.bake, tag: `bake${i}`, run: deferred().run }));
  }
  assert.ok(q.waiting.length <= 3, "a queue of stale intentions is worse than none");
  assert.equal(await drops[drops.length - 1], null, "the surplus resolves null, never hangs");
});

test("clear() abandons everything — one call where main used to wire interrupts by hand", async () => {
  const q = new VoiceQueue();
  const a = deferred(), b = deferred();
  const pa = q.request({ priority: PRIORITY.ambient, tag: "a", run: a.run });
  await tick();
  const pb = q.request({ priority: PRIORITY.ambient, tag: "b", run: b.run });
  q.clear("test");
  assert.equal(await pa, null);
  assert.equal(await pb, null);
  assert.ok(a.aborted, "the in-flight one is actually aborted");
  assert.equal(q.busy, false, "and the queue is genuinely idle afterwards");
});

test("a thrown request settles null rather than wedging the queue forever", async () => {
  const q = new VoiceQueue();
  const p = q.request({ priority: PRIORITY.ambient, tag: "boom", run: () => { throw new Error("x"); } });
  assert.equal(await p, null);
  assert.equal(q.busy, false, "a failure must never hold the thread — the original wedge");
});
