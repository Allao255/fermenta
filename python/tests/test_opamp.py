"""Ideal op-amp circuits (nullor) vs the MNA oracle."""
import numpy as np
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from oracles import nodal_mna, sine
from conftest import FS

INV = ("Vin N001 0\nR1 N001 N002 10k\nR2 N002 N003 100k\n"
       "C1 N002 N003 1n\nXOA1 N002 0 N003 idealopamp")
OA_DIODE = ("Vin N001 0\nR1 N001 N002 10k\nR2 N002 N003 100k\n"
            "XOA1 N002 0 N003 idealopamp\nR3 N003 N004 1k\n"
            "XD1 N004 0 extendedschockleydiode params: "
            "Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg\nC1 N004 0 1n")


def test_inverting_amp_linear():
    x = sine(500, 0.5, FS, 0.02)
    y = WDFCircuit(Netlist.parse(INV), FS, output_node="N003").process(x)
    r = nodal_mna(INV, FS, x, "N003")
    assert np.max(np.abs(y - r)) < 1e-9


def test_opamp_plus_diode():
    x = sine(1000, 0.5, FS, 0.02)
    y = WDFCircuit(Netlist.parse(OA_DIODE), FS, output_node="N004").process(x)
    r = nodal_mna(OA_DIODE, FS, x, "N004")
    assert np.max(np.abs(y - r)) / np.max(np.abs(r)) < 1e-4
