import os
import re
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from datetime import timedelta
import gspread
from google.oauth2.service_account import Credentials
from google.auth import default as google_auth_default
from gspread.exceptions import WorksheetNotFound, APIError

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_ID = os.environ.get("SHEET_ID")
SHEET_NAME = os.environ.get("SHEET_NAME", "Barbers")
HOURS_SHEET = os.environ.get("HOURS_SHEET", "Hours")
APPT_SHEET = os.environ.get("APPT_SHEET", "Appointments")
USERS_SHEET = os.environ.get("USERS_SHEET", "Users")
USERS_HEADERS = [
    "email", "plan", "payment_status", "custom_code",
    "code_status", "referred_by", "free_months", "expires_at"
]

BARBERS_HEADERS = [
    "barberId", "name", "email", "password_hash",
    "phone", "Address", "bio", "created_at",
    "profession", "location", "photo_url", "media_url"
]


APPTS_HEADERS = [
    "appointmentId", "barberId", "clientName", "clientPhone",
    "service", "start", "end", "notes", "createdAt",
]
HOURS_HEADERS = ["barberId", "weekday", "open", "close", "isClosed"]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# ✅ Add this mapping below WEEKDAYS
WEEKDAY_ALIASES = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun"
}


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").strip().lower())

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _a1_range(r1: int, c1: int, r2: int, c2: int) -> str:
    return f"{_col_letter(c1)}{r1}:{_col_letter(c2)}{r2}"


# -------------------------------------------------------------------
# CACHE & RETRY HELPERS
# -------------------------------------------------------------------
_sheet_cache = None
_last_open = 0
_cache: Dict[str, Dict[str, Any]] = {}

def _cached(key: str, ttl: int, fn):
    now = time.time()
    if key in _cache and now - _cache[key]["t"] < ttl:
        return _cache[key]["v"]
    val = fn()
    _cache[key] = {"v": val, "t": now}
    return val

def _safe_call(fn, *args, **kwargs):
    """Retry wrapper to gracefully handle transient API errors."""
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            if "Quota exceeded" in str(e):
                time.sleep(2)
                continue
            raise
        except Exception as e:
            # Some flaky gspread calls raise plain Exception
            if attempt < 2:
                time.sleep(1)
                continue
            raise
    return None


