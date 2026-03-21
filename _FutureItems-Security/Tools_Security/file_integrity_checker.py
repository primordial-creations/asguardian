#!/usr/bin/env python3
"""
File Integrity Checker
Creates and verifies file checksums to detect unauthorized modifications.
"""

import os
import hashlib
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class FileRecord:
    """Record of a file's integrity information."""
    path: str
    size: int
    md5: str
    sha256: str
    modified_time: str
    permissions: str


class FileIntegrityChecker:
    """Manages file integrity checking and monitoring."""

    def __init__(self, baseline_file: str = '.file_integrity_baseline.json'):
        self.baseline_file = baseline_file
        self.baseline: Dict[str, FileRecord] = {}
        self.current_scan: Dict[str, FileRecord] = {}

    def calculate_hashes(self, file_path: Path) -> tuple:
        """Calculate MD5 and SHA256 hashes for a file."""
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5_hash.update(chunk)
                    sha256_hash.update(chunk)
            return md5_hash.hexdigest(), sha256_hash.hexdigest()
        except (IOError, OSError):
            return None, None

    def get_file_record(self, file_path: Path) -> Optional[FileRecord]:
        """Get integrity record for a file."""
        try:
            stat = file_path.stat()
            md5, sha256 = self.calculate_hashes(file_path)

            if md5 is None:
                return None

            return FileRecord(
                path=str(file_path.absolute()),
                size=stat.st_size,
                md5=md5,
                sha256=sha256,
                modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                permissions=oct(stat.st_mode)[-3:]
            )
        except (IOError, OSError):
            return None

    def scan_directory(self, directory: Path, patterns: List[str] = None) -> Dict[str, FileRecord]:
        """Scan directory and create integrity records."""
        records = {}

        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}

        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                file_path = Path(root) / file

                # Skip binary and temporary files
                if file_path.suffix in {'.pyc', '.pyo', '.so', '.dylib', '.o'}:
                    continue

                # Check patterns if specified
                if patterns:
                    if not any(file_path.match(p) for p in patterns):
                        continue

                record = self.get_file_record(file_path)
                if record:
                    records[record.path] = record

        return records

    def create_baseline(self, directory: Path, patterns: List[str] = None):
        """Create a new baseline from directory scan."""
        print(f"Creating baseline for: {directory.absolute()}")

        self.baseline = self.scan_directory(directory, patterns)

        # Save baseline
        self.save_baseline()

        print(f"Baseline created with {len(self.baseline)} files")
        return len(self.baseline)

    def save_baseline(self):
        """Save baseline to file."""
        data = {
            'created': datetime.now().isoformat(),
            'files': {path: asdict(record) for path, record in self.baseline.items()}
        }

        with open(self.baseline_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Baseline saved to: {self.baseline_file}")

    def load_baseline(self) -> bool:
        """Load baseline from file."""
        if not Path(self.baseline_file).exists():
            return False

        try:
            with open(self.baseline_file, 'r') as f:
                data = json.load(f)

            self.baseline = {
                path: FileRecord(**record)
                for path, record in data['files'].items()
            }

            return True
        except (IOError, json.JSONDecodeError):
            return False

    def verify_integrity(self, directory: Path, patterns: List[str] = None) -> Dict:
        """Verify file integrity against baseline."""
        if not self.load_baseline():
            return {'error': 'No baseline found. Create one first with --create-baseline'}

        print(f"Verifying integrity for: {directory.absolute()}")

        self.current_scan = self.scan_directory(directory, patterns)

        results = {
            'verified_at': datetime.now().isoformat(),
            'total_baseline_files': len(self.baseline),
            'total_current_files': len(self.current_scan),
            'modified': [],
            'added': [],
            'deleted': [],
            'permission_changes': [],
            'ok': []
        }

        # Check for modified and deleted files
        for path, baseline_record in self.baseline.items():
            if path in self.current_scan:
                current_record = self.current_scan[path]

                # Check for modifications
                if current_record.sha256 != baseline_record.sha256:
                    results['modified'].append({
                        'path': path,
                        'old_hash': baseline_record.sha256[:16] + '...',
                        'new_hash': current_record.sha256[:16] + '...',
                        'old_size': baseline_record.size,
                        'new_size': current_record.size
                    })
                elif current_record.permissions != baseline_record.permissions:
                    results['permission_changes'].append({
                        'path': path,
                        'old_perms': baseline_record.permissions,
                        'new_perms': current_record.permissions
                    })
                else:
                    results['ok'].append(path)
            else:
                results['deleted'].append({
                    'path': path,
                    'size': baseline_record.size
                })

        # Check for new files
        for path in self.current_scan:
            if path not in self.baseline:
                record = self.current_scan[path]
                results['added'].append({
                    'path': path,
                    'size': record.size
                })

        return results

    def print_report(self, results: Dict):
        """Print verification report."""
        print("\n" + "=" * 70)
        print("FILE INTEGRITY VERIFICATION REPORT")
        print("=" * 70)

        if 'error' in results:
            print(f"\nError: {results['error']}")
            return 1

        print(f"\nVerified at: {results['verified_at']}")
        print(f"Baseline files: {results['total_baseline_files']}")
        print(f"Current files: {results['total_current_files']}")

        # Summary
        print("\n" + "-" * 40)
        print("SUMMARY")
        print("-" * 40)
        print(f"✓ Unchanged: {len(results['ok'])}")
        print(f"⚠ Modified: {len(results['modified'])}")
        print(f"+ Added: {len(results['added'])}")
        print(f"- Deleted: {len(results['deleted'])}")
        print(f"🔒 Permission changes: {len(results['permission_changes'])}")

        # Details
        if results['modified']:
            print("\n" + "-" * 40)
            print("MODIFIED FILES")
            print("-" * 40)
            for item in results['modified']:
                print(f"\n⚠ {item['path']}")
                print(f"  Size: {item['old_size']} → {item['new_size']} bytes")
                print(f"  Hash: {item['old_hash']} → {item['new_hash']}")

        if results['added']:
            print("\n" + "-" * 40)
            print("NEW FILES")
            print("-" * 40)
            for item in results['added']:
                print(f"+ {item['path']} ({item['size']} bytes)")

        if results['deleted']:
            print("\n" + "-" * 40)
            print("DELETED FILES")
            print("-" * 40)
            for item in results['deleted']:
                print(f"- {item['path']} ({item['size']} bytes)")

        if results['permission_changes']:
            print("\n" + "-" * 40)
            print("PERMISSION CHANGES")
            print("-" * 40)
            for item in results['permission_changes']:
                print(f"🔒 {item['path']}: {item['old_perms']} → {item['new_perms']}")

        print("\n" + "=" * 70)

        # Return exit code
        if results['modified'] or results['deleted']:
            return 1
        return 0

    def verify_single_file(self, file_path: Path) -> Dict:
        """Verify a single file's integrity."""
        record = self.get_file_record(file_path)

        if not record:
            return {'error': f'Cannot read file: {file_path}'}

        return {
            'file': str(file_path.absolute()),
            'size': record.size,
            'md5': record.md5,
            'sha256': record.sha256,
            'modified': record.modified_time,
            'permissions': record.permissions
        }


def main():
    parser = argparse.ArgumentParser(
        description='File integrity checking and monitoring'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='File or directory to check (default: current directory)'
    )
    parser.add_argument(
        '--create-baseline',
        action='store_true',
        help='Create a new baseline from the specified path'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify files against baseline'
    )
    parser.add_argument(
        '--hash',
        action='store_true',
        help='Show hash for a single file'
    )
    parser.add_argument(
        '-b', '--baseline-file',
        default='.file_integrity_baseline.json',
        help='Baseline file path (default: .file_integrity_baseline.json)'
    )
    parser.add_argument(
        '-p', '--pattern',
        action='append',
        help='File patterns to include (can be specified multiple times)'
    )

    args = parser.parse_args()
    checker = FileIntegrityChecker(baseline_file=args.baseline_file)

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    if args.hash and target.is_file():
        result = checker.verify_single_file(target)
        if 'error' in result:
            print(f"Error: {result['error']}")
            return 1

        print("\n" + "=" * 60)
        print("FILE HASH INFORMATION")
        print("=" * 60)
        print(f"\nFile: {result['file']}")
        print(f"Size: {result['size']} bytes")
        print(f"MD5: {result['md5']}")
        print(f"SHA256: {result['sha256']}")
        print(f"Modified: {result['modified']}")
        print(f"Permissions: {result['permissions']}")
        print("=" * 60)
        return 0

    if args.create_baseline:
        if target.is_file():
            print("Error: Cannot create baseline from single file")
            return 1
        checker.create_baseline(target, patterns=args.pattern)
        return 0

    if args.verify or not args.create_baseline:
        if target.is_file():
            result = checker.verify_single_file(target)
            print(json.dumps(result, indent=2))
        else:
            results = checker.verify_integrity(target, patterns=args.pattern)
            return checker.print_report(results)

    return 0


if __name__ == '__main__':
    exit(main())
