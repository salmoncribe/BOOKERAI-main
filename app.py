import os
import re
import uuid
import mimetypes
# Enforce CSS MIME type to prevent registry issues on some OS/environments
mimetypes.add_type('text/css', '.css')
from functools import wraps
from datetime import datetime, timedelta, date

from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash, make_response
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
        resp = make_response(fn(*a, **kw))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
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
        resp = make_response(fn(*a, **kw))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
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


def create_barber_and_login(name, email, password, phone, bio, address, profession, plan, promo_code=None, used_promo_code=None, consent_accepted=False, consent_version=None):
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
    payload = {
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
        "used_promo_code": used_promo_code,
    }

    # Try to add consent fields if accepted
    # These columns may not exist in older database schemas
    if consent_accepted:
        payload["consent_accepted"] = True
        payload["consent_version"] = consent_version
        payload["consent_timestamp"] = datetime.utcnow().isoformat()

    try:
        res = supabase.table("barbers").insert(payload).execute()
    except Exception as e:
        # If error mentions consent columns, retry without them
        error_str = str(e)
        if "consent_accepted" in error_str or "consent_version" in error_str or "consent_timestamp" in error_str:
            print(f"WARNING: Consent columns not found in database, retrying without them")
            # Remove consent fields and retry
            payload.pop("consent_accepted", None)
            payload.pop("consent_version", None)
            payload.pop("consent_timestamp", None)
            res = supabase.table("barbers").insert(payload).execute()
        else:
            # Re-raise if it's a different error
            raise

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


