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

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def get_git_name():
    for scope in ([], ["--global"], ["--system"]):
        try:
            r = subprocess.run(
                ["git", "config"] + scope + ["user.name"],
                capture_output=True,
                text=True,
                creationflags=NO_WINDOW,
                timeout=5,
            )
            name = r.stdout.strip()
            if name:
                return name
        except Exception:
            continue
    return None


def run_git(args, check=True):
    """Run a git command and return the CompletedProcess result."""
    try:
        return subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=check,
            creationflags=NO_WINDOW,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Git command failed: git {' '.join(args)}")
        if exc.stdout:
            print(exc.stdout)
        if exc.stderr:
            print(exc.stderr)
        raise


def get_current_branch():
    r = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    return (r.stdout or "").strip()


def has_local_changes():
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    return bool((r.stdout or "").strip())


def commits_ahead_of(ref):
    r = subprocess.run(
        ["git", "rev-list", f"{ref}..HEAD", "--count"],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    try:
        return int((r.stdout or "0").strip() or 0)
    except ValueError:
        return 0


def get_last_commit_summary():
    title_r = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    body_r = subprocess.run(
        ["git", "log", "-1", "--pretty=%b"],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    title = (title_r.stdout or "").strip() or "update: changes"
    body = (body_r.stdout or "").strip() or "Committed changes pending review."
    return title, body


def fetch_origin(timeout=45):
    print("Fetching latest from GitHub...")
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print("Warning: fetch timed out — continuing with local git state.")


def remote_branch_exists(branch):
    r = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    return bool((r.stdout or "").strip())


def get_existing_pr_url(config, branch_name):
    owner = config["GITHUB_REPO_OWNER"]
    repo = f"{owner}/{config['GITHUB_REPO_NAME']}"
    headers = {
        "Authorization": f"Bearer {config['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/pulls",
        headers=headers,
        params={
            "head": f"{owner}:{branch_name}",
            "state": "open",
            "base": config["DEFAULT_BRANCH"],
        },
        timeout=60,
    )
    resp.raise_for_status()
    pulls = resp.json()
    return pulls[0]["html_url"] if pulls else None


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


def generate_commit_message(api_key, model, diff_text, module):
    import re

    title = f"update: {module} changes"
    description = "Describe what you changed in this session."
    ai_success = False

    if not diff_text or len(diff_text.strip()) < 10:
        print("No actual code changes detected in diff.")
        return title, description, ai_success

    try:
        print("Asking SEA-LION for summary... (max 15s)")
        sys.stdout.flush()
        response = requests.post(
            "https://api.sea-lion.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a git commit assistant. Be concise and direct.",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Write a git commit summary for these changes.\n"
                            f"Output exactly two lines:\n"
                            f"Line 1: title starting with feat/fix/config, max 60 chars\n"
                            f"Line 2: one sentence max 100 chars\n\n"
                            f"Diff:\n{diff_text[:3000]}"
                        ),
                    },
                ],
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": 0.3,
                "max_tokens": 120,
            },
            timeout=(5, 15),
        )

        if response.status_code != 200:
            print(f"SEA-LION error: {response.status_code}")
            return title, description, False

        data = response.json()
        raw = (data["choices"][0]["message"].get("content") or "").strip()

        if not raw:
            reasoning = data["choices"][0]["message"].get("reasoning_content", "")
            matches = re.findall(r"`([^`]{10,})`", reasoning)
            if len(matches) >= 2:
                raw = matches[-2] + "\n" + matches[-1]
            elif len(matches) == 1:
                raw = matches[-1]

        if not raw:
            return title, description, False

        def clean(s):
            s = re.sub(r"\s*\(\d+\s*chars?\).*$", "", s)
            s = re.sub(r"^[-*\s]+", "", s)
            return s.strip()

        lines = [clean(l) for l in raw.splitlines() if clean(l)]
        if len(lines) >= 2:
            title = lines[0][:60]
            description = " ".join(lines[1:])[:200]
            ai_success = True
        elif len(lines) == 1:
            title = lines[0][:60]
            ai_success = True

    except requests.exceptions.Timeout:
        print("SEA-LION timeout — popup will open for manual input.")
    except Exception as exc:
        print(f"SEA-LION unavailable: {exc}")

    return title, description, ai_success


