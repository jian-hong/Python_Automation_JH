# Setup guide — PythonAutomation

## Step 1 — Install Python
Download Python 3.14

## Step 2 — Install Git
Download from https://git-scm.com/downloads
During installation, choose "Git from the command line and also from 3rd-party software". Leave all other options as default.

## Step 3 — Clone the repo
Open Command Prompt or PowerShell and run:
git clone https://github.com/RiFtNaWx/PythonAutomation.git
cd PythonAutomation

## Step 4 — Run the installer
In the repo folder, run:
    python install.py
This creates a virtual environment and installs all lab instrument packages.
It only needs to be run once.

## Step 5 — Drop in your env.local
Get the env.local file from the team lead.
Place it inside the Github_Auto/ folder.

## Step 6 — You are ready
To run lab tests:
    .\venv\Scripts\python.exe main.py
Or open main.py in VS Code — it will detect the venv automatically.

To push your work to GitHub:
Double-click Github_Auto/git-push.bat
The script activates the venv automatically — you do not need to do anything extra.
