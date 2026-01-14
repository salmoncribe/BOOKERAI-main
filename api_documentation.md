# BookerAI API Documentation

## 1. Authentication (Barber)
### Login
- **Endpoint**: `POST /login`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Parameters**: `email`, `password`
- **Response**: Redirects to `/dashboard` on success, or re-renders login with error.

### Signup (Free)
- **Endpoint**: `POST /signup/free`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Parameters**: `name`, `email`, `password`, `confirm_password`, `phone`, `bio`, `address`, `profession`, `promo_code`
- **Response**: Redirects to `/dashboard`.

### Signup (Premium)
- **Endpoint**: `POST /signup/premium`
- **Content-Type**: `application/json` or `form-data`
- **Parameters**: Same as free, plus `promo_code` handles discounts.
- **Response**: JSON with `{ ok: true, redirect_url: "..." }` for Stripe Checkout.

### Logout
- **Endpoint**: `GET /logout`
- **Response**: Redirects to login.

---

## 2. Core Barber Data (Dashboard)
### Get Appointments
- **Endpoint**: `GET /api/barber/appointments`
- **Auth Required**: Yes (Session)
- **Response**: JSON Array of appointment objects.
  ```json
  [
    {
      "id": 123,
      "date": "2023-10-25",
      "start_time": "14:00",
      "client_name": "John Doe",
      "status": "booked"
    }
  ]
  ```

### Weekly Schedule (Hours)
- **Endpoint**: `GET /api/barber/weekly-hours/<barber_id>`
- **Response**: JSON Array of schedule rules (Mon-Sun).
- **Endpoint**: `POST /api/barber/weekly-hours/<barber_id>`
- **Payload**:
  ```json
  [
    {
      "weekday": "mon",
      "start_time": "09:00",
      "end_time": "17:00",
      "is_closed": false
    }
  ]
  ```

### Uploads
- **Endpoint**: `POST /upload-photo`
- **Type**: `multipart/form-data`
- **Field**: `photo` (file)
- **Endpoint**: `POST /upload-media`
- **Type**: `multipart/form-data`
- **Field**: `file` (file)

---

## 3. Public Availability & Booking
### Get Availability Slots
- **Endpoint**: `GET /api/availability`
- **Query Params**:
  - `barber_id`: ID of the barber.
  - `date`: YYYY-MM-DD.
- **Response**: JSON Array of available time strings.
  ```json
  ["09:00", "10:00", "14:00"]
  ```

### Book Appointment
- **Endpoint**: `POST /api/appointments/create`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "barber_id": "...",
    "date": "2023-10-25",
    "start_time": "14:00",
    "client_name": "Test User",
    "client_phone": "555-0199"
  }
  ```
- **Response**: `{ success: true, message: "Appointment booked" }`

### Search Professionals
- **Endpoint**: `POST /find-pro`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Parameters**: `city`, `service`
- **Response**: HTML (Server Rendered) - *Note: For mobile, you might want to create a JSON version of this endpoint.*

---

## 4. Client Accounts
- `POST /client/signup` - params: name, email, phone, password.
- `POST /client/login` - params: email, password.
- `POST /client/appointments/cancel` - params: `appointment_id`. 

---

## 5. Stripe / Payments
- `POST /create-premium-checkout` - JSON: `{ email, promo_code }`. Returns Stripe URL.
- `GET /subscribe` - Redirects current user to Stripe Subscription Checkout.
- `POST /api/create-portal-session` - Redirects to Stripe Customer Portal (for cancellation/billing management).
- `POST /stripe/webhook` - Webhook listener for Stripe events.
