"""Single-diode circuits (D / Dser / Dap) vs the nodal oracle (Wright-omega acc)."""
import numpy as np
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from oracles import nodal_mna, sine
from conftest import FS, load_example

DAP = ("Vin N001 0\nR1 N001 N002 1k\nC1 N002 0 10n\n"
       "XDap1 N002 0 extendedschockleydiodeantiparallel params: "
       "Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg n=1")
DSER = ("Vin N001 0\nR1 N001 N002 1k\nC1 N002 0 10n\n"
        "XDser1 N002 0 extendedschockleydiodeseries params: "
        "Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg n=2")


def _rel(text, out_id, out_node, x):
    w = WDFCircuit(Netlist.parse(text), FS, output_element_id=out_id)
    y = w.process(x); r = nodal_mna(text, FS, x, out_node)
    return np.max(np.abs(y - r)) / max(np.max(np.abs(r)), 1e-9)


def test_demo_single_diode():
    txt = load_example("DEMO")
    assert _rel(txt, "C1", "N003", sine(1000, 0.5, FS, 0.03)) < 1e-4


def test_antiparallel_diode():
    assert _rel(DAP, "C1", "N002", sine(1000, 2.0, FS, 0.02)) < 1e-4


def test_series_diode():
    assert _rel(DSER, "C1", "N002", sine(300, 3.0, FS, 0.02)) < 1e-4
