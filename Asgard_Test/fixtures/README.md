# Asgard Test Fixtures

This directory contains intentionally vulnerable code used as ground-truth fixtures for L5 (Compliance) and L14 (Industry Benchmark) tests.

**⚠️ These files contain real security vulnerabilities by design. They must be excluded from all CI scanning, linting, and coverage runs.**

## Structure

```
fixtures/
    bandit/           # Bandit functional test examples (Apache 2.0, PyCQA/bandit)
        examples/     # 92 Python files, one per vulnerability category
        LICENSE
    semgrep/          # Semgrep rule test files (LGPL 2.1, semgrep/semgrep-rules)
        django/       # Annotated with # ruleid: (bad) and # ok: (safe)
        flask/
        ...           # Organised by framework/library
        LICENSE
    owasp/            # Hand-written CWE-tagged fixtures (mixed languages)
        CWE22_PathTraversal/bad/
        CWE22_PathTraversal/safe/
        CWE79_XSS/bad/
        ...
    webgoat/          # OWASP WebGoat Java lessons (GPL 2.0, OWASP/WebGoat)
        lessons/      # 188 .java files covering OWASP Top 10
    dvwa/             # Damn Vulnerable Web Application (GPL 3.0, digininja/DVWA)
        vulnerabilities/ # 155 .php files covering OWASP Top 10
    railsgoat/        # OWASP RailsGoat Ruby/Rails (MIT, OWASP/railsgoat)
        app/          # 46 .rb files covering OWASP Top 10
    govwa/            # Go Vulnerable Web App (MIT, 0c34/govwa)
                      # 20 .go files covering SQL injection, XSS, etc.
    nodegoat/         # OWASP NodeGoat JavaScript (Apache 2.0, OWASP/NodeGoat)
        app/          # 25 .js files covering OWASP Top 10
    webgoat_net/      # OWASP WebGoat.NET C# (GPL 2.0, OWASP/WebGoat.NET)
                      # 150 .cs files covering injection, auth bypass, etc.
```

## Sources

| Set | Language | Source | License | Count |
|-----|----------|--------|---------|-------|
| Bandit examples | Python | github.com/PyCQA/bandit/examples/ | Apache 2.0 | 92 files |
| Semgrep Python rules | Python | github.com/semgrep/semgrep-rules/python/ | LGPL 2.1 | 368 files |
| OWASP (hand-written) | Mixed | Asgard project | MIT | ~15 files |
| WebGoat | Java | github.com/WebGoat/WebGoat | GPL 2.0 | 188 files |
| DVWA | PHP | github.com/digininja/DVWA | GPL 3.0 | 155 files |
| RailsGoat | Ruby | github.com/OWASP/railsgoat | MIT | 46 files |
| govwa | Go | github.com/0c34/govwa | MIT | 20 files |
| NodeGoat | JavaScript | github.com/OWASP/NodeGoat | Apache 2.0 | 25 files |
| WebGoat.NET | C# | github.com/OWASP/WebGoat.NET | GPL 2.0 | 150 files |

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

# Refresh Java fixtures (WebGoat)
git clone --depth=1 https://github.com/WebGoat/WebGoat /tmp/webgoat-tmp
find /tmp/webgoat-tmp/src -name "*.java" | while read f; do
    mkdir -p "Asgard_Test/fixtures/webgoat/$(dirname ${f#/tmp/webgoat-tmp/src/})"
    cp "$f" "Asgard_Test/fixtures/webgoat/$(dirname ${f#/tmp/webgoat-tmp/src/})/"
done

# Refresh PHP fixtures (DVWA)
git clone --depth=1 https://github.com/digininja/DVWA /tmp/dvwa-tmp
cp -r /tmp/dvwa-tmp/vulnerabilities/ Asgard_Test/fixtures/dvwa/

# Refresh Ruby fixtures (RailsGoat)
git clone --depth=1 https://github.com/OWASP/railsgoat /tmp/railsgoat-tmp
cp -r /tmp/railsgoat-tmp/app/ Asgard_Test/fixtures/railsgoat/

# Refresh Go fixtures (govwa)
git clone --depth=1 https://github.com/0c34/govwa /tmp/govwa-tmp
find /tmp/govwa-tmp -name "*.go" -exec cp {} Asgard_Test/fixtures/govwa/ \;

# Refresh JS fixtures (NodeGoat)
git clone --depth=1 https://github.com/OWASP/NodeGoat /tmp/nodegoat-tmp
cp -r /tmp/nodegoat-tmp/app/ Asgard_Test/fixtures/nodegoat/

# Refresh C# fixtures (WebGoat.NET)
git clone --depth=1 https://github.com/OWASP/WebGoat.NET /tmp/webgoatnet-tmp
find /tmp/webgoatnet-tmp -name "*.cs" | while read f; do
    rel="${f#/tmp/webgoatnet-tmp/}"
    mkdir -p "Asgard_Test/fixtures/webgoat_net/$(dirname $rel)"
    cp "$f" "Asgard_Test/fixtures/webgoat_net/$rel"
done
```
