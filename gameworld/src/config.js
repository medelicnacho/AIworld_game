// Tunables in one place. Anything a designer would want to feel out belongs here.

export const WORLD_SEED = 1337;

/**
 * THE LAB — the local LLM + Piper bridge, and everything that rides on it.
 *
 * A DEV TOY, NOT A FEATURE OF THE GAME. It talks to http://127.0.0.1:8777, which exists on
 * exactly one machine in the world, so it has never run for a single player and never will:
 * a page served from itch cannot reach a stranger's localhost, and would not be allowed to
 * over HTTPS if it could. Every build ever shipped has quietly been the no-bridge build.
 *
 * That is now a DECISION rather than an accident of `import.meta.env.DEV`. The reasoning, so
 * it does not have to be rediscovered:
 *
 *   IT FIGHTS THE PILLAR. This is a parkour frontier shooter — movement, height, firefights.
 *   Walking into town to wait for a model to finish thinking is not a change of pace, it is a
 *   full stop, and no amount of tuning makes a twitch game and a chat interface share a rhythm.
 *
 *   IT IS A PER-PLAYER COST, FOREVER. Hosted inference bills on every conversation between
 *   every player and every villager. That is a business decision wearing a feature's clothes,
 *   and the wrong one to make before the game is known to be fun.
 *
 *   IT WAS NEVER GATED ON FUN. Verticality earned its stages by being played and enjoyed
 *   first. The talking villagers never had that test, while carrying more machinery than
 *   anything else in the game: a bridge, a queue, a scheduler, per-town memory, decay.
 *
 * WHAT IS KEPT is the part that was always the good part: towns REMEMBER. Who you are, what
 * you did, fading honestly while you are away. That lives in town/voice.js and town/chat.js
 * and needs no model — the model was only ever one way of reading it aloud.
 *
 * Set ?lab=0 in dev to play exactly what a player gets.
 */
export const LAB = {
  enabled: (() => {
    // A built copy never reaches for it. This is the whole of the shipping decision.
    if (!import.meta.env?.DEV) return false;
    if (typeof location === "undefined") return false;   // node, running the tests
    return new URLSearchParams(location.search).get("lab") !== "0";
  })(),
};

// VOICE.md V1 — the murmuring starter town. Every number here is the silence budget: the
// point of the feature is how RARELY it fires. Local-only by nature (the bridge refuses to
// connect in built copies), so none of this exists for an itch player.
export const VOICE = {
  enabled: true,
  // WHICH voice a villager gets lives in town/voice.js's CAST table (per ROLE — a smith
  // sounds like a smith in every town, the way trade colours already work). Models are
  // always passed explicitly: the bridge's server-side default is lessac, and lessac is
  // Santāna's (VOICE.md D7).
  // The cadence, tuned by ear against both extremes. The original silence budget
  // (34/18 — a murmur every ~34-52s) played as "way too slow": the town read as mute and
  // the feature as broken. The test cadence (5/4) read as a lobby. This sits between,
  // nearer the fast end — a voice every ~12-20s: often enough that the town is audibly
  // inhabited while you shop, rare enough that two villagers never talk over each other.
  cooldown: 12,        // seconds between murmurs, plus up to `jitter` more
  jitter: 8,           // one voice every ~12-20s
  firstDelay: 3,       // settle-in: entering town never triggers an instant greeting
  range: 26,           // a villager this close to you may speak; further is stage-whisper
  volume: 0.6,          // pulled down from 0.85: a villager was out-shouting the soundtrack
  // How far a town voice carries before it fades to nothing. Deliberately not much more
  // than `range`: a villager at the edge of earshot should be a murmur you lean toward,
  // and one at your elbow should be clear. The falloff is quadratic, so 45 puts the far
  // edge (26) near a fifth volume and someone beside you near full.
  reach: 45,
  // EVERY audible line is the model's (decided in play: voiced raw Markov sounded like
  // what it is). The chain still runs underneath — it feeds each prompt as "drifting
  // thoughts" and sets the speaker's MOOD — but it is subconscious now: nobody hears it
  // raw, and without ollama the town is simply quiet.
  lineWords: 14,       // short — a person muttering at a workbench, not giving a speech
  // THE CONVERSATION. A spoken line hangs in the air for convoWindow seconds; while it
  // does, the next speaker is a DIFFERENT villager prompted to ANSWER it. convoMax caps
  // the exchange — three turns is a chat between people working, five is a radio play.
  // Heard lines join the drift sources at heardWeight (above seed weight: what was said
  // out loud looms larger than the town's standing preoccupations), FIFO-capped at
  // heardMax so old talk fades — and through the drift they move the town's MOOD.
  convoWindow: 45,
  convoMax: 3,
  heardWeight: 1.6,
  heardMax: 12,
};

// WAR-CRIES — the factions' voices on the field. Every constraint here is a lesson the
// town's voice already paid for, applied to combat:
//   EVENT-DRIVEN, never ambient: a cry fires on aggro, on a charge wind-up, on a garrison
//   arming — moments that carry information. A cry IS a telegraph; chatter is noise.
//   PRE-BAKED, never live: synthesis happens in town, where it's quiet; combat plays
//   cached WAVs instantly. Piper mid-fight would stutter the exact frames that kill you.
//   BUDGETED: cooldowns per battlefield and per faction. One scream is a scream; five is
//   a playground.
export const WARCRY = {
  enabled: true,
  cachePerFaction: 8,     // baked cries kept warm per war-colour — overlap needs variety
  // 7, not 2: the model has ONE thread, and a baker firing every 2s occupied it for
  // minutes — every town murmur queued behind the arsenal until it timed out, and the
  // town went MUTE while its armies rehearsed. The gaps are where the town speaks.
  bakeEvery: 7,
  // RETUNED for the warband feel (asked for in play): the first budget produced a lone
  // soloist every nine seconds; a war party is a WALL of voices. Lead cries still gate on
  // cooldowns — what overlaps is the ECHO: packmates answering the lead, staggered.
  globalCd: 1.2,          // a breath between LEAD cries on the battlefield
  factionCd: 3,           // and per faction, so two armies still answer each other
  aggroChance: 0.8,       // a pack noticing you usually announces it
  chargeChance: 0.9,      // a charge nearly always screams — it is the audio telegraph
  // THE WARBAND: when a lead cry fires, up to this many nearby packmates answer it,
  // staggered and overlapping, each throat pitched slightly differently. This is where
  // "a group of warriors" lives — one voice raises the cry, the band takes it up.
  echoes: 2,
  echoDelayMin: 0.35,
  echoDelayMax: 1.4,
  echoVolume: 0.9,
  volume: 0.8,          // was 1.1 — see VOICE.volume; the whole voice bus came down
  // HAILS — the same machinery pointed the other way: YOUR colour's soldiers greet you.
  // "Hail, soldier." "Well met, warrior." A camp that only screams at enemies and says
  // nothing to its own reads as a texture; one that knows you're on its side reads as an
  // army you belong to. One hail per mob per long cooldown, one per battlefield window,
  // spoken at natural pitch — a greeting is a voice, not a monster.
  // WHAT YOUR OWN COLOURS SAY when you walk past — authored here beside the taunts, so
  // both halves of the war's vocabulary are edited in one place. The model still writes
  // extra clan-flavoured greetings on later bakes; these are the floor, and the floor is
  // what actually gets heard most.
  hails: [
    "Hail, comrade!",
    "Brother in arms!",
    "Greetings, soldier!",
    "We unite as one!",
    "Hail, soldier!",
    "Let's destroy the enemy!",
    "Let's fight in glory!",
    "Hail, friend!",
    "Well met, warrior!",
    "The colours hold!",
    "Good hunting out there!",
  ],
  hailPerFaction: 8,      // raised with the list: four kept ten of them unheard
  hailChance: 0.7,
  hailCd: 14,             // battlefield-wide gap between hails
  hailMobCd: 150,         // one soldier greets you once, then holds his peace a while
  hailRange: 11,          // walk this close to an ally before he bothers
  hailVolume: 0.7,
  // A battlefield carries further than a town square, but not forever: at 95 a cry from
  // across the fight is faint and one in your face is loud, which is what makes a scream
  // usable as a telegraph — you can hear how CLOSE the thing that is charging you is.
  reach: 95,
  hailReach: 45,        // a greeting is spoken to you, not broadcast
  // THE TAUNT FLOOR — hardcoded lines synthesized ONCE per session (piper only, no model),
  // then always loaded: an army is never silent again while the fancy lines bake, and
  // combat mixes these randomly between the generated cries (tauntChance). Authored HERE
  // on purpose: this is the game's trash-talk register, and re-toning it is one edit.
  // One shared voice; per-faction playbackRate at play time makes three throats of it.
  taunts: [
    "I will kill you!",
    "You're going to die!",
    "Evil fatso!",
    "Your mom is lame!",
    "You like doodoo!",
    "I poo and pee on your face!",
    "You're a homosapien!",
    "Go back to stupid school!",
    "I am going to own you, noob!",
    "Super ultra power boost!",
    "You smell of poo!",
    "I'm gonna put some dirt in your eye!",
    "I know kung fu!",
    "Run home to your mommy!",
    "Crawl back to your mommy!",
    "I'm going to wipe that smug look off your face!",
    "I'm going to beat you silly!",
    "You fat oaf!",
    "I will destroy your hopes and dreams!",
    "I am going to kill you!",
    "You will die slowly!",
    "I will inflict agonizing pain on you!",
    "Your mom is fat!",
    "I slept with your mother!",
    "You will taste my fist!",
    "While you were partying, I trained in the blade!",
    "I have two hundred and twenty-three confirmed kills!",
  ],
  tauntChance: 0.5,       // odds a cry slot uses the floor instead of a baked line
  // EVERY CLAN TAUNTS IN ITS OWN THROAT: taunts bake per faction through the same
  // `voices` table the war-cries use, so Iron's "I know kung fu" is the northern growl
  // and Vale's is the quick high one — three armies, never one actor doing all the parts.
  // Costs 3x the synths, which persistence makes a one-time price (they wake from disk).
  tauntBakeEvery: 2,      // piper-only: no model contention, so it can fill briskly
  // BATTLE CHATTER — the voices that keep going once a fight is UNDERWAY. The first cut
  // only spoke at the three punchy moments (noticing you, winding up, arming), so a long
  // fight fell silent after its opening line. These two kinds fill the middle:
  //   fight  a mob hunting YOU, mid-brawl, running its mouth
  //   war    two clans fighting EACH OTHER — the faction war, finally audible
  // Both sit UNDER the telegraph cries in priority: they share the one-voice-at-a-time
  // gate so nothing turns to mush, but they never set the faction cooldown, so a charge
  // scream is never blocked by chatter. And no warband echoes — an echo is for the
  // dramatic beat, not for the tenth line of a scrap.
  // RETUNED to be RELENTLESS (asked for in play): the first pass spoke once every few
  // seconds and a brawl still felt half-mute. A fight should be a wall of shouting — so
  // every fighter runs its mouth on a short personal clock, and the only battlefield
  // limit is a narrow gap that keeps voices from landing on the same instant. With six
  // mobs on you that lands roughly two lines a second, overlapping, from six directions.
  // FOUR SPEAKER SLOTS, owned by MOBS — not a cap on sounds, a cap on who may speak at
  // all (asked for in play: "only four mobs can be talking at a time"). Every fighter in
  // earshot asks to speak on a short personal clock, which in a giant fight is hundreds
  // of asks a second all running the voice machinery just to be refused at the end; with
  // slots, all but four are turned away at the front door for the price of a Map peek.
  // Four is also where the EAR tops out: past four overlapping voices "many warriors"
  // becomes mush, and every extra line only spends mix headroom drowning the ones already
  // talking. Chatter, hails and echoes need a slot; the TELEGRAPH cries (charge, aggro,
  // arm) walk past the door — a scream that exists to be dodged is information, it is
  // already rationed by its own cooldowns, and information does not queue.
  maxSpeakers: 4,
  chatterGap: 0.5,        // battlefield-wide minimum between chatter lines
  fightCd: 0.6,           // in-combat lines can come almost back to back
  fightChance: 0.9,
  fightMobCd: 3.5,        // one fighter shuts up only this long after speaking
  warCd: 1.6,             // clan-vs-clan is rarer than shouting at YOU, but still steady
  warChance: 0.8,
  warMobCd: 5,
  warHearRange: 70,       // clan brawls further than this stay a rumour, not a soundtrack
  // ALL THREE CLANS SHOUT IN VALE'S VOICE (decided by ear, 2026-07-25). Iron's northern
  // growl was hard to follow and its American replacement was no better; the quick high
  // one carries over gunfire and stays legible at speed, so the whole war speaks with it.
  // The rows stay per-faction so any clan can be handed its own throat back in one line —
  // identical rows simply mean one army's worth of voice, everywhere.
  voices: {
    0: { model: "en_US-amy-medium.onnx", pace: 0.8, rate: 1.12 },   // Iron
    1: { model: "en_US-amy-medium.onnx", pace: 0.8, rate: 1.12 },   // Ash
    2: { model: "en_US-amy-medium.onnx", pace: 0.8, rate: 1.12 },   // Vale
  },
  // Bump whenever `voices` changes. Baked WAVs are keyed by it, so audio in the browser's
  // store that was spoken in a retired throat is swept instead of played — otherwise a
  // voice change is inaudible until the caches happen to roll over.
  // 3 — bumped when "the green wind cuts" was cut from the Vale seeds. Removing a line from
  // the source stops it being GENERATED again, but audio baked from it in an earlier session
  // is sitting in IndexedDB and would go on being shouted for ever. loadPersisted sweeps
  // anything stamped with an older revision, so this is the one switch that retires a voice.
  voiceRev: 3,
};

// DAY AND NIGHT — 20 minutes each, with soft ~90s dawns and dusks. Night is visual only
// for now (the frontier does not yet get meaner in the dark); its real cargo is SLEEP:
// resting in a safe town skips to dawn, and the skip is when the town CONSOLIDATES — the
// day's heard talk is digested into standing lore (see town/voice.js consolidate()).
export const DAYNIGHT = {
  dayLen: 1200,
  nightLen: 1200,
  edge: 90,               // seconds of dawn/dusk ramp
};

// Shown in the corner of the screen, always. This exists because a build-staleness bug wore
// a gameplay bug's clothes for hours: the packaged dist/ (and an itch upload of it) kept the
// old garrison-ambush code long after src/ was fixed, and every report of "still broken" was
// actually "still running the old copy". A tag on screen ends that class of confusion — if
// the screen doesn't say this exact string, the fix being tested isn't in the build being
// played. Bump it whenever behaviour changes meaningfully.
export const BUILD_TAG = "garrison-v4 07-25";

// THE NAME, in one place. It lived twice — the <h1> on the character screen and the <title> in
// index.html — which is how a game ends up called two things at once, and the tab is the copy
// nobody looks at while they work. index.html still carries it as plain text because a tab needs
// a name before any script runs; main.js sets document.title from THIS the moment it loads, so
// this string is the one that wins and the HTML is only the bootstrap.
export const GAME_TITLE = "War Parkour";

// DIFFICULTY. Chosen once on the start screen and remembered in the save. HARD is the harshest
// the frontier gets — everything out there hits TWICE as hard as the raw numbers say, the level
// is lost on death, and every telegraph is unforgiving. EASY exists for someone who has never
// held a mouse-look shooter: it turns every dial toward mercy at ONE place each, so the game
// stays the same game, just far softer.
//
//   incoming    every point of damage you take, at the one choke point (damagePlayer). The
//               single biggest lever, and it covers mobs, meteors, the beam, burning ground
//               and your own grenades without any of them knowing it exists. Above 1.0 it
//               AMPLIFIES (hard doubles the hurt); below 1.0 it softens (easy).
//   playerDmg   everything you deal, folded into dmgMult where levels and gear already live.
//   wipeOnDeath a death ENDS the run — levels, gear, standing, all of it. Hardcore only.
//   grace       scales the early-game GRACE bonus, so easy stays kind well past level 12.
export const DIFFICULTY = {
  hard: {
    id: "hard", label: "Hard",
    blurb: "The frontier at its meanest — once you have found your feet. It eases you "
      + "through the first levels, then takes the cushion away. Dying costs only the walk back.",
    // incoming 1.4: mobs (and meteors, beams, burning ground) hit 40% harder than baseline,
    // down from DOUBLE.
    //
    // Two changes, and the second matters more than the first.
    //
    // The FLAT number came down because 2.0 was not a difficulty, it was a filter. Every
    // telegraph in the game is tuned to be readable and survivable once; doubling all of them
    // means the first mistake you make in any fight is often the last, and a player learning
    // the telegraphs is exactly the player who cannot yet avoid them. 1.4 still bites — the
    // deep rings are unforgiving — without making "I have not learned this yet" fatal.
    //
    // GRACE 2.2 is the real answer to "hard is brutal at the start". Grace is the early-game
    // cushion that fades out by level 12 (see GRACE): more damage dealt, much less taken, and
    // it was set to 1.0 here — meaning hard got the standard fade while ALSO taking double
    // damage, so the opening hours were by far the worst part of the mode. Stretching it to
    // easy's 2.2 keeps the cushion in place through the levels where you are still learning
    // what everything does, and it is GONE by the time you are deep enough for it to matter.
    // The mode ends up hard where hard should be hard: out in the rings, not in the tutorial.
    incoming: 1.4, playerDmg: 1.0, grace: 2.2,
  },
  hardcore: {
    id: "hardcore", label: "Hardcore",
    blurb: "One life. The same fight as Hard, but when you fall you lose all of it — "
      + "levels, gear, standing — and begin again with nothing.",
    // THE SAME FIGHT AS HARD, and it follows hard wherever hard goes — there is a test that
    // holds these two numbers equal on purpose. What changes is what a death MEANS: not a
    // setback, an ending. A stake you accept once, at the start, instead of a levy collected
    // every time you slip — which is the difference between tension and attrition.
    //
    // It inherits the gentler opening too, and that is right rather than a compromise: a mode
    // whose whole weight rests on one life should not spend that life on the levels where you
    // are still learning which telegraphs kill you.
    incoming: 1.4, playerDmg: 1.0, grace: 2.2, wipeOnDeath: true,
  },
  easy: {
    id: "easy", label: "Easy",
    blurb: "For a first shooter. You take far less damage and hit harder.",
    // Unchanged in ABSOLUTE terms (0.34) so a first-timer's experience is exactly as gentle as
    // before — it just reads as an even bigger gap now that hard hits twice as hard.
    incoming: 0.34, playerDmg: 1.6, grace: 2.2,
  },
};
export const DEFAULT_DIFFICULTY = "hard";

// The admin/testing panel is behind this code. It is a SPEED BUMP, not a lock — the code
// ships inside the game and anyone determined can read it out. That is fine, because the
// thing it is defending against is not an attacker, it is a curious playtester: the first
// instinct on seeing a button marked "admin" is to press it, and one who hands themselves
// level 50 and every spell can no longer tell you whether your opening hour is too hard.
// It only has to be enough friction that nobody wanders in by accident.
export const ADMIN_CODE = "4711";

// Chunk dimensions. Y is the full world height — the world is read-only (D1), so a
// chunk is a column, never a stack, and there is no vertical streaming to write.
export const CHUNK_X = 16;
// The world's CEILING — how much sky there is, not how tall the land gets. Raised from 80
// once islands existed: the land had always used almost all of it (TERRAIN_CAP below), so
// there was nowhere for an archipelago to climb into, and "higher and higher islands" was a
// request the world had no room to answer. Costs memory per chunk and nothing else, because
// fillChunk skips the empty air between the land and the sky rather than walking it.
/**
 * HOW TALL A LOADED CHUNK IS — a WINDOW on the world now, not the height of it.
 *
 * The world itself is unbounded upward: the sky repeats every RELIEF.deckH forever. What is
 * bounded is how much of it is resident, and this is that. The window SLIDES with you (see
 * WINDOW_STEP), so climbing does not run out of world — it just moves what is loaded.
 *
 * The reason that costs nothing visually: fog closes at VIEW_RADIUS * CHUNK_X * 0.95, which
 * is about 106 blocks. A 256-tall window is already more than twice what you can see in any
 * direction, so the part of it you give up at the bottom when you climb was invisible anyway.
 *
 * A window rather than vertical slabs because slabs multiply DRAW CALLS — the same disc of
 * columns cut into thirds is three times the meshes — and draw call overhead, not vertex
 * count, is what this renderer is short of.
 */
/**
 * DUNGEONS — instanced, and instanced almost for free.
 *
 * The world is a pure function of coordinates and a seed (D1) read through one door (D15), so
 * an instance is not a parallel world with its own store, collider and mesher. It is a
 * DIFFERENT FUNCTION behind the same door. Nothing downstream — movement, sight, the streamer,
 * the mesher — ever knew where blocks came from, so nothing downstream has to be told.
 *
 * It sits at the GATE'S OWN x,z, high above the terrain rather than off in some far corner of
 * the coordinate space. That is not a detail: tierAt() is a function of x,z, so a dungeon in
 * the mouth of a ring-9 mountain is automatically a ring-9 dungeon, and its mobs, loot and
 * pressure all scale from where you found it without a single special case.
 */
/**
 * MOUNTAINS — one landmark per ring, and the only thing in the world you can navigate by.
 *
 * Every other feature here is texture: hills, terraces, spires, chasms, islands. They make
 * ground interesting to cross and are deliberately everywhere, which means none of them tells
 * you WHERE you are. A mountain does. It is visible from most of a ring, it is in the same
 * place every time, and it is the only structure in the game a player can point at.
 *
 * That is why the dungeon gates are cut into them rather than scattered on open ground: an
 * entrance you can only find by following a compass arrow is a waypoint, but an entrance in
 * the side of the mountain you can already see is a place.
 *
 * They are allowed to break TERRAIN_CAP. The cap exists to stop ordinary land eating the sky
 * the islands live in; a mountain that respected it would be a hill.
 */
export const MOUNTAIN = {
  radius: 105,          // how wide its skirt is, in blocks
  height: 96,           // how far its peak stands above the land it grows out of
  cap: 168,             // mountains may reach this high — well past TERRAIN_CAP, under the sky
  sharp: 2.1,           // >1 pulls the dome into a peak instead of a bun
  rough: 9,             // noise on the slopes, so it is rock and not a cone
  // 0.62 puts the door on the FLANK, where the dome still has real height under it and the
  // slope above reads as a wall of rock you are walking into. At 0.86 it stood out on the
  // skirt where the mountain lifts the ground by about two feet — a door in a field.
  gateOut: 0.62,        // where on the slope the gate sits: 0 = peak, 1 = the very edge
  gateFlat: 13,         // radius of level ground at the gate's mouth, so you can stand there
};

/**
 * THE VOID FLOOR — how far you can fall before the world gives up on you.
 *
 * There is no bottom to this world. blockAt answers AIR below y=0 and an instance is a box
 * floating in nothing, so falling out of either one is not a long drop, it is a permanent
 * one: you keep accelerating, nothing ever catches you, and the only exit is deleting the
 * character. That is the worst failure state a game can have, because it does not even look
 * like a failure — it looks like the game stopped.
 *
 * So there is a line, and crossing it kills you like anything else would. Death is a state
 * the game already knows how to recover from: a screen, a button, and a town.
 *
 * Deliberately FAR below anything reachable. This is a backstop for bugs and for falling out
 * of a dungeon, not a hazard to design around — nothing you can walk off should ever put you
 * near it, and if this ever fires during ordinary play the bug is elsewhere.
 */
