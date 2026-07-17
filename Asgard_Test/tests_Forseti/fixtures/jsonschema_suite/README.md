# JSON Schema Test Suite (curated subset)

Curated, vendored subset of test cases following the format of the official
[JSON-Schema-Test-Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite)
(`[{description, schema, tests: [{description, data, valid}]}]`).

- `draft7.json` — draft-07 semantics (including `$ref`-ignores-siblings,
  array-form `items` + `additionalItems`, `dependencies`).
- `draft2020.json` — 2020-12 semantics (`prefixItems`, `dependentRequired`/
  `dependentSchemas`, `min/maxContains`, `unevaluatedProperties`/`Items`,
  `$anchor`/`$dynamicAnchor`/`$dynamicRef`, `$ref` with applied siblings).

Runner: `Asgard_Test/tests_Forseti/L0_Mocked/JSONSchema/test_schema_suite_parity.py`
(runs with `check_formats=False` — the suite treats `format` as annotation).

When extending coverage, keep case descriptions aligned with the official
suite so parity gaps are easy to cross-reference.
