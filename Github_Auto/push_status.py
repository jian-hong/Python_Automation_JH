"""Shared git push state for the floating button and git_helper."""
import subprocess
import sys

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _git(repo_root, args, timeout=10):
    return subprocess.run(
        ["git", "-C", repo_root] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=NO_WINDOW,
    )


def get_push_state(repo_root, default_branch="main"):
    """
    state: needs_push | waiting_review | synced | unknown
    local_count: number of uncommitted paths
    """
    out = {
        "state": "unknown",
        "local_count": 0,
        "branch": "",
        "message": "Push to GitHub",
        "detail": "Status unavailable",
    }
    try:
        branch = (_git(repo_root, ["branch", "--show-current"]).stdout or "").strip()
        out["branch"] = branch

        local_files = set()
        for line in (_git(repo_root, ["status", "--porcelain"]).stdout or "").splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            local_files.add(path)
        out["local_count"] = len(local_files)

        if out["local_count"] > 0:
            out["state"] = "needs_push"
            out["message"] = "Ready to push"
            out["detail"] = f"{out['local_count']} uncommitted file(s)"
            return out

        ahead_main = int(
            (_git(repo_root, ["rev-list", f"origin/{default_branch}..HEAD", "--count"]).stdout or "0").strip()
            or 0
        )
        if ahead_main == 0:
            out["state"] = "synced"
            out["message"] = "Up to date"
            out["detail"] = "In sync with main"
            return out

        if branch == default_branch:
            out["state"] = "needs_push"
            out["message"] = "Ready to push"
            out["detail"] = f"{ahead_main} commit(s) on {default_branch}"
            return out

        if (_git(repo_root, ["ls-remote", "--heads", "origin", branch]).stdout or "").strip():
            ahead_remote = int(
                (_git(repo_root, ["rev-list", f"origin/{branch}..HEAD", "--count"]).stdout or "0").strip()
                or 0
            )
            if ahead_remote == 0:
                out["state"] = "waiting_review"
                out["message"] = "Pushed — awaiting review"
                out["detail"] = f"On GitHub ({branch}), not merged yet"
                return out

        out["state"] = "needs_push"
        out["message"] = "Ready to push"
        out["detail"] = f"{ahead_main} commit(s) not on GitHub yet"
        return out

    except Exception:
        return out