export const VOID = {
  belowWorld: -30,      // outdoors: the land starts at y=1, so this is unreachable by falling
  belowRoom: 70,        // inside an instance: this far under its floor
};

export const DUNGEON = {
  y: 400,               // the altitude band an instance occupies — clear of any terrain
  height: 9,            // floor to ceiling, inside a room
  wall: 3,              // rock around the room; anything past it is simply void
  roomMin: 14,          // half-extent of the room, before the seed varies it
  roomSpan: 9,          // ...and how much the seed may add
  enterRange: 4,        // how close to a gate you must be for it to offer itself
  // How far in from the doorway you arrive. Far enough that the door is a place you go
  // BACK to rather than one you are already standing on, close enough that you can see it
  // from where you land and never have to wonder where the way out went.
  entryStep: 7,
  doorW: 3,             // half-width of the doorway recess, along the wall
  doorH: 6,             // and how tall it stands off the floor

  // THE GARRISON. A dungeon is a FIXED NUMBER of defenders, not a tap.
  //
  // Borrowing the open-world spawner gave the room three separate wrongnesses at once, all
  // from the same cause: the frontier is an endless place with a war on it, and a room is
  // neither. Camps rolled their own colours, so the dungeon's own occupants fought each other
  // while you watched; the population budget refilled for ever, so there was no such thing as
  // clearing it; and none of it was written down, so a reload handed back everything you had
  // already killed. A dungeon you cannot finish is a corridor with a respawn timer.
  garrison: [16, 34],   // how many hold it, rolled from the gate's own seed
  garrisonPack: [3, 6], // ...arriving in knots this size, so it is a series of fights
};

export const CHUNK_Y = 256;
/**
 * How far you climb before the window follows. Coarse on purpose: crossing a step re-streams
 * every loaded chunk, so it wants to be rare, and half the window means you are never nearer
 * than 64 blocks to an edge you cannot see anyway.
 */
export const WINDOW_STEP = 128;
// ...and how tall the LAND may get, which is a separate question and must stay where it was.
// Clamping terrain to the ceiling instead would have grown mountains into the new sky the
// moment it was raised.
export const TERRAIN_CAP = 78;
export const CHUNK_Z = 16;

export const VIEW_RADIUS = 7;          // chunks loaded around the player
// Build budget — keeps frame time flat while streaming. Dropped to 1 once the sky filled up:
// a chunk with an archipelago over it costs ~1.1ms to fill and ~5ms to mesh, so two of them
// was 12ms of a 16ms frame and streaming started to hitch exactly when you were moving fast
// enough to need it. One chunk a frame is still sixty a second.
export const CHUNKS_PER_FRAME = 1;

// Terrain shape
export const SEA_LEVEL = 24;
export const BASE_HEIGHT = 30;
/**
 * VERTICAL DRAMA — the land you have to read instead of walk.
 *
 * The terrain was gentle fbm on a voxel grid, which meant it never rose more than one block
 * at a time anywhere in the world. Beautiful, and completely flat as far as your legs were
 * concerned: nothing to jump over, nothing to jump between, nothing to climb. Relief is the
 * part that disagrees with you.
 *
 * The numbers come from what the player's body can actually do, which is a short jump and a
 * FAST run: 1.36 blocks of lift, but six blocks of ground covered in one sprinting leap. So
 * the parkour here is horizontal. You clear gaps by committing to a run-up, not by climbing
 * — and a ledge above double-jump height is not a challenge, it is a wall you route around.
 * That is the lesson: the land has levels, and choosing your level is choosing your fight.
 *
 * It GROWS with the ring, like everything else visible about difficulty (D8). The Commons
 * stays walkable because it is where movement is taught, and by the deep rings you are
 * reading terrain as carefully as you read a mob pack. Nobody has to be told this happened;
 * you can see it on the horizon.
 */
export const RELIEF = {
  fullTier: 4,          // sky islands still ramp from nothing at spawn to full by this ring
  // THE GROUND, though, does not wait for a whole ring. Rings are 260 blocks wide and widen
  // from there, so a tier-based ramp meant the first ridge appeared a four-minute walk out and
  // the terrain only became itself a kilometre and a half from spawn — the player met the game
  // as a field. These are a plain radius instead.
  //
  // AND THEY START ALMOST AT YOUR FEET. A settlement levels its own ground (see heightRaw) and
  // eases the wild land back in across its margin, so there is nothing to protect out here:
  // the spawn town stays a flat, buildable plain no matter how violent the country around it
  // gets. Which means the first thing the game can show you is the thing the game IS — walk
  // out of the gate and you are already climbing, rather than crossing a field first to find
  // out whether this one has any terrain in it.
  startR: 30,           // relief begins essentially at the town's edge
  spanR: 190,           // and is fully itself before you have left the first ring
  // TERRACES. Heights snap toward multiples of this, which turns smooth hills into stepped
  // plateaus with real edges. The effective step is terraceStep * terraceMix ≈ 2 blocks —
  // deliberately just above a single jump and just under a double, so every ledge asks for
  // the second jump you would otherwise only spend on emergencies.
  terraceStep: 3,
  terraceMix: 0.7,
  // SPIRES. Ridged noise: buttes and fingers of rock standing above the plateau. High ground
  // that has to be earned, and a landmark you can navigate by.
  spireScale: 0.03,
  spireWidth: 0.42,     // smaller = narrower, meaner spires
  spireSharp: 2.0,
  spireAmp: 15,
  // CHASMS. Long winding cuts, sized against that six-block leap: most are a committed jump,
  // some are a detour. There is no fall damage, so a chasm costs you time and position and
  // never your run — which is what makes trying the jump the right instinct.
  chasmScale: 0.008,
  chasmWidth: 0.13,
  chasmDepth: 12,

  /**
   * ISLANDS — rock in the sky, and the reason the world stops being a surface.
   *
   * Built from a 2D mask with a vertical profile rather than 3D noise: where the mask is
   * strong there is a lens of stone, thicker at the middle and tapering to nothing at the
   * rim. That keeps worldgen at ONE evaluation per column, which is the whole reason this is
   * affordable — true 3D density would put chunk builds from ~1ms to ~80ms.
   *
   * They are only worth having because things live on them. An island nothing can reach is
   * just a roof over an exploit; an island with a garrison on it and fliers circling it is a
   * place, and taking it is a decision.
   */
  island: {
    // AN ARCHIPELAGO, not a continent. The first version was one big smooth lens per ~480
    // units, which made islands both rare and — because the strength ramp never approached
    // 1 — paper thin. You could stand three thousand metres out with a 15% chance of one
    // being in sight. A sky worth climbing into is a scatter of small platforms at different
    // heights that you cross by jumping, so: small cells, a low threshold, and every island
    // taking its altitude from its OWN field.
    fromTier: 1,        // the Commons keeps a clean sky; everywhere else has them
    scale: 0.031,       // ~32-unit cells — stepping stones, not landmasses
    thresh: 0.16,       // measured against the real mask spread (p50 is ~0, p90 ~0.35)
    // THE SKY THICKENS AS IT CLIMBS. The threshold is relaxed by up to this much at the top
    // of the altitude range, so the high air is crowded and the low air stays open. It is
    // subtracted, never added, so nothing gets rarer down low — the ceiling gets busier
    // rather than the floor emptying out. Climbing should feel like going somewhere.
    threshHigh: 0.16,
    // SHAPED BY THE SAME PIPELINE AS THE LAND, not merely bumpy. Hill noise alone gave a
    // rolling top with a couple of terrace steps on it — nothing like the ground, which gets
    // hills AND ridged spires AND the terrace quantisation, and reads as steep because of the
    // last two. An island runs through all three, with its own seeds so it is a piece of the
    // same world rather than a copy of the bit underneath it.
    roughness: 7,       // hills
    spireAmp: 13,       // the steep part — ridged, exactly as RELIEF.spire does it
    underRough: 4,      // a torn bottom, not a machined one
    peak: 0.55,         // mask value at which an island is full size — reachable, unlike 1.0
    minThick: 2,        // even the smallest is something you can land on
    thick: 7,
    // Altitude comes from an ABSOLUTE field, not from the land below, or an island would
    // warp to follow the terrain under it instead of being flat.
    // ALTITUDE IN TWO PARTS, and the split is the whole trick.
    //
    // "Go up super high" and "let me jump between them" pull in opposite directions, because
    // the spread of altitudes IS the size of the step from one island to the next. One field
    // cannot do both: widen it and the sky climbs but every hop becomes impossible; narrow
    // it and everything is reachable and flat.
    //
    // So: a very SLOW field decides what altitude this whole REGION of sky sits at — walk far
    // enough and the archipelago climbs from just overhead to near the ceiling of the world —
    // and a faster, much smaller field jitters neighbours around that. Local hops stay short
    // while the sky as a whole goes a long way up.
    levelSlowScale: 0.0016,   // ~600-unit regions
    // The ceiling is 176 now and the land stops at 78, so the sky has ~90 blocks of room to
    // climb through. This is what actually makes islands go "higher and higher" — the old 34
    // could not, because there was nowhere above y73 to put one.
    levelSlowSpan: 88,
    // Noise is bell-shaped, so left alone most regions of sky sit at MIDDLE altitude and the
    // count actually falls off above y60 — the opposite of climbing into a thickening sky.
    // Below 1 this skews regions upward, so the high air is where most of the world is.
    levelBias: 0.62,
    levelScale: 0.006,
    levelSpan: 9,             // the part that becomes the step between neighbours
    baseY: 34,
    gapMin: 5,          // clearance under it; where the land rises into that, no island
  },

  /**
   * PEBBLES — the stepping stones. Small enough to be a landing rather than a place, sharing
   * the islands' altitude field so they sit between the big platforms instead of in their own
   * unrelated sky. These are what make a chain crossable: the gap between two real islands is
   * usually too far, and a pebble in the middle turns it into two jumps.
   */
  /**
   * WEDGES — the smallest thing in the sky, and the only one with a SLOPE.
   *
   * Everything else up there is a slab: flat on top, so hopping between them is a series of
   * identical landings and the only question is whether you cleared the gap. A wedge answers
   * a second question — WHICH END do you land on — because its top ramps, so the high lip is
   * a launch and the low lip is a landing, and a chain of them reads as a run rather than a
   * sequence of pads.
   *
   * Deliberately LOW and deliberately in deck 0 only. They are the rung between standing on
   * the ground and reaching the first real platform, which is exactly where the sky was
   * thinnest — up high there is already plenty to stand on, and a slope you cannot see the
   * top of is a hazard rather than a step.
   *
   * The ramp comes from a smooth field sampled at wedge SIZE: across a blob a few blocks
   * wide, smooth noise is near enough a straight line, so the top of one tilts like a plank
   * without any of them needing to know where its own edges are.
   */
  wedge: {
    scale: 0.115,       // small blobs — a few blocks across, not a platform
    thresh: 0.26,       // common enough to chain, sparse enough to be a choice
    above: 7,           // the lowest one sits this far over the land
    rise: 30,           // ...and they scatter up to this much higher
    thin: 1,            // the thin end is one block: a lip, not a pillar
    ramp: 5,            // how far the top climbs from thin end to thick
    // MATCHED TO THE BLOB, not to the landscape. At 0.05 the tilt field turned over roughly
    // every twenty blocks while a wedge is about eight across, so each one caught a slice of
    // the ramp and rose under a block end to end — a slope you cannot see is a flat pad with
    // extra maths. Near the mask's own scale, one blob spans most of one swing of the field,
    // which is what makes a low lip and a high lip on the SAME wedge.
    tiltScale: 0.1,     // the ramp's direction and length
  },
  pebble: {
    scale: 0.085,       // ~12-unit cells — a few strides across
    // 0.18 against a field whose median is 0.00 and 90th percentile 0.42 — about 30% of
    // columns, roughly double what 0.34 gave. Measured before it was chosen this time.
    thresh: 0.18,
    threshHigh: 0.16,   // same climb-and-thicken rule as the platforms
    peak: 0.62,
    thick: 3,
    // AND THEY HANG LOW. Sharing the platforms' altitude exactly put every pebble in the
    // same layer as the thing it was supposed to be a route TO, which is useless: you could
    // hop along the top of the sky but never get up there. Each pebble drops by its own
    // amount, so the air between the land and the platforms fills in at every level and the
    // climb becomes a staircase you can find rather than one you have to already be on.
    // Widened with the sky: stepping stones have to fill a ~90-block climb now, not a
    // ~20-block one, or the ladder loses its middle rungs and the top of the sky becomes
    // somewhere you can see and never reach.
    dropMin: 4,
    dropSpan: 60,
    dropScale: 0.022,   // its own field — neighbouring pebbles sit at different depths
  },

  /**
   * MOTES — the smallest tier, a few blocks across and barely thicker than a step. Not places
   * and not really landings: these are the things you touch for a fraction of a second on the
   * way somewhere, and they are what turns a climb of ninety blocks from a series of gaps
   * into a route. Scattered through the ENTIRE height of the sky rather than a layer of it,
   * so wherever you are there is usually something just above you.
   */
  mote: {
    scale: 0.095,       // ~10-unit cells — a landing you aim at, not one you thread
    thresh: 0.11,       // everywhere: these are the rungs, and a ladder needs a lot of them
    thick: 3,           // enough to read as a step from a distance; still not a floor
    // ...AND FAR MORE OF THEM UP HIGH. Its own relaxation rather than the pebbles', and a big
    // one: the top of a deck is where the platforms thin out and the gaps between them get
    // long, so it is exactly where a route needs the most rungs. Down low the big islands
    // already carry you.
    threshHigh: 0.34,
    dropScale: 0.055,
    // HOW HARD THE HEIGHT FIELD IS STRETCHED to cover a deck, top to bottom.
    //
    // fbm almost never reaches its own extremes — the tails are rare — so mapping it straight
    // onto a deck's height piles motes into the middle and thins them out at BOTH ends. The
    // ends are the deck boundaries, which is the one place a ladder cannot have a missing
    // rung, and measuring found a 5-6 block dead band at every one of them: you could see the
    // level above and there was nothing within reach of it.
    //
    // This clips the tails and stretches what is left across the whole deck, so the values
    // that used to be rare extremes saturate instead — and the boundaries end up with MORE
    // rungs than the middle rather than fewer.
    spread: 0.15,
  },

  /**
   * HOW TALL ONE DECK OF SKY IS.
   *
   * The archipelago is PERIODIC in altitude: the same generator runs again every deckH blocks
   * with a different noise offset, forever, so there is no altitude at which islands stop —
   * climb higher and there is simply more sky, made the same way and never the same shape.
   * That is what makes "upwards infinitely" a property of the generator rather than a number
   * someone has to keep raising.
   *
   * The one remaining bound is CHUNK_Y, the height of a column of world the streamer builds
   * in one piece. Removing THAT means splitting chunks vertically and streaming slabs, which
   * multiplies draw calls — a separate piece of work, and the honest edge of this one.
   */
  // How thick the slab under a sky town is. Lives here rather than with the rest of the
  // settlement numbers because worldgen is what builds it, and worldgen reads RELIEF.
  skyPlatform: 14,
  deckH: 96,
  // Each deck up gets a slightly easier threshold than the last, so the sky keeps thickening
  // the higher you climb instead of settling into one repeated density.
  deckThicken: 0.03,

  /**
   * HOLLOWS — the land bitten out from underneath: overhangs, undercuts, a roof to fight
   * beneath. The LID is never carved, so the walking surface on top is exactly what it
   * always was and everything that reads groundY keeps working. What you get is geometry on
   * the cliff faces and chasm walls, which is where you actually meet it.
   */
  hollow: {
    scale: 0.0055,
    thresh: 0.5,
    lid: 4,             // solid blocks always left on top — the roof you walk on
    depth: 7,           // how far under the lid the hollow sits
    thick: 6,
  },
};

export const CONTINENT_SCALE = 0.0035;  // big landforms
export const CONTINENT_AMP = 20;
export const HILL_SCALE = 0.02;         // local relief
export const HILL_AMP = 6;

// D8: difficulty is legible. Rings are named, visibly tinted bands of distance from
// spawn — not a smooth invisible gradient. Mob tables, loot, and (later) settlement
// harshness all key off ringAt().
// 260, not 400: at a walk of ~5-8 u/s, 400 units meant ~60s of travel IN A STRAIGHT LINE
// before you left the Commons, and wandering never gets there at all — you can circle for
// ten minutes and stay in ring 0. A ring should be a journey, not a commute.
export const RING_SIZE = 260;           // width of the FIRST band
// Each band is wider than the last, so the deep tiers are vast rather than a treadmill of
// thin shells. Band t is RING_SIZE * (1 + t*RING_WIDEN).
export const RING_WIDEN = 0.25;

/**
 * WHERE THE DIFFICULTY RAMP LEVELS OFF — see ringPressure() in world/gen.js.
 *
 * The ramp was a pure quadratic: pressure = ring + ramp·ring·(ring−1). Mob HP is
 * hpGrowth raised to that, so HP grew exponentially in a QUADRATIC while the player's damage
 * grows exponentially in a LINE (damageGrowth per level). Two curves of different order can
 * only ever diverge, and in an endless world (D9) there is no value of `ramp` that saves it —
 * it just moves the wall further out. Measured on the cleaver in easy mode, a plain mob cost:
 *
 *     ring 2    0.8 swings          ring 10     224 swings
 *     ring 7    8.2 swings          ring 12    3925 swings
 *     ring 8   20.7 swings          ring 15  700662 swings
 *
 * which is exactly the "above level 35 it takes forever" this is answering.
 *
 * So the acceleration SATURATES. The extra pressure still climbs quickly through the early
 * rings — where it is the whole reason the deep feels different — and then flattens into a
 * straight line, which puts mob HP back on the same order as player damage. Depth still
 * costs you: it grows about 1.16× per ring rather than 2.5×. It just stops being a wall.
 *
 * TWO numbers, because saturating from ring zero was the other error. Flattening the whole
 * curve took a ring-8 mob from 20.7 swings to 2.0 — from a wall to nothing, and "they die too
 * fast" was the immediate verdict. The early rings were never the problem: the ramp there is
 * what makes leaving the Commons mean something, and it should be left exactly alone.
 *
 * So RAMP_FREE rings keep the original quadratic untouched, and only past that does the
 * acceleration level off. The two reports bracket the target — 20.7 swings is a wall, 2.0 is
 * nothing — so ring 8 is set near the middle of them at about 7:
 *
 *     ring 2   0.8      ring 8    6.8      ring 12  14.2
 *     ring 6   4.3      ring 10   9.0      ring 15  31.3
 *
 * (before gear, which roughly halves them again.) Depth still costs; it just stops being an
 * exponent of a different order to your own growth. RAMP_KNEE lower flattens harder past the
 * free rings; RAMP_FREE higher keeps the old wall for longer.
 */
export const RAMP_FREE = 7;
export const RAMP_KNEE = 2;

// How many settlements a band holds: towns double per tier (capped), plus one CITY from
// tier 1 outward that grows as you go. So the frontier gets denser AND grander.
export const SETTLE = {
  townsBase: 1,           // tier 0: the spawn town, alone
  // Town count per tier is 3 + 6t (see townCount) — always a MULTIPLE OF THREE, so the three
  // faction colours deal out evenly and every ring is guaranteed all three: wherever you
  // stand, your people are nearby, and so are your enemies. The map itself is the war.
  // It climbs STEEPLY with depth: the outer bands are physically wider, and a frontier that
  // thins out as you push into it reads backwards — the deep should feel contested.
  // 60, up from 30. The cap existed so a ring could not run away, but a ring twelve bands out
  // is twenty-five times the area of ring one and was being handed the same thirty towns —
  // one per 837m of walking, which is a frontier with nothing on it.
  townCap: 60,
  // HOW HIGH A TOWN'S AIRSPACE REACHES. Being "in a sanctuary" was a purely flat question,
  // which was the only sensible reading while the sky was empty — now you can stand on an
  // island two hundred blocks over a town and the game still counted you as inside its walls,
  // which meant nothing could hurt you up there. A town is a place on the ground; above this
  // you are in the sky, and the sky belongs to nobody. Well clear of anything you could reach
  // from inside (the walls are 10 tall and a double jump adds 2.5), so ordinary play never
  // touches it.
  roof: 24,
  // ...and how far BELOW its floor still counts as being in it. A town is a slab of space,
  // not a half-space with a lid: bounding only the top meant standing on the ground under a
  // sky town put you inside its walls two hundred blocks down, so nothing could hurt you
  // there — while the frontier around you carried on spawning camps and bosses, because
  // those ask a different question. Small, because it only has to cover a dip inside the
  // walls, not the whole sky beneath them.
  cellar: 8,
  /**
   * SKY TOWNS. Settlements standing on their own flat platform up in the archipelago —
   * the same towns, with the same quartermasters, the same standing and the same counters.
   *
   * They are ADDED to each ring rather than converted from it: the frontier underneath keeps
   * every town it had, and the sky gets its own. Without them the whole climb is a place to
   * fight with nowhere to spend anything, and you have to come all the way down to sell.
   */
  /**
   * HOW FAR APART SKY TOWNS SIT, in metres — a DENSITY, not a count.
   *
   * Deriving them from the ground count was the mistake, because that count is capped at
   * townCap and a ring eight bands out encloses twenty-five times the area of ring one. Same
   * number, vastly more room: measured, one town per 138m at tier 1 and 588m at tier 12,
   * which is why the deep felt empty however high the multiplier went. Fog closes at about
   * 106m, so anything past a couple of hundred metres apart is a town you find by accident.
   *
   * A spacing scales itself. Deep rings get thousands of settlements, which is only
   * affordable because sanctuariesNear is indexed by bearing now — it used to walk every
   * settlement in three rings, from inside player collision.
   */
  // 165 rather than 150, because a ring is a THIN annulus and a sunflower on one does not
  // achieve sqrt(area/n) between neighbours — the spiral's Fibonacci arms bring index i and
  // index i+55 within about half of it. Measured against that real nearest-neighbour rather
  // than the theoretical one.
  skySpacing: 165,
  /**
   * ...AND A CEILING ON HOW MANY ONE RING MAY HOLD.
   *
   * A density with no cap is unbounded, because ring area grows with the square of the
   * distance out and the world is endless. At a million metres out — which a test reaches
   * simply by standing somewhere no wall could contain it — the honest answer is three
   * million settlements in one ring, and the process dies building them.
   *
   * Past this the spacing widens instead, so the deep-deep gets sparser rather than
   * impossible. The real fix is to generate settlements NEAR A POINT rather than a whole ring
   * at a time; this is the guard rail until then.
   */
  skyMax: 4000,
  // The band they are scattered through, measured from just clear of the tallest land. They
  // used to be snapped to three narrow shelves one deck apart, which read exactly as Luke
  // described it — one spot, and that spot far too high. Continuous now, and biased LOW
  // (skyLowBias), so most of them are a climb rather than an expedition and the high ones are
  // the exception you go looking for.
  // A SKY TOWN IS A COMPACT OUTPOST, not a full town. At the ground's radius, forty-five of
  // them in a ring needed 154 units of separation and the ring only affords about 107 — so
  // they either had to be rarer or smaller, and rare is the thing that made them unfindable
  // in the first place. Small enough to fit, big enough to walk around in and hold a market.
  // 26. Sunflower packing puts the nearest neighbour at about sqrt(area/n), but with real
  // variance — at radius 30 the tightest pair in a ring came out three units short of its
  // footprint. Shrinking the outpost keeps the DENSITY, which is the thing being asked for;
  // widening the spacing would have paid for it with the very thing it is meant to fix.
  skyRadius: 24,
  skyLow: 88,
  skySpan: 300,
  skyLowBias: 1.8,
  cityFromTier: 1,
  cityScale: 1.55,        // city radius = RADIUS * (cityScale + cityGrow * tier)
  cityGrow: 0.32,
  // How far a settlement levels the land, as a multiple of its furthest WALL corner. Every
  // settlement does this now, not just cities: once the terrain grew spires and chasms
  // (RELIEF), a town on raw ground meant walls hanging off a cliff and villagers pathing
  // into a canyon. Towns get the wider apron because they are small — the blend has to be
  // long enough that the drop back to wild land is a slope you walk, not a wall you meet.
  flatten: 1.25,
  // Daylight between a settlement's flattened apron and a mountain's skirt. A town levels
  // whatever it stands on, so one placed on a mountain bites a flat disc out of the only
  // landmark in the ring — and a town near the gate would put a dungeon door inside a safe
  // zone, where no weapon works. See mountainGap() in world/sanctuary.js.
  mountainGap: 30,
  // Open air a sky town keeps between the underside of its slab and whatever rock is below
  // it. Only mountains are tall enough for this to bite.
  skyClear: 12,
  // 1.35, not more: ring 1 packs nine towns into the narrowest band, and a wider apron made
  // neighbours overlap — where two aprons meet, one wins and the seam between them is a
  // cliff, which is the exact thing this was added to prevent.
  townFlatten: 1.35,
};
export const RINGS = [
  { name: "the Commons",  tint: [1.00, 1.00, 1.00] },
  { name: "the Fallows",  tint: [0.96, 0.98, 0.88] },
  { name: "the Reach",    tint: [0.90, 0.94, 0.86] },
  { name: "the Waste",    tint: [0.96, 0.88, 0.78] },
  { name: "the Ashlands", tint: [0.88, 0.78, 0.74] },
  { name: "the Deep",     tint: [0.74, 0.72, 0.82] },
];

