#!/usr/bin/env python3
"""
validate_cpp.py -- compile the generated C++ engine with g++ and confirm it is
bit-identical to the Python engine across sample rate, pot positions, and the
SIM/DSR path.  Run from python/:  python tools/validate_cpp.py
"""
import os, sys, subprocess, tempfile
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../fermenta
sys.path.insert(0, os.path.join(ROOT, "python"))
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from fermenta.codegen import emit_cpp

NLD = f"{ROOT}/viola/windows/Data/Input/Netlist"
RC = open(f"{ROOT}/tests/matlab/rc_lowpass.txt").read()

MAIN = r'''#include "dsp.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
int main(int c,char**v){double fs=atof(v[1]);int n=atoi(v[2]);double a=atof(v[3]),f=atof(v[4]);double px=c>5?atof(v[5]):-1;
 fermenta::Dsp d; d.reset(); d.setSampleRate(fs); if(px>=0){for(int k=0;k<d.NPOTS;++k)d.setPot(k,px);}
 for(int i=0;i<n;i++){double in=a*std::sin(2*M_PI*f*i/fs); printf("%.17g\n",d.process(in));}}'''


def main():
    tmp = tempfile.mkdtemp(); open(f"{tmp}/main.cpp", "w").write(MAIN)
    n, amp, freq = 2000, 0.1, 440.0

    def run(wdf, fs, px=None, a=amp, f=freq):
        open(f"{tmp}/dsp.h", "w").write(emit_cpp(wdf, "Dsp"))
        subprocess.run(["g++", "-O2", "-o", f"{tmp}/run", f"{tmp}/main.cpp"], check=True)
        args = [f"{tmp}/run", str(fs), str(n), str(a), str(f)] + ([str(px)] if px is not None else [])
        r = subprocess.run(args, capture_output=True, text=True, check=True)
        ycpp = np.array([float(x) for x in r.stdout.split()])
        ypy = wdf.process(a * np.sin(2*np.pi*f*np.arange(n)/fs))
        return float(np.max(np.abs(ycpp - ypy)))

    ok = True
    print("sample-rate accuracy (C++ at fs  vs  Python at fs):")
    for label, txt, kw in [("RC (lin)", RC, dict(output_element_id="C1")),
                           ("DEMO (diode)", open(f"{NLD}/DEMO.txt").read(), dict(output_element_id="C1")),
                           ("MXR (opamp+diode)", open(f"{NLD}/MXR.txt").read(), dict(output_node="N010")),
                           ("SBGEQ (lin_opamp)", open(f"{NLD}/SBGEQ.txt").read(), dict(output_node="N001"))]:
        for fs in (48000, 44100, 96000):
            e = run(WDFCircuit(Netlist.parse(txt), fs, **kw), fs)
            ok &= e < 1e-10
            print(f"   {label:20s} fs={fs}: {e:.2e}")

    print("live circuit pots (C++ setPot(all,0.7)  vs  Python netlist x=0.7):")
    for label, path, kw, a, f in [("MXR", f"{NLD}/MXR.txt", dict(output_node="N010"), 0.1, 440.),
                                  ("DOD", f"{NLD}/DOD.txt", dict(output_node="N009"), 0.2, 250.)]:
        txt = open(path).read()
        wdf = WDFCircuit(Netlist.parse(txt), 48000, **kw)
        open(f"{tmp}/dsp.h", "w").write(emit_cpp(wdf, "Dsp"))
        subprocess.run(["g++", "-O2", "-o", f"{tmp}/run", f"{tmp}/main.cpp"], check=True)
        r = subprocess.run([f"{tmp}/run", "48000", str(n), str(a), str(f), "0.7"],
                           capture_output=True, text=True, check=True)
        ycpp = np.array([float(x) for x in r.stdout.split()])
        wp = WDFCircuit(Netlist.parse(txt.replace("x=0.5", "x=0.7")), 48000, **kw)
        ypy = wp.process(a * np.sin(2*np.pi*f*np.arange(n)/48000))
        e = float(np.max(np.abs(ycpp - ypy))); ok &= e < 1e-9
        print(f"   {label:20s}         : {e:.2e}")

    print("SIM/DSR multi-nonlinearity (DOD):")
    e = run(WDFCircuit(Netlist.parse(open(f"{NLD}/DOD.txt").read()), 48000, output_node="N009"),
            48000, a=0.2, f=250.)
    ok &= e < 1e-9
    print(f"   DOD                          : {e:.2e}")

    print("ALL BIT-IDENTICAL" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
