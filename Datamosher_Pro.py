#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Datamosher Pro — DaVinci Resolve Integration (v2.0 Preview)
============================================================
A native DaVinci Resolve integration for precision video datamoshing.

New Features in v2.0:
1. Timeline Cut Alignment & Trim Control:
   - Full detection of timeline In-points, Out-points, and track positions.
   - Independent Pre-Cut (lead-in) and Post-Cut (tail) sliders for exact timing.
   - Live visual composition preview bar.
2. 1-Click Style Presets:
   - Subtle, Heavy Smash, Psychedelic Bloom, Motion Loop, and Fast Whip.
3. Automated Timeline Superposition:
   - Automatically adds a dedicated video track (V2/V3) and inserts the
     rendered transition clip centered over the cut point on the timeline.
4. Audio Crossfade Support:
   - Optional audio preservation with smooth crossfading across the cut boundary.
5. Cut Frame Visual Thumbnails:
   - Generates preview thumbnails of the exact frames at the cut boundary.
6. Step-by-Step Progress Feedback:
   - Real percentage and descriptive feedback during rendering and baking.

Attribution & Licensing:
- Based on the core bitstream datamoshing algorithms from Datamosher Pro by Akash Bora
  (https://github.com/Akascape/Datamosher-Pro), licensed under the MIT License.
- Includes Tomato Automosh by Kasper Ravel (MIT License) and pymosh by grampajoe (MIT License).

Usage in DaVinci Resolve:
  Workspace -> Scripts -> Datamosher_Pro
"""

import os
import sys
import threading
import subprocess
import webbrowser
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


def get_script_dir():
    """
    Safely resolves the directory where the script is located.
    Handles DaVinci Resolve's embedded script runner where '__file__' is not defined in globals.
    """
    if "__file__" in globals() and globals()["__file__"]:
        try:
            return os.path.dirname(os.path.abspath(globals()["__file__"]))
        except Exception:
            pass
    if sys.argv and sys.argv[0] and os.path.isfile(sys.argv[0]):
        try:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        except Exception:
            pass
    try:
        import DaVinciResolveScript as dvr
        app = dvr.scriptapp("Resolve")
        if app and app.Fusion():
            mapped = app.Fusion().MapPath("Scripts:Edit")
            if mapped and os.path.isdir(mapped):
                return mapped
    except Exception:
        pass
    appdata = os.getenv("APPDATA")
    if appdata:
        std_edit = os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Scripts", "Edit")
        if os.path.isdir(std_edit):
            return std_edit
    return os.getcwd()


# Configure module search paths
SCRIPT_DIR = get_script_dir()
if SCRIPT_DIR and SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Ensure DaVinci Fusion Modules directory is in sys.path
appdata = os.getenv("APPDATA")
if appdata:
    fusion_modules = os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Modules")
    if os.path.isdir(fusion_modules) and fusion_modules not in sys.path:
        sys.path.insert(0, fusion_modules)

# Import datamoshing engines
try:
    from DatamoshLib.Original import classic, classic_new, repeat, pymodes
    from DatamoshLib.Tomato import tomato
    MOTORS_OK = True
    MOTOR_ERR = ""
except Exception as e:
    MOTORS_OK = False
    MOTOR_ERR = str(e)


TRANS_MODES = [
    "Classic Motion Melt (Avidemux)",
    "Kinetic Stutter (P-Frame Repeat)",
    "Tomato Bloom (Vector Explosion)",
    "Macroblock Glide (Pixel Smear)",
    "Echo Drift (Motion Ghost)",
    "Tomato Pulse (Glitch Waves)",
    "Tomato Void (Bitstream Cut Drop)"
]

SINGLE_MODES = [
    "Classic Motion Melt (I-Frame Drop)",
    "Kinetic Repeat (Frame Loop)",
    "Macroblock Glide (Pixel Smear)",
    "Echo Drift (Motion Ghost)",
    "Tomato Bloom (Vector Flare)",
    "Tomato Pulse (Glitch Waves)",
    "Tomato Void (Automosh Cut Drop)"
]

MODE_DESCRIPTIONS = {
    "Classic Motion Melt (Avidemux)": (
        "✨ Datamosh Clásico: El movimiento del Clip 2 arrastra los píxeles del Clip 1 con fluidez natural sin tirones.\n"
        "Ideal para: Sujetos en movimiento, paneos de cámara o zooms. Se recupera limpiamente al terminar."
    ),
    "Kinetic Stutter (P-Frame Repeat)": (
        "⚡ Kinetic Stutter: Repite vectores de movimiento al corte creando un tartamudeo rítmico antes de fundirse.\n"
        "Ideal para: Vídeos musicales estilo Trap/Hip-Hop, cortes al beat y transiciones enérgicas."
    ),
    "Tomato Bloom (Vector Explosion)": (
        "🌸 Vector Bloom: Multiplica los vectores de movimiento creando llamaradas y explosiones cromáticas.\n"
        "Ideal para: Impactos, explosiones, bailes enérgicos y efectos psicodélicos."
    ),
    "Macroblock Glide (Pixel Smear)": (
        "🌊 Macroblock Glide: Estira los bloques de compresión a lo largo de las líneas de movimiento.\n"
        "Ideal para: Estelas continuas de píxeles y barridos direccionales suaves."
    ),
    "Echo Drift (Motion Ghost)": (
        "👻 Echo Drift: Genera un eco espectral continuo transfiriendo la inercia del plano anterior.\n"
        "Ideal para: Secuencias oníricas, de misterio o planos ambient."
    ),
    "Tomato Pulse (Glitch Waves)": (
        "📡 Glitch Pulse: Emite ondas periódicas y rítmicas de distorsión digital a intervalos regulares.\n"
        "Ideal para: Estilo cyberpunk, música electrónica y distorsión sci-fi."
    ),
    "Tomato Void (Bitstream Cut Drop)": (
        "🕳️ Tomato Void: Automosh puro de flujo binario que elimina keyframes basándose en el peso del fotograma.\n"
        "Ideal para: Colisiones de planos caóticas y crudas."
    ),
}


def get_resolve():
    """
    Connects to the active DaVinci Resolve scripting instance.
    Works inside DaVinci Resolve Studio and Free editions.
    """
    try:
        import DaVinciResolveScript as dvr
        return dvr.scriptapp("Resolve")
    except Exception:
        return globals().get("resolve", None)


def get_video_duration(filepath):
    """
    Retrieves video duration in seconds using ffprobe.
    """
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{filepath}"'
        res = subprocess.check_output(cmd, shell=True).decode().strip()
        return float(res)
    except Exception:
        return 0.0


def has_audio_stream(filepath):
    """
    Checks if a video file contains at least one audio stream.
    """
    try:
        cmd = f'ffprobe -v error -select_streams a -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "{filepath}"'
        res = subprocess.check_output(cmd, shell=True).decode().strip()
        return "audio" in res.lower()
    except Exception:
        return False


def count_video_frames(filepath, default_fps=30.0):
    """
    Accurately counts total video frames in an AVI/MP4 stream.
    """
    try:
        cmd = f'ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of default=nokey=1:noprint_wrappers=1 "{filepath}"'
        res = subprocess.check_output(cmd, shell=True).decode().strip()
        val = int(res)
        if val > 0:
            return val
    except Exception:
        pass
    dur = get_video_duration(filepath)
    return max(1, int(round(dur * default_fps)))


def get_item_file_path(item):
    """
    Safely retrieves the absolute file path from a TimelineItem or MediaPoolItem.
    """
    if not item:
        return None
    try:
        mp = item.GetMediaPoolItem() if hasattr(item, "GetMediaPoolItem") else item
        if not mp:
            return None
        props = mp.GetClipProperty()
        if isinstance(props, dict):
            fp = props.get("File Path", "")
            if fp and os.path.exists(fp):
                return fp
        fp = mp.GetClipProperty("File Path")
        if isinstance(fp, str) and os.path.exists(fp):
            return fp
    except Exception:
        pass
    return None


class DatamosherResolveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Datamosher Pro — DaVinci Resolve v2.0")
        self.root.geometry("720x860")
        self.root.minsize(660, 760)
        self.root.configure(bg="#181818")

        # Configure dark theme styles
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#181818", foreground="#ffffff", font=("Segoe UI", 10))
        self.style.configure("TLabel", background="#181818", foreground="#ffffff")
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#00b4d8")
        self.style.configure("Info.TLabel", font=("Segoe UI", 9), foreground="#00b4d8")
        self.style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#888888")
        self.style.configure("Bar.TLabel", font=("Segoe UI", 9, "bold"), foreground="#00f5d4", background="#222222", padding=6)
        self.style.configure("TCheckbutton", background="#181818", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.style.configure("TNotebook", background="#181818", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#282828", foreground="#ffffff", padding=[14, 7], font=("Segoe UI", 10, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", "#0077b6")], foreground=[("selected", "#ffffff")])
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), background="#2e2e2e", foreground="#ffffff")
        self.style.map("TButton", background=[("active", "#3f3f3f")])
        self.style.configure("Detect.TButton", font=("Segoe UI", 9, "bold"), background="#023e8a", foreground="#ffffff")
        self.style.map("Detect.TButton", background=[("active", "#0077b6")])
        self.style.configure("Preset.TButton", font=("Segoe UI", 8, "bold"), background="#333333", foreground="#ffffff")
        self.style.map("Preset.TButton", background=[("active", "#0077b6")])
        self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), background="#d90429", foreground="#ffffff")
        self.style.map("Action.TButton", background=[("active", "#ef233c")])

        # State variables for 2-clip transition
        self.trans_clip1 = tk.StringVar(value="")
        self.trans_clip2 = tk.StringVar(value="")
        self.trans_c1_in = tk.DoubleVar(value=0.0)
        self.trans_c1_dur = tk.DoubleVar(value=0.0)
        self.trans_c2_in = tk.DoubleVar(value=0.0)
        self.trans_c2_dur = tk.DoubleVar(value=0.0)
        self.c1_timeline_end = 0.0
        self.c1_track = 1

        # Timing controls
        self.trans_pre_cut = tk.DoubleVar(value=1.5)
        self.trans_duration = tk.DoubleVar(value=1.2)
        self.trans_post_cut = tk.DoubleVar(value=1.5)
        self.trans_delta = tk.IntVar(value=1)
        self.trans_mode = tk.StringVar(value="Classic Motion Melt (Avidemux)")

        # Workflow & audio options
        self.use_timeline_trim = tk.BooleanVar(value=True)
        self.auto_place_timeline = tk.BooleanVar(value=True)
        self.include_audio = tk.BooleanVar(value=False)
        self.auto_import = tk.BooleanVar(value=True)

        # State variables for single clip datamosh
        self.single_clip = tk.StringVar(value="")
        self.single_mode = tk.StringVar(value="Classic Motion Melt (I-Frame Drop)")
        self.single_start = tk.DoubleVar(value=0.0)
        self.single_end = tk.DoubleVar(value=2.5)
        self.single_delta = tk.IntVar(value=1)

        # Cache of detected timeline clips
        self.timeline_clips_cache = []
        self.thumb_c1 = None
        self.thumb_c2 = None

        self.status_var = tk.StringVar(value="Ready.")
        self.preview_str = tk.StringVar(value="Composition preview ready.")

        self.create_ui()

        # Check engine integrity on startup
        if not MOTORS_OK:
            self.status_var.set(f"Warning: DatamoshLib error: {MOTOR_ERR}")
        else:
            self.detect_from_timeline_playhead()

    def create_ui(self):
        # Header banner
        head_frame = ttk.Frame(self.root, padding=12)
        head_frame.pack(fill="x")
        title = ttk.Label(head_frame, text="DATAMOSHER PRO — DaVinci Resolve v2.0", style="Header.TLabel")
        title.pack(anchor="w")
        sub = ttk.Label(head_frame, text="Precision Bitstream Glitch & Automated Timeline Workflow",
                        style="Sub.TLabel")
        sub.pack(anchor="w")

        # Notebook tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=3)

        # TAB 1: 2-Clip Transition
        self.tab_trans = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_trans, text=" 🔀 2-Clip Transition ")
        self.build_trans_tab()

        # TAB 2: Single Clip
        self.tab_single = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_single, text=" 🎬 Single Clip ")
        self.build_single_tab()

        # Footer with status label and progress bar
        footer = ttk.Frame(self.root, padding=10)
        footer.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(footer, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress["value"] = 0

        lbl_status = ttk.Label(footer, textvariable=self.status_var, foreground="#00ff88", font=("Segoe UI", 10, "bold"))
        lbl_status.pack(anchor="w", pady=(0, 4))

        btn_orig = ttk.Button(footer, text="🌐 Based on Datamosher Pro by Akash Bora (GitHub)",
                              command=lambda: webbrowser.open("https://github.com/Akascape/Datamosher-Pro"))
        btn_orig.pack(fill="x")

    # -------------------------------------------------------------
    # TAB: 2-CLIP TRANSITION
    # -------------------------------------------------------------
    def build_trans_tab(self):
        # Detection action buttons
        det_bar = ttk.Frame(self.tab_trans)
        det_bar.pack(fill="x", pady=(0, 6))

        btn_cut = ttk.Button(det_bar, text="📍 Detect 2 Clips at Cut (Playhead)", style="Detect.TButton",
                             command=self.detect_from_timeline_playhead)
        btn_cut.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_pool = ttk.Button(det_bar, text="📁 Use 2 Media Pool Clips", style="Detect.TButton",
                              command=self.detect_from_media_pool)
        btn_pool.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Presets Bar
        preset_frame = ttk.LabelFrame(self.tab_trans, text=" ⚡ 1-Click Style Presets ", padding=6)
        preset_frame.pack(fill="x", pady=3)

        btn_p1 = ttk.Button(preset_frame, text="🟢 Fluid Melt", style="Preset.TButton",
                            command=lambda: self.apply_preset("melt"))
        btn_p1.pack(side="left", fill="x", expand=True, padx=2)

        btn_p2 = ttk.Button(preset_frame, text="🔴 Kinetic Stutter", style="Preset.TButton",
                            command=lambda: self.apply_preset("stutter"))
        btn_p2.pack(side="left", fill="x", expand=True, padx=2)

        btn_p3 = ttk.Button(preset_frame, text="🟣 Vector Bloom", style="Preset.TButton",
                            command=lambda: self.apply_preset("bloom"))
        btn_p3.pack(side="left", fill="x", expand=True, padx=2)

        btn_p4 = ttk.Button(preset_frame, text="🔵 Macro Glide", style="Preset.TButton",
                            command=lambda: self.apply_preset("glide"))
        btn_p4.pack(side="left", fill="x", expand=True, padx=2)

        btn_p5 = ttk.Button(preset_frame, text="⚡ Fast Whip", style="Preset.TButton",
                            command=lambda: self.apply_preset("whip"))
        btn_p5.pack(side="left", fill="x", expand=True, padx=2)

        # Outgoing Clip (A)
        f1 = ttk.LabelFrame(self.tab_trans, text=" 1. Outgoing Clip (Frozen Base Canvas) ", padding=6)
        f1.pack(fill="x", pady=3)

        self.cmb_clip1 = ttk.Combobox(f1, state="readonly", font=("Segoe UI", 9))
        self.cmb_clip1.pack(fill="x", pady=(0, 2))
        self.cmb_clip1.bind("<<ComboboxSelected>>", self.on_clip1_dropdown_select)

        r1 = ttk.Frame(f1)
        r1.pack(fill="x")
        ttk.Entry(r1, textvariable=self.trans_clip1, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=lambda: self.browse(self.trans_clip1, self.trans_c1_in, self.trans_c1_dur)).pack(side="right")

        self.lbl_c1_trim = ttk.Label(f1, text="✂️ Timeline Trim: In: 0.00s | Duration: Full File", style="Info.TLabel")
        self.lbl_c1_trim.pack(anchor="w", pady=(2, 0))

        # Incoming Clip (B)
        f2 = ttk.LabelFrame(self.tab_trans, text=" 2. Incoming Clip (Motion tearing into Clip A) ", padding=6)
        f2.pack(fill="x", pady=3)

        self.cmb_clip2 = ttk.Combobox(f2, state="readonly", font=("Segoe UI", 9))
        self.cmb_clip2.pack(fill="x", pady=(0, 2))
        self.cmb_clip2.bind("<<ComboboxSelected>>", self.on_clip2_dropdown_select)

        r2 = ttk.Frame(f2)
        r2.pack(fill="x")
        ttk.Entry(r2, textvariable=self.trans_clip2, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r2, text="Browse...", command=lambda: self.browse(self.trans_clip2, self.trans_c2_in, self.trans_c2_dur)).pack(side="right")

        self.lbl_c2_trim = ttk.Label(f2, text="✂️ Timeline Trim: In: 0.00s | Duration: Full File", style="Info.TLabel")
        self.lbl_c2_trim.pack(anchor="w", pady=(2, 0))

        # Thumbnail Previews Frame
        self.thumb_frame = ttk.Frame(self.tab_trans, padding=2)
        self.thumb_frame.pack(fill="x", pady=2)
        self.lbl_t1 = ttk.Label(self.thumb_frame, text="[ Clip 1 Cut Frame ]", style="Sub.TLabel")
        self.lbl_t1.pack(side="left", padx=8)
        ttk.Label(self.thumb_frame, text="⚡ CUT ⚡", foreground="#ff0055", font=("Segoe UI", 10, "bold")).pack(side="left", expand=True)
        self.lbl_t2 = ttk.Label(self.thumb_frame, text="[ Clip 2 Start Frame ]", style="Sub.TLabel")
        self.lbl_t2.pack(side="right", padx=8)

        # Transition Settings Frame
        p_frame = ttk.LabelFrame(self.tab_trans, text=" Transition Timing & Motion Settings ", padding=8)
        p_frame.pack(fill="x", pady=4)

        # Pre-cut and Glitch duration sliders
        row_timing1 = ttk.Frame(p_frame)
        row_timing1.pack(fill="x", pady=2)

        ttk.Label(row_timing1, text="Pre-Cut Lead-in:").pack(side="left")
        spn_pre = ttk.Spinbox(row_timing1, from_=0.5, to=5.0, increment=0.25, textvariable=self.trans_pre_cut, width=5, command=self.update_preview_bar)
        spn_pre.pack(side="left", padx=(4, 12))

        ttk.Label(row_timing1, text="Glitch Duration:").pack(side="left")
        spn_dur = ttk.Spinbox(row_timing1, from_=0.2, to=6.0, increment=0.2, textvariable=self.trans_duration, width=5, command=self.update_preview_bar)
        spn_dur.pack(side="left", padx=(4, 12))

        ttk.Label(row_timing1, text="Post-Cut Tail:").pack(side="left")
        spn_post = ttk.Spinbox(row_timing1, from_=0.5, to=5.0, increment=0.25, textvariable=self.trans_post_cut, width=5, command=self.update_preview_bar)
        spn_post.pack(side="left", padx=(4, 0))

        # Delta Multiplier and Mode
        row_timing2 = ttk.Frame(p_frame)
        row_timing2.pack(fill="x", pady=4)

        ttk.Label(row_timing2, text="Effect Mode:").pack(side="left")
        self.cmb_tm = ttk.Combobox(row_timing2, textvariable=self.trans_mode, state="readonly", width=32,
                                   values=TRANS_MODES)
        self.cmb_tm.pack(side="left", padx=(4, 12), fill="x", expand=True)
        self.cmb_tm.bind("<<ComboboxSelected>>", self.on_mode_change)

        ttk.Label(row_timing2, text="Intensity/Delta:").pack(side="left")
        spn_del = ttk.Spinbox(row_timing2, from_=1, to=20, increment=1, textvariable=self.trans_delta, width=4, command=self.update_preview_bar)
        spn_del.pack(side="left", padx=(4, 0))

        # Mode explanation description card
        self.lbl_mode_desc = ttk.Label(p_frame, text="", style="Info.TLabel", wraplength=660, justify="left")
        self.lbl_mode_desc.pack(fill="x", pady=(3, 3))

        # Dynamic Composition Preview Bar
        self.lbl_bar = ttk.Label(p_frame, textvariable=self.preview_str, style="Bar.TLabel")
        self.lbl_bar.pack(fill="x", pady=(2, 2))

        # Workflow Checkboxes
        wf_frame = ttk.Frame(self.tab_trans)
        wf_frame.pack(fill="x", pady=3)

        chk_place = ttk.Checkbutton(wf_frame, text="Auto-place on Timeline (New Track above cut)",
                                    variable=self.auto_place_timeline, style="TCheckbutton")
        chk_place.pack(side="left", padx=(0, 10))

        chk_trim = ttk.Checkbutton(wf_frame, text="Respect Timeline Trims",
                                   variable=self.use_timeline_trim, style="TCheckbutton")
        chk_trim.pack(side="left", padx=(0, 10))

        chk_audio = ttk.Checkbutton(wf_frame, text="Crossfade Audio",
                                    variable=self.include_audio, style="TCheckbutton")
        chk_audio.pack(side="left")

        # Execute Button
        btn_run = ttk.Button(self.tab_trans, text="💥 CREATE DATAMOSH TRANSITION", style="Action.TButton",
                             command=self.run_transition)
        btn_run.pack(fill="x", pady=(6, 2), ipady=6)

        self.update_mode_description()
        self.update_preview_bar()

    # -------------------------------------------------------------
    # TAB: SINGLE CLIP
    # -------------------------------------------------------------
    def build_single_tab(self):
        f1 = ttk.LabelFrame(self.tab_single, text=" Target Video Clip ", padding=8)
        f1.pack(fill="x", pady=4)
        ttk.Entry(f1, textvariable=self.single_clip, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(f1, text="Browse...", command=lambda: self.browse_single(self.single_clip)).pack(side="right")

        btn_detect = ttk.Button(self.tab_single, text="⚡ Detect Selected Clip in DaVinci",
                                style="Detect.TButton", command=self.detect_single_clip)
        btn_detect.pack(fill="x", pady=6)

        # Datamoshing Mode
        m_frame = ttk.LabelFrame(self.tab_single, text=" Datamoshing Algorithm ", padding=8)
        m_frame.pack(fill="x", pady=6)
        ttk.Combobox(m_frame, textvariable=self.single_mode, values=SINGLE_MODES, state="readonly").pack(fill="x", pady=2)

        # Time Range
        r_frame = ttk.LabelFrame(self.tab_single, text=" Effect Time Range (Seconds in Source) ", padding=8)
        r_frame.pack(fill="x", pady=6)
        rw1 = ttk.Frame(r_frame)
        rw1.pack(fill="x", pady=3)
        ttk.Label(rw1, text="Start Second:").pack(side="left")
        ttk.Spinbox(rw1, from_=0.0, to=999.0, increment=0.1, textvariable=self.single_start, width=8).pack(side="left", padx=10)
        ttk.Label(rw1, text="End Second:").pack(side="left")
        ttk.Spinbox(rw1, from_=0.1, to=999.0, increment=0.1, textvariable=self.single_end, width=8).pack(side="left", padx=10)

        rw2 = ttk.Frame(r_frame)
        rw2.pack(fill="x", pady=3)
        ttk.Label(rw2, text="Intensity Multiplier (Delta):").pack(side="left")
        ttk.Spinbox(rw2, from_=1, to=20, increment=1, textvariable=self.single_delta, width=8).pack(side="left", padx=10)

        # Execute Button
        btn_single_mosh = ttk.Button(self.tab_single, text="💥 DATAMOSH THIS CLIP", style="Action.TButton",
                                     command=self.run_single)
        btn_single_mosh.pack(fill="x", pady=15, ipady=6)

    def on_mode_change(self, event=None):
        self.update_mode_description()
        self.update_preview_bar()

    def update_mode_description(self):
        desc = MODE_DESCRIPTIONS.get(self.trans_mode.get(), "")
        if hasattr(self, "lbl_mode_desc"):
            self.lbl_mode_desc.config(text=desc)

    def apply_preset(self, p_type):
        if p_type == "melt":
            self.trans_mode.set("Classic Motion Melt (Avidemux)")
            self.trans_pre_cut.set(1.5)
            self.trans_duration.set(1.2)
            self.trans_post_cut.set(1.5)
            self.trans_delta.set(1)
        elif p_type == "stutter":
            self.trans_mode.set("Kinetic Stutter (P-Frame Repeat)")
            self.trans_pre_cut.set(1.0)
            self.trans_duration.set(1.0)
            self.trans_post_cut.set(1.2)
            self.trans_delta.set(3)
        elif p_type == "bloom":
            self.trans_mode.set("Tomato Bloom (Vector Explosion)")
            self.trans_pre_cut.set(1.5)
            self.trans_duration.set(1.5)
            self.trans_post_cut.set(1.2)
            self.trans_delta.set(8)
        elif p_type == "glide":
            self.trans_mode.set("Macroblock Glide (Pixel Smear)")
            self.trans_pre_cut.set(1.5)
            self.trans_duration.set(1.5)
            self.trans_post_cut.set(1.5)
            self.trans_delta.set(4)
        elif p_type == "whip":
            self.trans_mode.set("Classic Motion Melt (Avidemux)")
            self.trans_pre_cut.set(0.5)
            self.trans_duration.set(0.4)
            self.trans_post_cut.set(0.6)
            self.trans_delta.set(1)
        self.update_mode_description()
        self.update_preview_bar()

    def update_preview_bar(self):
        pre = self.trans_pre_cut.get()
        dur = self.trans_duration.get()
        post = self.trans_post_cut.get()
        delta = self.trans_delta.get()
        tot = pre + post
        self.preview_str.set(
            f"📊 Preview: [ Clip 1: {pre:.2f}s ] ➔ ⚡ [ GLITCH: {dur:.2f}s (x{delta}) ] ➔ [ Clip 2: {post:.2f}s ] | Total: {tot:.2f}s"
        )

    def browse(self, var, in_var, dur_var):
        f = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv"), ("All files", "*.*")])
        if f:
            var.set(f)
            in_var.set(0.0)
            dur_var.set(round(get_video_duration(f), 3))
            self.update_trim_labels()
            self.refresh_thumbnails()

    def browse_single(self, var):
        f = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv"), ("All files", "*.*")])
        if f:
            var.set(f)
            dur = get_video_duration(f)
            self.single_start.set(0.0)
            self.single_end.set(round(min(dur, 2.5), 2))

    def update_trim_labels(self):
        in1 = self.trans_c1_in.get()
        dur1 = self.trans_c1_dur.get()
        in2 = self.trans_c2_in.get()
        dur2 = self.trans_c2_dur.get()
        self.lbl_c1_trim.config(text=f"✂️ Timeline Trim: In: {in1:.2f}s | Duration: {dur1:.2f}s (Cut at: {in1 + dur1:.2f}s)")
        self.lbl_c2_trim.config(text=f"✂️ Timeline Trim: In: {in2:.2f}s | Duration: {dur2:.2f}s (Starts at: {in2:.2f}s)")
        self.update_preview_bar()

    def refresh_thumbnails(self):
        """
        Generates small preview images of the cut frames in background.
        """
        c1 = self.trans_clip1.get()
        c2 = self.trans_clip2.get()
        if not c1 or not os.path.exists(c1) or not c2 or not os.path.exists(c2):
            return

        def _worker():
            try:
                in1 = self.trans_c1_in.get()
                dur1 = self.trans_c1_dur.get()
                in2 = self.trans_c2_in.get()

                cut1 = max(0.0, in1 + dur1 - 0.05)
                start2 = max(0.0, in2 + 0.05)

                tmp_dir = tempfile.gettempdir()
                p1 = os.path.join(tmp_dir, "__datamosh_t1.png")
                p2 = os.path.join(tmp_dir, "__datamosh_t2.png")

                cmd1 = f'ffmpeg -y -ss {cut1:.3f} -i "{c1}" -vframes 1 -s 120x68 -y "{p1}"'
                cmd2 = f'ffmpeg -y -ss {start2:.3f} -i "{c2}" -vframes 1 -s 120x68 -y "{p2}"'

                subprocess.call(cmd1, shell=True)
                subprocess.call(cmd2, shell=True)

                if os.path.exists(p1) and os.path.exists(p2):
                    self.root.after(0, lambda: self._apply_thumbnails(p1, p2))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_thumbnails(self, p1, p2):
        try:
            self.thumb_c1 = tk.PhotoImage(file=p1)
            self.thumb_c2 = tk.PhotoImage(file=p2)
            self.lbl_t1.config(image=self.thumb_c1, text="")
            self.lbl_t2.config(image=self.thumb_c2, text="")
        except Exception:
            pass

    def on_clip1_dropdown_select(self, event=None):
        idx = self.cmb_clip1.current()
        if 0 <= idx < len(self.timeline_clips_cache):
            c = self.timeline_clips_cache[idx]
            self.trans_clip1.set(c["file_path"])
            self.trans_c1_in.set(c["in_sec"])
            self.trans_c1_dur.set(c["dur_sec"])
            self.c1_timeline_end = c["end"]
            self.c1_track = c["track"]
            self.update_trim_labels()
            self.refresh_thumbnails()

    def on_clip2_dropdown_select(self, event=None):
        idx = self.cmb_clip2.current()
        if 0 <= idx < len(self.timeline_clips_cache):
            c = self.timeline_clips_cache[idx]
            self.trans_clip2.set(c["file_path"])
            self.trans_c2_in.set(c["in_sec"])
            self.trans_c2_dur.set(c["dur_sec"])
            self.update_trim_labels()
            self.refresh_thumbnails()

    # -------------------------------------------------------------
    # DAVINCI RESOLVE TIMELINE CLIP DETECTION
    # -------------------------------------------------------------
    def get_all_timeline_clips(self, timeline):
        """
        Scans all video tracks on the timeline and returns sorted clips with accurate trim info.
        """
        clips = []
        try:
            track_count = timeline.GetTrackCount("video")
            timeline_fps = 24.0
            try:
                tl_fps = timeline.GetSetting("timelineFrameRate")
                if tl_fps:
                    timeline_fps = float(tl_fps)
            except Exception:
                pass
            if timeline_fps <= 0:
                timeline_fps = 24.0

            for t in range(1, track_count + 1):
                items = timeline.GetItemListInTrack("video", t) or []
                for it in items:
                    fp = get_item_file_path(it)
                    if fp:
                        name = it.GetName() or os.path.basename(fp)
                        start_frame = it.GetStart()
                        end_frame = it.GetEnd()
                        dur_frames = it.GetDuration()

                        source_fps = timeline_fps
                        mp = it.GetMediaPoolItem() if hasattr(it, "GetMediaPoolItem") else None
                        if mp:
                            try:
                                s_fps = float(mp.GetClipProperty("FPS") or timeline_fps)
                                if s_fps > 0:
                                    source_fps = s_fps
                            except Exception:
                                pass

                        in_sec = 0.0
                        left_offset = None
                        try:
                            left_offset = it.GetLeftOffset()
                        except Exception:
                            pass

                        try:
                            if hasattr(it, "GetSourceStartTime"):
                                st = it.GetSourceStartTime()
                                if isinstance(st, (int, float)) and st > 0:
                                    in_sec = float(st)
                        except Exception:
                            pass

                        if in_sec == 0.0 and isinstance(left_offset, (int, float)) and left_offset > 0:
                            in_sec = float(left_offset) / source_fps

                        dur_sec = float(dur_frames) / timeline_fps if dur_frames else 0.0

                        total_file_dur = get_video_duration(fp)
                        if total_file_dur > 0:
                            if in_sec >= total_file_dur:
                                if isinstance(left_offset, (int, float)) and 0 <= (float(left_offset) / source_fps) < total_file_dur:
                                    in_sec = float(left_offset) / source_fps
                                else:
                                    in_sec = 0.0
                            if dur_sec <= 0 or (in_sec + dur_sec) > (total_file_dur + 1.0):
                                dur_sec = max(0.5, total_file_dur - in_sec)

                        clips.append({
                            "item": it,
                            "name": name,
                            "file_path": fp,
                            "start": start_frame,
                            "end": end_frame,
                            "track": t,
                            "in_sec": round(in_sec, 3),
                            "dur_sec": round(dur_sec, 3),
                            "fps": source_fps
                        })
            clips.sort(key=lambda c: (c["start"], c["track"]))
        except Exception:
            pass
        return clips

    def update_dropdowns(self, clips):
        self.timeline_clips_cache = clips
        options = [
            f"{i+1}. {c['name']} (V{c['track']}, in: {c['in_sec']}s, dur: {c['dur_sec']}s)"
            for i, c in enumerate(clips)
        ]
        self.cmb_clip1["values"] = options
        self.cmb_clip2["values"] = options

    def detect_from_timeline_playhead(self):
        """
        Detects 2 contiguous clips at the cut point under the playhead.
        Accurately extracts timeline trim in-points and durations.
        """
        resolve = get_resolve()
        if not resolve:
            self.status_var.set("DaVinci Resolve not connected.")
            return

        try:
            pm = resolve.GetProjectManager()
            proj = pm.GetCurrentProject()
            if not proj:
                self.status_var.set("Please open a project in DaVinci Resolve.")
                return
            tl = proj.GetCurrentTimeline()
            if not tl:
                self.status_var.set("Please open a timeline in DaVinci Resolve.")
                return

            clips = self.get_all_timeline_clips(tl)
            if not clips:
                self.status_var.set("No video clips found on the active timeline.")
                return

            self.update_dropdowns(clips)

            curr_it = tl.GetCurrentVideoItem()
            curr_fp = get_item_file_path(curr_it) if curr_it else None

            c1 = None
            c2 = None

            if curr_fp:
                for i, c in enumerate(clips):
                    if c["file_path"] == curr_fp:
                        if i > 0:
                            c1 = clips[i - 1]
                            c2 = c
                        elif i < len(clips) - 1:
                            c1 = c
                            c2 = clips[i + 1]
                        break

            if not c1 or not c2:
                if len(clips) >= 2:
                    c1 = clips[0]
                    c2 = clips[1]
                elif len(clips) == 1:
                    c = clips[0]
                    self.single_clip.set(c["file_path"])
                    self.single_start.set(c["in_sec"])
                    self.single_end.set(round(c["in_sec"] + c["dur_sec"], 2))
                    self.trans_clip1.set(c["file_path"])
                    self.trans_c1_in.set(c["in_sec"])
                    self.trans_c1_dur.set(c["dur_sec"])
                    self.c1_timeline_end = c["end"]
                    self.c1_track = c["track"]
                    self.update_trim_labels()
                    self.status_var.set(f"Detected 1 clip: {c['name']}. Please select the second clip.")
                    return

            if c1 and c2:
                self.trans_clip1.set(c1["file_path"])
                self.trans_c1_in.set(c1["in_sec"])
                self.trans_c1_dur.set(c1["dur_sec"])
                self.c1_timeline_end = c1["end"]
                self.c1_track = c1["track"]

                self.trans_clip2.set(c2["file_path"])
                self.trans_c2_in.set(c2["in_sec"])
                self.trans_c2_dur.set(c2["dur_sec"])

                self.update_trim_labels()
                self.refresh_thumbnails()

                try:
                    self.cmb_clip1.current(clips.index(c1))
                    self.cmb_clip2.current(clips.index(c2))
                except Exception:
                    pass
                self.status_var.set(f"✅ Detected at cut: {c1['name']}  ➜  {c2['name']}")

        except Exception as e:
            self.status_var.set(f"Error detecting timeline: {str(e)}")

    def detect_from_media_pool(self):
        """
        Detects clips selected by the user in the DaVinci Resolve Media Pool panel.
        """
        resolve = get_resolve()
        if not resolve:
            messagebox.showinfo("Notice", "Please open DaVinci Resolve first.")
            return

        try:
            pm = resolve.GetProjectManager()
            proj = pm.GetCurrentProject()
            if not proj: return
            mp = proj.GetMediaPool()
            if not mp: return

            selected = mp.GetSelectedClips() or []
            files = []
            for item in selected:
                fp = get_item_file_path(item)
                if fp:
                    files.append(fp)

            if len(files) >= 2:
                self.trans_clip1.set(files[0])
                self.trans_c1_in.set(0.0)
                self.trans_c1_dur.set(round(get_video_duration(files[0]), 3))

                self.trans_clip2.set(files[1])
                self.trans_c2_in.set(0.0)
                self.trans_c2_dur.set(round(get_video_duration(files[1]), 3))

                self.update_trim_labels()
                self.refresh_thumbnails()
                self.status_var.set(f"✅ 2 clips loaded from Media Pool: {os.path.basename(files[0])} ➜ {os.path.basename(files[1])}")
            elif len(files) == 1:
                self.trans_clip1.set(files[0])
                self.trans_c1_in.set(0.0)
                self.trans_c1_dur.set(round(get_video_duration(files[0]), 3))
                self.update_trim_labels()
                self.status_var.set(f"1 clip selected in Media Pool: {os.path.basename(files[0])}. Please select the second clip.")
            else:
                messagebox.showinfo(
                    "Media Pool Selection",
                    "Select 2 clips in the DaVinci Resolve Media Pool (hold Ctrl or Shift and click two clips), then click this button again."
                )
        except Exception as e:
            self.status_var.set(f"Media Pool error: {str(e)}")

    def detect_single_clip(self):
        """
        Detects the clip under the playhead for single-clip datamoshing,
        pre-populating its trimmed timeline start and end times.
        """
        resolve = get_resolve()
        if not resolve:
            return
        try:
            pm = resolve.GetProjectManager()
            proj = pm.GetCurrentProject()
            if not proj: return
            tl = proj.GetCurrentTimeline()
            if not tl: return
            it = tl.GetCurrentVideoItem()
            if not it: return
            fp = get_item_file_path(it)
            if not fp: return
            self.single_clip.set(fp)

            found = False
            for c in self.timeline_clips_cache:
                if c["file_path"] == fp:
                    self.single_start.set(c["in_sec"])
                    self.single_end.set(round(c["in_sec"] + c["dur_sec"], 2))
                    found = True
                    break

            if not found:
                dur = get_video_duration(fp)
                self.single_start.set(0.0)
                self.single_end.set(round(min(dur, 2.5), 2))

            self.status_var.set(f"Detected clip: {os.path.basename(fp)} ({self.single_start.get()}s to {self.single_end.get()}s)")
        except Exception:
            pass

    # -------------------------------------------------------------
    # 2-CLIP TRANSITION EXECUTION
    # -------------------------------------------------------------
    def run_transition(self):
        c1 = self.trans_clip1.get()
        c2 = self.trans_clip2.get()

        if not c1 or not os.path.exists(c1) or not c2 or not os.path.exists(c2):
            messagebox.showerror("Missing Clips", "Both Clip 1 and Clip 2 must be selected to create a transition.")
            return

        self.progress["value"] = 5
        self.status_var.set("Initializing Datamosh transition...")

        t = threading.Thread(target=self._transition_thread, args=(c1, c2))
        t.daemon = True
        t.start()

    def _transition_thread(self, c1, c2):
        temp_c1_avi = ""
        temp_c2_avi = ""
        temp_list_txt = ""
        temp_joined_avi = ""
        temp_corrupt = ""
        temp_audio = ""
        try:
            base_dir = os.path.dirname(c1)
            name1 = os.path.splitext(os.path.basename(c1))[0]
            name2 = os.path.splitext(os.path.basename(c2))[0]
            out_trans = os.path.join(base_dir, f"Transition_{name1}_to_{name2}_datamoshed.mp4")

            self.root.after(0, lambda: self.progress.configure(value=10))
            self.status_var.set("Step 1/5: Analyzing timeline trim boundaries & fps...")

            # Retrieve trim and timing values
            in1 = self.trans_c1_in.get()
            dur1 = self.trans_c1_dur.get()
            in2 = self.trans_c2_in.get()
            dur2 = self.trans_c2_dur.get()
            use_trims = self.use_timeline_trim.get()

            pre_len = self.trans_pre_cut.get()
            mosh_len = self.trans_duration.get()
            post_len = self.trans_post_cut.get()
            delta = max(1, self.trans_delta.get())
            mode = self.trans_mode.get()

            tot_d1 = get_video_duration(c1)
            tot_d2 = get_video_duration(c2)

            if dur1 <= 0.0 or not use_trims:
                in1 = 0.0
                dur1 = tot_d1 if tot_d1 > 0 else 3.0

            if dur2 <= 0.0 or not use_trims:
                in2 = 0.0
                dur2 = tot_d2 if tot_d2 > 0 else 3.0

            # Calculate cut boundaries
            cut_point_1 = in1 + dur1
            if tot_d1 > 0:
                cut_point_1 = min(cut_point_1, tot_d1)

            # Lead-in duration of Clip 1 preceding cut
            c1_seek = max(in1, cut_point_1 - pre_len)
            c1_extract_dur = max(0.3, cut_point_1 - c1_seek)

            # Clip 2 starts directly at in2
            c2_seek = in2
            if tot_d2 > 0:
                c2_seek = min(c2_seek, max(0.0, tot_d2 - 0.2))

            # Clip 2 duration: cover the mosh length plus post-cut tail
            c2_extract_dur = max(mosh_len + post_len, 1.0)
            if dur2 > 0:
                c2_extract_dur = min(dur2, c2_extract_dur)
            if tot_d2 > 0 and (c2_seek + c2_extract_dur) > tot_d2:
                c2_extract_dur = max(0.3, tot_d2 - c2_seek)

            # Detect timeline frame rate
            fps = 30.0
            resolve = get_resolve()
            if resolve:
                try:
                    tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
                    if tl:
                        tf = tl.GetSetting("timelineFrameRate")
                        if tf: fps = float(tf)
                except Exception:
                    pass

            # Optional Audio Processing (crossfade between trims)
            has_aud = self.include_audio.get() and has_audio_stream(c1) and has_audio_stream(c2)
            if has_aud:
                temp_audio = os.path.join(base_dir, f"__tmp_audio_{name1}_{name2}.m4a")
                cmd_aud = (
                    f'ffmpeg -y '
                    f'-ss {c1_seek:.3f} -t {c1_extract_dur:.3f} -i "{c1}" '
                    f'-ss {c2_seek:.3f} -t {c2_extract_dur:.3f} -i "{c2}" '
                    f'-filter_complex "[0:a][1:a]acrossfade=d=0.4:c1=tri:c2=tri[aout]" -map "[aout]" -c:a aac -b:a 192k "{temp_audio}"'
                )
                subprocess.call(cmd_aud, shell=True)

            # Step 2: Encode Clip 1 and Clip 2 SEPARATELY into intermediate MPEG-4 AVI bitstreams
            # Crucial: Clip 2 starts with an independent I-frame, and has its recovery I-frame placed exactly at mosh_len!
            self.root.after(0, lambda: self.progress.configure(value=25))
            self.status_var.set("Step 2/5: Encoding intermediate MPEG-4 bitstreams (GOP-aligned)...")

            recovery_gop = max(10, int(round(mosh_len * fps)))
            temp_c1_avi = os.path.join(base_dir, f"__tmp_c1_{name1}.avi")
            temp_c2_avi = os.path.join(base_dir, f"__tmp_c2_{name2}.avi")

            cmd_c1 = (
                f'ffmpeg -y -ss {c1_seek:.3f} -t {c1_extract_dur:.3f} -i "{c1}" '
                f'-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}" '
                f'-bf 0 -g 1000 -b:v 14000k -vcodec mpeg4 -an "{temp_c1_avi}"'
            )
            cmd_c2 = (
                f'ffmpeg -y -ss {c2_seek:.3f} -t {c2_extract_dur:.3f} -i "{c2}" '
                f'-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}" '
                f'-bf 0 -g {recovery_gop} -b:v 14000k -vcodec mpeg4 -an "{temp_c2_avi}"'
            )
            subprocess.call(cmd_c1, shell=True)
            subprocess.call(cmd_c2, shell=True)

            if not os.path.exists(temp_c1_avi) or not os.path.exists(temp_c2_avi):
                raise Exception("Failed to encode intermediate MPEG-4 video streams.")

            # Measure exact frame count of Clip 1
            c1_frames = count_video_frames(temp_c1_avi, fps)

            # Step 3: Losslessly join intermediate containers into joined.avi via concat demuxer
            self.root.after(0, lambda: self.progress.configure(value=45))
            self.status_var.set("Step 3/5: Concatenating bitstreams with cut keyframe...")
            temp_list_txt = os.path.join(base_dir, f"__tmp_list_{name1}_{name2}.txt")
            temp_joined_avi = os.path.join(base_dir, f"__tmp_joined_{name1}_{name2}.avi")

            with open(temp_list_txt, "w", encoding="utf-8") as f:
                f.write(f"file '{temp_c1_avi.replace(os.sep, '/')}'\n")
                f.write(f"file '{temp_c2_avi.replace(os.sep, '/')}'\n")

            cmd_join = f'ffmpeg -y -f concat -safe 0 -i "{temp_list_txt}" -c copy "{temp_joined_avi}"'
            subprocess.call(cmd_join, shell=True)

            if not os.path.exists(temp_joined_avi):
                raise Exception("Failed to concatenate bitstreams into joined AVI.")

            # Step 4: Binary datamosh surgery at the exact cut frame (c1_frames)
            self.root.after(0, lambda: self.progress.configure(value=65))
            self.status_var.set(f"Step 4/5: Applying {mode} surgery at frame {c1_frames}...")
            temp_corrupt = os.path.join(base_dir, f"__corrupt_{name1}_{name2}.avi")

            cut_frame = c1_frames
            if "Classic Motion Melt" in mode:
                # Authentic Avidemux datamosh: Drop only the cut I-frame!
                classic_new.Datamosh(temp_joined_avi, temp_corrupt, s=cut_frame - 1, e=cut_frame + 2, fps=fps)
            elif "Kinetic Stutter" in mode:
                # Repeat motion frames at cut for rhythmic punch
                burst = max(2, min(delta, 8))
                repeat.Datamosh(temp_joined_avi, temp_corrupt, s=cut_frame, e=cut_frame + 12, p=burst, fps=fps)
            elif "Tomato Bloom" in mode:
                # Expanding vector bloom explosion
                tomato.mosh(infile=temp_joined_avi, outfile=temp_corrupt, m="bloom", c=delta, n=cut_frame, k=0.6, a=0, f=1)
            elif "Macroblock Glide" in mode:
                # Smear macroblocks along motion vectors
                pymodes.library.glide(delta, temp_joined_avi, temp_corrupt)
            elif "Echo Drift" in mode:
                # Motion drift and ghosting
                pymodes.library.process_streams(temp_joined_avi, temp_corrupt, mid=0.5)
            elif "Tomato Pulse" in mode:
                # Periodic glitch waves
                tomato.mosh(infile=temp_joined_avi, outfile=temp_corrupt, m="pulse", c=delta, n=5, k=0.7, a=0, f=1)
            elif "Tomato Void" in mode:
                # Automosh cut
                tomato.mosh(infile=temp_joined_avi, outfile=temp_corrupt, m="void", c=delta, n=cut_frame, k=0.6, a=0, f=1)
            else:
                classic_new.Datamosh(temp_joined_avi, temp_corrupt, s=cut_frame - 1, e=cut_frame + 2, fps=fps)

            if not os.path.exists(temp_corrupt):
                raise Exception("Datamosh surgery failed to create corrupted bitstream.")

            # Step 5: Decode with libavcodec to bake glitch into pristine H.264
            self.root.after(0, lambda: self.progress.configure(value=85))
            self.status_var.set("Step 5/5: Decoding & baking glitch into clean H.264...")

            if has_aud and os.path.exists(temp_audio):
                cmd_bake = f'ffmpeg -y -i "{temp_corrupt}" -i "{temp_audio}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a copy -shortest "{out_trans}"'
            else:
                cmd_bake = f'ffmpeg -y -i "{temp_corrupt}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an "{out_trans}"'

            subprocess.call(cmd_bake, shell=True)

            if not os.path.exists(out_trans):
                raise Exception("Failed to bake transition video with FFmpeg.")

            # Step 6: Automatically import and optionally place on Timeline
            placed_msg = ""
            if self.auto_import.get():
                self.status_var.set("Importing transition to DaVinci Media Pool...")
                resolve = get_resolve()
                if resolve:
                    pm = resolve.GetProjectManager()
                    proj = pm.GetCurrentProject()
                    if proj:
                        mp = proj.GetMediaPool()
                        imported = mp.ImportMedia([out_trans])

                        # Automated Timeline Placement on upper track
                        if self.auto_place_timeline.get() and imported and len(imported) > 0:
                            tl = proj.GetCurrentTimeline()
                            if tl:
                                try:
                                    tl_fps = 24.0
                                    try:
                                        t_fps = tl.GetSetting("timelineFrameRate")
                                        if t_fps: tl_fps = float(t_fps)
                                    except Exception: pass

                                    tot_dur_frames = int(round((c1_extract_dur + c2_extract_dur) * tl_fps))
                                    cut_frame_tl = self.c1_timeline_end if self.c1_timeline_end > 0 else tl.GetStart()
                                    record_frame = max(0, int(round(cut_frame_tl - (c1_extract_dur * tl_fps))))
                                    target_track = max(1, self.c1_track + 1)

                                    # Ensure upper track exists
                                    curr_tracks = tl.GetTrackCount("video")
                                    while curr_tracks < target_track:
                                        tl.AddTrack("video")
                                        curr_tracks = tl.GetTrackCount("video")

                                    clip_info = {
                                        "mediaPoolItem": imported[0],
                                        "startFrame": 0,
                                        "endFrame": tot_dur_frames,
                                        "trackIndex": target_track,
                                        "recordFrame": record_frame
                                    }
                                    res_items = mp.AppendToTimeline([clip_info])
                                    if res_items and len(res_items) > 0:
                                        placed_msg = f"\n\n✨ Automatically placed on Timeline Track V{target_track} centered over cut!"
                                except Exception as place_err:
                                    pass

            self.root.after(0, lambda: self.progress.configure(value=100))
            self.status_var.set("Datamosh Transition Created Successfully!")
            self.root.after(0, lambda: messagebox.showinfo(
                "Transition Complete!",
                f"Datamosh transition generated successfully:\n\n{out_trans}\n\nIt is now available in your DaVinci Resolve Media Pool.{placed_msg}"
            ))

        except Exception as ex:
            self.status_var.set(f"Error: {str(ex)}")
            self.root.after(0, lambda: messagebox.showerror("Transition Error", str(ex)))
        finally:
            for p in [temp_c1_avi, temp_c2_avi, temp_list_txt, temp_joined_avi, temp_corrupt, temp_audio]:
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass

    # -------------------------------------------------------------
    # SINGLE CLIP EXECUTION
    # -------------------------------------------------------------
    def run_single(self):
        c = self.single_clip.get()
        if not c or not os.path.exists(c):
            messagebox.showerror("Error", "Please select a valid clip first.")
            return

        self.progress["value"] = 10
        self.status_var.set("Processing single clip...")

        t = threading.Thread(target=self._single_thread, args=(c,))
        t.daemon = True
        t.start()

    def _single_thread(self, in_path):
        temp_avi = ""
        temp_corrupt = ""
        try:
            base_dir = os.path.dirname(in_path)
            name = os.path.splitext(os.path.basename(in_path))[0]
            out_file = os.path.join(base_dir, f"{name}_datamoshed.mp4")

            s = self.single_start.get()
            e = self.single_end.get()
            p = self.single_delta.get()
            m = self.single_mode.get()

            dur_trim = max(0.3, e - s)

            self.root.after(0, lambda: self.progress.configure(value=35))
            self.status_var.set(f"Step 1/3: Slicing trim ({s:.2f}s to {e:.2f}s) into MPEG-4 container...")
            temp_avi = os.path.join(base_dir, f"__tmp_{name}.avi")
            cmd_convert = f'ffmpeg -y -ss {s:.3f} -t {dur_trim:.3f} -i "{in_path}" -bf 0 -g 1000 -b:v 12000k -vcodec mpeg4 -an "{temp_avi}"'
            subprocess.call(cmd_convert, shell=True)

            self.root.after(0, lambda: self.progress.configure(value=65))
            self.status_var.set("Step 2/3: Corrupting I-frames and repeating P-frames...")
            temp_corrupt = os.path.join(base_dir, f"__corrupt_{name}.avi")

            if "Classic" in m:
                classic_new.Datamosh(temp_avi, temp_corrupt, s=int(s * 30), e=int(e * 30), fps=30)
            elif "Repeat" in m or "Kinetic" in m:
                repeat.Datamosh(temp_avi, temp_corrupt, s=int(s * 30), e=int(e * 30), p=p, fps=30)
            elif "Glide" in m:
                pymodes.library.glide(p, temp_avi, temp_corrupt)
            elif "Echo" in m:
                pymodes.library.process_streams(temp_avi, temp_corrupt, mid=0.5)
            elif "Bloom" in m:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="bloom", c=p, n=int(s * 30), k=0.6, a=0, f=1)
            elif "Pulse" in m:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="pulse", c=p, n=5, k=0.7, a=0, f=1)
            elif "Void" in m:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="void", c=p, n=0, k=0.6, a=0, f=1)
            else:
                classic_new.Datamosh(temp_avi, temp_corrupt, s=int(s * 30), e=int(e * 30), fps=30)

            self.root.after(0, lambda: self.progress.configure(value=85))
            self.status_var.set("Step 3/3: Re-encoding with libavcodec to bake glitch...")
            cmd_fix = f'ffmpeg -y -i "{temp_corrupt}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p "{out_file}"'
            subprocess.call(cmd_fix, shell=True)

            if self.auto_import.get():
                resolve = get_resolve()
                if resolve:
                    pm = resolve.GetProjectManager()
                    proj = pm.GetCurrentProject()
                    if proj:
                        proj.GetMediaPool().ImportMedia([out_file])

            self.root.after(0, lambda: self.progress.configure(value=100))
            self.status_var.set("Datamosh Completed Successfully!")
            self.root.after(0, lambda: messagebox.showinfo("Completed", f"Datamoshed clip ready:\n{out_file}"))

        except Exception as ex:
            self.status_var.set(f"Error: {str(ex)}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(ex)))
        finally:
            if temp_avi and os.path.exists(temp_avi):
                try: os.remove(temp_avi)
                except Exception: pass
            if temp_corrupt and os.path.exists(temp_corrupt):
                try: os.remove(temp_corrupt)
                except Exception: pass


def main():
    root = tk.Tk()
    app = DatamosherResolveApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
