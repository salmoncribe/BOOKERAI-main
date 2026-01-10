
try:
    from app import app
    print("Syntax OK")
except Exception as e:
    print(f"Syntax Error: {e}")
except SystemExit:
    print("SystemExit (maybe from early checks)")
