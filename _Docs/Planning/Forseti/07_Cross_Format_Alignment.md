# 07 — Cross-Format Entity Alignment (Priority P2)

## Research-Backed Rationale

- **DEEPTHINK_08** is the blueprint: abandon strict isomorphism for **semantic compatibility under projection**; parse all formats into a **Canonical Intermediate Representation (IR)**; normalize nullability (`["null","string"]` ≡ `optional` ≡ `nullable: true` ≡ missing `!`), unions/`oneOf`/`oneof` into IR `Variant` nodes; **lexical normalization** (`orderId` ≡ `order_id` ≡ `ORDER_ID` via tokenization); a **type-compatibility matrix** (isomorphic / coercible-idiomatic / incompatible, e.g. proto `int64` ↔ GraphQL `String` is a *safe idiomatic* mapping, Avro `string` ↔ proto `int64` is critical); entity identity via an **external catalog config** (`alignment-config.yaml`) as the practical adoption path over in-schema annotations or fragile name heuristics; severity graded by data-flow direction (upstream-optional→downstream-required = CRITICAL nullability breach; intentional subsetting = INFO).
- **DEEPTHINK_01 §1** supplies the direction rules the alignment checker reuses (which side is producer vs consumer determines which mismatch is fatal).
- **RESEARCH_12** documents the organizational demand: schemas propagate DB → CDC → broker → API; single-source-of-truth pipelines (proto→JSON Schema exporters, OpenAPI 3.1⇔JSON Schema extraction) exist precisely because cross-format drift is invisible today.
- **RESEARCH_08 §7** shows the industry pattern (Buf + Confluent dual-registry, protoc-gen-jsonschema) that Forseti can check *without* requiring those pipelines.

## Current State (gap)

Nothing exists. Forseti parses six schema formats (OpenAPI, AsyncAPI, JSON Schema, Avro, Protobuf, GraphQL, plus SQL DDL in `Database/`) into six unrelated model families; no code compares an entity across formats. This is the feature no benchmarked competitor ships either (DEEPTHINK_08 calls it "an invisible architectural headache") — highest differentiation potential in the suite.

## Target State

### New module: `Asgard/Forseti/Alignment/`

```
Alignment/
├── models/
│   ├── ir_models.py            # IRType, IRField, IRRecord, IRVariant, IREnum, Nullability, TypeClass
│   └── alignment_models.py     # AlignmentConfig, EntityBinding, AlignmentFinding, AlignmentReport
├── services/
│   ├── ir_builder_service.py       # per-format adapters -> IR
│   ├── _ir_openapi_helpers.py      # + jsonschema (shared walker)
│   ├── _ir_avro_helpers.py
│   ├── _ir_protobuf_helpers.py
│   ├── _ir_graphql_helpers.py
│   ├── _ir_sql_helpers.py          # Database module tables -> IR records (RESEARCH_12 DB-to-API alignment)
│   ├── alignment_checker_service.py
│   ├── _lexical_helpers.py         # tokenization, casing normalization
│   └── _type_matrix_helpers.py
└── utilities/
```

### IR data structures

```python
class TypeClass(str, Enum):
    BOOL, INT32, INT64, FLOAT32, FLOAT64, DECIMAL, STRING, BYTES, DATE, DATETIME, UUID, \
    RECORD, LIST, MAP, ENUM, VARIANT, ANY = ...

class IRField(BaseModel):
    lexical_tokens: tuple[str, ...]   # normalize("orderId") == ("order", "id")
    raw_name: str
    type: IRType
    nullable: bool                    # normalized across all formats (DEEPTHINK_08 §1)
    required: bool                    # presence-required (distinct from nullability)
    default: Any | None
    doc: str | None
    source: SourceRef                 # file, format, path — for reporting
```

Format adapters map into `TypeClass` with capacity annotations (bits, precision). `allOf`/`$ref` are flattened during IR build (reuse plan-03 resolver, plan-05 resolver).

### Alignment config (external catalog, DEEPTHINK_08 §3 option 1)

