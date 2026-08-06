# Fermenta

**From an LTspice circuit to a guitar-pedal plugin (VST3), via Wave Digital
Filters.** Fermenta is an open-source Python port of the method behind
[VIOLA](https://github.com/polimi-ispl/viola), plus its own C++/JUCE code
generator, graphical front-end and comparison tools — so no MATLAB or paid
toolboxes are needed to build a pedal.

Draw the circuit in LTspice, export the SPICE netlist, load it in the app, pick
the output node, name the knobs, and build the plugin.

---

## What it does

Given an LTspice netlist, Fermenta:

1. parses it and builds the circuit graph;
2. forms the fundamental cutset matrix `Q`, loop matrix `B` and the R-type
   scattering matrix `S` — one junction for the whole circuit, from topology;
3. runs the per-sample wave loop (linear networks, diodes in closed form via the
   Wright omega function, ideal op-amps as nullors, and multiple nonlinearities
   through the SIM/DSR iteration);
4. emits a self-contained C++ DSP engine;
5. wraps it in JUCE and compiles a VST3.

### Supported circuit classes

| Class | Example | Method |
|---|---|---|
| `lin` | RC network | R-type scattering |
| `one_non_lin` | diode clipper | Wright omega, closed form |
| `lin_opamp` | graphic EQ | nullor (dual graph) |
| `one_non_lin_opamp` | Tube Screamer, MXR Distortion+ | nullor + diode |
| `non_lin[_opamp]` | DOD 250 | SIM/DSR iteration |

Components: resistors, capacitors, inductors, voltage/current sources,
extended-Shockley diodes (single, series, antiparallel), linear/log/inverse-log
potentiometers and ideal op-amps. Transistors are not modelled.

---

## Getting started (Windows, from scratch)

1. Download or clone this repository.
2. Right-click `setup_windows.bat` → **Run as administrator**. It installs Git,
   Python, CMake and the Visual Studio 2022 Build Tools through `winget`.
3. Close the window, then double-click `abrir_app.bat` — it installs the Python
   dependencies and opens the application.

In the app: **Load** the netlist → **Analyze** → choose the output node → set a
name and the knob labels → **Export & Build VST3**. The plugin appears under
`<folder>\build\<Name>_artefacts\Release\VST3\`.

### From the command line

```bash
cd python
pip install -e ".[gui]"
pytest                       # test suite

python -m fermenta.gui       # main application
python -m fermenta.compare   # compare two pedals (time, spectrum, metrics)
```

Building a VST3 needs CMake and a C++ compiler; JUCE is fetched automatically on
the first build.

---

## Drawing the circuit

Copy the symbols in `ltspice_components/` next to your `.asc` file, then follow
VIOLA's schematic conventions: exactly one input source named `Vin`, ground as
node `0`, unique component IDs, unedited node labels (`N001`, `N002`, …), and
custom parts named `OA1`, `D1`, `Dser1`, `Dap1`, `Plin1`/`Plog1`/`Pilog1` —
potentiometers numbered in sequence, since that order is the knob order.

Export with **View → SPICE Netlist** (not *Tools → Export Netlist*, which writes
a PCB netlist).

Since the op-amp is ideal, supply rails are not modelled: wherever a schematic
shows a mid-rail bias (for instance +4.5 V), connect to node `0`.

Full walkthroughs, including the MATLAB/VIOLA route, are in `docs/`.

---

## Validation

Fermenta is a port, so the reference is VIOLA itself. Three independent checks:

- **Against an MNA oracle.** Every circuit class is compared to an independent
  nodal solver (Newton for diodes, nullor stamps for op-amps): `pytest`, 19
  tests.
- **Against VIOLA's own generated plugins.** RC 302 dB, DEMO 220 dB, DOD at
  machine precision, and a Tube Screamer clipping stage at ~287 dB SNR.
- **Randomised cross-check.** `tools/fuzz_vs_viola.py` generates random circuits
  (all classes, diodes anywhere in the topology, multiple op-amps, inductors,
  potentiometers) and compares the engine with `tools/viola_reference.py`, a
  second implementation transcribed from the MATLAB sources that computes the
  scattering matrix by a different route. No structural divergence in 320
  circuits.

The generated C++ matches the Python engine bit-for-bit on linear circuits and
within numerical noise on the ill-conditioned nonlinear ones
(`tools/validate_cpp.py`).

One design decision worth stating: VIOLA computes the diode's adapted port
resistance through a nullor-MNA reduction whose indexing departs from the
physical Thévenin resistance when the diode sits inside an op-amp feedback loop.
Fermenta reproduces VIOLA's formulation deliberately, so that plugins match the
ones VIOLA generates. See `docs/PROJECT_OVERVIEW.md`, section 7.

---

## Repository layout

```
python/       library (fermenta/), CLI and validation tools, test suite
cpp/          C++/JUCE plugin templates
examples/     example netlists
ltspice_components/   LTspice symbols for drawing circuits
viola_integration/    files to drop into a VIOLA clone (MATLAB route)
docs/         guides, project overview, theory notes
```

---

## Credits and licence

Fermenta reimplements the method published in:

> R. Giampiccolo, S. Ravasi and A. Bernardini, *"VIOLA: A Framework for the
> Automatic Generation of Virtual Analog Audio Plug-ins based on WDFs"*, Journal
> of the Audio Engineering Society, special issue "The Sound of Digital Audio
> Effects".

All credit for the method belongs to its authors. The LTspice symbol library in
`ltspice_components/` comes from the VIOLA repository and is redistributed here
under the GPL-3.0; the MATLAB framework itself is not redistributed. See
`CREDITS.md`.

Licensed under **GPL-3.0**, matching VIOLA.

### Development note

This project was developed with the assistance of a large language model
(Anthropic's Claude), used for code implementation, porting the MATLAB
algorithms, and building the validation tooling. All results reported here are
reproducible with the scripts in `python/tools/`, and the engine is checked
against VIOLA's own generated plugins and an independent implementation.
