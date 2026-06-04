import os
import sys
import subprocess
import tkinter as tk

def launch():
    root = tk.Tk()
    root.title("")
    root.attributes("-topmost", True)
    root.overrideredirect(True)
    root.configure(bg="#1a1a2e")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.geometry(f"56x56+{screen_w - 76}+{screen_h - 76}")

    def on_click():
        bat = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "git-push.bat")
        subprocess.Popen([
            "cmd", "/c", "start", "cmd", "/c",
            f"call \"{bat}\" & if errorlevel 1 pause"
        ])

    canvas = tk.Canvas(root, width=56, height=56,
                       bg="#1a1a2e", highlightthickness=0)
    canvas.pack()

    circle = canvas.create_oval(4, 4, 52, 52, fill="#2ea043", outline="")
    canvas.create_polygon(20, 14, 20, 42, 44, 28, fill="white", outline="")

    _state = {"drag_x": 0, "drag_y": 0, "dragging": False}
    tooltip = {"win": None}

    def show_tip(e):
        if tooltip["win"]: return
        tip = tk.Toplevel(root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg="#161b22")
        tk.Label(tip, text="Push to GitHub", bg="#161b22", fg="#e6edf3",
                font=("Segoe UI", 8), padx=8, pady=4).pack()
        tip.update_idletasks()
        tx = root.winfo_x() + (56 - tip.winfo_width()) // 2
        ty = root.winfo_y() - tip.winfo_height() - 6
        tip.geometry(f"+{tx}+{ty}")
        tooltip["win"] = tip

    def hide_tip(e):
        if tooltip["win"]:
            tooltip["win"].destroy()
            tooltip["win"] = None

    def on_press(e):
        _state["drag_x"] = e.x_root
        _state["drag_y"] = e.y_root
        _state["dragging"] = False

    def on_motion(e):
        dx = abs(e.x_root - _state["drag_x"])
        dy = abs(e.y_root - _state["drag_y"])
        if dx > 8 or dy > 8:
            _state["dragging"] = True
            nx = root.winfo_x() + e.x_root - _state["drag_x"]
            ny = root.winfo_y() + e.y_root - _state["drag_y"]
            root.geometry(f"+{nx}+{ny}")
            _state["drag_x"] = e.x_root
            _state["drag_y"] = e.y_root
            hide_tip(e)

    def on_release(e):
        if not _state["dragging"]:
            on_click()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_motion)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Enter>", lambda e: (canvas.itemconfig(circle, fill="#3fb950"), show_tip(e)))
    canvas.bind("<Leave>", lambda e: (canvas.itemconfig(circle, fill="#2ea043"), hide_tip(e)))

    close = tk.Label(root, text="×", bg="#1a1a2e", fg="#666666",
                    font=("Segoe UI", 9), cursor="hand2")
    close.place(x=40, y=0)
    close.bind("<Button-1>", lambda e: root.destroy())

    root.mainloop()

if __name__ == "__main__":
    launch()
