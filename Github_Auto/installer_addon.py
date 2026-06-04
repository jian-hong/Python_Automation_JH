import os
import sys
import subprocess


def run(root):

    # ── 1. Always ensure venv exists and deps are installed ──
    venv_python = os.path.join(root, "venv", "Scripts", "python.exe") \
                  if sys.platform == "win32" else \
                  os.path.join(root, "venv", "bin", "python")
    venv_pip = os.path.join(root, "venv", "Scripts", "pip.exe") \
               if sys.platform == "win32" else \
               os.path.join(root, "venv", "bin", "pip")

    if os.path.exists(venv_pip):
        subprocess.run(
            [venv_pip, "install", "requests", "python-dotenv",
             "--quiet", "--disable-pip-version-check"],
            capture_output=True
        )

    # ── 2. Create push.bat in repo root ──
    push_bat = os.path.join(root, "push.bat")
    git_push = os.path.join(root, "Github_Auto", "git-push.bat")
    if not os.path.exists(push_bat):
        with open(push_bat, "w") as f:
            f.write(f'@echo off\ncall "{git_push}"\n')

    # ── 3. Create push_button.bat in repo root ──
    push_btn_bat = os.path.join(root, "push_button.bat")
    pyw = os.path.join(root, "Github_Auto", "push_button.pyw")
    if not os.path.exists(push_btn_bat):
        with open(push_btn_bat, "w") as f:
            f.write(f'@echo off\nstart "" pythonw "{pyw}"\n')

    # ── 4. Register "push" in PowerShell profile (Windows only) ──
    if sys.platform == "win32":
        ps_cmd = (
            "$p = $PROFILE; "
            "$dir = Split-Path $p; "
            "if(!(Test-Path $dir)){New-Item -ItemType Directory $dir -Force|Out-Null}; "
            "if(!(Test-Path $p)){New-Item -ItemType File $p -Force|Out-Null}; "
            f"$alias = 'function push {{ & \\''{push_bat}\\'' }}'; "
            "$content = Get-Content $p -Raw -ErrorAction SilentlyContinue; "
            "if($content -notlike '*function push*'){"
            "Add-Content -Path $p -Value $alias}; "
            "Write-Host 'push command registered.'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy",
             "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True
        )
        if "registered" in result.stdout:
            print("push command registered — reopen terminal to use it.")

    # ── 5. Update .vscode/settings.json to auto-activate venv ──
    import json
    vscode_dir = os.path.join(root, ".vscode")
    settings_path = os.path.join(vscode_dir, "settings.json")
    os.makedirs(vscode_dir, exist_ok=True)

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except Exception:
            settings = {}

    settings.update({
        "python.defaultInterpreterPath":
            "${workspaceFolder}/venv/Scripts/python.exe",
        "python.terminal.activateEnvironment": True,
        "python.terminal.activateEnvInCurrentTerminal": True,
        "terminal.integrated.env.windows": {
            "VIRTUAL_ENV": "${workspaceFolder}/venv",
            "PATH": "${workspaceFolder}\\venv\\Scripts;${env:PATH}"
        }
    })

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    # ── 6. Launch floating push button silently ──
    if os.path.exists(pyw):
        try:
            subprocess.Popen(["pythonw", pyw])
            print("Push button launched — bottom-right of your screen.")
            print("Relaunch anytime: .\\push_button")
        except Exception:
            pass

    print()
    print("  All done. Reopen your terminal then type: push")
