"""
nonlinear.py -- nonlinear WDF elements, ported 1:1 from VIOLA.

VIOLA resolves a single diode at the (adapted) root of the R-type junction in
closed form using the Wright omega function, ω(x) = W(exp(x)) where W is the
Lambert W function. No per-sample Newton iteration is needed.

Ported functions:
  omega_wright(x)                    <- enhancedOmegaW.m
  ext_shockley_diode_scat(...)       <- extendedSchockleyDiodeScat.m
  ext_shockley_diode_res(...)        <- extendedSchockleyDiodeRes.m
"""

from __future__ import annotations
import numpy as np


def omega_wright(x: float) -> float:
    """Fast Wright omega, ported exactly from VIOLA's enhancedOmegaW.m
    (piecewise initial guess + one Fritsch-style correction step)."""
    if x < -3.6:
        y = 0.929404810843623 * np.exp(0.986418416898303 * x) - 6.79639452545093e-06
    elif x < 0:
        y = (-0.00431200176082888 * np.exp(3.55275697783407 * x)
             + 0.00792228971991872 * x**3 + 0.0907827580611564 * x**2
             + 0.375633000771424 * x + 0.571426071298747)
    elif x < 2.5:
        y = (-0.531567672565454 * np.exp(0.267412600010990 * x)
             - 0.00273225759962195 * x**3 + 0.0953348873301105 * x**2
             + 0.503184890060992 * x + 1.09876994061414)
    elif x < 7:
        y = (1.32189881177891 * np.exp(-2.05642141379680 * x)
             - 0.00164391849625201 * x**3 + 0.0428488786259462 * x**2
             + 0.481822411934234 * x + 0.418369998866986)
    elif x < 30:
        b = np.log(x + 0.217073722991741)
        y = (1.00007068672705 * x - 1.00147317311501 * b
             + 1.08561409526715 * b / x + 0.516677184575301 * b * (b - 2) / x**2)
    else:
        b = np.log(x)
        y = x - b + b / x + 0.5 * b * (b - 2) / x**2
    e = np.exp(x - y)
    f = y - e
    f1 = 1 + e
    y = y - f * (1 - 0.5 * (f * e / f1)**2) / f1
    return y


def ext_shockley_diode_scat(a, Z, Is, eta, Vth, Rs, Rp):
    """Reflected wave b for an extended-Shockley diode, exactly VIOLA's
    extendedSchockleyDiodeScat.m."""
    alpha = (2 * Rp * Is * Z + a * (Rp + Rs - Z)) / (Rp + Rs + Z)
    beta = 2 * eta * Vth * Z / (Rs + Z)
    gamma = Rp * Is * (Rs + Z) / (eta * Vth * (Rp + Rs + Z))
    delta = a * (Z - Rs) / (2 * eta * Vth * Z)
    return alpha - beta * omega_wright(np.log(gamma) + delta + alpha / beta)


def anti_ext_shockley_diode_scat(a, Z, Is, eta, Vth, Rs, Rp):
    """Reflected wave for an ANTIPARALLEL diode pair, exactly VIOLA's
    antiExtSchockleyDiodeScat.m (odd/symmetric characteristic via |a|,sign)."""
    mod_a = abs(a)
    sgn_a = np.sign(a)
    alpha = (2 * Rp * Is * Z + mod_a * (Rp + Rs - Z)) / (Rp + Rs + Z)
    beta = 2 * eta * Vth * Z / (Rs + Z)
    gamma = Rp * Is * (Rs + Z) / (eta * Vth * (Rp + Rs + Z))
    delta = mod_a * (Z - Rs) / (2 * eta * Vth * Z)
    return sgn_a * (alpha - beta * omega_wright(np.log(gamma) + delta + alpha / beta))


def ext_shockley_diode_res(v, i, Is, eta, Vth, Rs, Rp):
    """Small-signal Thevenin resistance, VIOLA's extendedSchockleyDiodeRes.m."""
    beta = eta * Vth
    expTerm = np.exp((v - Rs * i) / beta) / beta
    Rp_inv = 1.0 / Rp
    df_i = -1 - Rs * (Rp_inv + Is * expTerm)
    df_v = Rp_inv + Is * expTerm
    return -df_i / df_v


def anti_ext_shockley_diode_res(v, i, Is, eta, Vth, Rs, Rp):
    """Small-signal resistance of an antiparallel diode pair, VIOLA's
    antiExtSchockleyDiodeRes.m."""
    beta = eta * Vth
    hyp = 2 * Is * np.cosh((v - Rs * i) / beta) / beta
    Rp_inv = 1.0 / Rp
    return (Rs * (hyp + Rp_inv) + 1.0) / (hyp + Rp_inv)


if __name__ == "__main__":
    # ω(0) = W(1) = 0.5671432904...   ; ω(1) = 1.0 (since 1 + ln 1 = 1)
    for x, ref in [(0.0, 0.5671432904097838), (1.0, 1.0), (-5.0, np.exp(-5.0))]:
        print(f"omega({x:+.1f}) = {omega_wright(x):.12f}   ref ~ {ref:.12f}")
