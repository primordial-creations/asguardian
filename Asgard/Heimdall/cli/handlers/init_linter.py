import argparse
from pathlib import Path

from Asgard.Heimdall.Init.linter_initializer import LinterInitializer


def run_init_linter(args, verbose: bool = False) -> int:
    project_path = Path(args.path).resolve()

    if not project_path.exists():
        print(f"Error: path '{args.path}' does not exist.")
        return 1

    if not project_path.is_dir():
        print(f"Error: path '{args.path}' is not a directory.")
        return 1

    project_name = getattr(args, "project_name", None)
    project_type = getattr(args, "project_type", None)
    force = getattr(args, "force", False)

    initializer = LinterInitializer(
        project_path=project_path,
        project_name=project_name,
        force=force,
    )

    if project_type == "python":
        is_python, is_typescript = True, False
    elif project_type == "typescript":
        is_python, is_typescript = False, True
    elif project_type == "both":
        is_python, is_typescript = True, True
    else:
        is_python, is_typescript = initializer.detect_project_type()

    if verbose:
        detection_parts = []
        if is_python:
            detection_parts.append("Python")
        if is_typescript:
            detection_parts.append("TypeScript/JavaScript")
        detected = ", ".join(detection_parts) if detection_parts else "none"
        print(f"Project path: {project_path}")
        print(f"Project name: {initializer.project_name}")
        print(f"Detected type: {detected}")
        if project_type:
            print(f"Forced type:   {project_type}")
        print()

    results = initializer.init_all(project_type=project_type)

    print(f"Initializing linter configs in: {project_path}")
    print()

    print("  Config files:")
    for filename, status in results:
        print(f"    {filename:.<40s} {status}")

    print()
    print("  CLI tools:")
    tool_results = initializer.check_tools(is_python, is_typescript)
    missing_tools = []
    for tool in tool_results:
        marker = "[OK]" if tool["installed"] else "[MISSING]"
        print(f"    {marker:10s} {tool['name']:.<30s} {tool['purpose']}")
        if not tool["installed"]:
            missing_tools.append(tool)

    print()
    print("  VSCode extensions:")
    ext_results = initializer.check_vscode_extensions(is_python, is_typescript)
    missing_extensions = []
    if ext_results:
        for ext in ext_results:
            marker = "[OK]" if ext["installed"] else "[MISSING]"
            print(f"    {marker:10s} {ext['extension_id']}")
            if not ext["installed"]:
                missing_extensions.append(ext)
    else:
        print("    (could not detect VSCode - extension check skipped)")

    if missing_tools or missing_extensions:
        print()
        print("  " + "=" * 60)
        print("  WARNING: Missing dependencies detected")
        print("  " + "=" * 60)

        if missing_tools:
            print()
            print("  Install missing CLI tools:")
            for tool in missing_tools:
                print(f"    $ {tool['install']}")

        if missing_extensions:
            print()
            print("  Install missing VSCode extensions:")
            install_ids = " ".join(ext["extension_id"] for ext in missing_extensions)
            print(f"    $ code --install-extension {install_ids}")
            print()
            print("  Or in VSCode: open the Extensions panel (Ctrl+Shift+X),")
            print("  search for each extension, and click Install.")
            print("  (VSCode will also prompt you from .vscode/extensions.json)")

        print()
        print("  " + "=" * 60)
    else:
        print()

    print()
    print("Done. Run 'pre-commit install' to activate git hooks (if applicable).")

    return 0
