"""
fermenta.gui -- a Tkinter front-end for the WDF pedal generator.

Run:  python -m fermenta.gui

Features
--------
* Load / paste an LTspice netlist (VIOLA conventions).
* Analyze: shows circuit class, ports, detected potentiometers, output choices,
  and a "supported components" help panel.
* Pick the output node/element and the sample rate.
* Name each pedal knob (pot labels) and move the pots with live sliders.
* Plot the response to a test sine (input vs output waveform + magnitude
  spectrum), or the transfer curve (V_out vs V_in) for nonlinear circuits.
* Generate the C++ DSP header, export a ready-to-build JUCE plugin project, or
  render a WAV file through the circuit.

The GUI is a thin layer over `Session` (below), which has no Tk dependency and
is unit-testable on its own.
"""
from __future__ import annotations
import os
import copy
import numpy as np

from .netlist import Netlist, pot_taper
from .solver import WDFCircuit
from .codegen import emit_cpp

def _read_text(path):
    """Read a netlist file tolerating LTspice's encoding (UTF-8 or ANSI/latin-1)."""
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


SUPPORTED = """SUPPORTED COMPONENTS (VIOLA netlist conventions)

  Vin / Iin   input source  (exactly ONE, named Vin or Iin; mono)
  V  / I      DC voltage / current source        (e.g.  V1 N001 0 9)
  R           resistor                            (R1 N001 N002 4.7k)
  C           capacitor                           (C1 N002 0 0.1u)
  L           inductor                            (L1 N002 N003 10m)
  XD          diode  (extended Shockley)          params: Is eta Vth Rs Rp
  XDser       diode string (n in series)          + param  n
  XDap        antiparallel diode pair             + param  n
  XPlin/XPlog/XPilog   potentiometer (lin/log/inv-log)   params: Rp x
  XOA         ideal op-amp  (neg pos out)

RULES
  * Keep LTspice node names (N001, N002, ...).  Ground is 0.
  * Exactly one input source named Vin (or Iin).
  * Unique component ids (no two 'R1').
  * Copy the ltspice_custom_components/ symbols next to your .asc in LTspice.
"""


