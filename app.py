import os
import re
import uuid
import mimetypes
# Enforce CSS MIME type to prevent registry issues on some OS/environments
mimetypes.add_type('text/css', '.css')
from functools import wraps
from datetime import datetime, timedelta, date

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import stripe
import db  # Added db import
from flask_caching import Cache
from availability import AvailabilityService

# ----------------------------------------------
# Supabase
# ----------------------------------------------
from supabase import create_client, Client
from supabase_client import supabase_admin

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------
# Flask
# ----------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=4)
app.config["SESSION_FILE_DIR"] = "./flask_session"
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

Session(app)

# ----------------------------------------------
# Caching
# ----------------------------------------------
# Try Redis if URL provided, else SimpleCache
redis_url = os.environ.get("REDIS_URL")
if redis_url:
    try:
        cache = Cache(app, config={
            'CACHE_TYPE': 'RedisCache',
            'CACHE_REDIS_URL': redis_url
        })
        # Test connection? (Optional, but RedisCache usually lazy connects)
    except:
         cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})
else:
    # No Redis URL -> SimpleCache (Cloud Run safe)
    cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

availability_service = AvailabilityService(cache)

# ----------------------------------------------
# Stripe
# ----------------------------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")

# ----------------------------------------------
# Helpers
# ----------------------------------------------
@app.context_processor
def inject_globals():
    # Sanitize asset_ver (alphanumeric only) to prevent breaking HTML tags
    raw_ver = os.environ.get("GIT_REV") or datetime.now().strftime("%Y%m%d%H")
    safe_ver = re.sub(r'[^a-zA-Z0-9_\-\.]', '', raw_ver)
    
    return {
        "asset_ver": safe_ver,
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_KEY")
    }

def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if "barberId" not in session:
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return w
def premium_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if "barberId" not in session:
            return redirect(url_for("login"))

        barber_id = session["barberId"]
        barber = supabase.table("barbers").select("plan").eq("id", barber_id).execute().data
        plan = (barber[0].get("plan") if barber else "free") or "free"

        if plan != "premium":
            flash("That feature is Premium. Upgrade to unlock it.", "error")
            return redirect(url_for("dashboard"))
        return fn(*a, **kw)
    return w

def generate_slots(start, end, step):
    """Return list of 'HH:MM' slots. Accepts HH:MM or HH:MM:SS."""
    
    def normalize(t):
        # Strip seconds if present
        return t[:5]

    start = normalize(start)
    end = normalize(end)

    slots = []
    cur = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    step_td = timedelta(minutes=step)

    while cur + step_td <= end_dt:
        slots.append(cur.strftime("%H:%M"))
        cur += step_td

    return slots


def ensure_default_weekly_hours(barber_id):
    existing = supabase.table("barber_weekly_hours") \
        .select("id") \
        .eq("barber_id", barber_id) \
        .execute().data

    if existing:
        return

    defaults = []
    for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        defaults.append({
            "barber_id": barber_id,
            "weekday": day,
            "start_time": "09:00",
            "end_time": "17:00",
            "is_closed": False,
            "location_id": None
        })

    supabase.table("barber_weekly_hours").insert(defaults).execute()

PLAN_FEATURES = {
    "free": {
        "find_pro": True,
        "profile_media": False,
        "analytics": False,
        "ai_tools": False,
        "boosted_visibility": False,
        "locations": True,   # you already have /locations
    },
    "premium": {
        "find_pro": True,
        "profile_media": True,
        "analytics": True,
        "ai_tools": True,
        "boosted_visibility": True,
        "locations": True,
    }
}

def get_features(plan: str):
    plan = (plan or "free").lower().strip()
    return PLAN_FEATURES.get(plan, PLAN_FEATURES["free"])

# ============================================================
# HEALTH CHECKS
# ============================================================
@app.get("/healthz")
def health():
    return jsonify({"ok": True}), 200

@app.get("/status")
def status():
    return "ok"

# ============================================================
# AUTH — BARBER
# ============================================================

def generate_promo_code(name):
    base = re.sub(r"[^A-Z]", "", (name or "PRO").upper())[:6]
    suffix = str(uuid.uuid4().int)[-4:]
    return f"{base}{suffix}"


