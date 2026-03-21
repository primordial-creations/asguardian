import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.CodeFix.services.codefix_service import CodeFixService


def run_codefix_suggestions(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()
    rule_id = getattr(args, "rule_id", None)
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        service = CodeFixService()

        if rule_id:
            fix = service.get_fix(rule_id, code_snippet="")
            if fix is None:
                print(f"No fix template available for rule: {rule_id}")
                return 0

            if output_format == "json":
                print(json.dumps(fix.dict(), indent=2, default=str))
            else:
                print("")
                print("=" * 70)
                print(f"  CODE FIX: {fix.title}")
                print("=" * 70)
                print(f"  Rule:       {fix.rule_id}")
                print(f"  Type:       {fix.fix_type}")
                print(f"  Confidence: {fix.confidence}")
                print("")
                print(f"  Description:")
                print(f"    {fix.description}")
                if fix.explanation:
                    print("")
                    print(f"  Explanation:")
                    print(f"    {fix.explanation}")
                if fix.fixed_code:
                    print("")
                    print(f"  Suggested fix:")
                    for line in fix.fixed_code.splitlines():
                        print(f"    {line}")
                if fix.references:
                    print("")
                    print(f"  References:")
                    for ref in fix.references:
                        print(f"    {ref}")
                print("=" * 70)
                print("")
            return 0

        handlers = service._rule_handlers()
        if output_format == "json":
            catalogue = []
            for rid in sorted(handlers.keys()):
                fix = service.get_fix(rid)
                if fix:
                    catalogue.append({
                        "rule_id": rid,
                        "title": fix.title,
                        "fix_type": fix.fix_type,
                        "confidence": fix.confidence,
                    })
            print(json.dumps(catalogue, indent=2, default=str))
        else:
            print("")
            print("=" * 70)
            print("  AVAILABLE CODE FIX TEMPLATES")
            print("=" * 70)
            print(f"  Scan path: {scan_path}")
            print(f"  Use --rule RULE_ID to see fix details for a specific rule.")
            print("")
            for rid in sorted(handlers.keys()):
                fix = service.get_fix(rid)
                if fix:
                    print(f"  {rid}")
                    print(f"    -> {fix.title} [{fix.fix_type} / {fix.confidence}]")
            print("=" * 70)
            print("")

        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1
