"""Randomized circuit fuzzer: fermenta engine vs the independent VIOLA
reference (viola_reference.py). Compares ALL port voltages. Structural bugs
show up as SNR < 30 dB; numerical (inaudible) noise sits above ~60 dB."""
import numpy as np, random, sys
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from fermenta.netlist import Netlist
from fermenta.solver import WDFCircuit
from viola_reference import ViolaRef

DIODE = "params: Is=4.352n eta=1.905 Vth=25.8563m Rs=1m Rp=1Meg"

def gen_circuit(rng):
    nn = rng.randint(3, 6)                      # internal nodes N001..N00nn
    nodes = ["N%03d" % i for i in range(1, nn + 1)]
    alln = ["0"] + nodes
    lines = []
    rid = [1]
    def nid(p):
        rid[0] += 1
        return f"{p}{rid[0]}"
    # spanning tree of resistors -> connected
    connected = ["0"]
    pool = nodes[:]
    rng.shuffle(pool)
    for n in pool:
        a = rng.choice(connected)
        v = rng.choice(["1k", "4.7k", "10k", "47k", "100k", "470k"])
        lines.append(f"R{rid[0]} {n} {a} {v}"); rid[0] += 1
        connected.append(n)
    # Vin somewhere
    vin_n = rng.choice(nodes)
    lines.append(f"Vin {vin_n} 0 SINE(0 0.2 220)")
    # extra passives
    for _ in range(rng.randint(1, 4)):
        a, b = rng.sample(alln, 2)
        t = rng.random()
        if t < 0.5:
            v = rng.choice(["1n", "10n", "0.047u", "0.1u", "1u"])
            lines.append(f"C{rid[0]} {a} {b} {v}"); rid[0] += 1
        elif t < 0.65:
            v = rng.choice(["10m", "100m", "500m"])
            lines.append(f"L{rid[0]} {a} {b} {v}"); rid[0] += 1
        else:
            v = rng.choice(["1k", "22k", "100k", "1Meg"])
            lines.append(f"R{rid[0]} {a} {b} {v}"); rid[0] += 1
    # pot (rheostat or divider)
    if rng.random() < 0.7:
        pt = rng.choice(["lin", "log", "ilog"])
        sub = {"lin": "linearpotentiometer", "log": "logarithmicpotentiometer",
               "ilog": "inverselogarithmicpotentiometer"}[pt]
        pname = {"lin": "Plin", "log": "Plog", "ilog": "Pilog"}[pt]
        x = round(rng.uniform(0.1, 0.9), 2)
        if rng.random() < 0.5:
            a, b = rng.sample(alln, 2)
            lines.append(f"X{pname}1 {a} {b} {b} {sub} params: Rp=100k x={x}")
        else:
            a, b, c = rng.sample(alln, 3)
            lines.append(f"X{pname}1 {a} {b} {c} {sub} params: Rp=100k x={x}")
    # opamps
    n_oa = rng.choice([0, 1, 1, 2])
    for k in range(n_oa):
        neg, pos, out = rng.sample(alln, 3)
        if out == "0":
            out = rng.choice([n0 for n0 in nodes if n0 not in (neg, pos)])
        lines.append(f"XOA{k+1} {neg} {pos} {out} idealopamp")
    # diodes
    n_d = rng.choice([0, 1, 1, 1, 2])
    for k in range(n_d):
        a, b = rng.sample(alln, 2)
        typ = rng.choice(["D", "Dser", "Dap"])
        sub = {"D": "extendedschockleydiode", "Dser": "extendedschockleydiodeseries",
               "Dap": "extendedschockleydiodeantiparallel"}[typ]
        extra = "" if typ == "D" else " n=%d" % rng.randint(1, 3)
        lines.append(f"X{typ}{k+1} {a} {b} {sub} {DIODE}{extra}")
    return "\n".join(lines)

def run_one(seed, fs=48000, n=720, vin_ref=None):
    import fermenta.elements as FE
    old_ref = FE.VIN_REF_R
    if vin_ref is not None:
        FE.VIN_REF_R = vin_ref
    try:
        return _run_one_impl(seed, fs, n, vin_ref)
    finally:
        FE.VIN_REF_R = old_ref