def create_barber_and_login(name, email, password, phone, bio, address, profession, plan, promo_code=None):
    """
    Shared logic to create a barber account and log them into the session.
    """
    password_hash = generate_password_hash(password)

    # Generate unique promo code if not provided
    if not promo_code:
        while True:
            promo_code = generate_promo_code(name)
            exists = (
                supabase.table("barbers")
                .select("id")
                .eq("promo_code", promo_code)
                .execute()
                .data
            )
            if not exists:
                break
    
    # Insert Barber
    # Note: 'plan' logic is passed in. 
    # For Premium: we might pass 'pending_payment' or just 'premium' but rely on stripe redirect.
    # The requirement says: status="pending_payment" (or equivalent column if exists).
    # Since I didn't see a status column, I will use plan="pending_premium" as discussed.
    
    res = supabase.table("barbers").insert({
        "name": name,
        "email": email,
        "phone": phone,
        "bio": bio,
        "address": address,
        "profession": profession,
        "password_hash": password_hash,
        "slot_duration": 60,
        "plan": plan, 
        "role": "barber",
        "promo_code": promo_code,
    }).execute()

    if not res.data:
        return None

    barber = res.data[0]

    # Auto-login
    session["barberId"] = barber["id"]
    session["user_email"] = barber["email"]
    session["barber_name"] = barber["name"]
    
    # Ensure default data
    ensure_default_weekly_hours(barber["id"])
    
    return barber


def try_redeem_promo(email, promo_code, user_id):
    """
    Attempts to redeem a promo code for premium access.
    Returns True if successful, False otherwise.
    """
    if not supabase_admin:
        print("ERROR: Supabase Admin client not initialized.")
        return False
    
    if not promo_code:
        return False

    try:
        # Normalize inputs
        email = email.strip().lower()
        promo_code = promo_code.strip().lower()

        # Atomic UPDATE: Set used_at/used_by ONLY IF matching row exists and is unused
        # Using ilike for case-insensitive match (though we normalized, ilike is safer/requested)
        res = supabase_admin.table("premium_promo_access").update({
            "used_at": datetime.utcnow().isoformat(),
            "used_by_user_id": user_id
        })\
        .ilike("email", email)\
        .ilike("promo_code", promo_code)\
        .eq("is_active", True)\
        .is_("used_at", "null")\
        .execute()
        
        # Redemption succeeds ONLY if exactly 1 row is returned.
        if res.data and len(res.data) == 1:
            return True
            
        return False

    except Exception as e:
        print(f"Promo redemption error: {e}")
        return False


# ============================================================
# AUTH — BARBER (SIGNUP / LOGIN / LOGOUT)
# ============================================================

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/signup/premium", methods=["GET", "POST"])
def signup_premium():
    if request.method == "GET":
        return render_template("signup_premium.html")

    # Handle JSON or Form Data (preferred JSON for new flow)
    # But for backward compat/form submission we might get form data?
    # The new JS will send JSON.
    data = request.json if request.is_json else request.form

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    phone = data.get("phone")
    bio = data.get("bio", "")
    address = data.get("address", "")
    profession = data.get("profession", "")
    promo_code = (data.get("promo_code") or "").strip()
    
    # Validation
    if not email or not password:
        if request.is_json:
             return jsonify({"ok": False, "error": "Email and password are required."}), 400
        flash("Email and password are required.")
        return redirect(url_for("signup_premium"))

    # Check existing
    existing = supabase.table("barbers").select("id").eq("email", email).execute().data
    if existing:
        if request.is_json:
             return jsonify({"ok": False, "error": "An account with this email already exists."}), 400
        flash("An account with this email already exists.")
        return redirect(url_for("login"))

    # Create Account (Pending Payment or Premium if promo)
    # We start with pending_premium
    barber = create_barber_and_login(
        name=name, email=email, password=password, phone=phone,
        bio=bio, address=address, profession=profession,
        plan="pending_premium" 
    )
    
    if not barber:
        msg = "Signup failed. Please try again."
        if request.is_json:
             return jsonify({"ok": False, "error": msg}), 500
        flash(msg)
        return redirect(url_for("signup_premium"))

    # ------------------------------------------------------------
    # PROMO CODE CHECK
    # ------------------------------------------------------------
    if promo_code:
        redeemed = try_redeem_promo(email, promo_code, barber["id"])
        
        if redeemed:
            # Upgrade user immediately
            # Add timestamp only if used elsewhere (the task said: 
            # "set premium_expires_at ONLY if your existing code already uses it")
            # Existing code uses it for month calculation in add_premium_month. 
            # Let's use add_premium_month to be consistent!
            add_premium_month(barber["id"])
            
            # Also set used_promo_code
            supabase.table("barbers").update({
                "used_promo_code": promo_code
            }).eq("id", barber["id"]).execute()
            
            if request.is_json:
                return jsonify({"ok": True, "skipped_payment": True})
            
            # Fallback for non-JS (unlikely given instructions, but good practice)
            return redirect(url_for("dashboard"))

    # ------------------------------------------------------------
    # STRIPE CHECKOUT (Default)
    # ------------------------------------------------------------
    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=url_for("login", _external=True),
            cancel_url=url_for("signup_premium", _external=True),
            metadata={
                "source": "signup",
                "plan": "premium",
                "barber_id": barber["id"],
                "email": email 
            }
        )
        
        if request.is_json:
             return jsonify({"ok": True, "redirect_url": checkout.url})
             
        return redirect(checkout.url, code=303)
        
    except Exception as e:
        print(f"Stripe Checkout Error: {e}")
        msg = "Account created, but payment initialization failed. Please log in and upgrade from dashboard."
        if request.is_json:
             return jsonify({"ok": True, "redirect_url": url_for("dashboard"), "message": msg}) # Treat as success-ish (account created)
        
        flash(msg)
        return redirect(url_for("dashboard"))

