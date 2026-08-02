// Flat ESLint config shared by every TypeScript workspace in the monorepo.
// Type-aware linting is deliberately off here: `pnpm typecheck` runs tsc per
// workspace, so ESLint stays fast and does not need a project graph.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import vue from "eslint-plugin-vue";
import vueParser from "vue-eslint-parser";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.nuxt/**",
      "**/.output/**",
      "**/coverage/**",
      "**/.venv/**",
      "**/playwright-report/**",
      "**/test-results/**",
    ],
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.node },
    },
    rules: {
      // CLAUDE.md: "no unexplained `any`" — force an inline justification.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports" },
      ],
      eqeqeq: ["error", "always"],
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },

  // Vue SFCs in frontend
  ...vue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 2023,
        sourceType: "module",
        extraFileExtensions: [".vue"],
      },
      globals: {
        ...globals.browser,
        // Nuxt auto-imports and compiler macros.
        computed: "readonly",
        defineEventHandler: "readonly",
        defineNuxtConfig: "readonly",
        onMounted: "readonly",
        ref: "readonly",
        useRuntimeConfig: "readonly",
      },
    },
    rules: {
      // Nuxt auto-imports pages/layouts whose names are single words.
      "vue/multi-word-component-names": "off",
      // Pure formatting rules. The toolchain has no Vue formatter, so these
      // would only produce noise that never fails a build.
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
    },
  },

  // Tests may log and use looser typing helpers.
  {
    files: ["**/*.{test,spec}.{ts,tsx}", "**/tests/**/*.ts", "**/e2e/**/*.ts"],
    rules: { "no-console": "off" },
  },
);
