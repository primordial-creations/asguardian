"""
Linter configuration templates for TypeScript/JavaScript projects.

Contains canonical TypeScript/JavaScript linting and tooling configurations
derived from GAIA coding standards. Used by templates.py as part of the
split template set.
"""

# -- TypeScript/JavaScript: ESLint flat config --

ESLINT_CONFIG_JS = """\
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      react,
      "react-hooks": reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "warn",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
    settings: {
      react: {
        version: "detect",
      },
    },
  },
  {
    ignores: ["node_modules/", "dist/", "build/", "coverage/"],
  }
);
"""

# -- TypeScript: tsconfig.json --

TSCONFIG_JSON = """\
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist", "build", "coverage"]
}
"""

# -- Prettier configuration --

PRETTIERRC_JSON = """\
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "avoid",
  "endOfLine": "auto"
}
"""

# Map of TypeScript template names to their content and target filenames
TYPESCRIPT_TEMPLATES = {
    "eslint": {
        "content": ESLINT_CONFIG_JS,
        "filename": "eslint.config.js",
        "mode": "create",
    },
    "tsconfig": {
        "content": TSCONFIG_JSON,
        "filename": "tsconfig.json",
        "mode": "create",
    },
    "prettier": {
        "content": PRETTIERRC_JSON,
        "filename": ".prettierrc",
        "mode": "create",
    },
}

# -- VSCode settings for TypeScript projects --

VSCODE_SETTINGS_TYPESCRIPT = {
    "[typescript]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "editor.formatOnSave": True,
        "editor.codeActionsOnSave": {
            "source.fixAll.eslint": "explicit",
        },
    },
    "[typescriptreact]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "editor.formatOnSave": True,
        "editor.codeActionsOnSave": {
            "source.fixAll.eslint": "explicit",
        },
    },
    "[javascript]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "editor.formatOnSave": True,
    },
    "eslint.useFlatConfig": True,
}

# -- VSCode extension recommendations for TypeScript --

VSCODE_EXTENSIONS_TYPESCRIPT = [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
]

# -- CLI tool requirements for TypeScript --

TYPESCRIPT_TOOL_REQUIREMENTS = [
    {
        "command": "npx",
        "check_args": ["--version"],
        "name": "npx (Node.js)",
        "install": "Install Node.js from https://nodejs.org/ (LTS recommended)",
        "purpose": "Node.js package runner (required for ESLint and Prettier)",
    },
]

TYPESCRIPT_NPM_REQUIREMENTS = [
    {
        "package": "eslint",
        "name": "ESLint",
        "install": "npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react eslint-plugin-react-hooks",
        "purpose": "TypeScript/JavaScript linter",
    },
    {
        "package": "prettier",
        "name": "Prettier",
        "install": "npm install -D prettier",
        "purpose": "Code formatter",
    },
    {
        "package": "typescript",
        "name": "TypeScript",
        "install": "npm install -D typescript",
        "purpose": "TypeScript compiler",
    },
]
