from importlib.metadata import entry_points, version

import tomllib


def test_version_and_console_script():
    assert version("felt") == "0.1.0"
    scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert scripts["felt"] == "felt.app:main"


def test_pyproject_is_portable():
    with open("pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    assert data["project"]["requires-python"] == ">=3.10"
    assert any(d.startswith("textual") for d in data["project"]["dependencies"])
    assert data["project"]["scripts"]["felt"] == "felt.app:main"
