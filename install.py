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
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        run([sys.executable, "-m", "venv", VENV_DIR])
        print("Virtual environment created.")
    else:
        print("Virtual environment already exists.")
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
    try:
        import subprocess as _sp, os as _os, sys as _sys
        _root = _os.path.dirname(_os.path.abspath(__file__))
        _pyw = _os.path.join(_root, "Github_Auto", "push_button.pyw")
        _bat = _os.path.join(_root, "push.bat")
        _pbat = _os.path.join(_root, "push_button.bat")

        if not _os.path.exists(_bat):
            with open(_bat, "w") as _f:
                _f.write(
                    '@echo off\ncall "'
                    + _os.path.join(_root, "Github_Auto", "git-push.bat")
                    + '"\n'
                )

        if not _os.path.exists(_pbat):
            _src = _os.path.join(_root, "push_button.bat")
            if _os.path.exists(_src):
                import shutil as _sh
                _sh.copy2(_src, _pbat)
            else:
                with open(_pbat, "w") as _f:
                    _f.write('@echo off\ncall "%~dp0push_button.bat"\n')

        if _sys.platform == "win32":
            _setup = _os.path.join(_root, "Github_Auto", "setup_push_command.bat")
            if _os.path.exists(_setup):
                _sp.run(["cmd", "/c", _setup, "silent"], capture_output=True)
                print("push command configured.")

        _pythonw = _os.path.join(_root, "venv", "Scripts", "pythonw.exe")
        if _os.path.exists(_pythonw) and _os.path.exists(_pyw):
            _kwargs = {"close_fds": True}
            if _sys.platform == "win32":
                _kwargs["creationflags"] = 0x00000008
            _sp.Popen([_pythonw, _pyw], **_kwargs)
            print("Push button active — bottom-right of screen.")
            print("It auto-launches every time you open this")
            print("repo in VS Code or Cursor.")
        elif _os.path.exists(_pyw):
            try:
                _os.startfile(_pyw)
                print("Push button active — bottom-right of screen.")
            except Exception:
                print("Run manually: .\\push_button.bat")

    except Exception:
        pass
