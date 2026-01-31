$ErrorActionPreference = "Stop"

Write-Host "Running Filter-Branch ONLY..."

# Clean refs/original
if (Test-Path ".git/refs/original") {
    Write-Host "Removing old refs/original..."
    Remove-Item -Recurse -Force ".git/refs/original"
}

# Run Filter
# We assume 'docs', 'daena doc', '*.zip' are targets
# We use --force just in case
git filter-branch --force --index-filter "git rm -r --cached --ignore-unmatch 'daena doc' 'docs' '*.zip'" --prune-empty -- --all

# Cleanup
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now

Write-Host "Filter Complete."