@app.route("/signup/free", methods=["GET", "POST"])
def signup_free():
    if request.method == "GET":
        return render_template("signup_free.html")

    # ------------------------------------------------------------
    # Read form data
    # ------------------------------------------------------------
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").lower().strip()
    password = request.form.get("password")
    phone = request.form.get("phone")
    bio = request.form.get("bio", "")
    address = request.form.get("address", "")
    profession = request.form.get("profession", "")
    # plan is always "free" here
    
    # ------------------------------------------------------------
    # REQUIRED
    # ------------------------------------------------------------
    if not email or not password:
        flash("Email and password are required.")
        return redirect(url_for("signup_free"))

    # Check for existing email in OUR system
    existing = (
        supabase.table("barbers")
        .select("id")
        .eq("email", email)
        .execute()
        .data
    )
    if existing:
        flash("An account with this email already exists.")
        return redirect(url_for("login"))

    # ------------------------------------------------------------
    # FREE SIGNUP → CREATE ACCOUNT IMMEDIATELY
    # ------------------------------------------------------------
    barber = create_barber_and_login(
        name=name, email=email, password=password, phone=phone,
        bio=bio, address=address, profession=profession,
        plan="free"
    )

    if not barber:
        flash("Signup failed. Please try again.")
        return redirect(url_for("signup_free"))

    return redirect(url_for("dashboard"))



    


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password")

    res = supabase.table("barbers").select("*").eq("email", email).execute()
    if not res.data:
        flash("Invalid login")
        return redirect(url_for("login"))

    barber = res.data[0]

    if not check_password_hash(barber["password_hash"], password):
        flash("Invalid login")
        return redirect(url_for("login"))

    session["barberId"] = barber["id"]
    session["user_email"] = barber["email"]
    session["barber_name"] = barber["name"]

    return redirect(url_for("dashboard"))


@app.route('/settings')
def settings():
    if 'barberId' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/help')
def help_center():
    if 'barberId' not in session:
        return redirect(url_for('login'))
    return render_template('help.html')

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("login"))



# ============================================================
# DASHBOARD (BARBER)
# ============================================================
@app.get("/dashboard")
@login_required
def dashboard():
    barber_id = session["barberId"]

    barber = supabase.table("barbers").select("*").eq("id", barber_id).execute().data[0]

    # Optional: auto-downgrade if premium expired (only if you want)
    # If you DON'T want this behavior yet, skip this block.
    expires = barber.get("premium_expires_at")
    if barber.get("plan") == "premium" and expires:
        try:
            exp_dt = datetime.fromisoformat(expires)
            if exp_dt < datetime.utcnow():
                supabase.table("barbers").update({"plan": "free"}).eq("id", barber_id).execute()
                barber["plan"] = "free"
        except:
            pass

    appts = supabase.table("appointments").select("*") \
        .eq("barber_id", barber_id) \
        .order("date").order("start_time").execute().data

    features = get_features(barber.get("plan"))

    # ✅ Always ensure hours exist so free dashboard doesn't break
    ensure_default_weekly_hours(barber_id)

    # Choose which template to render
    if barber.get("plan") == "premium":
        return render_template("dashboard.html", barber=barber, appointments=appts, features=features)

    return render_template("dashboard_free.html", barber=barber, appointments=appts, features=features)


