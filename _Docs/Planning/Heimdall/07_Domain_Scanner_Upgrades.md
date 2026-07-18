# 07 — Domain Scanner Upgrades (Per-module Precision Recipes)

**Sources (Heimdall research):** DEEPTHINK_07 (SSRF), DEEPTHINK_09 (ReDoS), RESEARCH_03/12 (secrets & git scanning), RESEARCH_04 (SSRF/XXE), RESEARCH_05 (headers), RESEARCH_06 (TOCTOU/concurrency), RESEARCH_07 (ReDoS), RESEARCH_08 (container), RESEARCH_09 (crypto), RESEARCH_10 (access control), RESEARCH_11 (sensitive data), RESEARCH_14 (auth), RESEARCH_15 (deserialization), RESEARCH_16 (supply chain), RESEARCH_17 (TLS/mTLS), RESEARCH_18 (input validation).

Each recipe below is independently shippable behind the plan-01 dual engine and reports through the plan-06 normalization engine. Confidence buckets per plan 04.

## 7.1 SSRF / XXE (`Security/SSRF/services/ssrf_scanner.py`)

Current: regex over `requests.get(...url...)` shapes → the exact 40%+ FP profile DEEPTHINK_07 addresses. Replace with the 5-step decision pipeline (AST + intra-procedural backward slice):
1. **Host-control structural check**: f-string/concat where scheme+host are literal → reclassify to low-severity "API Path Injection", suppress SSRF (~15% FP cut).
2. **Source verification**: slice URL var back to `os.environ`/`app.config`/`settings`/`UPPER_SNAKE_CASE` constant → suppress (~15–20% cut).
3. **Entry-point tiering**: URL traces to a parameter — router-decorated function → HIGH confidence; generic helper → LOW (never blocks).
4. **Allowlist dominator check**: dominating `if` with strict equality → suppress; `startswith`/regex/`urlparse().hostname` guards → keep at MEDIUM as "Potential SSRF Validation Bypass (parser differential, CWE-601-style)" — never fully trust `urlparse` (RESEARCH_04 parser-differential evidence).
5. **Redirect metadata**: annotate finding with `allow_redirects`/`follow_redirects` presence; document that redirect-based SSRF is a runtime risk (don't flag validated URLs for it).
XXE: move from regex to AST kwarg checks (`resolve_entities`, `disallow-doctype-decl` features per language). Target: actionable FP <15% on fixtures.

## 7.2 ReDoS (`Security/ReDoS/services/redos_scanner.py`)

Current: regex-on-regex indicator table (nested quantifiers) — DEEPTHINK_09 rates this ~40% FP ("unfit"). Replace analysis core with **Glushkov-NFA ambiguity analysis** (`PyReDoS-Static` spec):
- Phase 1 extraction via AST: `re.compile/match/search/...` sinks; intra-procedural constant folding for f-strings/concats; extract flags. Unresolvable dynamic patterns → *silently skip* (defer to a separate Regex-Injection taint rule, CWE-400).
- Phase 2: regex-AST → rewrite for flags (`.`→`[\s\S]` under DOTALL; class expansion under IGNORECASE; unknown flags → analyze twice: bare + worst-case profile). Strip lookarounds to ε (safe over-approx); **abort on backreferences** (documented FN).
- Phase 3: Tarjan SCC on the NFA. **EDA** (two intersecting self-paths in one SCC) → O(2^n) → HIGH unconditionally. **IDA** (chained SCC loops on intersecting classes) → O(n^k) → LOW, suppressed if a local length guard (`len(x)<255`, slicing) dominates.
- Budget ≤25ms/regex, ≤100ms/file. Precision target >85%, recall >80% on statically resolvable patterns. Remediation text recommends RE2/possessive-rewrite/timeouts (RESEARCH_07).

## 7.3 Secrets (`Security/services/secrets_detection_service.py`, `Git/`)

Keep regex+entropy Layer-1 (correct per DEEPTHINK_01 — never AST-ify secrets). Upgrades (RESEARCH_03/12, DEEPTHINK_08 §3):
- **Dummy filter** as an explicit ordered pipeline: vendor doc strings (`AKIAIOSFODNN7EXAMPLE`), substrings `EXAMPLE|DUMMY|MOCK|FAKE|XXXX`, low entropy → drop. High-entropy survivors stay CRITICAL **even in test files** (secrets are never test-suppressed).
- **Semantic context scoring** (DEEPTHINK_03 §3): identifier names (`AWS_SECRET_ACCESS_KEY` → ~0.95; `commit_hash` → <0.1); behavioral proof (string flows into `Authorization` header/api URL → 1.0); `process.env`/`os.environ` proximity → drop.
- **Git history depth** (RESEARCH_12): `Git/` module gains full-history scan mode (all refs incl. packed/orphaned commits), plus a "phantom secret" warning in docs — history rewrite is compliance, rotation is the fix. Optional **active validation** hooks (AWS STS GetCallerIdentity-style) strictly opt-in and rate-limited, raising confidence to 1.0 and severity per plan 06 matrix (validated ≫ theoretical).

## 7.4 Crypto (`Security/services/cryptographic_validation_service.py`)

RESEARCH_09 + DEEPTHINK_10: MD5/SHA1 become **hotspots, not findings**, unless context proves password/signature use (var names, auth-module paths, `hashlib.md5(password...)`); honor `usedforsecurity=False` kwarg → suppress. AST kwarg checks: ECB mode, static IV/nonce literals, RSA padding (PKCS1v15 for encryption), `random` vs `secrets` for token flows (Layer-3 rule: weak PRNG flagged only when output reaches jwt/cookie/token sink — DEEPTHINK_01 §9). Map to NIST SP 800-131A transitions in remediation text.

## 7.5 Deserialization (`Security/Deserialization/`)

RESEARCH_15 + DEEPTHINK_10: `pickle.loads`/`yaml.load(Loader=Loader)` on **untrusted** data = finding (taint-integrated); on internal/broker data = hotspot (data-provenance question). Never claim gadget-chain proof — statically unprovable; wording must say "deserialization of attacker-influenced data" to avoid the 70%-FP trap of flagging every sink.

## 7.6 Auth & Access Control (`Security/Auth/`, `Security/Access/`)

RESEARCH_14/10: two distinct detection modes — (a) **absent control**: negative-space matching — route handlers lacking `@login_required`/`Depends(auth)`/permission mixins, via decorator AST checks (Layer 2, near-free precision) and framework stubs; (b) **present-but-weak**: JWT `verify=False`/`alg=none`, non-constant-time compares (`==` on secrets → `hmac.compare_digest`), session cookie flags. BOLA/IDOR: acknowledge SAST limits; ship an advisory rule (object fetch by request-supplied ID without ownership filter in the same slice) at Possible confidence, plus doc pointer to contract-driven fuzzing (Schemathesis) as the real control.

## 7.7 TOCTOU / Concurrency (`Security/RaceCondition/`)

RESEARCH_06 + DEEPTHINK_04 (FP-bias table): precision-first. Flag only canonical patterns: `os.path.exists(f)` → `open(f,'w')` same-slice (fix: `os.open(..., O_CREAT|O_EXCL)`); ORM `get(); mutate; save()` without `select_for_update()` *inside* a transaction context (`@transaction.atomic` check — presence of the lock without the transaction is still flagged); suppress for SQLite engines (serialized by default). Severity LOW/MEDIUM; never gate-blocking.

## 7.8 Container & IaC (`Security/Container/`, `Security/Misconfig/`)

RESEARCH_08: parse Dockerfiles/compose into instruction ASTs (not line regex): root user/missing USER, `--privileged`, `:latest` tags, secrets via COPY/ENV/ARG, missing HEALTHCHECK; map each rule to CIS Docker Benchmark / NIST SP 800-190 control IDs in finding metadata (compliance reporting already exists in `Security/Compliance` — extend mapping tables).

## 7.9 TLS / Headers (`Security/TLS/`, `Security/Headers/`)

RESEARCH_17/05 + DEEPTHINK_04: **max-precision posture** — apps behind proxies legitimately use HTTP internally, so config-file analysis (nginx `ssl_verify_client`, HAProxy `verify required`, Terraform ALB `mutual_authentication`, protocol/cipher minimums vs NIST 800-52r2) outranks code-level guesses; `verify=False` in code stays a hotspot (DEEPTHINK_10 pattern 3). Headers module: grade against OSHP baseline; downgrade browser-only headers in `is_api` context (plan 06 context modifier); flag `Server`/`X-Powered-By` exposure as LOW info-leak.

## 7.10 Supply Chain (`Security/services/dependency_vulnerability_service.py`)

RESEARCH_16: query **OSV** (aggregated, ecosystem-native IDs) as primary DB, NVD as secondary; static resolution of transitive graphs from lockfiles (never execute `setup.py`); typosquat similarity scoring (Levenshtein/keyboard-distance vs top-N PyPI names) on manifest entries; dependency-confusion check (internal package name present on public index); SBOM generator already exists — add provenance fields and dev-dependency severity discount (LOW per DEEPTHINK_11 matrix).

## 7.11 Sensitive Data / Logging (`Security/SensitiveData/`, `Security/LogAnalysis/`)

RESEARCH_11: PII-to-log-sink taint rule (identifier lexicon: ssn/dob/email/password/token → logging calls, `print`, exception messages); flag Django `DEBUG=True`; recommend Pydantic `SecretStr` in remediation; GDPR/PCI/HIPAA tags in metadata for compliance reports.

## 7.12 Input Validation (`Security/InputValidation/`)

RESEARCH_18: model validation as **control-flow barrier guards** vs sanitization as **data mutators**; flag raw access (`request.POST[...]` over `cleaned_data`, FastAPI `Request.body()` bypassing Pydantic), globally disabled Jinja2 autoescape, `mark_safe()` on tainted data, mass-assignment (Pydantic models without `extra='forbid'` on update routes — advisory). CWE-179 early-validation rule: validation followed by decode/mutation before sink.

## Cross-cutting

- Every upgraded rule: benchmark fixtures (vulnerable + safe pair) before merge (plan 01 gate).
- Every rule emits `mechanism_id` for plan-06 normalization and honors plan-08 test-context tags.
- FP/recall bias per category follows the DEEPTHINK_04 decision matrix (recall-biased: secrets, SQLi; precision-biased: TLS, MD5, TOCTOU, ReDoS).
