"""
compare_viola_python.py
=======================

Compares the wdfviola Python engine against VIOLA's exported output, computing a
full suite of compatibility metrics.

Usage
-----
  # after running tests/matlab/viola_export.m and copying its Compare/ folder here:
  python3 compare_viola_python.py --export-dir /path/to/Compare

  # dry run without MATLAB (uses an independent nodal solver as a stand-in ref):
  python3 compare_viola_python.py --selftest

Metrics (per signal)
--------------------
  max_abs   : max |y_py - y_ref|                         (strict pointwise)
  rmse      : sqrt(mean((y_py - y_ref)^2))
  nrmse     : rmse / rms(y_ref)
  esr       : sum((y_py-y_ref)^2)/sum(y_ref^2)           (virtual-analog standard)
  snr_db    : 10*log10(sum(y_ref^2)/sum((y_py-y_ref)^2))
  spec_err  : || |FFT(y_py)| - |FFT(y_ref)| || / || |FFT(y_ref)| ||
  lag       : integer sample offset (cross-correlation argmax)
  max_abs_aligned : max_abs after removing that lag
"""

import argparse
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
from wdfviola.netlist import Netlist          # noqa: E402
from wdfviola.solver import WDFCircuit         # noqa: E402

RC_NETLIST = os.path.join(HERE, "matlab", "rc_lowpass.txt")
FS_DEFAULT = 48000


# ------------------------------------------------------------------ metrics
def metrics(y_py, y_ref):
    y_py = np.asarray(y_py, float)
    y_ref = np.asarray(y_ref, float)
    m = min(len(y_py), len(y_ref))
    y_py, y_ref = y_py[:m], y_ref[:m]
    err = y_py - y_ref
    ref_energy = float(np.sum(y_ref ** 2)) or 1e-300

    # spectral magnitude error
    Yp, Yr = np.abs(np.fft.rfft(y_py)), np.abs(np.fft.rfft(y_ref))
    spec_err = float(np.linalg.norm(Yp - Yr) / (np.linalg.norm(Yr) or 1e-300))

    # integer lag via cross-correlation
    xc = np.correlate(y_py - y_py.mean(), y_ref - y_ref.mean(), mode="full")
    lag = int(np.argmax(xc) - (m - 1))
    if lag == 0:
        aligned = err
    elif lag > 0:
        aligned = y_py[lag:] - y_ref[:m - lag]
    else:
        aligned = y_py[:m + lag] - y_ref[-lag:]

    return {
        "max_abs": float(np.max(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "nrmse": float(np.sqrt(np.mean(err ** 2)) / (np.sqrt(np.mean(y_ref ** 2)) or 1e-300)),
        "esr": float(np.sum(err ** 2) / ref_energy),
        "snr_db": float(10 * np.log10(ref_energy / (float(np.sum(err ** 2)) or 1e-300))),
        "spec_err": spec_err,
        "lag": lag,
        "max_abs_aligned": float(np.max(np.abs(aligned))) if len(aligned) else float("nan"),
    }


def report(name, y_py, y_ref):
    r = metrics(y_py, y_ref)
    verdict = "MACHINE-PRECISION" if r["max_abs"] < 1e-9 else \
              ("CLOSE" if r["esr"] < 1e-6 else "DIVERGENT")
    print(f"\n[{name}]  n={min(len(y_py),len(y_ref))}   -> {verdict}")
    print(f"    max_abs = {r['max_abs']:.3e}   rmse = {r['rmse']:.3e}   "
          f"nrmse = {r['nrmse']:.3e}")
    print(f"    ESR     = {r['esr']:.3e}   SNR = {r['snr_db']:.1f} dB   "
          f"spec_err = {r['spec_err']:.3e}")
    print(f"    lag     = {r['lag']} samples   max_abs(aligned) = {r['max_abs_aligned']:.3e}")
    return r


# ------------------------------------------------------------------ python run
def run_python(input_signal, fs, netlist_path=RC_NETLIST, out_id="C1", out_node=None):
    nl = Netlist.parse(open(netlist_path).read())
    if out_node:
        wdf = WDFCircuit(nl, fs, output_node=out_node)
    else:
        wdf = WDFCircuit(nl, fs, output_element_id=out_id)
    return wdf.process(input_signal)


# ------------------------------------------------------------------ nodal ref (selftest)
def nodal_rc(vin, fs, R=1000.0, C=100e-9, Rvin=1e-9):
    """Independent trapezoidal nodal solver for the rc_lowpass circuit, with the
    same 1e-9 source resistance VIOLA uses -- a stand-in for VIOLA's output."""
    T = 1.0 / fs
    Geq = 2.0 * C / T
    v2n = iC = 0.0
    out = np.zeros(len(vin))
    for n, e in enumerate(vin):
        Ieq = -Geq * v2n - iC
        # node N001 eliminated: V(N001)=e - Rvin*i ; series Rvin+R to N002=v2
        Rs = Rvin + R
        # KCL at N002: (v2 - e)/Rs + Geq v2 + Ieq = 0
        v2 = (e / Rs - Ieq) / (1.0 / Rs + Geq)
        iC = Geq * v2 + Ieq
        v2n = v2
        out[n] = v2
    return out


# ------------------------------------------------------------------ main
def load_csv(path):
    return np.loadtxt(path, delimiter=",", ndmin=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-dir", help="folder with input_*.csv / viola_*.csv from viola_export.m")
    ap.add_argument("--selftest", action="store_true", help="run without MATLAB using a nodal stand-in")
    ap.add_argument("--netlist", default=RC_NETLIST, help="netlist the Python engine should run")
    ap.add_argument("--out-id", default="C1", help="output element id to probe")
    ap.add_argument("--out-node", default=None, help="output node (op-amp circuits)")
    ap.add_argument("--fs", type=int, default=FS_DEFAULT)
    args = ap.parse_args()

    if args.selftest or not args.export_dir:
        print("=== SELF-TEST (no MATLAB): Python engine vs independent nodal solver ===")
        fs = args.fs
        t = np.arange(int(fs * 0.05)) / fs
        cases = {
            "sine_1k": 0.8 * np.sin(2 * np.pi * 1000 * t),
            "step": np.where(t > 0, 1.0, 0.0),
            "sweep_20_2k": 0.5 * np.sin(2 * np.pi * (20 * t + (2000 - 20) / (2 * 0.05) * t ** 2)),
        }
        for name, x in cases.items():
            y_py = run_python(x, fs)
            y_ref = nodal_rc(x, fs)
            report(name, y_py, y_ref)
        print("\n(For the real test, run viola_export.m and pass --export-dir.)")
        return

    d = args.export_dir
    fs = int(load_csv(os.path.join(d, "fs.csv"))) if os.path.exists(os.path.join(d, "fs.csv")) else args.fs
    cases = sorted(f[len("input_"):-4] for f in os.listdir(d)
                   if f.startswith("input_") and f.endswith(".csv"))
    if not cases:
        print("No input_*.csv found in", d); return
    print(f"=== VIOLA vs Python  (fs={fs}, {len(cases)} signals) ===")
    for name in cases:
        x = load_csv(os.path.join(d, f"input_{name}.csv"))
        y_ref = load_csv(os.path.join(d, f"viola_{name}.csv"))
        y_py = run_python(x, fs, args.netlist, args.out_id, args.out_node)
        report(f"{name}: full Python pipeline vs VIOLA", y_py, y_ref)


if __name__ == "__main__":
    main()
