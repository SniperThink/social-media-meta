# TODO: Implement Incoming Webhooks for Instagram Notifications

## Steps to Complete

- [ ] Add FACEBOOK_WEBHOOK_VERIFY_TOKEN and FACEBOOK_APP_SECRET to app/config.py
- [ ] Create app/routes/instagram_webhook.py for webhook endpoints
- [ ] Add Pydantic models for webhook payloads in app/models/schemas.py
- [ ] Implement GET /api/instagram/webhook for verification
- [ ] Implement POST /api/instagram/webhook for notifications with signature verification
- [ ] Handle events by logging them (extend later for DB updates)
- [ ] Update app/main.py to include the new router
- [ ] Update README.md with webhook setup instructions
- [ ] Test the webhook endpoint
