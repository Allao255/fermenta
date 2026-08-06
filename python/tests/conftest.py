import os
import pytest

FS = 48000
_HERE = os.path.dirname(__file__)
# Netlists ship with the repo; a full VIOLA clone (if present) also works.
_BUNDLED = os.path.abspath(os.path.join(_HERE, "..", "..", "examples", "viola"))
_VIOLA = os.path.abspath(os.path.join(_HERE, "..", "..", "viola", "windows",
                                      "Data", "Input", "Netlist"))
NETLIST_DIR = _BUNDLED if os.path.isdir(_BUNDLED) else _VIOLA


@pytest.fixture(scope="session")
def fs():
    return FS


@pytest.fixture(scope="session")
def netlist_dir():
    return NETLIST_DIR


def load_example(name):
    with open(os.path.join(NETLIST_DIR, name + ".txt")) as f:
        return f.read()
