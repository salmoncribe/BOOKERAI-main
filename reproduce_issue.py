
from app import app
from flask import url_for

with app.test_request_context():
    try:
        print(f"URL for barber_logout: {url_for('barber_logout')}")
    except Exception as e:
        print(f"barber_logout failed: {e}")

    try:
        print(f"URL for client_logout: {url_for('client_logout')}")
    except Exception as e:
        print(f"client_logout failed: {e}")

    try:
        print(f"URL for logout: {url_for('logout')}")
    except Exception as e:
        print(f"logout failed: {e}")