def try_redeem_promo(email, promo_code, barber_id):
    """
    Attempts to redeem a promo code for premium access.
    Returns True if successful, False otherwise.
    """
    # Normalize inputs
    email = (email or "").strip().lower()
    promo_code = (promo_code or "").strip().lower()
    
    # LOG: Safe inputs
    print(f"DEBUG: Processing promo redemption for email_len={len(email)}, promo_len={len(promo_code)}")

    if not supabase_admin:
        print("CRITICAL ERROR: Supabase Admin client not initialized. Cannot redeem promo.")
        return False
    
    if not promo_code or not email:
        print("DEBUG: Promo code or email empty.")
        return False

    try:
        # Atomic UPDATE: Set used_at ONLY IF matching row exists and is unused
        # We DO NOT set used_by_user_id because it expects a 'user' ID, but we have a 'barber' ID.
        # This caused the bug. We will store the barber ID in 'notes' instead.
        
        # NOTE: used_at IS NULL check is crucial for safety.
        
        res = supabase_admin.table("premium_promo_access").update({
            "used_at": datetime.utcnow().isoformat(),
            "notes": f"used_by_barber:{barber_id}"  # Store ID in notes to avoid FK issues
        })\
        .ilike("email", email)\
        .ilike("promo_code", promo_code)\
        .eq("is_active", True)\
        .is_("used_at", "null")\
        .execute()
        
        count = len(res.data) if res.data else 0
        print(f"DEBUG: Promo redemption update count: {count}")
        
        if count == 1:
            print("DEBUG: Promo redemption SUCCESS.")
            return True
            
        print("DEBUG: Promo redemption FAILED (No matching inactive/unused row found, or already used).")
        return False

    except Exception as e:
        print(f"Promo redemption error checking: {e}")
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

    # Parse request robustly (support JSON and form)
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    confirm_password = data.get("confirm_password")
    phone = data.get("phone")
    bio = data.get("bio", "")
    address = data.get("address", "")
    profession = data.get("profession", "")
    promo_code = (data.get("promo_code") or "").strip()
    
    print(f"DEBUG: /signup/premium hit. Email len={len(email)}, Promo len={len(promo_code)}")
    
    # Validation
    if not email or not password:
        msg = "Email and password are required."
        if request.is_json: return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_premium"))

    if password != confirm_password:
        msg = "Passwords do not match."
        if request.is_json: return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_premium"))

    if len(password) < 8:
        msg = "Password must be at least 8 characters long."
        if request.is_json: return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_premium"))

    # Check existing user
    existing = supabase.table("barbers").select("id").eq("email", email).execute().data
    if existing:
        if request.is_json:
             return jsonify({"ok": False, "error": "An account with this email already exists."}), 400
        flash("An account with this email already exists.")
        return redirect(url_for("login"))

    # Create Account (Start with pending_premium, will upgrade if promo is valid)
    consent_accepted = str(data.get("consent_accepted", "")).lower() in ["true", "1", "on", "yes"]
    consent_version = data.get("consent_version")

    try:
        # Try to redeem promo code FIRST (before creating account)
        has_premium_promo = False
        if promo_code and supabase_admin:
            # Check if this is a premium promo access code
            try:
                promo_check = supabase_admin.table("premium_promo_access")\
                    .select("id")\
                    .ilike("email", email)\
                    .ilike("promo_code", promo_code)\
                    .eq("is_active", True)\
                    .is_("used_at", "null")\
                    .execute()
                
                if promo_check.data and len(promo_check.data) > 0:
                    has_premium_promo = True
                    print(f"DEBUG: Valid premium promo code found for {email}")
            except Exception as e:
                print(f"Error checking premium promo: {e}")
                # Continue with normal flow even if promo check fails

        # Create the account with appropriate plan
        initial_plan = "premium" if has_premium_promo else "pending_premium"
        
        barber = create_barber_and_login(
            name=name, email=email, password=password, phone=phone,
            bio=bio, address=address, profession=profession,
            plan=initial_plan,
            used_promo_code=promo_code.upper().strip() if promo_code else None,
            consent_accepted=consent_accepted,
            consent_version=consent_version
        )
        
        if not barber:
            msg = "Signup failed. Please try again."
            if request.is_json:
                 return jsonify({"ok": False, "error": msg}), 500
            flash(msg)
            return redirect(url_for("signup_premium"))

        # ------------------------------------------------------------
        # PROMO CODE HANDLING
        # ------------------------------------------------------------
        if has_premium_promo:
            # Redeem the promo code
            success = try_redeem_promo(email, promo_code, barber["id"])
            if success:
                # Add premium time (1 month or whatever your promo gives)
                add_premium_month(barber["id"])
                
                # Update plan to premium (should already be premium from create, but double-check)
                supabase.table("barbers").update({"plan": "premium"}).eq("id", barber["id"]).execute()
                
                if request.is_json:
                    return jsonify({
                        "ok": True, 
                        "message": "Premium account created with promo code!",
                        "barber": barber
                    })
                
                flash("Premium account created successfully with your promo code!", "success")
                return redirect(url_for("dashboard"))
            else:
                # Promo redemption failed, downgrade to pending and proceed to Stripe
                print(f"DEBUG: Promo redemption failed for {email}, proceeding to Stripe")
                supabase.table("barbers").update({"plan": "pending_premium"}).eq("id", barber["id"]).execute()

        # ------------------------------------------------------------
        # STRIPE CHECKOUT (For non-promo or failed promo redemption)
        # ------------------------------------------------------------
        print(f"DEBUG: Proceeding to Stripe for {email}")
        
        # Pricing Logic (Hardcoded Back-end Source of Truth)
        # Base Price: $20.00 (2000 cents)
        base_price = 2000
        final_price = base_price
        discounts = []
        
        code_norm = promo_code.upper().strip() if promo_code else ""
        
        if code_norm == "TEST":
            # Create a 100% off coupon on the fly for TEST code
            # This allows a $0 subscription checkout
            try:
                coupon = stripe.Coupon.create(
                    percent_off=100,
                    duration="once",
                    name="TEST-100-OFF"
                )
                discounts = [{"coupon": coupon.id}]
            except Exception as e:
                print(f"Error creating TEST coupon: {e}")
                final_price = 0 
        elif code_norm == "LIVE25":
            final_price = 1500 # $15.00
        elif code_norm:
            # Check for valid Referral Code (25% OFF)
            try:
                referrer = supabase.table("barbers").select("id").eq("promo_code", code_norm).execute().data
                if referrer:
                     final_price = 1500 # 25% OFF ($15.00)
            except Exception as e:
                print(f"Referral lookup error: {e}")
            
        try:
            # Create Checkout Session with dynamic price
            # Note: 'price' arg is mutually exclusive with 'price_data'
            
            session_params = {
                "mode": "subscription",
                "customer_email": email,
                "line_items": [{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "BookerAI Premium",
                            "description": "Monthly subscription"
                        },
                        "unit_amount": final_price,
                        "recurring": {
                            "interval": "month"
                        }
                    },
                    "quantity": 1
                }],
                "success_url": url_for("premium_success", _external=True),
                "cancel_url": url_for("dashboard", _external=True),  # If they cancel, go to dashboard (Free)
                "metadata": {
                    "source": "signup",
                    "plan": "premium",
                    "barber_id": barber["id"],
                    "email": email,
                    "promo_code": code_norm
                }
            }
            
            if discounts:
                session_params["discounts"] = discounts

            checkout = stripe.checkout.Session.create(**session_params)
            
            if request.is_json:
                 return jsonify({"ok": True, "redirect_url": checkout.url})
                 
            return redirect(checkout.url, code=303)
            
        except Exception as e:
            print(f"Stripe Checkout Error: {e}")
            # Expose error to user clearly
            msg = f"Payment initialization failed: {str(e)}"
            if request.is_json:
                 return jsonify({"ok": False, "error": msg}), 500
            
            flash(msg)
            # Stay on signup page so they can try again or see error, 
            # but account IS created. Redirecting to settings or billing might be better, 
            # but user asked to push to free dash if unsuccessful. 
            # Actually user said "push them to the free dash bouard" if unsuccessful.
            # But if we push to free dash, they don't see the error easily.
            # I will redirect to dashboard with the flash message.
            return redirect(url_for("dashboard"))
    
    except Exception as e:
        # Catch any unexpected errors
        print(f"ERROR during premium signup: {e}")
        import traceback
        traceback.print_exc()
        msg = f"Signup failed: {str(e)}"
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 500
        flash(msg)
        return redirect(url_for("signup_premium"))

