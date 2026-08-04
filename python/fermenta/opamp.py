"""
opamp.py -- ideal op-amp (nullor) support for the topological WDF, ported from
VIOLA's getVoltCurrGraphs / handleOpamps / findCommTreeCotree / getVoltCurrQB.

An ideal op-amp (neg, pos, out) is a nullor:
  * nullator at the input  -> V(neg) = V(pos), and no input current
  * norator at the output  -> the output delivers whatever current is needed

VIOLA realises this with TWO graphs over the non-op-amp elements:
  * voltage graph G_V : merge node  neg -> pos      (equal input voltages)
  * current graph G_I : merge node  out -> ground    (free output current)
Both graphs share one common spanning tree; from them come Q_V,B_V and Q_I,B_I,
and the scattering matrix couples the two (see adaptors.scattering_opamp).
"""

from __future__ import annotations
import random
import numpy as np


class _UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return False
        self.p[ra] = rb; return True


def _merge_map(nodes, pairs):
    """Return a function mapping each node to its merged representative."""
    parent = {n: n for n in nodes}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in pairs:            # merge a -> b
        parent[find(a)] = find(b)
    return find


def build_opamp_system(netlist, fs, make_port):
    """Returns dict with ordered non-OA elements, port resistances, and the
    four fundamental matrices Q_V,Q_I,B_V,B_I (columns in the ordered-element
    order), plus node bookkeeping for the output path."""
    els = netlist.elements
    opamps = [e for e in els if e.type == "OA"]
    lin = [e for e in els if e.type != "OA"]

    # node merges
    volt_pairs = [(e.nodes[0], e.nodes[1]) for e in opamps]      # neg -> pos
    curr_pairs = [(e.nodes[2], "0") for e in opamps]             # out -> ground
    allnodes = set()
    for e in lin:
        allnodes.update(e.nodes[:2])
    for e in opamps:
        allnodes.update(e.nodes[:3])
    fV = _merge_map(allnodes, volt_pairs)
    fI = _merge_map(allnodes, curr_pairs)

    endV = [(fV(e.nodes[0]), fV(e.nodes[1])) for e in lin]
    endI = [(fI(e.nodes[0]), fI(e.nodes[1])) for e in lin]
    nodesV = sorted({n for ab in endV for n in ab})
    nodesI = sorted({n for ab in endI for n in ab})
    iV = {n: k for k, n in enumerate(nodesV)}
    iI = {n: k for k, n in enumerate(nodesI)}

    # common spanning tree (acyclic in BOTH graphs), randomized like VIOLA
    t_target = len(nodesV) - 1
    tree = None
    for attempt in range(2000):
        rng = random.Random(21 + attempt)
        order = list(range(len(lin))); rng.shuffle(order)
        ufV, ufI = _UF(len(nodesV)), _UF(len(nodesI))
        picked = []
        for j in order:
            av, bv = iV[endV[j][0]], iV[endV[j][1]]
            ai, bi = iI[endI[j][0]], iI[endI[j][1]]
            if ufV.find(av) != ufV.find(bv) and ufI.find(ai) != ufI.find(bi):
                ufV.union(av, bv); ufI.union(ai, bi); picked.append(j)
        if len(picked) == t_target:
            tree = picked; break
    if tree is None:
        raise RuntimeError("no common spanning tree found for op-amp circuit")
    cotree = [j for j in range(len(lin)) if j not in tree]
    order = tree + cotree                    # column order for Q/B (== VIOLA)

    def _F(endp, idxmap):
        A = np.zeros((len(idxmap), len(lin)))
        for j, (a, b) in enumerate(endp):
            A[idxmap[a], j] += 1.0; A[idxmap[b], j] -= 1.0
        At = A[:, tree]; Ac = A[:, cotree]
        F = np.linalg.pinv(At) @ Ac
        F[np.abs(F) <= 1e-12] = 0.0
        return F
    t, l = len(tree), len(cotree)
    F_V = _F(endV, iV); F_I = _F(endI, iI)
    Q_V = np.hstack([np.eye(t), F_V]); Q_I = np.hstack([np.eye(t), F_I])
    B_V = np.hstack([-F_V.T, np.eye(l)]); B_I = np.hstack([-F_I.T, np.eye(l)])

    ordered = [lin[j] for j in order]
    endV_ordered = [(fV(e.nodes[0]), fV(e.nodes[1])) for e in ordered]
    ports = [make_port(e, fs) for e in ordered]
    Rp = np.array([p.Rp for p in ports])
    return {
        "elements": ordered, "ports": ports, "Rp": Rp,
        "Q_V": Q_V, "Q_I": Q_I, "B_V": B_V, "B_I": B_I,
        "fV": fV, "fI": fI, "nodesV": nodesV, "iV": iV,
        "endV_ordered": endV_ordered,
    }


def out_path_voltage_graph(system, out_node):
    """Path from ground to out_node in the (merged) voltage graph; returns a
    list of (ordered_element_index, sign) so the output voltage is
    sum(sign * (a+b)/2). Mirrors VIOLA's getOutPath in the voltage graph."""
    fV = system["fV"]
    endV = system["endV_ordered"]
    gnd = fV("0")
    tgt = fV(out_node)
    if tgt == gnd:
        return []
    # adjacency: node -> list of (neighbor, edge_index)
    adj = {}
    for j, (a, b) in enumerate(endV):
        adj.setdefault(a, []).append((b, j))
        adj.setdefault(b, []).append((a, j))
    # BFS shortest path
    from collections import deque
    prev = {gnd: (None, None)}
    dq = deque([gnd])
    while dq:
        u = dq.popleft()
        if u == tgt:
            break
        for v, j in adj.get(u, []):
            if v not in prev:
                prev[v] = (u, j); dq.append(v)
    if tgt not in prev:
        raise RuntimeError(f"output node {out_node!r} not reachable in voltage graph")
    # reconstruct
    path = []
    node = tgt
    while prev[node][0] is not None:
        u, j = prev[node]
        n1, n2 = endV[j]
        # VIOLA sign rule: stepping u->node; if u==n1 and node==n2 -> -1 else +1
        sgn = -1.0 if (u == n1 and node == n2) else 1.0
        path.append((j, sgn))
        node = u
    path.reverse()
    return path
