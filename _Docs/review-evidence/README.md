# Review evidence

Evidence packets from the cross-repository review rounds. Each round froze a
candidate change in an isolated checkout, ran verification and adverse
mutations against it, and had an independent reviewer accept or reject it.

**Packets here:** round-36: ASG-04
**Rounds:** round-36 

These files were produced under `Adrasta/.round3*-scratch/`, which is
git-ignored scratch. They were the only surviving copies, so they are preserved
here in the repository they describe. The isolated checkouts themselves were
not preserved — the `*-full.patch` files are full recovery patches taken
against the canonical worktree at freeze time and reproduce the candidate
state.

## What the file types are

| Pattern | Meaning |
|---|---|
| `*-report*.md` | The author's packet report: result, provenance, verification, remaining acceptance |
| `*-independent-review*.md` | The independent reviewer's verdict. `-no-go` / `-rejected` suffixes are rejected iterations, kept because later evidence references them by hash |
| `*-evidence*.json` | Machine-readable provenance: canonical HEAD at snapshot, candidate branch, before/after `sha256` per changed path, artifact hashes, verification counts |
| `*-full*.patch` | Full recovery patch against the canonical worktree at freeze |
| `*-incremental*.patch` | The packet's own delta only |
| `*-preservation*.json`, `*-preimages*.json`, `*.sha256` | Freeze/handoff identity records used to prove nothing drifted between author and reviewer |
| `*.log` | Verification, mutation and lint runs. The repository-wide `*.log` ignore is reversed by the `.gitignore` beside this file |
| `*mutations*.py`, `*probe*.py`, `*replay*.py` | The adverse-mutation and replay harnesses, so a run can be reproduced |

Byte-identical duplicates were removed; nothing else was edited.