// Player physics
export const PLAYER = {
  radius: 0.35,
  height: 1.8,
  eye: 1.62,
  // 8.2 and 10.8, up from 7.3 and 9.6. The BASE moved up as the ceiling came down (see
  // XP.speedSoftCap): the point of that change was to stop a levelled character outrunning
  // the terrain, not to make a level-1 one wade. Raising the floor while lowering the roof
  // narrows the whole band — the game feels closer to the same speed at hour one and hour
  // twenty, which is what makes the movement design tunable at all. Every jump, gap and
  // wall kick reads the same way for everybody rather than being a different game per level.
  walkSpeed: 8.2,      // level-1 baseline; levels multiply this (XP.speedGrowth)
  sprintSpeed: 10.8,
  accel: 45,
  friction: 12,
  gravity: -26,
  // 9.3, up from 8.4 — about 1.66 blocks instead of 1.36, and a full double-jump chain
  // reaching noticeably higher. The terrain grew taller faster than this number did: terraces
  // step ~2 blocks by design (RELIEF.terraceStep x terraceMix), which was tuned to sit "just
  // above a single jump and just under a double" — but with mountains, wedges and four island
  // decks in play, a great deal more of the world is a ledge you are trying to get onto.
  jumpSpeed: 9.3,
  // THREE FROM THE FIRST FRAME (a ground jump and two in the air), rising to four at level 10
  // and one more every ten after that — see XP.jumpsPerLevels.
  //
  // Two was the number from when this was a shooter that happened to have terrain. It is a
  // PARKOUR game now: the sky is where most of the world lives, the wedges and stepping stones
  // are laid out expecting a chain of hops, and starting with two meant a new player met that
  // architecture without the vocabulary to read it — every gap looked like a wall. Three is
  // the smallest number that lets you commit to a jump, misjudge it, and still save yourself,
  // which is the moment the whole pillar is selling.
  jumps: 3,             // ground jump + this many air jumps - 1
  airJumpScale: 0.92,   // air jumps slightly weaker, so the first one still feels best
  maxFall: -60,
  // AUTO STEP-UP. A capsule that tests its whole height against the voxel grid is stopped
  // by a one-block rise, and the land rises by exactly one block every twenty units — so
  // walking anywhere meant jumping every three seconds for no reason you could see.
  // One block is walking; two or more is parkour. That line is what the terrain is built
  // against, and it is why a ledge means something now: the ones that stop you are the ones
  // you were meant to notice.
  // YOU CANNOT STAND ON A WALL. The wall is a solid band with a flat top, so landing on the
  // parapet let you walk the whole ring like a catwalk — over the gate, over the garrison,
  // sniping down into a town you never entered. A wall is a barrier, not a road.
  //
  // Shoved sideways rather than blocked, and only while you are STANDING on it — in the air
  // nothing touches you, so you can still jump clean over a wall; the slide only starts if you
  // come to rest up there. It OWNS your movement while it runs, like a dodge roll: nudging
  // velocity competed with your own acceleration and you could simply walk against it.
  //
  // 11 blocks/sec — above sprint (9.6), so the parapet is behind you inside half a second and
  // there is no walking against it, but nowhere near fast enough to fling you off a ledge.
  wallSlide: 11,
  stepHeight: 1,
  // The body snaps up instantly (physics stays honest); the EYE lags and catches up over
  // about an eighth of a second, so a staircase reads as a climb instead of a series of
  // jolts. Blocks per second.
  stepSmooth: 9,
};

// D6: one hitscan gun. A raycast — no ballistics, no projectile pooling. Everything here
// is a stat a level-up card will later multiply (D9), which is why they're all named.
// WEAPONS — a family, not a gun. Each is the same hitscan core (one ray from the crosshair)
// with a different feel dialled entirely in data: rate, magazine, spread, range, pellets,
// and semi-vs-auto. They are the Weapon slot of GEAR.md — you own guns and switch between
// them (mouse wheel), and buying one from the smith equips it. Damage still rides the level
// multiplier and the (coming) Gun-Damage stat, so a weapon's number is its IDENTITY, not its
// power ceiling — a sniper hits like a truck at every level, an MG spits chip damage at every
// level, and gear scales both together.
/**
 * A 25% CUT TO WEAPON DAMAGE, applied in one pass. Damage ONLY — fire rates, magazines,
 * ranges, reloads and radii are all untouched, so every weapon still feels like itself and
 * simply takes longer to finish what it starts.
 *
 * NOT scaled: the two faction right-clicks (SPIN, LANCE_SPIN), Dash Strike or Whirlwind.
 * Those are abilities rather than triggers, and they keep their own numbers.
 *
 * ONE KNOCK-ON WAS FOLLOWED THROUGH. The lance's sweep is tuned to LOSE against simply holding
 * the beam on one target, and that is a RATIO, meaningful only against the beam — so cutting
 * the trigger to 142 dps left the sweep winning at 304 against 284, backwards. Re-derived to 28
 * a pass (224 against 284). It is the one ability in the kit whose number is pinned to a
 * weapon's damage, and so the only one that has to move when a gun does.
 */
export const WEAPONS = {
  rifle: {
    id: "rifle", name: "Repeater", price: 0,   // the starter; owned from the first frame
    // 60 ROUNDS AT 11 A SECOND. The starter's job is to let a new player LEARN — shoot, miss,
    // reposition, keep shooting — and every number here is bent toward "keep shooting". A
    // long belt on the weapon you never have to buy is the kindest place to put generosity,
    // and a fast one means a missed shot is a fifth of a second rather than an event.
    //
    // 5.5 seconds of continuous fire, up from 2.4 at the original 18/7.5. Long enough that
    // the reload is something you CHOOSE to do in a gap, rather than the thing every fight
    // interrupts you with.
    damage: 9, fireRate: 11, magSize: 60, reloadTime: 1.15, range: 220,
    pellets: 1, auto: true, recoil: 0.016, recoilRecover: 0.75,
    spreadHip: 0.06, spreadAim: 0.002, sound: "rifle",
    desc: "Balanced automatic. Hold to fire.",
  },
  shotgun: {
    id: "shotgun", name: "Scattergun", price: 260,
    // A wall of pellets that now carries a real distance. One booming shot, a pump between.
    damage: 8, fireRate: 1.3, magSize: 5, reloadTime: 0.65, range: 90,
    pellets: 9, auto: false, pump: true, recoil: 0.05, recoilRecover: 0.6,
    spreadHip: 0.14, spreadAim: 0.09, sound: "shotgun",
    desc: "9 pellets, long reach now, one booming shot with a pump between rounds.",
  },
  sniper: {
    id: "sniper", name: "Longshot", price: 300,
    // One enormous round across the whole map, then a bolt cycle. bam — ka-chunk — bam.
    damage: 124, fireRate: 1.1, magSize: 1, reloadTime: 1.05, range: 600,
    pellets: 1, auto: false, pump: true, recoil: 0.09, recoilRecover: 0.5,
    spreadHip: 0.11, spreadAim: 0.0, sound: "sniper",
    desc: "One huge round per reload — bam, bolt, bam. Enormous damage, map-long range.",
  },
  mg: {
    id: "mg", name: "Ripper", price: 300,
    // A hose. Low per-shot, huge belt, so it answers crowds and never stops for long.
    damage: 4, fireRate: 12, magSize: 60, reloadTime: 2.0, range: 180,
    pellets: 1, auto: true, recoil: 0.012, recoilRecover: 0.8,
    spreadHip: 0.12, spreadAim: 0.028, sound: "mg",
    desc: "Low damage, huge belt, high rate. Hoses down crowds.",
  },
};

// FACTION WEAPONS. See WEAPONS.md for the reasoning; this is only the numbers.
//
// The four starting guns are all one verb — point, click, a number happens — differing by
// rate and damage, which are adjectives. These three ask different QUESTIONS: the cleaver
// asks about range and commitment, the lobber about prediction, the lance about lines. That
// is what makes joining a faction change how you FIGHT rather than what you are called.
//
// `mode` is what the gun does with a trigger pull. Everything without one is hitscan, exactly
// as before, so the original four are untouched by any of this.
Object.assign(WEAPONS, {
  cleaver: {
    id: "cleaver", name: "Iron Cleaver", price: 900, faction: "iron", mode: "melee",
    // A cone, not a ray. Reach is short and the arc is wide: you are not aiming so much as
    // deciding to be here. 6.0, up from 4.4 after play — mobs bite at ~2.4 and lunge from
    // further, so a 4.4 swing meant trading hits with everything you fought. The extra reach
    // gives the cleaver a band where it strikes FIRST, which is what makes closing in feel
    // like a plan instead of a toll. The drawn arc follows this number automatically.
    // The swing is wide SIDEWAYS and aimed VERTICALLY. coneDeg is the fixed left-right arc;
    // coneVertDeg is the height band, and that band FOLLOWS YOUR PITCH — look up and you are
    // cutting high, look down and you are cutting low. One rigid cone tilted by the camera
    // did the opposite of what a swing should: looking down at things crowding you made the
    // cone point INTO the ground and miss them.
    // 9.5 and a 140-degree height band, up from 6.0 and 90. Both numbers are answers to the
    // terrain: RELIEF put the fight on several levels at once, and a swing that reached six
    // units on a 45-degree band could not touch the body standing on the terrace above you or
    // the one clawing up from the chasm below — the two places enemies now most often are. A
    // melee faction whose weapon only works on flat ground is a melee faction that cannot
    // play the game the terrain is asking you to play.
    // ONE CLICK, ONE SWING. It used to be `auto`, so leaning on the button swung forever and
    // the weapon played itself — melee stopped being a decision and became a state you held.
    // fireRate 5 is the FLOOR between swings (0.2s), not the rate you get: the semi-auto
    // latch means the trigger has to be released and pulled again every time, so how fast
    // you actually cut is how fast you choose to.
    // 74, a minor buff from 66 (the post-nerf floor; it was 88 before the 25% weapon pass).
    // Iron pays range for damage — that is its whole bargain — and after the pass the swing
    // sat at ~370 dps against the beam's 142-at-range, a premium that no longer felt like
    // one for a weapon that must walk through everything it fights. ~10% back, well short
    // of the old 88: the nerf stands, the bargain just pays a little better.
    damage: 74, fireRate: 5, range: 9.5, coneDeg: 100, coneVertDeg: 140, knock: 12,
    // THE SHOVE IS THE RATIONED PART, not the swing.
    //
    // Knockback is what makes a melee weapon SAFE: every hit buys back the spacing that
    // closing in cost you, so a cleaver that always shoves is a cleaver that never has to
    // stand its ground. Cutting the damage or the rate would answer that by making the weapon
    // worse; charging the shove answers it by making it a DECISION — five of them, then you
    // are in the crowd on the crowd's terms until they come back.
    //
    // The swing itself is untouched: same damage, same reach, same rate, always available.
    // Running out of shove means the arc stops clearing room, never that it stops working.
    knockCharges: 5,
    // 0.5, down from 1.5 — recovered one at a time, and now three times as fast. At 1.5 a
    // fully spent bank took 7.5 seconds to refill, which in a game where the melee weapon is
    // the one that must STAND IN the fight meant the cleaver's spacing tool spent most of a
    // long brawl absent. Half a second a charge keeps the ration real — five shoves back to
    // back still empties the bank, and burning it all still costs a beat before the next —
    // without the recovery outlasting the fight it was needed in.
    knockRecharge: 0.5,
    magSize: 0, reloadTime: 0, pellets: 1, auto: false, recoil: 0.004, recoilRecover: 0.7,
    spreadHip: 0, spreadAim: 0, sound: "cleave",
    desc: "A wide swing in front of you that throws things back. Right-click to spin: "
      + "untouchable for a heartbeat, then damage all around you.",
  },
  lobber: {
    id: "lobber", name: "Vale Cannon", price: 900, faction: "vale", mode: "projectile",
    // A CANNON now: one heavy shell at a time that bursts into a WIDE circle. Where the lance
    // clears a crowd along a line, this clears one in a ring — the speed faction's answer to
    // being surrounded, thrown from range.
    damage: 0,                     // all of it lands as splash; see blastDamage
    // THE DRUM FEEDS TWO GUNS, and both just got hungrier. Single shells are the aimed,
    // leading shot the weapon was built around; the BARRAGE below eats six at a time.
    //
    // 3.4 AND 48 — both doubled together, and the pairing is the whole edit. Doubling the
    // rate alone would have halved how long the drum lasts, turning the cannon's identity
    // (a patient placed shell) into a reload animation with gaps of shooting in it. Doubled
    // together, the SHAPE is preserved exactly — the same number of shells per drum, the
    // same eight volleys' worth of choice — and only the tempo changes. It is the same
    // weapon played at double speed rather than a different weapon.
    //
    // WHAT IT COSTS THE SECOND TRIGGER, stated plainly because it is a real loosening and
    // not a free lunch: a barrage still eats six, so a doubled drum funds EIGHT launches
    // instead of four and the flight ceiling before you run dry doubles with it. The drum
    // is the brake on the recoil ride (weapons.test says so), and this halves that brake's
    // grip. Left deliberately — Vale has been pointed at mobility all day — but it means
    // the honest limit on flying is now the twelve-odd seconds a full drum buys, and the
    // number to move if that reads as too long is `barrageShots`, not this line.
    fireRate: 3.4, magSize: 48, reloadTime: 1.4, range: 130,
    // THE BARRAGE — right mouse. Not an aim: a projectile you have to LEAD is not a weapon
    // that wants a zoom, and pressing RMB on it did nothing but narrow your view. Six shells
    // at once in a cone, which turns the cannon from a placed-shot weapon into a wall when
    // something is close enough that leading is impossible.
    //
    // Costs six rounds — one per shell, no discount. The volley's advantage is that it
    // arrives together; making it cheaper per shell as well would leave no reason to ever
    // fire a single one. Below six it fires whatever remains rather than refusing: the last
    // five rounds are not dead weight, they are a thinner wall.
    barrageShots: 6,
    barrageCost: 6,
    barrageSpread: 0.16,   // cone half-angle in radians — a spread, not a shotgun blast
    // THE RECOIL (asked for in play): the volley THROWS YOU the opposite way it fires —
    // aim down and it is a rocket jump, aim level and it is a disengage that opens the
    // range the cannon wants anyway. Pure opposite-of-aim, no special cases, so the aim
    // angle IS the control: steeper down means higher, flatter means further back. This
    // completes the triangle the other two spins drew — Iron's holds ground, Ash's lifts
    // off it, Vale's LEAVES in a hurry — and it rides the barrage's own cooldown and
    // ammo, so movement and violence spend the same trigger.
    // 17: near double a jump, launch-grade — and the hold (same mechanism as the wall
    // kick) is what keeps the shove from being eaten by the air blend five frames in.
    barrageKick: 17,
    barrageKickHold: 0.4,
    // How long a jump still COMPOUNDS the launch rather than merely failing to cut it.
    // 1.1s: long enough that "fire, then jump" is one motion at human speed even if you
    // are not frame-perfect, short enough that it cannot be saved up — jump late and you
    // simply keep the climb you had, which is the ordinary rule and no punishment at all.
    barrageLaunchGrace: 1.1,
    // The recoil is ANISOTROPIC, tuned in flight: the horizontal 15% under base (a level
    // blast was overshooting the disengage) and the climb 25% OVER it (the rocket jump is
    // the move worth building routes around, so it gets the headroom). Opposite-of-aim
    // stays the rule; these two shape how hard each half of it throws.
    barrageKickAcross: 0.85,
    barrageKickUp: 1.25,
    // THESE TWO SHAPE THE HORIZONTAL ONLY — planted feet absorb 65% of a sideways shove,
    // the air amplifies it half again. The VERTICAL ignores both and always flies at the
    // air value (see gun.js): a stance can brace against something pushing you sideways,
    // which is what a stance is, but there is nothing to brace against when the force
    // throws you off the ground entirely.
    //
    // That split was decided in play and it is the better rule. The first version taxed
    // the climb too, which made a rocket jump require a hop first — a timing tax on the
    // one move players already know how to want, since a rocket jump works from standing
    // in every game that has ever had one. Now the ride reads cleanly: aim DOWN and you
    // launch from anywhere, aim LEVEL and your boots decide whether it is an escape or a
    // step back.
    barrageKickGround: 0.35,
    barrageKickAir: 1.5,
    // 3 SECONDS — LONGER than the lance spin's clock, and the gap between them is the
    // point. Both are second triggers, but they sell different kinds of movement: the
    // rotor is a climb you HOLD and steer, paid for by committing two seconds of your
    // attention to a spin; the recoil is INSTANT, aimed in one frame, and the strongest
    // single launch in the game. Instant costs more than sustained — otherwise the
    // cannon is simply the better mobility tool as well as the crowd answer.
    //
    // It went 4 -> 2 -> 3 -> 2.8 -> 1.5 across the day, and the argument moved with the
    // WORLD rather than with the weapon. At two seconds the ride was "always available"
    // and Vale read as a pinball that occasionally shoots — but that was judged against a
    // sky nothing else was in. The sky is a theatre now: two decks of fliers, casters that
    // shoot upward, a war overhead with its own colours. Being airborne stopped being an
    // escape from the fight and became a place to have it, so the tool that gets you there
    // should not be rationed like an escape. 1.7 is roughly one launch per engagement beat
    // instead of one per lull.
    //
    // The damage price (barrageDamage) still does its own separate job — stopping the
    // volley outclassing the aimed shell — but a per-shell discount cannot pace a MOVEMENT
    // tool, because movement does not care what the shells did. Only the clock can, which
    // is why this number is the one that moves whenever the sky's meaning changes.
    barrageCd: 1.5,
    // The per-shell discount that pays for the volley's other gifts — spread, panic
    // coverage, and the recoil ride. A barrage that matched the placed shot per shell
    // would BE the cannon; 15% under it keeps the slow led shell the marksman's answer.
    barrageDamage: 0.85,
    pellets: 1, auto: false, recoil: 0.045, recoilRecover: 0.55,
    spreadHip: 0.05, spreadAim: 0.005, sound: "lob",
    // SLOW on purpose. With no self-damage and a huge blast, travel time is the ONLY skill
    // the weapon asks for — you must read where the crowd is going and place the shell there.
    // Keep it slow enough to lead; make it fast and the whole weapon becomes point-and-delete.
    // `drop` is a gentle downward curve as it flies: a heavy shell should sag, and the small
    // arc is another thing to read into the lead. A touch of upward launch (upBias) makes it
    // lob rather than merely sag, so the curve reads as an arc.
    // 53, up 25% twice (34 -> 42.5 -> 53). The shell stays a LED shot — that is the whole
    // skill of the weapon, and a test pins it under hitscan speed — but the world it is
    // aimed at has climbed: the sky now holds two decks of fliers, and a shell lobbed
    // thirty blocks up spent so long travelling that a wheeling target had finished its
    // whole manoeuvre before it arrived. Leading a moving thing is a skill; leading a thing
    // that is already somewhere else is a guess.
    //
    // THE CEILING IS CLOSE NOW, and it is worth naming before the next pass: past about 60
    // the shell stops being led at all — you point at a body and it dies, which is the one
    // thing this weapon was designed never to be. The arc (`drop`) is the other half of the
    // read and has not moved, so what is eroding is the TRAVEL time, not the trajectory.
    speed: 53, drop: -12, upBias: 0.06,
    blastRadius: 10.5, blastDamage: 98,
    // IT DOES NOT HURT YOU. The opposite of the grenade rule, on purpose — an explosive fired
    // like a sidearm would kill you constantly up close, punishing the exact thing the speed
    // faction is FOR. The cost is leading a slow shell, not fearing your own boom.
    selfDamage: false,
    desc: "Lobs a heavy shell that bursts in a WIDE circle. It never hurts you — the "
      + "difficulty is leading the shot into the crowd.",
  },
  lance: {
    id: "lance", name: "Ash Lance", price: 900, faction: "ash", mode: "beam",
    // Sustained, and it PIERCES: it does not stop at the first thing it touches.
    damage: 0,
    // 190, up from 132. The lance was the quietest of the three faction weapons by a wide
    // margin — the cleaver's swing ceiling is 440 in a hundred-degree cone and the cannon's
    // shell is 221 across a ten-metre burst, while this managed 132 and asked you to hold it
    // on a moving target the whole time. Ash is the DAMAGE faction; its weapon should not be
    // the one that kills slowest.
    //
    // At 190 hip and 295 aimed it sits between the other two, which is where a weapon with no
    // travel time and no reach requirement belongs: the cleaver still hits harder but has to
    // get there, the cannon still clears more ground but has to be led. What the lance sells
    // is CERTAINTY — it is the only one that cannot miss.
    // 196, up another 20% (142 -> 163 -> 196 across one sitting). LANCE_SPIN.damage is a
    // RATIO against this number and is re-derived every single time it moves — see the
    // essay there, and the formula, before touching either one alone.
    dps: 196, range: 78,
    // UNUSED, and kept as a headstone like SPIN.cdFloor. Right mouse is the spin now, so the
    // lance cannot enter an aimed stance at all and nothing can read this — the rig is told
    // not to blend for beam weapons (see main), which is the same switch that fed this bonus.
    // Named rather than deleted so the next person wondering "did aiming ever do anything"
    // finds the answer instead of silence. Its removal cost the lance a 295 aimed ceiling.
    aimMult: 1.55,
    // TWO BEAMS IN ONE TRIGGER. Aimed, it is a lance: 0.9 wide and +55% damage, for the thing
    // you chose. From the hip it fans to 1.9 — a bit over twice the reach to either side, and
    // it PIERCES, so a hip-fired sweep catches the bodies beside the one you are pointing at
    // while the aimed beam deletes a single target.
    //
    // Kept modest on purpose. A very wide hip beam stops being a sweep and becomes an aura:
    // you would hold the trigger, face roughly forward and never need to aim at all, which is
    // the same dominance the +55% used to be, wearing the other stance's clothes.
    //
    // This exists because aiming used to be free. Spread is zero in both stances (a beam does
    // not miss) and heat does not care either, so RMB was +55% damage for nothing and hip fire
    // had no reason to exist. Width is the cost that makes it a decision: you give up the
    // crowd to gain the target, and the fight in front of you decides which you want.
    beamRadius: 0.9,               // aimed — precise
    beamRadiusHip: 1.9,            // hip — a swathe, not an aura
    fireRate: 0, magSize: 0, reloadTime: 0, pellets: 1, auto: true,
    recoil: 0, recoilRecover: 1, spreadHip: 0, spreadAim: 0, sound: "beam",
    // OVERHEAT, because a piercing sustained beam with no cost is the best crowd answer in
    // the game and nobody would ever use anything else. This turns "hold the button" into
    // "manage the beam", which is a skill rather than a dominance.
    // 0.146 — a full tank burns for TWELVE seconds (1.75 / 0.146).
    //
    // Eight was the right number for the fights this weapon was originally tuned against, and
    // those fights no longer exist: the sky population was quadrupled the same day, so an
    // engagement on an island is now a dozen-plus bodies rather than a knot of three. A
    // piercing beam is the weapon that answers exactly that, and a crowd weapon whose tank
    // empties halfway through a crowd is not a limit, it is a tax on doing the thing it is for.
    //
    // The redline still has to mean something, which is what stops this being fourteen: twelve
    // outlasts a fight, not a ring. You can clear what is in front of you and then you are
    // holding a cooling gun with whatever else the sky sent, which is a real position to be in.
    //
    // Set here rather than by growing the tank, deliberately: heatDown drains a fixed-size tank
    // at a fixed rate, so the tank governs RECOVERY and this governs the burn. Keeping them
    // apart is what let this move 14 -> 8 -> 12 without the cool-down drifting once.
    // 0.292 — DOUBLED, so the tank fills in half the time (about twelve seconds of
    // continuous fire became six). Paired with the damage climb rather than separate from
    // it: the beam went 142 -> 163 -> 196 dps in one sitting, and a weapon that hits 38%
    // harder while running just as long is simply a stronger weapon, not a different one.
    // Halving the sustain turns that climb into a TRADE — the lance now deletes what it
    // points at and cannot point for long, which is a sharper version of what it already
    // was. The overheat lockout is unchanged, so the cost of misjudging it is the same
    // cost it always was; what changed is how often you have to make the judgement.
    heatUp: 0.292,                 // fraction of the bar per second while firing
    heatDown: 0.42,                // and per second while off it
    // 175% OF THE OLD TANK. The lance held 1.0 and burned 0.30 a second, so a trigger pull
    // was 3.3 seconds and then a 1.6s lockout — a rhythm where the weapon was unavailable
    // about a third of every fight, and where committing to a target you could not finish
    // was the default outcome rather than a mistake. At 1.75 a pull runs ~5.8 seconds, which
    // is long enough to hold a beam through a whole engagement and makes the redline
    // something you walk into by overreaching rather than by simply using the gun.
    //
    // The bar still reads 0-100% (main scales the display by this), so nothing on the HUD
    // starts speaking in numbers over a hundred — capacity grew, the gauge did not.
    heatMax: 1.75,
    overheatLock: 1.6,             // forced cool-down once it redlines
    desc: "A burning ray that goes THROUGH what it hits. Right mouse sweeps it around you, "
      + "shoving back what it touches. Hold it too long and it overheats.",
  },
});

