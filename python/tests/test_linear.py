"""Linear circuits (R/C/L, voltage & current sources) vs the nodal oracle."""
import numpy as np
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from oracles import nodal_mna, sine, sweep
from conftest import FS

RC = "Vin N001 0\nR1 N001 N002 1k\nC1 N002 0 100n"
RLC = "Vin N001 0\nR1 N001 N002 100\nL1 N002 N003 10m\nC1 N003 0 100n"
ISRC = "Iin N001 0\nR1 N001 0 1k\nC1 N001 0 100n"


def _run(text, out_id, out_node, drive):
    w = WDFCircuit(Netlist.parse(text), FS, output_element_id=out_id)
    return w.process(drive), nodal_mna(text, FS, drive, out_node)


def test_rc_lowpass():
    for x in (sine(1000, 0.8, FS, 0.03), sweep(20, 4000, 0.5, FS, 0.03)):
        y, r = _run(RC, "C1", "N002", x)
        assert np.max(np.abs(y - r)) < 1e-9


def test_rlc_inductor():
    for f in (1000, 5000):
        y, r = _run(RLC, "C1", "N003", sine(f, 1.0, FS, 0.02))
        assert np.max(np.abs(y - r)) < 1e-8


def test_current_source_norton():
    # near-ideal Norton (Rg=1e9): matches an ideal current source to ~1/Rg
    y, r = _run(ISRC, "C1", "N001", sine(1000, 1e-3, FS, 0.02))
    assert np.max(np.abs(y - r)) < 1e-5
