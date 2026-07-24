// The chosen difficulty, held in one place so the three choke points that read it — incoming
// damage, outgoing damage, and the death penalty — can never fall out of step with each
// other. It is a whole-run setting, picked on the start screen and carried in the save; there
// is no mid-game switch, because "turn it down when it gets hard" is exactly the tension the
// hard game is made of.

import { DIFFICULTY, DEFAULT_DIFFICULTY } from "../config.js";

let currentId = DEFAULT_DIFFICULTY;

export function setDifficulty(id) {
  if (DIFFICULTY[id]) currentId = id;
  return currentId;
}

export function difficultyId() { return currentId; }

/** The active preset — the object the choke points multiply by. Never null. */
export function diff() {
  return DIFFICULTY[currentId] || DIFFICULTY[DEFAULT_DIFFICULTY];
}
