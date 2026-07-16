from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_uv_owns_the_project_toolchain() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert (ROOT / "uv.lock").is_file()
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"
    assert config["build-system"]["build-backend"] == "uv_build"
    assert config["tool"]["uv"]["package"] is True
    assert config["tool"]["uv"]["required-version"] == ">=0.8.0"
    assert config["tool"]["uv"]["build-backend"]["module-name"] == "magazine"
    assert "pytest>=8.0" in config["dependency-groups"]["dev"]


def test_documented_commands_do_not_bypass_uv() -> None:
    direct_command = re.compile(
        r"^(?:(?:python3?|pip3?|pytest)(?:\s|$)|mag(?!\s*=)(?:\s|$))",
        re.MULTILINE,
    )

    for relative_path in ("README.md", "AGENTS.md"):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert direct_command.search(text) is None, relative_path

    dependency_messages = "\n".join(
        (ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in ("src/magazine/render.py", "src/magazine/booklet.py")
    )
    assert "pip install" not in dependency_messages
