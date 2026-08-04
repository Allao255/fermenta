"""
reference_solver.py
====================

Independent ground-truth solver for the DEMO circuit used by VIOLA.

This is NOT a Wave Digital Filter. It is a classic nodal (MNA-style) solver
with the trapezoidal rule for the capacitor and an inner Newton loop for the
extended Shockley diode. It exists to produce *method-independent* reference
signals that BOTH the MATLAB VIOLA implementation and the future Python WDF
port must reproduce.

Why trapezoidal integration?
----------------------------
WDF models a reactive element with the bilinear (Tustin) transform, which is
mathematically identical to trapezoidal integration of the branch ODE. A nodal
solver using the trapezoidal rule therefore solves *exactly the same discretized
circuit equations* that a correct WDF solves, just arranged in node voltages
instead of wave variables. Solved to a tight tolerance, the two must agree to
within solver tolerance. That makes this an honest, independent oracle.

DEMO circuit (from viola/windows/Data/Input/Netlist/DEMO.txt)
------------------------------------------------------------
    Vin --[ diode D1 ]-- N002 --[ R = Rp*x ]-- N003 --[ C ]-- gnd

    Vin        : ideal voltage source, N001 -> gnd
    D1         : extended Shockley diode, branch N002 <-> N001
                 Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg
    Plin1      : linear potentiometer wired as a variable resistor,
                 R_eff = Rp*x = 100k * 0.5 = 50k, between N002 and N003
    C1         : 0.1uF, N003 -> gnd

Nodes: N001 (= Vin, known), N002 (v2), N003 (v3), gnd (0).
Unknowns solved each step: v2, v3.
"""

import numpy as np


# ----------------------------------------------------------------------------
# Extended Shockley diode branch  (matches VIOLA's LTspice subckt)
#   I = Is*(exp((Vd - Rs*I)/(eta*Vth)) - 1) + (Vd - Rs*I)/Rp      (implicit in I)
# Returns branch current I (node1->node2) and small-signal conductance g=dI/dVd.
# ----------------------------------------------------------------------------
def diode_branch(Vd, p, I0=0.0, tol=1e-14, itmax=80):
    Is, eta, Vth, Rs, Rp = p["Is"], p["eta"], p["Vth"], p["Rs"], p["Rp"]
    vt = eta * Vth
    I = I0
    for _ in range(itmax):
        u = (Vd - Rs * I) / vt
        # guard the exponential against overflow
        u = min(u, 200.0)
        e = np.exp(u)
        # G(I) = I - Is*(e - 1) - (Vd - Rs*I)/Rp
        G = I - Is * (e - 1.0) - (Vd - Rs * I) / Rp
        # dG/dI = 1 + Is*Rs/vt*e + Rs/Rp
        dG = 1.0 + Is * Rs / vt * e + Rs / Rp
        step = G / dG
        I -= step
        if abs(step) < tol * (abs(I) + tol):
            break
    # small-signal conductance g = dI/dVd via implicit differentiation:
    #   0 = dI - Is/vt*e*(dVd - Rs*dI) - (dVd - Rs*dI)/Rp
    u = min((Vd - Rs * I) / vt, 200.0)
    e = np.exp(u)
    a = Is / vt * e + 1.0 / Rp          # d(.)/d(Vd - Rs I)
    g = a / (1.0 + a * Rs)              # dI/dVd
    return I, g


def demo_params():
    return {
        "Is": 4.352e-9, "eta": 1.905, "Vth": 25.8563e-3, "Rs": 1e-3, "Rp": 1e6,
        "Rp_pot": 100e3, "x": 0.5, "C": 0.1e-6,
    }


def solve_demo(vin, fs, params=None, out_node="N003", newton_tol=1e-12, itmax=100):
    """Process input signal `vin` (numpy array) at sample rate `fs`.

    Returns dict with node-voltage arrays for N002 and N003.
    """
    if params is None:
        params = demo_params()
    R = params["Rp_pot"] * params["x"]          # 50k
    C = params["C"]
    dp = {k: params[k] for k in ("Is", "eta", "Vth", "Rs", "Rp")}
    T = 1.0 / fs
    Geq = 2.0 * C / T                           # trapezoidal companion conductance

    N = len(vin)
    v2 = np.zeros(N)
    v3 = np.zeros(N)

    v2n, v3n = 0.0, 0.0        # node voltages at previous step
    iC = 0.0                    # capacitor current at previous step
    Id = 0.0                    # diode current warm-start

    for n in range(N):
        v1 = float(vin[n])
        Ieq = -Geq * v3n - iC                    # trapezoidal companion source

        # Newton on (v2, v3)
        a, b = v2n, v3n                          # warm start from previous sample
        for _ in range(itmax):
            Id, gd = diode_branch(a - v1, dp, I0=Id)
            F1 = Id + (a - b) / R
            F2 = (b - a) / R + Geq * b + Ieq
            # Jacobian
            J11 = gd + 1.0 / R
            J12 = -1.0 / R
            J21 = -1.0 / R
            J22 = 1.0 / R + Geq
            det = J11 * J22 - J12 * J21
            da = (F1 * J22 - F2 * J12) / det
            db = (J11 * F2 - J21 * F1) / det
            a -= da
            b -= db
            if abs(da) + abs(db) < newton_tol:
                break

        v2[n], v3[n] = a, b
        iC = Geq * b + Ieq                       # update cap current for next step
        v2n, v3n = a, b

    return {"N002": v2, "N003": v3}


# ----------------------------------------------------------------------------
# Test-signal generators
# ----------------------------------------------------------------------------
def sine(freq, amp, fs, dur):
    t = np.arange(int(fs * dur)) / fs
    return amp * np.sin(2 * np.pi * freq * t)


def dc_step(amp, fs, dur):
    x = np.full(int(fs * dur), amp)
    x[0] = 0.0
    return x


def sweep(f0, f1, amp, fs, dur):
    t = np.arange(int(fs * dur)) / fs
    return amp * np.sin(2 * np.pi * (f0 * t + (f1 - f0) / (2 * dur) * t ** 2))


if __name__ == "__main__":
    fs = 48000
    p = demo_params()
    # quick sanity: DC operating point should be bounded and follow input sign
    x = dc_step(1.0, fs, 0.02)
    r = solve_demo(x, fs, p)
    print("DC step -> N003 final:", r["N003"][-1], "V (expect ~1V, cap charges up)")
    x = sine(250, 0.2, fs, 0.02)
    r = solve_demo(x, fs, p)
    print("Sine 250Hz 0.2V -> N003 peak:", np.max(np.abs(r["N003"])))
