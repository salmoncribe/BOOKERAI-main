-- Create table for password resets
CREATE TABLE IF NOT EXISTS public.password_resets (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    email TEXT NOT NULL,
    token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    used BOOLEAN DEFAULT FALSE
);

-- Index for faster lookup
CREATE INDEX IF NOT EXISTS idx_password_resets_token ON public.password_resets(token);
CREATE INDEX IF NOT EXISTS idx_password_resets_email ON public.password_resets(email);