from werkzeug.utils import secure_filename

# ... (other imports are fine, just ensuring secure_filename is available if I could, but I can't add imports inside the function easily with replace. 
# actually I should add the import at the top first or just use it if available. 
# app.py doesn't have secure_filename imported in the view provided.
# I will add it to the top first.)

# Wait, I cannot add imports easily with replace_file_content if I don't see the top. 
# I saw lines 1-50 earlier. It was NOT there.
# I will do a multi_replace to add the import and the functions.

@app.post("/upload-photo")
@premium_required
def upload_photo():
    if "photo" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("dashboard"))
    
    file = request.files["photo"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("dashboard"))

    if file:
        filename = secure_filename(file.filename)
        barber_id = session["barberId"]
        file_path = f"avatars/{barber_id}/{int(datetime.utcnow().timestamp())}_{filename}"
        
        try:
            # Read file data
            file_data = file.read()
            # Upload to Supabase Storage
            # Note: upsert=True if you want to replace, or unique names
            res = supabase.storage.from_("barber_media").upload(file_path, file_data, {"content-type": file.content_type})
            
            # Get Public URL
            public_url = supabase.storage.from_("barber_media").get_public_url(file_path)
            
            # Update Database
            supabase.table("barbers").update({"photo_url": public_url}).eq("id", barber_id).execute()
            
            flash("Profile photo updated!", "success")
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "error")

    return redirect(url_for("dashboard"))

@app.post("/upload-media")
@premium_required
def upload_media():
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("dashboard"))
    
    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("dashboard"))

    if file:
        filename = secure_filename(file.filename)
        barber_id = session["barberId"]
        file_path = f"portfolio/{barber_id}/{int(datetime.utcnow().timestamp())}_{filename}"

        try:
            file_data = file.read()
            res = supabase.storage.from_("barber_media").upload(file_path, file_data, {"content-type": file.content_type})
            public_url = supabase.storage.from_("barber_media").get_public_url(file_path)

            # Append to media_urls (CSV)
            # Fetch current
            barber = supabase.table("barbers").select("media_urls").eq("id", barber_id).execute().data[0]
            current_urls = barber.get("media_urls") or ""
            
            if current_urls:
                new_urls = f"{current_urls},{public_url}"
            else:
                new_urls = public_url
            
            supabase.table("barbers").update({"media_urls": new_urls}).eq("id", barber_id).execute()
            
            flash("Media uploaded!", "success")
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "error")
            
    return redirect(url_for("dashboard"))



# ============================================================
# WEEKLY HOURS
# ============================================================
@app.get("/api/barber/weekly-hours/<barber_id>")
def get_weekly(barber_id):
    rows = supabase.table("barber_weekly_hours").select("*")\
        .eq("barber_id", barber_id).execute().data
    return jsonify(rows)

@app.post("/api/barber/weekly-hours/<barber_id>")
def update_weekly(barber_id):
    hours = request.json

    for row in hours:
        supabase.table("barber_weekly_hours").upsert({
            "barber_id": barber_id,
            "weekday": row["weekday"].lower()[:3],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "is_closed": row["is_closed"],
            "location_id": row.get("location_id"),
        }).execute()

    return jsonify({"success": True})
    return jsonify({"success": True})


# ============================================================
# OVERRIDES
# ============================================================
@app.post("/api/barber/override")
def override():
    data = request.json
    supabase.table("schedule_overrides").upsert(data).execute()
    return jsonify({"success": True})




def add_premium_month(barber_id):
    barber = supabase.table("barbers")\
        .select("premium_expires_at")\
        .eq("id", barber_id).execute().data[0]

    now = datetime.utcnow()

    if barber["premium_expires_at"]:
        try:
            current = datetime.fromisoformat(barber["premium_expires_at"])
            new_expiry = max(current, now) + timedelta(days=30)
        except:
            new_expiry = now + timedelta(days=30)
    else:
        new_expiry = now + timedelta(days=30)

    supabase.table("barbers").update({
        "plan": "premium",
        "premium_expires_at": new_expiry.isoformat()
    }).eq("id", barber_id).execute()