// Faction weapons are LEGENDARY — orange, the top of any colour ladder, and unmistakable
// beside grey/green/blue loot and even gold faction armour. They are the rarest thing a
// player wields, earned by joining and paying dear, and locked to the faction that made
// them. The colour is set here in one place so every panel that shows a weapon agrees.
export const WEAPON_LEGENDARY_COLOR = "#ff8a1e";
for (const id of ["cleaver", "lobber", "lance"]) {
  WEAPONS[id].rarity = "legendary";
  WEAPONS[id].color = WEAPON_LEGENDARY_COLOR;
}

// The right-click on the cleaver. A spin — not a block, because an active move that makes
// space fits melee far better than standing still, and because it makes the defensive faction
// the one that is best at READING incoming damage rather than the one that cannot be hurt.
export const SPIN = {
  // 2.5 SECONDS, up from 1.2 (which was up from 0.5, itself down from an earlier 2.5).
  //
  // UNTOUCHABLE THE WHOLE SPIN — that part has never changed and is the reason the number is
  // worth arguing about at all: a guard that expires halfway through is a guard you cannot
  // plan around, so however long it lasts, it lasts completely.
  //
  // What the length actually buys is not survival, it is DISTANCE. Half a second was long
  // enough to eat one blow and not long enough to go anywhere with it; 1.2 is long enough to
  // cross a gap, close on an archer, or leave a pack behind while nothing can touch you —
  // which is what a mobility game should be selling.
  //
  // THE COST IS UPTIME, and at this length it is no longer a rounding error. Against the 2.5s
  // gap the spin is now HALF the cycle spent untouchable — 50%, up from 32% at 1.2s and 17%
  // at 0.5s — and with haste stacked to the cooldown floor it reaches 68%.
  //
  // That is a different weapon, not a tuned one: past about half uptime a defensive button
  // stops being something you time and becomes a state you maintain, and the fights stop
  // asking whether you read the telegraph. Written down here rather than discovered later,
  // because the number that fixes it is `cd` and not `time` — lengthening the GAP keeps the
  // long, committal spin that was asked for while giving the danger somewhere to live.
  time: 2.5,
  iframes: 2.5,          // = time: guarded start to finish, on purpose
  // 1.5 — AND THE DAMAGE WAS CUT IN HALF TO PAY FOR IT. Read these two numbers together;
  // separately each one looks like a nudge and together they are a change of job.
  //
  // The old argument treated the gap as the only dial: a long spin that is also good damage
  // is a button you hold down, so the gap had to be stretched until being untouchable cost
  // you something. That works, but it pays for safety with DEAD TIME, and dead time is the
  // worst thing you can sell an Iron player — theirs is the one kit that has to stand in the
  // fight, so a long wait is spent backpedalling out of it.
  //
  // Cutting the damage pays for the safety directly instead. The spin is now clearly the
  // WRONG button for killing things: swinging beats it against anything you could have
  // reached. So it stops being an attack you also survive inside of and becomes what it is
  // best at — a guard, a shove, and a way to CROSS ground while nothing can touch you. You
  // can have it often, and having it often costs you your damage while it runs.
  //
  // That is a better question than the old one. "Can I afford to be safe right now?" is
  // answered by a timer; "is this worth not attacking for?" is answered by the fight.
  //
  // Still flat, still counted from the spin's END, and still deliberately deaf to haste: a
  // safety window that scales with gear is a telegraph deleter.
  cd: 1.5,
  // UNUSED, and kept only as a headstone. Haste no longer touches the spin's cooldown at all
  // (see updateSpin) — a floor exists to stop a shrinking number reaching zero, and nothing
  // is shrinking any more. Left named rather than deleted so the next person to wonder "did
  // haste ever affect this" finds the answer instead of the silence.
  cdFloor: 1.2,
  // THE CLEAVER IS A ROTOR TOO — hold SPACE while it spins and Iron leaves the ground,
  // the same verb Ash's beam has. 3.81, which is 75% under the lance's lift on purpose,
  // and the gap is the faction line rather than a balance figure.
  //
  // Ash climbs ONTO something: a full rotor clears the low flier deck with margin. Iron
  // gets a HOP — about nine blocks over the whole spin, which takes a ledge, clears a
  // crowd, or drops you back onto a fight from slightly above, and reaches none of the
  // sky's floors. That boundary is the point: Iron is still the faction that has to come
  // back down and stand in it, and a cleaver that could hold a deck would stop being the
  // kit that has to be there.
  //
  // Note the spin's own length works against the gap — Iron turns for far longer than the
  // lance does, so nine blocks against Ash's twenty-five is a much narrower ratio than
  // 75% suggests. Slower and briefer is the correct shape for the melee faction's flight:
  // it leaves the ground reluctantly.
  lift: 3.81,
  radius: 6.6,
  tick: 0.25,
  // HALVED, from 18 — see the essay on `cd` above, which this number is the other half of.
  //
  // It was already the weakest sustained damage in the kit on purpose. Now it is not close:
  // spinning is a real LOSS against anything you could have swung at, and it does not catch
  // up by hitting a crowd either — a pack you spin through takes noticeably less than a pack
  // you wade into. That is the point. The spin's payment is the guarded window and the shove
  // that opens it, and a defensive button that also happens to be good damage is a button
  // with no cost, which is a button with no decision attached.
  //
  // The floor this must stay above: ZERO would be cleaner still, but a spin that does nothing
  // reads as a bug the first time you use it on something already nearly dead. It has to
  // visibly hurt. It just must never be the reason anything died.
  damage: 9,
  knock: 9,              // one shove on the opening beat, not a permanent force field
  speed: 1.25,           // you move a little faster while spinning
};

// The starting weapon, and a back-compat alias for a few call sites that still say GUN.
/**
 * THE ASH LANCE'S SPIN — right mouse, and the reason the lance stopped having a boring one.
 *
 * Of the three faction weapons, two had an INVENTED second trigger (the cleaver spins, the
 * cannon fires a barrage) and the lance had "aim" — the same zoom every shooter has had for
 * thirty years. Aiming also happened to be strictly correct at all times, +55% for the cost of
 * some peripheral vision, so it was not a decision either. One button doing nothing interesting
 * on one weapon out of three is a whole third of the roster's identity missing.
 *
 * WHAT IT IS: two seconds of sweeping the beam around yourself at close range, shoving back
 * everything it passes over, taking 40% less while you do it.
 *
 * WHY IT IS THE RIGHT ABILITY FOR ASH SPECIFICALLY. Read the faction's own weakness line —
 * "crowds while it cools, and anything that reaches you during the lockout". That is the exact
 * hole this fills, and it fills it without patching over it: the spin costs NO HEAT, so the two
 * seconds you spend spinning are two seconds the tank is recovering (0.42/s of a 1.75 tank —
 * about half a second of beam handed back). The dead time in the weapon's own rhythm becomes
 * the thing you do with the crowd that arrived during it. A weapon that answers its own
 * weakness for free would be a bad fix; a weapon whose answer IS its downtime is a loop.
 *
 * WHY IT IS NOT IRON'S SPIN, which it superficially resembles. Iron's makes you UNTOUCHABLE.
 * This one makes them NOT THERE, and only softens what still lands. That is the difference
 * between a wall and a shove, and it keeps the two factions answering the same problem in
 * different verbs: Iron stands in the middle of it, Ash refuses to let it arrive.
 *
 * ON THE 50% UPTIME. Two seconds on, two off, would be alarming for a defensive button — the
 * long comment on SPIN.cd exists because a guard at that uptime stops being something you time
 * and becomes a state you hold. It is fine here precisely because 40% is not immunity: you are
 * still being hurt the whole time, so spinning through a pack is a decision with a bill, not a
 * safe place to stand.
 */
/**
 * THE LOW-HEALTH PULSE — the screen breathing red from the edges when you are nearly gone.
 *
 * The health bar already turns red, and a bar is a thing you have to LOOK AT. In a game played
 * at a crosshair in the middle of the screen, with a movement kit that wants your eyes on the
 * terrain, "glance down and read a number" is precisely what nobody does in the two seconds
 * that decide whether they live. So the warning is moved to where you cannot help but see it:
 * the edges of your own vision, which is exactly where real peripheral alarm lives.
 *
 * SLOW ON PURPOSE. A fast flash reads as damage arriving — that is what #hurt already says,
 * and saying it twice in two rhythms would make both harder to read. This one breathes, about
 * one cycle every two and a half seconds, closer to a heartbeat than to an alarm. It says a
 * STATE ("you are nearly dead"), not an EVENT ("you were hit"), and the pace is the whole
 * difference between those two sentences.
 *
 * It starts a little BEFORE the bar goes red (which is at 0.17): the ambient warning arrives
 * first and the precise one confirms it, rather than both landing at once and saying one thing
 * twice. Never fully opaque at the trough either — a warning that blinks out entirely reads as
 * a glitch, and the point is that it is always there once it starts.
 */
/**
 * WHAT SWEARING TO A COLOUR IS WORTH, on top of the weapon and the allies.
 *
 * The choice already hands you a weapon, an army and two thirds of the game's gear taken away,
 * which is plenty of consequence — but none of it touched your CHARACTER. Ash is "the damage
 * faction" and an Ash character with no Ash gear yet dealt precisely as much damage as anyone
 * else, so the identity lived entirely in equipment you had not earned. Five percent is small
 * on purpose: enough that the sheet agrees with the pitch from the first minute, nowhere near
 * enough to be the reason you pick one.
 *
 * Each pair matches the faction's own `focus`, so there is one story rather than two.
 *
 * WHY THESE ARE MULTIPLIERS ON DERIVED VALUES rather than points added to your stats: gear is
 * summed into player.armor and player.stamina wholesale on every equip, so a bonus living
 * there would be erased by the next re-sum. And +5% of a stat that reads 0 on a bare character
 * is 0 — Ash would work from the first frame while Iron's did nothing until it found a
 * breastplate. Applied to the OUTPUT, all three land immediately and still scale with the kit.
 */
export const FACTION_BONUS = {
  ash: { damage: 0.05 },                  // every source: gun, spell, grenade, melee
  vale: { speed: 0.05, haste: 0.05 },     // movement, and shorter cooldowns and casts
  iron: { health: 0.05, armor: 0.05 },    // a bigger pool, and more of every point of armour
};

export const LOWHP = {
  at: 0.2,               // fraction of max health at which it begins
  period: 2.5,           // seconds for one full breath
  min: 0.16,             // opacity at the trough — dim, but never gone
  max: 0.5,              // and at the peak
};

export const LANCE_SPIN = {
  // 1.62 — a second ten-percent cut, paired again with a ten-percent raise to the climb,
  // because the two are one decision: a HARDER, SHORTER spin. Held twice now, the shape
  // is stable and worth naming: shortening and speeding by the same fraction leaves the
  // altitude almost exactly where it was (~16.5 blocks) and changes only the DELIVERY —
  // it arrives sooner, whips faster (~4.9 turns a second), and hands your other verbs
  // back sooner. If a future pass wants a HIGHER ceiling rather than a snappier one, the
  // number to move is `lift` alone; cutting `time` will never buy altitude.
  //
  // What each cut DOES buy silently is sweep-damage margin, because the beam you could
  // have held instead got shorter too — see the ratio essay on `damage`, which had to be
  // re-derived at this step.
  time: 1.62,
  cd: 2,                 // starts when the spin ENDS, like the cleaver's — see updateLanceSpin
  // THE ROTOR (asked for in play): hold SPACE while the beam spins and the sweep lifts
  // you — Ash flies for as long as the spin lasts. 12.7, walked 6 -> 7 -> 8.4 -> 9.24 ->
  // 10.16 -> 12.7 in flight, well past a jump's 9.3 now. Recorded plainly because the
  // earlier essays named that number as a ceiling and it has been crossed on purpose.
  //
  // WHAT IT REACHES IS THE POINT, and it now reaches something specific: a full hold
  // climbs about 25 blocks, clearing the LOW FLIER DECK (flyLayers, 16) by nine. That is
  // the number worth tuning against from here — the rotor is Ash's way onto a deck, so it
  // should arrive with room to FIGHT rather than exactly level with the thing it came to
  // kill, and nine blocks of margin is comfortably that.
  //
  // The high deck at 44 remains out of reach of one spin, and that is a boundary rather
  // than a shortfall: it belongs to Vale's launch. Each faction's vertical verb reaching a
  // DIFFERENT floor of the sky is what gives the two decks separate identities instead of
  // making them the same place at two heights. The number to watch as this keeps climbing
  // is not the jump any more — it is 44. Reach that in one spin and Ash quietly inherits
  // Vale's floor, and the sky goes back to being one theatre.
  //
  // Why the jump survives being out-climbed. The two verbs never competed on speed alone:
  // a jump is INSTANT, free, unlimited, and available in the frame you want it, while
  // the rotor costs a committed ability, both hands, and a cooldown, and it only climbs
  // while the spin runs. What the crossing changes is that Ash's answer to "get up there"
  // is now decisively the spin rather than the jump — which is the faction's whole
  // identity pointed at the sky, and defensible. What it would NOT survive is the rotor
  // becoming free: if this ever stops costing the spin, the jump is dead.
  //
  // The real ceiling from here is not the jump, it is READABILITY — a climb fast enough
  // that you overshoot the ledge you aimed at stops being a route-maker and becomes a
  // thing you fight. That is a feel question, so it belongs to play, not to this comment.
  lift: 15.24,
  // HOW FAR THE BEAM REACHES WHILE IT SWEEPS. The lance shoots 78 blocks and does not stop at
  // the first thing it touches; a sweeping version of that would clear the horizon in every
  // direction at once, which is a screen-wipe rather than a defensive move. Keeping it far
  // short of that is what makes this a bubble you hold rather than an attack you aim.
  //
  // 13, up from 11 — DOUBLE the cleaver's 6.6, which is the relationship that matters here
  // rather than the number itself. Ash should never have to stand where Iron stands: Iron's
  // spin is a thing you do once you have already closed, and this one is what stops anything
  // closing in the first place. Two full body-lengths of clearance is what "do not come here"
  // looks like, and it is still under a fifth of what the beam does when you simply point it.
  range: 13,
  // EIGHT FULL TURNS IN TWO SECONDS — four a second. A blur rather than a sweep, but pulled
  // back from ten: past about that the passes stop reading as individual passes and the whole
  // thing smears into a disc, which loses the one thing a beam has over a ring — you can see
  // where it is pointing. This is the fastest it goes while still being a beam.
  //
  // Turns are DAMAGE PASSES, so this number cannot be raised on its own — everything in range
  // is crossed once per rotation, and tripling the rotations while leaving `damage` alone would
  // have tripled the ability. It went up, `damage` came down to match, and the total below is
  // what actually got tuned.
  turns: 8,
  // Fine enough that a tick is a QUARTER of a turn rather than a whole one. At 0.2s each tick
  // would have swept the full circle, every body in range would be inside every wedge, and the
  // sweep would quietly collapse back into the ring this ability exists not to be. The wedge
  // has to stay smaller than the circle for the beam to mean anything.
  tick: 0.05,
  // HOW TALL A SLAB IT CUTS. The beam sweeps flat at chest height, so this is what stops it
  // from being a column that reaches things standing far below you on a world made of ledges —
  // the same mistake the charge made with reachY, and it is not making it twice.
  height: 2.6,
  // 32 A PASS ACROSS EIGHT PASSES, so 256 over the full spin against one body versus 318 for
  // holding the beam on it for the same 1.62s. Deliberately the LOSING play single-target,
  // exactly like the cleaver's spin: if spinning out-damaged your own trigger there would be
  // no reason ever to stop. It wins only when there are several of them, which is the
  // situation it exists for.
  //
  // THE TOTAL IS THE TUNED NUMBER, not this one — and it is tuned against the beam, which is
  // why it moves every single time EITHER the beam's dps or the spin's DURATION does. The
  // whole history, because this one line has inverted once already and nearly did again:
  //   38, while the lance dealt 190 dps
  //   28, after the 25% weapon pass took the trigger to 142 and the sweep silently became
  //       the better single-target play at 304 vs 284 — the inversion, shipped and caught
  //   32, following the +15% pass to 163 dps
  //   26, after two 10% cuts to `time` shortened the beam you could have held instead: with
  //       no edit to this line the sweep drifted 78% -> 87% -> 97% of holding, and 97% is
  //       parity in everything but arithmetic
  //   32, HERE, following the +20% pass to 196 dps — back to an earlier number by a
  //       different road, which is exactly what a derived value does
  //
  // THE RULE, and the formula that keeps it: the sweep must sit around 80% of holding your
  // own trigger. `0.8 x dps x time / turns`. Re-derive EVERY time either side moves — the
  // margin erodes silently, from edits that never touch this number.
  damage: 32,
  knock: 14,             // the opening shove, before the beam has swept anywhere
  /**
   * ...AND A MUCH SMALLER ONE EACH TIME THE BEAM COMES ROUND. 3, down from 8.
   *
   * At 8 this was a force field, not an attack. A body was shoved every quarter of a second
   * against a walking speed of 3.1, so it lost ground faster than it could ever make it up:
   * nothing reached you for the whole two seconds, at fifty percent uptime, which quietly made
   * the 40% mitigation decoration — you cannot be softened out of damage you were never going
   * to take. An ability that removes the risk AND the answer to the risk has stopped being a
   * decision and become a place to stand.
   *
   * Small enough now to stagger rather than repel: a pack loses its footing and its shape, and
   * a determined one still closes on you. That is what makes the mitigation earn its place, and
   * it is the same conclusion SPIN.knock reached — the opening beat buys the space, the sweeps
   * only keep it untidy.
   */
  knockTick: 3,
  mitigation: 0.4,       // 40% off everything that lands while it runs
  // AND YOU MOVE FASTER WHILE YOU DO IT. Twenty percent, which is under the cleaver's 25 on
  // purpose — Iron's spin is untouchable, so its speed is for crossing ground safely, while
  // this one is for STAYING in the middle of what you are shoving. The point is repositioning
  // inside the fight rather than leaving it, and a spin you can outrun the crowd with would
  // quietly become an escape button on a two-second cooldown.
  speed: 1.2,
  beamThick: 0.55,       // the drawn core; the glow around it is twice this
};

export const GUN = WEAPONS.rifle;

// ARMOR — a WoW-style SLOT SET, and every piece rolls a LIST of stats, not just armour.
// Five slots, one unique piece each; ALL the stats across your worn pieces add up (see
// recomputeGear in main). A better piece REPLACES the one in ITS slot — you can never wear
// two of the same slot, but a full kit of five, each contributing its spread, is the goal.
//
// Each slot has a CHARACTER, so building a set is a set of choices: the vest is the tank
// piece, shoulders bring Strength, boots bring Agility and speed, and so on. The plain-terms
// meaning of every stat is spelled out in the character sheet's legend.
export const ARMOR_SLOT_ORDER = ["helm", "shoulders", "vest", "pants", "boots"];
const ARMOR_SLOT_NOUN = { helm: "Helm", shoulders: "Guards", vest: "Vest", pants: "Legs", boots: "Boots" };
// Three material tiers. `a` armour, `attr` primary points, `stam`, `rate` secondary rating,
// `dmg` a damage-bucket fraction — each slot draws the ones that fit its character.
const ARMOR_TIERS = [
  { key: "padded", label: "Padded", a: 26, attr: 3, stam: 6, rate: 22, dmg: 0.02, price: 70, minTier: 0 },
  { key: "chain", label: "Chain", a: 58, attr: 6, stam: 12, rate: 46, dmg: 0.04, price: 150, minTier: 1 },
  { key: "plate", label: "Plate", a: 108, attr: 11, stam: 21, rate: 82, dmg: 0.07, price: 300, minTier: 3 },
];
// What each slot rolls, as a function of the tier row. This is where slot identity lives.
const ARMOR_SLOT_STATS = {
  helm: (t) => ({ armor: t.a, rHaste: t.rate, dmgSpell: t.dmg }),
  shoulders: (t) => ({ armor: t.a, str: t.attr, dmgGun: t.dmg }),
  vest: (t) => ({ armor: Math.round(t.a * 1.3), stamina: t.stam, dmgGlobal: t.dmg }),
  pants: (t) => ({ armor: t.a, agi: t.attr, dmgGrenade: t.dmg }),
  boots: (t) => ({ armor: Math.round(t.a * 0.75), agi: t.attr, moveSpeed: t.dmg + 0.02 }),
};
export const ARMOR = {};
for (const slot of ARMOR_SLOT_ORDER) {
  for (const t of ARMOR_TIERS) {
    const id = `${t.key}_${slot}`;
    const stats = ARMOR_SLOT_STATS[slot](t);
    ARMOR[id] = {
      id, slot, name: `${t.label} ${ARMOR_SLOT_NOUN[slot]}`,
      stats, armor: stats.armor, price: t.price, minTier: t.minTier,
    };
  }
}

