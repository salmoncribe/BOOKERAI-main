# Testing Guide - Account Creation & Payment Flow

## Prerequisites

1. **Backend Server Running**
   ```bash
   cd /Users/michaeltadlock/Developer/BOOKERAI-main
   python app.py
   # Or use your production deployment
   ```

2. **Flutter App Running**
   ```bash
   cd /Users/michaeltadlock/Developer/BOOKERAI_app.2
   flutter run
   ```

3. **Database Setup**
   - Ensure `premium_promo_access` table exists in Supabase
   - Add test promo codes (see SQL below)

## Test Data Setup

### Create Premium Promo Codes in Supabase

```sql
-- Create a premium promo code for testing
INSERT INTO premium_promo_access (email, promo_code, is_active, created_at)
VALUES 
  ('test@bookerai.com', 'FREEPREMIUM', true, NOW()),
  ('demo@bookerai.com', 'TESTPRO2026', true, NOW());
```

## Test Cases

### 1. Free Account Creation ✅

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Starter" (Free) plan
4. Fill in all required fields:
   - Full Name: "Test User"
   - Phone: "555-1234"
   - Profession: Select from dropdown
   - Address: "123 Test St"
   - Email: "freetest@example.com"
   - Password: "password123"
   - Confirm Password: "password123"
5. Check the consent checkbox
6. Tap "Create Account"

**Expected Result:**
- ✅ Account created successfully
- ✅ Success message shown
- ✅ Redirected to `/dashboard/free`
- ✅ User is logged in
- ✅ Database shows `plan="free"` for this user

**Backend Logs to Check:**
```
DEBUG: /signup/free hit
```

---

### 2. Premium Account - No Promo Code 💳

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Pro" (Premium) plan
4. Fill in all required fields:
   - Full Name: "Premium User"
   - Phone: "555-5678"
   - Profession: Select from dropdown
   - Address: "456 Premium Ave"
   - Email: "premium@example.com"
   - Password: "password123"
   - Confirm Password: "password123"
5. Leave Promo Code field EMPTY
6. Check the consent checkbox
7. Tap "Proceed to Payment"

**Expected Result:**
- ✅ Account created with `plan="pending_premium"`
- ✅ "Account Created. Launching Payment..." message shown
- ✅ Stripe checkout opens in external browser
- ✅ Pricing: $20/month
- ✅ After completing payment, webhook updates account to `plan="premium"`

**Backend Logs to Check:**
```
DEBUG: /signup/premium hit. Email len=XX, Promo len=0
DEBUG: Proceeding to Stripe for premium@example.com
```

---

### 3. Premium Account - TEST Code 🆓

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Pro" (Premium) plan
4. Fill in all required fields
5. Enter Promo Code: "TEST"
6. Check the consent checkbox
7. Tap "Proceed to Payment"

**Expected Result:**
- ✅ Account created with `plan="pending_premium"`
- ✅ Stripe checkout opens
- ✅ Pricing: $0.00 (100% discount applied)
- ✅ Complete Stripe flow (no payment required)
- ✅ Webhook updates account to `plan="premium"`

**Backend Logs to Check:**
```
DEBUG: /signup/premium hit. Email len=XX, Promo len=4
DEBUG: Proceeding to Stripe for [email]
```

---

### 4. Premium Account - LIVE25 Code 💵

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Pro" (Premium) plan
4. Fill in all required fields
5. Enter Promo Code: "LIVE25"
6. Check the consent checkbox
7. Tap "Proceed to Payment"

**Expected Result:**
- ✅ Account created with `plan="pending_premium"`
- ✅ Stripe checkout opens
- ✅ Pricing: $15/month (25% discount)
- ✅ After payment, account upgraded to premium

---

### 5. Premium Account - Referral Code 🔗

**Prerequisites:**
1. Create a free or premium account first
2. Note the user's `promo_code` from the database

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Pro" (Premium) plan
4. Fill in all required fields
5. Enter the referral Promo Code (e.g., "JOHN1234")
6. Check the consent checkbox
7. Tap "Proceed to Payment"

