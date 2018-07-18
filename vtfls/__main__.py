from vtfls import VTFFile

import click
import sys


@click.command()
@click.argument('filename', type=click.File('r'))
def main(filename):
    try:
        vtf = VTFFile(filename)
        vtf.verify()
    except AssertionError as e:
        print('Error:', str(e), file=sys.stderr)
        sys.exit(1)
    vtf.summary()