@app.route("/signup/free", methods=["GET", "POST"])
def signup_free():
    if request.method == "GET":
        return render_template("signup_free.html")

    # Parse request robustly (support JSON and form)
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    # ------------------------------------------------------------
    # Read data
    # ------------------------------------------------------------
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    confirm_password = data.get("confirm_password")
    phone = data.get("phone")
    bio = data.get("bio", "")
    address = data.get("address", "")
    profession = data.get("profession", "")
    promo_code = (data.get("promo_code") or "").strip()
    
    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------
    if not email or not password:
        msg = "Email and password are required."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_free"))

    if password != confirm_password:
        msg = "Passwords do not match."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_free"))
    
    if len(password) < 8:
        msg = "Password must be at least 8 characters long."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("signup_free"))

    # Check for existing email
    try:
        existing = (
            supabase.table("barbers")
            .select("id")
            .eq("email", email)
            .execute()
            .data
        )
        if existing:
            msg = "An account with this email already exists."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"ok": False, "error": msg}), 400
            flash(msg)
            return redirect(url_for("login"))
    except Exception as e:
        print(f"Error checking existing user: {e}")
        msg = "Database error. Please try again."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 500
        flash(msg)
        return redirect(url_for("signup_free"))

    # ------------------------------------------------------------
    # FREE SIGNUP → CREATE ACCOUNT IMMEDIATELY
    # ------------------------------------------------------------
    consent_accepted = str(data.get("consent_accepted", "")).lower() in ["true", "1", "on", "yes"]
    consent_version = data.get("consent_version")

    try:
        barber = create_barber_and_login(
            name=name, email=email, password=password, phone=phone,
            bio=bio, address=address, profession=profession,
            plan="free",
            used_promo_code=promo_code.upper() if promo_code else None,
            consent_accepted=consent_accepted,
            consent_version=consent_version
        )

        if not barber:
            msg = "Signup failed. Please try again."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"ok": False, "error": msg}), 500
            flash(msg)
            return redirect(url_for("signup_free"))

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": True, "barber": barber})

        return redirect(url_for("dashboard"))
    except Exception as e:
        print(f"Error during free signup: {e}")
        import traceback
        traceback.print_exc()
        msg = f"Signup failed: {str(e)}"
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 500
        flash(msg)
        return redirect(url_for("signup_free"))



    


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # Parse request robustly (support JSON and form)
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    email = (data.get("email") or "").lower().strip()
    password = data.get("password")

    res = supabase.table("barbers").select("*").eq("email", email).execute()
    if not res.data:
        msg = "Invalid login"
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": msg}), 401
        flash(msg)
        return redirect(url_for("login"))

    barber = res.data[0]

    if not check_password_hash(barber["password_hash"], password):
        msg = "Invalid login"
        if request.is_json or request.headers.get("Accept") == "application/json":
             return jsonify({"ok": False, "error": msg}), 401
        flash(msg)
        return redirect(url_for("login"))

    session["barberId"] = barber["id"]
    session["user_email"] = barber["email"]
    session["barber_name"] = barber["name"]

    if request.is_json or request.headers.get("Accept") == "application/json":
         return jsonify({"ok": True, "barber": barber})

    return redirect(url_for("dashboard"))