**Expected Result:**
- ✅ Account created with `plan="pending_premium"`
- ✅ Stripe checkout opens
- ✅ Pricing: $15/month (25% discount)
- ✅ After payment:
  - New user gets premium
  - Original user gets 1 month added to their premium

---

### 6. Premium Account - Premium Promo Code ⭐ (NEW!)

**Prerequisites:**
```sql
-- Make sure this exists in premium_promo_access table
INSERT INTO premium_promo_access (email, promo_code, is_active)
VALUES ('premiumfree@example.com', 'FREEPREMIUM', true);
```

**Steps:**
1. Open the app
2. Tap "Sign Up"
3. Select "Pro" (Premium) plan
4. Fill in all required fields:
   - Email: "premiumfree@example.com" (MUST match database)
5. Enter Promo Code: "FREEPREMIUM"
6. Check the consent checkbox
7. Tap "Proceed to Payment"

**Expected Result:**
- ✅ Account created with `plan="premium"` immediately
- ✅ Success message: "Premium account created successfully!"
- ✅ Redirected to `/dashboard/premium` WITHOUT going to Stripe
- ✅ User is logged in
- ✅ Database shows:
  - `plan="premium"`
  - `premium_expires_at` set to 1 month from now
  - Promo code in `premium_promo_access` has `used_at` timestamp
  - Promo code `notes` field contains barber ID

**Backend Logs to Check:**
```
DEBUG: /signup/premium hit. Email len=XX, Promo len=11
DEBUG: Valid premium promo code found for premiumfree@example.com
DEBUG: Promo redemption SUCCESS.
```

---

### 7. Login Flow 🔐

**Steps:**
1. After creating any account, log out
2. Tap "Login"
3. Enter email and password
4. Tap "Login"

**Expected Result:**
- ✅ Successfully logged in
- ✅ Redirected to appropriate dashboard (free or premium)
- ✅ User details loaded

---

## Common Issues & Solutions

### Issue: "Invalid login" on first login
**Cause:** Session cookie not being set properly
**Solution:** Check that cookies are enabled in the app

### Issue: Premium promo code not working
**Possible Causes:**
1. Email doesn't match exactly (case-insensitive but must match)
2. Promo code doesn't match exactly (case-insensitive)
3. `is_active` is false
4. `used_at` is not NULL (already used)
5. `supabase_admin` client not initialized

**Debug:**
```sql
-- Check the promo code
SELECT * FROM premium_promo_access 
WHERE LOWER(email) = LOWER('your@email.com') 
  AND LOWER(promo_code) = LOWER('YOURCODE');
```

### Issue: Stripe not opening on mobile
**Solution:** Ensure `url_launcher` package is properly configured in the Flutter app

### Issue: Account created but not redirecting
**Solution:** Check that the route exists in the router configuration

---

## Database Verification Queries

### Check User Account
```sql
SELECT id, email, name, plan, premium_expires_at, used_promo_code
FROM barbers
WHERE email = 'test@example.com';
```

### Check Promo Code Usage
```sql
SELECT * FROM premium_promo_access
WHERE used_at IS NOT NULL
ORDER BY used_at DESC;
```

### Check Stripe Sessions
```sql
SELECT id, email, plan, last_stripe_session_id
FROM barbers
WHERE last_stripe_session_id IS NOT NULL
ORDER BY created_at DESC;
```

---

## Success Metrics

After testing, you should be able to confirm:

- [ ] ✅ Free accounts work
- [ ] ✅ Premium accounts without promo work (Stripe flow)
- [ ] ✅ TEST promo code gives 100% discount
- [ ] ✅ LIVE25 promo code gives 25% discount
- [ ] ✅ Referral codes give 25% discount and credit the referrer
- [ ] ✅ Premium promo codes bypass Stripe entirely
- [ ] ✅ Promo codes are marked as used after redemption
- [ ] ✅ Users are redirected to correct dashboard
- [ ] ✅ Login works for all account types

---

## Video Recording Checklist

If recording a demo, show:
1. Creating a free account → Dashboard
2. Creating premium account with no promo → Stripe opens
3. Creating premium account with premium promo → Direct to dashboard (NO STRIPE!)
4. Database showing the promo code was redeemed
5. Login flow working
