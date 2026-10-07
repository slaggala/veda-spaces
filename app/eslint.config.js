// ESLint for the workspace (12 §5 PR gate "lint: unsafeHTML, import boundaries"; IR-39).
import js from '@eslint/js';
import lit from 'eslint-plugin-lit';
import wc from 'eslint-plugin-wc';
import globals from 'globals';
import tseslint from 'typescript-eslint';

const sinks = [
  { object: 'document', property: 'write', message: 'No document.write.' },
  { property: 'innerHTML', message: 'Use Lit templates or textContent, never innerHTML.' },
  { property: 'outerHTML', message: 'Use Lit templates, never outerHTML.' },
  { property: 'insertAdjacentHTML', message: 'Use Lit templates, never insertAdjacentHTML.' },
];

export default tseslint.config(
  { ignores: ['dist/**', 'dist-staging-site/**', 'node_modules/**', 'e2e-artifacts/**', 'e2e/site-release/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  lit.configs['flat/recommended'],
  wc.configs['flat/recommended'],
  {
    files: ['src/**/*.ts', 'test/**/*.ts'],
    languageOptions: { globals: { ...globals.browser } },
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          { name: 'lit/directives/unsafe-html.js', message: 'unsafeHTML is banned (SEC-003).' },
          { name: 'lit/directives/unsafe-svg.js', message: 'unsafeSVG is banned (SEC-003).' },
        ],
      }],
      'no-restricted-properties': ['error', ...sinks],
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-script-url': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
  {
    // The shell, core and design system reach feature modules only through each module's index (02 §2.2).
    files: ['src/core/**/*.ts', 'src/shell/**/*.ts', 'src/design-system/**/*.ts'],
    rules: { 'no-restricted-imports': ['error', {
      paths: [
        { name: 'lit/directives/unsafe-html.js', message: 'unsafeHTML is banned (SEC-003).' },
        { name: 'lit/directives/unsafe-svg.js', message: 'unsafeSVG is banned (SEC-003).' },
      ],
      patterns: [{ regex: '/modules/[a-z]+/(?!index\\.js$)', message: 'Import a feature module only through its index (02 §2.2).' }],
    }] },
  },
  {
    files: ['test/**/*.ts'],
    languageOptions: { globals: { ...globals.mocha } },
    // Unit tests exercise module internals and feed hostile strings (javascript: URLs) to sanitizers.
    rules: { '@typescript-eslint/no-unused-expressions': 'off', '@typescript-eslint/no-explicit-any': 'off', 'no-script-url': 'off' },
  },
  {
    files: ['e2e/**/*.mjs', 'scripts/**/*.mjs', '*.config.*', 'eslint.config.js'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
);
