import os

FRONTEND_ROOT = r"d:\Ideas\Daena_old_upgrade_20251213\frontend"
REQUIRED_FILES = [
    "static/css/app.css",
    "static/js/api.js",
    "static/js/app.js",
    "static/js/operator.js",
    "static/js/workspace.js",
    "templates/base.html",
    "templates/partials/sidebar.html",
    "templates/partials/topbar.html",
    "templates/partials/toasts.html",
    "templates/pages/dashboard.html",
    "templates/pages/daena_office.html",
    "templates/pages/founder.html",
    "templates/pages/departments.html",
    "templates/pages/agents.html",
    "templates/pages/workspace.html",
    "templates/pages/operator.html",
    "templates/pages/council.html",
    "templates/pages/analytics.html",
    "templates/pages/system_monitor.html",
    "templates/pages/login_optional.html"
]

def verify_files():
    missing = []
    for rel_path in REQUIRED_FILES:
        full_path = os.path.join(FRONTEND_ROOT, rel_path)
        if not os.path.exists(full_path):
            missing.append(rel_path)
        else:
            # Basic content check
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        print(f"WARNING: {rel_path} is empty!")
            except Exception as e:
                print(f"ERROR reading {rel_path}: {e}")

    if missing:
        print("MISSING FILES:")
        for f in missing:
            print(f" - {f}")
        return False
    else:
        print("All required files exist.")
        return True

if __name__ == "__main__":
    verify_files()
