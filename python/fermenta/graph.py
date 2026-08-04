"""
graph.py -- circuit graph, spanning tree/cotree and fundamental matrices.

Mirrors viola/windows/Functions/{getGraph,getTreeCotree,getQB}.m

Given a parsed Netlist, we build the circuit's directed graph (one edge per
2-terminal element), choose a spanning tree, and form the fundamental cutset
matrix Q and fundamental loop matrix B exactly as VIOLA does:

    A            full incidence matrix (nodes x edges), ground row dropped
    At, Ac       incidence restricted to tree / cotree edges
    F  = pinv(At) @ Ac                      (tree-cotree coupling)
    Q  = [ I_t | F ]                        (fundamental cutset matrix)
    B  = [ -F^T | I_l ]                     (fundamental loop matrix)

with Q @ B^T = 0 (orthogonality of cutset and loop spaces), which is the
sanity check used to validate the topology stage against MATLAB.

Tree-selection policy
---------------------
VIOLA picks a *random* spanning tree (findUsualTreeCotree.m). We instead build a
deterministic "normal tree" with the priority  V > C > R/pot > L > I  so results
are reproducible for testing. Any spanning tree yields a valid (if differently
ordered) WDF; the priority above is the classic choice that puts voltage sources
and capacitors in the tree and current sources/inductors in the cotree.
"""

from __future__ import annotations
import numpy as np
from .netlist import Netlist

# lower number = higher priority to be placed in the tree
_TREE_PRIORITY = {"V": 0, "C": 1, "R": 2, "L": 3, "I": 4,
                  "D": 2, "Dser": 2, "Dap": 2, "OA": 0, "X": 2}


class _UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.p[ra] = rb
        return True


class CircuitGraph:
    def __init__(self, netlist: Netlist):
        self.netlist = netlist
        self.nodes = netlist.nodes                       # '0' is ground, index 0
        self.node_index = {n: i for i, n in enumerate(self.nodes)}
        self.edges = list(netlist.elements)              # each element = one edge
        self._build_incidence()
        self._build_tree_cotree()
        self._build_QB()

    # ------------------------------------------------------------------ graph
    def _build_incidence(self):
        n, e = len(self.nodes), len(self.edges)
        A = np.zeros((n, e))
        for j, el in enumerate(self.edges):
            a, b = el.nodes[0], el.nodes[1]
            A[self.node_index[a], j] += 1.0     # tail  (+)
            A[self.node_index[b], j] -= 1.0     # head  (-)
        self.A_full = A
        # reduced incidence: drop ground row (index 0)
        self.A = A[1:, :]

    def _build_tree_cotree(self):
        order = sorted(range(len(self.edges)),
                       key=lambda j: (_TREE_PRIORITY.get(self.edges[j].type, 5), j))
        uf = _UnionFind(len(self.nodes))
        tree, cotree = [], []
        for j in order:
            a = self.node_index[self.edges[j].nodes[0]]
            b = self.node_index[self.edges[j].nodes[1]]
            if uf.union(a, b):
                tree.append(j)
            else:
                cotree.append(j)
        # keep edges in original order within tree/cotree for stable matrices
        self.tree = sorted(tree)
        self.cotree = sorted(cotree)

    def _build_QB(self):
        At = self.A[:, self.tree]
        Ac = self.A[:, self.cotree]
        t, l = len(self.tree), len(self.cotree)
        F = np.linalg.pinv(At) @ Ac
        F[np.abs(F) <= 1e-12] = 0.0
        self.F = F
        self.Q = np.hstack([np.eye(t), F])           # [I | F]  in (tree, cotree) column order
        self.B = np.hstack([-F.T, np.eye(l)])        # [-F^T | I]
        # column order corresponding to Q/B: tree edges then cotree edges
        self.qb_edge_order = self.tree + self.cotree

    # ------------------------------------------------------------------ checks
    def orthogonality_residual(self) -> float:
        """max |Q B^T| -- must be ~0 for a valid topology decomposition."""
        return float(np.max(np.abs(self.Q @ self.B.T)))

    def summary(self) -> str:
        e = self.edges
        tnames = [e[j].id for j in self.tree]
        cnames = [e[j].id for j in self.cotree]
        return (f"nodes={len(self.nodes)}  edges={len(self.edges)}  "
                f"tree({len(self.tree)})={tnames}  cotree({len(self.cotree)})={cnames}\n"
                f"Q shape={self.Q.shape}  B shape={self.B.shape}  "
                f"orthogonality max|QB^T|={self.orthogonality_residual():.2e}")


if __name__ == "__main__":
    import sys, os
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    name = sys.argv[1] if len(sys.argv) > 1 else "DEMO"
    path = os.path.join(base, f"viola/windows/Data/Input/Netlist/{name}.txt")
    nl = Netlist.parse(open(path).read())
    g = CircuitGraph(nl)
    print(f"=== {name} ===")
    print(g.summary())
    np.set_printoptions(precision=4, suppress=True)
    print("edge order (Q/B columns):", [g.edges[j].id for j in g.qb_edge_order])
    print("F =\n", g.F)
    print("Q =\n", g.Q)
    print("B =\n", g.B)
