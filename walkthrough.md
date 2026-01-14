# Walkthrough & Audit: BookerAI To Mobile App Analysis

This document provides a comprehensive audit of the **BookerAI** web application to facilitate its conversion into a native mobile application.

## 1. Page Inventory & Purpose

| Route | Template | Purpose | Key Features |
|-------|----------|---------|--------------|
| `/` | `home.html` | Landing Page | Marketing, value prop, "Get Started" CTAs. |
| `/login` | `login.html` | Authentication | Barber login form. |
| `/signup` | `signup.html` | Onboarding | Split flow (likely directing to free/premium). |
| `/signup/premium` | `signup_premium.html` | Paid Signup | Account creation + Stripe Checkout integration. |
| `/dashboard` | `dashboard.html` / `_free.html` | **Core Hub** | View appointments, manage hours, upload media, access share links. |
| `/b/<barber_id>` | `book.html` | **Client Booking** | Public facing page for clients to select time & book. |
| `/find-pro` | `find_pro.html` / `results.html` | Discovery | Directory search for barbers by city/service. |
| `/profile/<id>` | `barber_profile.html` | Public Profile | Barber bio, gallery, and "Book Now" link. |
| `/settings` | `settings.html` | Account | (Assumed) Password reset, profile edits. |

## 2. UI/UX Audit (Design System)

**Theme Source**: `static/css/theme.css` & `base.css`

### Color Palette
| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--sky-blue` | `#0ea5e9` | **Primary Brand Color**, Actions, Links |
| `--teal` | `#14b8a6` | Secondary, Gradients, Success states |
| `--text-dark` | `#0f172a` | Headings, Main Text |
| `--muted` | `#64748b` | Subtitles, Secondary Text |
| `--bg-light` | `#f0faff` | App Background (Light Mode) |
| Gradient | `linear-gradient(135deg, #0ea5e9, #14b8a6)` | Headers, Primary Buttons |

### Typography
- **Font Family**: `"Poppins", system-ui, sans-serif`
- **Headings**: bold (700), distinct sizes (`clamp` based).
- **Body**: standard (400), readable line-height (1.6).

### Layout Patterns
- **Glassmorphism**: Cards use `backdrop-filter: blur(12px)` and semi-transparent white backgrounds (`rgba(255, 255, 255, 0.8)`).
- **Cards**: High border-radius (`1.5rem` or `12px`), soft shadows (`0 10px 25px rgba...`).
- **Animations**:
    - `floatGlow`: Hero background elements.
    - `fadeSlideUp`: Cards entering the viewport.
    - Hover Effects: Transport `translateY(-3px)` on buttons.

## 3. Logic Flow & State Management

### Authentication (Current)
- **Mechanism**: Server-side Flask Sessions (Cookies).
- **Mobile Implication**: You will need to either implement a Cookie Jar in the mobile app or Refactor the backend to issue **Auth Tokens (JWT)** for API requests.

### Data Flow
- **Dashboard**:
    - **Initial Load**: Data is injected via Server-Side Rendering (SSR) into the HTML.
    - **Interactive Updates**: Uses `static/js/dashboard.js` to fetch updates (e.g., `openCalendar()` calls `GET /api/barber/appointments`).
- **Booking Flow**:
    - **Step 1**: Client visits public page -> SSR renders available days/hours.
    - **Step 2**: User selects slot -> `GET /api/availability` (via JS) or pre-calculated slots.
    - **Step 3**: Submission -> `POST /api/appointments/create`.

### Key interactive features (JS)
- **Optimistic UI**: Media uploads show a local preview/spinner immediately before the server response confirms success (`dashboard.js` lines 390+).
- **Toggle Hours**: Direct API calls to `POST /api/barber/weekly-hours` on toggle change.

## 4. API Map (Backend Routes)

### Authentication & Account
- `POST /signup/premium` - Create account & initiate Stripe session.
- `POST /login` - Establish session.
- `GET /logout` - Clear session.
- `GET /subscribe/success` - Validation callback from Stripe.

### Core User Features (Barber)
- `GET /api/barber/appointments` - Fetch all future appointments.
- `GET /api/barber/weekly-hours/<id>` - Get schedule rules.
- `POST /api/barber/weekly-hours/<id>` - Update schedule rules.
- `POST /upload-photo` - Avatar update (Multipart/form-data).
- `POST /upload-media` - Gallery upload (Multipart/form-data).
- `GET /api/calendar/<id>` - Get full calendar slots.

### Public & Client Features
- `GET /api/availability?barber_id=X&date=Y` - **Critical**: Get available time slots.
- `POST /api/appointments/create` - **Critical**: Book an appointment. Params: `barber_id`, `date`, `start_time`, `client_name`.
- `POST /api/appointments/cancel` - Cancel an appointment.
- `POST /find-pro` - Search Barbers (City/Service).

### Stripe / Payments
- `POST /create-premium-checkout` - Initiate checkout logic.
- `POST /api/create-portal-session` - Manage subscription.
- `POST /stripe/webhook` - Handle async payment events.
