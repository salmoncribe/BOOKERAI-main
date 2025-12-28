import os
# Mock env before imports
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "fake-key"
os.environ["SECRET_KEY"] = "test-secret"

import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock modules that depend on Supabase if needed, or rely on env mock
# App import will trigger db import which triggers supabase client creation.
# Env vars above should satisfy the client creation check.

from app import app

class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home(self):
        rv = self.app.get('/')
        self.assertEqual(rv.status_code, 200)

    def test_login_page(self):
        rv = self.app.get('/login')
        self.assertEqual(rv.status_code, 200)

    def test_signup_page(self):
        rv = self.app.get('/signup')
        self.assertEqual(rv.status_code, 200)

    def test_demo_page(self):
        rv = self.app.get('/demo')
        self.assertEqual(rv.status_code, 200)

    # Dashboard should redirect if not logged in
    def test_dashboard_redirect(self):
        rv = self.app.get('/dashboard')
        self.assertEqual(rv.status_code, 302)

    def test_logout(self):
        rv = self.app.get('/logout')
        self.assertEqual(rv.status_code, 302)
        # Verify it redirects to login
        self.assertIn('/login', rv.headers['Location'])

if __name__ == '__main__':
    unittest.main()
