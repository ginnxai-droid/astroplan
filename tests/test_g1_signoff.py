import pytest

from tests.reference_harness import load_reference_fixture, verify_reference_entry

pytestmark = pytest.mark.release_gate_g1


def test_g1_minimum_30_independent_reference_charts() -> None:
    entries = load_reference_fixture()
    assert len(entries) >= 30, "G1 requires >= 30 independent human-supplied reference charts"
    for entry in entries:
        assert verify_reference_entry(entry) == []