def show_review_popup(default_title, default_description, ai_success=True, git_name="Team Member", branch_name="main"):
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
        text=f"{git_name}  →  {branch_name}",
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
        else "AI unavailable — describe your changes then click Push now"
    )
    status_fg = TEXT_MUTED if ai_success else "#e3b341"
    tk.Label(
        window,
        text=status_text,
        bg=BG,
        fg=status_fg,
        font=("Segoe UI", 8),
        padx=20,
        pady=8,
    ).pack(side="bottom", anchor="w")

    window.grab_set()
    window.mainloop()

    return result


def create_pull_request(config, branch_name, title, description, git_name="", git_email=""):
    repo = f"{config['GITHUB_REPO_OWNER']}/{config['GITHUB_REPO_NAME']}"
    headers = {
        "Authorization": f"Bearer {config['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    pr_body = f"**Submitted by:** {git_name} ({git_email})\n\n{description}"

    pr_response = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        headers=headers,
        json={
            "title": title,
            "body": pr_body,
            "head": branch_name,
            "base": config["DEFAULT_BRANCH"],
        },
        timeout=60,
    )
    if pr_response.status_code == 422:
        existing = get_existing_pr_url(config, branch_name)
        if existing:
            print(f"Pull request already open: {existing}")
            return existing
        pr_response.raise_for_status()

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