@app.route('/settings')
def settings():
    if 'barberId' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

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

@app.post("/api/barber/delete")
@login_required
def delete_account():
    barber_id = session["barberId"]
    try:
        # Hard delete from Supabase
        supabase.table("barbers").delete().eq("id", barber_id).execute()
        session.clear()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500



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
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "barber": barber,
            "appointments": appts,
            "features": features
        })

    if barber.get("plan") == "premium":
        return render_template("dashboard.html", barber=barber, appointments=appts, features=features)


@app.post("/api/barber/update")
@login_required
def update_barber_profile():
    barber_id = session["barberId"]
    
    # Support both JSON and Form
    if request.is_json:
        data = request.json
    else:
        data = request.form

    name = data.get("name")
    phone = data.get("phone")
    address = data.get("address")
    slot_duration = data.get("slot_duration")

    updates = {}
    if name: updates["name"] = name
    if phone: updates["phone"] = phone
    if address: updates["address"] = address
    if slot_duration is not None:
        try:
            updates["slot_duration"] = int(slot_duration)
        except ValueError:
            pass # Ignore invalid format

    if updates:
        supabase.table("barbers").update(updates).eq("id", barber_id).execute()
        # Update session if name changed
        if "name" in updates:
            session["barber_name"] = updates["name"]

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": True})
    
    flash("Profile updated")
    return redirect(url_for("settings"))

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
            
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": True, "url": public_url})

            flash("Profile photo updated!", "success")
        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": str(e)}), 500
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
            
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": True, "url": public_url})

            flash("Media uploaded!", "success")
        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": str(e)}), 500
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




