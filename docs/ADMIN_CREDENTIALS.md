# Admin Account Credentials

## System Administrator Accounts

### Primary Admin Account
- **Email**: `admin@example.com`
- **Password**: `admin%2025`
- **Role**: Admin (role_id = 1)
- **Status**: Active, Verified
- **Password Change Required**: No

### Additional Admin Accounts
- **Email**: `kevin.mccullor@xylem.com`
- **Password**: `NewSecurePass123!`
- **Role**: Admin (role_id = 1) 
- **Status**: Active, Verified
- **Password Change Required**: No

- **Email**: `jim.hitchcock@xylem.com`
- **Role**: Admin (role_id = 1)
- **Status**: Active
- **Password Change Required**: Yes (needs password reset on first login)

## Login Test
```python
import requests

BASE_URL = 'http://localhost:8008/api/auth'
login_data = {'email': 'admin@example.com', 'password': 'admin%2025'}
response = requests.post(f'{BASE_URL}/login', json=login_data)

if response.status_code == 200:
    print("✅ Admin login successful")
    data = response.json()
    # Use data['access_token'] for authenticated requests
else:
    print(f"❌ Login failed: {response.text}")
```

## Admin Endpoints Available
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get profile 
- `POST /api/auth/admin-reset` - Reset other users' passwords
- `POST /api/auth/change-password` - Change own password

## Password Reset Completed
✅ Admin password successfully reset to `admin%2025` on October 10, 2025
✅ Login functionality verified and working
✅ Profile endpoint tested and operational
✅ All admin privileges confirmed active