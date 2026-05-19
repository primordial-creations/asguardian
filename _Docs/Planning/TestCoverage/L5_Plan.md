# L5 (Compliance / Detection Quality) Coverage Plan

L5 tests are the ground-truth detection tests: known-bad code must produce a
finding; known-good code must produce none. If L5 fails, the scanner is
**broken**, not just slow.

See `_Docs/Testing/Testing_Standards.md` for the rules.

---

## Current state

- **18 L5 tests, 0 failures**
- Covers only the 14 newly-added security scanners + 4 architecture rules
- Missing: every older Heimdall scanner, all non-Heimdall compliance checks

---

## Phase 1 — Build the fixture library

Create a canonical library of vulnerable code samples, organised by CWE.

- [ ] `Asgard_Test/tests_Heimdall/fixtures/L5_known_bad/` — directory root
- [ ] One subdirectory per CWE/category, each containing a minimal vulnerable
      snippet with a header comment identifying the CWE and the expected
      detection signature:

      ```
      L5_known_bad/
          CWE-89_sql_injection/
              python_string_concat.py      # CWE-89, OWASP A03
              python_format_string.py
              python_fstring.py
          CWE-79_xss/
              flask_unescaped_template.py
              django_safe_filter.html
          CWE-78_command_injection/
              subprocess_shell_true.py
              os_system_user_input.py
          CWE-22_path_traversal/
              open_user_path.py
              zipfile_extract_all.py
          CWE-918_ssrf/
              requests_user_url.py
          CWE-611_xxe/
              lxml_resolve_entities.py
          CWE-502_deserialization/
              pickle_load_untrusted.py
              yaml_load.py
          CWE-798_hardcoded_secrets/
              aws_access_key.py
              password_constant.py
              jwt_secret.py
          CWE-327_weak_crypto/
              md5_password.py
              des_cipher.py
              ecb_mode.py
          CWE-330_weak_random/
              random_token.py
          CWE-1004_insecure_cookie/
              flask_cookie_no_httponly.py
          CWE-200_information_exposure/
              debug_true_production.py
      L5_known_good/
          ... (parallel structure with safe equivalents)
      ```

- [ ] Each fixture file < 30 lines. Header comment format:

      ```python
      # CWE-89: SQL Injection via string concatenation
      # OWASP: A03 Injection
      # Expected scanner: InjectionDetectionService
      # Expected severity: CRITICAL
      ```

---

## Phase 2 — L5 tests for older Heimdall scanners

Each scanner gets one test class with at least: instantiate, scan known-bad,
scan known-good, assert severity correct, assert CWE tag present.

- [ ] `Asgard_Test/tests_Heimdall/L5_Compliance/test_injection_detection_compliance.py`
      — `InjectionDetectionService` against all CWE-89/78/79/917 fixtures.
- [ ] `test_secrets_detection_compliance.py` — `SecretsDetectionService`
      against CWE-798 fixtures (AWS, Azure, GCP, generic API keys, JWT
      secrets, DB passwords, private keys).
- [ ] `test_cryptographic_validation_compliance.py` —
      `CryptographicValidationService` against CWE-327/328/329/330 fixtures
      (MD5/SHA1, DES, ECB mode, weak random, hardcoded IV).
- [ ] `test_dependency_vulnerability_compliance.py` —
      `DependencyVulnerabilityService` against fixture `requirements.txt` /
      `package.json` with known-CVE versions.
- [ ] `test_taint_analyzer_compliance.py` — `TaintAnalyzer` against
      end-to-end taint flow fixtures (source → sink chains).
- [ ] `test_compliance_reporter_compliance.py` — `ComplianceReporter` against
      a synthetic findings set; assert PCI/HIPAA/GDPR sections are emitted
      correctly.
- [ ] `test_hotspot_detector_compliance.py` — `HotspotDetector` against
      hotspot fixtures (high-complexity + recent churn).
- [ ] `test_static_security_compliance.py` — `StaticSecurityService` umbrella
      check across the full fixture library.