@app.post("/create-premium-checkout")
def create_premium_checkout():
    # Handle both JSON (from new separate flow) or request params if any legacy (but we are moving to JSON)
    try:
        data = request.json
        email = data.get("email") if data else None
        
        if not email:
            return jsonify({"error": "Email is required"}), 400

        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email, # Use the passed email
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=url_for("login", _external=True),
            cancel_url=url_for("signup_premium", _external=True), # Cancel goes back to premium input
            metadata={
                "source": "signup",
                "plan": "premium",
                "email": email 
            }
        )

        return jsonify({"url": checkout.url})
    except Exception as e:
        print(f"Checkout error: {e}")
        return jsonify({"error": str(e)}), 500



@app.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, endpoint_secret
        )
    except Exception:
        return "Invalid", 400

    if event["type"] != "checkout.session.completed":
        return "OK", 200

    session_obj = event["data"]["object"]
    metadata = session_obj.get("metadata", {})
    session_id = session_obj.get("id")
    
    # Retrieve email from customer_details instead of metadata/session root (since we didn't send it)
    email = session_obj.get("customer_details", {}).get("email")

    # ============================================================
    # CASE 1: PREMIUM SIGNUP (Update Pending Account)
    # ============================================================
    if metadata.get("source") == "signup":
        # We now create the account BEFORE Stripe, so we just need to find it and update it.
        # Check by barber_id (preferred) or email.
        
        target_barber_id = metadata.get("barber_id")
        
        if target_barber_id:
            # Update the existing pending account
             supabase.table("barbers").update({
                "plan": "premium", 
                "last_stripe_session_id": session_id,
                # If we want to store customer ID, do it here too
            }).eq("id", target_barber_id).execute()
            
             add_premium_month(target_barber_id)
             ensure_default_weekly_hours(target_barber_id) # Just in case
             
             return "OK", 200
             
        # FALLBACK: If for some reason we didn't pass barber_id (old version?), try to find by email
        # This part assumes account existence logic which we just refactored OUT of webhook for new flow.
        # But if we want to be safe, we can leave the old creation logic as a fallback?
        # The prompt said "reuse existing account creation logic" which implies the new flow.
        # I will assume the new flow is the way forward.
        
        if email:
             # Find user with pending_premium or free
             barber = supabase.table("barbers").select("id").eq("email", email).execute().data
             if barber:
                 barber_id = barber[0]["id"]
                 supabase.table("barbers").update({
                    "plan": "premium", 
                    "last_stripe_session_id": session_id
                }).eq("id", barber_id).execute()
                 add_premium_month(barber_id)
                 return "OK", 200
        
        return "OK", 200

    # ============================================================
    # CASE 2: EXISTING USER UPGRADING
    # ============================================================
    barber = (
        supabase.table("barbers")
        .select("*")
        .eq("email", email)
        .execute()
        .data
    )

    if not barber:
        return "OK", 200

    barber = barber[0]

    if barber.get("last_stripe_session_id") == session_id:
        return "OK", 200

    supabase.table("barbers").update({
        "last_stripe_session_id": session_id
    }).eq("id", barber["id"]).execute()

    add_premium_month(barber["id"])

    if barber.get("used_promo_code"):
        owner = (
            supabase.table("barbers")
            .select("id")
            .eq("promo_code", barber["used_promo_code"])
            .execute()
            .data
        )
        if owner:
            add_premium_month(owner[0]["id"])

    return "OK", 200


# ============================================================
# 30-DAY SCHEDULE GENERATION (Manual + Auto)
# ============================================================
def regenerate_month(barber_id):
    pass

@app.post("/api/barber/generate/<barber_id>")
def manual_generate(barber_id):
    # No-op: RPC handles slots now
    return jsonify({"success": True})


 


# ============================================================
# PUBLIC BOOKING PAGE
# ============================================================
@app.get("/b/<barber_id>")
def book_view(barber_id):
    barber_res = supabase.table("barbers").select("*").eq("id", barber_id).execute()
    if not barber_res.data:
        return "Not found", 404

    barber = barber_res.data[0]

    ensure_default_weekly_hours(barber["id"])

    weekly = (
        supabase.table("barber_weekly_hours")
        .select("*")
        .eq("barber_id", barber_id)
        .execute()
        .data
    ) or []

    hours = {
        row["weekday"]: {
            "open": row.get("start_time"),
            "close": row.get("end_time"),
            "isClosed": row.get("is_closed"),
        }
        for row in weekly
    }

    appts = (
        supabase.table("appointments")
        .select("*")
        .eq("barber_id", barber_id)
        .execute()
        .data
    ) or []

    return render_template(
        "book.html",
        barber=barber,
        hours=hours,
        barber_future_appts=appts,
        appointments=appts,
    )


