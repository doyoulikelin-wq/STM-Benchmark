"""CLI execution status must include cleanup failures even without errors."""
from unittest.mock import patch

import pytest

from stm_bench.cli import main


@pytest.mark.parametrize("cleanup_failures,expected_status", [(1, 1), (0, 0)])
def test_evaluate_exit_status_includes_cleanup_failures(tmp_path, cleanup_failures, expected_status):
    result = {"policies": {
        "rule": {"errors": 0, "cleanup_failures": 0},
        "random": {"errors": 0, "cleanup_failures": cleanup_failures},
    }}
    output = tmp_path / "evaluation"
    with patch("stm_bench.runner.evaluate", return_value=result) as evaluate:
        status = main(["evaluate", "--out", str(output)])
    evaluate.assert_called_once()
    assert not output.exists()
    assert status == expected_status


@pytest.mark.parametrize("cleanup_failures,expected_status", [(1, 1), (0, 0)])
def test_compare_exit_status_includes_cleanup_failures(tmp_path, cleanup_failures, expected_status):
    result = {"aggregate": {"episodes": 4}, "by_profile": {
        "strict-v1": {"rule": {"errors": 0, "cleanup_failures": 0}},
        "relaxed-v1": {"rule": {"errors": 0, "cleanup_failures": cleanup_failures}},
    }}
    output = tmp_path / "comparison"
    with patch("stm_bench.experiments.compare_profiles", return_value=result) as compare:
        status = main(["compare", "--out", str(output)])
    compare.assert_called_once()
    assert not output.exists()
    assert status == expected_status
