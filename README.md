# git-agent  CLI

CLI assistant that walks through (or auto-runs) the Git steps needed to push the **current directory** to GitHub: `git init`, `git add .`, first commit on `main`, **`git remote add origin <your-repo-url>`**, and `git push -u origin main`.

## Requirements

- Python 3.10+
- Git on `PATH`
- An empty GitHub repository you created in the browser (the tool asks you to paste its clone URL)

## Install

From this directory:

```bash
pip install -e .
```

That installs the `git-agent` command (or use `python -m git_agent` if Scripts is not on your PATH).

## Usage

```bash
cd /path/to/your/project
git-agent push              # confirm each Git command
git-agent push -y           # skip confirmations for Git steps (you still paste the repo URL)
git-agent push -v           # extra diagnostics on stderr
python -m git_agent push    # same without installing scripts
```

Flow:

1. On GitHub, create a **new empty repository** (no README/license if you want a clean first push from this tool—GitHub’s hints explain this).
2. Run `git-agent push`.
3. When prompted, **paste** the HTTPS or SSH clone URL (e.g. `https://github.com/you/repo.git`).
4. Complete any confirmations; Git handles sign-in for `git push` (browser, credential manager, or SSH).

## Security

- No API tokens are used by this tool.
- Do not paste passwords into the terminal; use normal Git/GitHub authentication for `git push`.

## Legacy script

`python github_push_agent.py` forwards to the same flow as `git-agent push`.
