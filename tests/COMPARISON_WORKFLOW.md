# VIOLA ↔ Python compatibility workflow

Calibrating the from-scratch Python engine against VIOLA, starting linear.

## Files
- `matlab/rc_lowpass.txt`     — linear RC test circuit (VIOLA-compatible netlist)
- `matlab/viola_export.m`     — runs VIOLA's exact numeric pipeline, exports signals + matrices
- `compare_viola_python.py`   — runs the Python engine on the same input, computes metrics

## Steps

1. **Dry run (no MATLAB yet)** — confirms the Python engine + metrics work:
   ```bash
   python3 compare_viola_python.py --selftest
   ```
   Expect machine-precision agreement (SNR ~300 dB) vs an independent nodal solver.

2. **Generate VIOLA output** (MATLAB):
   - Copy `matlab/rc_lowpass.txt` → `viola/windows/Data/Input/Netlist/`
   - Copy `matlab/viola_export.m` → `viola/windows/` and run it there.
   - It writes `viola/windows/Data/Output/Compare/` (input_*.csv, viola_*.csv, Q/B/Z/S/…).

3. **Compare**:
   ```bash
   python3 compare_viola_python.py --export-dir /path/to/viola/windows/Data/Output/Compare
   ```

## Metrics & expectations

| metric | meaning | linear target |
|---|---|---|
| `max_abs` | worst pointwise error | < 1e-9 (machine precision) |
| `ESR` | Σ(err²)/Σ(ref²), the VA-standard | < 1e-20 |
| `SNR (dB)` | 10·log10(ref²/err²) | > 250 dB |
| `spec_err` | FFT-magnitude error | ~1e-15 |
| `lag` | integer sample offset (xcorr) | 0 |

Why machine precision is expected: the Python engine now uses **VIOLA's exact
source model** (Vin = matched resistive source, Rp = 1e-9), **VIOLA's exact
reactance mapping** (bilinear: C→T/(2C), L→2L/T) and **VIOLA's exact scattering
formula** (`customizePlugin.m/setMatrices`). The only remaining variable is the
spanning-tree choice, and the *output signal is tree-invariant*.

## If results diverge
- Non-zero `lag` → a one-sample delay convention mismatch in the reactance state.
- `spec_err` tiny but `max_abs` large → phase/latency only, not a real difference.
- Constant scale factor → check `Volume` (should be 1) and the `outPath` sign.
- Small offset that scales with signal → source reference resistance mismatch.

## Next circuits
`rc_lowpass` (done) → linear + potentiometer → DEMO (adds the diode; requires the
nonlinear-root build) → MXR (opamp + antiparallel diodes).

## DEMO (um diodo) — não linear

O diodo já está implementado em Python (Wright-omega, idêntico à VIOLA) e valida
contra o solver nodal-Newton independente em ~1e-10.

1. Copie `matlab/viola_export_nl.m` para `viola/windows/` e rode:
   ```matlab
   viola_export_nl
   ```
   Exporta para `viola/windows/Data/Output/Compare_DEMO/`.
2. Compare:
   ```bash
   python3 compare_viola_python.py \
     --export-dir ../viola/windows/Data/Output/Compare_DEMO \
     --netlist ../viola/windows/Data/Input/Netlist/DEMO.txt --out-id C1
   ```
   Esperado: precisão de máquina (mesma função omega dos dois lados).

## Op-amp / multi-diode circuits (MXR, DOD) — via VIOLA's generated plug-in

The transcription harnesses above don't cover op-amps. For MXR/DOD we run
VIOLA's OWN generated plug-in code (`matlab/viola_run_plugin.m`), which
instantiates the class `customizePlugin` emits and processes a signal — no
re-transcription, so the numerics are guaranteed VIOLA-exact.

**MXR** (`one_non_lin_opamp`):
1. Copy `matlab/viola_run_plugin.m` into `viola/windows/` and run it
   (it is configured for MXR: `netlist='MXR'`, `outNode='N010'`, `code='MXRtest'`).
2. Compare:
   ```bash
   python3 compare_viola_python.py \
     --export-dir ../viola/windows/Data/Output/Compare_MXR \
     --netlist ../viola/windows/Data/Input/Netlist/MXR.txt --out-node N010
   ```

**DOD** (`non_lin_opamp`): edit the top of `viola_run_plugin.m` to
`netlist='DOD'; outNode='N009'; code='DODtest';`, run, then compare with
`--export-dir ...Compare_DOD --netlist ...DOD.txt --out-node N009`.

Notes:
- If you re-run with the same `code`, MATLAB may cache the old class — run
  `clear classes` first.
- If plug-in instantiation errors on a GUI asset, tell me the message; we can
  strip the GUI bits from the harness.

Expected: near machine-precision (Python uses the same Wright-omega, the same
bilinear discretization, the same exact pot tapers, and the output is
tree-invariant; SIM tolerances match VIOLA's defaults tol_slv=1e-5, tol_dsr=1000).
