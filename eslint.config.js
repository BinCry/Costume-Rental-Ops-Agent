import js from '@eslint/js';
import eslintConfigPrettier from 'eslint-config-prettier/flat';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

export const baseTypeScriptConfig = [
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
];

export const prettierCompatibilityConfig = eslintConfigPrettier;

export default defineConfig([
  globalIgnores(['**/dist/**', '**/coverage/**', '**/node_modules/**', '**/.next/**']),
  {
    files: ['*.{js,mjs,cjs}'],
    extends: [js.configs.recommended, eslintConfigPrettier],
    languageOptions: {
      globals: globals.node,
    },
  },
]);
