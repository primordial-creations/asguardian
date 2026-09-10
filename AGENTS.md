# Asgard — Agent Instructions

**Read the ecosystem master rules first: [`../CLAUDE.md`](../CLAUDE.md)** (identical to
`../AGENTS.md`). It carries the rules that apply to every repository in the GAIA Ecosystem —
the mandatory git workflow (never commit on `main`; all work lands through a PR; no
`git stash`), architecture rules, the CI/CD-only build and deploy rule, working style, and the
shared Claude service credentials.

This file carries **only what is specific to Asgard**. Where the two disagree, this file wins.

## Repo-specific rules

- Python 3.11 or higher is required.
- The package is published to PyPI as `asguardian`; the CLI is invoked as `asgard` (and
  `asgard-dashboard` for the web dashboard).
