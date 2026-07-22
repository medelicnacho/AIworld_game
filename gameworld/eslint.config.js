// D14 is enforced here, not by good intentions: Math.random() is unseedable, and an
// unseedable world makes the falsifier harness (PLAN.md §5) impossible to write.
export default [
  {
    files: ["src/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { window: "readonly", document: "readonly", performance: "readonly",
                 requestAnimationFrame: "readonly", console: "readonly" },
    },
    rules: {
      "no-restricted-properties": ["error", {
        object: "Math",
        property: "random",
        message: "Banned (PLAN.md D14). Use src/rng.js — every roll in this game must be seeded.",
      }],
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
];
