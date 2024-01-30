from src.fplan.fplan import Data


def test_load_file1():
    # test using examples/sample.toml config file
    #   TODO: determine if we want to test against the examples.
    #       Pro - ensures they work
    #       Con - doubles work when changing examples and tests too
    config_data = Data()
    config_data.load_file('examples/sample.toml')
    _check_config_contents(config_data)


def test_load_file2():
    # test using local config file
    config_data = Data()
    config_data.load_file('test/fplan/test_load_file/test1.toml')
    _check_config_contents(config_data)

def _check_config_contents(cfg: Data) -> None:
    assert cfg.i_rate == 1.021  # questionable floating point comparison
    assert cfg.r_rate == 1.08

    assert cfg.startage == 55
    assert cfg.endage == 100

    assert cfg.stded == 27700
    assert cfg.state_tax == 3 / 100.0
    assert cfg.state_cg_tax == 0 / 100.0
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
    assert cfg.maxsave_inflation == False
    assert cfg.worktax == 1.25
    assert cfg.retireage == 65
    assert cfg.numyr == 35

    assert cfg.aftertax['bal'] == 212000
    assert cfg.aftertax['basis'] == 115000

    assert cfg.IRA['bal'] == 420000
    assert cfg.IRA['maxcontrib'] == 18000

    assert cfg.roth['bal'] == 50000
    assert cfg.roth['maxcontrib'] == 11000
    assert cfg.roth['contributions'] == [[54, 20000], [55, 20000]]

    # TODO Determine if this is fragile on other python versions.  FP compares like this give me the willies.
    assert cfg.income == [0, 0, 0, 0, 0, 47802.892452600514, 48806.75319410512, 49831.69501118133, 50878.16060641613, 51946.60197915086, 53037.480620713024, 54151.26771374799, 55288.4443357367, 56449.50166678716, 57634.94120178968, 58845.27496702727, 60081.02574133483, 61342.72728190286, 62630.924554822814, 63946.17397047408, 65289.043623854035, 66660.11353995497, 68059.975924294, 69489.23541870418, 70948.50936249696, 72438.42805910938, 73959.63504835068, 75512.78738436603, 77098.55591943773, 78717.6255937459, 80370.69573121457, 82058.48034157006, 83781.70842874303, 85541.1243057466, 87337.48791616729]
    assert cfg.expenses == [9000, 9000, 9000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert cfg.taxed == [0, 0, 0, 0, 0, 47802.892452600514, 48806.75319410512, 49831.69501118133, 50878.16060641613, 51946.60197915086, 53037.480620713024, 54151.26771374799, 55288.4443357367, 56449.50166678716, 57634.94120178968, 58845.27496702727, 60081.02574133483, 61342.72728190286, 62630.924554822814, 63946.17397047408, 65289.043623854035, 66660.11353995497, 68059.975924294, 69489.23541870418, 70948.50936249696, 72438.42805910938, 73959.63504835068, 75512.78738436603, 77098.55591943773, 78717.6255937459, 80370.69573121457, 82058.48034157006, 83781.70842874303, 85541.1243057466, 87337.48791616729]

    assert cfg.sepp_end == 5
    assert cfg.sepp_ratio == 25
