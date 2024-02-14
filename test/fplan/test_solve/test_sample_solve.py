import math

from src.fplan.fplan import Data, solve


def test_sample_solve() -> None:
    """Proof of concept solver test.  Verification is intentionally light"""
    config_data = Data()
    config_data.load_file('test/fplan/test_solve/sample.toml')

    res = solve(S=config_data, sepp=False, verbose=False)
    expected_spend = 128415.14
    assert _isclose(res[0], expected_spend)


def test_flat_solve() -> None:
    tolerance = 0       # Note: expect this result to be nearly exact

    config_data = Data()
    config_data.load_file('test/fplan/test_solve/flat.toml')

    res = solve(S=config_data, sepp=False, verbose=False)
    expected_spend = 100_000.0
    assert _isclose(res[0], expected_spend, tolerance)

    for k in range(5):                      # Spend from savings first 5 years
        assert _isclose(res[2 + k * 4 + 0], expected_spend, tolerance)
        assert _isclose(res[2 + k * 4 + 2], 0.0, tolerance)

    for k in range(5, 50):                  # Spend from roth remaining 45 years
        assert _isclose(res[2 + k * 4 + 0], 0.0, tolerance)
        assert _isclose(res[2 + k * 4 + 2], expected_spend, tolerance)


def _isclose(x: float, y: float, abs_tol=100) -> bool:
    """Default check is within 100 - intended for use with monetary solver results"""
    return math.isclose(x, y, abs_tol=abs_tol)
