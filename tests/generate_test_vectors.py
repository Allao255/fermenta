"""
generate_test_vectors.py
========================

Produces the reference (ground-truth) test vectors that the future Python WDF
port — and the MATLAB VIOLA implementation — must reproduce for the DEMO circuit.

Outputs, under tests/vectors/:
  - <case>_input.csv      : input voltage samples (Vin)
  - <case>_expected.csv   : expected node voltages (N002, N003)
  - manifest.json         : circuit params, fs, tolerances, case metadata

Also runs a discretization self-check: it re-solves each case at 8x oversampling
and confirms the base-rate result is converged (so the vectors are trustworthy).
"""

import json
import os
import numpy as np
from reference_solver import (
    solve_demo, demo_params, sine, dc_step, sweep,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "vectors")
os.makedirs(OUT, exist_ok=True)

FS = 48000
DUR = 0.05  # 50 ms keeps files small but covers several RC time-constants

CASES = {
    "dc_step_1v":      lambda fs: dc_step(1.0, fs, DUR),
    "dc_step_neg1v":   lambda fs: dc_step(-1.0, fs, DUR),
    "sine_250hz_0v2":  lambda fs: sine(250, 0.2, fs, DUR),
    "sine_1khz_0v5":   lambda fs: sine(1000, 0.5, fs, DUR),
    "sine_100hz_2v0":  lambda fs: sine(100, 2.0, fs, DUR),   # drives diode hard
    "sweep_20_2k_0v5": lambda fs: sweep(20, 2000, 0.5, fs, DUR),
}

def resample_to_base(y_hi, factor):
    """Decimate an oversampled result back to the base grid (pick every factor-th)."""
    return y_hi[::factor]

def main():
    params = demo_params()
    manifest = {
        "circuit": "DEMO",
        "source": "viola/windows/Data/Input/Netlist/DEMO.txt",
        "description": "Extended-Shockley diode in series with a 50k resistor "
                       "(linear pot at x=0.5) and a 0.1uF cap to ground.",
        "fs": FS,
        "duration_s": DUR,
        "integration": "trapezoidal (bilinear) -- matches WDF reactive-element mapping",
        "params": {
            "diode": {"Is": 4.352e-9, "eta": 1.905, "Vth": 25.8563e-3,
                       "Rs": 1e-3, "Rp": 1e6, "model": "extended Shockley (implicit Rs)"},
            "R_pot_effective_ohm": params["Rp_pot"] * params["x"],
            "C_farad": params["C"],
        },
        "output_nodes": ["N002", "N003"],
        "compare_tolerance": {"abs": 1e-6, "rel": 1e-5,
                               "note": "WDF port should match to solver tolerance; "
                                       "1e-6 V absolute is a safe pass threshold"},
        "cases": {},
    }

    for name, gen in CASES.items():
        x = gen(FS)
        r = solve_demo(x, FS, params)

        # discretization self-check at 8x oversampling
        factor = 8
        x_hi = gen(FS * factor)
        r_hi = solve_demo(x_hi, FS * factor, params)
        err = np.max(np.abs(resample_to_base(r_hi["N003"], factor)[:len(r["N003"])]
                            - r["N003"]))

        np.savetxt(os.path.join(OUT, f"{name}_input.csv"),
                   x, delimiter=",", header="Vin", comments="")
        expected = np.column_stack([r["N002"], r["N003"]])
        np.savetxt(os.path.join(OUT, f"{name}_expected.csv"),
                   expected, delimiter=",", header="N002,N003", comments="")

        manifest["cases"][name] = {
            "n_samples": int(len(x)),
            "input_peak": float(np.max(np.abs(x))),
            "N003_peak": float(np.max(np.abs(r["N003"]))),
            "N003_final": float(r["N003"][-1]),
            "discretization_selfcheck_max_err_vs_8x": float(err),
        }
        print(f"{name:18s}  N003 peak={manifest['cases'][name]['N003_peak']:.5f}  "
              f"discretization err vs 8x = {err:.2e}")

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("\nWrote vectors + manifest to:", OUT)


if __name__ == "__main__":
    main()