// Human-readable stat meanings — the legend the character sheet prints so the numbers on a
// piece mean something. Keyed by the stat field; {label, kind} where kind picks formatting.
export const STAT_INFO = {
  armor: { label: "Armor", kind: "flat", note: "reduces damage taken (less per point as it grows, and less against deeper enemies)" },
  stamina: { label: "Stamina", kind: "flat", note: "+8 max health each" },
  str: { label: "Strength", kind: "flat", note: "raises ALL your damage — gun, grenade and spells" },
  agi: { label: "Agility", kind: "flat", note: "movement speed and dash distance" },
  dmgGlobal: { label: "Global Damage", kind: "pct", note: "more damage from every source" },
  dmgGun: { label: "Gun Damage", kind: "pct", note: "more damage from your guns" },
  dmgSpell: { label: "Spell Damage", kind: "pct", note: "more damage from abilities (ring, dash, whirlwind)" },
  dmgGrenade: { label: "Grenade Damage", kind: "pct", note: "more grenade damage" },
  rHaste: { label: "Haste", kind: "rate", note: "shorter ability cooldowns" },
  rAtkSpeed: { label: "Attack Speed", kind: "rate", note: "faster gun fire rate" },
  rReload: { label: "Reload", kind: "rate", note: "faster reloads" },
  moveSpeed: { label: "Move Speed", kind: "pct", note: "faster movement" },
};

// Early-game GRACE. The whole FIRST TEN LEVELS should be easy: a fresh player has no gear,
// no spells, and no faction, and the point of that stretch is to earn all three without
// being punished for not having them yet. This bonus is large at level 1 and fades to
// nothing by `levels`, so a gearless newbie hits hard and shrugs off hits, and the real
// challenge RAMPS UP as you level and kit out instead of landing all at once at the door.
// It carries the early game against the doubled mob health and hard mode's doubled damage:
// the numbers moved, so the newbie's cushion moved with them. The "more powerful at low
// level" dial — turn it up to make the start kinder, down to make it bite sooner.
export const GRACE = {
  levels: 12,         // fully gone here — so it still cushions all the way through level 10
  dmgBonus: 1.4,      // +140% damage at level 1 (a fresh hit lands like 2.4x), fading to 0
  mitigation: 0.62,   // -62% damage taken at level 1, fading to 0
};

// D9 — endless levels, and the economy that makes distance the real progression.
//
// The curve is the design. Level cost grows as level^1.55 while a trash mob's value is
// FLAT for its ring, so early on four mobs is a level and by level 20 it's a hundred.
// Elite value scales the same way but starts 7× higher, so elites overtake trash as the
// backbone of progress — while packs of small ones still meaningfully top you up during a
// fight. Both stay worth killing; only their ROLE changes.
export const XP = {
  /**
   * THE HEIGHT BONUS. Everything you kill is worth more the further you are above the land.
   *
   * The sky earns it: you are further from a refuge, there is no retreating downhill, a bad
   * step is a long fall back to the bottom of a climb you just made, and the camps up there
   * are as thick as anything on the ground. Without a reward the whole archipelago is a
   * scenic detour and the optimal play is to stay on the floor.
   *
   * Deliberately modest. 1.6x at full height is enough that a good island is worth crossing
   * the sky for, and small enough that it never beats simply going OUT — depth is the game's
   * long climb (D8) and this must not quietly replace it with an easier one. Measured against
   * the LOCAL ground, so a mountaintop is not a cheat: you have to actually be in the air.
   */
  altFull: 260,        // blocks above the land at which the bonus is fully earned
  altBonus: 0.6,       // ...and what it is worth there
  mobBase: 12,
  // How much a kill is worth per ring out. Tuned so an ON-LEVEL regular mob is worth about
  // what a same-level WoW Classic mob is: at level 20 you're in tier 3, so 12 × (1 + 1.3×3)
  // = ~59 xp against a ~9,600 level ≈ 0.6% per kill (Classic's ~145 / ~24,000 ≈ 0.6%). So
  // regular mobs stay worth killing at every depth, not just elites and bosses. Tier 0 is
  // unaffected (ring 0 → ×1), so the one-kill opening level is untouched.
  perRing: 1.3,
  eliteMult: 7,
  bossBase: 900,
  bossPerRing: 0.8,

  // A THREE-PHASE level curve shaped after WoW Classic (long grind, quadratic-ish) but a bit
  // faster, and keyed so a mob is worth ~12 xp: level 1 is ONE kill, and it climbs from there.
  // Continuous at the breakpoints (each phase starts where the last ended, just steeper), so
  // the first ten levels are quick RELATIVE to how long 20+ takes.
  //   kills-to-next (at ~12 xp/kill): L1 ~1 · L2 ~4 · L3 ~10 · L4 ~20 · L5 ~32 · L9 ~120
  //   xp: L1 12 · L5 ~390 · L10 ~1690 · L20 ~9560 · L30 ~32k · L50 ~149k  (Classic L50 ≈ 170k)
  xpBase: 12,
  xpEarlyExp: 2.15,    // phase 1 (below break1): quadratic, WoW-shaped
  xpMidExp: 2.5,       // phase 2 (break1..break2): the climb
  xpLateExp: 3.0,      // phase 3 (break2+): 20+ "takes forever"
  xpBreak1: 10,
  xpBreak2: 20,

  // WoW's GREY-MOB mechanic: once you outlevel a ring, its kills stop being worth your time,
  // so easy back-zones can't be farmed for xp — you're pushed outward. Each ring greys out
  // (0 xp) at greyBase + greyPerTier*ring, with a steep drop over the last greyBand levels.
  //   tier 0: full ≤ L9 · L10 ~42% · L11 ~9% · L12 ZERO   (exactly the "big drop then nothing")
  //   tier 1: full ≤ L14 · greys at L17 · tier 2: greys at L22 · …
  greyBase: 12,        // level at which the FIRST ring (tier 0) gives no xp
  greyPerTier: 5,      // each ring's grey level is this much higher
  greyBand: 3,         // levels over which xp falls from full to zero
  greyExp: 2.2,        // >1 makes the drop punchy rather than linear
  bossXpFloor: 0.2,    // a boss never greys BELOW this — it's still a fight, just not farmable

  // DEATH TAKES A LEVEL. This is the point of the whole design, not a rough edge on it:
  // hardcore WoW's grip without hardcore WoW's permanence.
  //
  // The dread comes from LEGIBILITY, not from the size of the setback. A level is a number
  // on your character that you can watch go down, name out loud, and be afraid of — which is
  // what makes a level something you HOLD rather than something you merely earned. A gentler,
  // fairer penalty measured in fractions of a bar is tidier and far less frightening, and
  // fear is the design goal here. Do not "fix" this into fairness.
  //
  // You land a third of the way into the level below, so the climb back is real but the
  // character is never stranded at zero.
  deathLandFrac: 0.33,

  // Interim level rewards. D9's real answer is a 1-of-3 card pick — this keeps levelling
  // FELT until that UI exists, and is meant to be replaced by it, not kept.
  // Levels buy MOBILITY, not bulk. Max HP never moves, so a meteor is as lethal at level 40
  // as at level 4 and survival stays a question of reading telegraphs rather than of having
  // a bigger bar. What you gain is the ability to be somewhere else.
  hpPerLevel: 0,
  // 0.8% per level, down from 2%. This HAD to come down with the cap, not after it: at 2% a
  // bare level-50 character already sat on a 0.55 ceiling, so every point of Agility and every
  // speed roll on every piece of gear was worth about a thousandth of a multiplier. Lowering
  // the cap alone would not have made speed a smaller stat — it would have made it a DEAD one,
  // decided entirely by your level and unaffected by anything you chose.
  //
  // At 0.8% the curve is still climbing at level 80, so gear and Agility keep mattering the
  // whole way up, which is the point of having them.
  speedGrowth: 1.008,     // raw per-level; fed through a tanh soft cap (see applyLevelStats)
  // The most speed levels + gear can ever add, as a fraction of base. tanh approaches but
  // never quite reaches it, so effective speed tops out near ×(1 + this).
  //
  // 0.55, down from 1.2 (and from uncapped before that). At ×2.2 the world had quietly
  // shrunk: a ring you were meant to cross took seconds, terrain you were meant to READ went
  // past too fast to read, and the parkour the whole game is built on stopped being about
  // choosing a line because you cleared every gap by accident. Speed is the stat that makes
  // all the OTHER content smaller, which is why it is the one that has to be held down.
  //
  // ×1.55 at the extreme still feels quick against a base you have played for hours, and it
  // leaves the dash and sprint as the things that make you fast — cooldowns you spend, rather
  // than a number you accumulate until distance stops existing.
  speedSoftCap: 0.55,
  jumpGrowth: 1.015,      // L20 ×1.35 launch = ~1.8× the height (h scales with v²)
  jumpsPerLevels: 10,     // +1 air jump at 10, 20, 30, …
  // COMPOUNDING, not additive. Mob HP grows 55% per ring and levelling is what carries you
  // outward, so a flat +6%/level meant getting relatively weaker the further you went.
  // 9% compounding: L5 ×1.4 · L10 ×2.2 · L20 ×5.1 · L35 ×18.7 — it outruns ring HP slowly,
  // which is the power fantasy without erasing the danger.
  damageGrowth: 1.09,
};

// Out-of-combat regeneration. Slow enough that it is never a substitute for the heal or a
// potion mid-fight — it is what saves you the walk back to town after a scrappy win.
export const REGEN = {
  delay: 6,          // seconds of NOT fighting before it starts
  rate: 3.2,         // hp per second in the field
  // A town MENDS you: it ignores the combat delay and heals a fraction of your max HP per
  // second, so you're back to full in a few seconds regardless of how big your pool is.
  safeFrac: 0.28,    // ~3.5s to full inside the walls
};

// Q — the heal. A 1.5s channel that ROOTS you, breaks if you move, and breaks if you're
// hit. In a game whose every other verb is movement, the cost of standing still is the
// whole design: it turns the boss's volley gaps into the window you're hunting for.
export const HEAL = {
  castTime: 1.5,
  // Heals a FRACTION of your max HP (so it stays relevant as your pool grows) boosted by
  // Spell Power, so a caster build mends more. No cooldown any more — the 1.5s root that
  // breaks on a hit is the whole cost.
  fraction: 0.55,
  cooldown: 0,
  breakOnDamage: true,
};

// Ability slots hold whatever you equip; each ability carries its own cooldown, so there
// is nothing global to tune here. `surgeSpeed` stays because the movement code reads it for
// any ability that grants a speed burst.
export const ABILITY = {
  surgeSpeed: 1.75,
};

// Dash Strike: a committed line through a fight. Untouchable while it travels, so it is
// both an escape and an opening — but the hitbox is NARROW, so it only catches what you
// actually pass through. Aim is the cost; the short cooldown is the reward for aiming well.
// EVERY spell below lost one second of cooldown in the same pass that steepened mob HP:
// fights got longer, so the toolkit comes back sooner. A flat second is deliberately shaped —
// it means the most on the short, woven spells (Chain, Nova) and almost nothing on the big
// panic buttons (Timewarp), so rotations get busier without emergencies getting cheap.
/**
 * ENERGY — the thing the ability bar never had: a shared cost.
 *
 * Eleven buttons is not eleven decisions when nothing competes for anything. A cooldown is a
 * DELAY, not a cost: it stops you pressing the same button twice, and says nothing at all
 * about whether pressing this one should mean not pressing that one. So every spell drew from
 * its own private timer and a fight was never a budget, only a rotation.
 *
 * The failure state this is built around is NOT the empty bar. Nobody dies to an empty bar —
 * they die to a plan that needed one more cast. It regenerates fast enough that you are never
 * standing about waiting, and costs enough that two big spells back to back is a decision you
 * have to have made on purpose.
 *
 * WHAT IT DOES NOT GOVERN: escape. Sprint, dodge, heal and potions are free, always. Being
 * punished for a misjudgement is the point; being punished by ALSO losing the tool that would
 * let you survive it turns a mistake into a death sentence, and makes the bar mean two things
 * at once. It means exactly one thing — how much damage you can do right now.
 */
/**
 * HOW FAR A BLAST REACHES UPWARD, as a divisor of its horizontal radius.
 *
 * Every blast in the game measured distance as hypot(dx, dz, dy * 0.5) — which is 3D, so it
 * looked right, and is exactly BACKWARDS: halving the vertical term DOUBLES the vertical
 * reach. A Ring of Fire with a 15m radius was hitting thirty metres straight down. On flat
 * ground nobody could tell; standing on an island casting at the world below, it is the whole
 * spell landing somewhere you cannot see.
 *
 * These are ground effects — a wall of flame, a ring of frost, a spin. They should be SLABS:
 * wide and shallow. 2 gives a blast half its radius above and below, so a Ring of Fire covers
 * 15m around you and about 7 up, and a grenade at your feet reaches a body on a low ledge but
 * not one two storeys up.
 *
 * Bigger = flatter. Below 1 it starts reaching further up than out again, which is the bug.
 */
export const BLAST_VSCALE = 2;

export const ENERGY = {
  max: 100,
  regen: 22,            // empty to full in about four and a half seconds
  // The costs. Read them as a rotation: Nova then Dash is 95 and leaves you 5 — not enough for
  // anything at all. That gap is where the game is, and it is now a much narrower one.
  //
  // EVERY OFFENSIVE SPELL WENT UP BY ABOUT HALF. Two reasons, and they are the same reason
  // twice. A full bar used to fund an opener AND a follow-up AND still be most of the way back
  // by the time the cooldowns were: the resource was a speed limit on a rotation rather than a
  // budget, and it never once said no to a plan you actually wanted. And a new character now
  // STARTS holding Explosion and Dash Strike — spells that used to be several hours of saving —
  // so the thing standing between level one and casting the best button in the game repeatedly
  // has to be something, and a price is a far better something than a locked shop door.
  //
  // Heal and the grenade are deliberately untouched at 30 and 35. Everyone owns those two from
  // the first frame whatever else they are carrying, and making the floor of the kit dearer
  // punishes the player who has nothing else — which is the opposite of the intent.
  //
  // BACK TO 25, after a detour up through 45, 60 and 80. That climb was chasing the wrong
  // thing: the dash had just learned to follow your aim upward and appeared to give absurd
  // free height, so it looked like it needed pricing out of reach. It did not — it had a bug.
  // Driving vertical velocity for the dash and then LEAVING it there meant an upward dash
  // expired with 46 of rise still in the bank, and gravity spent the next two seconds turning
  // that into roughly forty extra blocks of flight. The dash was never worth 80; it was worth
  // 25 and doing something it was never told to do. Fixed at the source (see controller), and
  // the price came home. Worth remembering the next time a number looks like it needs tripling.
  dash: 35,
  // 35, DOWN FROM 60. Nova is crowd CONTROL, not damage — it freezes, and what it buys is
  // the second you needed rather than a corpse. At 60 the opener (Nova then Dash) spent 95
  // of the bar and left 5, which read as "the control spell is the expensive one", and the
  // player learns from a price: the expensive button is the strong button. It taught the
  // wrong lesson about which of these two is the win condition. At 35 the pair costs 70 and
  // leaves 30 — a Chain short, still no second Nova (see the burst test) — so the opener is
  // a rotation you can complete instead of a bar you empty.
  nova: 35,
  chain: 50,
  // 45, AND EXPLOSION CHANGED JOBS — read this with FIRERING.cd, which went 15s to 1s and
  // its damage down 40% in the same breath. Those three numbers are one decision.
  //
  // It was the once-per-fight event: a fifteen-second gate and a screen-clearing 420, so
  // the whole spell was a button you saved. Now it is a spell you CAST — cheap in time,
  // dear in bar, and no longer able to end a fight by itself. That is a straight trade of
  // impact for rhythm, and it is the trade this game keeps making because ENERGY is
  // supposed to be the thing that says no. A fifteen-second cooldown says no far louder
  // than any price, which made the price decorative on exactly the spell it most wanted
  // to matter for.
  //
  // 45 is the dearest thing on the bar, deliberately: at one second the ONLY brake is the
  // cost, so it has to be a real one. A full bar is two Explosions and nothing else, and
  // the regen (~2s to earn one) is the real cadence — you can chain them, but only by
  // spending your whole rotation on it and having no answer to anything that goes wrong.
  firering: 45,
  // WHIRLWIND is charged UP FRONT, not by the second. It is a fixed 3.6s spin rather than a
  // hold, so a drain would only be a fixed cost with extra steps — and it could run dry
  // mid-spin and strip the invulnerability, which is the one thing this resource must never
  // do. You either get the whole spin or you never started it. Dearer than a Nova because
  // being untouchable for three seconds is worth more than any amount of damage.
  // 35, by decree, after two rounds of the same lesson (85 priced it out of the dash combo;
  // 65 fixed the combo but still made it the dearest button). The old rule here was
  // "invulnerability costs more than damage"; the new one is that Whirlwind is a RHYTHM
  // spell, priced like Dash so the pair reads as one sentence — dash in, whirl — with 30
  // left over for a heal. What still guards it: a 15.6s cooldown, which is the real ration
  // on being untouchable, and always was.
  whirl: 35,
  // THE TWO YOU START WITH. They were free while they lived on their own keys outside the
  // bar; now that they are spells they pay like spells, and the price is what makes them
  // decisions. Thirty each is deliberately under a third of the pool: a Nova and a heal still
  // fit in one breath, but panic-mashing heal while the grenade is out puts you on the floor
  // with no energy — which is exactly the mistake the resource exists to let you make.
  heal: 30,
  // The grenade is dearer than the heal because it is the one that ENDS things. With no
  // cooldown left on it, this number is the entire brake: 35 means two throws and you are
  // down to a Dash, three and you are on the floor with nothing.
  grenade: 35,
};

export const DASH = {
  price: 120,
  // 0.8, down from 3 — ENERGY is what limits this now. A cooldown on top of a cost is
  // double-gating: whichever is longer is the only one the player ever feels, and the other
  // is a bar they watch instead of a decision they make. Long cooldowns are kept only for the
  // big buttons (Ring of Fire, Timewarp), where the point is once-per-fight, not once-per-
  // rotation.
  cd: 0.8,
  speed: 46,
  time: 0.26,           // ~12 units of travel
  radius: 2.6,          // how close a mob must be to the line you cut
  // 130, up from 95 — a LITTLE more, deliberately. Dash is on a three-second cooldown and is
  // mostly a movement tool; the damage is a bonus for aiming it through something, and if it
  // paid like a nova there would be no reason to press anything else.
  damage: 130,
  knock: 9,
  iframePad: 0.1,       // a sliver of grace on landing, so you don't eat a hit on arrival
};

// Whirlwind: leap in, land hard, then spin through whatever survived. Two phases in one
// button — the slam is the commitment, the spin is the reward for committing.
export const WHIRL = {
  price: 260,
  minTier: 1,           // stocked from the first ring out
  // THE GAP AFTER THE SPIN, not counting the spin itself. The timer used to start on cast,
  // so 3.6 of the 12 seconds were spent mid-whirl and the real exposed gap was only 8.4 —
  // you were untouchable for a third of your own cooldown. See the ability's cd in shop.js,
  // which is this plus spinTime for exactly that reason.
  cd: 12,
  leapSpeed: 24,
  leapUp: 9.5,
  leapTime: 0.55,       // airtime cap; landing early triggers the slam early
  slamRadius: 10,
  slamDamage: 80,       // the landing, cut with the spin for the same reason
  spinTime: 3.6,
  spinRadius: 7.0,      // matches the drawn ring exactly
  spinTick: 0.22,       // damage every this many seconds while spinning
  // 9, down from 22 — about 40/s rather than 100/s. Whirlwind was three tools at once: it
  // moves you, it makes you untouchable, and it hit everything around you harder than the
  // spells that do nothing else. It is a COMMITMENT now rather than a free upgrade to
  // standing still: you cannot shoot and you cannot cast while it runs, so the guard and the
  // reposition are what you are buying and the damage is a bonus for aiming it well.
  spinDamage: 9,
  spinSpeed: 1.5,       // and you move faster while you do it
};

// --- New spells (WoW / LoL / Overwatch flavoured), sold by the Adept -------------------
// Timewarp: stamp your position/HP now; 5s later you SNAP back to it with all cooldowns
// reset (Zilean's Chronoshift crossed with a Recall). A panic button and a burst enabler.
export const TIMEWARP = { price: 340, minTier: 1, cd: 39, window: 5 };
// Cataclysm Orb: lob a red ball that bursts and leaves a burning pool doing heavy DoT.
// Rank 2 the pool SLOWS, rank 3 it ROOTS.
export const ORB = {
  price: 240, minTier: 0, cd: 10, speed: 27, up: 5, range: 66,
  // IT BOUNCES OFF TOWN WALLS. A wall is collision-only geometry, invisible to the voxel test
  // the orb was using, so it sailed straight through one and burst inside a market. Now it
  // rebounds, which turns a wall from a thing that swallows your spell into a thing you can
  // play OFF — bank it round a corner, or off the outside of a garrison you are not ready to
  // walk into. Speed is damped each time so it settles rather than rattling about, and after
  // this many it simply bursts where it is.
  bounce: 0.66,
  bounces: 3,
  burstRadius: 6, burstDamage: 130,
  poolRadius: 5.5, poolDps: 78, poolLife: 5, poolTick: 0.3,
  slowMul: 0.5, slowT: 1.2, rootT: 1.1,
};
// Frost Nova: instant ring around you — damage + a hard slow. Rank 2 roots instead.
// FROST NOVA. 260, up from 95. Spells scale with dmgMult exactly as weapons do, so they were
// never falling BEHIND — they were just small: at level 38 a nova landed about one cleaver
// swing on each target, for an eight-second cooldown. A button you press once per fight has
// to be worth more than a button you press five times a second, or there is no reason to
// learn it. Against a deep-ring mob this is now most of its health rather than a fifth.
export const NOVA = { price: 175, minTier: 0, cd: 1.2, radius: 11, damage: 260, slowMul: 0.5, slowT: 3, rootT: 1.6 };
// Chain Lightning: arcs from the nearest foe to the next, damage falling each jump.
// Chain Lightning. The BOLT numbers are pure presentation and matter more than they look:
// it was a one-pixel THREE.Line alive for 120ms, and line width is ignored by most GPUs, so
// the strongest-feeling spell in the kit read as a scratch on the lens. Real geometry now —
// jagged, thick, and on screen long enough to see where it went.
export const CHAIN = {
  price: 210, minTier: 1, cd: 1, range: 34, jumps: 5, jumpRange: 15, damage: 130, falloff: 0.8,
  boltLife: 0.42,       // was 0.12 — long enough to read the whole chain, not a flashbulb
  boltWidth: 0.22,      // actual thickness, in world units
  boltSegs: 7,          // pieces per arc; more means a wilder zigzag
  boltJitter: 0.9,      // how far each joint wanders off the straight line
  boltFlicker: 0.07,    // it re-jags this often while it lives, which is what sells it
};
// Sprint: a burst of movement speed on demand (a movement spell, the first of several).
export const SPRINT = { price: 150, minTier: 0, cd: 10, dur: 4, mult: 1.7 };


