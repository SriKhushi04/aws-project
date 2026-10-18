"""Tests for Lambda packaging script and archive integrity."""
import zipfile
from pathlib import Path
from scripts.package_lambdas import LAMBDA_TARGETS, package_lambda, DIST_DIR, PROJECT_ROOT

def test_package_lambdas_creates_valid_archives():
    """Verify that package_lambda produces valid ZIP archives with required modules."""
    for target in LAMBDA_TARGETS:
        zip_path = package_lambda(target)
        assert zip_path.exists(), f"Target zip {zip_path} was not created."
        assert zip_path.stat().st_size > 0, f"Target zip {zip_path} is empty."

        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.namelist()

            # Must include package init
            assert "lambdas/__init__.py" in file_list

            # Must include common modules
            assert "lambdas/common/config.py" in file_list
            assert "lambdas/common/dynamodb_service.py" in file_list
            assert "lambdas/common/utils.py" in file_list

            # Must include the specific target lambda function
            if target["name"] == "waste-ingest":
                assert "lambdas/waste_ingest/lambda_function.py" in file_list
            elif target["name"] == "waste-analytics":
                assert "lambdas/waste_analytics/lambda_function.py" in file_list
                assert "lambdas/waste_analytics/predictor.py" in file_list
                assert "lambdas/waste_analytics/optimizer.py" in file_list
            elif target["name"] == "waste-api":
                assert "lambdas/waste_api/lambda_function.py" in file_list

            # Must NOT include cache or compiled bytecode files
            for member in file_list:
                assert "__pycache__" not in member
                assert not member.endswith(".pyc")
                assert not member.endswith(".pyo")