- [ ] `test_headers_compliance.py` — missing CSP, HSTS, X-Frame-Options.
- [ ] `test_tls_compliance.py` — TLS 1.0/1.1, weak ciphers, expired certs.
- [ ] `test_auth_compliance.py` — missing auth on endpoints, weak password
      policy, no rate limiting.
- [ ] `test_access_compliance.py` — broken access control patterns (IDOR,
      privilege escalation paths).
- [ ] `test_container_compliance.py` — Dockerfile CIS benchmark violations
      (root user, no HEALTHCHECK, ADD vs COPY, latest tag).
- [ ] `test_frontend_compliance.py` — XSS in JSX, dangerouslySetInnerHTML,
      eval, inline event handlers.
- [ ] `test_infrastructure_compliance.py` — Terraform public S3 bucket, open
      security group, unencrypted RDS.
- [ ] `test_log_analysis_compliance.py` — sensitive data in logs (PII, PHI,
      credentials).

---

## Phase 3 — Non-Heimdall compliance

L5-style tests exist outside Heimdall too: any scanner that judges "good vs
bad" qualifies.

### Forseti

- [ ] `Asgard_Test/tests_Forseti/L5_Compliance/test_breaking_change_detection.py`
      — fixture pairs of OpenAPI v1/v2, AsyncAPI v1/v2, `.proto` v1/v2; assert
      removed field / changed type / removed endpoint is flagged.
- [ ] `test_database_migration_compliance.py` — destructive migration patterns
      (DROP COLUMN without nullable, RENAME without alias).

### Freya

- [ ] `Asgard_Test/tests_Freya/L5_Compliance/test_wcag_aa_compliance.py` —
      fixture pages violating WCAG 2.1 AA (contrast, alt text, label
      association, focus order); assert detection.
- [ ] `test_wcag_aaa_compliance.py` — AAA-only violations (enhanced contrast,
      no timing).

### Verdandi

- [ ] `Asgard_Test/tests_Verdandi/L5_Compliance/test_slo_breach_detection.py`
      — fixture time-series with known breach; assert detection + severity.
- [ ] `test_anomaly_compliance.py` — spike / dip / drift fixtures.

### Volundr

- [ ] `Asgard_Test/tests_Volundr/L5_Compliance/test_dockerfile_cis_compliance.py`
      — CIS Docker Benchmark HIGH/CRITICAL items.
- [ ] `test_kubernetes_cis_compliance.py` — CIS Kubernetes Benchmark
      (no resource limits, privileged containers, hostNetwork).
- [ ] `test_terraform_cis_compliance.py` — CIS AWS Foundations items.

---

## Phase 4 — Regulatory mapping

For each finding from each scanner, verify the report includes the correct
regulatory metadata:

- [ ] `Asgard_Test/tests_Heimdall/L5_Compliance/test_regulatory_mapping.py`:
  - Every CRITICAL injection finding must include `cwe_id="CWE-89"` (or
    appropriate) and an `owasp_category` field.
  - Every secrets finding must include `cwe_id="CWE-798"`.
  - PII-related findings must include `gdpr_article` or `hipaa_safeguard`
    where applicable.
  - PCI scanners must include `pci_dss_requirement`.

- [ ] Add a parametrized meta-test: walk every CRITICAL pattern in every
      scanner's pattern list and confirm at least one positive L5 test exists
      for it.

---

## Acceptance criteria

- [ ] Every security scanner has at least one L5 test class.
- [ ] Every CRITICAL pattern in every scanner's pattern list has at least one
      positive (known-bad) test.
- [ ] Every scanner has a known-good negative test (zero findings).
- [ ] Regulatory mapping meta-test passes.
- [ ] 0 L5 failures.

## How to track

```bash
pytest Asgard_Test/ -k L5_Compliance -v
ls Asgard_Test/tests_Heimdall/fixtures/L5_known_bad/ | wc -l
```
