# Jake — Manual To-Do

Items that require a human (credentials, external systems) — cannot be done by the tooling.

## 1. Rotate the leaked Vault token (SECURITY — do this first)

**What happened:** The project instructions file `CLAUDE.md` contained real, live credentials — most importantly a **HashiCorp Vault root/service token** (the hardcoded `VAULT_TOKEN='hvs.…'` value, referenced on two lines). During the uplift, `CLAUDE.md` was accidentally committed to the `uplift/asgard-p0` branch. GitHub's push-protection **caught it and rejected the push**, so the token **never reached GitHub**. The file was then purged from all local git history and added to `.gitignore`, so it can't be committed again.

**Why rotate anyway:** The token sat in local commit objects (now rewritten away) and in the working-tree file. It was never exposed remotely, but rotation is the safe, cheap call for any root-scoped credential that has been in more places than intended.

**Steps:**
- [ ] Revoke the current Vault token: `vault token revoke <the hvs.… token in CLAUDE.md>` (or revoke via the Vault UI / `vault token revoke -self` from a session using it).
- [ ] Issue a replacement token/AppRole for the `claude` identity with least-privilege scope (avoid a root token in a plaintext instructions file).
- [ ] Update `CLAUDE.md` locally with the new value (the file is now gitignored, so it stays local).
- [ ] Rotate the other credentials that live in `CLAUDE.md` for good measure, since they shared the same exposure surface: the MariaDB `claude` password (in Vault at `secrets/claude/mariadb`), the Gitea bot token (`secrets/claude/gitea`), and the AppRole `role_id`/`secret_id` in `~/.vault/claude.env`.
- [ ] Confirm nothing else in the repo history carries a secret: `git log -p | grep -iE 'hvs\.|password|secret_id' ` (should be clean — the purge already handled `CLAUDE.md`).

## 2. Optional: make `[ast]` / online features first-class in CI

- [ ] The multi-language AST/CST features (tree-sitter) require `pip install asguardian[ast]` — ensure CI installs the extra so the JS/TS/Java/Go analysis paths run rather than gracefully degrade.
- [ ] The live dependency-vulnerability lookup (OSV/NVD) is **opt-in** (`--online` / `enable_network=True`) and never runs by default. If you want it in a scheduled scan, wire the flag in your CI job and confirm outbound network egress to `api.osv.dev` / `services.nvd.nist.gov` is allowed.

## 3. Optional: enable GitHub secret scanning on the repo

- [ ] `primordial-creations/asguardian` is eligible but not enabled. Turning it on (Settings → Security → Code security and analysis) gives you server-side detection in addition to push protection.
