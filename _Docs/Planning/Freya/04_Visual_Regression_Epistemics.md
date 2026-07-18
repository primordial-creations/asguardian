# Plan 04 — Visual Regression: Environment Fingerprinting, Baseline Validity, Delta Framing

**Priority:** P1
**Primary research:** DEEPTHINK_03 (map-territory epistemics of synthetic testing)
**Depends on:** Plan 01 (severity mapping)

---

## 1. Rationale (research-backed)

Current state:

- `Asgard/Freya/Visual/services/visual_regression.py` + `_visual_regression_compare.py`: four pure-Python diff methods (pixel, SSIM, pHash, histogram) over the custom PNG codec in `image_ops.py` (zlib + Paeth unfiltering, no Pillow) with `mask_regions` support.
- `Asgard/Freya/Integration/services/baseline_manager.py` + `_baseline_manager_helpers.py`: `BaselineEntry` index (`baselines.json`), SHA hashing, versioning. **No environment metadata whatsoever** — a baseline captured on macOS/DPR-2 will be silently compared against a Linux-CI/DPR-1 screenshot.

DEEPTHINK_03's verdicts map directly:

1. **Absolute visual "correctness" is weak evidence** — font rasterization differs per OS (FreeType vs CoreText vs ClearType), text wraps differently, users apply zoom/scaling/high-contrast the tool never sees.
2. **The delta is ground truth** — "By locking hardware, OS, network, and viewport into a sterile state… if a metric shifts between deployments, the only changing variable is the code." A baseline is only valid as a **controlled delta**: same environment on both sides.
3. **Framing:** visual tests are **"structural tripwires"** — the question is "has the layout cascaded unintentionally from our baseline?", never "does this look right?". A pass does not guarantee readability under user overrides.

The intended docs (`_Docs/Asgard/Freya/Visual-Module.md`) specify Pillow + pixelmatch; per Overview ground rules we keep the pure-Python engine (Plan 07 fixes the docs). RESEARCH_03 (pending) will benchmark diff algorithms and baseline workflows in commercial tools — algorithm replacement decisions wait for it.

## 2. Target state

Baselines carry an **environment fingerprint**; comparisons against a mismatched fingerprint are refused by default (overridable, downgraded to WARNING). Reports frame results as tripwire deltas with the mandated epistemic language. Diff engine gets targeted hardening without changing algorithms.

## 3. Concrete changes

### 3.1 Environment fingerprint (`Asgard/Freya/Integration/models/_integration_base_models.py`, `Integration/services/_baseline_manager_helpers.py`)

```python
class EnvironmentFingerprint(BaseModel):
    os_name: str                 # platform.system()
    os_release: str
    browser_name: str            # "chromium"
    browser_version: str         # from playwright browser.version
    playwright_version: str
    viewport: str                # "1920x1080"
    device_scale_factor: float
    color_scheme: Optional[str] = None      # emulated prefers-color-scheme
    reduced_motion: Optional[str] = None
    font_stack_hash: Optional[str] = None   # sha256 of sorted document.fonts list (JS: [...document.fonts].map(f=>f.family+f.weight))
```

- `BaselineEntry` gains `fingerprint: Optional[EnvironmentFingerprint] = None` (optional — old `baselines.json` files keep loading).
- New helper `capture_fingerprint(page, context) -> EnvironmentFingerprint` in `_baseline_manager_helpers.py` (browser/page introspection + `platform`).
- `create_baseline` / `update_baseline` record it; `compare_to_baseline` computes a mismatch report.

### 3.2 Mismatch policy (`baseline_manager.py`)

Fields ranked by impact: `device_scale_factor`, `viewport`, `os_name` = **hard mismatch** (comparison meaningless — text metrics/raster differ); `browser_version`, `font_stack_hash` = **soft mismatch** (comparison allowed, result flagged).

