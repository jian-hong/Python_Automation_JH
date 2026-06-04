import os
import sys
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
from datetime import datetime

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please run install.py first, then run git-push.bat again.")
    input("Press Enter to close...")
    sys.exit(1)


def run_git(args, check=True):
    """Run a git command and return the CompletedProcess result."""
    try:
        return subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Git command failed: git {' '.join(args)}")
        if exc.stdout:
            print(exc.stdout)
        if exc.stderr:
            print(exc.stderr)
        raise


def load_config():
    load_dotenv(os.path.join(os.path.dirname(__file__), "env.local"))

    required = {
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
        "GITHUB_REPO_OWNER": os.getenv("GITHUB_REPO_OWNER"),
        "GITHUB_REPO_NAME": os.getenv("GITHUB_REPO_NAME"),
        "DEFAULT_BRANCH": os.getenv("DEFAULT_BRANCH"),
        "DEFAULT_REVIEWER": os.getenv("DEFAULT_REVIEWER"),
        "SEA_LION_API_KEY_SISWA": os.getenv("SEA_LION_API_KEY_SISWA"),
        "SEA_LION_MODEL": os.getenv("SEA_LION_MODEL"),
    }

    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return required


def detect_module(changed_files):
    mapping = {
        "opa_tests.py": "opa",
        "level_shifter_tests.py": "level-shifter",
        "ldo_tests.py": "ldo",
        "logic_tests.py": "logic",
        "configurations.py": "config",
        "limits.py": "config",
        "main.py": "core",
    }

    modules = []
    seen = set()
    for filepath in changed_files:
        basename = os.path.basename(filepath)
        module = mapping.get(basename, "general")
        if module not in seen:
            seen.add(module)
            modules.append(module)

    return "-".join(modules) if modules else "general"


