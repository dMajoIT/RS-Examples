"""
Signal Integrity Automator - GUI
R&S RTP Oscilloscope Automation Tool
"""

import os
import sys


def fix_tcl_path():
    if sys.platform == 'win32':
        base_python = sys.base_prefix
        tcl_lib = os.path.join(base_python, 'tcl')
        if os.path.exists(tcl_lib):
            os.environ['TCL_LIBRARY'] = os.path.join(tcl_lib, 'tcl8.6')
            os.environ['TK_LIBRARY']  = os.path.join(tcl_lib, 'tk8.6')
        dll_dir = os.path.join(base_python, 'DLLs')
        if os.path.exists(dll_dir):
            os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')


fix_tcl_path()

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from datetime import datetime

import PAM_AE_SignalIntegrity_Backend as backend

VALID_TARGETS = {0: [1, 2, 3], 1: [2, 3], 2: [3]}


class SignalIntegrityAutomator(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Signal Integrity Automator - Automotive Ethernet")
        self.geometry("1200x780")
        self.configure(bg='#f0f0f0')

        self.instr = None
        self.is_connected = False
        self.signal_configured = False
        self.last_operation = None  # 'signal' | 'sw_eye' | 'hw_eye' | 'jitter'

        self.create_header()
        self.create_main_container()
        self.create_tabs()

        self.log_message("Signal Integrity Automator Ready", "success")
        self.log_message("Configure settings and connect to begin", "info")

    # =========================================================================
    # LAYOUT
    # =========================================================================
    def create_header(self):
        header = tk.Frame(self, bg='#003366', height=60)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        tk.Label(header, text="🔬 Signal Integrity Automator",
                 font=('Segoe UI', 16, 'bold'), bg='#003366', fg='white').pack(pady=(10, 0))
        tk.Label(header, text="Automotive Ethernet PAM-N Analysis | R&S RTP Oscilloscope",
                 font=('Segoe UI', 9), bg='#003366', fg='#b3d9ff').pack()

    def create_main_container(self):
        self.main_container = tk.Frame(self, bg='#f0f0f0')
        self.main_container.pack(fill='both', expand=True, padx=8, pady=8)

        self.left_panel = tk.Frame(self.main_container, bg='white', relief='solid', borderwidth=1)
        self.left_panel.pack(side='left', fill='both', expand=True, padx=(0, 4))

        self.right_panel = tk.Frame(self.main_container, bg='white', relief='solid',
                                    borderwidth=1, width=380)
        self.right_panel.pack(side='right', fill='both', padx=(4, 0))
        self.right_panel.pack_propagate(False)

        self.create_log_panel()

    def create_log_panel(self):
        tk.Label(self.right_panel, text="📋 Activity Log",
                 font=('Segoe UI', 9, 'bold'), bg='white', fg='#003366').pack(
            pady=(8, 6), padx=8, anchor='w')

        self.log_text = scrolledtext.ScrolledText(
            self.right_panel, wrap=tk.WORD, width=45, height=40,
            font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4', insertbackground='white')
        self.log_text.pack(fill='both', expand=True, padx=8, pady=(0, 6))

        self.log_text.tag_config('timestamp', foreground='#858585')
        self.log_text.tag_config('info',    foreground='#4ec9b0')
        self.log_text.tag_config('success', foreground='#4ec9b0', font=('Consolas', 9, 'bold'))
        self.log_text.tag_config('warning', foreground='#dcdcaa')
        self.log_text.tag_config('error',   foreground='#f48771')

        tk.Button(self.right_panel, text="🗑 Clear", command=self.clear_log,
                  bg='#dc3545', fg='white', font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(pady=(0, 8), padx=8)

    def create_tabs(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='white', borderwidth=0)
        style.configure('TNotebook.Tab', padding=[15, 8], font=('Segoe UI', 9, 'bold'))
        style.map('TNotebook.Tab',
                  background=[('selected', '#007bff'), ('!selected', '#f8f9fa')],
                  foreground=[('selected', 'white'), ('!selected', '#495057')])

        self.notebook = ttk.Notebook(self.left_panel)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.notebook.add(self.create_signal_config_tab(), text="Signal Config")
        self.notebook.add(self.create_eye_tab(),           text="Eye Diagram")
        self.notebook.add(self.create_jitter_tab(),        text="Jitter Analysis")

    # =========================================================================
    # SIGNAL CONFIG TAB (includes instrument connection at top)
    # =========================================================================
    def create_signal_config_tab(self):
        tab = tk.Frame(self.notebook, bg='white')
        main = tk.Frame(tab, bg='white')
        main.pack(fill='both', expand=True, padx=12, pady=12)

        # ── Instrument Connection ─────────────────────────────────────────────
        conn_sec = tk.Frame(main, bg='#f8f9fa', relief='solid', borderwidth=1)
        conn_sec.pack(fill='x', pady=(0, 12))
        tk.Label(conn_sec, text="🔌 Instrument Connection",
                 font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', fg='#003366').pack(
            anchor='w', padx=12, pady=(10, 8))

        conn_content = tk.Frame(conn_sec, bg='#f8f9fa')
        conn_content.pack(fill='x', padx=12, pady=(0, 10))

        ip_row = tk.Frame(conn_content, bg='#f8f9fa')
        ip_row.pack(fill='x', pady=(0, 8))
        tk.Label(ip_row, text="IP Address:", bg='#f8f9fa',
                 font=('Segoe UI', 9, 'bold'), width=10, anchor='w').pack(side='left')
        self.ip_entry = tk.Entry(ip_row, font=('Segoe UI', 10))
        self.ip_entry.insert(0, "10.103.34.23")
        self.ip_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))

        self.status_label = tk.Label(
            conn_content, text="● Disconnected", font=('Segoe UI', 9, 'bold'),
            bg='#f8d7da', fg='#721c24', relief='solid', borderwidth=1, pady=5)
        self.status_label.pack(fill='x', pady=(0, 8))

        btn_row = tk.Frame(conn_content, bg='#f8f9fa')
        btn_row.pack(fill='x')
        self.connect_btn = tk.Button(
            btn_row, text="Connect", command=self.connect,
            bg='#28a745', fg='white', font=('Segoe UI', 9, 'bold'),
            relief='flat', cursor='hand2', height=2)
        self.connect_btn.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.disconnect_btn = tk.Button(
            btn_row, text="Disconnect", command=self.disconnect,
            bg='#dc3545', fg='white', font=('Segoe UI', 9, 'bold'),
            relief='flat', cursor='hand2', height=2, state=tk.DISABLED)
        self.disconnect_btn.pack(side='left', fill='x', expand=True, padx=(4, 0))

        # ── Channel Configuration ─────────────────────────────────────────────
        config_sec = tk.Frame(main, bg='#f8f9fa', relief='solid', borderwidth=1)
        config_sec.pack(fill='x', pady=(0, 12))
        tk.Label(config_sec, text="⚙️ Channel Configuration",
                 font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', fg='#003366').pack(
            anchor='w', padx=12, pady=(10, 8))

        content = tk.Frame(config_sec, bg='#f8f9fa')
        content.pack(fill='x', padx=12, pady=(0, 10))

        tk.Label(content, text="Channel Pair (DIFF1 = A - B):",
                 bg='#f8f9fa', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
        ch_frame = tk.Frame(content, bg='#f8f9fa')
        ch_frame.pack(fill='x', pady=(0, 8))
        self.channel_pair = tk.StringVar(value="24")
        tk.Radiobutton(ch_frame, text="Channels 1+3", variable=self.channel_pair,
                       value="13", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(0, 10))
        tk.Radiobutton(ch_frame, text="Channels 2+4", variable=self.channel_pair,
                       value="24", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left')

        tk.Label(content, text="Automotive Ethernet Standard:",
                 bg='#f8f9fa', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(8, 2))
        self.technology = tk.StringVar(value="5")
        tech_frame = tk.Frame(content, bg='#f8f9fa')
        tech_frame.pack(fill='x', pady=(0, 8))
        for val, txt in [("2.5", "2.5 GBASE-T1"), ("5", "5 GBASE-T1"), ("10", "10 GBASE-T1")]:
            tk.Radiobutton(tech_frame, text=txt, variable=self.technology, value=val,
                           bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(0, 8))

        scale_sec = tk.Frame(main, bg='#f8f9fa', relief='solid', borderwidth=1)
        scale_sec.pack(fill='x', pady=(0, 12))
        tk.Label(scale_sec, text="📏 Scaling Configuration",
                 font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', fg='#003366').pack(
            anchor='w', padx=12, pady=(10, 8))

        sc = tk.Frame(scale_sec, bg='#f8f9fa')
        sc.pack(fill='x', padx=12, pady=(0, 10))
        row = tk.Frame(sc, bg='#f8f9fa')
        row.pack(fill='x')

        vf = tk.Frame(row, bg='#f8f9fa')
        vf.pack(side='left', fill='x', expand=True, padx=(0, 5))
        tk.Label(vf, text="Vertical (V/div):", bg='#f8f9fa',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.v_scale = tk.Entry(vf, font=('Segoe UI', 10))
        self.v_scale.insert(0, "0.1")
        self.v_scale.pack(fill='x')

        hf = tk.Frame(row, bg='#f8f9fa')
        hf.pack(side='right', fill='x', expand=True, padx=(5, 0))
        tk.Label(hf, text="Horizontal (s/div):", bg='#f8f9fa',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.h_scale = tk.Entry(hf, font=('Segoe UI', 10))
        self.h_scale.insert(0, "10e-6")
        self.h_scale.pack(fill='x')

        sig_sec = tk.Frame(main, bg='#f8f9fa', relief='solid', borderwidth=1)
        sig_sec.pack(fill='x', pady=(0, 12))
        tk.Label(sig_sec, text="⚡ Signal Configuration",
                 font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', fg='#003366').pack(
            anchor='w', padx=12, pady=(10, 8))

        sig_c = tk.Frame(sig_sec, bg='#f8f9fa')
        sig_c.pack(fill='x', padx=12, pady=(0, 10))
        tk.Label(sig_c,
                 text="Configures: Factory preset • Channels • DIFF1 signal • "
                      "Scaling • Trigger on DIFF1 • Technology preset",
                 bg='#e7f3ff', fg='#004085', font=('Segoe UI', 9), relief='solid',
                 borderwidth=1, padx=12, pady=10, justify='left',
                 wraplength=700).pack(fill='x', pady=(0, 10))

        self.signal_config_btn = tk.Button(
            sig_c, text="⚡ Run Signal Configuration", command=self.run_signal_config,
            bg='#007bff', fg='white', font=('Segoe UI', 11, 'bold'),
            relief='flat', cursor='hand2', height=2, state='disabled')
        self.signal_config_btn.pack(fill='x')

        return tab

    # =========================================================================
    # EYE DIAGRAM TAB
    # =========================================================================
    def create_eye_tab(self):
        tab = tk.Frame(self.notebook, bg='white')

        tk.Label(tab, text="Eye Diagram Analysis", font=('Segoe UI', 12, 'bold'),
                 bg='white', fg='#003366').pack(pady=(15, 8))

        type_frame = tk.LabelFrame(tab, text="Eye Diagram Type",
                                   font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                   padx=15, pady=10)
        type_frame.pack(fill='x', padx=20, pady=(0, 6))

        self.eye_type = tk.StringVar(value="sw")
        tk.Radiobutton(type_frame, text="Software CDR Eye", variable=self.eye_type,
                       value="sw", bg='white', font=('Segoe UI', 9),
                       command=self.update_eye_options).pack(anchor='w', pady=2)
        tk.Radiobutton(type_frame, text="Hardware CDR Eye", variable=self.eye_type,
                       value="hw", bg='white', font=('Segoe UI', 9),
                       command=self.update_eye_options).pack(anchor='w', pady=2)

        # Fixed container — both frames grid here, buttons below never move
        self.options_container = tk.Frame(tab, bg='white')
        self.options_container.pack(fill='x', padx=20, pady=(0, 6))
        self.options_container.grid_columnconfigure(0, weight=1)

        # ── SW CDR options ────────────────────────────────────────────────────
        self.sw_frame = tk.LabelFrame(self.options_container, text="SW CDR Options",
                                      font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                      padx=15, pady=10)
        self.sw_frame.grid(row=0, column=0, sticky='ew')

        mode_row = tk.Frame(self.sw_frame, bg='white')
        mode_row.pack(fill='x', pady=4)
        tk.Label(mode_row, text="Eye Mode:", font=('Segoe UI', 9),
                 bg='white', width=12, anchor='w').pack(side='left')
        self.eye_mode = tk.StringVar(value="whole")
        for val, txt in [("whole", "Whole"), ("specific", "Specific"), ("selected", "Selected")]:
            tk.Radiobutton(mode_row, text=txt, variable=self.eye_mode, value=val,
                           bg='white', font=('Segoe UI', 9),
                           command=self.update_eye_mode).pack(side='left', padx=5)

        self.specific_frame = tk.Frame(self.sw_frame, bg='white')
        tk.Label(self.specific_frame, text="Specific Eye:", font=('Segoe UI', 9),
                 bg='white', width=12, anchor='w').pack(side='left')
        self.specific_eye = tk.StringVar(value="1-2")
        for val in ["0-1", "1-2", "2-3"]:
            tk.Radiobutton(self.specific_frame, text=val, variable=self.specific_eye,
                           value=val, bg='white', font=('Segoe UI', 9)).pack(side='left', padx=5)

        self.selected_frame = tk.Frame(self.sw_frame, bg='white')
        tk.Label(self.selected_frame, text="Base Level:", font=('Segoe UI', 9),
                 bg='white', width=12, anchor='w').pack(side='left')
        self.base_level = tk.StringVar(value="0")
        self.base_combo = ttk.Combobox(self.selected_frame, textvariable=self.base_level,
                                       values=["0", "1", "2"], width=6,
                                       state='readonly', font=('Segoe UI', 9))
        self.base_combo.pack(side='left', padx=(0, 10))
        self.base_combo.bind('<<ComboboxSelected>>', self._on_base_changed)

        tk.Label(self.selected_frame, text="Target Level:", font=('Segoe UI', 9),
                 bg='white').pack(side='left')
        self.target_level = tk.StringVar(value="1")
        self.target_combo = ttk.Combobox(self.selected_frame, textvariable=self.target_level,
                                         values=["1", "2", "3"], width=6,
                                         state='readonly', font=('Segoe UI', 9))
        self.target_combo.pack(side='left', padx=5)
        self._refresh_target_options()

        self.enable_meas = tk.BooleanVar(value=False)
        tk.Checkbutton(self.sw_frame,
                       text="Enable Eye Measurements (Height / Width / Amplitude)",
                       variable=self.enable_meas, bg='white',
                       font=('Segoe UI', 9)).pack(anchor='w', pady=(8, 0))

        # ── HW CDR options ────────────────────────────────────────────────────
        self.hw_frame = tk.LabelFrame(self.options_container, text="HW CDR Options",
                                      font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                      padx=15, pady=10)
        self.hw_frame.grid(row=0, column=0, sticky='ew')
        self.hw_frame.grid_remove()  # hidden initially

        self.enable_zoom = tk.BooleanVar(value=False)  # default OFF
        tk.Checkbutton(self.hw_frame, text="Enable Zoom Window",
                       variable=self.enable_zoom, bg='white', font=('Segoe UI', 9),
                       command=self._update_zoom_options).pack(anchor='w', pady=(0, 6))

        self.zoom_settings_frame = tk.Frame(self.hw_frame, bg='white')

        xstart_row = tk.Frame(self.zoom_settings_frame, bg='white')
        xstart_row.pack(fill='x', pady=4)
        tk.Label(xstart_row, text="Zoom Start (ns):", font=('Segoe UI', 9),
                 bg='white', width=15, anchor='w').pack(side='left')
        self.xstart = tk.Entry(xstart_row, font=('Segoe UI', 9), width=12)
        self.xstart.insert(0, "60")
        self.xstart.pack(side='left', padx=5)

        xstop_row = tk.Frame(self.zoom_settings_frame, bg='white')
        xstop_row.pack(fill='x', pady=4)
        tk.Label(xstop_row, text="Zoom Stop (ns):", font=('Segoe UI', 9),
                 bg='white', width=15, anchor='w').pack(side='left')
        self.xstop = tk.Entry(xstop_row, font=('Segoe UI', 9), width=12)
        self.xstop.insert(0, "62")
        self.xstop.pack(side='left', padx=5)

        self.hw_10g_warning = tk.Label(
            self.hw_frame,
            text="⚠️  10GBASE-T1 selected: symbol rate ~3.8 GBd — "
                 "HW CDR may not lock. Consider using SW CDR instead.",
            bg='#fff3cd', fg='#856404', font=('Segoe UI', 8, 'italic'),
            relief='solid', borderwidth=1, padx=8, pady=6,
            wraplength=480, justify='left')

        # ── Action buttons — always fixed position ────────────────────────────
        btn_frame = tk.Frame(tab, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(btn_frame, text="🔄 Preset + Config",
                  command=self.preset_and_configure_eye,
                  bg='#6c757d', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2', height=2).pack(
            side='left', fill='x', expand=True, padx=(0, 4))

        tk.Button(btn_frame, text="👁️ Configure Eye",
                  command=self.run_eye_config,
                  bg='#17a2b8', fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', cursor='hand2', height=2).pack(
            side='left', fill='x', expand=True, padx=(4, 0))

        self._update_zoom_options()  # hide zoom fields on startup
        self.technology.trace_add('write', lambda *_: self._update_hw_cdr_warning())

        return tab

    def _on_base_changed(self, _event=None):
        self._refresh_target_options()

    def _refresh_target_options(self):
        base  = int(self.base_level.get())
        valid = [str(t) for t in VALID_TARGETS[base]]
        self.target_combo.config(values=valid)
        self.target_level.set(valid[0])

    def _update_hw_cdr_warning(self):
        if self.eye_type.get() == "hw" and self.technology.get() == "10":
            self.hw_10g_warning.pack(fill='x', pady=(8, 0))
        else:
            self.hw_10g_warning.pack_forget()

    def _update_zoom_options(self):
        if self.enable_zoom.get():
            self.zoom_settings_frame.pack(fill='x')
        else:
            self.zoom_settings_frame.pack_forget()

    def update_eye_options(self):
        if self.eye_type.get() == "sw":
            self.hw_frame.grid_remove()
            self.sw_frame.grid()
        else:
            self.sw_frame.grid_remove()
            self.hw_frame.grid()
        self._update_hw_cdr_warning()

    def update_eye_mode(self):
        mode = self.eye_mode.get()
        self.specific_frame.pack_forget()
        self.selected_frame.pack_forget()
        if mode == "specific":
            self.specific_frame.pack(fill='x', pady=4)
        elif mode == "selected":
            self.selected_frame.pack(fill='x', pady=4)

    # =========================================================================
    # JITTER TAB
    # =========================================================================
    def create_jitter_tab(self):
        tab = tk.Frame(self.notebook, bg='white')

        tk.Label(tab, text="Jitter Analysis", font=('Segoe UI', 12, 'bold'),
                 bg='white', fg='#003366').pack(pady=(15, 8))

        type_frame = tk.LabelFrame(tab, text="Jitter Analysis Type",
                                   font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                   padx=15, pady=10)
        type_frame.pack(fill='x', padx=20, pady=(0, 8))

        self.jitter_type = tk.StringVar(value="quick")
        tk.Radiobutton(type_frame, text="Quick Start (Automatic — all components)",
                       variable=self.jitter_type, value="quick", bg='white',
                       font=('Segoe UI', 9), command=self.update_jitter_options).pack(anchor='w', pady=3)
        tk.Radiobutton(type_frame, text="Manual Components (select specific)",
                       variable=self.jitter_type, value="manual", bg='white',
                       font=('Segoe UI', 9), command=self.update_jitter_options).pack(anchor='w', pady=3)
        tk.Radiobutton(type_frame, text="PAM-N Results (transition-dependent)",
                       variable=self.jitter_type, value="pamn", bg='white',
                       font=('Segoe UI', 9), command=self.update_jitter_options).pack(anchor='w', pady=3)

        # Fixed container — option frames grid here so buttons below never move
        self.jitter_options_container = tk.Frame(tab, bg='white')
        self.jitter_options_container.pack(fill='x', padx=20, pady=(0, 6))
        self.jitter_options_container.grid_columnconfigure(0, weight=1)

        # ── Manual components frame ───────────────────────────────────────────
        self.manual_frame = tk.LabelFrame(self.jitter_options_container,
                                          text="Select Components",
                                          font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                          padx=15, pady=10)
        self.jitter_components = {}
        components = [
            ('DDJ', 'Data-Dependent Jitter'), ('RJ',  'Random Jitter'),
            ('TJ',  'Total Jitter'),           ('DJ',  'Deterministic Jitter'),
            ('PJ',  'Periodic Jitter'),         ('DCD', 'Duty Cycle Distortion'),
        ]
        for i, (comp, desc) in enumerate(components):
            var = tk.BooleanVar(value=(comp == 'DDJ'))
            self.jitter_components[comp] = var
            tk.Checkbutton(self.manual_frame, text=f"{comp} — {desc}",
                           variable=var, bg='white', font=('Segoe UI', 9)).grid(
                row=i // 2, column=i % 2, sticky='w', padx=10, pady=3)

        # ── PAM-N frame ───────────────────────────────────────────────────────
        self.pamn_frame = tk.LabelFrame(self.jitter_options_container,
                                        text="PAM-N Configuration",
                                        font=('Segoe UI', 10, 'bold'), bg='white', fg='#003366',
                                        padx=15, pady=10)

        comp_row = tk.Frame(self.pamn_frame, bg='white')
        comp_row.pack(fill='x', pady=5)
        tk.Label(comp_row, text="Component:", font=('Segoe UI', 9), bg='white',
                 width=12, anchor='w').pack(side='left')
        self.pamn_component = tk.StringVar(value="DDJ")
        ttk.Combobox(comp_row, textvariable=self.pamn_component,
                     values=['DDJ', 'RJ', 'TJ', 'DJ', 'PJ', 'DCD'],
                     width=10, state='readonly', font=('Segoe UI', 9)).pack(side='left', padx=5)

        tk.Label(self.pamn_frame, text="Transitions:", font=('Segoe UI', 9),
                 bg='white').pack(anchor='w', pady=(10, 5))

        trans_frame = tk.Frame(self.pamn_frame, bg='white')
        trans_frame.pack(fill='x')
        self.transitions = {}
        for i, (label, base, target) in enumerate(
                [('0→1', 0, 1), ('0→2', 0, 2), ('0→3', 0, 3),
                 ('1→2', 1, 2), ('1→3', 1, 3), ('2→3', 2, 3)]):
            var = tk.BooleanVar(value=False)
            self.transitions[(base, target)] = var
            tk.Checkbutton(trans_frame, text=label, variable=var,
                           bg='white', font=('Segoe UI', 9)).grid(
                row=i // 3, column=i % 3, sticky='w', padx=10, pady=3)

        sel_row = tk.Frame(self.pamn_frame, bg='white')
        sel_row.pack(pady=5)
        tk.Button(sel_row, text="Select All",
                  command=lambda: [v.set(True) for v in self.transitions.values()],
                  bg='#28a745', fg='white', font=('Segoe UI', 8),
                  relief='flat', padx=10, pady=4).pack(side='left', padx=5)
        tk.Button(sel_row, text="Clear All",
                  command=lambda: [v.set(False) for v in self.transitions.values()],
                  bg='#6c757d', fg='white', font=('Segoe UI', 8),
                  relief='flat', padx=10, pady=4).pack(side='left', padx=5)

        btn_frame = tk.Frame(tab, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=12)

        tk.Button(btn_frame, text="🔄 Preset + Config",
                  command=self.preset_and_configure_jitter,
                  bg='#6c757d', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2', height=2).pack(
            side='left', fill='x', expand=True, padx=(0, 4))

        tk.Button(btn_frame, text="📊 Configure Jitter",
                  command=self.run_jitter_config,
                  bg='#ffc107', fg='black', font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2', height=2).pack(
            side='left', fill='x', expand=True, padx=(4, 0))

        return tab

    def update_jitter_options(self):
        self.manual_frame.grid_remove()
        self.pamn_frame.grid_remove()
        jt = self.jitter_type.get()
        if jt == "manual":
            self.manual_frame.grid(row=0, column=0, sticky='ew')
        elif jt == "pamn":
            self.pamn_frame.grid(row=0, column=0, sticky='ew')

    # =========================================================================
    # SHARED HELPERS
    # =========================================================================
    def _get_signal_params(self):
        return dict(
            channel_pair=self.channel_pair.get(),
            technology=self.technology.get(),
            v_scale=float(self.v_scale.get()),
            h_scale=float(self.h_scale.get()),
        )

    def _run_signal_config_internal(self):
        self.log_message("=" * 50, "info")
        self.log_message("SIGNAL CONFIGURATION", "success")
        self.log_message("=" * 50, "info")
        p = self._get_signal_params()
        backend.setup_signal_config(
            self.instr, p['channel_pair'], p['technology'],
            p['v_scale'], p['h_scale'],
            log_callback_fn=self.log_message)
        self.signal_configured = True
        self.last_operation = 'signal'

    # =========================================================================
    # CONNECTION
    # =========================================================================
    def connect(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter IP address")
            return

        self.log_message("Connecting to oscilloscope...", "info")
        self.connect_btn.config(state=tk.DISABLED)

        def _connect():
            try:
                self.instr = backend.connect_instrument(ip, log_callback_fn=self.log_message)
                self.is_connected = True
                self.after(0, lambda: self.status_label.config(
                    text="● Connected", bg='#d4edda', fg='#155724'))
                self.after(0, lambda: self.connect_btn.config(state=tk.DISABLED))
                self.after(0, lambda: self.disconnect_btn.config(state=tk.NORMAL))
                self.after(0, lambda: self.signal_config_btn.config(state=tk.NORMAL))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Connection Error", str(e)))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))

        threading.Thread(target=_connect, daemon=True).start()

    def disconnect(self):
        if self.instr:
            try:
                self.instr.close()
                self.log_message("Disconnected from oscilloscope", "info")
            except Exception:
                pass
        self.instr = None
        self.is_connected = False
        self.signal_configured = False
        self.last_operation = None
        self.status_label.config(text="● Disconnected", bg='#f8d7da', fg='#721c24')
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.signal_config_btn.config(state=tk.DISABLED)

    # =========================================================================
    # SIGNAL CONFIG
    # =========================================================================
    def run_signal_config(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Please connect to oscilloscope first")
            return

        def _run():
            try:
                self._run_signal_config_internal()
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

        threading.Thread(target=_run, daemon=True).start()

    # =========================================================================
    # EYE DIAGRAM
    # =========================================================================
    def preset_and_configure_eye(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Please connect to oscilloscope first")
            return

        def _run():
            try:
                self._run_signal_config_internal()
                self._run_eye_internal()
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

        threading.Thread(target=_run, daemon=True).start()

    def run_eye_config(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Please connect to oscilloscope first")
            return
        if not self.signal_configured:
            messagebox.showwarning("Warning",
                                   "Signal not configured. Use 'Preset + Config' first.")
            return

        def _run():
            try:
                self._run_eye_internal()
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

        threading.Thread(target=_run, daemon=True).start()

    def _run_eye_internal(self):
        self.log_message("=" * 50, "info")
        self.log_message("EYE DIAGRAM CONFIGURATION", "success")
        self.log_message("=" * 50, "info")

        # If coming from any jitter mode, turn off jitter results display first
        if self.last_operation == 'jitter':
            self.log_message(
                "Jitter → Eye: turning off jitter results display...", "warning")
            backend.cleanup_jitter_state(self.instr, log_callback_fn=self.log_message)

        eye_type = self.eye_type.get()

        if eye_type == "sw":
            coming_from_hw = (self.last_operation == 'hw_eye')
            if coming_from_hw:
                self.log_message(
                    "HW CDR → SW CDR: removing zoom window and resetting trigger...",
                    "warning")

            mode     = self.eye_mode.get()
            specific = self.specific_eye.get() if mode == "specific" else None
            base     = int(self.base_level.get())   if mode == "selected" else None
            target   = int(self.target_level.get()) if mode == "selected" else None

            backend.setup_eye_sw_cdr(
                self.instr, mode, specific, base, target,
                self.enable_meas.get(),
                coming_from_hw_cdr=coming_from_hw,
                log_callback_fn=self.log_message)
            self.last_operation = 'sw_eye'

        else:  # hw
            if self.technology.get() == "10":
                self.log_message(
                    "⚠️  10GBASE-T1: symbol rate ~3.8 GBd — HW CDR may not lock. "
                    "Proceeding anyway...", "warning")

            if self.last_operation == 'sw_eye':
                self.log_message(
                    "SW CDR → HW CDR: signal already configured — "
                    "switching trigger + zoom only (no preset needed).", "info")

            backend.setup_eye_hw_cdr_with_zoom(
                self.instr,
                float(self.xstart.get()),
                float(self.xstop.get()),
                signal_already_configured=self.signal_configured,
                enable_zoom=self.enable_zoom.get(),
                log_callback_fn=self.log_message)
            self.last_operation = 'hw_eye'

    # =========================================================================
    # JITTER ANALYSIS
    # =========================================================================
    def preset_and_configure_jitter(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Please connect to oscilloscope first")
            return

        def _run():
            try:
                self._run_signal_config_internal()
                self._run_jitter_internal()
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

        threading.Thread(target=_run, daemon=True).start()

    def run_jitter_config(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Please connect to oscilloscope first")
            return
        if not self.signal_configured:
            messagebox.showwarning("Warning",
                                   "Signal not configured. Use 'Preset + Config' first.")
            return

        needs_reconfig = self.last_operation in ('sw_eye', 'hw_eye')

        def _run():
            try:
                if needs_reconfig:
                    self.log_message(
                        "Coming from eye diagram — re-running signal config for jitter...",
                        "warning")
                    self._run_signal_config_internal()
                self._run_jitter_internal()
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))

        threading.Thread(target=_run, daemon=True).start()

    def _run_jitter_internal(self):
        self.log_message("=" * 50, "info")
        self.log_message("JITTER ANALYSIS CONFIGURATION", "success")
        self.log_message("=" * 50, "info")

        jitter_type = self.jitter_type.get()

        if jitter_type != "quick":
            self.log_message("Resetting jitter decomposition state...", "info")
            self.instr.query_opc(30000)
            self.instr.write_str("ADVJitter1:SIGNal:SOURce DIFF1")
            self.instr.query_opc(30000)
            self.instr.write_str("ADVJitter1:RESult:ENABle ON")
            self.instr.query_opc(30000)
            # Single CLEJitcomp — backend functions do NOT repeat this
            self.instr.write_str("ADVJitter1:DCOMposition:CLEJitcomp")
            backend.opc_poll(self.instr, total_timeout_s=600,
                             label="CLEJitcomp",
                             log_callback_fn=self.log_message)
            # Correct commands from manual — no :ENABle suffix, BERScan does not exist
            self.log_message("  Disabling Quick Start display extras...", "info")
            for cmd, label in [
                ("ADVJitter1:RESult:STEPresponse OFF", "Step Response"),
                ("ADVJitter1:RESult:BATHtub OFF",      "DDJ Bathtub"),
                ("ADVJitter1:RESult:NBAThtub OFF",      "DDN Bathtub"),
            ]:
                try:
                    self.instr.write_str(cmd)
                    self.instr.query_opc(30000)
                    self.log_message(f"    {label}: OFF", "info")
                except Exception as e:
                    self.log_message(f"    {label}: could not disable — {e}", "warning")
            self.log_message("  ✅ Jitter state reset", "info")

        if jitter_type == "quick":
            backend.setup_jitter_quick_start(self.instr, log_callback_fn=self.log_message)

        elif jitter_type == "manual":
            selected = [c for c, v in self.jitter_components.items() if v.get()]
            if not selected:
                self.after(0, lambda: messagebox.showwarning("Warning", "No components selected"))
                return
            backend.setup_jitter_manual_components(
                self.instr, selected,
                log_callback_fn=self.log_message)

        else:  # pamn
            component = self.pamn_component.get()
            transitions = [{'base': b, 'target': t}
                           for (b, t), v in self.transitions.items() if v.get()]
            if not transitions:
                self.after(0, lambda: messagebox.showwarning("Warning", "No transitions selected"))
                return
            backend.setup_jitter_component_for_pamn(
                self.instr, component, log_callback_fn=self.log_message)
            backend.setup_jitter_pamn_results(
                self.instr, component, transitions, log_callback_fn=self.log_message)

        self.last_operation = 'jitter'

    # =========================================================================
    # LOGGING
    # =========================================================================
    def log_message(self, message, level="info"):
        def _log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] ", 'timestamp')
            self.log_text.insert(tk.END, message + "\n", level)
            self.log_text.see(tk.END)
            self.log_text.update()

        if threading.current_thread() is threading.main_thread():
            _log()
        else:
            self.after(0, _log)

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        self.log_message("Log cleared", "info")


def main():
    app = SignalIntegrityAutomator()
    app.mainloop()


if __name__ == '__main__':
    main()