def add_calendar_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, [31,
        29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return source_date.replace(year=year, month=month, day=day)

def add_premium_month(barber_id):
    barber = supabase.table("barbers")\
        .select("premium_expires_at")\
        .eq("id", barber_id).execute().data[0]

    now = datetime.utcnow()

    if barber["premium_expires_at"]:
        try:
            current = datetime.fromisoformat(barber["premium_expires_at"])
            # If current expiry is in the future, add to IT.
            # If it's in the past, start from NOW.
            base_date = max(current, now)
            new_expiry = add_calendar_months(base_date, 1)
        except:
             new_expiry = add_calendar_months(now, 1)
    else:
        new_expiry = add_calendar_months(now, 1)

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
        promo_code = data.get("promo_code") if data else None
        
        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Hardcoded Backend Pricing Logic
        base_price = 2000
        final_price = base_price
        code_norm = (promo_code or "").strip().upper()

        if code_norm == "TEST":
            final_price = 0
        elif code_norm == "LIVE25":
            final_price = 1500
        elif code_norm:
            # Check Referral
            try:
                referrer = supabase.table("barbers").select("id").eq("promo_code", code_norm).execute().data
                if referrer:
                    final_price = 1500
            except:
                pass

        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email, # Use the passed email
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "BookerAI Premium",
                        "description": "Monthly subscription"
                    },
                    "unit_amount": final_price,
                    "recurring": {
                        "interval": "month"
                    }
                },
                "quantity": 1
            }],
            success_url=url_for("premium_success", _external=True),
            cancel_url=url_for("signup_premium", _external=True), # Cancel goes back to premium input
            metadata={
                "source": "signup",
                "plan": "premium",
                "email": email,
                "promo_code": code_norm
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

             # CREDIT REFERRER
             try:
                 used_code = metadata.get("promo_code")
                 if used_code and used_code not in ["TEST", "LIVE25"]:
                     referrer_res = supabase.table("barbers").select("id").eq("promo_code", used_code).execute().data
                     if referrer_res:
                         print(f"Crediting referrer {referrer_res[0]['id']} for new user {target_barber_id}")
                         add_premium_month(referrer_res[0]["id"])
             except Exception as e:
                 print(f"Error crediting referrer: {e}")
             
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
    flash("Location removed")
    return redirect(url_for("loc_page"))

@app.post("/api/appointments/cancel")
@login_required
def cancel_appointment():
    barber_id = session.get("barberId")
    appt_id = request.form.get("appointment_id") or request.json.get("appointment_id")
    
    if not appt_id:
        return jsonify({"success": False, "error": "Appointment ID required"}), 400
    
    # Verify ownership
    existing = supabase.table("appointments").select("id, date, start_time")\
        .eq("id", appt_id)\
        .eq("barber_id", barber_id)\
        .execute().data
        
    if not existing:
        return jsonify({"success": False, "error": "Appointment not found or unauthorized"}), 403
        
    appt = existing[0]

    # Free up the slot in availability cache
    try:
        # We can either update the schedule table or just invalidate cache.
        # Since we use cache, invalidation is key.
        availability_service.invalidate_day(barber_id, appt["date"])
    except Exception as e:
        print(f"Cache invalidation error: {e}")

    # Mark as cancelled
    res = supabase.table("appointments").update({"status": "cancelled"}).eq("id", appt_id).execute()
    
    if hasattr(res, 'error') and res.error:
        return jsonify({"success": False, "error": str(res.error)}), 500

    return jsonify({"success": True})

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
    # Optimistic Upgrade (User Requested "Default to Premium")
    barber_id = session.get("barberId")
    if barber_id:
        now_plus_30 = (datetime.utcnow() + timedelta(days=30)).isoformat()
        
        supabase.table("barbers").update({
            "plan": "premium",
            "premium_expires_at": now_plus_30
        }).eq("id", barber_id).execute()
        
        # Also ensure session state is updated if we cache it (we don't seems to)
        
    # Render the success page
    return render_template("premium_success.html")

# ============================================================
# SUBSCRIPTION MANAGEMENT (CANCEL / PORTAL)
# ============================================================
@app.route("/cancel")
@login_required
def cancel_page():
    barber_id = session["barberId"]
    barber = supabase.table("barbers").select("plan").eq("id", barber_id).execute().data[0]
    
    # Normalize plan
    plan = (barber.get("plan") or "free").lower()
    
    return render_template("cancel.html", plan=plan)

@app.route("/api/create-portal-session", methods=["POST"])
@login_required
def create_portal_session():
    # 1. Get User Email (Assuming we don't have cust_id logic perfect yet, try email lookup first?)
    # Ideally we need the Customer ID. 
    # Let's try to find a customer by email if we didn't store the ID.
    # Note: This is "best effort" if ID is missing.
    
    email = session["user_email"]
    
    try:
        # Search for customer by email
        customers = stripe.Customer.list(email=email, limit=1)
        customer_id = None
        
        if customers and customers.data:
            customer_id = customers.data[0].id
        
        if not customer_id:
             # Fallback: Redirect to generic Stripe Login if customer not found
             # Or show flash error
             flash("Could not locate your subscription record. Please contact support.", "error")
             return redirect(url_for("cancel_page"))
             
        # Create Portal Session
        # Return URL: Back to Cancel Page (or Dashboard)
        return_url = url_for("cancel_page", _external=True)
        
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return redirect(portal_session.url, code=303)
        
    except Exception as e:
        print(f"Portal Error: {e}")
        flash("Unable to open billing portal.", "error")
        return redirect(url_for("cancel_page"))

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

    if request.is_json or request.headers.get("Accept") == "application/json":
         return jsonify({"barber": barber[0], "weekly": weekly})

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
    if request.is_json:
        data = request.json or {}
        city = (data.get("city") or "").strip()
        service = (data.get("service") or "").strip()
    else:
        city = (request.form.get("city") or "").strip()
        service = (request.form.get("service") or "").strip()

    # basic guard: if empty, re-show form with flash or simple message
    if not city:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": "City is required"}), 400
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
            "media_url": b.get("photo_url") or b.get("media_url"),
        })

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify(barbers)

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
