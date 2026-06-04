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
        "SEA_LION_API_KEY": os.getenv("SEA_LION_API_KEY_SISWA"),
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


def generate_commit_message(api_key, model, diff_text, module):
    title = f"update: {module} changes"
    description = "Please describe your changes below."

    try:
        truncated_diff = diff_text[:2000]
        response = requests.post(
            "https://api.sea-lion.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": model,
                "max_completion_tokens": 120,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "You are a git commit assistant. Based on this code diff, generate exactly "
                            "two lines. Line 1: a short commit title under 60 characters starting with "
                            "the type (feat/fix/config). Line 2: a short description under 120 characters "
                            "summarising what changed and why. Output only those two lines, nothing else.\n\n"
                            f"Diff:\n{truncated_diff}"
                        ),
                    }
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) >= 1:
            title = lines[0]
        if len(lines) >= 2:
            description = lines[1]
    except Exception:
        pass

    return title, description


def show_review_popup(default_title, default_description):
    result = {"title": default_title, "description": default_description, "confirmed": False}

    window = tk.Tk()
    window.title("Push your changes — PythonAutomation")
    window.geometry("520x320")
    window.resizable(False, False)

    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (520 // 2)
    y = (window.winfo_screenheight() // 2) - (320 // 2)
    window.geometry(f"520x320+{x}+{y}")

    header = tk.Label(window, text="Review and edit before pushing:", fg="grey", font=("TkDefaultFont", 9))
    header.pack(anchor="w", padx=12, pady=(12, 8))

    tk.Label(window, text="Commit title").pack(anchor="w", padx=12)
    title_entry = tk.Entry(window)
    title_entry.insert(0, default_title)
    title_entry.pack(fill="x", padx=12, pady=(4, 10))

    tk.Label(window, text="PR description").pack(anchor="w", padx=12)
    desc_text = tk.Text(window, height=4)
    desc_text.insert("1.0", default_description)
    desc_text.pack(fill="x", padx=12, pady=(4, 10))

    button_frame = tk.Frame(window)
    button_frame.pack(fill="x", padx=12, pady=(8, 12))

    def on_push():
        result["title"] = title_entry.get().strip()
        result["description"] = desc_text.get("1.0", "end-1c").strip()
        result["confirmed"] = True
        window.destroy()

    def on_cancel():
        result["confirmed"] = False
        window.destroy()

    push_button = tk.Button(
        button_frame,
        text="Push now",
        bg="#2ea44f",
        fg="white",
        activebackground="#2c974b",
        activeforeground="white",
        relief="flat",
        command=on_push,
    )
    push_button.pack(side="left", expand=True, fill="x", padx=(0, 6))

    cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(side="left", expand=True, fill="x", padx=(6, 0))

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

    review_response = requests.post(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/requested_reviewers",
        headers=headers,
        json={"reviewers": [config["DEFAULT_REVIEWER"]]},
        timeout=60,
    )
    review_response.raise_for_status()

    return pr_url


def main():
    try:
        config = load_config()

        print("Pulling latest changes...")
        run_git(["pull", "origin", "main"])

        status = run_git(["status", "--porcelain"])
        changed_lines = [line for line in status.stdout.splitlines() if line.strip()]
        if not changed_lines:
            print("Nothing to commit.")
            return

        changed_files = []
        for line in changed_lines:
            filepath = line[3:].strip()
            if " -> " in filepath:
                filepath = filepath.split(" -> ", 1)[1]
            changed_files.append(filepath)

        diff = run_git(["diff", "HEAD"])
        diff_text = diff.stdout

        module = detect_module(changed_files)
        title, description = generate_commit_message(
            config["SEA_LION_API_KEY"],
            config["SEA_LION_MODEL"],
            diff_text,
            module,
        )

        popup_result = show_review_popup(title, description)
        if not popup_result["confirmed"]:
            print("Cancelled.")
            return

        title = popup_result["title"]
        description = popup_result["description"]

        date_str = datetime.now().strftime("%Y-%m-%d")
        base_branch_name = f"{module}/{date_str}-auto"
        branch_name = get_unique_branch_name(base_branch_name)

        run_git(["checkout", "-b", branch_name])
        run_git(["add", "-A"])
        run_git(["commit", "-m", title])
        run_git(["push", "origin", branch_name])

        pr_url = create_pull_request(config, branch_name, title, description)
        print(pr_url)
        print(f"Done! PR created and sent to {config['DEFAULT_REVIEWER']} for review.")

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
