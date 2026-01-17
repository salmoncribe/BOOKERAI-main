# Deployment Checklist

## Pre-Deployment

### Database Setup
- [ ] Run `setup_promo_codes.sql` in Supabase SQL editor
- [ ] Verify `premium_promo_access` table exists
- [ ] Create at least one test promo code
- [ ] Test promo code query manually

### Environment Variables
- [ ] Backend `.env` has all required variables (see ENV_VARIABLES.md)
- [ ] Flutter app `.env` points to correct backend URL
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is set (required for admin client)
- [ ] Stripe keys are correct (test vs production)

### Code Review
- [ ] Backend changes in `app.py` reviewed
- [ ] Flutter auth repository changes reviewed
- [ ] Flutter auth provider changes reviewed
- [ ] Flutter register screen changes reviewed

## Testing (Local)

### Backend Testing
```bash
cd /Users/michaeltadlock/Developer/BOOKERAI-main
python app.py
```

- [ ] Server starts without errors
- [ ] Can access health check: `curl http://localhost:5000/status`
- [ ] Can test login: `curl -X POST http://localhost:5000/login -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"test"}'`

### Flutter App Testing
```bash
cd /Users/michaeltadlock/Developer/BOOKERAI_app.2
flutter run
```

Run through all test cases in `TESTING_GUIDE.md`:
- [ ] Free account creation
- [ ] Premium account (no promo)
- [ ] Premium account (TEST code)
- [ ] Premium account (LIVE25 code)
- [ ] Premium account (premium promo code) ⭐
- [ ] Login flow

### Database Verification
After each test, check:
- [ ] Account created in `barbers` table
- [ ] Correct `plan` value set
- [ ] Promo codes marked as used when applicable
- [ ] Premium expiration dates set correctly

## Deployment Steps

### 1. Backend Deployment

#### Option A: Manual Deploy
```bash
cd /Users/michaeltadlock/Developer/BOOKERAI-main
git add .
git commit -m "Fix account creation and payment flow - support premium promo codes"
git push origin main
# Then deploy via your hosting platform
```

#### Option B: Automated Deploy
- [ ] Push to repository
- [ ] Trigger deployment pipeline
- [ ] Wait for deployment to complete
- [ ] Verify deployment logs

### 2. Flutter App Deployment

#### iOS
```bash
cd /Users/michaeltadlock/Developer/BOOKERAI_app.2
flutter build ios --release
# Then submit to App Store
```

#### Android
```bash
cd /Users/michaeltadlock/Developer/BOOKERAI_app.2
flutter build appbundle --release
# Then submit to Play Store
```

## Post-Deployment Verification

### Backend
- [ ] Health check endpoint works: `curl https://your-domain.com/status`
- [ ] Can create free account via web interface
- [ ] Can create premium account and reach Stripe
- [ ] Promo code redemption works
- [ ] Webhooks receiving Stripe events

### Mobile App
- [ ] Download/install app on test device
- [ ] Go through complete signup flow
- [ ] Test with real payment (small amount or test mode)
- [ ] Verify premium features unlock after payment

### Monitoring
- [ ] Check server logs for errors
- [ ] Monitor Stripe dashboard for events
- [ ] Check database for new accounts
- [ ] Review webhook delivery in Stripe

## Rollback Plan

If issues occur:

### Backend Rollback
```bash
git revert HEAD
git push origin main
# Redeploy
```

### Flutter App
- Previous version will still be in App Store/Play Store
- Can revert to previous build if needed

### Database
- Promo codes table is additive only
- No existing data modified
- Can disable promo codes by setting `is_active = false`

## Production Promo Codes

### Creating Production Codes
```sql
-- Create real promo codes in production
INSERT INTO premium_promo_access (email, promo_code, is_active, notes)
VALUES 
  ('influencer@example.com', 'INFLUENCER2026', true, 'Influencer partnership'),
  ('event@example.com', 'EVENT2026', true, 'Event attendees')
ON CONFLICT DO NOTHING;
```

### Managing Promo Codes
- [ ] Document all promo codes created
- [ ] Set up monitoring for promo code usage
- [ ] Create process for generating unique codes
- [ ] Set up alerts for suspicious usage

## Support Preparation

### Documentation
- [ ] Update user-facing documentation
- [ ] Create support articles about promo codes
- [ ] Document common issues and solutions

### Team Training
- [ ] Train support team on new flow
- [ ] Provide troubleshooting guide
- [ ] Set up logging/monitoring dashboards

## Success Metrics

After 24 hours, verify:
- [ ] Free signups working (> 0 new accounts)
- [ ] Premium signups working (> 0 Stripe sessions)
- [ ] No increase in error rates
- [ ] Promo codes being used successfully
- [ ] No user complaints about signup flow

## Emergency Contacts

- Backend Issues: [Your backend dev contact]
- Mobile Issues: [Your mobile dev contact]
- Stripe Issues: [Stripe support]
- Database Issues: [Supabase support]

## Notes

- Keep test promo codes active in production for QA testing
- Monitor first few premium promo redemptions closely
- Be ready to disable promo codes if abuse detected
- Track conversion rates (free vs premium signups)
