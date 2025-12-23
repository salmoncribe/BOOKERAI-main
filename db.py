from supabase_client import supabase
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone


# ============================================================
# USERS
# ============================================================

def create_user(full_name, email, phone, password, role="client"):
    """Create a new user with hashed password."""
    hashed = generate_password_hash(password)

    data = {
        "full_name": full_name,
        "email": email.lower(),
        "phone": phone,
        "password_hash": hashed,
        "role": role,
        "plan": "free",
        "free_months": 0,
        "expires_at": None,
    }

    result = supabase.table("users").insert(data).execute()
    
    if not result.data:
        return None
    return result.data[0]


def get_user_by_email(email):
    """Fetch a user by email."""
    res = (
        supabase.table("users")
        .select("*")
        .eq("email", email.lower().strip())
        .execute()
    )
    if res.data:
        return res.data[0]
    return None


def verify_user(email, password):
    """Return user on correct password, else None."""
    user = get_user_by_email(email)
    if not user:
        return None
    
    if check_password_hash(user["password_hash"], password):
        return user
    
    return None


def update_user_plan(email, plan):
    """Update user plan (free, premium)."""
    supabase.table("users").update({"plan": plan}).eq("email", email).execute()


def add_free_month(email, months=1):
    """Add free months to a user's account."""
    user = get_user_by_email(email)
    if not user:
        return
    
    new_total = (user.get("free_months") or 0) + months
    supabase.table("users").update({
        "free_months": new_total
    }).eq("email", email).execute()


def check_and_update_premium_status(email):
    """Auto-upgrade/downgrade premium plan based on free_months + expires_at."""
    user = get_user_by_email(email)
    if not user:
        return
    
    free_months = user.get("free_months") or 0
    expires_at = user.get("expires_at")

    # Upgrade if free months available
    if free_months > 0 and user.get("plan") != "premium":
        new_expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        supabase.table("users").update({
            "plan": "premium",
            "expires_at": new_expires,
            "free_months": free_months - 1
        }).eq("email", email).execute()
        return

    # Downgrade if expired
    if user["plan"] == "premium" and expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp < datetime.now(timezone.utc):
                supabase.table("users").update({
                    "plan": "free",
                    "expires_at": None
                }).eq("email", email).execute()
        except:
            pass


# ============================================================
# BARBERS
# ============================================================

def create_barber_profile(user_id, full_name, profession, bio, address, phone):
    """Create a barber profile linked to a user."""
    data = {
        "user_id": user_id,
        "full_name": full_name,
        "profession": profession,
        "bio": bio,
        "address": address,
        "phone": phone,
        "photo_url": "",
        "media_urls": "",
    }
    res = supabase.table("barbers").insert(data).execute()
    return res.data[0]


def get_barber_by_id(barber_id):
    res = supabase.table("barbers").select("*").eq("id", barber_id).execute()
    if res.data:
        return res.data[0]
    return None


def get_barber_by_user_id(user_id):
    res = supabase.table("barbers").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    return None


def search_barbers(city="", profession=""):
    """Search barbers by city + profession (optional)."""
    query = supabase.table("barbers").select("*, locations(*)")

    if city:
        query = query.ilike("address", f"%{city}%")
    if profession:
        query = query.ilike("profession", f"%{profession}%")
    
    res = query.execute()
    return res.data


def update_barber_photo(barber_id, photo_url):
    supabase.table("barbers").update({"photo_url": photo_url}).eq("id", barber_id).execute()


def update_barber_media(barber_id, new_urls):
    """Append new media URLs to media_urls text field."""
    b = get_barber_by_id(barber_id)
    current = b.get("media_urls") or ""
    if current:
        combined = current + "," + new_urls
    else:
        combined = new_urls

    supabase.table("barbers").update({
        "media_urls": combined
    }).eq("id", barber_id).execute()


# ============================================================
# LOCATIONS
# ============================================================

def get_locations_for_barber(barber_id):
    res = supabase.table("locations").select("*").eq("barber_id", barber_id).execute()
    return res.data


# ============================================================
# SCHEDULES
# ============================================================

def create_schedule_slot(barber_id, date, start_time, end_time, location_id=None):
    data = {
        "barber_id": barber_id,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "is_available": True,
        "location_id": location_id
    }
    res = supabase.table("schedules").insert(data).execute()
    return res.data[0]


def get_available_slots(barber_id):
    res = (
        supabase.table("schedules")
        .select("*, locations(*)")
        .eq("barber_id", barber_id)
        .eq("is_available", True)
        .order("date")
        .order("start_time")
        .execute()
    )
    return res.data


def mark_slot_unavailable(schedule_id):
    supabase.table("schedules").update({
        "is_available": False
    }).eq("id", schedule_id).execute()


# ============================================================
# APPOINTMENTS
# ============================================================

def create_appointment(barber_id, schedule_id, service_name,
                       price=0, notes="", user_id=None,
                       guest_name=None, guest_phone=None):
    """Create an appointment for clients or guests."""
    data = {
        "barber_id": barber_id,
        "schedule_id": schedule_id,
        "service_name": service_name,
        "price": price,
        "status": "booked",
        "notes": notes,
        "user_id": user_id,           # client OR None
        "guest_name": guest_name,     # guest only
        "guest_phone": guest_phone,   # guest only
    }

    res = supabase.table("appointments").insert(data).execute()

    # Mark schedule slot unavailable
    mark_slot_unavailable(schedule_id)

    return res.data[0]


def list_barber_appointments(barber_id):
    res = (
        supabase.table("appointments")
        .select("*, schedules(*), users(full_name, email, phone)")
        .eq("barber_id", barber_id)
        .order("id", desc=True)
        .execute()
    )
    return res.data


def list_client_appointments(user_id):
    res = (
        supabase.table("appointments")
        .select("*, schedules(*), barbers(full_name, profession)")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .execute()
    )
    return res.data


def delete_appointment(appointment_id):
    supabase.table("appointments").delete().eq("id", appointment_id).execute()

