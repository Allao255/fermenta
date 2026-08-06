# fermenta (Python library)

Python port of VIOLA's topology-based Wave Digital Filter engine: an LTspice
netlist becomes a **single R-type scattering junction** built from the circuit's
fundamental cutset matrix `Q` and loop matrix `B`, rather than a tree of
series/parallel adaptors.

For the project overview, guides and validation results, see the repository
root and `docs/`.

## Install

```bash
cd python
pip install -e .            # library (numpy)
pip install -e ".[gui]"     # library + GUI/comparator (adds matplotlib)
pytest                      # 19 tests, every circuit class vs an MNA oracle
```

## Library use

```python
from fermenta import Netlist, WDFCircuit

nl  = Netlist.parse(open("pedal.txt").read())
wdf = WDFCircuit(nl, fs=48000, output_node="N002")   # op-amp circuits
# wdf = WDFCircuit(nl, fs=48000, output_element_id="C1")   # otherwise
y = wdf.process(x)          # numpy array in, numpy array out
```

Runnable example: `python example_demo.py`.

## Applications

```bash
python -m fermenta.gui       # netlist -> analyse -> plot -> export/build VST3
python -m fermenta.compare   # overlay two pedals (time, spectrum, metrics)
```

## Command line

```bash
# netlist -> self-contained C++ DSP header
python tools/gen_cpp.py pedal.txt --out-node N002 --name MyPedal \
       --pot-labels "Drive,Level" -o MyPedal.h
```

## Modules

| File | Role |
|---|---|
| `netlist.py` | LTspice netlist parsing, potentiometer expansion and tapers |
| `graph.py` | circuit graph, spanning tree/cotree, matrices `Q` and `B` |
| `elements.py` | port models (R, C, L, V, I) with bilinear reactances |
| `adaptors.py` | R-type scattering matrix `S` from `Q`, `B`, `Z` |
| `nonlinear.py` | extended-Shockley diode (Wright omega) |
| `opamp.py` | ideal op-amp as a nullor (dual voltage/current graphs) |
| `solver.py` | per-sample scattering loop, all circuit classes |
| `codegen.py` | emits the C++ DSP engine used by the VST3 |
| `gui.py`, `compare.py` | Tkinter applications |

## Validation tools

```bash
python tools/validate_cpp.py        # generated C++ vs the Python engine
python tools/fuzz_vs_viola.py 0 100 # random circuits vs an independent reference
```

`tools/viola_reference.py` is a second engine transcribed from the MATLAB
sources (nodal MNA with nullors instead of the `Q`/`B` path), used to
cross-check the main one.
