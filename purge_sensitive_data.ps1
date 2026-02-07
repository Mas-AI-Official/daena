# Purge sensitive folders and files from history and GitHub
# WARNING: This script rewrites git history. Ensure you have a backup of your repository before running.

$repoPath = "D:\Ideas\Daena_old_upgrade_20251213"
Set-Location $repoPath

# 1. Update .gitignore with ALL sensitive items
$gitignorePath = Join-Path $repoPath ".gitignore"
$itemsToIgnore = @(
    "docs/", 
    "daena doc/", 
    "config/production.env", 
    "*.db", 
    "*.sqlite", 
    "*.sqlite3"
)

$content = Get-Content $gitignorePath -Raw
foreach ($item in $itemsToIgnore) {
    if (-not ($content -like "*$item*")) {
        Add-Content -Path $gitignorePath -Value "`n$item"
        Write-Host "Added $item to .gitignore"
    }
    else {
        Write-Host "$item already in .gitignore"
    }
}

# 2. Commit the .gitignore changes if any
# We remove the files from the current index (staging) so they are deleted from the current commit's view of the repo
git add .gitignore
Write-Host "Removing sensitive files from current tracking..."
git rm -r --cached --ignore-unmatch "docs" "daena doc" "config/production.env" "*.db" "*.sqlite" "*.sqlite3"
git commit -m "chore: remove sensitive folders and secrets from tracking and update gitignore"

# 3. Purge from history using filter-branch
Write-Host "Starting history rewrite... this may take a while."
Write-Host "This will remove 'docs', 'daena doc', 'config/production.env' and database files from ALL previous commits."

# The command to run against every commit
# We use quotes carefully for paths with spaces
$filterCommand = 'git rm --cached --ignore-unmatch -r "docs" "daena doc" "config/production.env" "*.db" "*.sqlite" "*.sqlite3"'

# Set env var to allow filter-branch (sometimes needed on Windows git bash, but powershell usually ok)
$env:FILTER_BRANCH_SQUELCH_WARNING = 1

git filter-branch --force --index-filter $filterCommand --prune-empty --tag-name-filter cat -- --all

# 4. Optional Cleanup
# rm -rf .git/refs/original/
# git reflog expire --expire=now --all
# git gc --prune=now --aggressive

Write-Host "`nHistory rewritten." -ForegroundColor Green
Write-Host "CRITICAL STEP:" -ForegroundColor Red
Write-Host "To apply these changes to GitHub, you MUST run the following command manually:"
Write-Host "git push origin --force --all" -ForegroundColor Yellow
