"""Topology stage: Q (cutset) and B (loop) must satisfy Q Bᵀ = 0."""
import numpy as np
import pytest
from fermenta.netlist import Netlist
from fermenta.graph import CircuitGraph
from conftest import load_example

PLAIN = ["DEMO"]   # non-opamp examples have a single-graph Q/B


@pytest.mark.parametrize("name", PLAIN)
def test_qb_orthogonality(name):
    g = CircuitGraph(Netlist.parse(load_example(name)))
    assert g.orthogonality_residual() < 1e-9
    assert g.Q.shape[0] + g.B.shape[0] == g.Q.shape[1]


def test_rc_qb_small():
    g = CircuitGraph(Netlist.parse("Vin N001 0\nR1 N001 N002 1k\nC1 N002 0 100n\n.end"))
    assert g.Q.shape == (2, 3)
    assert g.B.shape == (1, 3)
    assert np.max(np.abs(g.Q @ g.B.T)) < 1e-12
