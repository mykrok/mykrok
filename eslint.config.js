import globals from "globals";

export default [
  {
    files: ["src/mykrok/assets/map-browser/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        // Leaflet globals
        L: "readonly",
        // Chart.js globals
        Chart: "readonly",
      }
    },
    rules: {
      // Possible Problems
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_", "caughtErrorsIgnorePattern": "^_|^e$" }],
      "no-undef": "error",
      "no-duplicate-case": "error",
      "no-empty": "warn",
      "no-extra-semi": "error",
      "no-func-assign": "error",
      "no-irregular-whitespace": "error",
      "no-unreachable": "error",

      // Suggestions
      "curly": ["error", "multi-line"],
      "eqeqeq": ["error", "always", { "null": "ignore" }],
      "no-var": "error",
      "prefer-const": "error",

      // Layout & Formatting (minimal - let prettier handle most)
      "semi": ["error", "always"],
      "indent": ["error", 4, { "SwitchCase": 1 }],
      "quotes": ["error", "single", { "avoidEscape": true }],
    }
  },
  {
    files: ["tests/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.jest,
      }
    },
    rules: {
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
      "no-undef": "error",
      "semi": ["error", "always"],
    }
  }
];
