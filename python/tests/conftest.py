import os
import pytest

FS = 48000
NETLIST_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "viola", "windows",
    "Data", "Input", "Netlist"))


@pytest.fixture(scope="session")
def fs():
    return FS


@pytest.fixture(scope="session")
def netlist_dir():
    return NETLIST_DIR


def load_example(name):
    with open(os.path.join(NETLIST_DIR, name + ".txt")) as f:
        return f.read()
