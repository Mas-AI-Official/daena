# Daena Admin Credentials

## Default User Accounts

The following accounts are pre-configured in `backend/services/auth_service.py`:

### 1. Masoud Account (Founder)
- **Username**: `masoud`
- **Password**: `masoudtnt2@`
- **Email**: `masoud@daena.ai`
- **Role**: `founder`
- **User ID**: `masoud_001`

### 2. Admin Account
- **Username**: `admin`
- **Password**: `admin2025!`
- **Email**: `admin@daena.ai`
- **Role**: `admin`
- **User ID**: `admin_001`

### 3. Founder Account
- **Username**: `founder`
- **Password**: `daena2025!`
- **Email**: `founder@daena.ai`
- **Role**: `founder`
- **User ID**: `founder_001`

## Login Endpoint

**POST** `/auth/token`

### Request Body:
```json
{
  "username": "masoud",
  "password": "masoudtnt2@"
}
```

### Response:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user": {
    "username": "masoud",
    "email": "masoud@daena.ai",
    "role": "founder"
  }
}
```

## Using the Token

Include the token in API requests:
```
Authorization: Bearer <access_token>
```

Or use the API key header:
```
X-API-Key: daena_secure_key_2025
```

## Security Note

⚠️ **Change these passwords in production!** These are default development credentials.

To change passwords, edit `backend/services/auth_service.py` and update the password hashes using bcrypt.
