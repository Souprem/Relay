"""Fixtures shared by the integration tests."""

import pytest

from tests.site_support import run_export


@pytest.fixture(scope="session")
def site_export(tmp_path_factory):
    """One full `export_site` run over the real repository, under the network guard."""
    out = tmp_path_factory.mktemp("site") / "data"
    run_export(out)
    return out
