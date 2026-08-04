"""
fermenta.compare -- side-by-side comparison of two pedals (e.g. our JUCE VST3
vs VIOLA's VST3), in time and frequency, like the main GUI but for TWO signals.

Idea
----
Feed the *same* input into both plugins, capture each output, and overlay the
two responses (waveform + magnitude spectrum) plus their difference and a few
numbers (max |diff|, RMS diff, SNR).

Workflow
--------
1. "Gerar input" writes a test stimulus WAV (sine or log sweep).
2. In your DAW (REAPER), run that WAV through plugin A, render -> outA.wav;
   through plugin B, render -> outB.wav.
3. Load outA and outB here and click "Comparar".

Shortcut: for signal A you can instead "Renderizar do netlist", which runs our
own engine directly (identical to our VST) so you only need to render VIOLA's
plugin in the DAW.

Run:  python -m fermenta.compare
"""
from __future__ import annotations
import os
import wave
import numpy as np

from .gui import Session


# ----------------------------------------------------------------- WAV helpers
def read_wav(path):
    with wave.open(path, "rb") as w:
        fs = w.getframerate(); ch = w.getnchannels(); sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    elif sw == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw*8}-bit")
    a = a.reshape(-1, ch)
    return fs, a[:, 0]                     # left / mono channel


def write_wav(path, fs, y):
    y = np.clip(y, -1, 1)
    yi = np.int16(y * 32767)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(fs))
        w.writeframes(yi.tobytes())


def gen_sine(fs, f, dur, amp):
    n = int(fs * dur); t = np.arange(n) / fs
    return amp * np.sin(2 * np.pi * f * t)


def gen_sweep(fs, f0, f1, dur, amp):
    n = int(fs * dur); t = np.arange(n) / fs
    return amp * np.sin(2 * np.pi * (f0 * t + (f1 - f0) / (2 * dur) * t ** 2))


# --------------------------------------------------------------- DSP utilities
def spectrum(y, fs):
    n = len(y); w = np.hanning(n)
    Y = np.abs(np.fft.rfft(y * w)); Y /= max(Y.max(), 1e-12)
    f = np.fft.rfftfreq(n, 1 / fs)
    return f, 20 * np.log10(Y + 1e-12)


def align(a, b):
    """Shift b by whole samples to best match a (removes plugin latency)."""
    n = min(len(a), len(b)); a = a[:n]; b = b[:n]
    c = np.correlate(a - a.mean(), b - b.mean(), "full")
    lag = int(np.argmax(c) - (n - 1))
    if lag > 0:
        b = np.r_[np.zeros(lag), b[:n - lag]]
    elif lag < 0:
        b = np.r_[b[-lag:], np.zeros(-lag)]
    return a, b, lag


def metrics(a, b):
    n = min(len(a), len(b)); a = a[:n]; b = b[:n]
    d = a - b
    rms = lambda z: float(np.sqrt(np.mean(z ** 2)))
    ra, rd = rms(a), max(rms(d), 1e-15)
    return {
        "max_abs_diff": float(np.max(np.abs(d))),
        "rms_diff_db": 20 * np.log10(rd),
        "snr_db": 20 * np.log10(max(ra, 1e-15) / rd),
    }


def render_netlist(netlist_text, fs, output, pot_x, x):
    """Run a signal x through our own engine (== our VST)."""
    s = Session().load(netlist_text)
    out = output or s.default_output()
    wdf = s.build(fs, out, pot_x or None)
    return wdf.process(np.asarray(x, dtype=np.float64)), s


def parse_pots(text):
    """'XPlog1=0.7, XPlog2=0.8' -> {'XPlog1':0.7,'XPlog2':0.8}"""
    d = {}
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            d[k.strip()] = float(v)
        except ValueError:
            pass
    return d


