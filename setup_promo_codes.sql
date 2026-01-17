-- ============================================================
-- Premium Promo Access Table Setup
-- ============================================================

-- Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS premium_promo_access (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT NOT NULL,
  promo_code TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  used_at TIMESTAMP,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_promo_lookup 
ON premium_promo_access(email, promo_code, is_active);

-- Create index for finding unused codes
CREATE INDEX IF NOT EXISTS idx_promo_unused 
ON premium_promo_access(is_active, used_at) 
WHERE used_at IS NULL;

-- ============================================================
-- Test Promo Codes
-- ============================================================

-- Insert test promo codes for development/testing
INSERT INTO premium_promo_access (email, promo_code, is_active, notes)
VALUES 
  -- General test codes
  ('test@bookerai.com', 'FREEPREMIUM', true, 'Test promo code for QA'),
  ('demo@bookerai.com', 'TESTPRO2026', true, 'Demo promo code'),
  ('qa@bookerai.com', 'QATEST', true, 'QA testing code'),
  
  -- Specific user codes
  ('alice@example.com', 'ALICE2026', true, 'Alice special promo'),
  ('bob@example.com', 'BOBPRO', true, 'Bob special promo')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Verification Queries
-- ============================================================

-- See all promo codes
SELECT 
  email, 
  promo_code, 
  is_active,
  used_at,
  notes,
  created_at
FROM premium_promo_access
ORDER BY created_at DESC;

-- See unused promo codes
SELECT 
  email, 
  promo_code,
  created_at
FROM premium_promo_access
WHERE is_active = true 
  AND used_at IS NULL
ORDER BY created_at DESC;

-- See used promo codes with usage details
SELECT 
  email, 
  promo_code,
  used_at,
  notes as barber_info,
  created_at
FROM premium_promo_access
WHERE used_at IS NOT NULL
ORDER BY used_at DESC;

-- ============================================================
-- Management Queries
-- ============================================================

-- Deactivate a promo code
-- UPDATE premium_promo_access 
-- SET is_active = false 
-- WHERE promo_code = 'CODE_TO_DEACTIVATE';

-- Create a new promo code
-- INSERT INTO premium_promo_access (email, promo_code, is_active, notes)
-- VALUES ('user@example.com', 'NEWCODE', true, 'Reason for this code');

-- Check if a specific promo is valid
-- SELECT * FROM premium_promo_access
-- WHERE LOWER(email) = LOWER('user@example.com')
--   AND LOWER(promo_code) = LOWER('TESTCODE')
--   AND is_active = true
--   AND used_at IS NULL;
