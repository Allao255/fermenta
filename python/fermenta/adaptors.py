"""
adaptors.py -- the single R-type scattering junction built from circuit topology.

This is the heart of VIOLA's method: the whole connection network is realised as
one N-port R-type adaptor whose scattering matrix S is computed directly from the
fundamental matrices Q (cutset) and B (loop) and the diagonal matrix of port
reference resistances Z = diag(Rp).

VIOLA's exact expressions (customizePlugin.m -> setMatrices), chosen by
tree/cotree size:

    t < l :  S = 2 Qᵀ (Q Z⁻¹ Qᵀ)⁻¹ Q Z⁻¹ − I         (cutset / voltage form)
    else  :  S = I − 2 Z Bᵀ (B Z Bᵀ)⁻¹ B              (loop / current form)

Both are the exact instantaneous scattering matrix of the reciprocal connection
network and are algebraically equal to the one-shot solve S = M⁻¹[−B; Q Z⁻¹]
(method="stacked", kept as an independent cross-check).
"""

from __future__ import annotations
import numpy as np


class RTypeJunction:
    def __init__(self, Q: np.ndarray, B: np.ndarray, Rp: np.ndarray):
        """Q, B in the SAME column/edge order as `Rp` (port reference resistances)."""
        self.Q = np.asarray(Q, float)
        self.B = np.asarray(B, float)
        self.set_port_resistances(Rp)

    def set_port_resistances(self, Rp, method="viola"):
        self.Rp = np.asarray(Rp, float)
        n = len(self.Rp)
        Z = np.diag(self.Rp)
        Zinv = np.diag(1.0 / self.Rp)
        t, l = self.Q.shape[0], self.B.shape[0]

        if method == "stacked":
            Ginv_rows = self.Q @ Zinv
            M = np.vstack([self.B, Ginv_rows])
            RHS = np.vstack([-self.B, Ginv_rows])
            self.S = np.linalg.solve(M, RHS)
        elif t < l:                                   # VIOLA cutset (Q) form
            Q = self.Q
            self.S = 2.0 * Q.T @ np.linalg.solve(Q @ Zinv @ Q.T, Q) @ Zinv - np.eye(n)
        else:                                         # VIOLA loop (B) form
            B = self.B
            self.S = np.eye(n) - 2.0 * Z @ B.T @ np.linalg.solve(B @ Z @ B.T, B)
        return self.S

    # ---- algebraic self-checks (used in tests) -----------------------------
    def kvl_residual(self):
        return float(np.max(np.abs(self.B @ (np.eye(len(self.Rp)) + self.S))))

    def kcl_residual(self):
        Zinv = np.diag(1.0 / self.Rp)
        return float(np.max(np.abs((self.Q @ Zinv) @ (np.eye(len(self.Rp)) - self.S))))

    def scatter(self, a: np.ndarray) -> np.ndarray:
        return self.S @ a


def scattering_opamp(Q_V, Q_I, B_V, B_I, Rp, method="viola"):
    """Scattering matrix for a circuit with ideal op-amps (nullors), exactly
    VIOLA's setMatrices op-amp branch:

        t < l :  S = 2 Q_Vᵀ (Q_I Z⁻¹ Q_Vᵀ)⁻¹ Q_I Z⁻¹ − I
        else  :  S = I − 2 Z B_Iᵀ (B_V Z B_Iᵀ)⁻¹ B_V
    """
    Rp = np.asarray(Rp, float)
    n = len(Rp)
    Z = np.diag(Rp); Zinv = np.diag(1.0 / Rp)
    t, l = Q_V.shape[0], B_V.shape[0]
    if t < l:
        return 2.0 * Q_V.T @ np.linalg.solve(Q_I @ Zinv @ Q_V.T, Q_I) @ Zinv - np.eye(n)
    return np.eye(n) - 2.0 * Z @ B_I.T @ np.linalg.solve(B_V @ Z @ B_I.T, B_V)


class _StaticJunction:
    """Minimal junction holding a precomputed scattering matrix S."""
    def __init__(self, S):
        self.S = np.asarray(S, float)
    def scatter(self, a):
        return self.S @ a