# -------------------------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------------------------
def _client():
    """Authorize Google Sheets client via ADC, SA JSON, or key file."""
    # 1. Application Default Credentials (Cloud Run)
    try:
        creds, _ = google_auth_default(scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception:
        pass

    # 2. Inline JSON key
    sa_json = os.environ.get("SECRET_GCP_SA")
    if sa_json:
        creds = Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
        return gspread.authorize(creds)

    # 3. Local key path
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path and os.path.exists(key_path):
        creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        return gspread.authorize(creds)

    raise RuntimeError("No valid Google credentials found. Set SECRET_GCP_SA or ADC.")


def _open():
    """Open and cache the spreadsheet for 10 minutes."""
    global _sheet_cache, _last_open
    if not SHEET_ID:
        raise RuntimeError("SHEET_ID environment variable is required")

    now = time.time()
    if _sheet_cache and now - _last_open < 600:
        return _sheet_cache

    for attempt in range(3):
        try:
            _sheet_cache = _client().open_by_key(SHEET_ID)
            _last_open = now
            return _sheet_cache
        except APIError as e:
            if "Quota exceeded" in str(e):
                time.sleep(2)
                continue
            raise
    raise RuntimeError("Failed to open Google Sheet after 3 retries")


# -------------------------------------------------------------------
# HEADER HELPERS
# -------------------------------------------------------------------
def _get_header(ws) -> List[str]:
    try:
        return ws.row_values(1)
    except Exception:
        return []

def _ensure_headers(ws, expected_headers: List[str]) -> List[str]:
    header = _get_header(ws)
    if not header:
        rng = _a1_range(1, 1, 1, len(expected_headers))
        ws.update(rng, [expected_headers])
        return expected_headers

    have_norm = {_norm(h): h for h in header if h}
    to_add = [h for h in expected_headers if _norm(h) not in have_norm]
    if to_add:
        new_header = header + to_add
        rng = _a1_range(1, 1, 1, len(new_header))
        ws.update(rng, [new_header])
        return new_header
    return header

def _header_index_map(header: List[str]) -> Dict[str, int]:
    idx_map = {}
    for i, h in enumerate(header):
        n = _norm(h)
        if n and n not in idx_map:
            idx_map[n] = i
    return idx_map

def _rows_with_expected_headers(ws, expected_headers: List[str]) -> List[Dict[str, Any]]:
    try:
        return _safe_call(ws.get_all_records, head=1, default_blank="") or []
    except Exception:
        values = _safe_call(ws.get_all_values) or []
        if not values:
            return []
        raw_header = values[0]
        data_rows = values[1:]
        norm_expected = [_norm(h) for h in expected_headers]
        idx_to_canon = {}
        for i, h in enumerate(raw_header):
            nh = _norm(h)
            if nh in norm_expected:
                canon = expected_headers[norm_expected.index(nh)]
                idx_to_canon[i] = canon
        out = []
        for r in data_rows:
            item = {k: "" for k in expected_headers}
            for i, cell in enumerate(r):
                canon = idx_to_canon.get(i)
                if canon:
                    item[canon] = cell
            out.append(item)
        return out

def _find_in_col(ws, col: int, value) -> Optional[int]:
    try:
        cells = _safe_call(ws.col_values, col)
        for idx, v in enumerate(cells or [], start=1):
            if str(v).strip() == str(value).strip():
                return idx
    except Exception:
        pass
    return None


# -------------------------------------------------------------------
# BOOTSTRAP
# -------------------------------------------------------------------
def ensure_workbooks():
    """Ensure all worksheets exist and have headers."""
    sh = _open()

    def ensure_ws(title: str, headers: List[str]):
        try:
            ws = sh.worksheet(title)
        except WorksheetNotFound:
            ws = sh.add_worksheet(title=title, rows=1000, cols=26)
            rng = _a1_range(1, 1, 1, len(headers))
            ws.update(rng, [headers])
            return ws
        _ensure_headers(ws, headers)
        return ws

    ensure_ws(SHEET_NAME, BARBERS_HEADERS)
    ensure_ws(APPT_SHEET, APPTS_HEADERS)
    ensure_ws(HOURS_SHEET, HOURS_HEADERS)
    ensure_ws(USERS_SHEET, USERS_HEADERS)


# -------------------------------------------------------------------
# BARBERS
# -------------------------------------------------------------------
def get_barber_by_email(email: str) -> Optional[Dict[str, Any]]:
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    rows = _cached("barbers", 30, lambda: _rows_with_expected_headers(ws, BARBERS_HEADERS))
    email_norm = (email or "").strip().lower()
    for r in rows:
        if (r.get("email") or "").strip().lower() == email_norm:
            return r
    return None

def get_barber_by_id(barber_id: str) -> Optional[Dict[str, Any]]:
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    rows = _cached("barbers", 30, lambda: _rows_with_expected_headers(ws, BARBERS_HEADERS))
    want = (barber_id or "").strip()
    for r in rows:
        if (r.get("barberId") or "").strip() == want:
            return r
    return None
def get_barber_media_urls(barber_id: str) -> List[str]:
    """Return a list of media URLs (images/videos) for a given barber."""
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    rows = _cached("barbers", 30, lambda: _rows_with_expected_headers(ws, BARBERS_HEADERS))
    for r in rows:
        if (r.get("barberId") or "").strip() == (barber_id or "").strip():
            media = (r.get("media_url") or "").strip()
            if not media:
                return []
            return [m.strip() for m in media.split(",") if m.strip()]
    return []

import re

def normalize_location(text: str) -> str:
    """Clean and normalize text for flexible location matching."""
    if not text:
        return ""
    # lowercase, remove punctuation
    text = text.lower()
    text = text.replace(",", " ").replace(".", " ")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # normalize texas names
    text = text.replace(" texas", " tx")
    return text


def get_barbers_by_location(search: str) -> List[Dict[str, Any]]:
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    rows = _cached("barbers", 30, lambda: _rows_with_expected_headers(ws, BARBERS_HEADERS))

    search_norm = normalize_location(search)
    print(f"\n🔍 SEARCHING FOR: '{search}' → normalized: '{search_norm}'")

    matches = []

    for r in rows:
        # ✅ Flexible: handles both 'Address' and 'address'
        address = (r.get("address") or r.get("Address") or "").strip()
        addr_norm = normalize_location(address)

        print(f"📍 ADDRESS: '{address}' → normalized: '{addr_norm}'")

        if search_norm and search_norm in addr_norm:
            print("✅ MATCH (direct substring)")
            matches.append(r)
            continue

        search_words = search_norm.split()
        if all(word in addr_norm.split() for word in search_words):
            print("✅ MATCH (word-based)")
            matches.append(r)
        else:
            print("❌ NO MATCH")

    print(f"🎯 TOTAL MATCHES FOUND: {len(matches)}")
    return matches

def append_barber_to_sheet(name, email, password_hash, phone, address, bio, profession):
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    header = _ensure_headers(ws, BARBERS_HEADERS)
    idx_map = _header_index_map(header)
    row = [""] * len(header)

    def set_field(field_name: str, value: Any):
        n = _norm(field_name)
        if n in idx_map:
            row[idx_map[n]] = value if value is not None else ""

    set_field("barberId", f"b_{os.urandom(6).hex()}")
    set_field("name", name)
    set_field("email", (email or "").strip().lower())
    set_field("password_hash", password_hash)
    set_field("phone", phone)
    set_field("address", address)
    set_field("bio", bio)
    set_field("profession", profession)
    set_field("created_at", _utc_now_iso())
    set_field("photo_url", "")
    set_field("media_url", "")



    _safe_call(ws.append_row, row)
    _cache.pop("barbers", None)


def update_barber_password_hash(barber_id: str, password_hash: str) -> bool:
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    header = _ensure_headers(ws, BARBERS_HEADERS)
    idx_map = _header_index_map(header)
    n_id = _norm("barberId")
    n_pw = _norm("password_hash")
    if n_id not in idx_map or n_pw not in idx_map:
        return False
    id_col = idx_map[n_id] + 1
    row_idx = _find_in_col(ws, id_col, barber_id)
    if not row_idx:
        return False
    pw_col = idx_map[n_pw] + 1
    _safe_call(ws.update_cell, row_idx, pw_col, password_hash)
    _cache.pop("barbers", None)
    return True

def get_user_from_users_sheet(email: str):
    ws = _open().worksheet("Users")
    rows = ws.get_all_records()
    for row in rows:
        if row.get("email") == email:
            return row
    return None

# -------------------------------------------------------------------
# APPOINTMENTS
# -------------------------------------------------------------------
def list_barber_appointments(barber_id: str) -> List[Dict[str, Any]]:
    ws = _safe_call(_open().worksheet, APPT_SHEET)
    rows = _cached("appointments", 20, lambda: _rows_with_expected_headers(ws, APPTS_HEADERS))
    return [r for r in rows if (r.get("barberId") or "").strip() == (barber_id or "").strip()]

def create_appointment(payload: Dict[str, Any]):
    ws = _safe_call(_open().worksheet, APPT_SHEET)
    header = _ensure_headers(ws, APPTS_HEADERS)
    idx_map = _header_index_map(header)
    row = [""] * len(header)

    def set_field(field_name: str, value: Any):
        n = _norm(field_name)
        if n in idx_map:
            row[idx_map[n]] = value if value is not None else ""

    for k in ["appointmentId", "barberId", "clientName", "clientPhone",
              "service", "start", "end", "notes"]:
        set_field(k, payload.get(k, ""))

    set_field("createdAt", _utc_now_iso())
    _safe_call(ws.append_row, row)
    _cache.pop("appointments", None)
def delete_appointment(appointment_id: str) -> bool:
    """Delete a specific appointment by its ID."""
    try:
        ws = _safe_call(_open().worksheet, APPT_SHEET)
        header = _ensure_headers(ws, APPTS_HEADERS)
        idx_map = _header_index_map(header)
        n_id = _norm("appointmentId")
        if n_id not in idx_map:
            return False

        id_col = idx_map[n_id] + 1
        row_idx = _find_in_col(ws, id_col, appointment_id)
        if not row_idx:
            return False

        _safe_call(ws.delete_rows, row_idx)
        _cache.pop("appointments", None)
        print(f"🗑️ Deleted appointment {appointment_id}")
        return True
    except Exception as e:
        print(f"Error deleting appointment {appointment_id}: {e}")
        return False

def delete_expired_appointments():
    """Delete appointments that ended (or started) more than 1 hour ago."""
    try:
        ws = _safe_call(_open().worksheet, APPT_SHEET)
        rows = _rows_with_expected_headers(ws, APPTS_HEADERS)
        now = datetime.now(timezone.utc)
        to_delete = []

        for i, row in enumerate(rows, start=2):  # skip header row
            end_str = row.get("end") or row.get("start") or ""
            if not end_str.strip():
                continue

            try:
                end_str_clean = end_str.replace(" ", "T")
                end_time = datetime.fromisoformat(end_str_clean)
                # If the datetime is naive, assume it's UTC
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
            except Exception:
                print(f"⚠️ Skipped unparsable time: {end_str}")
                continue

            if now - end_time > timedelta(hours=1):
                to_delete.append(i)

        # Delete from bottom to top
        for i in reversed(to_delete):
            _safe_call(ws.delete_rows, i)

        if to_delete:
            print(f"🧹 Deleted {len(to_delete)} expired appointments.")
        else:
            print("✅ No expired appointments to delete.")
    except Exception as e:
        print(f"Error in delete_expired_appointments: {e}")


# -------------------------------------------------------------------
# HOURS
# -------------------------------------------------------------------
def get_hours(barber_id: str) -> Dict[str, Dict[str, Any]]:
    ws = _safe_call(_open().worksheet, HOURS_SHEET)
    rows = _cached("hours", 30, lambda: _rows_with_expected_headers(ws, HOURS_HEADERS))
    out = {d: {"open": "09:00", "close": "17:00", "isClosed": False} for d in WEEKDAYS}
    for r in rows:
        if (r.get("barberId") or "").strip() == (barber_id or "").strip():
            wd = str(r.get("weekday", "")).lower().strip()
            if wd in WEEKDAYS:
                val = str(r.get("isClosed", "")).strip().lower()
                out[wd] = {
                    "open": str(r.get("open", "09:00")),
                    "close": str(r.get("close", "17:00")),
                    "isClosed": val in ("1", "true", "yes", "y", "t"),
                }
    return out

def set_hours_bulk(barber_id: str, hours: Dict[str, Dict[str, Any]]):
    ws = _safe_call(_open().worksheet, HOURS_SHEET)
    header = _ensure_headers(ws, HOURS_HEADERS)
    idx_map = _header_index_map(header)
    all_rows = _rows_with_expected_headers(ws, HOURS_HEADERS)
    row_lookup = {}
    row_cursor = 2

    for r in all_rows:
        row_lookup[(r.get("barberId", ""), str(r.get("weekday", "")).lower())] = row_cursor
        row_cursor += 1

    for wd in WEEKDAYS:
        cfg = hours.get(wd, {})
        open_t = str(cfg.get("open", "09:00"))
        close_t = str(cfg.get("close", "17:00"))
        is_closed = str(cfg.get("isClosed", False)).lower() in ("1", "true", "yes")
        key = (barber_id, wd)
        row_data = [""] * len(header)
        row_data[idx_map[_norm("barberId")]] = barber_id
        row_data[idx_map[_norm("weekday")]] = wd
        row_data[idx_map[_norm("open")]] = open_t
        row_data[idx_map[_norm("close")]] = close_t
        row_data[idx_map[_norm("isClosed")]] = "TRUE" if is_closed else "FALSE"

        if key in row_lookup:
            row_idx = row_lookup[key]
            rng = _a1_range(row_idx, 1, row_idx, len(header))
            _safe_call(ws.update, rng, [row_data])
        else:
            _safe_call(ws.append_row, row_data)

    _cache.pop("hours", None)
# -------------------------------------------------------------------
# USERS (for referrals + plan tracking)
# -------------------------------------------------------------------

def add_user_to_users_sheet(email: str, plan: str = "free"):
    ws = _safe_call(_open().worksheet, USERS_SHEET)
    header = _ensure_headers(ws, USERS_HEADERS)
    row = [""] * len(header)
    data = {
        "email": email.lower().strip(),
        "plan": plan,
        "payment_status": "none",
        "custom_code": "",
        "code_status": "inactive",
        "referred_by": "",
        "free_months": "0",
        "expires_at": "",
    }
    for k, v in data.items():
        if k in header:
            row[header.index(k)] = v
    _safe_call(ws.append_row, row)
    return True

def update_custom_code(email: str, code: str) -> bool:
    ws = _safe_call(_open().worksheet, USERS_SHEET)
    rows = ws.get_all_records()

    # ensure unique code
    for r in rows:
        if r.get("custom_code", "").upper() == code.upper():
            return False

    for i, r in enumerate(rows, start=2):
        if r.get("email", "").strip().lower() == email.strip().lower():
            ws.update_cell(i, USERS_HEADERS.index("custom_code") + 1, code.upper())
            ws.update_cell(i, USERS_HEADERS.index("code_status") + 1, "active")
            return True
    return False


def get_barbers(limit=None):
    """Return all barbers from the sheet (optionally limited)."""
    ws = _safe_call(_open().worksheet, SHEET_NAME)
    rows = _rows_with_expected_headers(ws, BARBERS_HEADERS)
    if limit:
        return rows[:limit]
    return rows

def validate_promo_code(code: str, email: str) -> dict:
    """
    Validate a promo/referral code.
    - Promo codes (SAVE20, etc.): give free months to the new user.
    - Referral codes (custom_code): give 1 free month only to the code owner.
    """
    ws = _safe_call(_open().worksheet, USERS_SHEET)
    rows = _rows_with_expected_headers(ws, USERS_HEADERS)

    code = code.strip().upper()
    valid_promos = {
        "SAVE20": 1,   # Promo codes → reward new user
        "BOOKERAI10": 1,
        "FREEAI": 2,
    }

    # ✅ 1. If it's a normal promo code
    if code in valid_promos:
        free_months_add = valid_promos[code]
        for i, row in enumerate(rows, start=2):
            if (row.get("email") or "").strip().lower() == email.lower():
                try:
                    current = int(row.get("free_months") or 0)
                    ws.update(f"G{i}:G{i}", [[str(current + free_months_add)]])
                    ws.update(f"F{i}:F{i}", [[code]])  # store which code was used
                    return {"status": "success", "msg": f"Promo '{code}' applied: +{free_months_add} free month(s)!"}
                except Exception as e:
                    return {"status": "error", "msg": f"Failed to apply code: {e}"}
        return {"status": "error", "msg": "User not found in Users sheet."}

    # ✅ 2. Otherwise treat it as a referral code
    for i, row in enumerate(rows, start=2):
        if (row.get("custom_code") or "").strip().upper() == code:
            try:
                # Reward the code owner ONLY
                current = int(row.get("free_months") or 0)
                new_total = current + 1
                ws.update(f"G{i}:G{i}", [[str(new_total)]])
                ws.update(f"E{i}:E{i}", [["active"]])  # mark code_status active
                return {"status": "success", "msg": f"Referral '{code}' applied — the code owner got +1 free month!"}
            except Exception as e:
                return {"status": "error", "msg": f"Failed to reward referrer: {e}"}

    return {"status": "error", "msg": "Invalid promo or referral code."}

# -------------------------------------------------------------------
# PREMIUM PLAN AUTOMATION
# -------------------------------------------------------------------
def check_and_update_premium_status(email: str):
    """If a user has free_months > 0, upgrade them to premium for 1 month.
       If expired, downgrade back to free automatically."""
    ws = _safe_call(_open().worksheet, USERS_SHEET)
    rows = _rows_with_expected_headers(ws, USERS_HEADERS)

    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is header
        if row.get("email", "").strip().lower() == email.strip().lower():
            plan = (row.get("plan") or "free").lower()
            free_months = int(row.get("free_months") or 0)
            expires_at = row.get("expires_at", "")

            # Case 1️⃣: Upgrade if user has free_months left
            if free_months > 0 and plan != "premium":
                new_expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                ws.update(f"B{i}:B{i}", [["premium"]])          # plan
                ws.update(f"H{i}:H{i}", [[new_expiry]])         # expires_at
                ws.update(f"G{i}:G{i}", [[str(free_months - 1)]])  # reduce free_months
                print(f"✅ Upgraded {email} to Premium for 1 month.")
                return True

            # Case 2️⃣: Downgrade if expired
            if plan == "premium" and expires_at:
                try:
                    exp_date = datetime.fromisoformat(expires_at)
                    if exp_date < datetime.now(timezone.utc):
                        ws.update(f"B{i}:B{i}", [["free"]])
                        ws.update(f"G{i}:G{i}", [["0"]])
                        ws.update(f"H{i}:H{i}", [[""]])

                        print(f"🔁 Downgraded {email} back to Free (expired).")
                        return True
                except Exception as e:
                    print(f"⚠️ Could not parse expiry for {email}: {e}")
            break
    return False
