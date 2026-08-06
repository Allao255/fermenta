"""
fermenta -- a Python port of VIOLA's topology-based Wave Digital Filter engine.

Pipeline (mirrors the MATLAB VIOLA framework, polimi-ispl/viola):

    LTspice netlist
        -> parse                                      (netlist.py)
        -> circuit graph, spanning tree / cotree      (graph.py)
        -> fundamental matrices Q (cutset), B (loop)  (graph.py)
        -> R-type scattering matrix S                 (adaptors.py)
        -> per-sample wave scattering                 (solver.py)
        -> self-contained C++ DSP engine              (codegen.py)

Typical use:

    from fermenta import Netlist, WDFCircuit
    nl  = Netlist.parse(open("pedal.txt").read())
    wdf = WDFCircuit(nl, fs=48000, output_node="N002")
    y   = wdf.process(x)

See docs/ for the theory guide and the LTspice-to-VST3 walkthroughs.
"""

__version__ = "1.0.0"

from .netlist import Netlist, Element            # noqa: F401
from .graph import CircuitGraph                   # noqa: F401
from .solver import WDFCircuit                    # noqa: F401
