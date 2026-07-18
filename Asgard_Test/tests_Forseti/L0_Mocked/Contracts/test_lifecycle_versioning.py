"""
Tests for breaking-change lifecycle & versioning (plan 04): lifecycle
metadata extraction, time-travel severity adjustment, SemVer bump matrix,
migration-guide scaffolds, structured changelogs and audit-deps.
"""

from datetime import date

import pytest

from Asgard.Forseti.Compatibility.models._compat_base_models import TierVerdict
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Contracts.models.contract_models import Bump, LifecycleMeta
from Asgard.Forseti.Contracts.services._lifecycle_helpers import (
    apply_lifecycle,
    extract_avro_lifecycle,
    extract_graphql_lifecycle,
    extract_openapi_lifecycle,
    extract_protobuf_lifecycle,
    find_lifecycle_meta,
    lifecycle_adjust,
)
from Asgard.Forseti.Contracts.services._versioning_helpers import (
    generate_migration_guide,
    generate_structured_changelog,
    recommend_version,
)
from Asgard.Forseti.Contracts.services.breaking_change_detector_service import (
    BreakingChangeDetectorService,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

TODAY = date(2026, 7, 17)


def removal_change():
    return make_change(
        "OAS-PATH-REMOVED", SchemaFormat.OPENAPI, Direction.INPUT,
        "/legacy", "Endpoint removed: /legacy",
    )


class TestLifecycleExtraction:
    def test_openapi_extraction(self):
        spec = {
            "openapi": "3.0.0",
            "paths": {"/old": {"get": {
                "deprecated": True,
                "x-sunset-date": "2026-12-01",
                "x-replaced-by": "#/paths/~1v2~1old",
                "x-migration-guide": "https://example.com/migrate",
                "responses": {"200": {"description": "ok"}},
            }}},
            "components": {"schemas": {"Old": {
                "deprecated": True,
                "properties": {"legacyId": {"type": "string",
                                            "deprecated": True}},
            }}},
        }
        metas = extract_openapi_lifecycle(spec)
        op = metas["/old/get"]
        assert op.deprecated and op.sunset == date(2026, 12, 1)
        assert op.replaced_by == "#/paths/~1v2~1old"
        assert op.migration_guide == "https://example.com/migrate"
        assert "/old" in metas  # all ops deprecated => path deprecated
        assert "#/components/schemas/Old" in metas
        assert "#/components/schemas/Old/properties/legacyId" in metas

    def test_graphql_extraction(self):
        sdl = '''
        type User {
          id: ID!
          oldName: String @deprecated(reason: "Use fullName; sunset=2026-01-01")
          fullName: String
        }
        '''
        metas = extract_graphql_lifecycle(sdl)
        assert metas["User.oldName"].deprecated
        assert metas["User.oldName"].sunset == date(2026, 1, 1)

    def test_protobuf_extraction(self):
        proto = '''
        syntax = "proto3";
        message User {
          string old_name = 2 [deprecated = true];
          string full_name = 3;
        }
        '''
        metas = extract_protobuf_lifecycle(proto)
        assert metas["User.old_name"].deprecated
        assert "User.full_name" not in metas

    def test_avro_extraction(self):
        schema = {
            "type": "record", "name": "User",
            "fields": [
                {"name": "oldName", "type": "string",
                 "doc": "@deprecated(since=2025-01-01, sunset=2026-06-01)"},
                {"name": "fullName", "type": "string", "doc": "Full name"},
            ],
        }
        metas = extract_avro_lifecycle(schema)
        meta = metas["User.oldName"]
        assert meta.deprecated
        assert meta.since == date(2025, 1, 1)
        assert meta.sunset == date(2026, 6, 1)

    def test_prefix_lookup(self):
        metas = {"/old": LifecycleMeta(location="/old", deprecated=True)}
        assert find_lifecycle_meta("/old/get", metas) is not None
        assert find_lifecycle_meta("/older/get", metas) is None


class TestTimeTravelAdjustment:
    """Same removal, three lifecycle states, three scores (DEEPTHINK_04 §C)."""

    def test_not_deprecated_full_deduction(self):
        change = lifecycle_adjust(removal_change(), None, TODAY)
        assert change.base_severity == 25
        assert change.impact.structural == TierVerdict.FAIL

    def test_deprecated_pre_sunset_halved_with_mitigation(self):
        meta = LifecycleMeta(location="/legacy", deprecated=True,
                             sunset=date(2027, 1, 1))
        change = lifecycle_adjust(removal_change(), meta, TODAY)
        assert change.base_severity == 12  # halved
        assert "2027-01-01" in (change.mitigation or "")

    def test_post_sunset_zero_deduction_pass(self):
        meta = LifecycleMeta(location="/legacy", deprecated=True,
                             sunset=date(2026, 1, 1))
        change = lifecycle_adjust(removal_change(), meta, TODAY)
        assert change.base_severity == 0
        assert change.impact.structural == TierVerdict.PASS
        assert change.impact.semantic == TierVerdict.PASS
        assert "graceful removal" in change.message

    def test_non_removal_changes_untouched(self):
        change = make_change(
            "OAS-PARAM-REQUIRED-ADDED", SchemaFormat.OPENAPI, Direction.INPUT,
            "/legacy/get/parameters/x", "Required parameter 'x' added",
        )
        meta = LifecycleMeta(location="/legacy", deprecated=True,
                             sunset=date(2020, 1, 1))
        adjusted = lifecycle_adjust(change, meta, TODAY)
        assert adjusted.base_severity == 20

    def test_apply_lifecycle_uses_prefix_matching(self):
        change = make_change(
            "OAS-METHOD-REMOVED", SchemaFormat.OPENAPI, Direction.INPUT,
            "/legacy/get", "Method GET removed from /legacy",
        )
        metas = {"/legacy": LifecycleMeta(location="/legacy", deprecated=True,
                                          sunset=date(2020, 1, 1))}
        apply_lifecycle([change], metas, TODAY)
        assert change.base_severity == 0


class TestSemVerMatrix:
    def test_no_changes_patch(self):
        rec = recommend_version([], "1.2.3")
        assert rec.recommended_bump == Bump.PATCH
        assert rec.recommended_version == "1.2.4"

    def test_structural_fail_major(self):
        rec = recommend_version([removal_change()], "1.2.3")
        assert rec.recommended_bump == Bump.MAJOR
        assert rec.recommended_version == "2.0.0"
        assert any("OAS-PATH-REMOVED" in r for r in rec.reasons)

    def test_hazard_only_minor(self):
        change = make_change(
            "OAS-RES-ENUM-EXTENDED", SchemaFormat.OPENAPI, Direction.OUTPUT,
            "/a", "New enum value emitted",
        )
        rec = recommend_version([change], "1.2.3")
        assert rec.recommended_bump == Bump.MINOR
        assert rec.recommended_version == "1.3.0"

    def test_pre_stability_downgrades_major(self):
        rec = recommend_version([removal_change()], "0.4.2")
        assert rec.pre_stability
        assert rec.recommended_bump == Bump.MINOR
        assert rec.recommended_version == "0.5.0"

    def test_lifecycle_neutralised_change_does_not_force_major(self):
        change = removal_change()
        meta = LifecycleMeta(location="/legacy", deprecated=True,
                             sunset=date(2020, 1, 1))
        lifecycle_adjust(change, meta, TODAY)
        rec = recommend_version([change], "1.2.3")
        assert rec.recommended_bump == Bump.PATCH

    def test_waived_change_ignored(self):
        change = removal_change()
        change.waived = True
        rec = recommend_version([change], "1.2.3")
        assert rec.recommended_bump == Bump.PATCH

    def test_unparseable_version_still_recommends_bump(self):
        rec = recommend_version([removal_change()], "not-a-version")
        assert rec.recommended_bump == Bump.MAJOR
        assert rec.recommended_version is None


class TestGuidesAndChangelogs:
    def test_migration_guide_scaffold(self):
        change = removal_change()
        lifecycle = {"/legacy": LifecycleMeta(
            location="/legacy", deprecated=True,
            replaced_by="/v2/legacy", migration_guide="https://example.com/m",
        )}
        # guide keys off change.location, so meta must be under that key
        guide = generate_migration_guide([change], "2.0.0", lifecycle)
        assert guide.startswith("# Migrating to 2.0.0")
        assert "OAS-PATH-REMOVED" in guide
        assert "/v2/legacy" in guide
        assert "TODO(author)" in guide

    def test_migration_guide_stable_ordering(self):
        changes = [
            make_change("OAS-PATH-REMOVED", SchemaFormat.OPENAPI,
                        Direction.INPUT, loc, f"Endpoint removed: {loc}")
            for loc in ("/zebra", "/alpha")
        ]
        guide = generate_migration_guide(changes, "2.0.0")
        assert guide.index("/alpha") < guide.index("/zebra")
        assert guide == generate_migration_guide(list(reversed(changes)), "2.0.0")

    def test_changelog_groups(self):
        breaking = removal_change()
        graceful = removal_change()
        lifecycle_adjust(
            graceful,
            LifecycleMeta(location="/legacy", deprecated=True,
                          sunset=date(2020, 1, 1)),
            TODAY,
        )
        changelog = generate_structured_changelog([breaking, graceful], "2.0.0")
        assert "## [2.0.0]" in changelog
        assert "### Breaking" in changelog
        assert "### Deprecated" in changelog
        assert "`OAS-PATH-REMOVED`" in changelog


@pytest.fixture()
def spec_pair(tmp_path):
    old = tmp_path / "old.yaml"
    new = tmp_path / "new.yaml"
    old.write_text("""
openapi: 3.0.0
info: {title: T, version: 1.4.2}
paths:
  /legacy:
    get:
      deprecated: true
      x-sunset-date: "2025-01-01"
      responses: {"200": {description: ok}}
  /live:
    get:
      responses: {"200": {description: ok}}
""", encoding="utf-8")
    new.write_text("""
openapi: 3.0.0
info: {title: T, version: 2.0.0}
paths:
  /live:
    get:
      responses: {"200": {description: ok}}
""", encoding="utf-8")
    return old, new


class TestDetectorServiceIntegration:
    def test_detect_unified_rescores_after_lifecycle(self, spec_pair):
        old, new = spec_pair
        service = BreakingChangeDetectorService()
        report = service.detect_unified(old, new, today=TODAY)
        assert report.score == 100
        assert report.structural_breaks == 0
        assert any("graceful removal" in c.message for c in report.changes)

    def test_recommend_version_end_to_end(self, spec_pair):
        old, new = spec_pair
        rec = BreakingChangeDetectorService().recommend_version(
            old, new, "1.4.2", today=TODAY,
        )
        assert rec.recommended_bump == Bump.PATCH

    def test_migration_guide_end_to_end(self, spec_pair):
        old, new = spec_pair
        guide = BreakingChangeDetectorService().generate_migration_guide(
            old, new, "2.0.0", today=TODAY,
        )
        assert "/legacy" in guide


class TestAuditDeps:
    def _run(self, tmp_path, spec_text, operations, horizon):
        import argparse

        from Asgard.Forseti.cli.handlers_schema import _handle_audit_deps

        spec = tmp_path / "dep.yaml"
        spec.write_text(spec_text, encoding="utf-8")
        config = tmp_path / "deps.yaml"
        config.write_text(
            "dependencies:\n"
            f"  - spec: {spec.name}\n"
            "    operations:\n"
            + "".join(f"      - \"{op}\"\n" for op in operations),
            encoding="utf-8",
        )
        args = argparse.Namespace(config=str(config), horizon=horizon)
        return _handle_audit_deps(args)

    SPEC_SUNSET_SOON = """
openapi: 3.0.0
info: {title: D, version: 1.0.0}
paths:
  /soon:
    get:
      deprecated: true
      x-sunset-date: "%s"
      responses: {"200": {description: ok}}
"""

    def test_sunset_within_horizon_fails(self, tmp_path):
        from datetime import timedelta
        sunset = (date.today() + timedelta(days=10)).isoformat()
        exit_code = self._run(tmp_path, self.SPEC_SUNSET_SOON % sunset,
                              ["GET /soon"], horizon=30)
        assert exit_code == 1

    def test_sunset_beyond_horizon_passes(self, tmp_path):
        from datetime import timedelta
        sunset = (date.today() + timedelta(days=10)).isoformat()
        exit_code = self._run(tmp_path, self.SPEC_SUNSET_SOON % sunset,
                              ["GET /soon"], horizon=5)
        assert exit_code == 0

    def test_unused_deprecated_operation_ignored(self, tmp_path):
        from datetime import timedelta
        sunset = (date.today() + timedelta(days=1)).isoformat()
        spec = self.SPEC_SUNSET_SOON % sunset + """
  /other:
    get:
      responses: {"200": {description: ok}}
"""
        exit_code = self._run(tmp_path, spec, ["GET /other"], horizon=30)
        assert exit_code == 0

    def test_missing_config_is_input_error(self, tmp_path):
        import argparse

        from Asgard.Forseti.cli.handlers_schema import _handle_audit_deps

        args = argparse.Namespace(config=str(tmp_path / "nope.yaml"), horizon=30)
        assert _handle_audit_deps(args) == 2
