# GitHub Token Setup for neo-light

## Recommended storage location

**File:** `~/.config/github/token`

A placeholder file has already been created at that location.

## Steps to add your token

1. Edit the file:
   ```bash
   nano ~/.config/github/token
   # or use your editor:
   # code ~/.config/github/token
   # vim ~/.config/github/token
   ```

2. Replace the line `PASTE_YOUR_TOKEN_HERE` with your full token (the entire `ghp_...` or `github_pat_...` string).

3. Save the file.

4. Ensure permissions (already set):
   ```bash
   chmod 600 ~/.config/github/token
   ```

## Why this location?

This follows the same pattern used by the project:
- OpenRouter: `~/.config/openrouter/api_key`
- NVIDIA: `~/Work/Projects/nvapi.key`
- GitHub: `~/.config/github/token`

The `bin/neo` script can be extended later to load `GITHUB_TOKEN` from here automatically.

## Alternative: gh CLI (often easier)

```bash
# One-time setup
gh auth login
# or with token:
# echo "YOUR_TOKEN" | gh auth login --with-token

gh auth setup-git   # wires git to use gh credentials
```

## Security notes

- This file is in your home directory and should be ignored by git (already in .gitignore patterns)
- Never commit tokens to the repository
- Rotate the token if you ever suspect it was exposed
- Use the smallest scopes possible (usually just `repo`)

## Current file content example

The file currently contains instructions + a placeholder line.

You can view it with:
```bash
cat ~/.config/github/token
```
