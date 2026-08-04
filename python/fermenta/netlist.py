"""
netlist.py -- LTspice netlist parsing for VIOLA-style circuits.

Mirrors viola/windows/Functions/{cleanNetlist,handlePots,netlistParse}.m

Supported element prefixes (VIOLA naming rules, see viola/README.md):
    V    ideal voltage source        (Vin = the single input source)
    I    ideal current source
    R    resistor
    C    capacitor
    L    inductor
    XD   diode (extended Shockley)                  -> type 'D'
    XDser diode series                              -> type 'Dser'
    XDap diode antiparallel                         -> type 'Dap'
    XPlin/XPlog/XPilog potentiometer (lin/log/inv)  -> type 'P*'
    XOA  ideal opamp                                -> type 'OA'

Potentiometers are expanded into two resistors Ra, Rb (handlePots.m):
    Ra between node1-node2 = Rp*x        (+ tolerance)
    Rb between node2-node3 = Rp*(1-x)    (+ tolerance)
When node2 == node3 (as in DEMO) Rb collapses and the pot is a single
variable resistor Ra = Rp*x.

SI-suffix engineering notation is handled (eng2num.m): p n u/µ m k Meg g.
"""

from __future__ import annotations
import re
import math
from dataclasses import dataclass, field
from typing import Optional


_ENG = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3,
    "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12,
}


def eng2num(s: str) -> float:
    """Convert an LTspice engineering-notation value (e.g. '4.7k', '0.1µ') to float."""
    s = s.strip()
    m = re.match(r"^([+-]?[\d.]+(?:[eE][+-]?\d+)?)\s*([a-zA-Zµ]*)$", s)
    if not m:
        return float(s)
    val, suf = m.group(1), m.group(2).lower()
    if suf == "":
        return float(val)
    if suf.startswith("meg"):
        return float(val) * 1e6
    return float(val) * _ENG.get(suf[0], 1.0)


@dataclass
class Element:
    id: str                       # e.g. 'R4', 'C1', 'D1', 'Vin'
    type: str                     # 'V','I','R','C','L','D','Dser','Dap','Plin',...
    nodes: tuple                  # ('N002','N003')  (2-terminal after pot expansion)
    params: dict = field(default_factory=dict)
    value: Optional[float] = None  # scalar value for R/C/L/V/I


