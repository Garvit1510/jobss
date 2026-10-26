# JobLens AI — Test Credentials

## DB: MongoDB Atlas (cluster joblensai.6ghq0p1, DB joblens_ai) since 2026-10-10. Admin is seeded on startup; test1 must be registered again if needed.

## Test user (has resume uploaded)
- email: test1@joblens.dev
- password: Test@12345
- role: user
- Registered via API with device_id "devtest000000000000001"

## Admin (seeded on startup from backend/.env ADMIN_EMAIL / ADMIN_PASSWORD)
- email: admin@joblens.dev
- password: Admin@12345
- role: admin (exempt from device/IP ban check at login). Admin panel at /admin

## Notes
- Admin endpoints: GET /api/admin/stats, /api/admin/bans?status=active|lifted|all, POST /api/admin/bans/{id}/unban, GET /api/admin/users?q=&banned=true, POST /api/admin/users/{id}/unban Auth = email/password JWT in httpOnly cookies (access 60m + refresh 7d).
- Register requires device_id (browser fingerprint, min 16 chars). One account per device_id.
- A 2nd registration from the same device_id BANS that device + IP + the existing account (IP_BAN_ENABLED=true).
- Login elsewhere invalidates the older session (401 "SESSION_REPLACED").

## Endpoints
POST /api/auth/register {name,email,password,device_id}
POST /api/auth/login {email,password,device_id}
GET /api/auth/me · POST /api/auth/refresh · POST /api/auth/logout
