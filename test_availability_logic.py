import os
import unittest
from unittest.mock import MagicMock, patch

# Mock env vars BEFORE imports to satisfy supabase_client
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "fake-key"

from availability import AvailabilityService

class TestAvailabilityLogic(unittest.TestCase):
    def setUp(self):
        self.mock_cache = MagicMock()
        self.service = AvailabilityService(self.mock_cache)
        self.mock_cache.get.return_value = None

    def test_basic_slots(self):
        # Mock DB data
        hours = [{"weekday": "mon", "start_time": "09:00", "end_time": "12:00", "is_closed": False}]
        overrides = []
        appts = [] # No appts

        with patch('db.get_weekly_hours_raw', return_value=hours), \
             patch('db.get_date_override_raw', return_value=overrides), \
             patch('db.get_appointments_raw', return_value=appts):
            
            # 2023-12-25 is a Monday
            res = self.service.get_availability("barber1", "2023-12-25", 60)
            slots = res["slots"]
            
            # 09:00 - 12:00 with 60 min slots -> 09:00, 10:00, 11:00. (12:00 is end)
            self.assertEqual(slots, ["09:00", "10:00", "11:00"], f"Expected 09, 10, 11. Got {slots}")
            self.assertFalse(res["cached"])

    def test_overlap_filtering(self):
        hours = [{"weekday": "mon", "start_time": "09:00", "end_time": "12:00", "is_closed": False}]
        overrides = []
        # Book 10:00-11:00
        appts = [{"start_time": "10:00:00", "end_time": "11:00:00", "status": "booked"}]

        with patch('db.get_weekly_hours_raw', return_value=hours), \
             patch('db.get_date_override_raw', return_value=overrides), \
             patch('db.get_appointments_raw', return_value=appts):
            
            res = self.service.get_availability("barber1", "2023-12-25", 60)
            slots = res["slots"]
            
            # 10:00 should be removed
            self.assertEqual(slots, ["09:00", "11:00"], f"Expected 09, 11. Got {slots}")

    def test_caching(self):
        # Setup cache hit
        self.mock_cache.get.return_value = ["09:00"]
        
        # We don't need to mock DB here because it hits cache first
        res = self.service.get_availability("barber1", "2023-12-25", 60)
        self.assertEqual(res["slots"], ["09:00"])
        self.assertTrue(res["cached"])

    def test_text_parsing_formats(self):
        hours = [{"weekday": "mon", "start_time": "09:00", "end_time": "12:00", "is_closed": False}]
        overrides = []
        # Test distinct formats for "10:00-11:00"
        appts = [
            {"start_time": "10:00", "end_time": "11:00", "status": "booked"},   # HH:MM
            {"start_time": "11:00:00", "end_time": "12:00:00", "status": "booked"}, # HH:MM:SS
        ]

        with patch('db.get_weekly_hours_raw', return_value=hours), \
             patch('db.get_date_override_raw', return_value=overrides), \
             patch('db.get_appointments_raw', return_value=appts):
            
            res = self.service.get_availability("barber1", "2023-12-25", 60)
            slots = res["slots"]
            
            # 09:00 is free. 
            # 10:00 is booked (format 1). 
            # 11:00 is booked (format 2).
            self.assertEqual(slots, ["09:00"], f"Expected 09:00 only. Got {slots}")

if __name__ == '__main__':
    unittest.main()