// Haste — the Adept's answer to the smith's plating. Where armour makes you harder to
// kill, haste makes everything you do arrive sooner. All three terms are multiplicative
// per stack, so like armour it approaches a limit instead of crossing one.
export const HASTE = {
  price: 160,
  fire: 1.07,           // gun rounds per second, per stack
  cooldown: 0.92,       // grenade cooldown
  cast: 0.93,           // heal channel length
  castFloor: 0.45,      // ...but a channel can never become instant
};

// Rank 2s. Sold from the first ring out — the reward for leaving the Commons is not just
// bigger numbers but a better VERSION of what you already know how to use.
export const RANK2 = {
  fireringPrice: 210,
  // 1, TRACKING RANK 1. This was 11 against rank 1's 15 — the upgrade you bought WAS the
  // shorter wait. When rank 1 dropped to a one-second cooldown, that made the rank-2 spell
  // strictly worse than the free one: two hundred and ten points to wait eleven times as
  // long. An upgrade that downgrades is the worst object a shop can sell, and it is the
  // kind of bug a rank system produces every time a base number moves without its ranks.
  //
  // So rank 2 stops selling TIME and sells what it always also had: the shove. Rank 1
  // clears the room, rank 2 clears it and throws the survivors off you — which is a better
  // rank anyway by this game's own rule, since it changes what happens rather than how
  // often. Pinned to FIRERING.cd rather than written as 1, so the next person to retune the
  // base cooldown cannot re-open this hole by forgetting the rank exists.
  get fireringCd() { return FIRERING.cd; },
  dashPrice: 230,
  dashCharges: 2,        // hold two, spend both, then wait two cooldowns
};

// Abilities sold by the Adept. The first one is deliberately strong for its price: it is
// the first real power spike, and it should feel like one on the walk home from buying it.
export const FIRERING = {
  price: 90,
  // 1 SECOND, DOWN FROM 15 — Explosion stopped being an event and became a spell. See the
  // essay on ENERGY.firering, which moved to 45 in the same decision: at a one-second
  // cooldown the COST is the only brake left, which is exactly where this game keeps
  // deciding the brake belongs. A fifteen-second gate says no louder than any price could,
  // and that made the price decorative on the very spell it most wanted to matter for.
  cd: 1,
  radius: 15,
  // 252, DOWN 40% from 420 — the other half of the same trade. 420 was priced against
  // fifteen seconds of silence: a screen-clearing number you got once, which is a fair deal
  // for a button you save. Cast every second or two it would simply be the whole game, so
  // the impact comes down as the rhythm comes up. Still the widest radius in the kit, so
  // what it buys is unchanged in KIND — the room clears, it just takes more than one press.
  damage: 252,
  knock: 13,
  grow: 0.55,           // seconds for the wall of flame to reach full radius
  shove: 26,            // rank 2 only: how hard survivors are thrown outward
};

// Grenade: your answer to a crowd, and the only thing in the game that can kill YOU by
// your own hand. Supply refills on kills, so using it is rewarded by fighting, not hoarding.
export const GRENADE = {
  throwSpeed: 19,
  upBias: 0.28,          // arcs instead of flying flat
  gravity: -26,          // matches the player's, so the arc reads as the same world
  radius: 6.5,
  damage: 90,
  selfScale: 0.5,        // you take half — dangerous, not instantly lethal
  // NO COOLDOWN AT ALL. The 2.2s wait was doing the rationing back when the grenade was free;
  // now that it is a spell costing ENERGY.grenade, two other things already say no — the
  // energy and the stock you only refill by killing. A third gate on top of those is one
  // nobody can feel: whichever is slowest is the only limit that ever speaks, and the rest
  // are bars you watch instead of decisions you make. Throw all three if you like. Then you
  // have no grenades, no energy, and something is still walking at you.
  cooldown: 0,
  // Haste shrinks the throw cooldown (0.92^haste). Without a floor, enough speed drives it
  // to ~0, and you empty the whole stock in a blink -- then, since supply only ever came
  // from kills, nothing you throw has died yet and they never come back. Same shape as the
  // gun-reload bug: a rate pushed past the floor it needed. Floor it, and haste makes
  // grenades arrive SOONER instead of breaking them.
  cdFloor: 0.4,
  maxFuse: 4.0,          // safety net; ground contact is the real trigger
  max: 3,
  refillPerKill: 1,
  // A real reload, so spamming can no longer strand you at zero. Kills still refill FASTER
  // (that is the "rewarded by fighting" design), but the stock always crawls back on its
  // own -- hasted like everything else, and likewise floored so speed can never zero it.
  reload: 4.2,
  reloadFloor: 1.1,
  knockback: 11,
};

// Villagers, and the little economy that gives a sanctuary a point. Gold comes off the
// GEAR.md G1 — the additive stat model (see src/prog/stats.js for the formulas). Every value
// here is a raw number that goes ON gear; the diminishing returns are in the formulas, so
// these can grow without ever needing a clamp.
export const STATS = {
  // Health from Stamina. Base is the old flat 100; stamina on gear (G2) grows it from there.
  //
  // SOFT-CAPPED, like every other stat in this file. Stamina was the one that escaped the
  // rule: armour is armor/(armor+K), the ratings are rating/(rating+K), speed is a tanh and
  // the dash is a sqrt — all "always climbing, never linear". Stamina was `100 + 8*stam`,
  // linear and unbounded, and it was doing essentially ALL of the survivability spread: at
  // ring 5 a farmed kit's armour was worth x2.1 effective HP while its stamina was worth
  // x16. That is what let a geared player ignore a telegraph the design promised would
  // always be lethal.
  //
  // stamHp is kept as the SLOPE AT ZERO, so the first points are worth exactly what they
  // were and the early game is untouched (stam 27: 316 -> 283 hp). stamK sets where it
  // bends; stamHpCap is the ceiling it approaches but never reaches.
  //
  // BENT EARLIER (2026-07-25). The soft cap fixed the shape but left the ceiling too high:
  // a farmed survival kit still tripled the health bar, and a boss volley the design promises
  // is always lethal was something a geared player could simply eat. The lever is stamK and
  // stamHpCap TOGETHER, because the slope at zero is stamHpCap/stamK — hold that ratio at
  // stamHp and the first points keep their exact value while the ceiling comes down. So the
  // nerf lands entirely where the problem was: a fresh character does not feel it, and a
  // full Sworn set gains ~28% less health than it did.
  //   stam  10 -> 173 (was 174) ·  27 -> 273 (was 283) ·  90 -> 496 (was 567)
  //   stam 187 -> 654 (was 813) · 265 -> 722 (was 934) · 600 -> 844 (was 1177)
  baseHp: 100,
  stamHp: 8,
  stamK: 110,             // stamina at which you have half the cap
  stamHpCap: 880,         // = stamHp * stamK, so the curve's slope at 0 is exactly stamHp
  // Armour curve: DR = armor / (armor + armorK + armorPerTier*attackerTier). Tuned so the
  // old shop feel roughly ports -- 1 Heavy Plating (+45) ~13% at tier 0, 5 ~43%, 10 ~60%,
  // close to the old 0.9^n at low-mid stacks but SANE at high stacks and weaker at depth.
  armorK: 300,
  armorPerTier: 60,
  armorDRCap: 0.85,       // a rail, not a target; the formula approaches but rarely nears it
  // Primary attributes -> effect. Strength pours into GLOBAL damage; Agility into speed and
  // dash. Both are flat integers on gear; these coefficients turn a point into an effect.
  strDmg: 0.006,          // each Strength = +0.6% to ALL damage
  // Each Agility = +0.15% into the speed input, down from 0.4%. Agility still buys speed,
  // it just stops being the stat that decides what the game feels like: a big Agility roll
  // used to be worth more than the terrain, and gear should not be able to opt out of a
  // pillar. Its DASH half (agiDash) is untouched — that is a burst you aim and spend, which
  // is exactly the kind of speed this game wants to sell.
  agiSpeed: 0.0015,
  agiDash: 0.05,          // dash gains agiDash * sqrt(Agility)
  // Secondary-rating denominators (rating -> % via rating/(rating+K)). Diminishing by shape:
  // a lone 80-rating helm ~35%, and stacking more approaches but never reaches 100%.
  hasteK: 150,
  attackSpeedK: 150,
  reloadK: 150,
};

// frontier; it is only worth anything where someone will take it.
export const VILLAGE = {
  perSanctuary: 14,
  maxRendered: 180,
  keepRange: 620,
  talkRange: 3.6,
  smithBonus: 0.08,       // permanent, stacking damage from the smith
  // Armour stacks MULTIPLICATIVELY: each plate multiplies incoming damage by this, so it
  // has diminishing returns by construction and can never reach immunity. Additive
  // reduction would hit 100% at the twelfth purchase and break the game quietly.
  armorMult: 0.90,
  // Potions heal a FRACTION of your max HP, stepping up every 10 levels, so they stay a real
  // emergency button at any level instead of a flat 60 that does nothing once your pool is big.
  //   L0-9 40% · L10-19 50% · L20-29 60% · L30-39 70% · …
  potionFracBase: 0.4,
  potionFracPer10: 0.1,
  potionCap: 5,          // hold at most this many at once
  potionCd: 18,          // an emergency, not a rotation — but usable more than once a fight now
};


// THE RAID. A rival faction's town is already "cold, not hostile" — it refuses to serve you,
// and fighting is allowed on its ground (isHostileSanctuary). This makes that refusal mean
// something: the town's people take up arms against an intruder, and killing EVERY defender
// sacks the town — a boss-sized reputation payout and a fountain of loot across the streets.
//
// The defenders are a designed encounter, not a mob camp. Three champions each teach a
// different threat: the ADEPT is artillery (a five-fireball barrage — break line of sight or
// eat all five), the HERBALIST is the priority target (an AoE heal pulse on the defenders —
// kill order becomes a decision), and the QUARTERMASTER is the boss (a charge you already
// know to fear, and the most health in town). Soldiers fill out the line.
export const RAID = {
  // Musters at 150, not 90: at 90 a town was in plain sight for a hundred metres before its
  // people existed, so every approach began with an empty town — which reads as a spawn bug,
  // not a quiet moment. 150 puts the garrison on its feet beyond the minimap's rim and about
  // as far as walls resolve by eye, so a town is simply never seen unmanned.
  engage: 150,           // the garrison musters when you come this close to a faction town
  notice: 44,            // and it sees an intruder from further than a wild mob would
  // THE GARRISON — every faction town has one, yours included, bunched at the gate: a big
  // group in the town's colour that fights the faction war for real. Yours fight beside you;
  // a rival's are the raid. The mix is the mob vocabulary you already know: melee bodies,
  // casters, and chargers, so reading a garrison is the same skill as reading the field.
  // A rival town holds NO civilians at all — every body on hostile ground is a combatant —
  // so the group is sized like a war-camp, not a patrol.
  melee: 7,
  ranged: 5,
  chargers: 3,
  soldierHp: 1.5,
  // NO AMBUSH. Every town is fully manned from the moment it musters — you can see a rival's
  // war-camp, count it, and decide against it from outside the wall. What waits is not WHETHER
  // they exist but whether they have turned on you: a rival garrison holds its posts until you
  // cross the wall or draw first blood (town/raid.js arm()). The sack still begins on your
  // terms; you can just see what you are choosing now.
  adeptHp: 6,            // champions are multiples of the ring's base mob health — now the
  herbHp: 7,             // three of them are proper mini-bosses, not just bigger soldiers,
  qmHp: 14,              // the QM most of all: the wall the whole raid ends on
  qmDamage: 1.4,
  champScale: 1.9,       // champions read BIG — you should pick them out of the mob instantly
  qmScale: 2.5,          // the QM towers over the garrison
  burst: 5,              // the adept's barrage: this many fireballs...
  burstGap: 0.16,        // ...this far apart — a stream you dodge by moving, not by luck
  healEvery: 3.5,        // herbalist pulse cadence
  healRadius: 14,
  healFrac: 0.10,        // each pulse restores this fraction of every defender's max HP
  loot: 14,              // the sack fountain: field-table rolls, so mostly grays — the
                         // spectacle is the point, and reagents will take gray slots later
  // THE CHAMPIONS ARE MINI-BOSSES, AND MINI-BOSSES PAY. Each pays out ON ITS OWN DEATH —
  // rep, xp, points and a loot burst, as a fraction of what a real boss is worth — and the
  // death is DURABLE: a fallen champion stays out of every re-muster until the rebuild
  // clock runs. Before this they paid nothing and were rebuilt on every approach, so the
  // hardest fights in a raid were also the only worthless ones, killable forever for
  // nothing. The fractions ladder with the fight: the QM is the wall, so the QM is the prize.
  // QUARTERED from the first cut (0.25/0.3/0.6): three champions paid more standing than the
  // boss they were fractions of, which made raiding strictly better than the real fight the
  // ladder is supposed to be about. A full raid's champions now sum to ~0.29 of a boss —
  // seasoning on the sack's payout, not a second boss hiding in a town.
  champRep: { adept: 0.0625, herbalist: 0.075, qm: 0.15 },
  // XP and points keep the original fractions — the fight is still the fight, and only the
  // STANDING was outbidding bosses. Two dials, because they answer different complaints.
  champXp: { adept: 0.25, herbalist: 0.3, qm: 0.6 },
  champLoot: 4,          // pieces the adept and herbalist each burst on death
  champLootQm: 7,        // the quartermaster's burst — a boss-sized moment, boss-sized pile
  rebuild: 600,          // seconds a sacked town stays quiet: ~10 minutes. Long enough that
                         // you move ON to the next town instead of farming this one — which
                         // pushes you outward, where the better rewards already live
};

export const LOOT = {
  base: 4,
  perTier: 2.5,
  eliteMult: 4,
  bossMult: 45,
};

// WHAT DIES, AND WHAT IT LEAVES.
//
// Two ideas, and the gap between them is the whole reward structure:
//
//   A FIELD KILL is a lottery ticket. Almost every drop is grey, and purple is possible but
//   vanishingly so — which is exactly why it is worth having. A ticket that never pays is a
//   waste of a slot, but one that pays roughly once in an evening's hunting turns every
//   ordinary kill into a small held breath. That feeling is worth more than the item.
//
//   A BOSS is a guarantee. It is the hardest thing in the ring and it must never hand you
//   something you would sell without reading, so its drops have a FLOOR — blue at worst — and
//   a real shot at purple that grows the deeper you fight. Occasionally it gives up a SPELL
//   instead of numbers, which is the only reward in the game that changes how you play rather
//   than what your numbers say.
export const DROP = {
  // Tuned by feel rather than by taste in percentages: roughly one purple per several
  // THOUSAND ordinary kills, which is an evening or three of hunting. Rare enough that you
  // remember where you were standing; not so rare that the ticket never pays and the whole
  // idea quietly becomes decoration.
  fieldEpic: 0.0012,         // chance a field drop rolls purple at ring 0...
  fieldEpicPerRing: 0.0004,  // ...creeping up with depth.
  bossPieces: 2,             // a boss is rare enough to be worth more than a single item
  bossMinRarity: "rare",     // never worse than blue — a boss must not disappoint
  bossEpic: 0.22,            // ...and this often, purple
  bossEpicPerRing: 0.05,     // deeper bosses are the real source of epics
  bossSpell: 0.25,           // instead of a piece: an ability you do not own yet

  // How loot behaves once it is lying on the ground. (These moved here from the old RELIC
  // block when relics were removed — they were never about relics, they were about anything
  // waiting to be picked up.)
  pickupRange: 2.4,
  life: 240,                 // seconds a drop waits before fading
};

// REMOVED: the green folk — the roaming nomad bands you could not attack. They were the BODY
// layer a soul brain was meant to drive later, but as unattackable green dots wandering the
// frontier they only distracted from the things you CAN fight. When the substrate arrives it
// will drive the settlement villagers (who already have a home and a purpose), not aimless
// wanderers. src/mobs/folk.js is deleted with them.

