$ErrorActionPreference = "Continue"

Write-Host "Nuking Docs and Zips..."

# 0. Clean refs/original just in case
if (Test-Path ".git/refs/original") {
    Write-Host "Removing old refs/original..."
    Remove-Item -Recurse -Force ".git/refs/original"
}

# 1. Update .gitignore (Ensure it's there)
$gitignorePath = ".gitignore"
$rules = @(
    "",
    "# Block Documentation Dumps",
    "daena doc/",
    "docs/",
    "*.zip"
)
Add-Content -Path $gitignorePath -Value $rules
Write-Host "Updated .gitignore."

# 2. Commit the removal from HEAD first (Current State)
Write-Host "Removing from current index..."
git rm -r -f --cached "daena doc" "docs" 2>$null
git add .gitignore
git commit -m "chore: remove confidential docs and archives"
Write-Host "Committed removal."

# 3. Scrub History
Write-Host "Scrubbing history..."
# Using --ignore-unmatch to avoid errors if file missing in some commit
git filter-branch --force --index-filter "git rm -r --cached --ignore-unmatch 'daena doc' 'docs' '*.zip'" --prune-empty -- --all

# 4. Cleanup
Write-Host "Cleaning up garbage..."
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now

Write-Host "Nuke Complete."
