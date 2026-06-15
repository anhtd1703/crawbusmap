import sys
import json
from pathlib import Path

# Add the script folder to path so we can import fetch_hanoi_routes
sys.path.append(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\script")
import fetch_hanoi_routes

def main():
    print("Fetching decrypt key...")
    key = fetch_hanoi_routes.get_decrypt_key()
    
    print("Fetching route list for Hanoi...")
    routes = fetch_hanoi_routes.fetch_and_decrypt("/web/public/route/list", params={"regionCode": "hn"}, key=key)
    
    if routes:
        out_path = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\list\hn.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(routes, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(routes)} routes to {out_path}")
    else:
        print("Failed to fetch routes.")

if __name__ == "__main__":
    main()
