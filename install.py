import os
import sys
import subprocess
import platform

VENV_DIR = "venv"
REQUIRED_PACKAGES = [
    "pyvisa",
    "pyvisa-py",
    "pandas",
    "openpyxl",
]

def run(cmd):
    subprocess.check_call(cmd)

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

    print()
    print("Installing required Python packages...")
    for pkg in REQUIRED_PACKAGES:
        print(f"  Installing {pkg}...")
        run([pip_path, "install", pkg])

    print()
    print("=" * 60)
    print(" ✅ INSTALLATION COMPLETED SUCCESSFULLY ")
    print("=" * 60)
    print()
    print("Run your scripts using the virtual environment Python:")
    print("  .\\venv\\Scripts\\python.exe main.py")

if __name__ == "__main__":
    main()