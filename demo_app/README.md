# Daena Live Demo

A public demonstration of Daena AI VP capabilities.

## What's Included

- **Demo UI**: Interactive router + council demonstration
- **Sample Queries**: Pre-built scenarios showing governance
- **Trace Timeline**: Visual request lifecycle

## NOT Included (Private)

- Full production backend
- Founder panel / admin features
- Database operations
- Voice cloning
- File system access

## Quick Start

```bash
# Requires external Daena backend running
# This demo connects to localhost:8000

# Open demo.html in browser
# Or run the smoke test:
python scripts/demo_smoke_test.py
```

## Demo Flow

1. Open http://localhost:8000/demo
2. Select a sample prompt or type your own
3. Click "RUN DEMO"
4. Watch:
   - Router decision card
   - Council votes (Security, Reliability, Product)
   - Trace timeline
   - Final response

## API Endpoints (Demo Only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/demo/health` | GET | Check demo status |
| `/api/v1/demo/run` | POST | Run demo scenario |
| `/api/v1/demo/trace/{id}` | GET | Get trace timeline |

## Security Notes

- This demo does NOT include authentication
- No sensitive endpoints exposed
- Read-only operations only
- No database migrations

## License

Proprietary - Mas-AI Official
