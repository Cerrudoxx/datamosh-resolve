#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Datamosher Pro — DaVinci Resolve Integration
============================================
A native DaVinci Resolve integration for authentic video datamoshing.

Features:
1. Intelligent Clip Detection:
   - Automatically detects 2 contiguous clips at the timeline playhead cut point.
   - Detects clips selected in the Media Pool.
   - Provides an interactive dropdown of all timeline video clips.
2. 2-Clip Datamosh Transitions:
   - Performs binary I-frame stripping at the exact transition cut point.
   - Glitches motion vectors across clips using MPEG-4 / AVI bitstream corruption.
3. Single Clip Datamosh:
   - Applies motion trails, velocity explosions, and frame repetitions by time range.
4. Automatic Media Pool Import:
   - Seamlessly imports rendered glitched media directly back into DaVinci Resolve.

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

# Also ensure DaVinci Fusion Modules directory is in sys.path
appdata = os.getenv("APPDATA")
if appdata:
    fusion_modules = os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion", "Modules")
    if os.path.isdir(fusion_modules) and fusion_modules not in sys.path:
        sys.path.insert(0, fusion_modules)

# Import datamoshing engines
try:
    from DatamoshLib.Original import classic, repeat
    from DatamoshLib.Tomato import tomato
    MOTORS_OK = True
    MOTOR_ERR = ""