// D7: mobs are SOULLESS. Stats roll from the ring they spawn in; no memory, no bonds, no
// substrate — the emergent layer arrives at M3 and lands on settlements, not on things you
// kill in three seconds.
export const MOB = {
  // DOUBLED from 76 — mobs were dying a touch too fast to feel like a fight, so every one now
  // takes twice as long to bring down. This is the base the ring-growth and elite factors
  // multiply on top of, so ALL mobs (field, elite, swarm, splits) got twice the health at once.
  // The early game stays fair because the GRACE bonus below still front-loads the PLAYER: a
  // fresh, gearless character is strong and fades out by ~level 12, so the longer fights land as
  // the world gets meaner rather than at the door.
  hp: 152,
  damage: 8,
  speed: 3.1,
  // They live their own lives until you give them a reason. Notice range is SHORT, and the
  // leash is measured from HOME, not from you — mirroring how the lab's souls are held by
  // their own place and people rather than by the player (world/sim.py _drift_positions).
  noticeRange: 20,
  leashRange: 62,         // drag them this far from home and they give up and go back
  loseInterest: 7.0,      // seconds out of contact before disengaging
  alertRadius: 18,        // hurt one and its KIN come from this far
  alertOthers: 11,        // anything else nearby reacts too — a scream is a scream
  homeWander: 11,         // how far they mill around their camp when idle
  homePull: 1.1,
  attackRange: 2.4,
  attackCd: 1.15,
  lungeTime: 0.28,
  lungeSpeed: 9.5,
  radius: 0.55,
  knockback: 5.5,
  knockTime: 0.45,        // how long a shoved mob stays airborne-ish
  // Casters FLY. Ranged pressure comes from the sky, which puts it outside the plane every
  // other threat lives in and finally makes pitch matter.
  flyHeight: 8.5,
  flyBob: 0.7,

  // Per-ring multipliers — D8's difficulty gradient, expressed as numbers.
  //
  // HP grows EXPONENTIALLY because player damage does. Compounding 9%/level works out to
  // ~1.41x per tier at the pace people actually level, so linear HP inevitably falls behind
  // and everything starts dying in one shot around level 30. Matching the curve holds
  // time-to-kill at ~4 shots forever: outlevel the frontier and it gets easier, run ahead
  // of your level and it bites. That relationship is the difficulty design, not a number.
  hpGrowth: 1.42,
  // The LINEAR term sets early-ring damage; the ramp below sets how it accelerates. Rings 1-3
  // were too punishing, so the linear base drops (gentle early) while rampDamage rises (still
  // brutal deep) — the acceleration does the work instead of a flat high number everywhere.
  damagePerRing: 0.30,
  speedPerRing: 0.06,

  // ACCELERATION on top of the flat curve above (see ringPressure() in gen.js). The base
  // exponentials hold time-to-kill constant; these BEND them so the first ring past the
  // Commons is barely harder and the deep climbs fast. For an on-level player that lands at
  // roughly: ring 2 ~1.1x TTK, ring 4 ~1.8x, ring 5 ~2.8x, ring 6 ~4.5x, ring 8 ~16x — so
  // "multiple bombs per regular mob" arrives around ring 5 and only worsens. An UNDER-level
  // player (run out ahead of your bed) feels it far sooner, which is the whole point of a
  // frontier. Turn these DOWN to soften the deep; they are the difficulty dial now.
  //
  // REBALANCED TWICE. First pass halved this to 0.09: the deep was bullet-sponge tanky AND
  // toothless — long fights that were also safe, the worst combination. That reasoning is now
  // stale: hard mode has since doubled incoming damage, so a long fight is genuinely dangerous.
  // Second pass (after play with a full Iron set): a geared, leveled character melts regular
  // mobs, because the flat exponential only matches an ON-PACE player — gear puts you ahead of
  // pace permanently. So the ramp comes back UP: rings 1-2 barely move (a few % — the early
  // game keeps its feel), but by the rings a geared player hunts in, mobs carry roughly twice
  // the health they did, and it keeps compounding from there. The floor (MOB.hp) is untouched —
  // the CURVE is the dial for "strong players kill too fast", never the base.
  ramp: 0.17,           // HP acceleration — the deep keeps pace with a geared character
  rampDamage: 0.38,     // damage — accelerates hard, so the deep still bites despite the lower base
  rampCrowd: 0.14,      // more bodies, sooner — reaches the population cap faster

  // ★elites: rarer near spawn, common in the deep. Valheim's star system, which is the
  // cheapest legible "this one is worse" signal there is.
  eliteChance: 0.06,
  eliteChancePerRing: 0.06,   // ring 5: 36% elite — the deep is mostly stars
  // Elites get tougher the further out they are, on TOP of the per-tier HP every mob gets —
  // so a star near spawn is a speed bump and a star in the deep is a real fight.
  eliteHp: 2.2,
  eliteHpPerRing: 0.12,
  eliteDamage: 1.5,
  eliteScale: 1.55,

  // CASTERS — a second kind of elite that fights at range. They hold a standoff and lob
  // slow fireballs in a STRAIGHT line, aimed where you were when it left their hands. That
  // makes them a pure movement problem: the counter is to be somewhere else, not to out-DPS
  // them. Mixed into a melee pack they force you to keep moving while something closes.
  casterChance: 0.55,     // of elites — ranged is the common star now, not the exception
  // 0.6 OF EVERY CASTER — and read that against the structural change beside it (spawnOne):
  // flight used to be reachable only through the ELITE branch, so however high this number
  // went, fliers were capped by the star rate at a couple of percent of the world. The old
  // 1.0 was not "every mob flies", it was "every rare star that happened to be ranged" —
  // which is why cranking it never produced a sky and cutting it never emptied one.
  //
  // Now any caster can leave the ground, so this number finally means what it says. At 0.6
  // the field measured 18% airborne; DOUBLED to 1.0 it is every caster, which puts roughly
  // a third of everything alive in the air — the sky is now the same size theatre as the
  // ground rather than a balcony over it. That also completes the split the war-targeting
  // makes (fliers only war with fliers): two armies, two floors, both worth watching, and
  // the ground caster becomes the rarity instead of the rule.
  //
  // The fliers went 1.0 -> 0.25 -> 0 -> back, and the two facts that justified the cut have
  // both been answered: the GLITCH was fixed at the source (a hover recomputing its own
  // floor mid-climb, and an easing so fast it stapled the body to your altitude — restY),
  // and the air stopped being empty of PLAYERS once the rotor and the recoil launch made
  // hovering a rotation. A sky with no predator is a refuge, and a refuge deletes the fight.
  flyChance: 1.0,
  // 0.34, up from 0.2 — a third of ordinary bodies are ranged now. This is the number that
  // actually decides how ranged the world FEELS, because ordinary mobs outnumber stars
  // fifteen to one: casterChance tunes the flavour of a rare encounter, this tunes the
  // texture of every fight. Combined with flight no longer being elite-only, it is also
  // what fills the sky — most of these take off.
  groundCasterChance: 0.34,
  flyHitScale: 2.4,       // flyers get a generous hitbox — see targets()
  castMin: 11,            // closer than this and they back off — they don't want a brawl
  castMax: 34,
  // A CASTER'S FIGHT IS ON ITS OWN FLOOR. Its whole design is a conversation at mid-range:
  // it holds a band, it glows, and you dodge or break line of sight. Every part of that
  // conversation assumes you share a floor — a wind-up thirty blocks below your feet is a
  // telegraph you cannot see, and a target thirty blocks above the band is one the band
  // means nothing against. So a ground-bound caster gives up on any target further than
  // this above or below it and goes about its business, instead of holding a range band for
  // the rest of its life against something it will never reach. That treadmill was most of
  // what "a sky full of ranged mobs" cost: not the shots — the shots mostly couldn't land
  // (castMax is 3D, and the sky starts past it) — but the hundreds of frames of a fighter's
  // full attention, spent adding nothing.
  //
  // Fliers are exempt: closing the vertical gap is their entire identity, and the red
  // diamond at your altitude is the sky's one HONEST ranged threat.
  //
  // 14: taller than any melee reach (a caster still out-guns a biter upward, so terraces
  // and mesa rims stay contested) and well inside castMax (its patience ends before its
  // range does, never the other way round — a caster that keeps caring past the edge of
  // its own shot is the treadmill again).
  // 30, UP FROM 14 — ground casters shoot UP now, and that is the second half of giving
  // the sky a predator. 14 was two storeys: a single rotor climb cleared it, so a player
  // who went up was instantly unreachable by every ranged mob in the world and the deep
  // sky became a place to stand and watch. 30 sits just under the shot's own reach
  // (castMax), which is the real ceiling — patience must end before range does, or a
  // caster spends its life aiming at something it can never hit.
  //
  // This is fair by the oldest rule in the game: a caster's wind-up is a visible tell and
  // its shot is dodgeable, so being hit at altitude is still "I didn't move" and never "I
  // couldn't have known". What it costs the flying factions is CAMPING, not mobility —
  // you can still cross, climb, and escape, you simply cannot hover over a fight and be
  // exempt from it. The sky is a route again rather than a refuge.
  castVert: 30,
  // THE SKY PUTS DOWN THE BOW. Camps that settle a sky floor mostly arrive as melee: an
  // island's garrison exists to make TAKING the island a fight, and the fight worth having
  // up there is on its deck when you arrive — not artillery leaning over the rim into a
  // war it isn't part of. This keeps roughly one archer in five, so a perch can still
  // surprise you without the air over every battle being a weather of unreadable shots.
  // Sky TOWNS and dungeons are exempt: their garrisons are designed encounters on their own
  // floor, and you are on it when you meet them.
  skyCasterKeep: 0.2,
  castCd: 3.4,
  castWindup: 0.8,        // they stop and glow before releasing: the telegraph
  // 22.5, up 50% then another 25% as the sky filled. It was tuned when a caster's target
  // stood on the same ground it did, and
  // at that range a slow ball is a fair read: you see the glow, you step, it passes. The
  // sky changed the geometry — casters shoot UP now (castVert), and a shot climbing 30
  // blocks at the old speed took long enough that a hovering player simply drifted out of
  // its path without ever deciding to. A projectile that cannot catch what it is aimed at
  // is a telegraph with no sentence after it.
  //
  // The TELL is untouched (castWindup): the wind-up is where the dodge is bought, and it
  // is the same length it always was. What changed is the price of ignoring one. That is
  // the right half of the pair to sharpen — being hit stays "I didn't move", never "I
  // couldn't have known", because the warning still arrives just as early.
  ballSpeed: 22.5,        // fast enough to punish a drift, slow enough to read the glow
  ballDamage: 24,
  ballRadius: 1.0,
  ballLife: 4.5,
  // 64, doubled with the caster population. A pool that runs dry does not queue the shot,
  // it DROPS it — silently, so a sky full of casters would wind up, glow, and fire nothing,
  // which reads as the game breaking rather than as a limit. The pool has to comfortably
  // exceed how many balls can be in flight at once, and that number just doubled twice
  // over (more casters, and each one now shooting a longer distance upward).
  ballPool: 64,

  // --- SWARM: tiny, fast, fragile, and only dangerous in numbers ------------------
  // The question it asks is "do you have a crowd answer" — Ring of Fire finally has a
  // customer, and a single-target build has to learn to back up.
  swarmPackChance: 0.26,  // of new camps
  swarmSize: [14, 22],
  swarmHp: 0.15,
  swarmSpeed: 1.55,
  swarmScale: 0.5,
  swarmDamage: 0.45,
  swarmCohesion: 2.4,     // multiplier on the flocking pull: they move as one body

  // --- CHARGER: wind up, commit, then be helpless ---------------------------------
  // The question is sidestep TIMING. Everything else punishes where you stand; this
  // punishes when you move. Its recovery is a real window, not a formality.
  chargerChance: 0.17,    // of ordinary (non-caster) mobs
  chargeRange: 27,
  chargeWind: 0.75,       // rooted and glowing before it goes
  chargeSpeed: 21,
  chargeTime: 1.15,
  chargeRecover: 1.7,     // helpless afterwards, whether it hit or missed
  chargeDamage: 2.3,      // multiplier on its own damage
  chargeKnock: 15,
  /**
   * HOW LEVEL WITH A GROUNDED BODY YOU MUST BE FOR ITS MELEE TO LAND — charge AND lunge,
   * one rule, and the reason a jump beats both.
   *
   * The charge was gated only by MOB.reachY, which is 18: a GLOBAL "how high can anything
   * fight you" number that exists to stop bodies far below shooting up at you. Applied to a
   * charge it made the hitbox a cylinder three blocks wide and thirty-six tall, and the very
   * best jump in this game reaches 7.3. So there was no height a player could ever reach that
   * a charge could not, and the one verb the whole game teaches was not an answer to the one
   * attack that most looks like it should be. You could only ever step sideways.
   *
   * 1.3 is the body's own height, and that makes the rule physical instead of arbitrary:
   * get your feet above its head and it goes underneath you. It does not need explaining in a
   * tooltip, because it is what the thing looks like it should do.
   *
   * The charge learned this rule first; the LUNGE — the standing bite of every grounded mob —
   * kept the old 18-block allowance for a while longer, which meant the ordinary attack could
   * still do the thing the spectacular one had been forbidden: reach the top of your jump from
   * a floor below. One gate now, so they cannot drift apart again. FLYERS are the deliberate
   * exception — they hunt AT your altitude, which is their whole answer to high ground, so
   * their gate is derived from the hover they actually keep (see mobs.js).
   *
   * Missing already costs it 1.7 helpless seconds, so the jump is not just a dodge — it is how
   * you buy the opening. The window is about a third of a second at the top of a jump, which
   * is tighter than it sounds until you remember the wind-up SCREAMS three quarters of a second
   * before it moves, and that spending your second jump at the apex holds you up there much
   * longer. It rewards timing and it rewards the movement kit, which is the point.
   */
  meleeClearY: 1.3,
  /**
   * ...and how level you have to be for it to BOTHER — a different question from whether it
   * connects, so a different number.
   *
   * Starting a charge never checked height at all: only flat distance. Something under an
   * island would wind up, scream, rush its full twenty-four blocks and recover, three and a
   * half seconds spent on a target it could not have touched. With the clearance above in
   * place that would have got far worse — every charger would telegraph at anyone standing on
   * a rock. And that sound is the ONLY warning this game gives for an attack that arrives from
   * off screen, so spending it on threats that are not threats teaches players to ignore it.
   *
   * Six blocks is deliberately loose: slopes and low steps still get charged, because the
   * ground between you resolves as it runs. A ledge or a deck does not. The caster forty lines
   * away in the same loop has measured this in 3D for a while — this is the charger catching up.
   */
  chargeStartY: 6,
  // The lunge's start gate, much tighter than the charge's six: a lunge travels under three
  // blocks (lungeSpeed x lungeTime), so the ground can only resolve a couple of blocks of
  // slope on the way. Committing at a target higher than that is a hop at unreachable air —
  // and, once melee could no longer CONNECT upward, it would have been every mob under every
  // ledge hopping forever at the person standing on it.
  lungeStartY: 2.5,

  // --- FACTIONS AT WAR: the cheap emergent win ------------------------------------
  // Every camp belongs to a faction (a colour). Enemy factions fight EACH OTHER, not just
  // you — so you can crest a hill onto two armies already colliding and rob the winner. It
  // reuses the aggro/steering/pack brain wholesale: a mob simply treats a near enemy-faction
  // mob as a target the way it treats you, and brawls it in melee.
  factions: 3,           // how many warring colours exist
  factionWar: true,      // toggle the whole behaviour
  // How far a town's colour reaches into the field. Camps pitched inside a town's claim fly
  // that town's colour instead of rolling their own (prog/factions territoryColorAt), so the
  // bodies outside a gate are the same army as the bodies inside it. ~3x a town's radius:
  // wide enough that the approach to a town is unmistakably its ground, narrow enough that
  // the gaps between towns stay unclaimed — and unclaimed ground is where the colours still
  // meet and fight, which is the only place the field war can actually happen. Raise this and
  // the map tidies into blocs; lower it and the war goes back to being confetti.
  territory: 140,
  warRange: 17,          // a mob engages an enemy-faction mob within this
  // How many full-radius war-target searches ONE FRAME may run. The steady load fits well
  // under this (a few hundred bodies on ~0.3s clocks is ~25 a frame); it exists for the
  // waves — clocks drifting into step and coming due together — which profiling caught
  // costing thirty times the average frame. Over-budget bodies retry a few frames later,
  // invisibly against a 0.2s rethink cadence.
  warScanBudget: 32,
  factionDamage: 0.65,   // mob-vs-mob hits for this fraction of their damage-to-you

  // --- steering: emergent movement, no substrate required -------------------------
  // The brain decides INTENT (close, hold, lunge); these decide HOW the body gets there.
  // Same seam as PLAN §4 — a mob brain and a soul brain will drive the same locomotion.
  // THE DISTANCE TICK. Every body used to pay the same per-frame price — flocking, terrain
  // probes, steering — whether it was the knife at your throat or a camp milling ninety
  // units away. In a big fight the second kind outnumbers the first ten to one: the war
  // between two camps at the edge of earshot is THEATRE, and theatre was billed at the
  // same rate as the fight you are actually in.
  //
  // So attention now costs what it is worth. A body far from you thinks on a longer stride
  // — every 2nd frame if it is fighting (the war stays believable, just cheaper), every
  // 3rd if it is calm — and each think covers the skipped time exactly, so nothing moves
  // slower, it just decides less often. Altitude counts double in "far", the same
  // philosophy as the despawn sweep: sixty blocks up is another world, not another street.
  //
  // What NEVER strides: anything committed (a lunge, a charge, a wind-up, a leap, a
  // barrage — a committed attack is a promise about where a body will be, and promises are
  // kept at full rate), and anything you just hurt — the thing you shot is the thing you
  // are looking at.
  // Tightened (64/48 -> 48/40) when the fights stayed heavy: camps spawn 22-58 out, so at
  // 64 the entire fight thought at full rate and the stride only ever trimmed the horizon.
  // 48 puts the BRAWL'S EDGE on the stride while everything you are actually trading blows
  // with stays frame-perfect — committed attacks and anything you just hurt never stride,
  // whatever their distance, so nothing that can touch you gets cheaper to watch.
  farTick: 48,            // past this (flat + 2x altitude), a FIGHTING body strides
  farStride: 2,
  calmTick: 40,           // past this, a CALM body strides longer
  calmStride: 3,
  // A GIANT fight is mostly not about you: three clans brawling means most bodies are
  // fighting EACH OTHER, and a fight you watch does not need the frame-perfect attention
  // of a fight you are in. Bodies locked on another mob stride from arm's length out —
  // anything targeting YOU, mid-attack, or that you just shot still never strides.
  warTick: 24,            // past this, a body brawling with ANOTHER MOB strides
  // THE STAMPEDE THRESHOLD: when more bodies than this are being processed around you,
  // the full-rate floors above give way — close war-brawlers halve their thinking, calm
  // bodies stretch to a third, and only what concerns YOU (committed attacks, your own
  // hunters, anything you just shot) stays frame-perfect. 200 is past the point where a
  // human can track individuals in the mass anyway; below it, the ordinary rules return.
  stampede: 200,
  // How rarely the WAR thinks during one — a brawl between two mobs updating three times
  // a second reads identically to one updating sixty, because its blows land on cooldown
  // clocks either way. This is the deepest stride in the game and it applies only to
  // fights the player is neither in nor the target of.
  stampedeStride: 3,
  neighborRadius: 10,     // who counts as "nearby" for flocking
  // In a dense pile-up, EVERY mob scanning EVERY neighbour is the O(n²) that lags. Flocking
  // only needs a SAMPLE, so we stop after this many — the motion looks identical, the cost
  // stops exploding. This is the single biggest knob for big-group performance.
  // 8, down from 12. Flocking is a SAMPLE, not a census — the spread and the shove read
  // identically off eight neighbours, and in the dense brawls where this matters most it
  // is a third of the per-body cost gone exactly where the frame is tightest.
  maxNeighbours: 8,
  separation: 2.8,        // below this they actively push apart — no stacking, ever
  sepForce: 3.4,
  alignForce: 1.0,        // match your neighbours' heading: a pack moves as one body
  cohesionForce: 0.45,    // stragglers rejoin rather than trickling in alone
  // ENCIRCLEMENT: they steer to a slot on a ring around you, not to your feet. This is
  // what makes a group spread out and surround instead of forming a queue.
  ringRadius: 6.0,
  ringForce: 2.4,
  slotSpread: 2.4,        // radians of arc a pack fans across
  // COURAGE FROM NUMBERS: alone they circle at range; in a pack they commit. Emergent
  // "they gather, then they come" — nothing scripts the wave.
  packCourage: 3,
  timidStandoff: 11.0,
  // One mob committing makes its neighbours more likely to follow within the second.
  contagion: 0.45,
  // Blocks it can step up; steeper terrain must be walked around.
  //
  // This was 1.15 when the land never rose more than a block, so it never mattered. Once
  // RELIEF put ~2-block terraces everywhere, it meant a mob could not follow you onto a
  // ledge — and standing on the nearest step became a free win against anything in the
  // game. A movement pillar that hands you an exploit is not a movement pillar.
  //
  // 2.4 is chosen against the measured terrain, not by feel: it lets a mob follow you up
  // roughly 90% of the rises in the deep rings, and leaves the top tenth — 3+ block faces,
  // spires, chasm edges — as ground they genuinely cannot take. High ground still wins you
  // fights; it just has to be high ground you FOUND, not the step you happened to be next
  // to. STOPGAP: the real answer is chargers that leap and lobbers that arc over cover,
  // so that height is a trade rather than a hiding place.
  maxClimb: 2.4,
  // How tall the burner's fire patch stands. It is a FLOOR hazard, so it is tested as a slab
  // you can be inside or above — it used to be a horizontal circle of infinite height, which
  // meant it burned you on a ledge three blocks up and at the top of a jump. Harmless when
  // the ground was flat and nobody jumped; absurd the moment the world had ledges in it.
  // 1.2 sits just under the player's 1.66-block jump, so clearing a patch mid-stride is a
  // real option and standing in one is still a mistake.
  fireHeight: 1.2,
  // YOUR OWN SIDE'S FIRE MENDS YOU. A blue pool that merely failed to hurt would be a patch
  // of ground with no reason to exist — you would learn to ignore it, which is the same as
  // not drawing it. Making it heal turns an ally's burner from scenery into a REASON TO
  // MOVE somewhere, and gives the war a shape you can stand inside.
  //
  // A fraction of your maximum rather than a flat number, so it keeps meaning the same thing
  // at level 40 as at level 4. Small on purpose: this is a trickle you hold ground in, never
  // an alternative to the heal you cast — three seconds standing in one is worth about a
  // tenth of your bar, which is a nudge, not a strategy.
  allyFireHeal: 0.035,
  // THE LEAP. maxClimb is what a body can WALK up; this is what it can throw itself over.
  // Without it, RELIEF's terraces were a wall that thinking creatures stood and stared at,
  // and the answer to every hard fight was "find a step". A leap costs them a beat of
  // commitment and gets them to you, which is the trade high ground is supposed to be: it
  // buys you TIME, not immunity.
  leapClimb: 6,         // blocks a leap can gain — well past a terrace, well under a spire
  leapReach: [3, 5, 7], // how far ahead it looks for somewhere to land
  leapDur: 0.42,        // airborne seconds; long enough to read as a jump and dodge around
  leapArc: 1.3,         // how high over the straight line it travels — the readable part
  leapCd: 1.6,          // so a body that cannot find a route does not strobe
  // How often a caster re-asks whether it can actually SEE its target. A sight line costs
  // about 4.5µs, which is nothing once and eight milliseconds a frame if every caster asks
  // every frame. Jittered per body so they never all ask on the same tick, and slow enough
  // that stepping behind a rock buys you a beat before they notice — which is the right
  // feel anyway: a moment of being missed, not an instant switch.
  losCheck: 0.45,
  // How far off the land a body has to be before we pay for the "which floor am I on"
  // question. Almost everything alive is standing on the land, and for those the cheap
  // answer is the right one — only islanders and things under an overhang need the rest.
  floorSlack: 2.5,
  // A body will hop down a terrace all day; it will not walk off a cliff. Without this, every
  // mob standing on a sky island strolled straight off the edge within seconds, because a
  // drop of any size passed the climb test — it is negative, and the test only had a ceiling.
  maxDrop: 4,
  // HOW FAR UP A MOB CAN FIGHT. Every range a mob measured was flat — the same missing
  // dimension the boss had, the fire patches had and the town walls had. On a surface it was
  // the whole truth; with a sky full of islands it means a body on the ground two hundred
  // blocks below you is at flat distance zero, so it bites you, shoots you, and charges you
  // from somewhere you cannot see and cannot reach. That is the invisible damage.
  //
  // 18 is tighter than the boss's 32 because a mob is a body, not a siege engine: it should
  // reach a ledge above it and nothing further.
  // UNUSED — a headstone, like SPIN.cdFloor and the lance's aimMult. This was the one global
  // "how far up can anything fight you" number, 18 blocks tall on every melee, and it is the
  // reason "something hit me from a level below" was ever a bug report: no jump in the game
  // reaches 8, so there was no air it did not cover. Melee now gates on meleeClearY per body;
  // ranged attacks measure honest 3D distance and need no allowance at all. Named rather than
  // deleted so the next person wondering what happened to it finds the answer.
  reachY: 18,
  // How often a body that COULD be put on an island is. Islands with nothing on them are
  // scenery; the whole argument for having them is that taking one is a fight.
  /**
   * WHERE A BODY IS BORN, in a world with several floors.
   *
   * A single "sky or ground" coin flip cannot do this job. Set it low and the upper decks
   * stay empty; set it high and it does not fill the sky so much as MOVE the world into it,
   * leaving the ground you walk across bare. Both were tried and both were wrong, because
   * the question is not how much of the world is airborne — it is what is near YOU.
   *
   * So every floor over a column competes, weighted by how close it is to the player's own
   * altitude, and the sky carries a standing multiplier on top. Standing in a valley, most of
   * what spawns is on the ledges above you rather than beside you; standing on a deck three
   * hundred blocks up, the world fills in around you there instead of far below. Nothing is
   * taken from the ground to pay for the air — the budget simply lands where you are.
   */
  // A perch is worth this many ground slots before distance is counted.
  //
  // 1.6, DOWN FROM 14. Fourteen was a thumb on the scale so heavy it broke the thing it was
  // pushing: measured over three thousand real columns, a player standing ON THE GROUND had
  // only 9% of camps spawn on the ground with them. The frontier had emptied out, and the
  // reason was this number rather than the budget.
  //
  // The altitude term below (skyAffinity) is what should decide which level fills — it
  // already prefers whichever floor you are standing on. This only exists to stop the ONE
  // ground floor being outvoted by the several sky floors stacked over every column, so it
  // needs to be a nudge, not a landslide.
  //
  // 0.8 — BELOW ONE, which is the honest expression of what this number is for. A perch is
  // not worth more than the land; there are simply more perches, three or four sky floors
  // stacked over every column against the ground's one, and an even weight per FLOOR quietly
  // means the sky wins four votes to one. Weighting each perch slightly under the ground
  // corrects for that count rather than adding a preference on top of it.
  //
  // 0.6, WALKED BACK FROM 2.2, WITH THE BUDGET WALKED BACK TO MATCH — the same pairing as
  // the raise, run in reverse, for the same reason: the two numbers only mean anything
  // together.
  //
  // 2.2 was tuned to an ask ("far more in the sky, the same on the ground") that play has
  // now reversed twice over: at 2.2 MORE THAN HALF of all camps stood in the air — measured
  // again over four thousand real columns, ground share 46% — and a big ground fight was
  // paying rent on a second, bigger fight hanging over it that mostly could not touch you
  // and that you mostly could not read. The sky's job in this game is to be a place you GO
  // — a ladder, a perch, a garrison worth taking — not where the war lives. The war lives
  // on the land, because the land is where you can read it.
  //
  // Below even the "honest" 0.8: several sky floors still stack over every column, so a
  // per-floor thumb under the land is what keeps the sky a scatter of held positions
  // rather than a crowd. Measured at 0.6: ground share 71%, and with skyCrowd walked back
  // in step the ground's ABSOLUTE count is unchanged (x1.34 base before, x1.35 after)
  // while the sky holds roughly a THIRD of the bodies it did.
  skyWeight: 0.6,
  skyAffinity: 55,      // blocks of altitude over which a floor's share falls away
  // The world grew a sky, so the crowd budget grows with it — otherwise populating the air
  // just empties the ground, and the frontier you walk through gets quieter the more there
  // is above it.
  // 1.9, DOWN FROM 2.9 — the other half of skyWeight's walk-back, derived not eyeballed:
  // this is the multiplier at which the ground keeps the exact body count it has today
  // while the sky drops to about a third. Every cost in a fight — brains, bars, dots, the
  // fleet upload — scales with the living, so this is also the single biggest lever on the
  // worst frame, pulled in the one place that was holding bodies the fight didn't need.
  skyCrowd: 1.9,
  // A FLIER CHASES IN THREE DIMENSIONS. Hovering a fixed distance over the LAND meant an air
  // mob would sail along underneath an island with you standing on top of it, which makes
  // the sky a safe place and the fliers ornaments. Chasing, it climbs to your height plus
  // this — so taking an island costs you the ground war and buys you the air war.
  flyChaseLift: 3.2,
  // HOW FAST IT LABOURS UPWARD, in blocks a second — a SPEED, replacing an eased fraction
  // that closed almost the whole gap within a second and made fliers feel stapled to the
  // player's head ("it was following the character's vertical level").
  //
  // 1.5, walked 7 -> 3 -> 1.5 in play. A flier barely climbs now: every movement verb you
  // own is several times this, so leaving its altitude is not an escape you execute, it is
  // a decision you make and then simply have.
  //
  // That is a deliberate re-pointing of what a flier IS. It is no longer a pursuer — it is
  // a body that OWNS an altitude. Meet it on its deck and it fights you; leave, and it
  // keeps the deck rather than following you off it. Which is why the two flying LAYERS
  // matter more than this number does: the sky's threat is now positional (there are
  // things up there, at known heights, and you choose whether to be among them) rather
  // than adhesive (a thing that comes wherever you go).
  //
  // What keeps that from being an exemption is the GROUND: casters shoot thirty blocks up
  // and do not care what altitude you picked. You can out-climb the pursuer; you cannot
  // out-climb the pressure.
  flyClimbSpeed: 1.5,
  // HOW LONG IT COMMITS TO A READING of your altitude before taking another. The speed cap
  // above was only half the fix — a body climbing at a fixed rate toward your LIVE height
  // is still a servo, just a slow one. This is the reaction time that makes it a creature:
  // leap while it is committed and it finishes climbing to where you were.
  //
  // 4, up from 1.8 (and 1.8 was already the fix for "it follows perfectly"). Four seconds
  // is long enough to be a CHARACTER TRAIT rather than latency: these things are slow to
  // notice and slow to move, which is what makes catching one at your own altitude feel
  // like you chose the fight. Combined with the crawl above, a body that loses your height
  // has effectively lost you — and the honest consequence is that fliers are now something
  // you go and kill rather than something that arrives.
  flyChaseDelay: 4,
  flyClear: 3,          // never closer than this to the land, whatever its deck says
  // THE MEANDER — how hard a hunting flier refuses to hold a fixed point, and how fast its
  // circle turns. Read the essay at the call site: a hovering body that settles into its
  // firing band is a turret bolted to the sky, and a turret is something you shoot at your
  // leisure. The wander is deliberately weaker than the band-keeping force, so it perturbs
  // the caster's brain rather than overriding it — it wobbles the aim point, it does not
  // decide where the aim point is.
  flyWander: 1.0,
  flyWanderRate: 0.85,
  // TWO DECKS OF SKY, measured from wherever YOU are — which is what keeps the air stocked
  // as you travel and, more importantly, as you CLIMB. Fliers used to be dealt onto
  // whatever floor their camp stood on, so the sky was only populated where the world
  // happened to provide a shelf, and going above the terrain meant going somewhere empty.
  // Flight does not need a floor; that was the last place the old one-surface thinking was
  // hiding.
  //
  // Two, not one, because a single altitude is a ceiling and two is a STAIRCASE: you can
  // be fighting the low deck while the high one wheels above you, climb into it, and leave
  // the first fight below. That is the same lesson the named rings teach horizontally — a
  // gradient you can SEE beats a gradient you can only measure.
  //
  // 16 is a rotor climb away; 44 is a recoil launch away. Both numbers are deliberately
  // pinned to a movement verb, so each deck is a place one of your tools can actually take
  // you rather than an arbitrary height.
  flyLayers: [16, 44],
  flyLayerJitter: 5,    // spread within a deck, so a layer reads as a band not a sheet

  avoidArc: 1.05,         // radians it will veer to find a walkable line

  // Population around the player. Cost is bounded by COUNT, not by world size.
  // Packs, not scattered individuals: camps that mill, flock, and BREED.
  //
  // Population scales with TIER as well as being large: the deep is not just meaner, it is
  // more CROWDED. That reinforces D8's gradient with density instead of only with stats,
  // and it's why walking out feels like pressure rather than arithmetic.
  // The tier-0 BASE is deliberately calm — the Commons is where you learn the game, and it
  // read as a swarm. The crowd ramp (rampCrowd) climbs off this base fast, so ring 1 is
  // already busier and the deep still fills to the cap; only the first level is quieter.
  // Tier 0 was BOTH the most crowded AND the hardest, which is backwards for a learning zone.
  // The count drops hard at the base and the ramp steepens to make it up, so the Commons is
  // a handful of mobs you can read while the deep stays a horde. (GEAR.md G5/G6 take this
  // further into the MMO direction: fewer, meatier mobs.)
  // TRIMMED ~22% (188/114 -> 146/90) when the sky emptied, because the war CONCENTRATED:
  // bodies that used to spread across three floors above you now almost all stand on
  // yours, so a pool that felt right split across theatres reads as a flood delivered to
  // one ("waaaay more enemies spawning on the ground"). The pool was sized for two
  // theatres; it is one theatre now, and it shrinks toward its one-theatre size — the
  // ground keeps a real horde, it just stops receiving the sky's share of it too.
  maxAlive: 146,          // scaled by MOB.skyCrowd — see budget()
  // 60, DOWN FROM 90 — the deep-water flood, drained (2026-07-27, from level-50 play on a
  // laptop: "so many mobs it's just overwhelming"). Density-as-difficulty stops working
  // past the point where the crowd stops being READABLE: at fifty levels deep the world
  // held over a thousand bodies, which for the one faction that must STAND IN the fight
  // is not pressure, it is weather — and it is also the single biggest number behind the
  // worst frame. GEAR.md already chose this direction (fewer, meatier mobs); the depth
  // keeps its menace through stats, elites and affixes, which scale forever anyway.
  maxAlivePerTier: 60,    // deep rings ride the cap
  // Raised with the sky. The deep rings sit ON this cap, so skyCrowd alone would have done
  // nothing out there — the extra bodies the air needs would have been taken straight off the
  // ground instead of added.
  // 1900, WALKED BACK FROM 2940 in step with skyCrowd (2940 x 1.9/2.9). The old essay here
  // promised this was "the number to walk back first if the deep rings ever stutter" — the
  // deep rings stuttered, and a promise a config makes to its future self is kept or it
  // was never worth writing. The deep rings ride this cap, so the deep-ring horde thins by
  // the same third the rest of the world did — and stays a horde.
  // ...then to 1500 riding the one-theatre trim, then to 900 with the deep-water drain
  // (see maxAlivePerTier): the cap is where the deepest rings actually live, so it is
  // the number a level-50 session breathes through.
  maxAliveCap: 900,
  maxPacks: 23,
  maxPacksPerTier: 18,
  maxPacksCap: 196,
  packSize: [9, 18],      // a camp is a crowd, not a squad
  packCap: 26,            // and it can breed to this
  breedEvery: [35, 80],   // seconds between a mob's offspring (idle only, never mid-fight)
  // Tighter band than before: camps sat 32-88 units out, which put most of them past the
  // fog and made the world read as empty. 22-58 keeps several in sight at once.
  spawnMin: 22,
  spawnMax: 58,
  // 140, UP FROM 105 — every mob lasts longer and reaches further before fading, asked
  // for in play after bodies kept evaporating mid-fight. This is affordable now in a way
  // it was not this morning: the population itself was cut hard (maxAlive, maxAlivePerTier,
  // the cap) for the laptop, so a wider circle holding fewer bodies costs less than the
  // old tight circle packed with them. What it buys is that the world stops rearranging
  // itself just outside your notice — camps you walked past are still there when you turn
  // around, and a fight you backed away from is still a fight when you come back.
  despawn: 140,
  // ALTITUDE COUNTS, AND COUNTS DOUBLE. The sweep above was flat distance, which was the whole
  // truth while the world was a surface. With a sky full of islands it meant that climbing to
  // a perch left every mob on the land below you inside "nearby" — ten metres away across the
  // map, sixty metres straight down, unreachable by either of you, and holding a slot in a
  // budget that counts EVERY living mob. The upper levels were not under-spawning; they had
  // nowhere to spawn INTO, because the ground crowd never let go of the allowance.
  //
  // Doubled rather than merely counted, because vertical separation matters more than
  // horizontal: you can walk sixty metres, but sixty metres down is a different level of the
  // world with its own fight on it. At x2 a mob is swept by roughly 52 blocks of pure
  // altitude. That has to sit comfortably UNDER a layer's separation or arriving on a level
  // fails to clear the one you left: the median first island stands 59 blocks over the land,
  // and x2 swept at 52.5 — a six-block margin, which the lower half of the distribution would
  // have eaten. x2.4 sweeps at ~44 and keeps the whole layer.
  //
  // Nothing that could actually fight you is anywhere near this line: MOB.reachY is 18, so a
  // body 44 blocks above or below you was already unable to touch you, and you it.
  // 1.5, DOWN FROM 2.4 — the doubling was written for a world that no longer exists, and
  // it had started deleting fights. Its argument was sound at the time: the sky held half
  // the war, so climbing to a perch left a hundred unreachable bodies on the land below
  // holding budget slots. Two things have changed since. The sky was emptied (skyWeight,
  // flyChance 0), so there is no longer a second theatre stacked overhead to protect the
  // budget from — and FLIGHT BECAME A VERB: the lance's rotor and the cannon's recoil
  // both throw you tens of blocks up, mid-fight, on purpose. At 2.4 a rocket jump over
  // your own brawl measured every enemy in it as a hundred blocks away and swept them.
  // The game was punishing the exact movement it had just been built to sell.
  //
  // Altitude still counts for MORE than horizontal, because it should — sixty blocks down
  // is a different level of the world with its own fight on it. It simply no longer counts
  // so much that jumping is a way to delete the thing you are fighting.
  despawnVScale: 1.5,
  // A FIGHT YOU STARTED DOES NOT EVAPORATE. Reported in play: sniping with the lance, a
  // wounded body simply faded, and the only way to finish it was to walk toward the thing
  // you had deliberately engaged from range. That is the sweep punishing the one playstyle
  // the longest-ranged weapon in the game exists for — and worse, it punishes it silently,
  // so it reads as the mob escaping rather than as a budget doing its job.
  //
  // The altitude doubling above is what made it bite so early: a body 80 out and 40 BELOW
  // measures as 160, so a downhill shot from a perch could cull a target well inside the
  // lance's own 78-block reach. Correct for the budget, absurd for the fight.
  //
  // So: anything the PLAYER has damaged holds a grace period, and while it lasts the body
  // is swept on a far longer leash instead of the ordinary one. Not immortal — see
  // engagedDespawn — because a mob that outlived the ground it stands on is a worse bug
  // than the one this fixes.
  engagedGrace: 45,       // seconds a body remembers you hit it
  // THE LONG LEASH, and it is pinned to the WORLD rather than chosen: VIEW_RADIUS chunks
  // of terrain are loaded around you (7 x 16 = 112 blocks), and this sits just inside the
  // far corner of that disc. The rule it encodes is the one asked for in play — an engaged
  // body survives exactly as long as the ground it is standing on does. Past this the
  // chunk itself is gone, and keeping a body alive over unloaded world means it is
  // standing on nothing, falling forever, and still holding a slot in the alive budget.
  // Flat, deliberately: no altitude doubling on this one, or the vertical exaggeration
  // that caused the original complaint would come straight back in through the fix.
  engagedDespawn: 150,
  // Deeper rings repopulate faster as well as holding more: a camp you clear at tier 8
  // is replaced almost at once, so the frontier never feels emptied.
  // 0.18, down from 0.3 — the budget only matters if the world can REACH it. A camp every
  // third of a second took the best part of a minute to fill a deep ring, which is most of
  // the time you spend in one; the population was right on paper and thin in practice.
  spawnInterval: 0.18,
  spawnFasterPerTier: 0.12,   // interval x (1 - this)^tier, floored below
  spawnIntervalMin: 0.06,
};

