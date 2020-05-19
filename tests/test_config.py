import os
from typing import List
from unittest.mock import patch, MagicMock, mock_open

import pytest

from clin.config import load_config

VALID_CONFIG = """
environments:
    dev:
        nakadi_url: https://nakadi.dev
    prod:
        nakadi_url: https://nakadi.prod
"""

all_config_files = [os.path.abspath(".clin"), os.path.expanduser("~/.clin")]


@patch("os.path.isfile")
@pytest.mark.parametrize("config_file", all_config_files)
def test_reads_config_from_single_config_file(m_isfile: MagicMock, config_file: str):
    m_isfile.side_effect = _only_files_exist([config_file])

    with patch("clin.config.open", mock_open(read_data=VALID_CONFIG)) as m_open:
        config = load_config()

    assert len(config.environments) == 2
    assert "dev" in config.environments
    assert config.environments["dev"].nakadi_url == "https://nakadi.dev"
    assert "prod" in config.environments
    assert config.environments["prod"].nakadi_url == "https://nakadi.prod"

    m_open.assert_called_with(config_file)


@patch("os.path.isfile")
def test_reads_config_from_project_config_before_user_config(m_isfile: MagicMock):
    m_isfile.side_effect = _only_files_exist(all_config_files)

    with patch("clin.config.open", mock_open(read_data=VALID_CONFIG)) as m_open:
        config = load_config()

    assert len(config.environments) == 2

    m_open.assert_called_with(os.path.abspath(".clin"))


@patch("os.path.isfile")
def test_errors_when_no_config_file_exists(m_isfile: MagicMock):
    m_isfile.return_value = False

    with pytest.raises(Exception) as ex:
        load_config()

    config_locations = [os.getcwd(), os.path.expanduser("~")]
    assert str(ex.value) == f"No valid configuration file found. Inspected locations: {config_locations}"


@patch("os.path.isfile")
def test_errors_when_config_does_not_contain_environments(m_isfile: MagicMock):
    m_isfile.side_effect = _only_files_exist(all_config_files)

    invalid_config = """
        dev:
            xxx: nope
    """

    with patch("clin.config.open", mock_open(read_data=invalid_config)), pytest.raises(Exception) as ex:
        load_config()

    assert str(ex.value) == "Environments section not found in configuration"


@patch("os.path.isfile")
def test_errors_when_config_does_not_contain_nakadi(m_isfile: MagicMock):
    m_isfile.side_effect = _only_files_exist(all_config_files)

    invalid_config = """
    environments:
        dev:
            xxx: nope
    """

    with patch("clin.config.open", mock_open(read_data=invalid_config)), pytest.raises(Exception) as ex:
        load_config()

    assert str(ex.value) == "Nakadi url not found in configuration for environment: dev"


@patch("os.path.isfile")
def test_errors_when_config_is_invalid_yaml(m_isfile: MagicMock):
    m_isfile.side_effect = _only_files_exist(all_config_files)

    invalid_config = "}}:"

    with patch("clin.config.open", mock_open(read_data=invalid_config)), pytest.raises(Exception) as ex:
        load_config()

    assert str(ex.value).startswith(f"Failed to parse configuration file: {all_config_files[0]}")


def _only_files_exist(file_names: List[str]):
    return lambda *args, **kwargs: args[0] in file_names
