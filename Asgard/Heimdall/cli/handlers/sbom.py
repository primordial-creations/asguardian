import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat
from Asgard.Heimdall.Dependencies.services.sbom_generator import SBOMGenerator


def run_sbom_generation(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        fmt_str = getattr(args, "format", "cyclonedx")
        fmt = SBOMFormat.SPDX if fmt_str == "spdx" else SBOMFormat.CYCLONEDX

        config = SBOMConfig(
            scan_path=scan_path,
            output_format=fmt,
            project_name=getattr(args, "project_name", "") or "",
            project_version=getattr(args, "project_version", "") or "",
        )
        generator = SBOMGenerator(config)
        document = generator.generate(str(scan_path))

        if fmt == SBOMFormat.SPDX:
            output_dict = generator.to_spdx_json(document)
        else:
            output_dict = generator.to_cyclonedx_json(document)

        output_json = json.dumps(output_dict, indent=2, default=str)

        output_file = getattr(args, "output", None)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as fh:
                fh.write(output_json)
            print(f"SBOM written to: {output_file}")
            print(f"Format:          {fmt_str.upper()}")
            print(f"Components:      {document.total_components}")
        else:
            print(output_json)

        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1
