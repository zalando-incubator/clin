import toml

from clin import __version__


def test_pyproject_version_matches_package_version():
    pyproj = toml.load("pyproject.toml")
    assert __version__ == pyproj["tool"]["poetry"]["version"]
