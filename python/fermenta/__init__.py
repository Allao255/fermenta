"""
fermenta -- a Python port of the VIOLA topology-based Wave Digital Filter engine.

This package mirrors the pipeline of the MATLAB VIOLA framework
(polimi-ispl/viola):

    LTspice netlist
        -> parse                (netlist.py)         [IMPLEMENTED]
        -> circuit graph        (graph.py)           [IMPLEMENTED]
        -> spanning tree/cotree (graph.py)           [IMPLEMENTED]
        -> fundamental matrices Q (cutset) & B (loop) (graph.py) [IMPLEMENTED]
        -> WDF R-type scattering matrix S            (adaptors.py) [SCAFFOLD]
        -> per-sample wave scattering + NL iteration (solver.py)  [SCAFFOLD]

The deterministic linear-algebra stages (parse -> Q/B) are fully implemented and
can be validated directly against VIOLA's MATLAB output. The wave-domain solver
is scaffolded with the equations documented, to be completed as "the Python
version we will build".

See ../../docs for the theory guide, and ../../tests for ground-truth vectors.
"""

__version__ = "0.1.0"

from .netlist import Netlist, Element            # noqa: F401
from .graph import CircuitGraph                   # noqa: F401
from .solver import WDFCircuit                    # noqa: F401