```yaml
# alignment-config.yaml
entities:
  Order:
    sources:
      - {file: kafka/order.avsc}                          # whole schema
      - {file: grpc/order.proto, type: acme.OrderEvent}
      - {file: rest/openapi.yaml, schema: OrderResponse}
      - {file: gql/schema.graphql, type: Order}
      - {file: db/schema.sql, table: orders}
    direction:                        # producer -> consumer edges (drives severity)
      - {from: kafka/order.avsc, to: gql/schema.graphql}
    ignore_fields: [internal_routing_key]   # declared intentional exclusions
```

A one-shot `forseti align discover <paths...>` wizard applies name-heuristics (strip `Event|Response|Dto` suffixes) **only** to draft the initial YAML — heuristics never run in enforcement mode (DEEPTHINK_08 §3 option 3 "too fragile").

### Checking algorithm

For each entity: build IR per source; match fields by `lexical_tokens`; then per matched pair evaluate, in order:

1. **Type contradiction** (matrix class INCOMPATIBLE, e.g. STRING vs BOOL) ⇒ 🔴 CRITICAL.
2. **Nullability contract breach**: producer-side nullable/optional but consumer-side required/non-null on a declared direction edge ⇒ 🔴 CRITICAL (DEEPTHINK_08 severity table).
3. **Enum divergence**: producer enum symbols ⊄ consumer symbols ⇒ 🔴 CRITICAL; consumer superset ⇒ 🔵 INFO.
4. **Precision risk** (COERCIBLE_LOSSY: INT64→INT32, FLOAT64→FLOAT32, DECIMAL→FLOAT) ⇒ 🟡 WARNING.
5. **Idiomatic coercion** (INT64↔STRING for GraphQL IDs; STRING(uuid)↔UUID) ⇒ 🔵 INFO.
6. **Subset divergence**: field present in some sources, absent in others, not in `ignore_fields` ⇒ 🔵 INFO with "add to ignore_fields if intentional" hint.
7. **Lexical divergence**: tokens match, raw casing violates the configured convention ⇒ 🔵 INFO.

Type matrix implemented as `dict[tuple[TypeClass, TypeClass], MatrixVerdict]` with capacity comparison for numeric pairs — small, exhaustively unit-testable.

### Output

Entity-centric matrix report exactly in DEEPTHINK_08 §5's terminal format (per-entity block, graded findings, final counts + build verdict); JSON via the plan-08 Finding model; exit 1 iff any CRITICAL.

CLI: `forseti align check --config alignment-config.yaml [--entity Order]`, `forseti align discover <paths...> -o alignment-config.yaml`.

## Concrete Changes

1. New `Alignment/` package; adapters import existing parsers (`AsyncAPI/services/asyncapi_parser_service`, `Avro` models, `Protobuf/services/_protobuf_validator_parse_helpers`, `GraphQL/utilities/_graphql_parse_utils`, `Database/services/schema_analyzer_service`) — no parser duplication.
2. `Database` IR adapter maps SQL types (VARCHAR(n)→STRING+maxlen, DECIMAL(p,s)→DECIMAL, nullable columns) closing the DB→API loop RESEARCH_12 emphasizes.
3. CLI wiring in `_parser_commands.py` + `cli/handlers_alignment.py`; alignment findings flow through the plan-02 severity/suppression machinery (`align.*` rule ids).

## Phased Steps

- **Phase 1**: IR models + OpenAPI/JSONSchema + Avro adapters + lexical/type matrix + checker for those two formats.
- **Phase 2**: Protobuf + GraphQL adapters; direction edges + nullability-breach severity.
- **Phase 3**: SQL adapter; `align discover` wizard.
- **Phase 4**: hook into `forseti audit` (auto-run when `alignment-config.yaml` present).

## Testing Notes

- Golden test reproducing DEEPTHINK_08 §5's Order example end-to-end (4 fixture files, expected: 2 CRITICAL, 1 WARNING, 2 INFO, exit 1).
- Type-matrix table test: exhaustive over `TypeClass × TypeClass` asserting verdict symmetry properties (INCOMPATIBLE is symmetric; LOSSY is directional).
- Lexical tests: `orderId`/`order_id`/`ORDER_ID`/`OrderID` all normalize equal; `orderId` vs `orderedId` do not.
- Nullability normalization matrix across all five formats (one fixture each) mapping to identical IR.
- `ignore_fields` suppresses subset findings but never type contradictions (intentional-projection ≠ type error).
