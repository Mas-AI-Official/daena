# Fixing Large File History in Git

Your git push is failing because large files (like `local_brain/` blobs and `.pptx` files) are still in your git history, even though I removed them from the current working tree.

To fix this and successfully push to GitHub, run the following commands in your PowerShell terminal:

```powershell
# 1. Download BFG Repo Cleaner (Optional but faster)
# If you don't have Java/BFG, skip to Option 2.

# 2. Option 2: Using git filter-branch (Built-in, slower but works)
# WARNING: This rewrites history. Make sure you have a backup if needed.

git filter-branch --force --index-filter "git rm --cached --ignore-unmatch local_brain/blobs/*" --prune-empty -- --all
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch *.pptx" --prune-empty -- --all
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch *.zip" --prune-empty -- --all

# 3. Clean up the repo
git for-each-ref --format='delete %(refname)' refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now

# 4. Push changes
git push origin reality_pass_full_e2e --force
```

After running this, your repository size will be significantly smaller and the push will succeed.
