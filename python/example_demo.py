"""Minimal end-to-end example: run the DEMO circuit through the WDF engine.

    python example_demo.py [path/to/DEMO.txt]
"""
import os
import sys

import numpy as np

from fermenta import Netlist, WDFCircuit

DEFAULT = os.path.join(os.path.dirname(__file__), "..", "examples", "viola",
                       "DEMO.txt")


def main(path=DEFAULT, fs=48000, freq=440.0, amp=0.5, dur=0.02):
    nl = Netlist.parse(open(path).read())
    wdf = WDFCircuit(nl, fs, output_element_id="C1")

    t = np.arange(int(fs * dur)) / fs
    x = amp * np.sin(2 * np.pi * freq * t)
    y = wdf.process(x)

    print(f"netlist   : {os.path.basename(path)}")
    print(f"elements  : {len(nl.elements)}   input: {nl.input_id}")
    print(f"in  peak  : {np.max(np.abs(x)):.4f} V")
    print(f"out peak  : {np.max(np.abs(y)):.4f} V")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
