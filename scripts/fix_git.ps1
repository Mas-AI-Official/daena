$ErrorActionPreference = "Stop"

Write-Host "Starting Git History Cleanup..."

# 1. Remove blobs
Write-Host "Removing local_brain/blobs..."
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch local_brain/blobs/*" --prune-empty -- --all
if ($LASTEXITCODE -ne 0) { Write-Host "Warning: Blobs cleanup had issues or nothing to clean." }

# 2. Remove PPTX
Write-Host "Removing .pptx files..."
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch *.pptx" --prune-empty -- --all

# 3. Remove ZIPs
Write-Host "Removing .zip files..."
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch *.zip" --prune-empty -- --all

# 4. Cleanup refs and gc
Write-Host "Cleaning up refs..."
git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
git reflog expire --expire=now --all
git gc --prune=now

Write-Host "Git History Fix Complete."
