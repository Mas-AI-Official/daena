---
name: file-ops
description: "File system operations: read, write, search, and manage files in the workspace. Use when user asks to create, modify, find, or organize files."
department: Engineering
cost_tier: low
requires: {}
---

# File Operations Skill

Read, write, search, and manage files in the user's workspace.

## When to Use

- Reading file contents to answer questions about code
- Creating or modifying files as requested
- Searching for files by name or content pattern
- Organizing files (move, rename, delete with confirmation)

## Operations

### Read Files
```bash
cat path/to/file.py
head -50 path/to/file.py
```

### Search Files
```bash
find . -name "*.py" -type f
grep -rn "pattern" src/
```

### Write Files
```bash
cat > path/to/new_file.py << 'EOF'
# file content here
EOF
```

### File Info
```bash
ls -la path/to/file
wc -l path/to/file.py
file path/to/unknown
```

## Safety Rules

- Never delete files without explicit user confirmation
- Always show file contents before overwriting
- Use git status to check for uncommitted changes before bulk operations
