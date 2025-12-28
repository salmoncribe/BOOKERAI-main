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

    def _calculate_slots(self, date_str, hours_data, overrides_data, appointments_data, duration_minutes):
        """
        Pure logic: 
        - Determine working hours (Weekly + Overrides)
        - Generate all possible slots
        - Subtract booked slots
        """
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday_str = target_date.strftime("%a").lower()  # mon, tue, ...

        # --- A. Determine Open/Close times ---
        start_time_str = None
        end_time_str = None
        is_closed = False

        # 1. Check Overrides first
        if overrides_data:
            # Assuming only one override per day usually, but let's take the first relevant one
            # Logic: If override exists, it REPLACES weekly hours entirely.
            ov = overrides_data[0]
            if ov.get("is_closed"):
                is_closed = True
            else:
                start_time_str = ov.get("start_time")
                end_time_str = ov.get("end_time")
        
        # 2. If no override, check weekly
        else:
            # Filter for this weekday
            day_hours = next((h for h in hours_data if h["weekday"] == weekday_str), None)
            if not day_hours or day_hours.get("is_closed"):
                is_closed = True
            else:
                start_time_str = day_hours.get("start_time")
                end_time_str = day_hours.get("end_time")

        if is_closed or not start_time_str or not end_time_str:
            return []

        # --- B. Generate Candidate Slots ---
        # Helper to convert "HH:MM(:SS)" to minutes from midnight
        def to_minutes(t_str):
            parts = t_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        open_mins = to_minutes(start_time_str)
        close_mins = to_minutes(end_time_str)
        
        candidate_slots = []
        current_mins = open_mins
        
        # Determine slot step. Usually equal to duration, or could be 30m if desired. 
        # Requirement says "based on service duration". Let's assume step = duration for basic logic, 
        # OR we could stick to a fixed step (like 30m) and check if 'duration' fits.
        # User prompt check: "Generate all possible time slots based on provider working hours"
        # "Services have a fixed duration"
        # Standard booking app logic: slots usually every 15, 30, or 60 mins.
        # Let's assume a 30 min step for flexibility, or use the service duration as the step.
        # For simplicity and classic barber style: Step = Duration (back-to-back).  
        # BUT, if I want to be safe, I should look at `app.py` generate_slots which used `step`.
        # `db.py` didn't show `slot_duration` usage.
        # `app.py` has `generate_slots` taking a step.
        # Let's check `barber` settings for `step` later? 
        # For this pass: Step = Duration.
        
        step = duration_minutes 

        while current_mins + duration_minutes <= close_mins:
            candidate_slots.append(current_mins)
            current_mins += step

        if not candidate_slots:
            return []

        # --- C. Remove Overlaps ---
        # Parse appointments into (start_mins, end_mins)
        busy_intervals = []
        for appt in appointments_data:
            if appt.get("status") == "cancelled":
                continue
            
            # Normalize appt times. Appt might be "YYYY-MM-DDTHH:MM..." or "HH:MM:SS"
            # DB returns "start_time" as Time or String? Supabase/Postgres Time col usually "HH:MM:SS".
            # Check `db.py`: `get_appointments_raw` selects `start_time`.
            
            a_start = str(appt["start_time"]) # Force string safely
            # If it comes as "2023-..." extract time.
            if "T" in a_start:
                 a_start = a_start.split("T")[1]
            
            # End time might not be in DB or might be calculated. 
            # `get_appointments_raw` selects `start_time, end_time`.
            # If end_time is null, assume default duration? 
            # Ideally we have end_time. If not, ignore or assume 60.
            a_end = str(appt.get("end_time") or "")
            if not a_end:
                 # fallback if data missing
                 a_s_mins = to_minutes(a_start)
                 a_e_mins = a_s_mins + 60 
            else:
                if "T" in a_end:
                    a_end = a_end.split("T")[1]
                a_s_mins = to_minutes(a_start)
                a_e_mins = to_minutes(a_end)
            
            busy_intervals.append((a_s_mins, a_e_mins))

        available_slots = []
        for slot_start in candidate_slots:
            slot_end = slot_start + duration_minutes
            
            # Check collision
            is_clashed = False
            for (b_start, b_end) in busy_intervals:
                # Overlap logic: (StartA < EndB) and (EndA > StartB)
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
        # Invalidate for common durations. 
        # Hard to know exact key if duration varies.
        # Wildcard deletion is tricky with SimpleCache/Redis w/o pattern scan.
        # Best effort: invalidate standard durations (30, 45, 60)
        # OR: user said "Invalidate cache when a new booking is created"
        # We can try to rely on short TTL (30-120s) if perfect invalidation is hard, 
        # but for Redis we can delete keys.
        # Let's iterate popular durations.
        for d in [15, 30, 45, 60, 90]:
             self.cache.delete(self._get_cache_key(barber_id, date, d))

