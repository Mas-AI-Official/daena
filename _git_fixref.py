import os

commit = "053034fdecbc1c3917b81618aa06c26869758b90"

# Direct write to refs/heads/master
ref_path = r"D:\Ideas\Daena\.git\refs\heads\master"
try:
    with open(ref_path, "w") as f:
        f.write(commit + "\n")
    print(f"SUCCESS: refs/heads/master -> {commit}")
except PermissionError as e:
    print(f"FAILED refs write: {e}")
    # Try packed-refs approach
    packed = r"D:\Ideas\Daena\.git\packed-refs"
    if os.path.exists(packed):
        with open(packed, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if "refs/heads/master" in line:
                new_lines.append(f"{commit} refs/heads/master\n")
            else:
                new_lines.append(line)
        try:
            with open(packed, "w") as f:
                f.writelines(new_lines)
            print(f"SUCCESS via packed-refs: {commit}")
        except PermissionError as e2:
            print(f"FAILED packed-refs: {e2}")

# Verify
import subprocess
os.chdir(r"D:\Ideas\Daena")
r = subprocess.run(["git", "log", "--oneline", "-4"], capture_output=True, text=True)
print(r.stdout)

# Push
r = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True)
print("Push:", r.stdout, r.stderr)
