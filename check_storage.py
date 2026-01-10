
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: Missing Supabase credentials")
    sys.exit(1)

supabase = create_client(url, key)

print(f"Connecting to Supabase: {url}")

try:
    # List buckets
    print("Attempting to list buckets...")
    res = supabase.storage.list_buckets()
    buckets = res
    print(f"Found {len(buckets)} buckets.")
    
    found = False
    for b in buckets:
        print(f" - {b.name}")
        if b.name == "barber_media":
            found = True
            
    if found:
        print("\n✅ 'barber_media' bucket EXISTS.")
        # Try listing files
        try:
            files = supabase.storage.from_("barber_media").list()
            print(f"✅ Listed files in 'barber_media': {len(files)} items found.")
        except Exception as e:
            print(f"❌ Failed to list files in 'barber_media': {e}")
    else:
        print("\n❌ 'barber_media' bucket DOES NOT EXIST.")
        print("Creating 'barber_media' bucket...")
        try:
            # Try to create it (might need service role key if public key insufficient)
            # But let's try
             supabase.storage.create_bucket("barber_media", options={"public": True})
             print("✅ Created 'barber_media' bucket.")
        except Exception as e:
             print(f"❌ Failed to create bucket: {e}")

except Exception as e:
    print(f"❌ Error communicating with Supabase Storage: {e}")
