# fermenta → C++ / VST

Generate a self-contained C++ Wave Digital Filter DSP from any netlist, and
optionally wrap it as a VST3 plug-in with JUCE. The generated DSP is
**bit-identical** to the Python engine (validated by `tools/validate_cpp.py`,
g++ vs Python ≈ 1e-15).

## 1. Generate the DSP header from a netlist

```bash
cd ../python
python tools/gen_cpp.py <netlist>.txt --out-node N010 --name MxrDsp \
       --pot-labels "Gain,Level" -o ../cpp/MxrDsp.h
#   non-op-amp circuits: use --out-id <elementId> instead of --out-node
```

This writes `MxrDsp.h` defining `struct MxrDsp` in namespace `fermenta`:

```cpp
fermenta::MxrDsp d;         // construct (defaults: 48 kHz, pots at netlist positions)
d.setSampleRate(hostFs);   // sample-rate-accurate: rebuilds S for the host rate
d.setPot(0, 0.8);          // live circuit knob (Gain/Level), 0..1 ; rebuilds S
d.reset();                 // clear state
double y = d.process(x);   // one sample in -> one sample out
// d.NPOTS = number of live circuit knobs for this circuit
```

No dependencies (just `<cmath>`), so it drops into any audio project.

## 2. Build the VST3 (JUCE)

Requirements: CMake ≥ 3.22 and a C++17 compiler. JUCE is fetched automatically.

```bash
cd cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

The plug-in matches VIOLA's control scheme: a **Volume** knob (output gain,
linear 0..2, default 1), the **circuit potentiometers** labelled exactly like
VIOLA ("Gain (P1)", "Level (P2)", ... from `--pot-labels`), and an **Enable**
ON/OFF switch (bypass). No extra utility knobs. `--pot-labels` are matched to
pots by their number (P1, P2, ...) just like VIOLA.

The VST3 lands in `build/WdfViolaMXR_artefacts/Release/VST3/` (also a Standalone
app). The plug-in exposes **Input Drive** and **Output Volume** knobs; the
circuit is the MXR Distortion+ at its default pot positions.


## 3. Quick audio test WITHOUT a DAW (WAV → WAV)

`wdf_render.cpp` runs a WAV file through the generated DSP — no JUCE, no DAW.

```bash
g++ -O2 -o wdf_render wdf_render.cpp          # one command, no dependencies
./wdf_render in.wav out.wav [driveDB] [volumeDB]
# e.g.  ./wdf_render guitar.wav mxr.wav 12 -6
```
(16-bit PCM WAV, mono or stereo). On Windows with MSVC: `cl /O2 /EHsc wdf_render.cpp`.
Change the `#include` and `DspType` at the top to use a different generated circuit.

## Runtime features (all validated bit-identical to Python)

- **Sample-rate accurate.** `setSampleRate(fs)` rebuilds the port resistances and
  scattering matrix for any host rate (validated at 44.1 / 48 / 96 kHz).
- **Live circuit knobs.** `setPot(k, x)` (x in 0..1) retunes the potentiometer
  and rebuilds S; the JUCE plug-in exposes them as "Circuit Knob k".
- **Every circuit class**, including multiple-nonlinearity SIM/DSR circuits
  (e.g. DOD) — the engine runs the iterative solver internally.

`python tools/validate_cpp.py` compiles the generated engine with g++ and checks
all of the above against the Python reference (≈ 1e-15).

Note: `setSampleRate` / `setPot` rebuild S (a small matrix solve), so call them
on parameter changes / prepareToPlay — not per audio sample. `process()` itself
is cheap (one scatter, or a few SIM iterations).
