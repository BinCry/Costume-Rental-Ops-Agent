import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import { defineConfig, globalIgnores } from 'eslint/config';

import { baseTypeScriptConfig, prettierCompatibilityConfig } from '../../eslint.config.js';

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      ...baseTypeScriptConfig,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      prettierCompatibilityConfig,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
]);
