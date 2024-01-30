from src.fplan.fplan import Data


def test_load_file1():
    # test using examples/sample.toml config file
    #   TODO: determine if we want to test against the examples.
    #       Pro - ensures they work
    #       Con - doubles work when changing examples and tests too
    config_data = Data()
    config_data.load_file('examples/sample.toml')
    assert config_data.i_rate == 1.021  # questionable floating point comparison
    assert config_data.startage == 55


def test_load_file2():
    # test using local config file
    config_data = Data()
    config_data.load_file('test/fplan/test_load_file/test1.toml')
    assert config_data.i_rate == 1.021  # questionable floating point comparison
    assert config_data.startage == 55
