import { defineConfig } from "vite";
import { appendFileSync } from "node:fs";

export default defineConfig({
  // RELATIVE paths, not absolute.
  //
  // By default Vite writes `<script src="/assets/index-abc.js">` into the built page, which
  // assumes the game is served from the ROOT of a domain. That is true of `npm run preview`
  // and untrue of most places you would actually put it: itch.io serves HTML games from a
  // subfolder, so a leading slash points at the top of the CDN instead of at the game, the
  // script 404s, and the page loads to an inert frame with nothing to click and no error a
  // player could act on.
  //
  // "./" makes every reference relative to the page itself, which is correct at a domain
  // root AND in a subfolder. There is no case where the absolute form is needed and this one
  // is not, so it is simply the right default for a game meant to be handed to people.
  base: "./",

  // THE AUDIO BLACK BOX — dev only, never in a build. Chasing "the voices stutter then die"
  // by asking the player to read debug numbers mid-fight failed three times running, so the
  // game reports its own audio vitals here (sfx.js, DEV-gated) and they land in a log file
  // the toolchain can read while the session is still going. A flight recorder, not a
  // feature: delete this plugin and the game does not change.
  plugins: [{
    name: "audio-blackbox",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__vitals", (req, res) => {
        let body = "";
        req.on("data", (c) => { body += c; });
        req.on("end", () => {
          try {
            appendFileSync(".vitals.log", body + "\n");
          } catch { /* a lost heartbeat is fine */ }
          res.statusCode = 204;
          res.end();
        });
      });
    },
  }],
});
