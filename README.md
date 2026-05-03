# GitHub Push Assistant Agent

A lightweight CLI agent that helps developers push a project to GitHub safely.

## What it does

- Guides you through the required Git push steps
- Shows each command before execution
- Asks for your confirmation before running every command
- Detects common push errors and suggests practical fixes

## Run

```bash
python github_push_agent.py
```

## Typical flow

1. Detect if the folder is a Git repository (`git init` when needed)
2. Ask for a GitHub remote URL (`git remote add origin ...` when needed)
3. Stage and commit changes (if changes exist)
4. Ensure branch naming (`main`) based on your choice
5. Push with upstream (`git push -u origin <branch>`)

## Notes

- Nothing runs automatically; every step asks for explicit confirmation.
- On failures, the agent reads command errors and offers suggested fixes.
