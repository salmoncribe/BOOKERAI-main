import os
import unittest
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
