# Authentication Removal Inventory - Dev Mode

**Date**: 2025-01-12  
**Branch**: `dev/no-auth-dashboard-20250112`  
**Purpose**: Complete inventory of all login/auth related code for local dev mode

---

## 📋 Summary

This inventory documents all authentication and login-related code in the Daena repository. All auth is **disabled** when `DISABLE_AUTH=1` (default for local dev).

---

## 🎨 Templates

### Login Templates
| Path | Purpose | Status | Action |
|------|---------|--------|--------|
| `backend/ui/templates/login.html` | Main login page | ✅ DELETED | Already removed |
| `archive/ui/templates/login_new.html` | Alternative login page | ⚠️ QUARANTINED | In archive |
| `archive/ui/templates/login_old.html` | Legacy login page | ⚠️ QUARANTINED | In archive |

---

## 🛣️ Routes

### Auth Route Files
| Path | Purpose | Referenced By | Type | Action |
|------|---------|---------------|------|--------|
| `archive/routes/auth.py` | Auth API endpoints | None (quarantined) | Security | **QUARANTINED** |
| `backend/middleware/auth_middleware.py` | Auth middleware | `main.py` (commented out) | Security | **DISABLED** |

### Routes Using `Depends(get_current_user)`
All routes now work with `DISABLE_AUTH=True`:
- `get_current_user()` returns `DevUser` when `DISABLE_AUTH=True`
- No 401 errors when auth is disabled
- All `/api/*` routes accessible without tokens

---

## 🔍 Security Utils

| Path | Purpose | Action |
|------|---------|--------|
| `backend/services/auth_service.py` | Core auth service | **MODIFIED** - Returns DevUser when DISABLE_AUTH=True |
| `backend/security/dev_user.py` | Dev user model | **CREATED** - Mock user for local dev |
| `archive/services/jwt_service.py` | JWT utilities | **QUARANTINED** |

---

## ⚙️ Configuration

| File | Change | Purpose |
|------|--------|---------|
| `backend/config/settings.py` | Added `disable_auth: bool = True` (default) | Global dev flag |
| `backend/config/settings.py` | Added `dev_founder_name: str = "Masoud"` | Dev founder name |
| `config/settings.py` | Updated to Pydantic v2 with `protected_namespaces=()` | Fix model_* warnings |

---

## 🚀 Launcher

| File | Change | Purpose |
|------|--------|---------|
| `LAUNCH_DAENA_COMPLETE.bat` | Added `set DISABLE_AUTH=1` | Enable dev mode |
| `LAUNCH_DAENA_COMPLETE.bat` | Added `set DEV_FOUNDER_NAME=Masoud` | Set dev founder |
| `LAUNCH_DAENA_COMPLETE.bat` | Opens `/ui/dashboard` directly | Skip login |

---

## ✅ Implementation Status

### Completed
1. ✅ Created `DevUser` class for mock user
2. ✅ Updated `get_current_user()` to return DevUser when DISABLE_AUTH=True
3. ✅ Updated `get_current_user_optional()` to return DevUser when DISABLE_AUTH=True
4. ✅ Updated UI routes to provide dev user context
5. ✅ Fixed sunflower adjacency `get_neighbor_indices()` to guard invalid k values
6. ✅ Silenced optional council route import errors
7. ✅ Fixed Pydantic namespace warnings
8. ✅ Updated launcher with DISABLE_AUTH env vars
9. ✅ Created agent activation script
10. ✅ Added smoke tests

### How to Re-enable Auth

1. Set `DISABLE_AUTH=0` in `.env` or environment
2. Uncomment auth middleware in `main.py`
3. Restore auth routes from `archive/` if needed
4. Update `get_current_user()` to remove DevUser logic

---

## 📊 Files Changed

**Created:**
- `backend/security/dev_user.py`
- `backend/maintenance/activate_all_agents.py`
- `tests/test_ui_smoke.py` (updated)

**Modified:**
- `backend/config/settings.py` - Added DISABLE_AUTH flag
- `backend/services/auth_service.py` - Returns DevUser when disabled
- `backend/ui/routes_ui.py` - Provides dev user context
- `backend/utils/sunflower.py` - Fixed adjacency k validation
- `backend/main.py` - Silenced council errors
- `config/settings.py` - Fixed Pydantic warnings
- `LAUNCH_DAENA_COMPLETE.bat` - Added env vars

**Quarantined:**
- `archive/routes/auth.py`
- `archive/ui/templates/login_*.html`
- `archive/services/jwt_service.py`
