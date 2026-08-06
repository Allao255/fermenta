"""
solver.py -- assemble ports + R-type junction and run the per-sample scattering.

Circuit classes supported (matching VIOLA):
  * lin                 : sources + R/C/L
  * one_non_lin         : + a single diode (D/Dser/Dap), closed form
  * lin_opamp           : + ideal op-amps (nullor, dual graph)
  * one_non_lin_opamp   : op-amp + one diode (e.g. MXR), closed form
  * non_lin[_opamp]     : 2+ diodes -> SIM/DSR iterative solver (e.g. DOD)
"""

from __future__ import annotations
import numpy as np
from .netlist import Netlist
from .graph import CircuitGraph
from .elements import make_port, DiodePort, CapacitorPort
from .adaptors import RTypeJunction, scattering_opamp, _StaticJunction
from .nonlinear import (ext_shockley_diode_scat, anti_ext_shockley_diode_scat,
                        ext_shockley_diode_res, anti_ext_shockley_diode_res)
from . import opamp as _opamp

_SCAT = {"D": ext_shockley_diode_scat, "Dser": ext_shockley_diode_scat,
         "Dap": anti_ext_shockley_diode_scat}
_RES = {"D": ext_shockley_diode_res, "Dser": ext_shockley_diode_res,
        "Dap": anti_ext_shockley_diode_res}


