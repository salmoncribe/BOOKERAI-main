# Required Environment Variables

## Backend (.env in BOOKERAI-main)

Make sure your `.env` file contains these variables:

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx or sk_live_xxx
STRIPE_PRICE_ID=price_xxx (your monthly subscription price ID)
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Flask
SECRET_KEY=your_random_secret_key

# Optional
REDIS_URL=redis://localhost:6379 (if using Redis cache)
GIT_REV=v1.0.0 (for asset versioning)
```

## Flutter App (.env in BOOKERAI_app.2)

```env
API_BASE_URL=https://your-backend-url.com
# or for local testing:
# API_BASE_URL=http://localhost:5000
```

## Important Notes

1. **SUPABASE_SERVICE_ROLE_KEY**: Required for `supabase_admin` client to work with `premium_promo_access` table

2. **STRIPE_WEBHOOK_SECRET**: Required for Stripe webhook signature verification

3. **API_BASE_URL** in Flutter app must point to your backend server

## Verification

Run these commands to verify:

```bash
# Backend
cd /Users/michaeltadlock/Developer/BOOKERAI-main
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Supabase URL:', bool(os.getenv('SUPABASE_URL'))); print('Stripe Key:', bool(os.getenv('STRIPE_SECRET_KEY')))"

# Flutter
cd /Users/michaeltadlock/Developer/BOOKERAI_app.2
cat .env
```
