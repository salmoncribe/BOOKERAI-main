import unittest
from unittest.mock import MagicMock, patch
import json
import os

# Set mocks before importing app to avoid real DB connection attempts if strict
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "fake-key"
os.environ["SECRET_KEY"] = "test-secret"

from app import app

class BookingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch("app.supabase")
    @patch("app.availability_service")
    def test_booking_success(self, mock_avail, mock_supabase):
        # Mock Barber Duration Fetch
        # barber_res.data[0].get("slot_duration")
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"slot_duration": 60}]
        
        # Mock Existing Appointments (Empty -> No Overlap)
        # We need to be careful because multiple calls to supabase happen.
        # 1. Barber fetch (for duration)
        # 2. Existing appts fetch (for overlap)
        # 3. Insert
        
        # Helper to side_effect the execute result based on table name or context could be hard.
        # Simpler approach: verify the execute() call chain returns what we need sequentially.
        
        # We can use side_effect on the final .data property access if we mock the chain better,
        # but supabase chain is .table().select().eq()...execute().data
        
        # Let's mock the execute return values logic
        def execute_side_effect(*args, **kwargs):
            # Create a mock result object
            res = MagicMock()
            # Default empty
            res.data = []
            
            # Identify which query this is by looking at earlier calls in chain? 
            # It's hard with standard mocks. 
            # However, we can know the order of execution in the function.
            # 1. barbers query (duration)
            # 2. appointments query (overlap check)
            # 3. appointments insert
            return res

        # Setup distinct return values for the sequence of execute() calls
        # 1. Duration check -> return [{"slot_duration": 60}]
        res1 = MagicMock()
        res1.data = [{"slot_duration": 60}]
        
        # 2. Overlap check -> return [] (no overlap)
        res2 = MagicMock()
        res2.data = []
        
        # 3. Insert -> return [{"id": "new-id", ...}]
        res3 = MagicMock()
        res3.data = [{"id": "new-123", "status": "booked", "start_time": "10:00", "end_time": "11:00"}]
        
        # Apply side effect to the end of the chain... 
        # Chain: table() -> select()/insert() -> eq()/etc -> execute()
        # All intermediate methods return a builder.
        # We mock the builder.
        
        builder = MagicMock()
        mock_supabase.table.return_value = builder
        builder.select.return_value = builder
        builder.insert.return_value = builder
        builder.eq.return_value = builder
        builder.neq.return_value = builder
        
        builder.execute.side_effect = [res1, res2, res3]

        payload = {
            "barber_id": "barber-1",
            "date": "2024-01-01",
            "start_time": "10:00",
            "client_name": "John Doe",
            "client_phone": "1234567890"
        }

        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), 
                             content_type="application/json")
        
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["id"], "new-123")
        
    @patch("app.supabase")
    def test_booking_overlap_exact(self, mock_supabase):
        # 1. Duration check
        res1 = MagicMock()
        res1.data = [{"slot_duration": 60}]
        
        # 2. Overlap check -> return EXISTING appointment 10:00-11:00
        res2 = MagicMock()
        res2.data = [{"start_time": "10:00", "end_time": "11:00"}]
        
        builder = MagicMock()
        mock_supabase.table.return_value = builder
        builder.select.return_value = builder
        builder.eq.return_value = builder
        builder.neq.return_value = builder
        builder.execute.side_effect = [res1, res2]

        payload = {
            "barber_id": "barber-1",
            "date": "2024-01-01",
            "start_time": "10:00", # exact start match
            "client_name": "Overlapper",
            "client_phone": "000"
        }
        
        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), 
                             content_type="application/json")
        
        self.assertEqual(resp.status_code, 409)
        self.assertIn("unavailable", resp.get_json()["error"])
        
    @patch("app.supabase")
    def test_booking_overlap_partial(self, mock_supabase):
        # 1. Duration check
        res1 = MagicMock()
        res1.data = [{"slot_duration": 60}]
        
        # 2. Overlap check -> Existing appt 10:30-11:30
        res2 = MagicMock()
        res2.data = [{"start_time": "10:30", "end_time": "11:30"}]
        
        builder = MagicMock()
        mock_supabase.table.return_value = builder
        builder.select.return_value = builder
        builder.eq.return_value = builder
        builder.neq.return_value = builder
        builder.execute.side_effect = [res1, res2]

        # Request 10:00 (ends 11:00) -> Overlaps 10:30-11:00 segment
        payload = {
            "barber_id": "barber-1",
            "date": "2024-01-01",
            "start_time": "10:00", 
            "client_name": "Partial",
            "client_phone": "000"
        }
        
        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), 
                             content_type="application/json")
        
        self.assertEqual(resp.status_code, 409)

    def test_validation_bad_date(self):
        payload = {
            "barber_id": "b1",
            "date": "01-01-2024", # Wrong format
            "start_time": "10:00",
            "client_name": "N",
            "client_phone": "P"
        }
        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid date", resp.get_json()["error"])

    def test_validation_bad_time(self):
        payload = {
            "barber_id": "b1",
            "date": "2024-01-01",
            "start_time": "25:00", # Invalid hour
            "client_name": "N",
            "client_phone": "P"
        }
        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid time", resp.get_json()["error"])


    @patch("app.supabase")
    def test_booking_success_fallback(self, mock_supabase):
        # 1. Duration check
        res1 = MagicMock()
        res1.data = [{"slot_duration": 60}]
        
        # 2. Overlap check -> Empty (Safe)
        res2 = MagicMock()
        res2.data = []
        
        # 3. Insert -> EMPTY (Simulate issue)
        res3 = MagicMock()
        res3.data = []
        
        # 4. Fallback Verify -> Success
        res4 = MagicMock()
        res4.data = [{"id": "fallback-id", "status": "booked"}]
        
        builder = MagicMock()
        mock_supabase.table.return_value = builder
        builder.select.return_value = builder
        builder.insert.return_value = builder
        builder.eq.return_value = builder
        builder.neq.return_value = builder
        builder.order.return_value = builder
        builder.limit.return_value = builder
        
        # The sequence of execute calls:
        # 1. Barber duration
        # 2. Overlap check
        # 3. Insert
        # 4. Fallback Select
        builder.execute.side_effect = [res1, res2, res3, res4]

        payload = {
            "barber_id": "barber-1",
            "date": "2024-01-01",
            "start_time": "12:00",
            "client_name": "Fallback User",
            "client_phone": "111"
        }

        resp = self.app.post("/api/appointments/create", 
                             data=json.dumps(payload), 
                             content_type="application/json")
        
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["id"], "fallback-id")

if __name__ == '__main__':
    unittest.main()
