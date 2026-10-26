# Auth testing
- Admin: admin@joblens.dev / Admin@12345 (seeded). Login body needs device_id (>=16 chars).
- Non-admin calling /api/admin/* -> 403 "Admin access required."
- WARNING: registering a 2nd account with same device_id bans device + IP. IP ban means ALL non-admin logins from that IP fail until admin unbans (use /admin or POST /api/admin/bans/{id}/unban).
