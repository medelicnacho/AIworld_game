// DAY AND NIGHT — the world's clock, and nothing else.
//
// This module owns TIME: where in the cycle we are, how much daylight that means, and the
// jump to dawn that sleeping takes. It deliberately owns no lighting, no colours, no
// meshes — main.js reads daylight() and drives the sky, the same seam as everything else
// (sim state is not render state). Night is visual-only for now; its real cargo is what
// SLEEP does to the town's memory (town/voice.js consolidate()), and later it is when the
// factions' war-cries are baked for the next day.

import { DAYNIGHT } from "../config.js";

export class DayNight {
  constructor() {
    this.t = DAYNIGHT.edge;    // a fresh world wakes at morning, just past dawn
  }

  get cycle() { return DAYNIGHT.dayLen + DAYNIGHT.nightLen; }

  advance(dt) {
    this.t = (this.t + dt) % this.cycle;
  }

  get isNight() { return this.t >= DAYNIGHT.dayLen; }

  /**
   * How much day there is right now, 0..1, with soft ramps at both ends: a ~90s dawn
   * from the end of night into morning, and a ~90s dusk at the end of day. Everything
   * visual lerps off this one number.
   */
  daylight() {
    const { dayLen, edge } = DAYNIGHT;
    const t = this.t;
    if (t < edge) return t / edge;                                // dawn
    if (t < dayLen - edge) return 1;                              // day
    if (t < dayLen) return (dayLen - t) / edge;                   // dusk
    return 0;                                                     // night
  }

  /** Sleep. The night is skipped; the caller owns everything that happens IN the skip
   *  (consolidation, healing, the save) — this only moves the clock. */
  skipToDawn() {
    this.t = 0;
  }

  /** For the HUD: "day" / "dusk" / "night" / "dawn", the word a townsperson would use. */
  phase() {
    const d = this.daylight();
    if (d >= 1) return "day";
    if (d <= 0) return "night";
    return this.t < DAYNIGHT.edge ? "dawn" : "dusk";   // the only two ramps there are
  }
}
