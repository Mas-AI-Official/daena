# 🔍 Daena Breaking Awareness System

## Overview

Daena now has a comprehensive **Breaking Awareness System** that automatically detects and reports all breaks in the system. This system continuously monitors:

- ✅ API endpoint failures
- ✅ Route breaks
- ✅ Template errors
- ✅ Database connection issues
- ✅ Service unavailability
- ✅ Authentication failures
- ✅ Frontend-backend sync issues

## Features

### 1. **Automatic Monitoring**
- Runs every 60 seconds (configurable)
- Starts automatically when backend starts
- Detects breaks in real-time

### 2. **Comprehensive Testing**
- **API Endpoints**: Tests all critical endpoints
- **Routes**: Verifies route registration
- **Templates**: Checks template files exist
- **Database**: Tests database connectivity
- **Frontend-Backend Sync**: Verifies template paths are correct
- **Authentication**: Tests token generation/verification
- **Services**: Checks critical services availability

### 3. **Break Detection**
- Categorizes breaks by type
- Assigns severity levels (critical, high, medium, low)
- Logs all detected breaks
- Maintains history of audits

### 4. **API Endpoints**

#### Get Breaking Status
```http
GET /api/v1/breaking-awareness/status
```
Returns current status and summary of breaks.

#### Get Current Breaks
```http
GET /api/v1/breaking-awareness/breaks
```
Returns all currently detected breaks.

#### Get Break History
```http
GET /api/v1/breaking-awareness/history
```
Returns audit history.

#### Trigger Manual Audit
```http
POST /api/v1/breaking-awareness/audit
```
Manually triggers a full system audit.

#### Get System Health
```http
GET /api/v1/breaking-awareness/health
```
Returns breaking awareness system health.

## Usage

### Automatic (Default)
The system starts automatically when the backend starts. No configuration needed.

### Manual Audit
You can trigger a manual audit via API:
```bash
curl -X POST http://localhost:8000/api/v1/breaking-awareness/audit
```

### Check Status
```bash
curl http://localhost:8000/api/v1/breaking-awareness/status
```

## Break Severity Levels

- **🔴 Critical**: System cannot function (e.g., database down, server down)
- **🟠 High**: Major functionality broken (e.g., API endpoint failing)
- **🟡 Medium**: Minor issues (e.g., optional service unavailable)
- **🟢 Low**: Informational (e.g., warnings)

## Example Response

```json
{
  "status": "active",
  "summary": {
    "total_breaks": 2,
    "by_type": {
      "api_endpoint": 1,
      "template": 1
    },
    "by_severity": {
      "critical": 0,
      "high": 1,
      "medium": 1,
      "low": 0
    },
    "latest_break": {
      "type": "api_endpoint",
      "endpoint": "/api/v1/departments/",
      "error": "HTTP 500",
      "severity": "high",
      "detected_at": "2025-01-14T12:00:00"
    }
  },
  "timestamp": "2025-01-14T12:00:00"
}
```

## Integration

The breaking awareness system is integrated into:
- ✅ `backend/main.py` - Auto-starts on server startup
- ✅ `backend/routes/breaking_awareness.py` - API endpoints
- ✅ `backend/services/breaking_awareness.py` - Core system

## Testing

Run the comprehensive test:
```bash
python test_system_comprehensive.py
```

This will test:
- Frontend routes
- Backend APIs
- Breaking awareness system
- Template files

## Configuration

The system can be configured via environment variables:
- `BREAKING_AWARENESS_INTERVAL` - Check interval in seconds (default: 60)
- `DATABASE_URL` - Database URL for testing (default: sqlite:///./daena.db)

## Next Steps

1. ✅ System is now monitoring automatically
2. ✅ Check `/api/v1/breaking-awareness/status` for current status
3. ✅ Review break history via `/api/v1/breaking-awareness/history`
4. ✅ Fix any detected breaks

Daena is now **self-aware** of system breaks! 🔍