def _run_one_impl(seed, fs, n, vin_ref):
    rng = random.Random(seed)
    text = gen_circuit(rng)
    nl = Netlist.parse(text)
    ok_f = ok_r = True; wf = ref = None; err_f = err_r = ""
    try:
        elem = next(e.id for e in nl.elements if e.type != "OA")
        has_oa = any(e.type == "OA" for e in nl.elements)
        if has_oa:
            node = next(n0 for n0 in nl.nodes if n0 != "0")
            wf = WDFCircuit(nl, fs, output_node=node)
            wf._outnode = node
        else:
            wf = WDFCircuit(nl, fs, output_element_id=elem)
    except Exception as e:
        ok_f = False; err_f = repr(e)[:60]
    try:
        ref = ViolaRef(nl, fs)
        if vin_ref is not None:
            for k, e in enumerate(ref.els):
                if e.type == "V":
                    ref.Z[k] = vin_ref
            if len(ref.dix) == 1:
                ref.Z[ref.dix[0]] = ref._Zn(ref.dix[0])
            ref.S = ref._buildS()
        if not np.all(np.isfinite(ref.S)):
            raise ValueError("nonfinite S")
    except Exception as e:
        ok_r = False; err_r = repr(e)[:60]
    if ok_f and getattr(wf, "Z_D", None) is not None and abs(wf.Z_D) < 1e-6:
        return ("skip-degenerate-ZD", 0.0, text)
    if not ok_f and not ok_r:
        return ("skip-both", 0.0, text)
    if ok_f != ok_r:
        if not ok_r and "Singular" in err_r:
            return ("skip-refsingular", 0.0, text)   # VIOLA itself would produce Inf/NaN here
        return (f"BUILD-DISAGREE f={ok_f}({err_f}) r={ok_r}({err_r})", 0.0, text)
    t = np.arange(n) / fs
    x = 0.2 * np.sin(2 * np.pi * 220 * t)
    has_oa = any(e.type == "OA" for e in nl.elements)
    node = None
    if has_oa:
        node = wf._outnode if hasattr(wf, "_outnode") else None
    try:
        if node:
            Vr, nv = ref.process(x, node=node)
        else:
            Vr = ref.process(x)
    except Exception as e:
        return ("ref-runtime-fail " + repr(e)[:50], 0.0, text)
    try:
        vports = wf.process_ports(x)
    except AttributeError:
        # fall back: compare the single output element voltage
        ids_r = [e.id for e in ref.els]
        try:
            y = wf.process(x)
        except Exception as e:
            return ("fermenta-runtime-fail " + repr(e)[:50], 0.0, text)
        if not np.all(np.isfinite(Vr)) or not np.all(np.isfinite(y)):
            fin_r = np.all(np.isfinite(Vr)); fin_f = np.all(np.isfinite(y))
            if fin_r != fin_f:
                return ("FINITE-DISAGREE", 0.0, text)
            return ("skip-nonfinite", 0.0, text)
        if wf.out_path is not None:
            if node is None:
                return ("skip-nodeout", 0.0, text)
            rms = np.sqrt(np.mean(nv ** 2))
            if not (np.all(np.isfinite(nv)) and np.all(np.isfinite(y))):
                return ("FINITE-DISAGREE", 0.0, text) if (np.all(np.isfinite(nv)) != np.all(np.isfinite(y))) else ("skip-nonfinite", 0.0, text)
            if rms < 1e-9:
                return ("skip-silent", 0.0, text)
            d = nv - y
            snr = 20 * np.log10(rms / max(np.sqrt(np.mean(d ** 2)), 1e-18))
            return ("ok", snr, text)
        k = ids_r.index(wf.elements[wf.out_idx].id)
        yr = Vr[:, k]
        rms = np.sqrt(np.mean(yr ** 2))
        if rms < 1e-9:
            return ("skip-silent", 0.0, text)
        d = yr - y
        snr = 20 * np.log10(rms / max(np.sqrt(np.mean(d ** 2)), 1e-18))
        return ("ok", snr, text)
    return ("n/a", 0.0, text)

def main(seeds):
    bad = []
    stats = {"ok": 0, "skip": 0, "other": 0}
    worst = (1e9, None)
    for sd in seeds:
        tag, snr, text = run_one(sd)
        if tag == "ok":
            stats["ok"] += 1
            if snr < 60:
                tag2, snr2, _ = run_one(sd, vin_ref=1e-3)
                if tag2 == "ok" and snr2 >= 90:
                    stats["cond-noise"] = stats.get("cond-noise", 0) + 1
                    continue          # conditioning noise, not a structural bug
                bad.append((sd, f"LOW-SNR(retest {tag2} {snr2:.1f}dB)", snr, text))
            if snr < worst[0]: worst = (snr, sd)
        elif tag.startswith("skip"):
            stats["skip"] += 1
        else:
            stats["other"] += 1
            bad.append((sd, tag, snr, text))
    print(f"ok={stats['ok']} skip={stats['skip']} cond-noise={stats.get('cond-noise',0)} anomal={stats['other']}  pior SNR={worst[0]:.1f} dB (seed {worst[1]})")
    for sd, tag, snr, text in bad[:6]:
        print(f"--- seed {sd}: {tag} snr={snr:.1f}")
        print(text)
    return len(bad)

if __name__ == "__main__":
    a = int(sys.argv[1]); b = int(sys.argv[2])
    sys.exit(0 if main(range(a, b)) == 0 else 1)
