import sys
import json
import time
from pathlib import Path

# Add the script folder to path so we can import fetch_hanoi_routes
sys.path.append(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\script")
import fetch_hanoi_routes

def main():
    print("Fetching decrypt key...")
    key = fetch_hanoi_routes.get_decrypt_key()
    
    hn_list_path = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\list\hn.json")
    out_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\detail")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if not hn_list_path.exists():
        print(f"Error: Could not find {hn_list_path}")
        return
        
    with open(hn_list_path, 'r', encoding='utf-8') as f:
        routes = json.load(f)
        
    print(f"Found {len(routes)} routes. Starting to fetch details...")
    
    success_count = 0
    fail_count = 0
    
    for idx, route in enumerate(routes):
        route_id = route.get("routeId")
        route_no = str(route.get("routeNo", "unknown")).replace("/", "_").replace("\\", "_").strip()
        
        # padding 0 cho routeNo nếu là số (để có 01_hn, thay vì 1_hn)
        # Tùy nhiên đề bài chỉ bảo routeNo_hn nên ta lấy gốc từ routeNo nếu cần format.
        # Ở script cũ có dùng str(route_no).zfill(2)
        # Nếu `route_no` là "1", thành "01". Nếu "01" thành "01". Nếu "103A" thì zfill vẫn là "103A"
        try:
            if route_no.isdigit():
                route_no_formatted = route_no.zfill(2)
            else:
                route_no_formatted = route_no
        except Exception:
            route_no_formatted = route_no
            
        file_name = f"{route_no_formatted}_hn.json"
        out_path = out_dir / file_name
        
        # Bỏ qua nếu đã tải rồi để tiết kiệm thời gian nếu chạy lại
        # Nhưng ở đây ta cứ lấy mới.
        
        print(f"[{idx+1}/{len(routes)}] Fetching detail for route {route_no} (ID: {route_id})...")
        
        try:
            detail = fetch_hanoi_routes.fetch_and_decrypt(
                "/web/public/route/detail", 
                params={"routeId": route_id, "regionCode": "hn"}, 
                key=key
            )
            
            if detail:
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(detail, f, ensure_ascii=False, indent=2)
                success_count += 1
            else:
                print(f"  -> Failed to get detail for {route_no}")
                fail_count += 1
        except Exception as e:
            print(f"  -> Exception fetching {route_no}: {e}")
            fail_count += 1
            
        # Nghỉ chút tránh bị block
        time.sleep(0.5)
        
    print(f"\nDone! Successfully fetched: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