- Default: hard mismatch → comparison refused; result object returned with `status="environment_mismatch"`, listing differing fields and the DEEPTHINK_03 rationale ("cross-environment pixel comparison measures the environment, not your code"). CLI exit treats it as inconclusive (distinct from regression-found), mapped to a MAJOR finding, not CRITICAL.
- `--allow-env-mismatch` flag (and config key, Plan 06) downgrades hard→soft: comparison runs, result carries `environment_warning` and is capped at WARNING severity regardless of diff size.
- Baselines without a fingerprint (legacy) → soft warning "unverified baseline environment; re-capture recommended".

### 3.3 Delta framing in reports

- `VisualComparisonResult` (`Visual/models/visual_models.py`) gains optional `framing: str` populated with tripwire language: *"Structural tripwire: N% of pixels diverged from baseline `<name>` captured in an identical environment. This indicates an unintended layout cascade, not an aesthetic judgment. A pass does not guarantee readability under user zoom, OS text scaling, or high-contrast modes."*
- Formatters (`cli/_formatters_visual_responsive.py`) and `html_reporter.py` print baseline fingerprint + current fingerprint side-by-side for every comparison.
- Severity mapping (Plan 01 table): diff > hard threshold with valid fingerprint → CRITICAL; > soft threshold → MAJOR; any env-warned result → MAJOR max; fingerprint-missing → MINOR note.

### 3.4 Diff-engine hardening (`Visual/services/_visual_regression_compare.py`)

Targeted, algorithm-preserving improvements:

1. **Anti-aliasing tolerance in pixel_comparison:** before counting a differing pixel, check its 8-neighborhood in the baseline for a pixel within the color delta — classic pixelmatch AA heuristic, implementable in pure Python; controlled by existing `ComparisonConfig` threshold plus new `ignore_antialiasing: bool = True`.
2. **Difference clustering:** connected-component pass (BFS over the boolean diff mask, 8-connectivity) producing `DifferenceRegion` boxes (model already exists at `visual_models.py:153`) so reports say "3 regions: header (1240×80), …" instead of raw pixel counts. Cap components at 50, merge overlapping boxes.
3. **Perf note:** `image_ops.Image` stores pixels as `List[Tuple[int,int,int]]` — memory-heavy for full-page shots. Optional internal refactor to a flat `bytearray` with the same public accessors (`get_pixel`/`set_pixel`/`histogram`), pure stdlib, ~5-10x memory reduction. Do only if profiling on `freya_crawl_output/screenshots` samples shows compare times > ~2s per full-page pair; keep the public class API identical.

### 3.5 What we deliberately do NOT do here

- No algorithm swap (SSIM window sizes, pHash bit depth) — wait for RESEARCH_03 benchmarks.
- No cross-browser baseline matrices — single-engine (Chromium) fingerprints first; matrix support is a config/crawler concern layered later.
- No high-contrast / forced-colors emulation runs — DEEPTHINK_03 names the gap; we disclose it in the framing text rather than half-implement it. Candidate for post-RESEARCH_08 responsive/visual work.

## 4. Phased steps

1. **Phase A:** `EnvironmentFingerprint` model + capture helper + write path (baselines start recording; no enforcement).
2. **Phase B:** mismatch policy in `compare_to_baseline` + CLI flag + inconclusive exit semantics.
3. **Phase C:** framing text, fingerprint display in text/HTML reports, Plan 01 severity mapping.
4. **Phase D:** AA tolerance + diff clustering (pure functions first, then wiring).
5. **Phase E (conditional):** bytearray refactor if profiling justifies.

## 5. Testing notes

- `Asgard_Test/tests_Freya/L0_Mocked/Visual/` + `Integration/`: fingerprint equality/mismatch classification matrix (hard/soft/none), legacy-entry load (fingerprint=None), refusal + override behavior, AA-tolerance on hand-built 5×5 pixel grids (edge pixel vs true change), clustering on synthetic masks (two blobs → two regions; adjacent blobs merge), framing text presence.
- All diff-math tests are Playwright-free (pure functions over `image_ops.Image` built in-memory).

## 6. Thin-research flags

- **RESEARCH_03 (pending — visual tooling landscape):** diff-algorithm choice/benchmarks, baseline review workflows (approve/reject UX), flakiness-suppression techniques. Phases here are deliberately algorithm-neutral so its findings slot into `_visual_regression_compare.py` without model changes.
