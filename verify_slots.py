
import os
import uuid
from datetime import datetime, timedelta
from db import supabase, get_available_slots, create_schedule_slot

# Create a unique test barber
suffix = str(uuid.uuid4())[:8]
barber_data = {
    "name": f"Test Barber {suffix}",
    "email": f"test_{suffix}@example.com",
    "password_hash": "dummy",
    "slot_duration": 60,
    "plan": "free",
    "role": "barber",
    "promo_code": f"TEST{suffix}"
}

print(f"Creating barber {barber_data['name']}...")
b_res = supabase.table("barbers").insert(barber_data).execute()
barber = b_res.data[0]
barber_id = barber["id"]

try:
    # 1. Setup Weekly Hours (Mon 09:00 - 12:00)
    print("Setting up weekly hours...")
    supabase.table("barber_weekly_hours").insert({
        "barber_id": barber_id,
        "weekday": "mon",
        "start_time": "09:00",
        "end_time": "12:00",
        "is_closed": False
    }).execute()

    # 2. Test Standard Date (Assume next Monday is standard)
    # Find next Monday
    today = datetime.now()
    days_ahead = 0 - today.weekday() if today.weekday() < 0 else 7 - today.weekday() # Next mon
    next_mon = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    print(f"Testing standard slots for {next_mon}...")
    slots = get_available_slots(barber_id, next_mon)
    print("Slots:", slots)
    assert "09:00" in slots
    assert "10:00" in slots
    assert "11:00" in slots
    assert "12:00" not in slots # End time is exclusive usually? Logic says <= end_dt. 
    # Logic: while current + step <= end_dt. 
    # If 9-12, slots: 9, 10, 11. 11+60=12. So 11:00 is last slot.
    assert len(slots) == 3

    # 3. Test Override
    print("Testing override...")
    override_date = (today + timedelta(days=days_ahead + 7)).strftime("%Y-%m-%d") # Mon after next
    supabase.table("schedule_overrides").insert({
        "barber_id": barber_id,
        "date": override_date,
        "start_time": "10:00",
        "end_time": "11:00",
        "is_closed": False
    }).execute()

    slots_ov = get_available_slots(barber_id, override_date)
    print(f"Override Slots for {override_date}:", slots_ov)
    assert "09:00" not in slots_ov
    assert "10:00" in slots_ov
    assert len(slots_ov) == 1

    # 4. Test Appointment
    print("Testing appointment...")
    supabase.table("appointments").insert({
        "barber_id": barber_id,
        "date": next_mon,
        "start_time": "10:00",
        "end_time": "11:00",
        "status": "booked",
        "service_name": "Test Cut"
    }).execute()

    slots_booked = get_available_slots(barber_id, next_mon)
    print(f"Slots after booking for {next_mon}:", slots_booked)
    assert "09:00" in slots_booked
    assert "10:00" not in slots_booked
    assert "11:00" in slots_booked
    
    print("\nSUCCESS: All verify steps passed!")

except Exception as e:
    print("\nFAILED:", e)
    raise e

finally:
    # Cleanup
    print("Cleaning up...")
    supabase.table("barbers").delete().eq("id", barber_id).execute()
