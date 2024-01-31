from src.fplan.fplan import Data, solve


def test_sample_solve() -> None:
    """Proof of concept solver test.  Verification is intentionally light"""
    config_data = Data()
    config_data.load_file('test/fplan/test_solve/sample.toml')

    res = solve(S=config_data, sepp=False, verbose=False)
    expected_spend = 128415.14293319076
    assert res[0] == expected_spend


def test_flat_solve() -> None:
    config_data = Data()
    config_data.load_file('test/fplan/test_solve/flat.toml')

    res = solve(S=config_data, sepp=False, verbose=False)
    expected_spend = 100_000.0
    assert res[0] == expected_spend

    for k in range(5):                      # Spend from savings first 5 years
        assert res[2+k*4+0] == expected_spend
        assert res[2+k*4+2] == 0.0

    for k in range(5, 50):                  # Spend from roth remaining 45 years
        assert res[2+k*4+0] == 0.0
        assert res[2+k*4+2] == expected_spend
