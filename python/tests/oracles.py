"""
oracles.py -- independent reference solvers used as ground truth in the tests.

These deliberately DO NOT use any Wave Digital Filter code. `nodal_mna` is a
classic modified-nodal-analysis transient solver (trapezoidal integration for
C/L, Newton for diodes, nullor stamps for ideal op-amps). Because WDF models a
reactance with the bilinear transform -- identical to trapezoidal integration --
a correct WDF must reproduce this solver's node voltages: to machine precision
for linear/op-amp circuits, and to the Wright-omega approximation accuracy
(~1e-5..1e-6) for diode nonlinearities.
"""
import numpy as np
from fermenta.netlist import Netlist

_Vth = 25.8563e-3   # not used directly; params carry their own Vth


def _diode_ig(kind, V, p, I0):
    Is, eta, Vth, Rs, Rp = p["Is"], p["eta"], p["Vth"], p["Rs"], p["Rp"]
    vt = eta * Vth
    I = I0
    for _ in range(100):
        u = np.clip((V - Rs * I) / vt, -200, 200)
        if kind == "Dap":
            G = I - 2 * Is * np.sinh(u) - (V - Rs * I) / Rp
            dG = 1 + 2 * Is * Rs / vt * np.cosh(u) + Rs / Rp
        else:
            G = I - Is * (np.exp(u) - 1) - (V - Rs * I) / Rp
            dG = 1 + Is * Rs / vt * np.exp(u) + Rs / Rp
        I -= G / dG
        if abs(G) < 1e-16:
            break
    c = (2 * Is * np.cosh(u) / vt if kind == "Dap" else Is * np.exp(u) / vt) + 1 / Rp
    return I, c / (1 + c * Rs)


def nodal_mna(netlist_or_text, fs, drive, out_node):
    """Transient MNA solve. `drive` is the input (Vin voltage or Iin current)
    sample array. Returns the voltage at `out_node` per sample."""
    nl = (netlist_or_text if isinstance(netlist_or_text, Netlist)
          else Netlist.parse(netlist_or_text))
    els = nl.elements
    nodes = sorted({n for e in els for n in e.nodes[:3] if n != "0"})
    idx = {n: i for i, n in enumerate(nodes)}
    nN = len(nodes)
    vs = [e for e in els if e.type == "V"]
    isrc = [e for e in els if e.type == "I"]
    oas = [e for e in els if e.type == "OA"]
    dio = [e for e in els if e.type in ("D", "Dser", "Dap")]
    caps = [e for e in els if e.type == "C"]
    inds = [e for e in els if e.type == "L"]
    dim = nN + len(vs) + len(oas)
    T = 1.0 / fs
    cst = {e.id: 0.0 for e in caps}; cist = {e.id: 0.0 for e in caps}
    lip = {e.id: 0.0 for e in inds}; lvp = {e.id: 0.0 for e in inds}
    Id = {e.id: 0.0 for e in dio}
    out = np.zeros(len(drive)); oid = idx[out_node]; x = np.zeros(dim)

    def stamp(A, a, b, g):
        for n1, n2, sg in [(a, a, g), (b, b, g), (a, b, -g), (b, a, -g)]:
            if n1 != "0" and n2 != "0":
                A[idx[n1], idx[n2]] += sg

    for step, d in enumerate(drive):
        for _ in range(120):                       # Newton (linear -> 1 iter)
            A = np.zeros((dim, dim)); z = np.zeros(dim)
            for e in els:
                if e.type == "R":
                    stamp(A, e.nodes[0], e.nodes[1], 1.0 / e.value)
                elif e.type == "C":
                    Geq = 2 * e.value / T; Ieq = -Geq * cst[e.id] - cist[e.id]
                    stamp(A, e.nodes[0], e.nodes[1], Geq)
                    a, b = e.nodes[:2]
                    if a != "0": z[idx[a]] -= Ieq
                    if b != "0": z[idx[b]] += Ieq
                elif e.type == "L":
                    Geq = T / (2 * e.value); Ieq = lip[e.id] + Geq * lvp[e.id]
                    stamp(A, e.nodes[0], e.nodes[1], Geq)
                    a, b = e.nodes[:2]
                    if a != "0": z[idx[a]] -= Ieq
                    if b != "0": z[idx[b]] += Ieq
            for e in dio:
                a, b = e.nodes[:2]
                va = x[idx[a]] if a != "0" else 0.0
                vb = x[idx[b]] if b != "0" else 0.0
                I, g = _diode_ig(e.type, va - vb, e.params, Id[e.id]); Id[e.id] = I
                Ieq = I - g * (va - vb); stamp(A, a, b, g)
                if a != "0": z[idx[a]] -= Ieq
                if b != "0": z[idx[b]] += Ieq
            for k, e in enumerate(vs):
                r = nN + k; a, b = e.nodes[:2]
                if a != "0": A[idx[a], r] += 1; A[r, idx[a]] += 1
                if b != "0": A[idx[b], r] -= 1; A[r, idx[b]] -= 1
                z[r] = d if e.id.lower() == "vin" else (e.value or 0.0)
            for e in isrc:
                J = d if e.id.lower() == "iin" else (e.value or 0.0)
                a, b = e.nodes[:2]
                if a != "0": z[idx[a]] -= J
                if b != "0": z[idx[b]] += J
            for k, e in enumerate(oas):
                r = nN + len(vs) + k; neg, pos, o = e.nodes[:3]
                if o != "0": A[idx[o], r] += 1
                if neg != "0": A[r, idx[neg]] += 1
                if pos != "0": A[r, idx[pos]] -= 1
            xn = np.linalg.solve(A, z)
            done = np.max(np.abs(xn - x)) < 1e-12
            x = xn
            if done:
                break
        for e in caps:
            a, b = e.nodes[:2]
            va = x[idx[a]] if a != "0" else 0.0; vb = x[idx[b]] if b != "0" else 0.0
            v = va - vb; Geq = 2 * e.value / T; Ieq = -Geq * cst[e.id] - cist[e.id]
            cist[e.id] = Geq * v + Ieq; cst[e.id] = v
        for e in inds:
            a, b = e.nodes[:2]
            va = x[idx[a]] if a != "0" else 0.0; vb = x[idx[b]] if b != "0" else 0.0
            v = va - vb; Geq = T / (2 * e.value); Ieq = lip[e.id] + Geq * lvp[e.id]
            lip[e.id] = Geq * v + Ieq; lvp[e.id] = v
        out[step] = x[oid]
    return out


# --- signal helpers ---------------------------------------------------------
def sine(freq, amp, fs, dur):
    t = np.arange(int(fs * dur)) / fs
    return amp * np.sin(2 * np.pi * freq * t)


def sweep(f0, f1, amp, fs, dur):
    t = np.arange(int(fs * dur)) / fs
    return amp * np.sin(2 * np.pi * (f0 * t + (f1 - f0) / (2 * dur) * t ** 2))
