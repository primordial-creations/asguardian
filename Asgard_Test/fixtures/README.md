# Asgard Test Fixtures

This directory contains intentionally vulnerable code used as ground-truth fixtures for L5 (Compliance) and L10 (Industry Benchmark) tests.

**⚠️ These files contain real security vulnerabilities by design. They must be excluded from all CI scanning, linting, and coverage runs.**

## Structure

```
fixtures/
    bandit/          # Bandit functional test examples (Apache 2.0, PyCQA/bandit)
        examples/    # 92 Python files, one per vulnerability category
        LICENSE
    semgrep/         # Semgrep rule test files (LGPL 2.1, semgrep/semgrep-rules)
        django/      # Annotated with # ruleid: (bad) and # ok: (safe)
        flask/
        ...          # Organised by framework/library
        LICENSE
    owasp/           # Hand-written CWE-tagged fixtures
        CWE22_PathTraversal/bad/
        CWE22_PathTraversal/safe/
        CWE79_XSS/bad/
        ...
```

## Sources

| Set | Source | License | Count |
|-----|--------|---------|-------|
| Bandit examples | github.com/PyCQA/bandit/examples/ | Apache 2.0 | 92 files |
| Semgrep Python rules | github.com/semgrep/semgrep-rules/python/ | LGPL 2.1 | 368 files |
| OWASP (hand-written) | Asgard project | MIT | varies |

## Updating

```bash
# Refresh Bandit fixtures
git clone --depth=1 --filter=blob:none --sparse https://github.com/PyCQA/bandit /tmp/bandit-sparse
cd /tmp/bandit-sparse && git sparse-checkout set examples
cp examples/*.py Asgard_Test/fixtures/bandit/examples/

# Refresh Semgrep fixtures
git clone --depth=1 --filter=blob:none --sparse https://github.com/semgrep/semgrep-rules /tmp/semgrep-sparse
cd /tmp/semgrep-sparse && git sparse-checkout set python
cp -r python/ Asgard_Test/fixtures/semgrep/
```
