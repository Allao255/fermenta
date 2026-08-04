"""
validate_linear_engine.py
=========================

Proves the wdfviola scattering engine (topology -> Q/B -> R-type S -> per-sample
scatter) is numerically correct on a LINEAR circuit, by comparing it to an
independent nodal solver with the same trapezoidal capacitor discretization.

Test circuit = DEMO with the diode replaced by a plain series resistor Rd:
    Vin --[ Rd ]-- N002 --[ R=50k ]-- N003 --[ C=0.1uF ]-- gnd,  output = V(N003)

If the WDF engine and the nodal solver agree to ~1e-9, the linear core is correct
and only the nonlinear root (diode) remains for the build-later phase.
"""

import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from wdfviola.netlist import Netlist            # noqa: E402
from wdfviola.solver import WDFCircuit          # noqa: E402

FS = 48000
RD = 100.0        # series resistor replacing the diode
RPOT = 50e3
C = 0.1e-6

LINEAR_NETLIST = f"""
* linear DEMO (diode -> resistor) for engine validation
Vin N001 0
Rd N002 N001 {RD}
Rpot N002 N003 {RPOT}
C1 N003 0 {C}
.end
"""


def nodal_reference(vin, fs):
    T = 1.0 / fs
    Geq = 2.0 * C / T
    v2n = v3n = iC = 0.0
    out = np.zeros(len(vin))
    for n, v1 in enumerate(vin):
        Ieq = -Geq * v3n - iC
        # KCL:  [ 1/Rd+1/Rpot , -1/Rpot ] [v2]   [ v1/Rd ]
        #       [ -1/Rpot     , 1/Rpot+Geq][v3] = [ -Ieq  ]
        A = np.array([[1/RD + 1/RPOT, -1/RPOT],
                      [-1/RPOT,       1/RPOT + Geq]])
        rhs = np.array([v1 / RD, -Ieq])
        v2, v3 = np.linalg.solve(A, rhs)
        iC = Geq * v3 + Ieq
        v2n, v3n = v2, v3
        out[n] = v3
    return out


def main():
    nl = Netlist.parse(LINEAR_NETLIST)
    wdf = WDFCircuit(nl, FS, output_element_id="C1")

    # algebraic checks on the junction
    print("junction KVL residual :", wdf.junction.kvl_residual())
    print("junction KCL residual :", wdf.junction.kcl_residual())

    t = np.arange(int(FS * 0.05)) / FS
    for name, x in {
        "sine_1k":  0.5 * np.sin(2 * np.pi * 1000 * t),
        "step":     np.where(t > 0, 1.0, 0.0),
        "sweep":    0.5 * np.sin(2 * np.pi * (20 * t + (2000 - 20) / (2 * 0.05) * t**2)),
    }.items():
        y_wdf = wdf.process(x)
        y_ref = nodal_reference(x, FS)
        err = np.max(np.abs(y_wdf - y_ref))
        status = "OK" if err < 1e-9 else "FAIL"
        print(f"  {name:8s} max|WDF - nodal| = {err:.3e}   [{status}]")


if __name__ == "__main__":
    main()
