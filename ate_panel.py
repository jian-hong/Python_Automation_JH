"""Tkinter ATE control panel — entry point for bench GUI."""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from ate_runner import (
    ATERunner,
    SmokeId,
    TestId,
    TestParams,
    default_vcc,
    ensure_screenshot_dir,
    resolve_excel_path,
    timestamped_sheet_name,
)

# --- UI labels mapped to runner actions ---
TEST_CHOICES: list[tuple[str, TestId | SmokeId | None]] = [
    ("VOS DC Sweep", TestId.VOS_SWEEP),
    ("AC Gain Check", TestId.AC_GAIN_CHECK),
    ("AC Vin Sweep (−5…+5 mV)", TestId.AC_VIN_SWEEP),
    ("Discover Instruments", SmokeId.FIND_INSTRUMENTS),
    ("Reset All", SmokeId.RESET_ALL),
    ("Stop Gen Output", SmokeId.STOP_OUTPUT),
    ("PSU Power Off", SmokeId.POWER_OFF),
]

AC_TESTS = {TestId.AC_GAIN_CHECK, TestId.AC_VIN_SWEEP}
SMOKE_ACTIONS = {
    SmokeId.FIND_INSTRUMENTS,
    SmokeId.RESET_ALL,
    SmokeId.STOP_OUTPUT,
    SmokeId.POWER_OFF,
}


class QueueWriter:
    """Redirect stdout into a thread-safe queue for the GUI log."""

    def __init__(self, log_queue: queue.Queue[str]) -> None:
        self._queue = log_queue

    def write(self, text: str) -> None:
        if text:
            self._queue.put(text)

    def flush(self) -> None:
        pass


class ATEPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ATE Control Panel — OPA Bench")
        self.geometry("920x680")
        self.minsize(780, 560)

        self.runner = ATERunner()
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._stop_poll = False

        self._build_styles()
        self._build_widgets()
        self._bind_events()
        self._poll_log_queue()
        self._update_ac_fields_visibility()

    def _build_styles(self) -> None:
        self.configure(bg="#1e1e1e")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#2b2b2b"
        fg = "#e0e0e0"
        accent = "#3d6ea8"
        entry_bg = "#353535"

        style.configure(".", background=bg, foreground=fg, fieldbackground=entry_bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#f0f0f0")
        style.configure("TButton", padding=6)
        style.configure("Accent.TButton", foreground="#ffffff")
        style.map(
            "Accent.TButton",
            background=[("active", "#4a7fbf"), ("!disabled", accent)],
            foreground=[("disabled", "#888888"), ("!disabled", "#ffffff")],
        )
        style.configure("TEntry", fieldbackground=entry_bg, foreground=fg)
        style.configure("TCombobox", fieldbackground=entry_bg, foreground=fg)
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("Status.TLabel", background="#141414", foreground="#b0b0b0", padding=(8, 4))

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="ATE Control Panel — OPA Bench", style="Title.TLabel").pack(
            anchor=tk.W, pady=(0, 10)
        )

        # --- Test selection ---
        sel_frame = ttk.LabelFrame(outer, text="Test / Action", padding=10)
        sel_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(sel_frame, text="Select:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.test_var = tk.StringVar(value=TEST_CHOICES[0][0])
        self.test_combo = ttk.Combobox(
            sel_frame,
            textvariable=self.test_var,
            values=[label for label, _ in TEST_CHOICES],
            state="readonly",
            width=36,
        )
        self.test_combo.grid(row=0, column=1, sticky=tk.W)
        self.test_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_ac_fields_visibility())

        # --- Parameters ---
        params_frame = ttk.LabelFrame(outer, text="Parameters", padding=10)
        params_frame.pack(fill=tk.X, pady=(0, 8))

        self.vcc_var = tk.StringVar(value=f"{default_vcc():.1f}")
        self.gain_var = tk.StringVar(value="201")
        self.freq_var = tk.StringVar(value="500")
        self.amp_var = tk.StringVar(value="0.004")
        self.repeats_var = tk.StringVar(value="3")
        self.excel_var = tk.StringVar(value=resolve_excel_path(""))
        self.reset_var = tk.BooleanVar(value=False)

        ttk.Label(params_frame, text="VCC (V):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(params_frame, textvariable=self.vcc_var, width=12).grid(
            row=0, column=1, sticky=tk.W, padx=(0, 16), pady=2
        )

        ttk.Label(params_frame, text="Gain (board):").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.gain_entry = ttk.Entry(params_frame, textvariable=self.gain_var, width=12, state="readonly")
        self.gain_entry.grid(row=0, column=3, sticky=tk.W, pady=2)

        self.freq_label = ttk.Label(params_frame, text="Freq (Hz):")
        self.freq_label.grid(row=1, column=0, sticky=tk.W, pady=2)
        self.freq_entry = ttk.Entry(params_frame, textvariable=self.freq_var, width=12)
        self.freq_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 16), pady=2)

        self.amp_label = ttk.Label(params_frame, text="Amp Vpp:")
        self.amp_label.grid(row=1, column=2, sticky=tk.W, pady=2)
        self.amp_entry = ttk.Entry(params_frame, textvariable=self.amp_var, width=12)
        self.amp_entry.grid(row=1, column=3, sticky=tk.W, pady=2)

        self.repeats_label = ttk.Label(params_frame, text="Repeats:")
        self.repeats_label.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.repeats_entry = ttk.Entry(params_frame, textvariable=self.repeats_var, width=12)
        self.repeats_entry.grid(row=2, column=1, sticky=tk.W, padx=(0, 16), pady=2)

        ttk.Label(params_frame, text="Excel path:").grid(row=3, column=0, sticky=tk.W, pady=2)
        excel_row = ttk.Frame(params_frame)
        excel_row.grid(row=3, column=1, columnspan=3, sticky=tk.EW, pady=2)
        self.excel_entry = ttk.Entry(excel_row, textvariable=self.excel_var)
        self.excel_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(excel_row, text="Browse…", command=self._browse_excel).pack(side=tk.LEFT)

        ttk.Checkbutton(
            params_frame,
            text="Reset instruments before run",
            variable=self.reset_var,
        ).grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))

        # --- Control buttons ---
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self.discover_btn = ttk.Button(btn_frame, text="Discover", command=self._on_discover)
        self.discover_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_btn = ttk.Button(
            btn_frame, text="Open Session (Init)", command=self._on_open_session
        )
        self.open_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.run_btn = ttk.Button(btn_frame, text="Run", style="Accent.TButton", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.screenshot_btn = ttk.Button(
            btn_frame, text="Screenshot", command=self._on_screenshot
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_folder_btn = ttk.Button(
            btn_frame, text="Open Screenshots", command=self._on_open_screenshots
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(btn_frame, text="Clear Log", command=self._clear_log).pack(side=tk.LEFT)

        # --- Log ---
        log_frame = ttk.LabelFrame(outer, text="Log", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=16,
            wrap=tk.WORD,
            bg="#1a1a1a",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            font=("Consolas", 10),
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

        # --- Result summary ---
        result_frame = ttk.LabelFrame(outer, text="Result Summary", padding=6)
        result_frame.pack(fill=tk.X, pady=(0, 8))

        self.result_text = tk.Text(
            result_frame,
            height=6,
            wrap=tk.WORD,
            bg="#252525",
            fg="#c8e6c9",
            font=("Consolas", 10),
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.result_text.pack(fill=tk.X)
        self.result_text.configure(state=tk.DISABLED)

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _bind_events(self) -> None:
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _selected_action(self) -> tuple[str, TestId | SmokeId | None]:
        label = self.test_var.get()
        for item_label, action in TEST_CHOICES:
            if item_label == label:
                return label, action
        return label, None

    def _update_ac_fields_visibility(self) -> None:
        _, action = self._selected_action()
        show_ac = action in AC_TESTS
        show_repeats = action is TestId.AC_VIN_SWEEP
        ac_state = tk.NORMAL if show_ac else tk.DISABLED
        repeats_state = tk.NORMAL if show_repeats else tk.DISABLED
        for widget in (self.freq_label, self.freq_entry, self.amp_label, self.amp_entry):
            widget.configure(state=ac_state)
        for widget in (self.repeats_label, self.repeats_entry):
            widget.configure(state=repeats_state)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_result_summary(self, text: str) -> None:
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        if text:
            self.result_text.insert(tk.END, text)
        self.result_text.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _set_controls_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in (
            self.discover_btn,
            self.open_btn,
            self.run_btn,
            self.screenshot_btn,
            self.open_folder_btn,
        ):
            btn.configure(state=state)
        self.stop_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)
        self.test_combo.configure(state="disabled" if busy else "readonly")

    def _browse_excel(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Excel output file",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
            initialfile="VOS Research.xlsx",
        )
        if path:
            self.excel_var.set(path)

    def _build_params(self, action: TestId | SmokeId | None) -> TestParams:
        excel_path = resolve_excel_path(self.excel_var.get())
        try:
            vcc = float(self.vcc_var.get())
            gain = float(self.gain_var.get())
            freq = float(self.freq_var.get())
            amp = float(self.amp_var.get())
            n_repeats = int(self.repeats_var.get())
        except ValueError as exc:
            raise ValueError(f"Invalid numeric parameter: {exc}") from exc

        sheet_name = ""
        if action is TestId.VOS_SWEEP:
            sheet_name = timestamped_sheet_name("vos sweep")
        elif action is TestId.AC_GAIN_CHECK:
            sheet_name = timestamped_sheet_name("ac gain check")

        return TestParams(
            vcc=vcc,
            gain=gain,
            freq_hz=freq,
            amp_vpp=amp,
            excel_path=excel_path,
            sheet_name=sheet_name,
            reset_before_run=self.reset_var.get(),
            n_repeats=n_repeats,
        )

    def _poll_log_queue(self) -> None:
        if self._stop_poll:
            return
        try:
            while True:
                chunk = self._log_queue.get_nowait()
                self._append_log(chunk)
        except queue.Empty:
            pass
        self.after(80, self._poll_log_queue)

    def _run_in_thread(self, target) -> None:
        if self.runner.busy or (self._worker and self._worker.is_alive()):
            messagebox.showwarning("Busy", "An operation is already running.")
            return

        self._set_controls_busy(True)
        self._set_status("Running…")

        def worker() -> None:
            old_stdout = sys.stdout
            sys.stdout = QueueWriter(self._log_queue)
            try:
                target()
            finally:
                sys.stdout = old_stdout

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()
        self.after(100, self._watch_worker)

    def _watch_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            self.after(100, self._watch_worker)
            return
        self._set_controls_busy(False)

    def _finish_operation(self, title: str, success: bool, summary: str = "", error: str = "") -> None:
        if summary:
            self._set_result_summary(summary)
        if success:
            self._set_status("Done — success")
            messagebox.showinfo(title, summary or "Operation completed successfully.")
        else:
            self._set_status("Done — failed")
            messagebox.showerror(title, error or "Operation failed.")

    def _on_discover(self) -> None:
        def task() -> None:
            try:
                mapping = self.runner.discover()
                summary = f"Found {len(mapping)} instrument(s)."
                self.after(0, lambda: self._finish_operation("Discover", bool(mapping), summary))
            except Exception as exc:
                self.after(
                    0,
                    lambda: self._finish_operation("Discover", False, error=str(exc)),
                )

        self._run_in_thread(task)

    def _on_open_session(self) -> None:
        """Init: open PyVISA session (MSO5072 required; PSU/AWG optional)."""

        def task() -> None:
            try:
                mapping = self.runner.mapping or None
                self.runner.open_session(mapping)
                found = self.runner.mapping
                lines = ["Init complete — session open.", f"Connected: {', '.join(found) or '(none)'}"]
                if "MSO" in found:
                    lines.append("Screenshot ready (MSO5072).")
                if "PSU" not in found:
                    lines.append("PSU (DP832) not found — Run tests that need power will fail.")
                if "AWG" not in found:
                    lines.append("AWG not found — AC/VOS sweeps need the generator.")
                summary = "\n".join(lines)
                self.after(
                    0,
                    lambda: self._finish_operation(
                        "Open Session (Init)",
                        True,
                        summary,
                    ),
                )
            except Exception as exc:
                self.after(
                    0,
                    lambda: self._finish_operation(
                        "Open Session (Init)", False, error=str(exc)
                    ),
                )

        self._run_in_thread(task)

    def _on_screenshot(self) -> None:
        """One-click RIGOL MSO5072 capture via open session (:DISP:DATA?)."""
        if not self.runner.session_open:
            messagebox.showwarning(
                "Screenshot",
                "Open Session (Init) first — screenshot needs the live MSO5072 handle.",
            )
            return

        def task() -> None:
            try:
                saved = self.runner.capture_screenshot(prefix="manual")
                self.after(
                    0,
                    lambda: self._finish_operation(
                        "Screenshot",
                        True,
                        f"MSO5072 JPEG saved (Excel-ready):\n{saved}",
                    ),
                )
            except Exception as exc:
                self.after(
                    0,
                    lambda: self._finish_operation("Screenshot", False, error=str(exc)),
                )

        self._run_in_thread(task)

    def _on_open_screenshots(self) -> None:
        """Open oscilloscope_screenshots/ in Windows Explorer (creates folder if needed)."""
        try:
            folder = ensure_screenshot_dir()
            os.startfile(str(folder))
            self._set_status(f"Opened: {folder}")
            self._append_log(f"\n[Open Screenshots] {folder}\n")
        except Exception as exc:
            messagebox.showerror("Open Screenshots", str(exc))

    def _on_run(self) -> None:
        label, action = self._selected_action()
        if action is None:
            messagebox.showwarning("Selection", "No action selected.")
            return

        def task() -> None:
            try:
                if isinstance(action, SmokeId):
                    if action is SmokeId.FIND_INSTRUMENTS:
                        result = self.runner.run_smoke(action)
                    else:
                        if not self.runner.session_open:
                            raise RuntimeError("Open a session first for this action.")
                        result = self.runner.run_smoke(action)
                elif isinstance(action, TestId):
                    if not self.runner.session_open:
                        raise RuntimeError("Open a session before running tests.")
                    params = self._build_params(action)
                    result = self.runner.run_test(action, params)
                else:
                    raise RuntimeError(f"Unknown action: {action}")

                def done() -> None:
                    if result.success:
                        self._finish_operation(label, True, result.summary)
                    else:
                        self._finish_operation(label, False, error=result.error or "Failed")

                self.after(0, done)
            except Exception as exc:
                self.after(
                    0,
                    lambda: self._finish_operation(label, False, error=str(exc)),
                )

        self._run_in_thread(task)

    def _on_stop(self) -> None:
        self.runner.request_cancel()
        self._append_log(
            "\n[Stop] emergency cleanup: stop_output(gen) + power_off(psu)\n"
        )
        self._set_status("Stop — emergency cleanup")
        try:
            self.runner.emergency_cleanup()
        except Exception as exc:
            self._append_log(f"[Stop] cleanup error: {exc}\n")
        messagebox.showwarning(
            "Stop",
            "Emergency cleanup sent (gen OFF + PSU OFF).\n"
            "If a sweep is mid-flight, wait for the worker to finish "
            "before starting another run.",
        )

    def _on_close(self) -> None:
        if messagebox.askokcancel("Quit", "Close the ATE panel and run emergency cleanup?"):
            self._stop_poll = True
            try:
                self.runner.emergency_cleanup()
            except Exception as exc:
                print(f"Cleanup error: {exc}")
            try:
                self.runner.close_session(force=True)
            except Exception as exc:
                print(f"Close session error: {exc}")
            self.destroy()


def main() -> None:
    app = ATEPanel()
    app.mainloop()


if __name__ == "__main__":
    main()
