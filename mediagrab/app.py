"""MediaGrab graphical interface (Tkinter).

The layout follows the original sketch:
  * left — service selection panel;
  * top — the link input row, the "➜" download button and the "…"
    folder picker (the folder is remembered between runs);
  * below the input — the mp3/mp4 switch with the active format
    highlighted in green; clicking it slides out a quality panel;
  * below that — download history and current status: finished
    items get a check mark.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import CONFIG_DIR, COOKIES_DIR, Config
from .engine import MP3_BITRATES, MP4_QUALITIES, DownloadManager
from .updater import update_ytdlp, ytdlp_version
from .version import check_remote, local_version
from . import services

# --- palette (light theme, green accent) --------------------------------
BG = "#f5f9f5"          # window background
PANEL = "#e8f2e8"       # sidebar
CARD = "#ffffff"        # input fields / list
ACCENT = "#2e7d32"      # primary green
ACCENT_DARK = "#1b5e20"
ACCENT_SOFT = "#c8e6c9"
TEXT = "#1c231c"
MUTED = "#5f6f5f"
ERROR = "#c62828"

AUTO_ID = "__auto__"

STATUS_QUEUED = "⏳ queued"
STATUS_PROCESSING = "⚙ processing…"
STATUS_DONE = "✓ downloaded"
STATUS_ERROR = "✗ error"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaGrab — mp3/mp4 downloader")
        self.geometry("1020x600")
        self.minsize(860, 480)
        self.configure(bg=BG)

        self.config_store = Config()
        self.manager = DownloadManager()
        self.selected_service = AUTO_ID
        self.current_format = self.config_store.format
        self.quality_panel_visible = False
        self.tasks = {}          # task_id -> {"item": tree row id, "entry": history dict}
        self.row_entries = {}    # tree row id -> history entry dict
        self.service_buttons = {}
        self.format_buttons = {}
        self.quality_buttons = {}

        self.latest_version = None    # newer version on GitHub (if any)
        self._version_note = None     # background check result
        self._version_shown = False

        self._build_statusbar()
        self._build_sidebar()
        self._build_main_area()
        self._load_history()
        self._check_dependencies()
        self.after(150, self._poll_events)
        threading.Thread(target=self._check_updates_bg,
                         daemon=True).start()

    # ------------------------------------------------------------------
    # interface construction
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=PANEL, width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Service", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(16, 6))

        self._add_service_button(sidebar, AUTO_ID, "Auto (by link)")
        for plugin in services.all_plugins():
            self._add_service_button(sidebar, plugin.id, plugin.name)

        tk.Label(sidebar, text="+ add your own:\nsee docs/ADDING_SERVICES.md",
                 bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8),
                 justify="left", anchor="w").pack(
            side="bottom", fill="x", padx=14, pady=12)

    def _add_service_button(self, parent, service_id, label):
        btn = tk.Label(parent, text=label, bg=PANEL, fg=TEXT, anchor="w",
                       padx=14, pady=7, cursor="hand2",
                       font=("TkDefaultFont", 10))
        btn.pack(fill="x", padx=8, pady=2)
        btn.bind("<Button-1>",
                 lambda _e, sid=service_id: self._select_service(sid))
        self.service_buttons[service_id] = btn
        if service_id == self.selected_service:
            self._style_service_buttons()

    def _build_main_area(self):
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        # --- link input row -------------------------------------------
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x")

        self.url_var = tk.StringVar()
        entry = tk.Entry(row, textvariable=self.url_var,
                         font=("TkDefaultFont", 12), bg=CARD, fg=TEXT,
                         relief="solid", bd=1,
                         highlightthickness=1, highlightcolor=ACCENT,
                         highlightbackground="#b8ccb8")
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        entry.bind("<Return>", lambda _e: self._start_download())
        entry.insert(0, "")
        self.url_entry = entry
        self._set_placeholder()
        # Ctrl+V/C/X/A on any keyboard layout (see _on_ctrl_key)
        entry.bind("<Control-KeyPress>", self._on_ctrl_key)
        entry.bind("<Shift-Insert>", lambda _e: self._paste_into_entry())
        self.bind("<Control-KeyPress>", self._on_ctrl_key_global)

        self.download_btn = tk.Button(
            row, text="➜", font=("TkDefaultFont", 14, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_DARK,
            activeforeground="white", relief="flat", cursor="hand2",
            width=4, command=self._start_download)
        self.download_btn.pack(side="left", padx=(0, 8))

        folder_btn = tk.Button(
            row, text="…", font=("TkDefaultFont", 12, "bold"),
            bg=CARD, fg=TEXT, relief="solid", bd=1, cursor="hand2",
            width=3, command=self._choose_folder)
        folder_btn.pack(side="left")

        profile_btn = tk.Button(
            row, text="👤", font=("TkDefaultFont", 12),
            bg=CARD, fg=ACCENT_DARK, relief="solid", bd=1, cursor="hand2",
            width=3, command=self._show_profile)
        profile_btn.pack(side="left", padx=(8, 0))

        # --- format switch --------------------------------------------
        fmt_row = tk.Frame(main, bg=BG)
        fmt_row.pack(fill="x", pady=(10, 0))
        tk.Frame(fmt_row, bg=BG).pack(side="left", expand=True)  # push right
        for fmt in ("mp3", "mp4"):
            btn = tk.Button(
                fmt_row, text=fmt, font=("TkDefaultFont", 11, "bold"),
                relief="flat", bd=0, cursor="hand2", width=7, pady=4,
                command=lambda f=fmt: self._select_format(f))
            btn.pack(side="left", padx=4)
            self.format_buttons[fmt] = btn

        # --- slide-out quality panel ----------------------------------
        # the slot pins the panel's place right under the format
        # buttons, so pack() on show does not send it to the window end
        self.quality_slot = tk.Frame(main, bg=BG)
        self.quality_slot.pack(fill="x")
        self.quality_panel = tk.Frame(self.quality_slot, bg=ACCENT_SOFT)
        self.quality_inner = tk.Frame(self.quality_panel, bg=ACCENT_SOFT)
        self.quality_inner.pack(side="right", padx=6, pady=5)
        tk.Label(self.quality_panel, text="Quality:", bg=ACCENT_SOFT,
                 fg=ACCENT_DARK, font=("TkDefaultFont", 9, "bold")).pack(
            side="right", padx=(0, 4))
        self._style_format_buttons()

        # --- history ---------------------------------------------------
        tk.Label(main, text="Download history and status", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(14, 4))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=26, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL,
                        foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected", ACCENT_SOFT)],
                  foreground=[("selected", TEXT)])

        table_frame = tk.Frame(main, bg=BG)
        table_frame.pack(fill="both", expand=True)
        columns = ("url", "service", "format", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show="headings", selectmode="browse")
        self.tree.heading("url", text="Link")
        self.tree.heading("service", text="Service")
        self.tree.heading("format", text="Format")
        self.tree.heading("status", text="Status")
        self.tree.column("url", width=430, anchor="w")
        self.tree.column("service", width=120, anchor="center")
        self.tree.column("format", width=70, anchor="center")
        self.tree.column("status", width=150, anchor="center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        self.tree.tag_configure("done", foreground=ACCENT_DARK)
        self.tree.tag_configure("error", foreground=ERROR)
        self.tree.tag_configure("active", foreground=TEXT)
        self.tree.bind("<Double-1>", self._on_history_doubleclick)
        self.tree.bind("<Button-3>", self._show_context_menu)
        if sys.platform == "darwin":  # on macOS right-click is Button-2
            self.tree.bind("<Button-2>", self._show_context_menu)
            self.tree.bind("<Control-Button-1>", self._show_context_menu)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar()
        tk.Label(bar, textvariable=self.status_var, bg=PANEL, fg=MUTED,
                 anchor="w", padx=12, pady=5,
                 font=("TkDefaultFont", 9)).pack(side="left", fill="x")
        self._update_statusbar()

    def _update_statusbar(self, extra: str = ""):
        text = f"Download folder: {self.config_store.download_dir}"
        if extra:
            text += f"   •   {extra}"
        self.status_var.set(text)

    # ------------------------------------------------------------------
    # input placeholder
    # ------------------------------------------------------------------
    PLACEHOLDER = "Paste a video or music link…"

    def _set_placeholder(self):
        if not self.url_var.get():
            self.url_entry.configure(fg=MUTED)
            self.url_var.set(self.PLACEHOLDER)
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        self.url_entry.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, _event=None):
        if self.url_var.get() == self.PLACEHOLDER:
            self.url_var.set("")
            self.url_entry.configure(fg=TEXT)

    def _restore_placeholder(self, _event=None):
        if not self.url_var.get().strip():
            self.url_entry.configure(fg=MUTED)
            self.url_var.set(self.PLACEHOLDER)

    def _current_url(self) -> str:
        value = self.url_var.get().strip()
        return "" if value == self.PLACEHOLDER else value

    # ------------------------------------------------------------------
    # clipboard on any keyboard layout
    # ------------------------------------------------------------------
    # Standard Tk bindings (Ctrl+V etc.) only work on the latin layout.
    # The control code of the pressed key (event.char) does not depend
    # on the layout: Ctrl+V always yields \x16, Ctrl+C — \x03,
    # Ctrl+X — \x18, Ctrl+A — \x01.
    def _on_ctrl_key(self, event):
        char = event.char
        if char == "\x16":
            return self._paste_into_entry()
        if char == "\x03":
            self.url_entry.event_generate("<<Copy>>")
            return "break"
        if char == "\x18":
            self.url_entry.event_generate("<<Cut>>")
            return "break"
        if char == "\x01":
            self.url_entry.select_range(0, "end")
            self.url_entry.icursor("end")
            return "break"
        return None

    def _on_ctrl_key_global(self, event):
        # Ctrl+V while focus is elsewhere — paste into the input anyway
        if event.char == "\x16" and event.widget is not self.url_entry:
            self.url_entry.focus_set()
            return self._paste_into_entry()
        return None

    def _paste_into_entry(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return "break"
        self._clear_placeholder()
        try:
            self.url_entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass  # no selection
        self.url_entry.insert("insert", text.strip())
        self.url_entry.configure(fg=TEXT)
        return "break"

    # ------------------------------------------------------------------
    # service / format / quality / folder selection
    # ------------------------------------------------------------------
    def _select_service(self, service_id):
        self.selected_service = service_id
        self._style_service_buttons()

    def _style_service_buttons(self):
        for sid, btn in self.service_buttons.items():
            if sid == self.selected_service:
                btn.configure(bg=ACCENT, fg="white",
                              font=("TkDefaultFont", 10, "bold"))
            else:
                btn.configure(bg=PANEL, fg=TEXT,
                              font=("TkDefaultFont", 10))

    def _select_format(self, fmt):
        if fmt == self.current_format:
            # second click on the active format toggles the quality panel
            self._toggle_quality_panel()
        else:
            self.current_format = fmt
            self.config_store.format = fmt
            if not self.quality_panel_visible:
                self._toggle_quality_panel(show=True)
        self._style_format_buttons()

    def _style_format_buttons(self):
        for fmt, btn in self.format_buttons.items():
            if fmt == self.current_format:
                btn.configure(bg=ACCENT, fg="white",
                              activebackground=ACCENT_DARK,
                              activeforeground="white")
            else:
                btn.configure(bg="#d7e3d7", fg=TEXT,
                              activebackground=ACCENT_SOFT,
                              activeforeground=TEXT)
        self._rebuild_quality_buttons()

    def _toggle_quality_panel(self, show=None):
        target = (not self.quality_panel_visible) if show is None else show
        if target and not self.quality_panel_visible:
            self.quality_panel.pack(fill="x", pady=(4, 0))
            self.quality_panel_visible = True
        elif not target and self.quality_panel_visible:
            self.quality_panel.pack_forget()
            self.quality_panel_visible = False

    def _rebuild_quality_buttons(self):
        for btn in self.quality_buttons.values():
            btn.destroy()
        self.quality_buttons.clear()
        options = (MP3_BITRATES if self.current_format == "mp3"
                   else MP4_QUALITIES)
        current = self.config_store.quality_for(self.current_format)
        for value in options:
            label = f"{value} kbps" if self.current_format == "mp3" else value
            btn = tk.Button(
                self.quality_inner, text=label,
                font=("TkDefaultFont", 9), relief="flat", bd=0,
                cursor="hand2", padx=8, pady=2,
                bg=ACCENT if value == current else ACCENT_SOFT,
                fg="white" if value == current else ACCENT_DARK,
                command=lambda v=value: self._select_quality(v))
            btn.pack(side="left", padx=2)
            self.quality_buttons[value] = btn

    def _select_quality(self, value):
        self.config_store.set_quality(self.current_format, value)
        self._rebuild_quality_buttons()

    def _choose_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.config_store.download_dir,
            title="Where to save downloads")
        if folder:
            self.config_store.download_dir = folder
            self._update_statusbar()

    # ------------------------------------------------------------------
    # downloading
    # ------------------------------------------------------------------
    def _start_download(self):
        url = self._current_url()
        if not url:
            messagebox.showinfo("MediaGrab",
                                "Paste a link into the box above.")
            return
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showwarning(
                "MediaGrab", "This does not look like a link. A link "
                "must start with http:// or https://")
            return

        if self.selected_service == AUTO_ID:
            plugin = services.detect(url)
        else:
            plugin = services.by_id(self.selected_service)
            if plugin and not plugin.matches(url):
                detected = services.detect(url)
                if detected:
                    plugin = detected  # link from another service — trust it

        fmt = self.current_format
        note = ""
        if plugin and fmt not in plugin.supported_formats:
            fmt = plugin.supported_formats[0]
            note = f"{plugin.name}: only {fmt} is available"

        quality = self.config_store.quality_for(fmt)
        service_name = plugin.name if plugin else "Auto (yt-dlp)"

        entry = self.config_store.add_history(url, service_name, fmt,
                                              "queued")
        item = self.tree.insert(
            "", 0, values=(url, service_name, fmt, STATUS_QUEUED),
            tags=("active",))
        task_id = self.manager.submit(url, plugin, fmt, quality,
                                      self.config_store.download_dir)
        self.tasks[task_id] = {"item": item, "entry": entry}
        self.row_entries[item] = entry

        self.url_var.set("")
        self.url_entry.focus_set()
        self._update_statusbar(note or f"Download added: {fmt}, {quality}")

    def _poll_events(self):
        if self._version_note and not self._version_shown:
            self._version_shown = True
            self.latest_version = self._version_note
            self._update_statusbar(
                f"New version {self.latest_version} is available — "
                "run update.bat (Windows) or ./update.sh")
        while not self.manager.events.empty():
            task_id, event, payload = self.manager.events.get_nowait()
            task = self.tasks.get(task_id)
            if not task:
                continue
            item, entry = task["item"], task["entry"]
            if event == "start":
                self.tree.set(item, "status", "0%")
            elif event == "progress":
                self.tree.set(item, "status", f"{payload:.0f}%")
            elif event == "processing":
                self.tree.set(item, "status", STATUS_PROCESSING)
            elif event == "retry":
                attempt, total = payload
                self.tree.set(item, "status",
                              f"↻ retry {attempt}/{total}")
            elif event == "done":
                self.tree.set(item, "status", STATUS_DONE)
                self.tree.item(item, tags=("done",))
                self.config_store.update_history(entry, "done", payload)
                name = os.path.basename(payload) if payload else entry["url"]
                self._update_statusbar(f"Done: {name}")
                del self.tasks[task_id]
            elif event == "error":
                self.tree.set(item, "status", STATUS_ERROR)
                self.tree.item(item, tags=("error",))
                self.config_store.update_history(
                    entry, "error",
                    error=payload.get("message"),
                    hint=payload.get("hint"),
                    report_path=payload.get("report_path"))
                self._update_statusbar(
                    "Error. Right-click the row → “Why it failed…” "
                    "for the cause and a report")
                del self.tasks[task_id]
        self.after(150, self._poll_events)

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def _load_history(self):
        for record in self.config_store.history:
            status = record.get("status")
            if status == "done":
                text, tag = STATUS_DONE, "done"
            elif status == "error":
                text, tag = STATUS_ERROR, "error"
            else:  # left unfinished by a previous run
                text, tag = STATUS_ERROR, "error"
            item = self.tree.insert(
                "", "end",
                values=(record.get("url", ""), record.get("service", ""),
                        record.get("format", ""), text),
                tags=(tag,))
            self.row_entries[item] = record

    def _on_history_doubleclick(self, _event):
        selection = self.tree.selection()
        if selection:
            url = self.tree.set(selection[0], "url")
            self._clear_placeholder()
            self.url_var.set(url)
            self.url_entry.configure(fg=TEXT)
            self.url_entry.focus_set()

    # ------------------------------------------------------------------
    # history context menu (right-click)
    # ------------------------------------------------------------------
    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        entry = self.row_entries.get(item)
        if entry is None:
            return
        menu = tk.Menu(self, tearoff=0)
        if entry.get("status") == "done" and entry.get("file"):
            menu.add_command(
                label="Open",
                command=lambda: self._open_file(entry["file"]))
            menu.add_command(
                label="Show in folder",
                command=lambda: self._reveal_file(entry["file"]))
            menu.add_separator()
        if entry.get("status") == "error" and entry.get("error"):
            menu.add_command(
                label="Why it failed…",
                command=lambda: self._show_error_details(entry))
            menu.add_separator()
        menu.add_command(
            label="Copy link",
            command=lambda: self._copy_url(entry.get("url", "")))
        is_active = any(t["item"] == item for t in self.tasks.values())
        if not is_active:
            menu.add_command(
                label="Remove from history", foreground=ERROR,
                activeforeground=ERROR,
                command=lambda: self._delete_history_row(item, entry))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_url(self, url: str):
        self.clipboard_clear()
        self.clipboard_append(url)
        self._update_statusbar("Link copied to clipboard")

    def _resolve_file(self, filepath: str):
        if not filepath:
            return None
        if not os.path.isabs(filepath):
            # older history entries stored just the file name
            filepath = os.path.join(self.config_store.download_dir, filepath)
        return filepath if os.path.exists(filepath) else None

    def _open_file(self, filepath: str):
        path = self._resolve_file(filepath)
        if not path:
            messagebox.showinfo(
                "MediaGrab", "File not found — it may have been "
                "moved or deleted.")
            return
        self._open_in_system(path)

    def _reveal_file(self, filepath: str):
        path = self._resolve_file(filepath)
        if not path:
            messagebox.showinfo(
                "MediaGrab", "File not found — it may have been "
                "moved or deleted.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            self._open_in_system(os.path.dirname(path))

    @staticmethod
    def _open_in_system(path: str):
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 — open the file via the OS
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _delete_history_row(self, item, entry):
        self.config_store.remove_history(entry)
        self.row_entries.pop(item, None)
        self.tree.delete(item)

    # ------------------------------------------------------------------
    # "why it did not download" window
    # ------------------------------------------------------------------
    def _show_error_details(self, entry: dict):
        win = tk.Toplevel(self)
        win.title("Why it failed")
        win.configure(bg=BG)
        win.geometry("600x430")
        win.transient(self)

        tk.Label(win, text=entry.get("url", ""), bg=BG, fg=MUTED,
                 wraplength=560, justify="left",
                 font=("TkDefaultFont", 9)).pack(
            anchor="w", padx=16, pady=(12, 2))

        tk.Label(win, text="What you can do", bg=BG, fg=ACCENT_DARK,
                 font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=16, pady=(8, 2))
        tk.Label(win, text=entry.get("hint") or "Unknown cause.",
                 bg=BG, fg=TEXT, wraplength=560, justify="left").pack(
            anchor="w", padx=16)

        tk.Label(win, text="Error text", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=16, pady=(12, 2))
        text = tk.Text(win, height=5, wrap="word", bg=CARD, fg=ERROR,
                       relief="solid", bd=1, font=("TkDefaultFont", 9))
        text.insert("1.0", entry.get("error") or "")
        text.configure(state="disabled")
        text.pack(fill="x", padx=16)

        report_path = entry.get("report_path") or ""
        if report_path:
            tk.Label(win, text=f"Full report: {report_path}", bg=BG,
                     fg=MUTED, wraplength=560, justify="left",
                     font=("TkDefaultFont", 8)).pack(
                anchor="w", padx=16, pady=(6, 0))

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill="x", padx=16, pady=14)
        tk.Button(buttons, text="Copy report", bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", padx=10,
                  command=lambda: self._copy_report(entry)).pack(side="left")
        if report_path:
            tk.Button(buttons, text="Open reports folder", bg=CARD,
                      fg=TEXT, relief="solid", bd=1, cursor="hand2",
                      padx=10,
                      command=lambda: self._open_in_system(
                          os.path.dirname(report_path))).pack(
                side="left", padx=8)
        tk.Button(buttons, text="Close", bg=CARD, fg=TEXT,
                  relief="solid", bd=1, cursor="hand2", padx=10,
                  command=win.destroy).pack(side="right")

    def _copy_report(self, entry: dict):
        report = ""
        path = entry.get("report_path") or ""
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    report = fh.read()
            except OSError:
                report = ""
        if not report:
            report = "\n".join(filter(None, [
                "MediaGrab — download error",
                f"Link:    {entry.get('url', '')}",
                f"Service: {entry.get('service', '')}",
                f"Format:  {entry.get('format', '')}",
                f"Error:   {entry.get('error', '')}",
            ]))
        self.clipboard_clear()
        self.clipboard_append(report)
        self._update_statusbar(
            "Report copied — paste it into a message to the developer")

    # ------------------------------------------------------------------
    # profile and settings
    # ------------------------------------------------------------------
    def _check_updates_bg(self):
        """Background check for a new version on GitHub (non-blocking)."""
        try:
            self._version_note = check_remote()
        except Exception:  # noqa: BLE001 — no network etc.: skip silently
            self._version_note = None

    def _version_summary(self) -> str:
        if self.latest_version:
            return (f"Installed: {local_version()}. New version "
                    f"{self.latest_version} is available!\nClose the app "
                    "and run update.bat (Windows) or ./update.sh "
                    "(macOS/Linux).")
        return (f"Installed version {local_version()} — no newer version "
                "found on GitHub.")

    @staticmethod
    def _run_async(window, work, finished):
        """Run work() off the UI thread, then call finished(result, error).

        Tk widgets may only be touched from the main thread, so the
        result is polled with after() instead of being handed over
        directly from the worker thread.
        """
        state = {}

        def worker():
            try:
                state["result"] = work()
            except Exception as exc:  # noqa: BLE001 — reported in the window
                state["error"] = exc
            state["done"] = True

        def poll():
            if not window.winfo_exists():
                return
            if not state.get("done"):
                window.after(200, poll)
                return
            finished(state.get("result"), state.get("error"))

        threading.Thread(target=worker, daemon=True).start()
        window.after(200, poll)

    def _show_profile(self):
        win = tk.Toplevel(self)
        win.title("Profile & settings")
        win.configure(bg=BG)
        win.geometry("620x640")
        win.minsize(560, 560)
        win.transient(self)

        def section(text):
            tk.Label(win, text=text, bg=BG, fg=ACCENT_DARK,
                     font=("TkDefaultFont", 10, "bold")).pack(
                anchor="w", padx=16, pady=(14, 4))

        # --- profile ---------------------------------------------------
        section("Profile")
        name_row = tk.Frame(win, bg=BG)
        name_row.pack(fill="x", padx=16)
        tk.Label(name_row, text="Name:", bg=BG, fg=TEXT).pack(side="left")
        name_var = tk.StringVar(value=self.config_store.profile_name)
        name_entry = tk.Entry(name_row, textvariable=name_var, bg=CARD,
                              fg=TEXT, relief="solid", bd=1)
        name_entry.pack(side="left", fill="x", expand=True,
                        padx=8, ipady=3)

        def save_name(*_args):
            self.config_store.profile_name = name_var.get().strip()

        name_entry.bind("<FocusOut>", save_name)
        win.protocol("WM_DELETE_WINDOW",
                     lambda: (save_name(), win.destroy()))

        # --- version ---------------------------------------------------
        section("App version")
        version_var = tk.StringVar(value=self._version_summary())
        version_label = tk.Label(win, textvariable=version_var, bg=BG,
                                 fg=ERROR if self.latest_version else TEXT,
                                 wraplength=560, justify="left")
        version_label.pack(anchor="w", padx=16)

        library_var = tk.StringVar(
            value=f"Download library: yt-dlp {ytdlp_version()}")
        tk.Label(win, textvariable=library_var, bg=BG, fg=MUTED,
                 wraplength=560, justify="left").pack(
            anchor="w", padx=16, pady=(4, 0))

        version_buttons = tk.Frame(win, bg=BG)
        version_buttons.pack(fill="x", padx=16, pady=(8, 0))
        check_btn = tk.Button(
            version_buttons, text="Check for updates", bg=CARD, fg=TEXT,
            relief="solid", bd=1, cursor="hand2", padx=8)
        check_btn.pack(side="left")
        update_btn = tk.Button(
            version_buttons, text="Update yt-dlp", bg=CARD, fg=TEXT,
            relief="solid", bd=1, cursor="hand2", padx=8)
        update_btn.pack(side="left", padx=8)

        def check_updates():
            check_btn.configure(state="disabled")
            version_var.set("Checking GitHub for a new version…")
            version_label.configure(fg=MUTED)

            def finished(result, error):
                check_btn.configure(state="normal")
                if error is not None:
                    version_var.set(
                        f"Installed version {local_version()} — could not "
                        "reach GitHub. Check your internet connection.")
                    version_label.configure(fg=ERROR)
                    return
                self.latest_version = result
                self._version_shown = True   # do not repeat it in the status bar
                version_var.set(self._version_summary())
                version_label.configure(fg=ERROR if result else TEXT)

            self._run_async(win, check_remote, finished)

        def update_library():
            update_btn.configure(state="disabled")
            library_var.set("Updating yt-dlp, this may take a minute…")

            def finished(result, error):
                update_btn.configure(state="normal")
                if error is not None:
                    library_var.set(f"Update failed: {error}")
                    return
                ok, message = result
                prefix = "" if ok else "Update failed: "
                library_var.set(
                    f"{prefix}{message}\nDownload library: "
                    f"yt-dlp {ytdlp_version()}")
                self._update_statusbar(message)

            self._run_async(win, update_ytdlp, finished)

        check_btn.configure(command=check_updates)
        update_btn.configure(command=update_library)

        # --- downloads ---------------------------------------------------
        section("Downloads")
        folder_var = tk.StringVar(
            value=f"Folder: {self.config_store.download_dir}")
        tk.Label(win, textvariable=folder_var, bg=BG, fg=TEXT,
                 wraplength=560, justify="left").pack(anchor="w", padx=16)
        history = self.config_store.history
        done = sum(1 for e in history if e.get("status") == "done")
        tk.Label(win, text=f"History: {len(history)} downloads, "
                           f"{done} successful",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=16, pady=(2, 0))

        def change_folder():
            self._choose_folder()
            folder_var.set(f"Folder: {self.config_store.download_dir}")

        dl_buttons = tk.Frame(win, bg=BG)
        dl_buttons.pack(fill="x", padx=16, pady=(6, 0))
        tk.Button(dl_buttons, text="Change folder…", bg=CARD, fg=TEXT,
                  relief="solid", bd=1, cursor="hand2", padx=8,
                  command=change_folder).pack(side="left")
        tk.Button(dl_buttons, text="Clear history", bg=CARD, fg=ERROR,
                  relief="solid", bd=1, cursor="hand2", padx=8,
                  command=self._clear_history_ui).pack(side="left", padx=8)

        # --- profile data ------------------------------------------------
        section("Profile data")
        tk.Label(win, text=(
            "All data — settings, history, cookies, error reports — is "
            f"stored separately from the program, in:\n{CONFIG_DIR}\n"
            "Updating via update.bat / update.sh replaces only the program "
            "files and does NOT touch this folder."),
            bg=BG, fg=TEXT, wraplength=560, justify="left").pack(
            anchor="w", padx=16)
        tk.Label(win, text=(
            "Signing in to accounts (X, Facebook etc.) works through "
            "browser cookie files — e.g. cookies/x.txt. Step-by-step "
            "guide: docs/COOKIES.md (a HOW_TO_CONNECT_ACCOUNT.txt memo "
            "appears in the cookies folder)."),
            bg=BG, fg=MUTED, wraplength=560, justify="left").pack(
            anchor="w", padx=16, pady=(6, 0))

        data_buttons = tk.Frame(win, bg=BG)
        data_buttons.pack(fill="x", padx=16, pady=(8, 0))
        tk.Button(data_buttons, text="Open data folder", bg=CARD,
                  fg=TEXT, relief="solid", bd=1, cursor="hand2", padx=8,
                  command=lambda: self._open_in_system(str(CONFIG_DIR))
                  ).pack(side="left")
        tk.Button(data_buttons, text="Cookies folder", bg=CARD, fg=TEXT,
                  relief="solid", bd=1, cursor="hand2", padx=8,
                  command=self._open_cookies_folder).pack(
            side="left", padx=8)

        tk.Button(win, text="Close", bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", padx=12,
                  command=lambda: (save_name(), win.destroy())).pack(
            side="bottom", anchor="e", padx=16, pady=12)

    COOKIES_README = """How to connect an account (e.g. X/Twitter):

