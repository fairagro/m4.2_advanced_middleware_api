/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // Renovate uses commitMessagePrefix "deps:" (shared renovate.json).
    "type-enum": [
      2,
      "always",
      [
        "build",
        "chore",
        "ci",
        "deps",
        "docs",
        "feat",
        "fix",
        "perf",
        "refactor",
        "revert",
        "style",
        "test",
      ],
    ],
  },
};
