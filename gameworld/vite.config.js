import { defineConfig } from "vite";

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
});
