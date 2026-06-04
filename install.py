import os
import sys
import subprocess
import platform

VENV_DIR = "venv"


def run(cmd):
    subprocess.check_call(cmd)


def load_packages_from_requirements(requirements_path="requirements.txt"):
    packages = []
    with open(requirements_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sep in (">=", "==", "~=", "<=", "!=", ">", "<"):
                if sep in line:
                    line = line.split(sep, 1)[0].strip()
                    break
            packages.append(line)
    return packages


def main():
    print("=" * 60)
    print(" Lab Automation Environment Setup (Python Installer) ")
    print("=" * 60)
    print()

    print("Project folder:")
    print(os.getcwd())
    print()

    print("Python interpreter in use:")
    print(sys.executable)
    print(sys.version)
    print()

    # Create virtual environment if missing
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        run([sys.executable, "-m", "venv", VENV_DIR])
        print("Virtual environment created.")
    else:
        print("Virtual environment already exists.")

    # OS‑specific pip path
    if platform.system() == "Windows":
        pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        pip_path = os.path.join(VENV_DIR, "bin", "pip")

    required_packages = load_packages_from_requirements()

    print()
    print("Installing required Python packages...")
    for pkg in required_packages:
        print(f"  Installing {pkg}...")
        run([pip_path, "install", pkg])

    print()
    print("=" * 60)
    print(" ✅ INSTALLATION COMPLETED SUCCESSFULLY ")
    print("=" * 60)
    print()
    print("Run your scripts using the virtual environment Python:")
    print("  .\\venv\\Scripts\\python.exe main.py")
    print()
    print("Next steps:")
    print("  1. Get env.local from team lead → place in Github_Auto/")
    print("  2. To push your work: double-click Github_Auto/git-push.bat")
    print("     OR type: push   (in VS Code terminal, after Step 3 below)")
    print("  3. Run this once to enable the push command in terminal:")
    print("     Windows:  Github_Auto\\setup_push_command.bat")
    print("     macOS:    bash Github_Auto/setup_push_command.sh")
    print()

    # Launch floating push button
    try:
        import tkinter as tk
        import threading

        def launch_button():
            root = tk.Tk()
            root.title("")
            root.geometry("180x50+20+20")
            root.attributes("-topmost", True)
            root.overrideredirect(True)
            root.configure(bg="#2d7d46")

            def on_click():
                bat = os.path.join(
                    os.path.dirname(__file__),
                    "Github_Auto",
                    "git-push.bat",
                )
                subprocess.Popen(["cmd", "/c", bat])

            def start_drag(event):
                root._drag_x = event.x
                root._drag_y = event.y

            def on_drag(event):
                x = root.winfo_x() + event.x - root._drag_x
                y = root.winfo_y() + event.y - root._drag_y
                root.geometry(f"+{x}+{y}")

            btn = tk.Button(
                root,
                text="Push to GitHub",
                command=on_click,
                bg="#2d7d46",
                fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                bd=0,
                activebackground="#3a9d5c",
                activeforeground="white",
                cursor="hand2",
                padx=10,
                pady=8,
            )
            btn.pack(fill="both", expand=True)
            btn.bind("<ButtonPress-1>", start_drag)
            btn.bind("<B1-Motion>", on_drag)

            close_btn = tk.Label(
                root,
                text="×",
                bg="#2d7d46",
                fg="white",
                font=("Segoe UI", 12),
                cursor="hand2",
            )
            close_btn.place(relx=1.0, x=-5, y=2, anchor="ne")
            close_btn.bind("<Button-1>", lambda e: root.destroy())

            root.mainloop()

        print("Launching floating Push button on your desktop...")
        print("(You can drag it anywhere on screen. × to close.)")
        t = threading.Thread(target=launch_button, daemon=True)
        t.start()
        input("Press Enter to close this installer window...")

    except Exception:
        pass  # silently skip if tkinter unavailable


if __name__ == "__main__":
    main()