# ============================================================
# FULL CALENDAR API
# ============================================================
@app.get("/api/calendar/<barber_id>")
def calendar_slots(barber_id):
    rows = supabase.table("schedules").select("*")\
        .eq("barber_id", barber_id).eq("is_available", True)\
        .order("date").order("start_time").execute().data
    return jsonify(rows)

# ============================================================
# APPOINTMENT CREATION
# ============================================================

@app.get("/api/barber/appointments")
@login_required
def get_barber_appointments():
    barber_id = session["barberId"]
    
    # Fetch all appointments for this barber
    # TODO: Filter by month if dataset gets too large, but for now fetch all future
    now = datetime.utcnow().strftime("%Y-%m-%d")
    appts = supabase.table("appointments").select("*")\
        .eq("barber_id", barber_id)\
        .gte("date", now)\
        .neq("status", "cancelled")\
        .order("date").order("start_time").execute().data
        
    return jsonify(appts)


@app.get("/api/public/slots/<barber_id>")
def public_slots(barber_id):
    # Old RPC way - keeping for compat if needed, or we can switch this to use new service too!
    # Let's switch it to use new service for consistency? 
    # User asked for "A Flask API endpoint (GET /api/availability)"
    # But existing frontend calls THIS endpoint. 
    # I should update this function to use availability_service!
    target_date = request.args.get("date")
    if not target_date:
        return jsonify([])
    
    # Defaults to 60 mins if not specified, or fetch from barber
    # For now, let's fetch barber slot_duration to be safe
    barber_res = supabase.table("barbers").select("slot_duration").eq("id", barber_id).execute()
    duration = 60
    if barber_res.data:
        duration = barber_res.data[0].get("slot_duration", 60)

    result = availability_service.get_availability(barber_id, target_date, duration)
    return jsonify(result["slots"])

@app.get("/api/availability")
def get_availability_v2():
    """New standard endpoint"""
    barber_id = request.args.get("barber_id")
    date_str = request.args.get("date")
    service_id = request.args.get("service_id") # Optional, could map to duration
    
    if not barber_id or not date_str:
        return jsonify({"error": "Missing params"}), 400

    # Determine duration
    duration = 60
    if service_id:
        # TODO: lookup service duration if we had a services table
        pass
    else:
        # Fallback to barber default
        barber_res = supabase.table("barbers").select("slot_duration").eq("id", barber_id).execute()
        if barber_res.data:
            duration = barber_res.data[0].get("slot_duration", 60)

    result = availability_service.get_availability(barber_id, date_str, duration)
    # Return just the list of slots as requested
    return jsonify(result["slots"])

