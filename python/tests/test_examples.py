"""All seven VIOLA example netlists must build and produce finite output."""
import numpy as np
import pytest
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from oracles import sine
from conftest import FS, load_example

CASES = {
    "DEMO":  ("elem", "C1"),
    "MXR":   ("node", "N010"),
    "MBB":   ("node", "N001"),
    "MTG":   ("node", "N001"),
    "SBGEQ": ("node", "N001"),
    "EHBMP": ("node", "N001"),
    "DOD":   ("node", "N009"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_example_builds_and_runs(name):
    kind, val = CASES[name]
    nl = Netlist.parse(load_example(name))
    w = (WDFCircuit(nl, FS, output_node=val) if kind == "node"
         else WDFCircuit(nl, FS, output_element_id=val))
    y = w.process(sine(440, 0.1, FS, 0.01))
    assert np.all(np.isfinite(y))
