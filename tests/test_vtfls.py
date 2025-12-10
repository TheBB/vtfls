from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from vtfls.__main__ import main

FILES = [
    "DroppedBox.vtf",
    "Q4.vtf",
    "T3.vtf",
]


@pytest.mark.parametrize("filename", FILES)
def test_vtfls(filename: str) -> None:
    inpath = Path(__file__).parent / "testdata" / filename
    outpath = inpath.with_suffix(".out")

    result = CliRunner().invoke(main, [str(inpath.absolute())])
    if result.exit_code != 0:
        print(result.stdout)
        print(result.stderr)
        assert False

    assert result.stdout == outpath.open("r").read()
