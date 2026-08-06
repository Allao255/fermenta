"""
elements.py -- wave-domain models for individual circuit elements (ports).

Each 2-terminal element becomes one port of the big R-type junction. A port has:
  * a reference (port) resistance  Rp
  * a local reflection law that returns its outgoing wave b given the incoming a
    (and, for reactances, its internal state; for sources, the input voltage).

Wave convention (voltage waves):
    a = v + Rp * i
    b = v - Rp * i          =>   v = (a + b)/2 ,  i = (a - b)/(2 Rp)

Discretization of reactances uses the bilinear (trapezoidal) transform, which is
exactly what VIOLA / the reference nodal solver use, so results are comparable:

    Capacitor C :  Rp = T / (2 C)      b[n] =  a[n-1]          (state = last a)
    Inductor  L :  Rp = 2 L / T        b[n] = -a[n-1]

Sources and nonlinear devices are "root" ports handled by the solver.
"""

from __future__ import annotations
import numpy as np


class Port:
    is_root = False
    is_source = False

    def __init__(self, element, fs):
        self.el = element
        self.fs = fs
        self.T = 1.0 / fs
        self.Rp = self.port_resistance()
        self.a = 0.0
        self.b = 0.0

    def port_resistance(self) -> float:
        raise NotImplementedError

    def reflect(self) -> float:
        """Return outgoing wave b (called before the junction scatters)."""
        return 0.0

    def set_incident(self, a: float):
        self.a = a

    def voltage(self) -> float:
        return 0.5 * (self.a + self.b)

    def current(self) -> float:
        return 0.5 * (self.a - self.b) / self.Rp

    def reset(self):
        self.a = self.b = 0.0


class ResistorPort(Port):
    def port_resistance(self):
        return float(self.el.value)

    def reflect(self):
        self.b = 0.0            # matched: a resistor at its own reference reflects nothing
        return self.b


class CapacitorPort(Port):
    def port_resistance(self):
        return self.T / (2.0 * float(self.el.value))

    def reflect(self):
        self.b = self._state    # bilinear: b[n] = a[n-1]
        return self.b

    def set_incident(self, a):
        self.a = a
        self._state = a

    def reset(self):
        super().reset()
        self._state = 0.0


class InductorPort(Port):
    def port_resistance(self):
        return 2.0 * float(self.el.value) / self.T

    def reflect(self):
        self.b = -self._state   # bilinear: b[n] = -a[n-1]
        return self.b

    def set_incident(self, a):
        self.a = a
        self._state = a

    def reset(self):
        super().reset()
        self._state = 0.0


# VIOLA's fixed reference resistance for the input source Vin (extractElValues:
# case 'Vin' -> values(1) = 10^(-9)). Matching this exactly is required for
# bit-compatibility with VIOLA on the source port.
VIN_REF_R = 1e-9


class IdealVoltageSourcePort(Port):
    """Input voltage source, modelled exactly as VIOLA does: a *matched
    resistive* source with a tiny fixed reference resistance (1e-9 ohm) whose
    reflected wave is simply the input sample, b = E. Because the port is
    matched to its own internal resistance it is adapted (a leaf, not a root):
    the reflection does not depend on the incident wave."""
    is_root = False

    def __init__(self, element, fs, r_ref=None):
        self._r_ref = VIN_REF_R if r_ref is None else r_ref
        super().__init__(element, fs)
        self.E = float(element.value) if element.value is not None else 0.0

    def port_resistance(self):
        return self._r_ref

    is_source = True

    def set_voltage(self, E):
        self.E = float(E)

    set_input = set_voltage

    def reflect(self):
        self.b = self.E          # VIOLA: p.b(pos_Vin) = in(ii)
        return self.b


class DiodePort(Port):
    """Extended-Shockley diode as a nonlinear root port.

    NOTE: this is the piece intended for the "build later" phase. The wave-domain
    reflection is implicit and solved iteratively (Newton / Lambert-W). Here we
    expose the branch model and a scalar fixed-point so the solver can be
    completed; the resistance is a fixed linearization reference.
    """
    is_root = True

    @property
    def kind(self):
        return self.el.type           # 'D', 'Dser', or 'Dap'

    def port_resistance(self):
        return float(self.el.params.get("Rs", 1e-3)) + 1e3   # crude reference

    def branch_current(self, Vd, I0=0.0, tol=1e-14, itmax=80):
        p = self.el.params
        Is, eta, Vth = p["Is"], p["eta"], p["Vth"]
        Rs, Rp = p["Rs"], p["Rp"]
        vt = eta * Vth
        I = I0
        for _ in range(itmax):
            u = min((Vd - Rs * I) / vt, 200.0)
            e = np.exp(u)
            G = I - Is * (e - 1.0) - (Vd - Rs * I) / Rp
            dG = 1.0 + Is * Rs / vt * e + Rs / Rp
            I -= G / dG
        return I

    def reflect(self):
        # TODO(build-later): solve b such that the diode constitutive law holds
        # in the wave domain (implicit -> Newton on b). Placeholder passthrough.
        self.b = self.a
        return self.b


# VIOLA's fixed reference resistance for current sources (extractElValues:
# case 'Iin' -> 1e9 ; case 'I' -> P(:,2)=1e9). Large parallel resistance ~ ideal
# current source. Faithful copy of VIOLA's handling (no shipped example uses it).
IIN_REF_R = 1e9


class CurrentSourcePort(Port):
    """Current source (Norton) with a large parallel reference resistance Rg=1e9
    (VIOLA's value), i.e. a near-ideal current source.

    NOTE ON VIOLA FIDELITY: VIOLA's shipped code sets the reflected wave to the
    raw current, b = J (linearRefScat case 3/4). Tested, that produces ~0 output
    because with Z=1e9 the port is nearly open -- VIOLA's current-source handling
    is an untested stub (no shipped circuit uses Iin/I). The physically correct
    Norton wave is b = Rg*J, which we use here so the element actually works.
    Set viola_faithful=True to reproduce VIOLA's (non-functional) b = J instead."""
    is_source = True
    viola_faithful = False

    def __init__(self, element, fs, r_ref=None):
        self._r_ref = IIN_REF_R if r_ref is None else r_ref
        super().__init__(element, fs)
        self.J = float(element.value) if element.value is not None else 0.0

    def port_resistance(self):
        return self._r_ref

    def set_input(self, J):
        self.J = float(J)

    def reflect(self):
        self.b = self.J if self.viola_faithful else -self._r_ref * self.J
        return self.b


_PORT_TYPES = {
    "R": ResistorPort, "C": CapacitorPort, "L": InductorPort,
    "V": IdealVoltageSourcePort,
    "I": CurrentSourcePort,
    "D": DiodePort, "Dser": DiodePort, "Dap": DiodePort,
}


def make_port(element, fs) -> Port:
    cls = _PORT_TYPES.get(element.type)
    if cls is None:
        raise NotImplementedError(
            f"No wave model yet for element type {element.type!r} "
            f"({element.id}). See docs/ for the roadmap.")
    return cls(element, fs)
