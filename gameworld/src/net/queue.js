// THE VOICE QUEUE — one owner for the one model thread.
//
// The lab runs a single model on a single thread, and by the end of one day THREE systems
// were competing for it: the town's ambient murmurs, the player's chat, and the war-cry
// baker. They negotiated PAIRWISE — each knowing the names of the others — through five
// hand-rolled mechanisms: a holdWhile predicate naming its betters, two separate `busy`
// flags, interrupt() calls wired by hand in main, generation counters, and a Promise.race
// deadline. Five mechanisms, one job, and coupling that grew with the square of the
// speakers. That is why one underlying bug surfaced three times in three costumes: the
// chat that wedged, the town that went mute after sleeping, the hails that never baked.
// None of those files was wrong. The coordination simply lived nowhere.
//
// So it lives here. Everyone asks the queue instead of calling the bridge, and the queue
// enforces four rules in one testable place:
//
//   ONE IN FLIGHT      the model is serial, so pretending otherwise only builds a backlog
//   HIGHER PREEMPTS    a player waiting outranks a town musing outranks a cache warming
//   EQUAL/LOWER QUEUES  ...and is dropped rather than banked when the queue is already deep
//   STALE IS DISCARDED  a preempted result must never arrive late and speak over the thing
//                       that preempted it — the "she mumbled at me while I waited" bug
//
// Adding a speaker is now one line — declare a priority — instead of an edit to every
// speaker that already exists. Santāna is the reason this exists before she does.

/**
 * Who outranks whom. The numbers are ordinal; only their order carries meaning.
 * The ordering is the design, and it reads as a sentence: a person waiting on a reply
 * beats a companion, who beats a town going to sleep, who beats a town musing aloud, who
 * beats a cache quietly warming itself for later.
 */
export const PRIORITY = {
  chat: 100,        // the player typed something and is watching a cursor blink
  santana: 80,      // Stage 2's companion — a companion who lags is not a companion
  consolidate: 60,  // sleep is a transition the player is sitting through
  ambient: 40,      // a villager musing; it can always wait a beat
  bake: 10,         // pure prefetch. yields to everything, always
};

const MAX_QUEUED = 3;   // past this the eldest waiting request is dropped, not banked

export class VoiceQueue {
  constructor() {
    this.running = null;    // { priority, tag, ctrl, gen }
    this.waiting = [];      // [{ priority, tag, run, resolve, gen }]
    this.gen = 0;           // stamps every request; a stale generation never speaks
    this.stats = { done: 0, preempted: 0, dropped: 0 };
  }

  /** Is anything using the model right now? (For HUD/debug only — never for logic; the
   *  whole point is that callers no longer reason about each other's state.) */
  get busy() { return !!this.running || this.waiting.length > 0; }

  /**
   * Ask for the model.
   * @param priority one of PRIORITY
   * @param tag      short label, for the transcript when contention is being debugged
   * @param run      (signal) => Promise — MUST pass the signal to the bridge call, or
   *                 preemption can only discard the result rather than free the thread
   * @returns the run()'s value, or null if preempted, dropped, or failed. Every caller
   *          already copes with null, because the bridge has always been allowed to fail.
   */
  request({ priority = PRIORITY.ambient, tag = "?", run }) {
    return new Promise((resolve) => {
      const job = { priority, tag, run, resolve, gen: ++this.gen };

      // Nothing running: go now.
      if (!this.running) return this.start(job);

      // Something lower-ranked is running: take the thread off it. Its own promise
      // resolves null and its generation is already spent, so a late result is ignored.
      if (priority > this.running.priority) {
        this.preempt(`${tag} outranks ${this.running.tag}`);
        return this.start(job);
      }

      // Otherwise wait your turn — highest priority first, FIFO within a priority.
      this.waiting.push(job);
      this.waiting.sort((a, b) => (b.priority - a.priority) || (a.gen - b.gen));
      while (this.waiting.length > MAX_QUEUED) {
        // Drop the LEAST important waiter, not the newest: a backlog of ambient musings
        // is worth less than the newest one, and worth nothing beside a queued chat.
        const cut = this.waiting.pop();
        this.stats.dropped++;
        cut.resolve(null);
      }
      return undefined;
    });
  }

  start(job) {
    const ctrl = new AbortController();
    this.running = { priority: job.priority, tag: job.tag, ctrl, gen: job.gen, job };
    const mine = job.gen;
    Promise.resolve()
      .then(() => job.run(ctrl.signal))
      .then(
        (res) => this.finish(mine, job, res),
        () => this.finish(mine, job, null),      // a failed call is a quiet one, as ever
      );
  }

  /** Settle a job, but ONLY if it is still the one we are waiting on. A preempted job's
   *  result lands here too, late, and must be thrown away rather than returned. */
  finish(gen, job, res) {
    if (this.running?.gen !== gen) {
      job.resolve(null);       // preempted: whatever it produced is stale by definition
      return;
    }
    this.running = null;
    this.stats.done++;
    job.resolve(res);
    this.pump();
  }

  preempt(why) {
    const r = this.running;
    if (!r) return;
    this.running = null;
    this.stats.preempted++;
    try { r.ctrl.abort(); } catch { /* already settled */ }
    // SETTLE THE CALLER OURSELVES, now — do not wait for the aborted work to notice.
    // Relying on the job to resolve its own promise means a run() that ignores its signal
    // (or a server that keeps generating) leaves its caller awaiting forever, holding the
    // busy flag it took the lock with. That is the exact wedge this class exists to
    // prevent, and it was sitting inside the preventer until a test drove it out.
    // finish() is generation-guarded, so a late result changes nothing.
    r.job.resolve(null);
    console.info(`[queue] preempted ${r.tag} — ${why}`);
  }

  pump() {
    if (this.running || !this.waiting.length) return;
    this.start(this.waiting.shift());
  }

  /**
   * The player did something that makes every pending voice irrelevant — pressed G,
   * opened a menu, died. Everything in flight is abandoned and everything waiting is
   * dropped. Replaces the hand-wired interrupt() calls that main used to make one by one.
   */
  clear(why = "cleared") {
    this.preempt(why);
    for (const job of this.waiting.splice(0)) {
      this.stats.dropped++;
      job.resolve(null);
    }
  }
}

/** The one queue. Systems import the instance — one model, one owner. */
export const voiceQueue = new VoiceQueue();
