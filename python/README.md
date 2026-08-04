# wdfviola (Python) — a from-scratch port of VIOLA's WDF engine

A Python library that reproduces the **method** of the MATLAB VIOLA framework
(`polimi-ispl/viola`): turn an LTspice netlist into a Wave Digital Filter by
building a **single R-type scattering junction from circuit topology** (the
fundamental cutset matrix `Q` and loop matrix `B`), rather than a tree of
series/parallel adaptors.

This is **not** a wrapper around any existing Python WDF package — it is written
from the ground up to mirror VIOLA's pipeline so results can be compared
one-to-one.

## Install & test

```bash
cd python
pip install -e .            # installs the `wdfviola` package (needs numpy)
pytest                      # 19 tests, all circuit classes vs independent oracle
```

```python
from wdfviola import Netlist, WDFCircuit
nl  = Netlist.parse(open("DEMO.txt").read())
wdf = WDFCircuit(nl, fs=48000, output_element_id="C1")   # op-amp circuits: output_node="Nxxx"
y   = wdf.process(input_signal)          # numpy array in -> numpy array out
```


## Graphical app (Tkinter)

```bash
pip install -e ".[gui]"     # adds matplotlib
python -m wdfviola.gui       # or:  wdfviola-gui
```

Load/paste an LTspice netlist → **Analyze** (shows circuit class, elements,
detected pots, output choices, and a "supported components" help). Pick the
output node/element and sample rate, name the pedal knobs and move the pots with
live sliders, **Plot** the response to a test sine (waveform + spectrum) or the
transfer curve, then **Generate C++ header**, **Export a JUCE plugin project**,
or **Render a WAV** through the circuit — all from the GUI.

## Pipeline

| Stage | Module | Status |
|---|---|---|
| Parse LTspice netlist (elements, pots, eng-notation) | `wdfviola/netlist.py` | ✅ implemented |
| Build circuit graph, spanning tree / cotree | `wdfviola/graph.py` | ✅ implemented |
| Fundamental matrices `Q` (cutset), `B` (loop) | `wdfviola/graph.py` | ✅ implemented |
| Port models (R, C, L, V/DC, current src) bilinear reactances | `wdfviola/elements.py` | ✅ implemented |
| R-type scattering matrix `S` from `Q,B,R` | `wdfviola/adaptors.py` | ✅ implemented |
| Per-sample scattering loop (linear + ideal sources) | `wdfviola/solver.py` | ✅ implemented |
| Diode nonlinearity D/Dser/Dap (Wright-omega) | `nonlinear.py`, `solver.py` | ✅ implemented |
| Ideal op-amps (nullor, dual voltage/current graph) | `opamp.py` | ✅ implemented |
| Op-amp + one diode (one_non_lin_opamp, e.g. MXR) | `solver.py` | ✅ implemented |
| Log / inverse-log pot tapers | `netlist.py` | ✅ implemented |
| Multiple nonlinearities (SIM/DSR iterative) | `solver.py`, `nonlinear.py` | ✅ implemented |

The scattering matrix is built directly from topology:

```
M = [ B ; Q R⁻¹ ]           S = M⁻¹ [ -B ; Q R⁻¹ ]
```

with `R = diag(port reference resistances)`.

## Validation

```bash
pytest                                   # full suite (topology, linear, diode, op-amp, multi-NL)
python3 -m wdfviola.graph DEMO           # prints Q, B, and max|Q Bᵀ| == 0
```

Every implemented class is validated against an independent nodal/MNA solver. The linear engine matches (same trapezoidal cap
discretization) to **~1e-14** on sine, step and sweep inputs — the topology and
scattering core is proven correct. Ground-truth vectors for the full nonlinear
DEMO circuit live in `../tests/vectors/` (see `../tests/generate_test_vectors.py`).

## Circuit classes (all of VIOLA's)

| Class | Example | Method |
|---|---|---|
| `lin` | RC | R-type scattering |
| `one_non_lin` | DEMO | closed-form diode (Wright-omega) |
| `lin_opamp` | SBGEQ | nullor dual-graph |
| `one_non_lin_opamp` | MXR, Big Muff | nullor + closed-form diode |
| `non_lin[_opamp]` | DOD | SIM/DSR iterative solver |

All seven VIOLA example netlists (DEMO, MXR, MBB, MTG, SBGEQ, EHBMP, DOD) build
and run. Each class is validated against an independent nodal/MNA solver
(machine precision for linear/opamp; Wright-omega accuracy ~1e-5..1e-6 for the
diode nonlinearities — the same approximation VIOLA uses, so vs VIOLA it is
machine-precision).

## Not ported (out of scope for a simulation library)

- Plugin / GUI / C++ code generation (VIOLA's MATLAB Audio Toolbox + Coder output).
- Nothing structural. Inductor (L) and current sources (Iin/I) are now implemented and validated against a nodal solver (L to ~1e-12; current source is a near-ideal Norton, Rg=1e9). VIOLA's own current-source code is a non-functional stub (b=J → ~0 output); a `viola_faithful` flag reproduces it, but the default is the working Norton form.


## Bit-for-bit validation against VIOLA's own generated plug-in

Beyond the independent nodal oracle, each class was compared to VIOLA's ACTUAL
generated plug-in output (instantiated in MATLAB, see `../tests/matlab/`):

| Circuit | Class | SNR vs VIOLA |
|---|---|---|
| RC | `lin` | 302 dB |
| DEMO | `one_non_lin` | 220 dB |
| MXR | `one_non_lin_opamp` | 87.5 dB |
| DOD | `non_lin_opamp` (SIM/DSR) | 292.6 dB (machine) |

Two VIOLA-fidelity findings this surfaced:
- **Inverse-log pot taper.** VIOLA's netlist expansion (`handlePots`) and its
  plug-in runtime updater (`getUpFuncs`) use *different* inverse-log tapers that
  agree only at x=0 and x=1. The deployed plug-in uses the log-based form, so the
  port matches that (`netlist.py`). (lin/log tapers agree between the two.)
- **MXR residual (~5e-6).** Under hard antiparallel-diode clipping, the Wright-omega
  argument is sensitive to the diode's adapted port resistance Z_D. We compute Z_D
  by a physical nullor-MNA driving-point solve; VIOLA uses its U/K/H formula. Both
  are the same Thevenin resistance but differ ~1e-6, amplified through the
  nonlinearity. DOD hits machine precision because its diodes barely conduct here.
