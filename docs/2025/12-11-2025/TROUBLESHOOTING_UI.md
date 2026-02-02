# Troubleshooting /ui Route Issues

## Problem: `/ui` shows error after login

### Quick Fix Steps:

1. **Restart the Server**
   - Close all backend terminal windows
   - Run `LAUNCH_DAENA_COMPLETE.bat` again
   - Wait 20-30 seconds for full startup

2. **Clear Browser Cache**
   - Press `Ctrl + Shift + Delete`
   - Clear cookies and cached files
   - Or use Incognito/Private mode

3. **Login Flow**
   - Go to: `http://localhost:8000/login`
   - Username: `masoud`
   - Password: `daena2025!` (or your .env password)
   - After login, you'll be redirected to `/ui?token=...`

4. **Check Browser Console**
   - Press `F12` to open Developer Tools
   - Check Console tab for JavaScript errors
   - Check Network tab to see which requests are failing

### Common Errors:

#### "Data source not found"
- **Cause**: API endpoints not receiving authentication token
- **Fix**: Already fixed in code - restart server to apply changes

#### Blank page or "Loading..."
- **Cause**: HTMX requests failing silently
- **Fix**: Check Network tab in browser DevTools to see failed requests

#### Redirect loop
- **Cause**: Token not being stored properly
- **Fix**: Clear cookies and try again

### Manual Test:

1. Open browser DevTools (F12)
2. Go to Console tab
3. Type: `localStorage.getItem('access_token')`
4. If it returns `null`, you need to login again
5. If it returns a token, try: `window.location.href = '/ui?token=' + localStorage.getItem('access_token')`

### Verify Server is Running:

Check if these endpoints work:
- `http://localhost:8000/api/v1/health` - Should return JSON
- `http://localhost:8000/login` - Should show login page
- `http://localhost:8000/docs` - Should show API documentation

### If Still Not Working:

1. Check backend terminal for error messages
2. Look for lines starting with `❌` or `ERROR`
3. Share the error message for further help