@dataclass
class Netlist:
    elements: list = field(default_factory=list)
    input_id: Optional[str] = None      # 'Vin' or 'Iin'

    @property
    def nodes(self):
        s = set()
        for e in self.elements:
            s.update(e.nodes)
        # ground '0' first, then sorted
        rest = sorted(n for n in s if n != "0")
        return (["0"] + rest) if "0" in s else rest

    @classmethod
    def parse(cls, text: str) -> "Netlist":
        nl = cls()
        in_subckt = False
        for raw in text.splitlines():
            line = raw.strip()
            low = line.lower()
            # skip everything inside .subckt ... .ends block bodies
            if low.startswith(".subckt"):
                in_subckt = True
                continue
            if low.startswith(".ends"):
                in_subckt = False
                continue
            if in_subckt:
                continue
            if not line or line.startswith("*") or line.startswith("."):
                continue
            if low.startswith("b "):
                continue
            toks = line.split()
            name = toks[0]
            up = name.upper()

            # --- sources -----------------------------------------------------
            if up.startswith("V") or up.startswith("I"):
                n1, n2 = toks[1], toks[2]
                val = None
                if len(toks) > 3:
                    try:
                        val = eng2num(toks[3])          # DC source value (e.g. "9")
                    except ValueError:
                        val = None                      # e.g. SINE(...) input
                el = Element(name, name[0].upper(), (n1, n2), value=val)
                if name.lower() in ("vin", "iin"):
                    nl.input_id = name
                nl.elements.append(el)

            # --- linear R/C/L ------------------------------------------------
            elif up.startswith(("R", "C", "L")):
                n1, n2 = toks[1], toks[2]
                val = eng2num(toks[3]) if len(toks) > 3 else None
                nl.elements.append(Element(name, name[0].upper(), (n1, n2), value=val))

            # --- X sub-circuit devices --------------------------------------
            elif up.startswith("X"):
                nl._parse_x(toks)
        return nl

    def _parse_x(self, toks):
        name = toks[0]
        low = name.lower()
        params = _kv_params(toks)
        # node list is between name and the subckt keyword / 'params:'
        subkw_idx = next((i for i, t in enumerate(toks)
                          if t.lower() in ("params:",) or i > 0 and _is_subckt_kw(t)),
                         len(toks))
        nodes = toks[1:subkw_idx]

        if "diode" in low or low.startswith("xd"):
            # VIOLA types diodes by element-name prefix (XD / XDser / XDap),
            # falling back to the subckt keyword.
            if low.startswith("xdap") or "antiparallel" in _kw(toks):
                typ = "Dap"
            elif low.startswith("xdser") or "series" in _kw(toks):
                typ = "Dser"
            else:
                typ = "D"
            if typ in ("Dser", "Dap"):        # VIOLA scales eta, Rs, Rp by n
                nn = float(params.get("n", 1.0))
                params = dict(params)
                for key in ("eta", "Rs", "Rp"):
                    if key in params:
                        params[key] = params[key] * nn
            self.elements.append(Element(name, typ, tuple(nodes[:2]), params=params))
        elif "opamp" in _kw(toks) or low.startswith("xoa"):
            self.elements.append(Element(name, "OA", tuple(nodes), params=params))
        elif "potentiometer" in _kw(toks) or low.startswith("xp"):
            self._expand_pot(name, nodes, params, _kw(toks))
        else:
            self.elements.append(Element(name, "X", tuple(nodes), params=params))

    def _expand_pot(self, name, nodes, params, kw):
        if "inverselog" in kw:
            typ, pt = "Pilog", "ilog"
        elif "log" in kw:
            typ, pt = "Plog", "log"
        else:
            typ, pt = "Plin", "lin"
        n1, n2, n3 = nodes[0], nodes[1], nodes[2]
        Rp = params.get("Rp", 0.0)
        x = params.get("x", 0.5)
        tol = 1e-6
        # exact tapers matching VIOLA's deployed plug-in (getUpFuncs)
        Ra = pot_taper(pt, "Ra", x, Rp, tol)
        Rb = pot_taper(pt, "Rb", x, Rp, tol)
        # VIOLA handlePots has three cases (never a degenerate ground-ground R):
        meta = {"pot": name, "type": typ, "x": x, "Rp": Rp}
        if n1 == n2:                     # only Rb (node2-node3)
            self.elements.append(Element(name + "_Rb", "R", (n2, n3), value=Rb, params=meta))
        elif n2 == n3:                   # only Ra (node1-node2)
            self.elements.append(Element(name + "_Ra", "R", (n1, n2), value=Ra, params=meta))
        else:                            # both
            self.elements.append(Element(name + "_Ra", "R", (n1, n2), value=Ra, params=meta))
            self.elements.append(Element(name + "_Rb", "R", (n2, n3), value=Rb, params=meta))


def pot_taper(pt, role, x, Rp, tol=1e-6):
    """Potentiometer resistance for taper `pt` ('lin'|'log'|'ilog'), leg `role`
    ('Ra'|'Rb'), wiper position x in [0,1]. Matches VIOLA's runtime updater
    (getUpFuncs) -- the tapers the deployed plug-in uses."""
    ra = (role == "Ra" or role == 0)
    if pt == "log":
        return (0.0125 * Rp * (81 ** x - 1) if ra else 1.0125 * Rp * (1 - 81 ** (x - 1))) + tol
    if pt == "ilog":
        return (0.25 * math.log(1 + x / 0.0125) * Rp / math.log(3) if ra
                else 0.25 * math.log(1.0125 / (x + 0.0125)) * Rp / math.log(3)) + tol
    return (Rp * x if ra else Rp * (1 - x)) + tol


def _kv_params(toks):
    params = {}
    for t in toks:
        if "=" in t:
            k, v = t.split("=", 1)
            try:
                params[k] = eng2num(v)
            except ValueError:
                params[k] = v
    return params


def _kw(toks):
    return " ".join(t.lower() for t in toks)


def _is_subckt_kw(t):
    t = t.lower()
    return any(k in t for k in ("diode", "opamp", "potentiometer"))

if __name__ == "__main__":
    import sys, os
    if len(sys.argv) > 1:
        txt = open(sys.argv[1]).read()
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        txt = open(os.path.join(base, "viola/windows/Data/Input/Netlist/DEMO.txt")).read()
    nl = Netlist.parse(txt)
    print("input:", nl.input_id)
    print("nodes:", nl.nodes)
    for e in nl.elements:
        print(f"  {e.id:12s} {e.type:5s} {e.nodes}  value={e.value}  {e.params}")
