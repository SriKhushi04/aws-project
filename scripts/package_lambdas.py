#!/usr/bin/env python3
"""
package_lambdas.py - Automated deployment packaging utility.
Packages AWS Lambda functions into deployable ZIP archives in 'dist/'.

Uses only standard library modules (os, sys, zipfile, pathlib).
Does not require external dependencies or active AWS credentials.
"""
import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAMBDAS_DIR = PROJECT_ROOT / "lambdas"
DIST_DIR = PROJECT_ROOT / "dist"

LAMBDA_TARGETS = [
    {
        "name": "waste-ingest",
        "zip_name": "waste_ingest.zip",
        "handler": "lambdas.waste_ingest.lambda_function.lambda_handler",
        "include_subdirs": ["common", "waste_ingest"]
    },
    {
        "name": "waste-analytics",
        "zip_name": "waste_analytics.zip",
        "handler": "lambdas.waste_analytics.lambda_function.lambda_handler",
        "include_subdirs": ["common", "waste_analytics"]
    },
    {
        "name": "waste-api",
        "zip_name": "waste_api.zip",
        "handler": "lambdas.waste_api.lambda_function.lambda_handler",
        "include_subdirs": ["common", "waste_api"]
    }
]

EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".pyd"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".venv", "venv", ".git"}

def should_exclude(path: Path) -> bool:
    """Check if file or directory should be excluded from package."""
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    if path.suffix in EXCLUDE_EXTENSIONS:
        return True
    return False

def package_lambda(target: dict) -> Path:
    """Package a specific Lambda function into a ZIP archive preserving 'lambdas/' package path."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / target["zip_name"]

    print(f"[*] Packaging {target['name']} -> {zip_path.relative_to(PROJECT_ROOT)}...")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Include lambdas/__init__.py
        init_file = LAMBDAS_DIR / "__init__.py"
        if init_file.exists():
            zf.write(init_file, arcname="lambdas/__init__.py")

        # Include specified subdirectories
        for subdir_name in target["include_subdirs"]:
            subdir_path = LAMBDAS_DIR / subdir_name
            if not subdir_path.exists():
                print(f"    [WARN] Subdirectory not found: {subdir_path}")
                continue

            for root, dirs, files in os.walk(subdir_path):
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for file_name in files:
                    file_path = Path(root) / file_name
                    if should_exclude(file_path):
                        continue
                    # Archive path relative to project root (e.g. lambdas/common/config.py)
                    arcname = file_path.relative_to(PROJECT_ROOT).as_posix()
                    zf.write(file_path, arcname=arcname)

    size_kb = zip_path.stat().st_size / 1024.0
    print(f"    [OK] Created {target['zip_name']} ({size_kb:.1f} KB). Handler: {target['handler']}")
    return zip_path

def main():
    print("=" * 70)
    print("AWS Smart Waste Monitoring System - Lambda Packaging Utility")
    print(f"Root: {PROJECT_ROOT}")
    print(f"Output: {DIST_DIR}")
    print("=" * 70)

    if not LAMBDAS_DIR.exists():
        print(f"[ERROR] Lambdas directory not found: {LAMBDAS_DIR}")
        sys.exit(1)

    created_zips = []
    for target in LAMBDA_TARGETS:
        zip_file = package_lambda(target)
        created_zips.append(zip_file)

    print("-" * 70)
    print(f"[SUCCESS] Packaged {len(created_zips)} deployment archives in 'dist/'.")
    print("Ready for deployment via AWS CLI (`aws lambda create-function` / `update-function-code`).")
    print("=" * 70)

if __name__ == "__main__":
    main()

