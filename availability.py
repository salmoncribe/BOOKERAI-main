import logging
import datetime
from datetime import timedelta
from flask import current_app
from flask_caching import Cache
import db

# Setup logging
logger = logging.getLogger(__name__)

class AvailabilityService:
    def __init__(self, cache: Cache):
        self.cache = cache

    def get_availability(self, barber_id, date_str, service_duration=60):
        """
        Main entry point. 
        Returns list of available start times (HH:MM).
        """
        cache_key = self._get_cache_key(barber_id, date_str, service_duration)
        cached_result = self.cache.get(cache_key)
        
        if cached_result is not None:
             return {"slots": cached_result, "cached": True}

        # 1. Fetch raw data
        hours_raw = db.get_weekly_hours_raw(barber_id)
        overrides_raw = db.get_date_override_raw(barber_id, date_str)
        appointments_raw = db.get_appointments_raw(barber_id, date_str)

        # 2. Calculate
        slots = self._calculate_slots(date_str, hours_raw, overrides_raw, appointments_raw, service_duration)

        # 3. Cache (TTL 60s default)
        self.cache.set(cache_key, slots, timeout=60)
        
        return {"slots": slots, "cached": False}

    def _calculate_slots(self, date_str, hours_raw, overrides_raw, appointments_raw, duration_minutes):
        """
        Pure logic: 
        - Determine working hours (Weekly + Overrides)
        - Generate all possible slots
        - Subtract booked slots using OVERLAP logic
        """
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday_str = target_date.strftime("%a").lower()  # mon, tue, ...

        # --- A. Determine Open/Close times ---
        start_time_str = None
        end_time_str = None
        is_closed = False

        # 1. Check Overrides first
        if overrides_raw:
            # Logic: If override exists, it REPLACES weekly hours entirely.
            ov = overrides_raw[0]
            if ov.get("is_closed"):
                is_closed = True
            else:
                start_time_str = ov.get("start_time")
                end_time_str = ov.get("end_time")
        
        # 2. If no override, check weekly
        else:
            # Filter for this weekday
            day_hours = next((h for h in hours_raw if h["weekday"] == weekday_str), None)
            if not day_hours or day_hours.get("is_closed"):
                is_closed = True
            else:
                start_time_str = day_hours.get("start_time")
                end_time_str = day_hours.get("end_time")

        if is_closed or not start_time_str or not end_time_str:
            return []

        # --- B. Generate Candidate Slots ---
        
        def to_minutes(t_val):
            """Robustly convert HH:MM or HH:MM:SS string or object to minutes."""
            if isinstance(t_val, (datetime.time, datetime.datetime)):
                return t_val.hour * 60 + t_val.minute
            
            if not t_val:
                return 0
            
            t_str = str(t_val).strip()
            # Handle "2023-01-01T09:00:00"
            if "T" in t_str:
                t_str = t_str.split("T")[1]
            
            # Allow "9:00" or "09:00:00"
            parts = t_str.split(":")
            if len(parts) >= 2:
                try:
                    h = int(parts[0])
                    m = int(parts[1])
                    return h * 60 + m
                except ValueError:
                    pass
            return 0

        open_mins = to_minutes(start_time_str)
        close_mins = to_minutes(end_time_str)
        
        # Generator loop
        candidate_slots = []
        current_mins = open_mins
        step = int(duration_minutes) # ensure int

        # Strict: Slot must finish by closing time
        while current_mins + step <= close_mins:
            candidate_slots.append(current_mins)
            current_mins += step

        if not candidate_slots:
            return []

        # --- Filter Past Slots (Timezone Safely) ---
        # We assume the user is booking in the barber's timezone or roughly "now".
        # For safety, if booking "today", filter out past times.
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        # Basic check: if date string matches today's date
        # Note: Ideally we'd use barber timezone. For now, we use a 15m buffer if date matches UTC date.
        if target_date == now_utc.date():
            # Convert now UTC to minutes
            now_mins = now_utc.hour * 60 + now_utc.minute
            buffer_mins = 15
            
            candidate_slots = [
                s for s in candidate_slots 
                if s > (now_mins + buffer_mins)
            ]

        if not candidate_slots:
            return []

        # --- C. Remove Overlaps ---
        busy_intervals = []
        for appt in appointments_raw:
            if appt.get("status") == "cancelled":
                continue
            
            # Start
            a_start_val = appt.get("start_time")
            a_s_mins = to_minutes(a_start_val)
            
            # End
            a_end_val = appt.get("end_time")
            if a_end_val:
                a_e_mins = to_minutes(a_end_val)
            else:
                # Fallback if specific appt has no end time (should be rare/legacy)
                a_e_mins = a_s_mins + step
            
            busy_intervals.append((a_s_mins, a_e_mins))

        available_slots = []
        for slot_start in candidate_slots:
            slot_end = slot_start + step
            
            # Collision Logic
            is_clashed = False
            for (b_start, b_end) in busy_intervals:
                # Overlap: (StartA < EndB) and (EndA > StartB)
                if slot_start < b_end and slot_end > b_start:
                    is_clashed = True
                    break
            
            if not is_clashed:
                # Convert back to HH:MM
                hh = slot_start // 60
                mm = slot_start % 60
                available_slots.append(f"{hh:02d}:{mm:02d}")

        return available_slots

    def _get_cache_key(self, barber_id, date, service_duration):
        return f"availability:{barber_id}:{service_duration}:{date}"

    def invalidate_day(self, barber_id, date):
        # Clear multiple possible durations
        for d in [15, 30, 45, 60, 90]:
             self.cache.delete(self._get_cache_key(barber_id, date, d))

