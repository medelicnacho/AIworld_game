// Shorten the music loops WITHOUT re-encoding them.
//
// An MP3 is a chain of self-contained frames, each holding a fixed slice of time. So a track
// can be shortened by simply writing out the first N seconds' worth of whole frames and
// stopping — no decoder, no encoder, no quality loss at all, and no tooling to install.
//
// Why bother: the soundtrack is ~97% of what a visitor downloads, and it is big because the
// tracks are LONG, not because they sound good. The game loops them forever, so a player
// hears the first minute or two and never reaches the rest. Shipping eight minutes of a track
// nobody gets to the end of is paying a loading screen for nothing.
//
// The one thing this CANNOT do is choose a musical loop point. It cuts at the nearest frame
// to the target, wherever that lands in the bar — so a seam may be audible each time a loop
// comes round. Fixing that properly is an ears job: pick the point, or fade the tail with a
// real audio tool. This gets the size down today; the polish is a separate pass.
//
//   node tools/trim_audio.mjs [--apply]
// Without --apply it only reports what it would do.

import { readFileSync, writeFileSync, readdirSync, existsSync } from "fs";
import { join } from "path";

const SRC = "audio_originals";
const OUT = "public/audio";

// Seconds to keep per track. Beds can be shorter than melodic layers — you notice a repeat
// far less in a texture than in a tune.
const KEEP = {
  "warsound.mp3": 60,
  "warsound2.mp3": 60,
  "radio.mp3": 0,          // already short; leave it alone
  "donkeybeats.mp3": 90,
  "chillax.mp3": 90,
  "popsound.mp3": 0,       // a 2s effect, not a loop
  "killerspacetuna.mp3": 0,
};

const BITRATE = {
  1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],   // MPEG1 L3
  2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],       // MPEG2/2.5 L3
};
const SAMPLERATE = {
  3: [44100, 48000, 32000, 0],     // MPEG1
  2: [22050, 24000, 16000, 0],     // MPEG2
  0: [11025, 12000, 8000, 0],      // MPEG2.5
};

/** Where the audio starts — past any ID3v2 tag on the front. */
function audioStart(b) {
  if (b.length > 10 && b.toString("latin1", 0, 3) === "ID3") {
    const size = ((b[6] & 0x7f) << 21) | ((b[7] & 0x7f) << 14) | ((b[8] & 0x7f) << 7) | (b[9] & 0x7f);
    return 10 + size;
  }
  return 0;
}

/** Decode one frame header at `i`, or null if that is not a valid frame. */
function frameAt(b, i) {
  if (i + 4 > b.length) return null;
  if (b[i] !== 0xff || (b[i + 1] & 0xe0) !== 0xe0) return null;
  const verBits = (b[i + 1] >> 3) & 0x3;        // 3 = MPEG1, 2 = MPEG2, 0 = MPEG2.5
  const layer = (b[i + 1] >> 1) & 0x3;          // 1 = Layer III
  if (verBits === 1 || layer !== 1) return null;
  const brIdx = (b[i + 2] >> 4) & 0xf;
  const srIdx = (b[i + 2] >> 2) & 0x3;
  if (brIdx === 0 || brIdx === 15 || srIdx === 3) return null;
  const kbps = BITRATE[verBits === 3 ? 1 : 2][brIdx];
  const sr = SAMPLERATE[verBits][srIdx];
  if (!kbps || !sr) return null;
  const pad = (b[i + 2] >> 1) & 0x1;
  // MPEG1 Layer III carries 1152 samples per frame; MPEG2/2.5 carry 576.
  const samples = verBits === 3 ? 1152 : 576;
  const size = Math.floor((samples / 8) * kbps * 1000 / sr) + pad;
  return size > 4 ? { size, dur: samples / sr, kbps, sr } : null;
}

/** True if this frame is a Xing/Info header — metadata about a length we are about to change. */
function isXing(b, i, size) {
  const tag = b.toString("latin1", i + 4, Math.min(i + size, b.length));
  return tag.includes("Xing") || tag.includes("Info");
}

const apply = process.argv.includes("--apply");
let before = 0, after = 0;

for (const name of readdirSync(SRC).filter((f) => f.endsWith(".mp3"))) {
  const src = join(SRC, name);
  const buf = readFileSync(src);
  const keep = KEEP[name] ?? 0;
  before += buf.length;

  if (!keep) {
    after += buf.length;
    console.log(`${name.padEnd(24)} ${(buf.length / 1048576).toFixed(1).padStart(5)} MB  — left alone`);
    continue;
  }

  let i = audioStart(buf);
  const out = [];
  let secs = 0, dropped = 0;
  while (i < buf.length) {
    const f = frameAt(buf, i);
    if (!f) { i++; continue; }                       // resync past junk
    // A stale Xing header would advertise the OLD duration of a file we just shortened, which
    // can make a browser's loop land in the wrong place. Drop it; players do fine without.
    if (out.length === 0 && isXing(buf, i, f.size)) { i += f.size; dropped++; continue; }
    if (secs + f.dur > keep) break;
    out.push(buf.subarray(i, i + f.size));
    secs += f.dur;
    i += f.size;
  }

  const result = Buffer.concat(out);
  after += result.length;
  const pct = (100 - (result.length / buf.length) * 100).toFixed(0);
  console.log(`${name.padEnd(24)} ${(buf.length / 1048576).toFixed(1).padStart(5)} MB -> `
    + `${(result.length / 1048576).toFixed(1).padStart(5)} MB  (${secs.toFixed(1)}s, -${pct}%`
    + `${dropped ? ", dropped Xing" : ""})`);
  if (apply) writeFileSync(join(OUT, name), result);
}

console.log(`\ntotal ${(before / 1048576).toFixed(1)} MB -> ${(after / 1048576).toFixed(1)} MB`);
if (!apply) console.log("(dry run — re-run with --apply to write)");
