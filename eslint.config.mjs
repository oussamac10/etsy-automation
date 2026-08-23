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
      "**/.agents/**",
      "**/.claude/**",
      "**/.gemini/**",
      "**/.serena/**",
      "**/strix_runs/**",
      "**/scratch/**",
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
      // Dynamic payload schemas from external APIs (Etsy/USPTO) require flexible shapes.
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
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
        $fetch: "readonly",
        computed: "readonly",
        createError: "readonly",
        defineEventHandler: "readonly",
        defineNuxtConfig: "readonly",
        definePageMeta: "readonly",
        defineProps: "readonly",
        defineEmits: "readonly",
        navigateTo: "readonly",
        nextTick: "readonly",
        onMounted: "readonly",
        onUnmounted: "readonly",
        ref: "readonly",
        showError: "readonly",
        useAsyncData: "readonly",
        useCookie: "readonly",
        useHead: "readonly",
        useLazyFetch: "readonly",
        useRequestHeaders: "readonly",
        useRoute: "readonly",
        useRouter: "readonly",
        useRuntimeConfig: "readonly",
        useSeoMeta: "readonly",
        watch: "readonly",
      },
    },
    rules: {
      // Nuxt auto-imports pages/layouts whose names are single words.
      "vue/multi-word-component-names": "off",
      // Pure formatting & template style rules. The toolchain does not enforce Vue formatting.
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/multiline-html-element-content-newline": "off",
      "vue/html-indent": "off",
      "vue/html-self-closing": "off",
      "vue/attributes-order": "off",
      "vue/attribute-hyphenation": "off",
      "vue/first-attribute-linebreak": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/html-closing-bracket-spacing": "off",
      "vue/html-comment-content-spacing": "off",
    },
  },

  // Tests may log and use looser typing helpers.
  {
    files: ["**/*.{test,spec}.{ts,tsx}", "**/tests/**/*.ts", "**/e2e/**/*.ts"],
    rules: {
      "no-console": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);