# ===================================================================== Tk GUI
def launch():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    state = {"A": None, "B": None, "fsA": None, "fsB": None}

    root = tk.Tk()
    root.title("Fermenta — comparar dois pedais")
    root.geometry("1180x780")
    main = ttk.Frame(root, padding=6); main.pack(fill="both", expand=True)
    left = ttk.Frame(main); left.pack(side="left", fill="y")
    right = ttk.Frame(main); right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    fig = Figure(figsize=(7.4, 7.2), dpi=100)
    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    info = tk.Text(left, width=44, height=7, font=("Consolas", 9))
    def log(m):
        info.configure(state="normal"); info.insert("end", m + "\n")
        info.see("end"); info.configure(state="disabled")

    # ---------- test stimulus ----------
    sf = ttk.LabelFrame(left, text="1. Sinal de teste (input p/ os dois VSTs)", padding=6)
    sf.pack(fill="x")
    sig_kind = tk.StringVar(value="sweep")
    ttk.Radiobutton(sf, text="Seno", variable=sig_kind, value="sine").grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(sf, text="Sweep (varredura)", variable=sig_kind, value="sweep").grid(row=0, column=1, sticky="w")
    def _row(r, label, default):
        ttk.Label(sf, text=label).grid(row=r, column=0, sticky="w")
        e = ttk.Entry(sf, width=10); e.insert(0, default); e.grid(row=r, column=1, sticky="w")
        return e
    e_fs = _row(1, "fs (Hz)", "48000")
    e_amp = _row(2, "amplitude", "0.3")
    e_dur = _row(3, "duração (s)", "1.0")
    e_f0 = _row(4, "freq / f0 (Hz)", "50")
    e_f1 = _row(5, "f1 (sweep, Hz)", "5000")

    def gen_input():
        fs = int(float(e_fs.get())); amp = float(e_amp.get()); dur = float(e_dur.get())
        if sig_kind.get() == "sine":
            x = gen_sine(fs, float(e_f0.get()), dur, amp)
        else:
            x = gen_sweep(fs, float(e_f0.get()), float(e_f1.get()), dur, amp)
        p = filedialog.asksaveasfilename(defaultextension=".wav", initialfile="input_teste.wav",
                                         filetypes=[("WAV", "*.wav")])
        if not p:
            return
        write_wav(p, fs, x)
        log(f"input salvo: {os.path.basename(p)}  ({fs} Hz, {dur:g}s)")
        messagebox.showinfo("Input gerado",
                            "Agora no REAPER: passe este WAV pelo VST A e renderize (outA.wav), "
                            "e pelo VST B e renderize (outB.wav). Depois carregue os dois aqui.")
    ttk.Button(sf, text="Gerar input.wav", command=gen_input).grid(row=6, column=0, columnspan=2, sticky="ew", pady=4)

    # ---------- signal A ----------
    af = ttk.LabelFrame(left, text="2. Sinal A", padding=6); af.pack(fill="x", pady=(8, 0))
    labA = ttk.Entry(af, width=24); labA.insert(0, "A (JUCE)"); labA.grid(row=0, column=0, columnspan=2, sticky="w")
    def load_A():
        p = filedialog.askopenfilename(title="WAV do plugin A", filetypes=[("WAV", "*.wav")])
        if not p:
            return
        fs, y = read_wav(p); state["A"] = y; state["fsA"] = fs
        log(f"A carregado: {os.path.basename(p)}  ({fs} Hz, {len(y)} amostras)")
    ttk.Button(af, text="Carregar WAV…", command=load_A).grid(row=1, column=0, sticky="ew", pady=2)

    # render A from netlist (our engine)
    rn = ttk.LabelFrame(af, text="…ou renderizar A do netlist (nossa engine)", padding=4)
    rn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    nl_path = {"p": None}
    def pick_nl():
        p = filedialog.askopenfilename(title="Netlist", filetypes=[("Netlist", "*.txt *.net *.cir"), ("All", "*.*")])
        if p:
            nl_path["p"] = p; log(f"netlist: {os.path.basename(p)}")
    ttk.Button(rn, text="Netlist…", command=pick_nl).grid(row=0, column=0, sticky="w")
    ttk.Label(rn, text="output (nó/elem):").grid(row=1, column=0, sticky="w")
    e_out = ttk.Entry(rn, width=12); e_out.grid(row=1, column=1, sticky="w")
    ttk.Label(rn, text="pots (n=x,..):").grid(row=2, column=0, sticky="w")
    e_pots = ttk.Entry(rn, width=18); e_pots.grid(row=2, column=1, sticky="w")
    inwav = {"p": None}
    def pick_in():
        p = filedialog.askopenfilename(title="Input WAV p/ renderizar", filetypes=[("WAV", "*.wav")])
        if p:
            inwav["p"] = p; log(f"input p/ render: {os.path.basename(p)}")
    ttk.Button(rn, text="Input WAV…", command=pick_in).grid(row=3, column=0, sticky="w")
    def render_A():
        if not nl_path["p"] or not inwav["p"]:
            messagebox.showwarning("Faltando", "Escolha um netlist e um input WAV."); return
        fs, x = read_wav(inwav["p"])
        pot_x = parse_pots(e_pots.get())
        try:
            y, s = render_netlist(open(nl_path["p"]).read(), fs, e_out.get().strip(), pot_x, x)
        except Exception as e:
            messagebox.showerror("Erro no render", str(e)); return
        state["A"] = y; state["fsA"] = fs
        log(f"A renderizado pela engine ({fs} Hz, {len(y)} amostras)")
    ttk.Button(rn, text="Renderizar A", command=render_A).grid(row=3, column=1, sticky="ew")

    # ---------- signal B ----------
    bf = ttk.LabelFrame(left, text="3. Sinal B", padding=6); bf.pack(fill="x", pady=(8, 0))
    labB = ttk.Entry(bf, width=24); labB.insert(0, "B (VIOLA)"); labB.grid(row=0, column=0, columnspan=2, sticky="w")
    def load_B():
        p = filedialog.askopenfilename(title="WAV do plugin B", filetypes=[("WAV", "*.wav")])
        if not p:
            return
        fs, y = read_wav(p); state["B"] = y; state["fsB"] = fs
        log(f"B carregado: {os.path.basename(p)}  ({fs} Hz, {len(y)} amostras)")
    ttk.Button(bf, text="Carregar WAV…", command=load_B).grid(row=1, column=0, sticky="ew", pady=2)

    # ---------- options + compare ----------
    of = ttk.LabelFrame(left, text="4. Opções", padding=6); of.pack(fill="x", pady=(8, 0))
    do_align = tk.BooleanVar(value=True)
    do_norm = tk.BooleanVar(value=False)
    ttk.Checkbutton(of, text="Alinhar latência (cross-correlation)", variable=do_align).pack(anchor="w")
    ttk.Checkbutton(of, text="Normalizar amplitude antes de comparar", variable=do_norm).pack(anchor="w")

    def compare():
        A, B = state["A"], state["B"]
        if A is None or B is None:
            messagebox.showwarning("Faltando", "Carregue/renderize A e B primeiro."); return
        fs = state["fsA"] or state["fsB"] or 48000
        if state["fsA"] and state["fsB"] and state["fsA"] != state["fsB"]:
            log(f"AVISO: fs diferentes (A={state['fsA']}, B={state['fsB']}). Use o mesmo fs.")
        a = np.asarray(A, float); b = np.asarray(B, float)
        if do_norm.get():
            a = a / max(np.max(np.abs(a)), 1e-12); b = b / max(np.max(np.abs(b)), 1e-12)
        lag = 0
        if do_align.get():
            a, b, lag = align(a, b)
        else:
            n = min(len(a), len(b)); a, b = a[:n], b[:n]
        m = metrics(a, b)
        nameA = labA.get() or "A"; nameB = labB.get() or "B"

        fig.clf()
        t = np.arange(len(a)) / fs
        # zoom window: a few cycles / a slice in the middle
        w = slice(0, min(len(a), int(fs * 0.02)))
        ax1 = fig.add_subplot(311)
        ax1.plot(t[w] * 1e3, a[w], color="#1f3864", lw=1.3, label=nameA)
        ax1.plot(t[w] * 1e3, b[w], color="#c0392b", lw=1.3, ls="--", label=nameB)
        ax1.set_xlabel("tempo (ms)"); ax1.set_ylabel("amp"); ax1.grid(alpha=0.3)
        ax1.legend(fontsize=8); ax1.set_title("Forma de onda (sobreposta)")

        fA, mA = spectrum(a, fs); fB, mB = spectrum(b, fs)
        ax2 = fig.add_subplot(312)
        ax2.plot(fA, mA, color="#1f3864", lw=1.1, label=nameA)
        ax2.plot(fB, mB, color="#c0392b", lw=1.1, ls="--", label=nameB)
        ax2.set_xlim(0, min(fs / 2, 8000)); ax2.set_ylim(-90, 3)
        ax2.set_xlabel("frequência (Hz)"); ax2.set_ylabel("dB"); ax2.grid(alpha=0.3)
        ax2.legend(fontsize=8); ax2.set_title("Espectro de magnitude")

        ax3 = fig.add_subplot(313)
        ax3.plot(t * 1e3, a - b, color="#7d3c98", lw=0.8)
        ax3.set_xlabel("tempo (ms)"); ax3.set_ylabel("A − B"); ax3.grid(alpha=0.3)
        ax3.set_title(f"Diferença  |  max|Δ|={m['max_abs_diff']:.2e}   "
                      f"RMS Δ={m['rms_diff_db']:.1f} dB   SNR={m['snr_db']:.1f} dB   lag={lag}")
        fig.tight_layout(); canvas.draw()
        log(f"comparado: max|Δ|={m['max_abs_diff']:.3e}  SNR={m['snr_db']:.1f} dB  lag={lag}")

    ttk.Button(left, text="Comparar ▶", command=compare).pack(fill="x", pady=(8, 0))
    info.pack(fill="x", pady=(8, 0))
    info.configure(state="disabled")
    log("1) Gere um input.  2) Renderize nos dois VSTs no DAW.")
    log("3) Carregue A e B (ou renderize A do netlist) e Comparar.")
    root.mainloop()


if __name__ == "__main__":
    launch()
