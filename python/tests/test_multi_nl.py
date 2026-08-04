"""Multiple simultaneous nonlinearities (SIM/DSR) vs the MNA oracle."""
import numpy as np
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from oracles import nodal_mna, sine
from conftest import FS, load_example

TWO_D = ("Vin N001 0\nR1 N001 N002 1k\n"
         "XD1 N002 0 extendedschockleydiode params: Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg\n"
         "C1 N002 0 10n\nR2 N002 N003 2.2k\n"
         "XD2 N003 0 extendedschockleydiode params: Is=2.52n eta=1.75 Vth=25.8563m Rs=1m Rp=1Meg\n"
         "C2 N003 0 4.7n")


def test_two_diodes_plain():
    w = WDFCircuit(Netlist.parse(TWO_D), FS, output_element_id="C2")
    assert w.sim
    x = sine(1000, 0.5, FS, 0.02)
    y = w.process(x); r = nodal_mna(TWO_D, FS, x, "N003")
    assert np.max(np.abs(y - r)) / np.max(np.abs(r)) < 1e-4


def test_dod_opamp_two_diodes():
    txt = load_example("DOD")
    w = WDFCircuit(Netlist.parse(txt), FS, output_node="N009")
    assert w.sim and w.has_opamp
    x = sine(250, 0.2, FS, 0.02)
    y = w.process(x); r = nodal_mna(txt, FS, x, "N009")
    assert np.max(np.abs(y - r)) / np.max(np.abs(r)) < 1e-4