def generate_commit_message(api_key, model, diff_text, module, unpushed_log="", unpushed_count=0):
    import re

    title = f"update: {module} changes"
    description = "Please describe your changes below."
    ai_success = False

    def clean(s):
        s = re.sub(r"\s*\(\d+\s*chars?\).*$", "", s)
        s = re.sub(r"^[-*\s]+", "", s)
        return s.strip()

    if not diff_text or len(diff_text.strip()) < 10:
        print("No actual code changes detected in diff.")
        return title, description, ai_success

    try:
        print(f"SEA_LION_API_KEY_SISWA present: {bool(os.getenv('SEA_LION_API_KEY_SISWA'))}")
        print("Calling SEA-LION API...")

        response = requests.post(
            "https://api.sea-lion.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are a git commit assistant.
Summarise ALL of these unpushed changes as one push.

Unpushed commits so far ({unpushed_count}):
{unpushed_log[:500]}

Full diff vs origin/main:
{diff_text[:6000]}

Output exactly two lines:
Line 1: overall commit title (feat/fix/config, under 60 chars)
Line 2: one sentence covering everything changed (under 120 chars)""",
                    }
                ],
            },
            timeout=60,
        )
        print(f"SEA-LION response status: {response.status_code}")
        if response.status_code != 200:
            print(f"SEA-LION error response: {response.text}")
            return title, description, ai_success

        response_data = response.json()
        print(f"SEA-LION full JSON: {response_data}")

        raw = response_data["choices"][0]["message"].get("content")

        if not raw:
            reasoning = response_data["choices"][0]["message"].get("reasoning_content", "")
            matches = re.findall(r"`([^`]{10,})`", reasoning)
            if len(matches) >= 2:
                title = matches[-2].strip()
                description = matches[-1].strip()
                ai_success = True
            elif len(matches) == 1:
                title = matches[-1].strip()
                description = "Please describe your changes below."
                ai_success = True
            else:
                ai_success = False
        else:
            print(f"SEA-LION raw content: {raw}")
            lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
            if len(lines) >= 2:
                title = lines[0]
                description = " ".join(lines[1:])
                ai_success = True
            elif len(lines) == 1:
                title = lines[0]
                description = "Please describe your changes below."
                ai_success = True

        title = clean(title)
        description = clean(description)
    except Exception as exc:
        print(f"SEA-LION call failed: {exc}")

    return title, description, ai_success


def show_review_popup(default_title, default_description, ai_success=True, push_context=""):
    FONT_LABEL = ("Segoe UI", 9)
    FONT_INPUT = ("Consolas", 10)
    FONT_TITLE = ("Segoe UI Semibold", 11)
    FONT_BTN = ("Segoe UI", 10, "bold")

    BG = "#0d1117"
    BAR_BG = "#161b22"
    BORDER = "#30363d"
    TEXT_MUTED = "#8b949e"
    TEXT_PRIMARY = "#e6edf3"
    ACCENT = "#2ea043"

    result = {"title": default_title, "description": default_description, "confirmed": False}

    window = tk.Tk()
    window.title("Push to GitHub — PythonAutomation")
    window.geometry("540x380")
    window.resizable(False, False)
    window.configure(bg=BG)

    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (540 // 2)
    y = (window.winfo_screenheight() // 2) - (380 // 2)
    window.geometry(f"540x380+{x}+{y}")

    top_bar = tk.Frame(window, bg=BAR_BG, height=40)
    top_bar.pack(fill="x")
    top_bar.pack_propagate(False)

    top_left = tk.Frame(top_bar, bg=BAR_BG)
    top_left.pack(side="left", padx=16, pady=10)
    dot_canvas = tk.Canvas(top_left, width=12, height=12, bg=BAR_BG, highlightthickness=0)
    dot_canvas.pack(side="left")
    dot_canvas.create_oval(2, 2, 10, 10, fill=ACCENT, outline="")
    tk.Label(
        top_left,
        text="PythonAutomation",
        bg=BAR_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 10),
    ).pack(side="left", padx=(8, 0))

    tk.Label(
        top_bar,
        text=push_context or "→ ready to push",
        bg=BAR_BG,
        fg=TEXT_MUTED,
        font=("Segoe UI", 9),
    ).pack(side="right", padx=16, pady=10)

    separator = tk.Frame(window, bg=BORDER, height=1)
    separator.pack(fill="x")

    body = tk.Frame(window, bg=BG, padx=20, pady=20)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="Commit title", bg=BG, fg=TEXT_MUTED, font=FONT_LABEL).pack(anchor="w")
    title_entry = tk.Entry(
        body,
        bg=BAR_BG,
        fg=TEXT_PRIMARY,
        insertbackground="white",
        font=FONT_INPUT,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    title_entry.insert(0, default_title)
    title_entry.pack(fill="x", ipady=6, ipadx=8, pady=(4, 0))

    tk.Frame(body, bg=BG, height=12).pack()

    tk.Label(body, text="PR description", bg=BG, fg=TEXT_MUTED, font=FONT_LABEL).pack(anchor="w")
    desc_text = tk.Text(
        body,
        height=6,
        wrap="word",
        bg=BAR_BG,
        fg=TEXT_PRIMARY,
        insertbackground="white",
        font=FONT_INPUT,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    desc_text.insert("1.0", default_description)
    desc_text.pack(fill="x", ipady=6, ipadx=8, pady=(4, 0))

    tk.Frame(body, bg=BG, height=16).pack()

    button_row = tk.Frame(body, bg=BG)
    button_row.pack(fill="x")

    def on_push():
        result["title"] = title_entry.get().strip()
        result["description"] = desc_text.get("1.0", "end-1c").strip()
        result["confirmed"] = True
        window.destroy()

    def on_cancel():
        result["confirmed"] = False
        window.destroy()

    cancel_button = tk.Button(
        button_row,
        text="Cancel",
        command=on_cancel,
        bg="#21262d",
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 10),
        relief="flat",
        bd=0,
        padx=16,
        pady=8,
        cursor="hand2",
        activebackground="#30363d",
        activeforeground=TEXT_PRIMARY,
    )
    cancel_button.pack(side="right", padx=(8, 0))

    push_button = tk.Button(
        button_row,
        text="  Push now  ",
        command=on_push,
        bg=ACCENT,
        fg="white",
        font=FONT_BTN,
        relief="flat",
        bd=0,
        padx=20,
        pady=8,
        cursor="hand2",
        activebackground="#3fb950",
        activeforeground="white",
    )
    push_button.pack(side="right")

    status_text = (
        "SEA-LION AI generated · edit freely before pushing"
        if ai_success
        else "AI unavailable · please describe your changes"
    )
    tk.Label(
        window,
        text=status_text,
        bg=BG,
        fg=TEXT_MUTED,
        font=("Segoe UI", 8),
        padx=20,
        pady=8,
    ).pack(side="bottom", anchor="w")

    window.grab_set()
    window.mainloop()

    return result


def get_unique_branch_name(base_name):
    branch_name = base_name
    suffix = 2
    while True:
        remote = run_git(["ls-remote", "--heads", "origin", branch_name])
        if not remote.stdout.strip():
            return branch_name
        branch_name = f"{base_name}-{suffix}"
        suffix += 1


def create_pull_request(config, branch_name, title, description):
    repo = f"{config['GITHUB_REPO_OWNER']}/{config['GITHUB_REPO_NAME']}"
    headers = {
        "Authorization": f"Bearer {config['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    pr_response = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        headers=headers,
        json={
            "title": title,
            "body": description,
            "head": branch_name,
            "base": config["DEFAULT_BRANCH"],
        },
        timeout=60,
    )
    pr_response.raise_for_status()
    pr_data = pr_response.json()
    pr_number = pr_data["number"]
    pr_url = pr_data["html_url"]
    reviewer = config["DEFAULT_REVIEWER"]

    try:
        reviewer_resp = requests.post(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/requested_reviewers",
            headers=headers,
            json={"reviewers": [reviewer]},
            timeout=60,
        )
        if reviewer_resp.status_code == 422:
            print("Note: Skipping reviewer — PR author cannot review own PR.")
        elif reviewer_resp.status_code not in (200, 201):
            print(f"Reviewer assignment failed: {reviewer_resp.status_code}")
        else:
            print(f"Reviewer {reviewer} assigned successfully.")
    except Exception as e:
        print(f"Could not assign reviewer (non-critical): {e}")

    return pr_url


def main():
    try:
        config = load_config()

        print("Pulling latest changes...")
        run_git(["pull", "origin", "main"])

        subprocess.run(["git", "fetch", "origin"], capture_output=True, text=True)

        diff_result = subprocess.run(
            ["git", "diff", "origin/main...HEAD"],
            capture_output=True,
            text=True,
        )
        diff_text = diff_result.stdout.strip()

        log_result = subprocess.run(
            ["git", "log", "origin/main..HEAD", "--oneline"],
            capture_output=True,
            text=True,
        )
        unpushed_log = log_result.stdout.strip()
        unpushed_count = len([line for line in unpushed_log.splitlines() if line])

        unstaged = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        staged = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
        ).stdout.strip()

        full_diff = "\n".join(filter(None, [diff_text, unstaged, staged]))

        if not full_diff and unpushed_count == 0:
            print("Nothing new compared to origin/main. Nothing to push.")
            return

        changed_files = []
        names_result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
        )
        changed_files.extend(line for line in names_result.stdout.splitlines() if line.strip())

        status = run_git(["status", "--porcelain"])
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            filepath = line[3:].strip()
            if " -> " in filepath:
                filepath = filepath.split(" -> ", 1)[1]
            changed_files.append(filepath)

        module = detect_module(changed_files)
        title, description, ai_success = generate_commit_message(
            config["SEA_LION_API_KEY_SISWA"],
            config["SEA_LION_MODEL"],
            full_diff,
            module,
            unpushed_log=unpushed_log,
            unpushed_count=unpushed_count,
        )

        date_str = datetime.now().strftime("%Y-%m-%d")
        preview_branch = f"{module}/{date_str}-auto"
        push_context = f"→ {unpushed_count} unpushed commit(s) + local changes"

        popup_result = show_review_popup(
            title,
            description,
            ai_success=ai_success,
            push_context=push_context,
        )
        if not popup_result["confirmed"]:
            print("Cancelled.")
            return

        title = popup_result["title"]
        description = popup_result["description"]

        base_branch_name = preview_branch
        branch_name = get_unique_branch_name(base_branch_name)

        run_git(["checkout", "-b", branch_name])
        run_git(["add", "-A"])
        run_git(["commit", "-m", title])
        run_git(["push", "origin", branch_name])

        pr_url = create_pull_request(config, branch_name, title, description)
        print(pr_url)
        print("Done! PR created successfully.")

    except subprocess.CalledProcessError:
        sys.exit(1)
    except requests.HTTPError as exc:
        print(f"GitHub API error: {exc}")
        if exc.response is not None:
            print(exc.response.text)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
