"""Regenerate the Kubernetes golden files.

Run from the repo root AFTER a deliberate, reviewed change to generated
output:

    python3 Asgard_Test/tests_Volundr/golden/kubernetes/regenerate.py

Diffs to these files are reviewed like code (plan 01 testing notes).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from Asgard.Volundr.Kubernetes import ManifestGenerator  # noqa: E402
from Asgard_Test.tests_Volundr.test_kubernetes_hardening import (  # noqa: E402
    ALL_KINDS,
    GOLDEN_DIR,
    GOLDEN_SETS,
    _config,
)


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    generator = ManifestGenerator()
    for kind in ALL_KINDS:
        for set_name, kwargs in GOLDEN_SETS.items():
            result = generator.generate(_config(kind, **kwargs))
            path = os.path.join(GOLDEN_DIR, f"{kind.value.lower()}_{set_name}.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(result.yaml_content)
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
