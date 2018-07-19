## VTFLS

This repository contains the `vtfls` program: a script that reads ASCII VTF files (for Ceetron
GLView) and produces a summary. It is intended as a component in testing suites.

### Installation

This program requires Python 3 and the `click` package. Recommended installation is with `pip` to
the user home directory, i.e.

    pip install --user .

If `pip` points to Python 2 (which is the case on some systems), you may need to use `pip3` instead.

    pip3 install --user .

To use `vtfls`, the directory `$HOME/.local/bin` must be added to your path, e.g. in `.bashrc`:

    export PATH=$PATH:$HOME/.local/bin

### Usage

Run with a filename as the first and only argument.

    vtfls somefile.vtf

This will produce a brief summary of the steps, geometry blocks and fields defined in the file.

### Compatibility

This tool may be incompatible with some variants of the VTF format. Please report these as bugs.
