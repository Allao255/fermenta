#!/usr/bin/env python3
"""
gen_cpp.py -- generate a self-contained C++ WDF DSP header from a netlist.

Usage:
  python tools/gen_cpp.py NETLIST.txt --out-id C1            -o Dsp.h --name Dsp
  python tools/gen_cpp.py MXR.txt     --out-node N010 --fs 48000 -o MxrDsp.h --name MxrDsp

The emitted header defines `struct <name>` in namespace `fermenta` with
`reset()` and `double process(double in)`. It is bit-identical to
fermenta.WDFCircuit.process at the chosen sample rate.
"""
import argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from fermenta.codegen import emit_cpp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--out-id", default=None, help="output element id (non-op-amp circuits)")
    ap.add_argument("--out-node", default=None, help="output node Nxxx (op-amp circuits)")
    ap.add_argument("--fs", type=int, default=48000)
    ap.add_argument("--name", default="Dsp")
    ap.add_argument("--pot-labels", default=None, help="comma-separated pot labels, e.g. \"Gain,Level\"")
    ap.add_argument("-o", "--output", default=None)
    a = ap.parse_args()
    nl = Netlist.parse(open(a.netlist).read())
    wdf = WDFCircuit(nl, a.fs, output_element_id=a.out_id, output_node=a.out_node)
    labels = a.pot_labels.split(',') if a.pot_labels else None
    code = emit_cpp(wdf, a.name, pot_labels=labels)
    out = a.output or (a.name + ".h")
    open(out, "w").write(code)
    print(f"wrote {out}  ({len(wdf.ports)} ports, fs={a.fs}, name={a.name})")


if __name__ == "__main__":
    main()
