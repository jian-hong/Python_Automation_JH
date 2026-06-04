import os
import sys
import subprocess
import tkinter as tk
import threading
import time

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git-push.bat")

# Layout
WIN_W, WIN_H = 84, 108
HEADER_H = 28
PAD = 10
WIN_ALPHA = 0.88

BG = "#1c1c24"
BAR_BG = "#252530"
TEXT = "#f0f3f6"
MUTED = "#9aa4b2"
GREEN = "#46c876"
GREEN_HOVER = "#5fd98a"
GRAY = "#5a5a62"
GRAY_HOVER = "#72727c"
CIRCLE_RING = "#ffffff18"
TRI_FILL = "#f5f8fc"
CLOSE_IDLE = "#8b949e"
CLOSE_HOVER = "#ff7b72"
FONT = "Segoe UI"


def get_change_count():
    try:
        r1 = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=NO_WINDOW,
        )
        r2 = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=NO_WINDOW,
        )
        r3 = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=NO_WINDOW,
        )
        files = set(
            r1.stdout.strip().splitlines()
            + r2.stdout.strip().splitlines()
            + r3.stdout.strip().splitlines()
        )
        files.discard("")
        return len(files)
    except Exception:
        return -1


def _point_in_circle(cx, cy, r, x, y):
    return ((x - cx) / r) ** 2 + ((y - cy) / r) ** 2 <= 1.0