class Session:
    """Non-GUI backend: parse a netlist, build the circuit, plot, generate C++."""

    def __init__(self):
        self.nl = None
        self.has_opamp = False
        self.pots = []          # list of (name, taper)  in first-seen order
        self.circuit_class = ""

    # -------------------------------------------------------------- analyze
    def load(self, text: str):
        self.nl = Netlist.parse(text)
        if not self.nl.elements:
            raise ValueError("No elements parsed. Is this an LTspice netlist?")
        if self.nl.input_id is None:
            raise ValueError("No input source found. Add a source named 'Vin' (or 'Iin').")
        self.has_opamp = any(e.type == "OA" for e in self.nl.elements)
        ndiode = sum(e.type in ("D", "Dser", "Dap") for e in self.nl.elements)
        base = ("lin" if ndiode == 0 else "one_non_lin" if ndiode == 1 else "non_lin")
        self.circuit_class = base + ("_opamp" if self.has_opamp else "")
        # pots in first-seen order
        seen = {}
        for e in self.nl.elements:
            if e.type == "R" and e.params and "pot" in e.params:
                nm = e.params["pot"]
                if nm not in seen:
                    seen[nm] = e.params.get("type", "Plin")
        self.pots = [(nm, t) for nm, t in seen.items()]
        return self

    def elements_table(self):
        rows = []
        for e in self.nl.elements:
            val = ""
            if e.value is not None:
                val = f"{e.value:g}"
            elif e.type in ("D", "Dser", "Dap"):
                val = "Is={Is:g} eta={eta:g}".format(**e.params)
            rows.append((e.id, e.type, "-".join(e.nodes[:3]), val))
        return rows

    def output_choices(self):
        """Op-amp circuits output a node (Nxxx); others probe an element id."""
        if self.has_opamp:
            return [n for n in self.nl.nodes if n != "0"]
        return [e.id for e in self.nl.elements if e.type != "OA"]

    def default_output(self):
        ch = self.output_choices()
        # prefer a capacitor-to-ground for non-op-amp, else last node/elem
        if not self.has_opamp:
            for e in self.nl.elements:
                if e.type == "C" and "0" in e.nodes:
                    return e.id
        return ch[-1] if ch else None

    # --------------------------------------------------------------- build
    def _netlist_with_pots(self, pot_x):
        if not pot_x:
            return self.nl
        nl2 = copy.deepcopy(self.nl)
        tmap = {"Plin": "lin", "Plog": "log", "Pilog": "ilog"}
        for el in nl2.elements:
            if el.type == "R" and el.params and "pot" in el.params:
                nm = el.params["pot"]
                if nm in pot_x:
                    pt = tmap.get(el.params.get("type", "Plin"), "lin")
                    role = "Ra" if el.id.endswith("_Ra") else "Rb"
                    el.value = pot_taper(pt, role, pot_x[nm], el.params["Rp"])
                    el.params = dict(el.params); el.params["x"] = pot_x[nm]
        return nl2

    def build(self, fs, output, pot_x=None):
        nl = self._netlist_with_pots(pot_x)
        if self.has_opamp:
            return WDFCircuit(nl, int(fs), output_node=output)
        return WDFCircuit(nl, int(fs), output_element_id=output)

    def sine_response(self, fs, freq, amp, output, pot_x=None, dur=0.05):
        wdf = self.build(fs, output, pot_x)
        n = int(fs * dur)
        t = np.arange(n) / fs
        x = amp * np.sin(2 * np.pi * freq * t)
        y = wdf.process(x)
        return t, x, y

    def transfer_curve(self, fs, amp, output, pot_x=None, npts=4000):
        wdf = self.build(fs, output, pot_x)
        ramp = np.linspace(-amp, amp, npts)
        return ramp, wdf.process(ramp)

    def spectrum(self, y, fs):
        n = len(y)
        w = np.hanning(n)
        Y = np.abs(np.fft.rfft(y * w))
        Y /= max(Y.max(), 1e-12)
        f = np.fft.rfftfreq(n, 1 / fs)
        return f, 20 * np.log10(Y + 1e-12)

    # ------------------------------------------------------------ generate
    def generate_cpp(self, path, name, fs, output, pot_labels=None, pot_x=None):
        wdf = self.build(fs, output, pot_x)
        code = emit_cpp(wdf, name, pot_labels=pot_labels)
        with open(path, "w") as f:
            f.write(code)
        return wdf