except Exception as e:
    MOTORS_OK = False
    MOTOR_ERR = str(e)



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
        self.root.title("Datamosher Pro — DaVinci Resolve")
        self.root.geometry("680x720")
        self.root.minsize(620, 660)
        self.root.configure(bg="#181818")

        # Configure dark theme styles
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#181818", foreground="#ffffff", font=("Segoe UI", 10))
        self.style.configure("TLabel", background="#181818", foreground="#ffffff")
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#00b4d8")
        self.style.configure("TNotebook", background="#181818", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#282828", foreground="#ffffff", padding=[14, 7], font=("Segoe UI", 10, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", "#0077b6")], foreground=[("selected", "#ffffff")])
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), background="#2e2e2e", foreground="#ffffff")
        self.style.map("TButton", background=[("active", "#3f3f3f")])
        self.style.configure("Detect.TButton", font=("Segoe UI", 9, "bold"), background="#023e8a", foreground="#ffffff")
        self.style.map("Detect.TButton", background=[("active", "#0077b6")])
        self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), background="#d90429", foreground="#ffffff")
        self.style.map("Action.TButton", background=[("active", "#ef233c")])

        # State variables for 2-clip transition
        self.trans_clip1 = tk.StringVar(value="")
        self.trans_clip2 = tk.StringVar(value="")
        self.trans_duration = tk.DoubleVar(value=2.0)
        self.trans_delta = tk.IntVar(value=8)
        self.trans_mode = tk.StringVar(value="Classic (I-Frame Drop at Cut)")

        # State variables for single clip datamosh
        self.single_clip = tk.StringVar(value="")
        self.single_mode = tk.StringVar(value="Classic (I-Frame Drop)")
        self.single_start = tk.DoubleVar(value=0.0)
        self.single_end = tk.DoubleVar(value=2.5)
        self.single_delta = tk.IntVar(value=6)

        # Cache of detected timeline clips
        self.timeline_clips_cache = []

        # Global options
        self.auto_import = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready.")

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
        title = ttk.Label(head_frame, text="DATAMOSHER PRO — DaVinci Resolve", style="Header.TLabel")
        title.pack(anchor="w")
        sub = ttk.Label(head_frame, text="True Bitstream Datamoshing via MPEG-4 / AVI Binary Corruption",
                        font=("Segoe UI", 9), foreground="#888888")
        sub.pack(anchor="w")

        # Notebook tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=5)

        # TAB 1: 2-Clip Transition
        self.tab_trans = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_trans, text=" 🔀 2-Clip Transition ")
        self.build_trans_tab()

        # TAB 2: Single Clip
        self.tab_single = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_single, text=" 🎬 Single Clip ")
        self.build_single_tab()

        # Footer with status label and credits link
        footer = ttk.Frame(self.root, padding=12)
        footer.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(footer, mode="indeterminate")

        lbl_status = ttk.Label(footer, textvariable=self.status_var, foreground="#00ff88", font=("Segoe UI", 10, "bold"))
        lbl_status.pack(anchor="w", pady=(0, 6))

        btn_orig = ttk.Button(footer, text="🌐 Based on Datamosher Pro by Akash Bora (Visit GitHub)",
                              command=lambda: webbrowser.open("https://github.com/Akascape/Datamosher-Pro"))
        btn_orig.pack(fill="x")

    # -------------------------------------------------------------
    # TAB: 2-CLIP TRANSITION
    # -------------------------------------------------------------
    def build_trans_tab(self):
        # Detection action buttons
        det_bar = ttk.Frame(self.tab_trans)
        det_bar.pack(fill="x", pady=(0, 10))

        btn_cut = ttk.Button(det_bar, text="📍 Detect 2 Clips at Cut (Playhead)", style="Detect.TButton",
                             command=self.detect_from_timeline_playhead)
        btn_cut.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_pool = ttk.Button(det_bar, text="📁 Use 2 Selected Media Pool Clips", style="Detect.TButton",
                              command=self.detect_from_media_pool)
        btn_pool.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Outgoing Clip (A)
        f1 = ttk.LabelFrame(self.tab_trans, text=" 1. Outgoing Clip (Frozen Base Canvas) ", padding=8)
        f1.pack(fill="x", pady=4)

        self.cmb_clip1 = ttk.Combobox(f1, state="readonly", font=("Segoe UI", 9))
        self.cmb_clip1.pack(fill="x", pady=(0, 4))
        self.cmb_clip1.bind("<<ComboboxSelected>>", self.on_clip1_dropdown_select)

        r1 = ttk.Frame(f1)
        r1.pack(fill="x")
        ttk.Entry(r1, textvariable=self.trans_clip1, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(r1, text="Browse...", command=lambda: self.browse(self.trans_clip1)).pack(side="right")

        # Incoming Clip (B)
        f2 = ttk.LabelFrame(self.tab_trans, text=" 2. Incoming Clip (Motion tearing into Clip A) ", padding=8)
        f2.pack(fill="x", pady=4)

        self.cmb_clip2 = ttk.Combobox(f2, state="readonly", font=("Segoe UI", 9))
        self.cmb_clip2.pack(fill="x", pady=(0, 4))
        self.cmb_clip2.bind("<<ComboboxSelected>>", self.on_clip2_dropdown_select)

        r2 = ttk.Frame(f2)
        r2.pack(fill="x")
        ttk.Entry(r2, textvariable=self.trans_clip2, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(r2, text="Browse...", command=lambda: self.browse(self.trans_clip2)).pack(side="right")

        # Transition Settings
        p_frame = ttk.LabelFrame(self.tab_trans, text=" Cut Glitch Settings ", padding=10)
        p_frame.pack(fill="x", pady=8)

        # Effect duration
        row1 = ttk.Frame(p_frame)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Cut Glitch Duration:").pack(side="left")
        spn_dur = ttk.Spinbox(row1, from_=0.5, to=10.0, increment=0.25, textvariable=self.trans_duration, width=6)
        spn_dur.pack(side="right")
        ttk.Label(row1, text="seconds", foreground="#888888").pack(side="right", padx=6)

        # Delta multiplier
        row2 = ttk.Frame(p_frame)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Motion Trail Multiplier (Delta):").pack(side="left")
        spn_del = ttk.Spinbox(row2, from_=1, to=50, increment=1, textvariable=self.trans_delta, width=6)
        spn_del.pack(side="right")

        # Transition Mode
        row3 = ttk.Frame(p_frame)
        row3.pack(fill="x", pady=4)
        ttk.Label(row3, text="Transition Algorithm:").pack(side="left")
        cmb_tm = ttk.Combobox(row3, textvariable=self.trans_mode, state="readonly", width=36,
                              values=[
                                  "Classic (I-Frame Drop at Cut)",
                                  "Bloom (Explosion & Trail at Cut)",
                                  "Repeat (Motion Loop at Cut)"
                              ])
        cmb_tm.pack(side="right")

        # Execute Button
        btn_run = ttk.Button(self.tab_trans, text="💥 CREATE DATAMOSH TRANSITION", style="Action.TButton",
                             command=self.run_transition)
        btn_run.pack(fill="x", pady=(10, 4), ipady=6)

    # -------------------------------------------------------------
    # TAB: SINGLE CLIP
    # -------------------------------------------------------------
    def build_single_tab(self):
        f1 = ttk.LabelFrame(self.tab_single, text=" Target Video Clip ", padding=8)
        f1.pack(fill="x", pady=4)
        ttk.Entry(f1, textvariable=self.single_clip, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(f1, text="Browse...", command=lambda: self.browse(self.single_clip)).pack(side="right")

        btn_detect = ttk.Button(self.tab_single, text="⚡ Detect Selected Clip in DaVinci",
                                style="Detect.TButton", command=self.detect_single_clip)
        btn_detect.pack(fill="x", pady=6)

        # Datamoshing Mode
        m_frame = ttk.LabelFrame(self.tab_single, text=" Datamoshing Algorithm ", padding=8)
        m_frame.pack(fill="x", pady=6)
        modes = [
            "Classic (I-Frame Drop)",
            "Bloom (Velocity Multiplier)",
            "Void (Automosh Cut Drop)",
            "Repeat (P-Frame Loop)"
        ]
        ttk.Combobox(m_frame, textvariable=self.single_mode, values=modes, state="readonly").pack(fill="x", pady=2)

        # Time Range
        r_frame = ttk.LabelFrame(self.tab_single, text=" Effect Time Range ", padding=8)
        r_frame.pack(fill="x", pady=6)
        rw1 = ttk.Frame(r_frame)
        rw1.pack(fill="x", pady=3)
        ttk.Label(rw1, text="Start Second:").pack(side="left")
        ttk.Spinbox(rw1, from_=0.0, to=999.0, increment=0.1, textvariable=self.single_start, width=8).pack(side="left", padx=10)
        ttk.Label(rw1, text="End Second:").pack(side="left")
        ttk.Spinbox(rw1, from_=0.1, to=999.0, increment=0.1, textvariable=self.single_end, width=8).pack(side="left", padx=10)

        rw2 = ttk.Frame(r_frame)
        rw2.pack(fill="x", pady=3)
        ttk.Label(rw2, text="P-Frame Multiplier (Delta):").pack(side="left")
        ttk.Spinbox(rw2, from_=1, to=50, increment=1, textvariable=self.single_delta, width=8).pack(side="left", padx=10)

        # Execute Button
        btn_single_mosh = ttk.Button(self.tab_single, text="💥 DATAMOSH THIS CLIP", style="Action.TButton",
                                     command=self.run_single)
        btn_single_mosh.pack(fill="x", pady=15, ipady=6)

    def browse(self, var):
        f = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv"), ("All files", "*.*")])
        if f:
            var.set(f)

    def on_clip1_dropdown_select(self, event=None):
        idx = self.cmb_clip1.current()
        if 0 <= idx < len(self.timeline_clips_cache):
            self.trans_clip1.set(self.timeline_clips_cache[idx]["file_path"])

    def on_clip2_dropdown_select(self, event=None):
        idx = self.cmb_clip2.current()
        if 0 <= idx < len(self.timeline_clips_cache):
            self.trans_clip2.set(self.timeline_clips_cache[idx]["file_path"])

    # -------------------------------------------------------------
    # DAVINCI RESOLVE TIMELINE CLIP DETECTION
    # -------------------------------------------------------------
    def get_all_timeline_clips(self, timeline):
        """
        Scans all video tracks on the timeline and returns sorted clips.
        """
        clips = []
        try:
            track_count = timeline.GetTrackCount("video")
            for t in range(1, track_count + 1):
                items = timeline.GetItemListInTrack("video", t) or []
                for it in items:
                    fp = get_item_file_path(it)
                    if fp:
                        name = it.GetName() or os.path.basename(fp)
                        start = it.GetStart()
                        end = it.GetEnd()
                        clips.append({
                            "item": it,
                            "name": name,
                            "file_path": fp,
                            "start": start,
                            "end": end,
                            "track": t
                        })
            # Sort by timeline start position, then by track number
            clips.sort(key=lambda c: (c["start"], c["track"]))
        except Exception:
            pass
        return clips

    def update_dropdowns(self, clips):
        self.timeline_clips_cache = clips
        options = [f"{i+1}. {c['name']} (V{c['track']}, start: {c['start']})" for i, c in enumerate(clips)]
        self.cmb_clip1["values"] = options
        self.cmb_clip2["values"] = options

    def detect_from_timeline_playhead(self):
        """
        Detects 2 contiguous clips at the cut point under the playhead.
        Falls back to adjacent timeline clips or first clip if single.
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

            # Check clip currently under playhead
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

            # Fall back to first 2 contiguous clips if playhead is ambiguous
            if not c1 or not c2:
                if len(clips) >= 2:
                    c1 = clips[0]
                    c2 = clips[1]
                elif len(clips) == 1:
                    self.single_clip.set(clips[0]["file_path"])
                    self.trans_clip1.set(clips[0]["file_path"])
                    self.status_var.set(f"Detected 1 clip: {clips[0]['name']}. Please select the second clip.")
                    return

            if c1 and c2:
                self.trans_clip1.set(c1["file_path"])
                self.trans_clip2.set(c2["file_path"])
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
            if not proj:
                return
            mp = proj.GetMediaPool()
            if not mp:
                return

            selected = mp.GetSelectedClips() or []
            files = []
            for item in selected:
                fp = get_item_file_path(item)
                if fp:
                    files.append(fp)

            if len(files) >= 2:
                self.trans_clip1.set(files[0])
                self.trans_clip2.set(files[1])
                self.status_var.set(f"✅ 2 clips loaded from Media Pool: {os.path.basename(files[0])} ➜ {os.path.basename(files[1])}")
            elif len(files) == 1:
                self.trans_clip1.set(files[0])
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
        Detects the clip under the playhead for single-clip datamoshing.
        """
        resolve = get_resolve()
        if not resolve:
            return
        try:
            pm = resolve.GetProjectManager()
            proj = pm.GetCurrentProject()
            if not proj:
                return
            tl = proj.GetCurrentTimeline()
            if not tl:
                return
            it = tl.GetCurrentVideoItem()
            fp = get_item_file_path(it) if it else None
            if fp:
                self.single_clip.set(fp)
                self.status_var.set(f"Detected clip: {os.path.basename(fp)}")
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

        self.progress.pack(fill="x", padx=15, pady=6)
        self.progress.start(10)
        self.status_var.set("Creating Datamosh transition...")

        t = threading.Thread(target=self._transition_thread, args=(c1, c2))
        t.daemon = True
        t.start()

    def _transition_thread(self, c1, c2):
        temp_avi = ""
        temp_corrupt = ""
        try:
            base_dir = os.path.dirname(c1)
            name1 = os.path.splitext(os.path.basename(c1))[0]
            name2 = os.path.splitext(os.path.basename(c2))[0]
            out_trans = os.path.join(base_dir, f"Transition_{name1}_to_{name2}_datamoshed.mp4")

            self.status_var.set("Step 1/4: Analyzing clip durations...")
            d1 = get_video_duration(c1)
            if d1 <= 0.0:
                d1 = 3.0

            mosh_len = self.trans_duration.get()
            mosh_start = max(0.0, d1 - 0.05)  # Exact cut point
            mosh_end = d1 + mosh_len
            delta = self.trans_delta.get()
            mode = self.trans_mode.get()

            # Step 2: Concatenate both clips into a clean MPEG-4 AVI container without B-frames
            self.status_var.set("Step 2/4: Joining clips into MPEG-4 intermediate container...")
            temp_avi = os.path.join(base_dir, f"__tmp_joined_{name1}_{name2}.avi")

            cmd_join = (
                f'ffmpeg -y -i "{c1}" -i "{c2}" '
                f'-filter_complex "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0]; '
                f'[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1]; '
                f'[v0][v1]concat=n=2:v=1:a=0[v]" -map "[v]" -bf 0 -g 1000 -b:v 14000k -vcodec mpeg4 -an "{temp_avi}"'
            )
            subprocess.call(cmd_join, shell=True)

            if not os.path.exists(temp_avi):
                raise Exception("Failed to concatenate clips with FFmpeg.")

            # Step 3: Binary I-frame surgery at the exact cut point
            self.status_var.set(f"Step 3/4: Stripping I-Frame at cut ({round(d1, 2)}s)...")
            temp_corrupt = os.path.join(base_dir, f"__corrupt_trans_{name1}_{name2}.avi")

            if "Bloom" in mode:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="bloom", c=delta, n=int(d1 * 30),
                            k=0.7, a=0, f=1)
            elif "Repeat" in mode:
                repeat.Datamosh(temp_avi, temp_corrupt, s=int(mosh_start * 30), e=int(mosh_end * 30), p=delta, fps=30)
            else:
                # Classic I-Frame drop at cut
                classic.Datamosh(temp_avi, temp_corrupt, s=mosh_start, e=mosh_end, p=delta, fps=30)

            if not os.path.exists(temp_corrupt):
                raise Exception("Binary surgery failed to produce corrupted bitstream.")

            # Step 4: Decode with libavcodec to bake the decompression glitch into clean H.264
            self.status_var.set("Step 4/4: Re-encoding with libavcodec to bake glitch...")
            cmd_bake = f'ffmpeg -y -i "{temp_corrupt}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p "{out_trans}"'
            subprocess.call(cmd_bake, shell=True)

            if not os.path.exists(out_trans):
                raise Exception("Failed to bake transition video with FFmpeg.")

            # Step 5: Automatically import into DaVinci Resolve Media Pool
            if self.auto_import.get():
                self.status_var.set("Importing transition to DaVinci Media Pool...")
                resolve = get_resolve()
                if resolve:
                    pm = resolve.GetProjectManager()
                    proj = pm.GetCurrentProject()
                    if proj:
                        mp = proj.GetMediaPool()
                        mp.ImportMedia([out_trans])

            self.status_var.set("Datamosh Transition Created Successfully!")
            self.root.after(0, lambda: messagebox.showinfo(
                "Transition Complete!",
                f"Datamosh transition generated successfully:\n\n{out_trans}\n\nIt is now available in your DaVinci Resolve Media Pool."
            ))

        except Exception as ex:
            self.status_var.set(f"Error: {str(ex)}")
            self.root.after(0, lambda: messagebox.showerror("Transition Error", str(ex)))
        finally:
            # Clean up intermediate temporary files
            if temp_avi and os.path.exists(temp_avi):
                try:
                    os.remove(temp_avi)
                except Exception:
                    pass
            if temp_corrupt and os.path.exists(temp_corrupt):
                try:
                    os.remove(temp_corrupt)
                except Exception:
                    pass
            self.progress.stop()
            self.progress.pack_forget()

    # -------------------------------------------------------------
    # SINGLE CLIP EXECUTION
    # -------------------------------------------------------------
    def run_single(self):
        c = self.single_clip.get()
        if not c or not os.path.exists(c):
            messagebox.showerror("Error", "Please select a valid clip first.")
            return

        self.progress.pack(fill="x", padx=15, pady=6)
        self.progress.start(10)
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

            self.status_var.set("Step 1/3: Preparing intermediate MPEG-4 AVI container...")
            temp_avi = os.path.join(base_dir, f"__tmp_{name}.avi")
            cmd_convert = f'ffmpeg -y -i "{in_path}" -bf 0 -g 1000 -b:v 12000k -vcodec mpeg4 -an "{temp_avi}"'
            subprocess.call(cmd_convert, shell=True)

            self.status_var.set("Step 2/3: Corrupting I-frames and repeating P-frames...")
            temp_corrupt = os.path.join(base_dir, f"__corrupt_{name}.avi")

            m = self.single_mode.get()
            s = self.single_start.get()
            e = self.single_end.get()
            p = self.single_delta.get()

            if "Bloom" in m:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="bloom", c=p, n=int(s * 30),
                            k=0.7, a=0, f=1)
            elif "Repeat" in m:
                repeat.Datamosh(temp_avi, temp_corrupt, s=int(s * 30), e=int(e * 30), p=p, fps=30)
            elif "Void" in m:
                tomato.mosh(infile=temp_avi, outfile=temp_corrupt, m="void", c=p, n=int(s * 30),
                            k=0.7, a=0, f=1)
            else:
                classic.Datamosh(temp_avi, temp_corrupt, s=s, e=e, p=p, fps=30)

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

            self.status_var.set("Datamosh Completed Successfully!")
            self.root.after(0, lambda: messagebox.showinfo("Completed", f"Datamoshed clip ready:\n{out_file}"))

        except Exception as ex:
            self.status_var.set(f"Error: {str(ex)}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(ex)))
        finally:
            if temp_avi and os.path.exists(temp_avi):
                try:
                    os.remove(temp_avi)
                except Exception:
                    pass
            if temp_corrupt and os.path.exists(temp_corrupt):
                try:
                    os.remove(temp_corrupt)
                except Exception:
                    pass
            self.progress.stop()
            self.progress.pack_forget()


def main():
    root = tk.Tk()
    app = DatamosherResolveApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