def show_version_history():
    print("Recent commits (latest first):")
    print("-" * 50)
    log = subprocess.run(
        ["git", "log", "--oneline", "--since=30 days ago", "-20"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    lines = log.splitlines()
    for i, line in enumerate(lines):
        print(f"  [{i+1:2d}] {line}")

    print()
    print("To restore a file to a previous version:")
    print("  git checkout <hash> -- filename.py")
    print()
    print("Example — restore configurations.py from 3 commits ago:")
    if len(lines) >= 3:
        hash3 = lines[2].split()[0]
        print(f"  git checkout {hash3} -- configurations.py")
    print()
    print("To see what changed in a specific commit:")
    print("  git show <hash>")
    input("Press Enter to close...")


def main():
    try:
        config = load_config()

        git_name = get_git_name()

        if not git_name:
            from tkinter import simpledialog
            _root = tk.Tk()
            _root.withdraw()
            git_name = simpledialog.askstring(
                "Your name",
                "Enter your name for GitHub PRs:",
                parent=_root,
            ) or "Team Member"
            _root.destroy()
            subprocess.run(
                ["git", "config", "--global", "user.name", git_name],
                capture_output=True,
                creationflags=NO_WINDOW,
            )
            print(f"Saved git name: {git_name}")

        git_email = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW,
        ).stdout.strip()

        fetch_origin()

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

        local_diff = "\n".join(filter(None, [unstaged, staged]))
        full_diff = "\n".join(filter(None, [diff_text, unstaged, staged]))

        default_branch = config["DEFAULT_BRANCH"]
        current_branch = get_current_branch()
        ahead_of_main = commits_ahead_of(f"origin/{default_branch}")
        has_local = bool(local_diff.strip())
        has_commits_vs_main = ahead_of_main > 0

        if not has_local and not has_commits_vs_main:
            print("=" * 50)
            print(" Everything is already up to date.")
            print(" No changes to push. You are in sync with main.")
            print("=" * 50)
            input("Press Enter to close...")
            sys.exit(0)

        if (
            not has_local
            and has_commits_vs_main
            and current_branch != default_branch
            and remote_branch_exists(current_branch)
            and commits_ahead_of(f"origin/{current_branch}") == 0
        ):
            existing_pr = get_existing_pr_url(config, current_branch)
            if existing_pr:
                print("=" * 50)
                print(" Your changes are already on GitHub.")
                print(f" Open PR: {existing_pr}")
                print(" Waiting for review — no need to push again.")
                print("=" * 50)
                input("Press Enter to close...")
                sys.exit(0)

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

        if has_local:
            print("New file changes detected — generating summary...")
            title, description, ai_success = generate_commit_message(
                config["SEA_LION_API_KEY_SISWA"],
                config["SEA_LION_MODEL"],
                local_diff or full_diff,
                module,
            )
        else:
            print("Commits already saved — skipping AI summary.")
            title, description = get_last_commit_summary()
            ai_success = False

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"{module}/{timestamp}"

        if (
            not has_local
            and current_branch != default_branch
            and remote_branch_exists(current_branch)
            and commits_ahead_of(f"origin/{current_branch}") == 0
        ):
            existing_pr = get_existing_pr_url(config, current_branch)
            if existing_pr:
                print("=" * 50)
                print(" Already pushed — no AI or commit needed.")
                print(f" Open PR: {existing_pr}")
                print("=" * 50)
                input("Press Enter to close...")
                sys.exit(0)
            print("Branch on GitHub — creating PR without new commit...")
            branch_name = current_branch
            push_result = run_git(["push", "-u", "origin", branch_name], check=False)
            if push_result.returncode != 0:
                err = (push_result.stderr or "") + (push_result.stdout or "")
                if "up to date" not in err.lower():
                    push_result.check_returncode()
            pr_url = create_pull_request(
                config, branch_name, title, description, git_name, git_email
            )
            print(pr_url)
            print(f"PR created by: {git_name}")
            input("Press Enter to close...")
            sys.exit(0)

        popup_result = show_review_popup(
            title,
            description,
            ai_success=ai_success,
            git_name=git_name,
            branch_name=branch_name,
        )
        if not popup_result["confirmed"]:
            print("Cancelled.")
            return

        title = popup_result["title"]
        description = popup_result["description"]

        current_branch = get_current_branch()
        created_new_branch = False

        if has_local:
            if current_branch == default_branch:
                run_git(["checkout", "-b", branch_name])
                created_new_branch = True
            else:
                branch_name = current_branch
                print(f"Committing on existing branch: {branch_name}")
            run_git(["add", "-A"])
            if has_local_changes():
                run_git(["commit", "-m", title])
            else:
                print("Note: no new files to commit after staging.")
        else:
            if current_branch == default_branch:
                run_git(["checkout", "-b", branch_name])
                created_new_branch = True
            else:
                branch_name = current_branch
                print(f"Reusing branch with existing commits: {branch_name}")
                print("(working tree clean — skipping commit)")

        push_result = run_git(
            ["push", "-u", "origin", branch_name],
            check=False,
        )
        if push_result.returncode != 0:
            err = (push_result.stderr or "") + (push_result.stdout or "")
            if "up to date" in err.lower() or "everything up-to-date" in err.lower():
                print("Branch already pushed to GitHub.")
            else:
                push_result.check_returncode()

        pr_url = create_pull_request(
            config, branch_name, title, description, git_name, git_email
        )
        print(pr_url)
        print(f"PR created by: {git_name}")

        if created_new_branch:
            old_branches = subprocess.run(
                ["git", "branch", "--list", f"{module}/*"],
                capture_output=True,
                text=True,
                creationflags=NO_WINDOW,
            ).stdout.strip().splitlines()

            for old in old_branches:
                old = old.strip().lstrip("* ")
                if old and old != branch_name:
                    subprocess.run(
                        ["git", "branch", "-D", old],
                        capture_output=True,
                        text=True,
                        creationflags=NO_WINDOW,
                    )

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
    if len(sys.argv) > 1 and sys.argv[1] == "--history":
        show_version_history()
    else:
        main()