@app.post("/api/appointments/create")
def create_appt():
    data = request.json
    # 1. Strict Validation
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required = ["barber_id", "date", "start_time", "client_name", "client_phone"]
    for r in required:
        if not data.get(r):
            return jsonify({"error": f"Missing {r}"}), 400

    barber_id = data["barber_id"]
    d_str = data["date"]
    start_str = data["start_time"]

    # Validate Date Format (YYYY-MM-DD)
    try:
        datetime.strptime(d_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Validate Time Format & Normalize (HH:MM or HH:MM:SS -> HH:MM)
    try:
        # Allow HH:MM or HH:MM:SS, but strictly enforce HH:MM for storage
        parsed_start = datetime.strptime(start_str.split("T")[-1], "%H:%M" if len(start_str.split(":")) == 2 else "%H:%M:%S")
        start_norm = parsed_start.strftime("%H:%M")
    except ValueError:
        return jsonify({"error": "Invalid time format. Use HH:MM."}), 400

    # 2. Calculate Durations & End Time
    barber_res = supabase.table("barbers").select("slot_duration").eq("id", barber_id).execute()
    duration = 60
    if barber_res.data:
        duration = barber_res.data[0].get("slot_duration", 60)
        
    start_dt = datetime.strptime(start_norm, "%H:%M")
    end_dt = start_dt + timedelta(minutes=duration)
    end_norm = end_dt.strftime("%H:%M")

    # Helper to convert to minutes for overlap check
    def to_mins(t_str):
        h, m = map(int, t_str.split(':')[:2])
        return h * 60 + m

    new_start_m = to_mins(start_norm)
    new_end_m = to_mins(end_norm)

    # 3. True Overlap Check
    # Fetch existing appointments for this barber & date
    # Only fetch active ones (not cancelled)
    existing_appts = supabase.table("appointments").select("start_time, end_time")\
        .eq("barber_id", barber_id)\
        .eq("date", d_str)\
        .neq("status", "cancelled")\
        .execute().data

    for appt in existing_appts:
        # Robustly handle existing times
        try:
            e_start_m = to_mins(appt["start_time"])
            if appt.get("end_time"):
                e_end_m = to_mins(appt["end_time"])
            else:
                # Fallback if legacy data has no end_time
                e_end_m = e_start_m + duration
            
            # Allow touching but not overlapping? 
            # Usually: start < existing_end AND end > existing_start
            if new_start_m < e_end_m and new_end_m > e_start_m:
                 return jsonify({
                     "error": "Slot unavailable due to overlap",
                     "conflict": {"start": appt["start_time"], "end": appt.get("end_time")}
                 }), 409
        except Exception:
            # If data is corrupt, skip or log? For safety, treat as potential blocker?
            # Let's log and continue to avoid blocking valid slots due to bad legacy data, 
            # but in strict mode we might want to block. 
            pass

    # 4. Insert with Success Confirmation
    # 4. Insert with Success Confirmation
    # 4. Insert with Success Confirmation (STRICT FIX)
    try:
        # Use full dict for insert to ensure all fields are present
        insert_payload = {
            "barber_id": barber_id,
            "date": d_str,
            "start_time": start_norm,
            "end_time": end_norm,
            "client_name": data.get("client_name"),
            "client_phone": data.get("client_phone"),
            "status": "booked"
        }

        res = supabase.table("appointments").insert(insert_payload).execute()
        
        # FIX: Check for error object/property explicitly if available OR rely on the fact that
        # supabase-py raises exception on error. 
        # For safety per user request: "If res.error exists..."
        # Note: In standard postgrest-py, it raises exception. 
        # But if the user says check res.error, we check it safely.
        if hasattr(res, 'error') and res.error:
            return jsonify({"error": str(res.error)}), 500

        # OPTIONAL: Verify existence to be extra safe (Success Criteria)
        # But fundamentally, if we got here, it worked.
        
        # 5. Invalidate Cache
        try:
            availability_service.invalidate_day(barber_id, d_str)
        except Exception as e:
            print(f"Cache invalidation error: {e}")

        # Return Success
        return jsonify({
            "success": True, 
            "message": "Appointment booked",
            "data": res.data # Optional debug
        }), 200

    except Exception as e:
        print(f"Booking invalid: {e}")
        return jsonify({"error": str(e)}), 500



# ============================================================
# CLIENT ACCOUNT
# ============================================================
@app.post("/client/signup")
def client_signup():
    name = request.form.get("name")
    email = request.form.get("email", "").lower().strip()
    phone = request.form.get("phone")
    password = request.form.get("password")

    hashed = generate_password_hash(password)

    res = supabase.table("clients").insert({
        "name": name,
        "email": email,
        "phone": phone,
        "password_hash": hashed
    }).execute()

    client = res.data[0]
    session["clientId"] = client["id"]

    flash("Account created!", "success")
    return redirect(request.referrer)

@app.post("/client/login")
def client_login():
    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password")

    res = supabase.table("clients").select("*").eq("email", email).execute()
    if not res.data:
        flash("Invalid login")
        return redirect(request.referrer)

    client = res.data[0]

    if not check_password_hash(client["password_hash"], password):
        flash("Invalid login")
        return redirect(request.referrer)

    session["clientId"] = client["id"]
    flash("Logged in!", "success")
    return redirect(request.referrer)

@app.get("/client/logout")
def client_logout():
    session.pop("clientId", None)
    flash("Logged out")
    return redirect(request.referrer or "/")

# ============================================================
# CANCEL APPT (CLIENT ONLY)
# ============================================================
@app.post("/client/appointments/cancel")
def client_cancel():
    cid = session.get("clientId")
    appt_id = request.form.get("appointment_id")

    if not cid:
        return jsonify({"error": "Not logged in"}), 401

    res = supabase.table("appointments").select("*")\
        .eq("id", appt_id).eq("client_id", cid).execute().data

    if not res:
        return jsonify({"error": "Unauthorized"}), 403

    appt = res[0]

    supabase.table("schedules").update({"is_available": True})\
        .eq("barber_id", appt["barber_id"])\
        .eq("date", appt["date"])\
        .eq("start_time", appt["start_time"]).execute()

    supabase.table("appointments").update({"status": "cancelled"})\
        .eq("id", appt_id).execute()

    return jsonify({"success": True})

# ============================================================
# LOCATIONS
# ============================================================
@app.get("/locations")
@login_required
def loc_page():
    barber_id = session["barberId"]
    rows = supabase.table("barber_locations").select("*")\
        .eq("barber_id", barber_id).execute().data
    return render_template("locations.html", locations=rows)

@app.post("/locations/add")
@login_required
def loc_add():
    barber_id = session["barberId"]
    name = request.form.get("name")
    address = request.form.get("address")

    supabase.table("barber_locations").insert({
        "barber_id": barber_id,
        "name": name,
        "address": address
    }).execute()

    flash("Location added")
    return redirect(url_for("loc_page"))

@app.post("/locations/delete")
@login_required
def loc_delete():
    barber_id = session["barberId"]
    loc_id = request.form.get("id")

    supabase.table("barber_locations").delete()\
        .eq("id", loc_id).eq("barber_id", barber_id).execute()

    flash("Location removed")
    return redirect(url_for("loc_page"))

# ============================================================
# PREMIUM (STRIPE)
# ============================================================
@app.route("/subscribe", methods=["GET", "POST"])
@login_required
def subscribe():
    email = session["user_email"]

    session_obj = stripe.checkout.Session.create(
        customer_email=email,
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=url_for("premium_success", _external=True),
        cancel_url=url_for("dashboard", _external=True),
    )

    return redirect(session_obj.url, 303)


@app.get("/subscribe/success")
@login_required
def premium_success():
    # ⚠️ IMPORTANT:
    # Do NOT update plan or promo rewards here.
    # Stripe webhook handles everything.
    
    # Render the success page instead of redirecting
    return render_template("premium_success.html")

# ============================================================
# BASIC PAGES / MARKETING
# ============================================================
@app.get("/")
def home():
    return render_template("home.html")
    
# if you want url_for('home') to be explicit:
app.add_url_rule("/", "home", home)


@app.get("/demo")
def demo():
    return render_template("demo.html")




@app.get("/results")
def results():
    return render_template("results.html")




# ============================================================
# ERROR PAGES
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html"), 500

# ============================================================
# PUBLIC BARBER PROFILE
# ============================================================
@app.get("/profile/<barber_id>")
def profile(barber_id):
    barber = supabase.table("barbers").select("*").eq("id", barber_id).execute().data
    if not barber:
        return "Not found", 404

    weekly = supabase.table("barber_weekly_hours")\
        .select("*").eq("barber_id", barber_id).execute().data

    return render_template("barber_profile.html", barber=barber[0], weekly=weekly)

# ============================================================
# FIND A PRO (SEARCH)
# ============================================================
@app.route("/find-pro", methods=["GET", "POST"], endpoint="find_pro_route")
def find_pro():

    if request.method == "GET":
        # just show the search form
        return render_template("find_pro.html")

    # POST – handle search
    city = (request.form.get("city") or "").strip()
    service = (request.form.get("service") or "").strip()

    # basic guard: if empty, re-show form with flash or simple message
    if not city:
        flash("Please enter a city or location.", "error")
        return render_template("find_pro.html")

    # Build Supabase query
    query = supabase.table("barbers").select("*")

    # match city/location inside address/location fields (case-insensitive)
    # adjust column names if yours are different
    query = query.ilike("address", f"%{city}%")

    if service:
        # match against profession (e.g. "Barber", "Nail Tech", etc.)
        query = query.ilike("profession", f"%{service}%")

    res = query.execute()
    rows = res.data or []

    def plan_rank(barber):
        return 1 if barber.get("plan") == "premium" else 0

    rows.sort(key=plan_rank, reverse=True)

    # Shape data for results.html (what that template expects)
    barbers = []
    for b in rows:
        barbers.append({
            "barberId": b["id"],
            "name": b.get("name"),
            "profession": b.get("profession"),
            # results.html uses b.location → map from address (or your city field)
            "location": b.get("address") or b.get("location") or "",
            "media_url": b.get("media_url"),
        })

    return render_template(
        "results.html",
        barbers=barbers,
        city=city,
        service=service,
    )

@app.route("/confirmed")
def confirmed():
    return render_template("confirmed.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
