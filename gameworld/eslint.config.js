// D14 is enforced here, not by good intentions: Math.random() is unseedable, and an
// unseedable world makes the falsifier harness (PLAN.md §5) impossible to write.
export default [
  {
    files: ["src/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        window: "readonly", document: "readonly", performance: "readonly",
        requestAnimationFrame: "readonly", console: "readonly", localStorage: "readonly",
        setInterval: "readonly", clearInterval: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly", addEventListener: "readonly",
        innerWidth: "readonly", innerHeight: "readonly", devicePixelRatio: "readonly",
        navigator: "readonly", fetch: "readonly", Worker: "readonly", URL: "readonly",
        EventSource: "readonly", AudioContext: "readonly", Audio: "readonly",
      },
    },
    rules: {
      // ON, and load-bearing: a missing import builds cleanly under vite and only explodes
      // at runtime. With no browser automation in this session, static checks are the only
      // safety net there is — `PLAYER` was already missing from main.js when this landed.
      "no-undef": "error",
      "no-restricted-properties": ["error", {
        object: "Math",
        property: "random",
        message: "Banned (PLAN.md D14). Use src/rng.js — every roll in this game must be seeded.",
      }],
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
];
