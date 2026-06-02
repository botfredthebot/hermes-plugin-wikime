const js = require("@eslint/js");

module.exports = [
  js.configs.recommended,
  {
    files: ["dist/index.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        React: "readonly",
        __dirname: "readonly",
      },
    },
    rules: {
      "no-shadow": "error",
      "no-unused-vars": "warn",
      "no-undef": "warn",
      "no-redeclare": "error",
    },
  },
];