1. Install a cookies-export extension in your browser:
   - Chrome/Edge: "Get cookies.txt LOCALLY"
   - Firefox: "cookies.txt"
2. Sign in to your account on the site (e.g. x.com).
3. While on that site, click the extension icon -> Export.
4. Save the file into THIS folder as <service>.txt:
   x.txt, facebook.txt, youtube.txt, tiktok.txt
   (an all.txt file is used for every service)
5. Retry the download in MediaGrab — cookies are picked up
   automatically.

IMPORTANT: a cookies file grants access to your account.
Never send it to anyone and never publish it online.
Cookies expire over time — if signing in stops working,
export the file again.

Detailed guide: docs/COOKIES.md in the program folder.
"""

    def _open_cookies_folder(self):
        try:
            COOKIES_DIR.mkdir(parents=True, exist_ok=True)
            readme = COOKIES_DIR / "HOW_TO_CONNECT_ACCOUNT.txt"
            if not readme.exists():
                readme.write_text(self.COOKIES_README, encoding="utf-8")
        except OSError:
            pass
        self._open_in_system(str(COOKIES_DIR))

    def _clear_history_ui(self):
        if not messagebox.askyesno(
                "MediaGrab", "Clear the download history?\n"
                "The downloaded files stay on disk."):
            return
        active_items = {t["item"] for t in self.tasks.values()}
        active_entries = [t["entry"] for t in self.tasks.values()]
        self.config_store.clear_history(keep=active_entries)
        for item in list(self.row_entries):
            if item not in active_items:
                self.row_entries.pop(item, None)
                self.tree.delete(item)
        self._update_statusbar("History cleared")

    # ------------------------------------------------------------------
    def _check_dependencies(self):
        problems = []
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            problems.append("yt-dlp is not installed "
                            "(pip install -r requirements.txt)")
        import shutil
        if not shutil.which("ffmpeg"):
            problems.append("ffmpeg not found — mp3 and video merging "
                            "will not work (see README)")
        if problems:
            self._update_statusbar("⚠ " + "; ".join(problems))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
