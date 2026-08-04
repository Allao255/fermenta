"""
example_demo.py -- end-to-end use of the wdfviola scaffold on the DEMO circuit.

Linear stages (parse -> graph -> Q/B -> R-type scattering) run fully. The DEMO
circuit contains a diode (nonlinear root), so process() will stop at the
build-later stage with a clear message -- that is expected for the scaffold.
Run tests/validate_linear_engine.py to see the linear engine matched to a nodal
reference at machine precision.
"""

import os
from wdfviola.netlist import Netlist
from wdfviola.graph import CircuitGraph

BASE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(BASE, "..", "viola", "windows", "Data", "Input", "Netlist", "DEMO.txt")


def main():
    nl = Netlist.parse(open(DEMO).read())
    print("Parsed DEMO netlist:")
    print("  input source:", nl.input_id)
    for e in nl.elements:
        print(f"    {e.id:12s} {e.type:5s} {e.nodes}")

    g = CircuitGraph(nl)
    print("\nTopology (VIOLA-equivalent):")
    print("  " + g.summary().replace("\n", "\n  "))

    print("\nThe fundamental matrices Q (cutset) and B (loop) above are exactly what "
          "VIOLA computes in getQB.m; max|Q B^T| == 0 confirms a valid decomposition.")
    print("Fully-working linear engine + validation: tests/validate_linear_engine.py")


if __name__ == "__main__":
    main()
