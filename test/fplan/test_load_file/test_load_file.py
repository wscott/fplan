import math

from src.fplan.fplan import Data


def test_load_file1():
    # test using examples/sample.toml config file
    #   TODO: determine if we want to test against the examples.
    #       Pro - ensures they work
    #       Con - doubles work when changing examples
    #   For now, leave it in here.  We can delete the test if we decide against this path.
    config_data = Data()
    config_data.load_file('examples/sample.toml')
    _check_sample_config_contents(config_data)


def test_load_file2():
    # test using local config file
    config_data = Data()
    config_data.load_file('test/fplan/test_load_file/sample.toml')
    _check_sample_config_contents(config_data)


def _check_sample_config_contents(cfg: Data) -> None:
    assert math.isclose(cfg.i_rate, 1.021)
    assert math.isclose(cfg.r_rate, 1.08)

    assert cfg.startage == 55
    assert cfg.endage == 100

    assert cfg.stded == 27700
    assert math.isclose(cfg.state_tax, 3 / 100.0)
    assert math.isclose(cfg.state_cg_tax, 0 / 100.0)
    assert cfg.taxrates == [[0, 0],
                            [0, 10/100.0],
                            [22000, 12/100.0],
                            [89450, 22/100.0],
                            [190750, 24/100.0],
                            [364200, 32/100.0],
                            [462500, 35/100.0],
                            [693750, 37/100.0]]

    assert cfg.workyr == 10
    assert cfg.maxsave == 60000
    assert cfg.maxsave_inflation is False
    assert math.isclose(cfg.worktax, 1.25)
    assert cfg.retireage == 65
    assert cfg.numyr == 35

    assert _isclose_dol(cfg.aftertax['bal'], 212000)
    assert _isclose_dol(cfg.aftertax['basis'], 115000)

    assert _isclose_dol(cfg.IRA['bal'], 420000)
    assert _isclose_dol(cfg.IRA['maxcontrib'], 18000)

    assert _isclose_dol(cfg.roth['bal'], 50000)
    assert _isclose_dol(cfg.roth['maxcontrib'], 11000)
    assert all(_isclose_dol(x, y) for x, y in zip(cfg.roth['contributions'][0], [54, 20000]))
    assert all(_isclose_dol(x, y) for x, y in zip(cfg.roth['contributions'][1], [55, 20000]))

    expected_inc_tax = [0, 0, 0, 0, 0, 47802.89, 48806.76, 49831.70, 50878.16, 51946.60, 53037.48, 54151.27, 55288.44, 56449.50, 57634.94, 58845.27, 60081.03, 61342.73, 62630.92, 63946.17, 65289.04, 66660.11, 68059.98, 69489.24, 70948.51, 72438.43, 73959.64, 75512.79, 77098.56, 78717.63, 80370.70, 82058.48, 83781.71, 85541.12, 87337.49]
    expected_expenses = [9000, 9000, 9000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert all(_isclose_dol(x, y) for x, y in zip(cfg.income, expected_inc_tax))
    assert all(_isclose_dol(x, y) for x, y in zip(cfg.expenses, expected_expenses))
    assert all(_isclose_dol(x, y) for x, y in zip(cfg.taxed, expected_inc_tax))

    assert cfg.sepp_end == 5
    assert cfg.sepp_ratio == 25


def _isclose_dol(x: float, y: float) -> bool:
    """Test for dollar values within $0.01"""
    return math.isclose(x, y, abs_tol=0.01)