# ============================================================= Tk front-end
def launch():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    sess = Session()
    state = {"pot_names": [], "pot_labels": {}, "pot_x": {}}

    root = tk.Tk()
    root.title("Fermenta — WDF pedal generator")
    root.geometry("1180x760")

    main = ttk.Frame(root, padding=6); main.pack(fill="both", expand=True)
    left = ttk.Frame(main); left.pack(side="left", fill="y")
    right = ttk.Frame(main); right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    def log(msg):
        info.configure(state="normal"); info.insert("end", msg + "\n")
        info.see("end"); info.configure(state="disabled")

    # ---------- netlist ----------
    nlf = ttk.LabelFrame(left, text="1. Netlist (LTspice)", padding=6); nlf.pack(fill="x")
    txt = tk.Text(nlf, width=46, height=10, font=("Consolas", 9)); txt.pack(fill="x")
    brow = ttk.Frame(nlf); brow.pack(fill="x", pady=4)

    def do_load():
        p = filedialog.askopenfilename(filetypes=[("Netlist", "*.txt *.net *.cir"), ("All", "*.*")])
        if p:
            txt.delete("1.0", "end"); txt.insert("1.0", _read_text(p))
            log(f"Loaded {os.path.basename(p)}")

    ttk.Button(brow, text="Load .txt…", command=do_load).pack(side="left")
    ttk.Button(brow, text="Supported components",
               command=lambda: messagebox.showinfo("Supported components", SUPPORTED)).pack(side="right")

    # ---------- circuit info ----------
    cif = ttk.LabelFrame(left, text="2. Circuit", padding=6); cif.pack(fill="x", pady=6)
    lbl_class = ttk.Label(cif, text="class: —"); lbl_class.pack(anchor="w")
    row = ttk.Frame(cif); row.pack(fill="x", pady=2)
    ttk.Label(row, text="Output:").pack(side="left")
    out_cb = ttk.Combobox(row, width=14, state="readonly"); out_cb.pack(side="left", padx=4)
    ttk.Label(row, text="fs:").pack(side="left")
    fs_cb = ttk.Combobox(row, width=8, state="readonly",
                         values=["44100", "48000", "88200", "96000"]); fs_cb.set("48000")
    fs_cb.pack(side="left")

    # ---------- pots ----------
    potf = ttk.LabelFrame(left, text="3. Pedal knobs (potentiometers)", padding=6)
    potf.pack(fill="x", pady=6)
    pot_holder = ttk.Frame(potf); pot_holder.pack(fill="x")

    def rebuild_pot_rows():
        for w in pot_holder.winfo_children():
            w.destroy()
        state["pot_names"] = [nm for nm, _ in sess.pots]
        if not sess.pots:
            ttk.Label(pot_holder, text="(no potentiometers in this circuit)").pack(anchor="w")
            return
        for i, (nm, taper) in enumerate(sess.pots):
            fr = ttk.Frame(pot_holder); fr.pack(fill="x", pady=1)
            ttk.Label(fr, text=f"P{i+1}", width=3).pack(side="left")
            lab = tk.StringVar(value=state["pot_labels"].get(nm, ""))
            ent = ttk.Entry(fr, textvariable=lab, width=10)
            ent.pack(side="left")
            ent.bind("<KeyRelease>", lambda e, n=nm, v=lab: state["pot_labels"].__setitem__(n, v.get()))
            xv = tk.DoubleVar(value=state["pot_x"].get(nm, 0.5))
            vlbl = ttk.Label(fr, text=f"{xv.get():.2f}", width=5)

            def on_slide(val, n=nm, v=xv, l=vlbl):
                state["pot_x"][n] = float(val); l.configure(text=f"{float(val):.2f}")

            ttk.Scale(fr, from_=0, to=1, value=xv.get(), command=on_slide,
                      length=120).pack(side="left", padx=4)
            vlbl.pack(side="left")
            ttk.Label(fr, text=f"[{taper[1:]}]").pack(side="left")
            state["pot_labels"].setdefault(nm, "")
            state["pot_x"].setdefault(nm, 0.5)

    # ---------- test signal ----------
    tsf = ttk.LabelFrame(left, text="4. Test signal", padding=6); tsf.pack(fill="x", pady=6)
    r1 = ttk.Frame(tsf); r1.pack(fill="x")
    ttk.Label(r1, text="freq (Hz):").pack(side="left")
    freq_e = ttk.Entry(r1, width=8); freq_e.insert(0, "440"); freq_e.pack(side="left", padx=4)
    ttk.Label(r1, text="amp (V):").pack(side="left")
    amp_e = ttk.Entry(r1, width=8); amp_e.insert(0, "0.3"); amp_e.pack(side="left", padx=4)
    transfer_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(tsf, text="transfer curve (V_out vs V_in)", variable=transfer_var).pack(anchor="w")
    ttk.Button(tsf, text="Plot response", command=lambda: do_plot()).pack(fill="x", pady=3)

    # ---------- generate ----------
    gnf = ttk.LabelFrame(left, text="5. Generate", padding=6); gnf.pack(fill="x", pady=6)
    r2 = ttk.Frame(gnf); r2.pack(fill="x")
    ttk.Label(r2, text="name:").pack(side="left")
    name_e = ttk.Entry(r2, width=16); name_e.insert(0, "MyPedalDsp"); name_e.pack(side="left", padx=4)
    r3 = ttk.Frame(gnf); r3.pack(fill="x", pady=2)
    ttk.Label(r3, text="Channels:").pack(side="left")
    mode_var = tk.StringVar(value="mono")
    ttk.Radiobutton(r3, text="Mono (like VIOLA)", variable=mode_var, value="mono").pack(side="left")
    ttk.Radiobutton(r3, text="Stereo", variable=mode_var, value="stereo").pack(side="left")
    ttk.Button(gnf, text="Generate C++ header (.h)", command=lambda: do_gen_h()).pack(fill="x", pady=2)
    ttk.Button(gnf, text="Export JUCE plugin project…", command=lambda: do_export()).pack(fill="x", pady=2)
    ttk.Button(gnf, text="Export & Build VST3 (auto)…", command=lambda: do_export_build()).pack(fill="x", pady=2)
    ttk.Button(gnf, text="Render a WAV through the circuit…", command=lambda: do_render()).pack(fill="x", pady=2)

    # ---------- right: figure + log ----------
    fig = Figure(figsize=(6.4, 4.6), dpi=100)
    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    info = scrolledtext.ScrolledText(right, height=8, font=("Consolas", 9), state="disabled")
    info.pack(fill="x", pady=(6, 0))

    # ---------- actions ----------
    def do_analyze():
        try:
            sess.load(txt.get("1.0", "end"))
        except Exception as e:
            messagebox.showerror("Parse error", str(e)); return
        lbl_class.configure(text=f"class: {sess.circuit_class}   |   input: {sess.nl.input_id}"
                                 f"   |   elements: {len(sess.nl.elements)}")
        ch = sess.output_choices(); out_cb.configure(values=ch)
        out_cb.set(sess.default_output() or (ch[0] if ch else ""))
        state["pot_x"].clear(); state["pot_labels"].clear()
        rebuild_pot_rows()
        rows = sess.elements_table()
        log("── analyzed ──")
        log(f"  {sess.circuit_class}, {len(rows)} elements, "
            f"{len(sess.pots)} pot(s): {', '.join(n for n,_ in sess.pots) or '—'}")
        log("  output node/element: " + (sess.default_output() or "—"))

    ttk.Button(nlf, text="Analyze ▶", command=do_analyze).pack(fill="x")

    def _fs(): return int(fs_cb.get())
    def _out(): return out_cb.get()

    def do_plot():
        if sess.nl is None:
            messagebox.showwarning("No circuit", "Load a netlist and Analyze first."); return
        try:
            fs, out = _fs(), _out()
            amp = float(amp_e.get())
            fig.clf()
            if transfer_var.get():
                vin, vout = sess.transfer_curve(fs, amp, out, state["pot_x"])
                ax = fig.add_subplot(111)
                ax.plot(vin, vin, ":", color="#bbb", lw=1, label="unity")
                ax.plot(vin, vout, color="#c0392b", lw=2, label="V_out")
                ax.set_xlabel("V_in (V)"); ax.set_ylabel("V_out (V)")
                ax.set_title("Transfer characteristic"); ax.grid(alpha=0.3); ax.legend()
            else:
                freq = float(freq_e.get())
                t, x, y = sess.sine_response(fs, freq, amp, out, state["pot_x"])
                ax1 = fig.add_subplot(211)
                per = int(fs / max(freq, 1)); win = slice(0, min(len(t), 6 * per))
                ax1.plot(t[win]*1e3, x[win], color="#999", lw=1, label="input")
                ax1.plot(t[win]*1e3, y[win], color="#c0392b", lw=1.6, label="output")
                ax1.set_xlabel("time (ms)"); ax1.set_ylabel("V"); ax1.grid(alpha=0.3); ax1.legend(fontsize=8)
                ax1.set_title(f"{sess.circuit_class}  @  {freq:g} Hz, {amp:g} V")
                f, mag = sess.spectrum(y, fs)
                ax2 = fig.add_subplot(212)
                ax2.plot(f, mag, color="#1f3864", lw=1.2)
                ax2.set_xlim(0, min(fs/2, 6000)); ax2.set_ylim(-90, 3)
                ax2.set_xlabel("frequency (Hz)"); ax2.set_ylabel("dB"); ax2.grid(alpha=0.3)
            fig.tight_layout(); canvas.draw()
            log("plotted.")
        except Exception as e:
            messagebox.showerror("Plot error", str(e))

    def _labels_list():
        # pot labels in P-number order (as VIOLA expects)
        return [state["pot_labels"].get(nm, "") for nm, _ in sess.pots]

    def do_gen_h():
        if sess.nl is None:
            messagebox.showwarning("No circuit", "Analyze a netlist first."); return
        name = name_e.get().strip() or "MyPedalDsp"
        p = filedialog.asksaveasfilename(defaultextension=".h", initialfile=name + ".h",
                                         filetypes=[("C++ header", "*.h")])
        if not p:
            return
        try:
            sess.generate_cpp(p, name, _fs(), _out(),
                              pot_labels=_labels_list() or None, pot_x=state["pot_x"])
            log(f"wrote {p}")
            messagebox.showinfo("Done", f"Generated {os.path.basename(p)}")
        except Exception as e:
            messagebox.showerror("Codegen error", str(e))

    def do_export():
        if sess.nl is None:
            messagebox.showwarning("No circuit", "Analyze a netlist first."); return
        folder = filedialog.askdirectory(title="Choose an empty folder for the plugin project")
        if not folder:
            return
        try:
            name = name_e.get().strip() or "MyPedalDsp"
            _export_project(sess, folder, name, _fs(), _out(), _labels_list(),
                            state["pot_x"], stereo=(mode_var.get() == "stereo"))
            log(f"exported plugin project to {folder}")
            messagebox.showinfo("Exported",
                                "Plugin project written.\nBuild with:\n  cmake -B build\n  cmake --build build --config Release")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def do_export_build():
        if sess.nl is None:
            messagebox.showwarning("No circuit", "Analyze a netlist first."); return
        folder = filedialog.askdirectory(title="Choose an empty folder for the plugin project")
        if not folder:
            return
        name = name_e.get().strip() or "MyPedalDsp"
        try:
            _export_project(sess, folder, name, _fs(), _out(), _labels_list(),
                            state["pot_x"], stereo=(mode_var.get() == "stereo"))
        except Exception as e:
            messagebox.showerror("Export error", str(e)); return
        log(f"exported plugin project to {folder}")
        log("Building VST3 with CMake (downloads JUCE the first time; can take several minutes)...")

        import threading, subprocess, shutil
        def _run(cmd):
            proc = subprocess.Popen(cmd, cwd=folder, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                root.after(0, log, line.rstrip())
            proc.wait()
            return proc.returncode

        def worker():
            try:
                # JUCE needs MSVC, not MinGW: force the Visual Studio generator.
                # Wipe any stale build/ (e.g. a previous MinGW/Ninja cache) first.
                shutil.rmtree(os.path.join(folder, "build"), ignore_errors=True)
                cfg = _run(["cmake", "-B", "build",
                            "-G", "Visual Studio 17 2022", "-A", "x64"])
                if cfg != 0:
                    root.after(0, log, "[cmake configure failed - see log above]"); return
                if _run(["cmake", "--build", "build", "--config", "Release"]) != 0:
                    root.after(0, log, "[build failed - see log above]"); return
                root.after(0, log, "BUILD OK. The .vst3 is under:  " + folder +
                           "\\build\\" + name + "_artefacts\\Release\\VST3")
                root.after(0, lambda: messagebox.showinfo("Built",
                    "VST3 built!\nFind it under:\n" + folder + "\\build\\...\\VST3\n\n"
                    "Copy it to  C:\\Program Files\\Common Files\\VST3  and rescan your DAW."))
            except FileNotFoundError:
                root.after(0, lambda: messagebox.showerror("CMake not found",
                    "CMake isn't on your PATH.\nInstall CMake + Visual Studio (Desktop C++),\n"
                    "or open the exported folder and run build.bat manually."))
            except Exception as e:
                root.after(0, log, "build error: " + str(e))

        threading.Thread(target=worker, daemon=True).start()

    def do_render():
        if sess.nl is None:
            messagebox.showwarning("No circuit", "Analyze a netlist first."); return
        inp = filedialog.askopenfilename(title="Input WAV", filetypes=[("WAV", "*.wav")])
        if not inp:
            return
        outp = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV", "*.wav")])
        if not outp:
            return
        try:
            import wave
            with wave.open(inp, "rb") as w:
                fs = w.getframerate(); ch = w.getnchannels()
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            xin = raw.astype(np.float64).reshape(-1, ch)[:, 0] / 32768.0
            wdf = sess.build(fs, _out(), state["pot_x"])
            y = wdf.process(xin)
            pk = np.max(np.abs(y)); y = y / pk if pk > 1 else y
            yi = np.int16(np.clip(y, -1, 1) * 32767)
            with wave.open(outp, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs); w.writeframes(yi.tobytes())
            log(f"rendered {os.path.basename(inp)} -> {os.path.basename(outp)} ({fs} Hz)")
            messagebox.showinfo("Rendered", f"Wrote {os.path.basename(outp)}")
        except Exception as e:
            messagebox.showerror("Render error", str(e))

    log("Load or paste a netlist, then click Analyze.")
    root.mainloop()


def _export_project(sess, folder, name, fs, output, labels, pot_x=None, stereo=False):
    """Write <name>.h + a JUCE project (copied templates with the include swapped
    and the mono/stereo mode set)."""
    import sys as _sys
    if getattr(_sys, "frozen", False):
        cpp_tpl = os.path.join(_sys._MEIPASS, "cpp_templates")   # bundled in the .exe
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        cpp_tpl = os.path.abspath(os.path.join(here, "..", "..", "cpp"))
    sess.generate_cpp(os.path.join(folder, name + ".h"), name, fs, output,
                      pot_labels=labels or None, pot_x=pot_x)
    import re as _re
    # 4-char JUCE plugin code from the pedal name (1 uppercase + 3 lowercase)
    alnum = _re.sub(r"[^A-Za-z0-9]", "", name) or "Pdl1"
    code = (alnum + "Dsp1")[:4]
    code = code[0].upper() + code[1:].lower()
    for fn in ("CMakeLists.txt", "PluginProcessor.h", "PluginProcessor.cpp",
               "wdf_render.cpp", "build.bat", "README.md"):
        src = os.path.join(cpp_tpl, fn)
        if not os.path.exists(src):
            continue
        s = open(src).read()
        s = s.replace('#include "MxrDsp.h"', f'#include "{name}.h"')
        s = s.replace("using Circuit = fermenta::MxrDsp;", f"using Circuit = fermenta::{name};")
        s = s.replace("using DspType = fermenta::MxrDsp;", f"using DspType = fermenta::{name};")
        # give each pedal its own CMake target / product / plugin name
        s = s.replace("WdfViolaMXR", name)          # target, project, *_artefacts
        s = s.replace('"fermenta MXR"', f'"{name}"')  # PRODUCT_NAME + build.bat paths
        s = s.replace("fermenta MXR", name)          # any remaining refs (exe/vst3 names)
        s = _re.sub(r"(PLUGIN_CODE\s+)\w+", r"\g<1>" + code, s)
        if fn == "PluginProcessor.h":
            s = s.replace("  #define WDFVIOLA_STEREO 0        // default: mono, identical to VIOLA",
                          f"  #define WDFVIOLA_STEREO {1 if stereo else 0}")
        open(os.path.join(folder, fn), "w").write(s)


if __name__ == "__main__":
    launch()