class WDFCircuit:
    def __init__(self, netlist, fs, output_element_id=None, output_node=None,
                 tol_slv=1e-5, tol_dsr=1000.0):
        self.netlist = netlist
        self.fs = fs
        self.tol_slv = tol_slv
        self.tol_dsr = tol_dsr
        self.has_opamp = any(e.type == "OA" for e in netlist.elements)
        if self.has_opamp:
            self._init_opamp(output_node)
        else:
            self._init_plain(output_element_id)
        self._setup_nonlinear()

    # ---------------------------------------------------------------- plain
    def _init_plain(self, output_element_id):
        self.graph = CircuitGraph(self.netlist)
        order = self.graph.qb_edge_order
        self.elements = [self.graph.edges[j] for j in order]
        self.ports = [make_port(el, self.fs) for el in self.elements]
        self.Rp = np.array([p.Rp for p in self.ports])
        self.source_idx = [i for i, p in enumerate(self.ports)
                           if getattr(p, "is_source", False)]
        self.diode_idx = [i for i, p in enumerate(self.ports) if isinstance(p, DiodePort)]
        Q, B = self.graph.Q, self.graph.B
        self._rebuild_S = lambda Z: RTypeJunction(Q, B, Z).S
        self.out_path = None
        self.out_idx = next(i for i, el in enumerate(self.elements)
                            if el.id == output_element_id)

    # ---------------------------------------------------------------- opamp
    def _init_opamp(self, output_node):
        sysd = _opamp.build_opamp_system(self.netlist, self.fs, make_port)
        self.elements = sysd["elements"]
        self.ports = sysd["ports"]
        self.Rp = sysd["Rp"]
        self.source_idx = [i for i, p in enumerate(self.ports)
                           if getattr(p, "is_source", False)]
        self.diode_idx = [i for i, p in enumerate(self.ports) if isinstance(p, DiodePort)]
        QV, QI, BV, BI = sysd["Q_V"], sysd["Q_I"], sysd["B_V"], sysd["B_I"]
        self._rebuild_S = lambda Z: scattering_opamp(QV, QI, BV, BI, Z)
        if output_node is None:
            raise ValueError("op-amp circuits need output_node='Nxxx'")
        self.out_path = _opamp.out_path_voltage_graph(sysd, output_node)
        self.out_idx = None
        self._sysd = sysd

    # ------------------------------------------------ nonlinear setup / dispatch
    def _setup_nonlinear(self):
        self.sim = len(self.diode_idx) >= 2
        self.Z_D = None
        if not self.diode_idx:                        # linear (± op-amp)
            self.junction = _StaticJunction(self._rebuild_S(self.Rp))
        elif not self.sim:                            # single diode, closed form
            d = self.diode_idx[0]
            self.Z_D = self._viola_Zn(d)
            self._dprev = 0.0
            self.Rp[d] = self.Z_D
            self.junction = _StaticJunction(self._rebuild_S(self.Rp))
        else:                                         # SIM/DSR (2+ diodes)
            for d in self.diode_idx:
                self.Rp[d] = 1.0                      # VIOLA: Z(nl) init = eye
            self.junction = _StaticJunction(self._rebuild_S(self.Rp))
            self._nl = [{"i": d, "type": self.elements[d].type,
                         "p": self.elements[d].params,
                         "scat": _SCAT[self.elements[d].type],
                         "res": _RES[self.elements[d].type]} for d in self.diode_idx]
            self.R_th = np.array([1.0 + self.tol_dsr] * len(self.diode_idx))
        self.leaf_idx = [i for i in range(len(self.ports)) if i not in self.diode_idx]

    # ---- VIOLA's exact nullor-MNA reduction for the adapted diode port ------
    # Faithful port of viola getMnaData/reorderMnaData + the plugin's updateS:
    #   Z_n = Yni (I + Up (H - Kp Yni Up)^{-1} Kp Yni),  Yni = (Ap Zp^{-1} Ap^T)^{-1}
    # datum row = alpha (first diode node); Z_D = Z_n[beta, beta] with beta taken
    # UNSHIFTED after the alpha row removal -- reproducing VIOLA's indexing
    # exactly (when beta > alpha this differs from the physical Thevenin; we
    # replicate it for bit-faithfulness with VIOLA-generated plugins).
    def _viola_mna_data(self, dport_idx):
        """Constant MNA structure for VIOLA's Z_n (also consumed by codegen)."""
        import re as _re
        de = self.elements[dport_idx]
        opamps = [e for e in self.netlist.elements if e.type == "OA"]
        lin = [(k, e) for k, e in enumerate(self.elements) if k != dport_idx]
        labels = {"0"} | {n for _, e in lin for n in e.nodes[:2]} | set(de.nodes[:2])
        for e in opamps:
            labels |= set(e.nodes[:3])
        def _num(l):
            m = _re.findall(r"\d+", l)
            return int(m[-1]) if m else None
        if all(l == "0" or _num(l) is not None for l in labels):
            ordered = sorted(labels, key=lambda l: 0 if l == "0" else _num(l))
        else:                                   # non-numeric labels: stable fallback
            ordered = ["0"] + sorted(l for l in labels if l != "0")
        idx = {l: i for i, l in enumerate(ordered)}
        nN = len(ordered); ne = len(lin); nO = len(opamps)
        Ainc = np.zeros((nN, ne)); eport = []
        for c, (k, e) in enumerate(lin):
            Ainc[idx[e.nodes[0]], c] -= 1.0
            Ainc[idx[e.nodes[1]], c] += 1.0
            eport.append(k)
        U = np.zeros((nN, nO)); K = np.zeros((nO, nN))
        for k, e in enumerate(opamps):
            neg, pos, out = e.nodes[:3]
            # ground is an ordinary row/column here (only alpha is removed)
            U[idx["0"], k] += 1.0; U[idx[out], k] -= 1.0     # NOR: 0 -> out
            K[k, idx[neg]] += 1.0; K[k, idx[pos]] -= 1.0     # NULL: neg -> pos
        al = idx[de.nodes[0]]; be = idx[de.nodes[1]]
        Ared = np.delete(Ainc, al, axis=0)
        Up = np.delete(U, al, axis=0); Kp = np.delete(K, al, axis=1)
        b = be if be < Ared.shape[0] else be - 1   # VIOLA indexes beta unshifted
        return Ared, eport, Up, Kp, b, nO

    @staticmethod
    def _gj_inv(Ain):
        """Gauss-Jordan inverse mirroring the generated C++ gsolve exactly
        (same pivoting and operation order => bit-identical results)."""
        import math
        n = Ain.shape[0]
        A = [[float(Ain[i, j]) for j in range(n)] for i in range(n)]
        B = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for c in range(n):
            piv = c; best = abs(A[c][c])
            for r in range(c + 1, n):
                v = abs(A[r][c])
                if v > best: best = v; piv = r
            if piv != c:
                A[c], A[piv] = A[piv], A[c]
                B[c], B[piv] = B[piv], B[c]
            d = A[c][c]
            for k in range(n): A[c][k] /= d
            for k in range(n): B[c][k] /= d
            for r in range(n):
                if r == c: continue
                f = A[r][c]
                if f != 0.0:
                    for k in range(n): A[r][k] -= f * A[c][k]
                    for k in range(n): B[r][k] -= f * B[c][k]
        return B

    def _viola_Zn(self, dport_idx):
        """Bit-exact mirror of the generated C++ computeZD()."""
        import math
        Ared, eport, Up, Kp, b, nO = self._viola_mna_data(dport_idx)
        nM = Ared.shape[0]; ne = Ared.shape[1]
        A = [[float(Ared[i, j]) for j in range(ne)] for i in range(nM)]
        Yn = [[0.0] * nM for _ in range(nM)]
        for e in range(ne):
            g = 1.0 / float(self.ports[eport[e]].Rp)
            for r in range(nM):
                ar = A[r][e]
                if ar == 0.0: continue
                for c in range(nM):
                    ac = A[c][e]
                    if ac != 0.0: Yn[r][c] += g * ar * ac
        dsc = [0.0] * nM
        for i in range(nM):
            v = abs(Yn[i][i]); dsc[i] = math.sqrt(v) if v > 0.0 else 1.0
        for i in range(nM):
            for j in range(nM): Yn[i][j] /= (dsc[i] * dsc[j])
        Yni = self._gj_inv(np.array(Yn))
        for i in range(nM):
            for j in range(nM): Yni[i][j] /= (dsc[i] * dsc[j])
        if nO == 0:
            return float(Yni[b][b])
        T1 = [[0.0] * nM for _ in range(nO)]
        T2 = [[0.0] * nO for _ in range(nM)]
        M = [[0.0] * nO for _ in range(nO)]
        for i in range(nO):
            for j in range(nM):
                t = 0.0
                for k in range(nM): t += float(Kp[i, k]) * Yni[k][j]
                T1[i][j] = t
        for i in range(nM):
            for j in range(nO):
                t = 0.0
                for k in range(nM): t += Yni[i][k] * float(Up[k, j])
                T2[i][j] = t
        for i in range(nO):
            for j in range(nO):
                t = 0.0
                for k in range(nM): t += T1[i][k] * float(Up[k, j])
                M[i][j] = -t
        Mi = self._gj_inv(np.array(M))
        z = Yni[b][b]
        for i in range(nO):
            for j in range(nO): z += T2[b][i] * Mi[i][j] * T1[j][b]
        return float(z)

    # ---- Thevenin driving-point resistances (for closed-form single diode) ---
    def _driving_point_resistance(self, dport_idx):
        nodes = self.graph.nodes; idx = {n: i for i, n in enumerate(nodes)}
        Y = np.zeros((len(nodes), len(nodes)))
        for k, (el, port) in enumerate(zip(self.elements, self.ports)):
            if k == dport_idx: continue
            g = 1.0 / port.Rp; a, b = idx[el.nodes[0]], idx[el.nodes[1]]
            Y[a, a] += g; Y[b, b] += g; Y[a, b] -= g; Y[b, a] -= g
        de = self.elements[dport_idx]; da, db = idx[de.nodes[0]], idx[de.nodes[1]]
        keep = [i for i in range(len(nodes)) if i != db]
        v = np.linalg.solve(Y[np.ix_(keep, keep)],
                            np.eye(len(keep))[keep.index(da)])
        return float(v[keep.index(da)])

    def _driving_point_resistance_mna(self, dport_idx):
        opamps = [e for e in self.netlist.elements if e.type == "OA"]
        lin = [(k, e, p) for k, (e, p) in enumerate(zip(self.elements, self.ports))
               if k != dport_idx]
        nodes = sorted({n for _, e, _ in lin for n in e.nodes[:2]}
                       | {n for e in opamps for n in e.nodes[:3]} | {"0"})
        nodes = [n for n in nodes if n != "0"]; idx = {n: i for i, n in enumerate(nodes)}
        nN, nO = len(nodes), len(opamps); dim = nN + nO
        A = np.zeros((dim, dim))
        def stamp(a, b, g):
            for n1, n2, sg in [(a, a, g), (b, b, g), (a, b, -g), (b, a, -g)]:
                if n1 != "0" and n2 != "0": A[idx[n1], idx[n2]] += sg
        for _, e, port in lin: stamp(e.nodes[0], e.nodes[1], 1.0 / port.Rp)
        for k, e in enumerate(opamps):
            r = nN + k; neg, pos, o = e.nodes[:3]
            if o != "0": A[idx[o], r] += 1.0
            if neg != "0": A[r, idx[neg]] += 1.0
            if pos != "0": A[r, idx[pos]] -= 1.0
        de = self.elements[dport_idx]; z = np.zeros(dim); da, db = de.nodes[0], de.nodes[1]
        if da != "0": z[idx[da]] += 1.0
        if db != "0": z[idx[db]] -= 1.0
        x = np.linalg.solve(A, z)
        return float((x[idx[da]] if da != "0" else 0.0) - (x[idx[db]] if db != "0" else 0.0))

    # ------------------------------------------------------------------ run
    def reset(self):
        self._dprev = 0.0
        for p in self.ports:
            p.reset()
        if self.sim:
            n = len(self.ports)
            self._a = np.zeros(n); self._b = np.zeros(n); self._v = np.zeros(n)
            for d in self.diode_idx: self.Rp[d] = 1.0
            self.R_th = np.array([1.0 + self.tol_dsr] * len(self.diode_idx))
            self.junction.S = self._rebuild_S(self.Rp)

    def _out_from(self, a, b):
        if self.out_path is not None:
            return sum(sgn * 0.5 * (a[j] + b[j]) for j, sgn in self.out_path)
        j = self.out_idx
        return 0.5 * (a[j] + b[j])

    # ---- closed-form path (linear / single diode) --------------------------
    def _sample_closed(self, sample):
        S = self.junction.S
        a = np.zeros(len(self.ports))
        for i in self.source_idx:
            if self.elements[i].id == self.netlist.input_id:
                self.ports[i].set_input(sample)
        for i in self.leaf_idx:
            a[i] = self.ports[i].reflect()
        if self.diode_idx:
            d = self.diode_idx[0]
            a[d] = getattr(self, '_dprev', 0.0)   # VIOLA keeps the diode's previous
            a_D = float(S[d, :] @ a)        # reflection in the b-vector
            P = self.elements[d].params
            scat = _SCAT[self.elements[d].type]
            a[d] = scat(a_D, self.Z_D, P["Is"], P["eta"], P["Vth"], P["Rs"], P["Rp"])
            self._dprev = a[d]
        b = S @ a
        for i, p in enumerate(self.ports):
            p.set_incident(b[i]); p.b = a[i]
        return self._out_from(b, a)     # note: voltage=(incident+reflection)/2

    # ---- SIM/DSR path (2+ diodes) ------------------------------------------
    def _sample_sim(self, sample):
        b = self._b; a = self._a
        for i in self.source_idx:
            if self.elements[i].id == self.netlist.input_id:
                self.ports[i].set_input(sample)
        for i in self.leaf_idx:
            b[i] = self.ports[i].reflect()            # linear reflections (VIOLA b)

        # DSR: re-adapt nonlinear port resistances when they drift, rebuild S
        Znl = np.array([self.Rp[nl["i"]] for nl in self._nl])
        if np.sum(np.abs(Znl - self.R_th)) >= self.tol_dsr:
            for k, nl in enumerate(self._nl):
                self.Rp[nl["i"]] = self.R_th[k]
            self.junction.S = self._rebuild_S(self.Rp)
        S = self.junction.S

        # SIM: fixed-point scattering iteration until port voltages converge
        v = self._v; v_old = v + self.tol_slv
        it = 0
        while np.linalg.norm(v - v_old) >= self.tol_slv and it < 200:
            v_old = v.copy()
            for nl in self._nl:
                d = nl["i"]; P = nl["p"]
                b[d] = nl["scat"](a[d], self.Rp[d],
                                  P["Is"], P["eta"], P["Vth"], P["Rs"], P["Rp"])
            a[:] = S @ b
            v = 0.5 * (a + b)
            it += 1
        self._v = v

        # update per-diode small-signal resistance for next sample's DSR
        for k, nl in enumerate(self._nl):
            d = nl["i"]; P = nl["p"]
            iv = 0.5 * (a[d] - b[d]) / self.Rp[d]
            self.R_th[k] = nl["res"](v[d], iv, P["Is"], P["eta"], P["Vth"], P["Rs"], P["Rp"])

        # latch capacitor states from converged incident waves
        for i, p in enumerate(self.ports):
            if isinstance(p, CapacitorPort):
                p.set_incident(a[i])
        return self._out_from(a, b)

    def process_sample(self, sample):
        return self._sample_sim(sample) if self.sim else self._sample_closed(sample)

    def process(self, signal):
        self.reset()
        return np.array([self.process_sample(s) for s in np.asarray(signal, float)])
