#!/usr/bin/env bash
# DESTRUCTIVE: Run only at the very END of a test session.
# After this test, IP will be permanently banned for register/login.
# User A account gets banned too.
set -eu
BASE=${BASE:-https://career-lens-ai-3.preview.emergentagent.com}
DEV=bantestdevice$(date +%s)123456
EMAIL_A="TEST_bana_$(date +%s)@ex.com"
EMAIL_B="TEST_banb_$(date +%s)@ex.com"
echo "Register A (should 200)"
curl -s -o /tmp/a.json -w "HTTP=%{http_code}\n" -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"BanA\",\"email\":\"$EMAIL_A\",\"password\":\"Password123!\",\"device_id\":\"$DEV\"}"
echo "Register B same device (should 403)"
curl -s -o /tmp/b.json -w "HTTP=%{http_code}\n" -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"BanB\",\"email\":\"$EMAIL_B\",\"password\":\"Password123!\",\"device_id\":\"$DEV\"}"
echo "Login A (should 403 - banned)"
curl -s -o /tmp/la.json -w "HTTP=%{http_code}\n" -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_A\",\"password\":\"Password123!\",\"device_id\":\"newdev$(date +%s)1234\"}"
cat /tmp/a.json /tmp/b.json /tmp/la.json
