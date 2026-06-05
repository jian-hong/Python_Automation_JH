---

# PythonAutomation — Team Workflow

## What this is
A shared Python codebase for lab hardware test automation.
Each engineer owns their own module file.
All changes go through a Pull Request reviewed by Eugene (RiFtNaWx).

---

## First time setup — do this once on a new machine

**Step 1 — Install Python 3.11**
Download from https://www.python.org/downloads/
On Windows: tick **Add Python to PATH** during install.

**Step 2 — Install Git**
Download from https://git-scm.com/downloads
During install choose: *Git from the command line and also from 3rd-party software*

Set your identity — open any terminal and run:
```
git config --global user.name "Your Full Name"
git config --global user.email "your@email.com"
```

**Step 3 — Clone the repo**
```
git clone https://github.com/RiFtNaWx/PythonAutomation.git
cd PythonAutomation
```

**Step 4 — Run the installer**
```
python install.py
```
This creates the virtual environment, installs all packages,
registers the push command, and launches the push button.
Run this only once per machine.

**Step 5 — Get env.local from team lead**
Ask Eugene for the env.local file.
Place it inside the Github_Auto/ folder.
Never share this file or commit it to GitHub.

**Step 6 — Reopen your terminal**
Close the current terminal and open a new one.
This activates the PATH change so the push command works.

Setup is complete. Never repeat these steps on the same machine.

---

## Daily workflow — pushing your changes

When you finish editing and want to share your work, use any one method:

**Method 1 — Terminal command**
```
push
```
Type this from anywhere inside the repo folder.

**Method 2 — Floating button**
Click the green circle button on your screen.
If it is not visible, type:
```
.\push_button
```

**Method 3 — VS Code**
Terminal menu → Run Task → Push to GitHub

---

## What happens when you push

1. Script checks what you changed vs the main branch
2. SEA-LION AI generates a short title and description (about 20 seconds)
3. A popup shows the AI suggestion — read it, edit if needed
4. Click **Push now**
5. A Pull Request is created on GitHub automatically
6. Eugene reviews and merges

If nothing changed since your last push, the script says
*"Everything is already up to date"* and closes. Nothing is sent.

If AI is unavailable, the popup opens with a blank description.
Type what you changed, click Push now. Works the same.

---

## Before you close for the day

When you click × on the green push button, if you have
unpushed changes it will ask:
*"You have unpushed changes. Push before you go?"*

Click **Push now** to send your work, or **Skip** to close without pushing.

---

## Module ownership

| File | Owner |
|------|-------|
| opa_tests.py | OPA engineer |
| level_shifter_tests.py | Level shifter engineer |
| ldo_tests.py | LDO engineer |
| logic_tests.py | Logic engineer |
| configurations.py, limits.py | Eugene (team lead) |
| main.py | Eugene (team lead) |
| Github_Auto/ | Do not edit unless adding features |

---

## Rules

- Do not edit main.py or configurations.py without checking with Eugene
- Do not share or commit env.local
- Always use the push tool — do not run raw git commands to push
- If push fails, screenshot the terminal and send to Eugene

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| push not recognised | Run `.\Github_Auto\setup_push_command.bat`, close terminal, open new one, then `push` |
| venv not found | Run `python install.py` again |
| Nothing to push message | You are already synced — no action needed |
| AI timeout | Popup opens anyway — type your description manually |
| Push button disappeared | Type `.\push_button` in terminal |
| PR not on GitHub | Check terminal for red error text, send to Eugene |

---

## Repo structure

```
PythonAutomation/
├── Github_Auto/            automation tools
│   ├── git_helper.py       push script (do not edit)
│   ├── push_button.pyw     floating button
│   └── env.local           your keys — never commit this
├── venv/                   Python environment (auto-created)
├── main.py                 run this for lab tests
├── opa_tests.py            OPA module
├── configurations.py       test parameters
├── install.py              run once per machine
├── push.bat                terminal push command
├── push_button.bat         relaunch floating button
└── WORKFLOW.md             this file
```

---

*Questions? Message Eugene on the team chat.*
