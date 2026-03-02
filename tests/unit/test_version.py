"""Unit tests for version module."""

from __future__ import annotations

import re

from reinforce_spec.version import VERSION


class TestVersion:
    """Test version constant."""

    def test_version_is_string(self) -> None:
        assert isinstance(VERSION, str)

    def test_version_is_semver(self) -> None:
        assert re.match(r"^\d+\.\d+\.\d+", VERSION)

    def test_version_value(self) -> None:
        assert VERSION == "0.1.0"

    def test_package_version_matches(self) -> None:
        from reinforce_spec import __version__

        assert __version__ == VERSION
