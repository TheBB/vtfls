from __future__ import annotations

import sys
from typing import TextIO

import click

from vtfls import VTFFile


@click.command()
@click.argument("filename", type=click.File("r"))
def main(filename: TextIO) -> None:
    try:
        vtf = VTFFile(filename)
        vtf.verify()
    except AssertionError as e:
        print("Error:", str(e), file=sys.stderr)
        sys.exit(1)
    vtf.summary()