// D10 — the giant boss. ONE reusable rig, re-dressed per ring. Everything here is tuned
// around a single rule: the fight must be long enough that its pattern becomes legible,
// and every source of damage must be avoidable by a player who reads the telegraph.
export const BOSS = {
  // HP COMPOUNDS, like the mobs'. The curve was matched to LEVELS alone — but gear and relic
  // damage are uncapped and multiply on top, so a player who stacked sharpen deleted bosses
  // that the maths said should last five rotations. That is exactly the "bosses die super
  // fast" you hit. Two answers: a higher base (the shallow fight), and a depth RAMP so bosses
  // accelerate alongside the now-accelerating trash instead of becoming the softest thing on
  // the ring. The ramp is deliberately GENTLER than the mobs' HP ramp — a boss already lasts
  // ~22s, so mob-grade acceleration would turn the deep ones into minutes of tedium.
  //   tier 1: 5680 · tier 3: 14100 · tier 5: 46600 · tier 8: ~471000
  hp: 4000,
  hpGrowth: 1.42,
  ramp: 0.10,            // see ringPressure(); << MOB.ramp on purpose — bosses tank, not sponge

  // TOUGHNESS — the answer to uncapped gear, and why it does NOT punish an ungeared player.
  //
  // A flat "damage taken x0.7" would be a lie: mathematically it is identical to giving the
  // boss more HP, so it hits the level-baseline damage exactly as hard as it hits the gear
  // bonus, and an ungeared player just fights a longer fight for no reason. What actually
  // separates a geared player from a bare one is BIG PER-HIT NUMBERS. So the boss caps the
  // damage any SINGLE hit may deal to a fraction of its max HP: small hits sail under it
  // untouched, burst gets clamped. A whale can no longer delete a boss in three buttons, an
  // ungeared player never even notices the cap exists, and the floor on a fight becomes
  // "1 / fraction" hits no matter how absurd your sharpen stack.
  //
  // It scales with tier two ways: the cap is a fraction of a tier-scaled HP pool, and the
  // fraction itself tightens with depth — so the deep bosses are the hardest to burst.
  // How long the boss health bar stays up after the last blow landed either way. Long
  // enough to cover a full disengage — dodge out, heal, reload, come back — because a bar
  // that blinked off every time you stopped shooting would be worse than one always on.
  // Short enough that walking away from a fight clears the top of the screen.
  // HOW FAR UP THE FIGHT REACHES. Every distance a boss measured was flat — Math.hypot of x
  // and z — which was the whole truth while the world was a surface. With a sky full of
  // islands it meant a boss standing under you at ground level read as being AT your feet:
  // it charged, beamed and clubbed you from a hundred blocks below, and its meteors landed on
  // an island you were not standing on.
  //
  // 32 is chosen to keep the fight honest rather than to end it. A boss is ~10 tall, its
  // meteors fall from overhead, and dropping onto one from a ledge should absolutely still be
  // a fight — so anything within a few storeys is in reach. Above that you are not fighting
  // it, you are looking at it.
  reachY: 32,
  barHold: 10,

  // LETTING GO. Running away used to mean nothing until you cleared aggroRange — ninety
  // metres of being shelled by something you had already decided to leave alone. Lowering
  // that range is the wrong fix: it is also the range at which a boss NOTICES you, and a boss
  // you can walk up to unmolested is not a boss.
  //
  // So disengaging is a separate question from distance alone: it lets go when you have not
  // hurt it for giveUp seconds AND you are past releaseRange. Both halves matter. Fighting it
  // toe to toe never triggers it however long the fight runs, and neither does backing off to
  // reload and coming straight back in — that is a rotation, not a retreat. But turn and run
  // without shooting, and it stops rather than following you across the ring.
  //
  // The clock is refreshed by YOUR damage only, never by its own hits landing on you.
  // Refreshing on both would mean a boss that is shooting you keeps its own reason to shoot.
  // Deliberately LOOSE. The fight as it stands is good, and the only thing being fixed is the
  // tail: ninety metres of shelling after you had plainly left. Five seconds untouched AND
  // forty-five metres out is unmistakably a retreat — you cannot reach it by repositioning, by
  // reloading, or by any pause inside a real fight. Everything before that point is unchanged.
  giveUp: 5,
  releaseRange: 45,
  maxHitFraction: 0.03,     // ring 1: no single hit may exceed 3% of max HP (~34-hit floor)
  hitCapTighten: 0.06,      // and that shrinks: fraction / (1 + this * ring)

  // EVADE. Run past aggroRange and the boss disengages: it drops every telegraph and heals
  // back to full, so you can't chip it down and stroll away between fights. Same idea as a
  // WoW boss resetting when you leash it out. regenFrac is fraction of MAX HP per second, so
  // a full reset takes ~1/regenFrac seconds regardless of the boss's tier.
  regenFrac: 0.12,          // ~8s from near-death back to full once you've left
  // And it hits harder as you go out. A longer fight against fixed damage is an EASIER
  // fight; the deep should not be safer just because it takes longer.
  damagePerTier: 0.18,
  speed: 1.7,             // slow — you can always outrun it; the meteors are the threat
  scale: 6.0,
  contactRange: 6.5,
  contactDamage: 26,
  contactCd: 1.4,
  weakMultiplier: 2.5,    // the glowing core: aim is rewarded, spraying is not
  aggroRange: 90,
  // Out in the ring, not on top of you. Past aggroRange (90) so a boss appears at a distance
  // — you spot it on the minimap and GO to it, rather than it materialising in your face.
  spawnDist: [110, 165],
  spawnRing: 1,           // no bosses in the Commons — it stays the safe ground
  retry: 12,              // seconds between spawn attempts once you're eligible
  despawn: 250,           // wider than spawnDist, so a boss you're walking toward won't vanish

  // Meteor volleys.
  // The boss alternates volley -> beam -> volley. They ask opposite questions: meteors
  // punish predictable movement, the beam punishes stillness. Together you have to keep
  // moving without moving in a straight line.
  beamWarm: 1.15,         // telegraph before it burns
  beamTime: 5.0,          // how long it hunts you
  beamRadius: 3.2,
  beamDps: 46,
  beamSpeed: 6.0,         // just under a level-1 walk (6.3): moving escapes, standing cooks
  beamSpeedPerTier: 0.5,  // deeper tiers close the gap, so your speed upgrades stay a reward
  volleyCd: 4.6,
  chargeTime: 1.25,       // audible + visible wind-up BEFORE the ground markers appear
  roarEvery: [7, 13],     // ambient roars while it's alive and near — dread on a timer
  volleyCount: 5,
  volleyPerRing: 1,
  phase2At: 0.5,          // below this HP fraction: faster volleys, more rocks
  phase2Rate: 0.6,
  phase2Bonus: 3,

  // TELEGRAPHED DAMAGE IS A FRACTION OF YOUR MAX HP — but never LESS than the flat,
  // ring-scaled number above. `max(flat, frac * maxHp)` gives both designs at once:
  //
  //   - the flat term is the DEPTH term and is unchanged, so an under-geared player walking
  //     out too far is punished exactly as hard as before (ring 5 bare: still 1.5 meteors);
  //   - the fraction only ever BINDS on someone who out-stacked it, which is the only case
  //     that was broken. Farmed kit at ring 5 went from 51 meteors-to-die to ~6.
  //
  // This is what keeps D10's promise honest at every gear level: "a meteor is as lethal at
  // level 40 as at level 4". Armour still reduces it (armour is bounded by its own curve, so
  // it can only ever be worth ~2x, which is a reward rather than an exemption). Note the game
  // already treats RESTORATION this way — HEAL.fraction and the potions are both %max-HP —
  // so this is the damage side finally matching the healing side.
  //
  // Untelegraphed damage (trash melee, fireballs) stays FLAT on purpose: chip damage is what
  // Stamina is legitimately for. The line is telegraph, not source.
  meteorFrac: 0.34,       // ~2.9 rocks to die — exactly what a level-1 player feels today
  beamFrac: 0.30,         // per second in the beam
  contactFrac: 0.26,      // walking into the boss

  meteorTelegraph: 1.30,  // seconds the ground marker shows BEFORE the rock lands
  meteorFall: 0.45,       // seconds from sky to impact once it's committed
  meteorHeight: 46,
  meteorRadius: 3.6,
  meteorDamage: 34,
  meteorScatter: 9,       // spread around the aim point
  meteorAtPlayer: 0.6,    // fraction aimed at you; the rest rain around the boss
  shake: 0.55,
};

// Dodge-roll. i-frames are the point of it; the burst of speed is what makes it read.
export const DODGE = {
  speed: 15.0,
  time: 0.30,
  iframes: 0.22,
  cooldown: 0.70,
  // Double-tap window. Too long and ordinary strafing triggers rolls you didn't ask for;
  // too short and deliberate taps get eaten. 280ms is the usual comfortable middle.
  doubleTapMs: 280,

  /**
   * THE WALL KICK. Roll into a wall and you go UP it instead of stopping against it.
   *
   * A dodge that ends in a thud is the one place the movement stopped being a conversation
   * with the terrain: everywhere else in this game a wall is something to read and use, and
   * here it was a full stop. Since the auto step-up (tryStep) already swallows anything knee
   * height, ANY surface still blocking a roll is genuinely a wall — which makes "was that
   * worth kicking off" a question the terrain has already answered.
   *
   * Up AND out, not just up: a purely vertical launch would paste you to the wall and leave
   * you sliding back down it. Kicking away at an angle is what turns two walls into a route
   * and what makes a single wall a way to gain height and change direction at once.
   *
   * A LEAP, NOT A HOP — and thrown DIAGONALLY, with more push across than up.
   *
   * The first version was deliberately weaker than a jump, which was the wrong instinct: a
   * kick that gains less height than simply jumping is a worse option than the one you
   * already had, so nobody would ever aim a roll at a wall and the wall stayed a full stop
   * with extra steps. To be worth doing, it has to give you something no other move can.
   *
   * And what it gives is DISTANCE with height attached, not a boost straight up. A vertical
   * launch pins you to the face you just kicked and drops you back down beside it, which is
   * a lift, not a move. Out ~15 against up ~12.5 puts the launch near forty degrees: it
   * clears about three blocks while carrying you fourteen across, so a wall becomes a way to
   * cross a chasm, reach the ledge opposite, or leave a fight — a redirection you aim, which
   * is what the roll was always for.
   *
   * What keeps it honest is not the size but the COST: it spends the roll, which is a 0.7s
   * cooldown and a double-tap. Scaling a tall face means kick, fall, land, tap-tap, kick —
   * a rhythm you can drop, not a ladder you ride.
   */
  kickUp: 12.5,           // vertical launch off the wall — ~3.0 blocks of height
  kickOut: 15.0,          // and how hard it throws you ACROSS — the larger half, on purpose
  // HOW LONG THE LAUNCH OWNS YOU. Without this the outward half simply did not exist: the
  // movement blend runs every frame in the AIR as well as on the ground, so with no key held
  // it pulled the kick's horizontal speed to nothing within about five frames and a 15-unit
  // throw became six tenths of a block. The dodge, the dash and the wall slide all solve this
  // the same way — they own velocity for a fixed window — so this does too, and for the same
  // reason: an impulse you can accidentally cancel by not holding a key is not a move.
  kickHold: 0.5,

  // The roll SCALES now (see applyLevelStats -> player.dashMult). It gets both faster and
  // farther — the i-frame window is unchanged, so a bigger dash covers more ground inside
  // the same protection, which is pure mobility, not more safety. Two sources, each with
  // sqrt diminishing returns: always growing, never linear, no hard ceiling (faith with the
  // no-limits rule), but the tenth stack is worth a fraction of the first.
  //   speedGain: ANY speed increase — levels, Lighten, Swiftness relics — lengthens the dash
  //   dashStatGain: the dedicated Vault stat you buy or find
  speedGain: 0.5,
  dashStatGain: 0.22,
};

// D3/D4: three camera states. AIM blends to first person so steep upward aim stops
// fighting the over-shoulder rig; the blend (not a cut) is what makes it feel good.
export const CAMERA = {
  fov: 72,
  aimFov: 60,
  thirdPersonDist: 4.2,
  // 0 = camera dead behind you, character centred (Zelda/Mario framing).
  // >0 offsets to the right, putting the body left of centre (Gears/Fortnite framing) —
  // that exists so the crosshair isn't behind your own head, which is a problem this game
  // doesn't have: aiming blends to first person anyway (D4). Centred it is.
  shoulder: 0.0,
  height: 1.55,
  aimBlendTime: 0.17,   // seconds — BOTW-ish
  minPitch: -Math.PI / 2 + 0.05,
  maxPitch: Math.PI / 2 - 0.05,
  // Radians of turn per pixel of mouse travel. Tune live in-game with [ and ] — feel is
  // not a thing to guess at in a config file. This value is just the starting point.
  // Radians of turn per pixel of mouse travel.
  //
  // BACK TO 0.004 after trying 0.009. The report that drove it up ("vertical does not work,
  // everything is too slow") turned out to be a BROWSER problem, not a speed problem — the
  // game was being played in Firefox, where mouse look misbehaves. Raising the default
  // treated a symptom that was never really about this number, and on Chrome it made the
  // game unplayably fast.
  //
  // Worth remembering as a general thing: when a report is "X feels wrong", changing the
  // number that controls X is the obvious move and often the wrong one. The number was fine.
  //
  // Note the saved value lives PER SITE, so tuning this while developing on localhost does
  // nothing for anyone playing the build you hand out — they all get this default. That is
  // what the slider on the pause screen is for.
  sensitivity: 0.004,
};