def launch():
    root = tk.Tk()
    root.title("")
    root.attributes("-topmost", True)
    root.overrideredirect(True)
    root.configure(bg=BG)
    try:
        root.attributes("-alpha", WIN_ALPHA)
    except tk.TclError:
        pass

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{WIN_W}x{WIN_H}+{sw - WIN_W - 20}+{sh - WIN_H - 20}")

    _state = {"drag_x": 0, "drag_y": 0, "dragging": False, "count": -1, "press_in_circle": False}
    tooltip = {"win": None}

    # ── Top bar: drag only (no push) ──
    header = tk.Frame(root, bg=BAR_BG, height=HEADER_H, cursor="fleur")
    header.pack(fill="x")
    header.pack_propagate(False)

    grip = tk.Label(
        header,
        text="⋮⋮",
        bg=BAR_BG,
        fg=MUTED,
        font=(FONT, 8),
        cursor="fleur",
    )
    grip.pack(side="left", padx=(10, 0), pady=7)

    tk.Label(
        header,
        text="drag",
        bg=BAR_BG,
        fg=MUTED,
        font=(FONT, 8),
        cursor="fleur",
    ).pack(side="left", padx=(4, 0), pady=7)

    close_hit = tk.Frame(header, bg=BAR_BG, width=32, height=HEADER_H, cursor="hand2")
    close_hit.pack(side="right", padx=2)
    close_hit.pack_propagate(False)

    close_lbl = tk.Label(
        close_hit,
        text="✕",
        bg=BAR_BG,
        fg=CLOSE_IDLE,
        font=(FONT, 13, "bold"),
        cursor="hand2",
    )
    close_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def close_hover_in(_e=None):
        close_hit.configure(bg="#32323d")
        close_lbl.configure(bg="#32323d", fg=CLOSE_HOVER)

    def close_hover_out(_e=None):
        close_hit.configure(bg=BAR_BG)
        close_lbl.configure(bg=BAR_BG, fg=CLOSE_IDLE)

    close_hit.bind("<Enter>", close_hover_in)
    close_hit.bind("<Leave>", close_hover_out)
    close_lbl.bind("<Enter>", close_hover_in)
    close_lbl.bind("<Leave>", close_hover_out)

    # ── Push circle (click only here) ──
    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True)

    canvas_size = WIN_H - HEADER_H
    canvas = tk.Canvas(
        body, width=canvas_size, height=canvas_size, bg=BG, highlightthickness=0, cursor="hand2"
    )
    canvas.pack()

    cx = cy = canvas_size // 2
    r = canvas_size // 2 - PAD
    circle = canvas.create_oval(
        cx - r, cy - r, cx + r, cy + r, fill=GRAY, outline=CIRCLE_RING, width=1
    )
    tri_w = int(r * 0.52)
    canvas.create_polygon(
        cx - tri_w // 2,
        cy - int(tri_w * 0.45),
        cx - tri_w // 2,
        cy + int(tri_w * 0.55),
        cx + int(tri_w * 0.5),
        cy,
        fill=TRI_FILL,
        outline="",
        smooth=True,
    )
    badge_bg = canvas.create_oval(
        cx + r - 18, cy - r + 2, cx + r - 2, cy - r + 18,
        fill="#e85d5d", outline=BG, width=1.5, state="hidden",
    )
    badge_tx = canvas.create_text(
        cx + r - 10, cy - r + 10, text="0", fill="white",
        font=(FONT, 9, "bold"), state="hidden",
    )

    def update_status(count):
        fill = GREEN if count > 0 else GRAY
        canvas.itemconfig(circle, fill=fill)
        if count > 0:
            canvas.itemconfig(badge_bg, state="normal")
            canvas.itemconfig(
                badge_tx, text=str(count) if count < 10 else "9+", state="normal"
            )
        else:
            canvas.itemconfig(badge_bg, state="hidden")
            canvas.itemconfig(badge_tx, state="hidden")

    def poll_loop():
        while True:
            count = get_change_count()
            _state["count"] = count
            try:
                root.after(0, update_status, count)
            except Exception:
                break
            time.sleep(60)

    threading.Thread(target=poll_loop, daemon=True).start()
    root.after(200, lambda: update_status(get_change_count()))

    def on_click():
        try:
            os.startfile(BAT_PATH)
        except Exception as exc:
            print(f"Could not launch: {exc}")

        def refresh():
            root.after(0, update_status, get_change_count())

        root.after(10000, lambda: threading.Thread(target=refresh, daemon=True).start())

    def show_tip(_e=None):
        if tooltip["win"]:
            return
        tip = tk.Toplevel(root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=BAR_BG)
        try:
            tip.attributes("-alpha", 0.94)
        except tk.TclError:
            pass

        c = _state["count"]
        if c > 0:
            title = "Ready to push"
            detail = f"{c} file(s) changed"
            hint = "Click the circle below to push"
        elif c == 0:
            title = "Up to date"
            detail = "No local changes vs main"
            hint = "Click the circle to push anyway"
        else:
            title = "Push to GitHub"
            detail = "Status unavailable"
            hint = "Click the circle to open push"

        tk.Label(tip, text=title, bg=BAR_BG, fg=TEXT, font=(FONT, 10, "bold")).pack(
            anchor="w", padx=14, pady=(12, 3)
        )
        tk.Label(tip, text=detail, bg=BAR_BG, fg=TEXT, font=(FONT, 10)).pack(
            anchor="w", padx=14
        )
        tk.Frame(tip, bg="#404050", height=1).pack(fill="x", padx=12, pady=8)
        tk.Label(tip, text=hint, bg=BAR_BG, fg=MUTED, font=(FONT, 9)).pack(
            anchor="w", padx=14
        )
        tk.Label(
            tip,
            text="Drag the top bar  ·  ✕ hides the button",
            bg=BAR_BG,
            fg=MUTED,
            font=(FONT, 8),
        ).pack(anchor="w", padx=14, pady=(6, 12))

        tip.update_idletasks()
        tx = root.winfo_x() + (WIN_W - tip.winfo_width()) // 2
        ty = root.winfo_y() - tip.winfo_height() - 8
        tip.geometry(f"+{tx}+{ty}")
        tooltip["win"] = tip

    def hide_tip(_e=None):
        if tooltip["win"]:
            tooltip["win"].destroy()
            tooltip["win"] = None

    def on_drag_press(e):
        _state["drag_x"] = e.x_root
        _state["drag_y"] = e.y_root
        _state["dragging"] = False

    def on_drag_motion(e):
        if abs(e.x_root - _state["drag_x"]) > 4 or abs(e.y_root - _state["drag_y"]) > 4:
            _state["dragging"] = True
            nx = root.winfo_x() + e.x_root - _state["drag_x"]
            ny = root.winfo_y() + e.y_root - _state["drag_y"]
            root.geometry(f"+{nx}+{ny}")
            _state["drag_x"] = e.x_root
            _state["drag_y"] = e.y_root
            hide_tip()

    def on_circle_press(e):
        _state["press_in_circle"] = _point_in_circle(cx, cy, r - 2, e.x, e.y)
        _state["drag_x"] = e.x_root
        _state["drag_y"] = e.y_root
        _state["dragging"] = False

    def on_circle_motion(e):
        if not _state["press_in_circle"]:
            return
        if abs(e.x_root - _state["drag_x"]) > 10 or abs(e.y_root - _state["drag_y"]) > 10:
            _state["dragging"] = True
            nx = root.winfo_x() + e.x_root - _state["drag_x"]
            ny = root.winfo_y() + e.y_root - _state["drag_y"]
            root.geometry(f"+{nx}+{ny}")
            _state["drag_x"] = e.x_root
            _state["drag_y"] = e.y_root
            hide_tip()

    def on_circle_release(e):
        if (
            _state["press_in_circle"]
            and not _state["dragging"]
            and _point_in_circle(cx, cy, r - 2, e.x, e.y)
        ):
            on_click()
        _state["press_in_circle"] = False
        _state["dragging"] = False

    def circle_hover_in(_e=None):
        c = _state["count"]
        canvas.itemconfig(circle, fill=GREEN_HOVER if c > 0 else GRAY_HOVER)
        show_tip()

    def circle_hover_out(_e=None):
        update_status(_state["count"])
        hide_tip()

    for w in (header, grip, close_hit):
        w.bind("<ButtonPress-1>", on_drag_press)
        w.bind("<B1-Motion>", on_drag_motion)

    canvas.bind("<ButtonPress-1>", on_circle_press)
    canvas.bind("<B1-Motion>", on_circle_motion)
    canvas.bind("<ButtonRelease-1>", on_circle_release)
    canvas.bind("<Enter>", circle_hover_in)
    canvas.bind("<Leave>", circle_hover_out)

    def on_close(_e=None):
        try:
            result = subprocess.run(
                ["git", "-C", REPO_ROOT, "diff", "origin/main...HEAD", "--name-only"],
                capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW,
            )
            uncommitted = subprocess.run(
                ["git", "-C", REPO_ROOT, "diff", "--name-only"],
                capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW,
            )
            has_changes = bool(result.stdout.strip() or uncommitted.stdout.strip())
        except Exception:
            has_changes = False

        if has_changes:
            dialog = tk.Toplevel(root)
            dialog.title("")
            dialog.geometry("340x200")
            dialog.configure(bg="#14141c")
            dialog.attributes("-topmost", True)
            dialog.resizable(False, False)
            try:
                dialog.attributes("-alpha", 0.96)
            except tk.TclError:
                pass
            dx = (dialog.winfo_screenwidth() - 340) // 2
            dy = (dialog.winfo_screenheight() - 200) // 2
            dialog.geometry(f"340x200+{dx}+{dy}")

            dlg_bg = "#14141c"
            tk.Label(
                dialog, text="Unpushed changes",
                bg=dlg_bg, fg=TEXT, font=(FONT, 12, "bold"),
            ).pack(pady=(22, 6))
            tk.Label(
                dialog,
                text="You still have work that is not on GitHub.\nPush now, or hide the button anyway.",
                bg=dlg_bg, fg=MUTED, font=(FONT, 10), justify="center",
            ).pack(padx=24)
            row = tk.Frame(dialog, bg=dlg_bg)
            row.pack(pady=20)

            def push_and_close():
                dialog.destroy()
                on_click()

            def hide_button():
                dialog.destroy()
                root.destroy()

            tk.Button(
                row, text="  Push now  ", bg=GREEN, fg="white",
                font=(FONT, 10, "bold"), relief="flat", cursor="hand2",
                activebackground=GREEN_HOVER, padx=14, pady=8,
                command=push_and_close,
            ).pack(side="left", padx=8)

            tk.Button(
                row, text="Hide button", bg="#2d2d38", fg=TEXT,
                font=(FONT, 10), relief="flat", cursor="hand2",
                activebackground="#3d3d4a", padx=14, pady=8,
                command=hide_button,
            ).pack(side="left", padx=8)
            dialog.grab_set()
            dialog.wait_window()
        else:
            root.destroy()

    close_hit.bind("<Button-1>", on_close)
    close_lbl.bind("<Button-1>", on_close)
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


if __name__ == "__main__":
    launch()
