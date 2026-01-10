
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
# Use Service Role Key for admin tasks (creating buckets)
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_SERVICE_ROLE_KEY or URL")
    # Fallback to verify if maybe we can just read with normal key? No, we need to create.
    sys.exit(1)

supabase = create_client(url, key)

print(f"Connecting to Supabase (Admin): {url}")

try:
    print("Checking 'barber_media' bucket...")
    res = supabase.storage.list_buckets()
    
    found = False
    for b in res:
        if b.name == "barber_media":
            found = True
            
    if found:
        print("✅ 'barber_media' bucket ALREADY EXISTS.")
        # Make sure it is public
        try:
             supabase.storage.update_bucket("barber_media", options={"public": True})
             print("✅ Verified/Updated bucket to be PUBLIC.")
        except Exception as e:
             print(f"⚠️ warning updating bucket: {e}")
             
    else:
        print("Creating 'barber_media' bucket...")
        supabase.storage.create_bucket("barber_media", options={"public": True})
        print("✅ Created 'barber_media' bucket successfully.")

except Exception as e:
    print(f"❌ Error: {e}")
