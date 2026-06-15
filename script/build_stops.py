import json
import csv
from pathlib import Path

def main():
    detail_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\detail")
    gtfs_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\gtfs")
    gtfs_dir.mkdir(parents=True, exist_ok=True)
    
    stops_map = {}
    
    # Process all json files
    for file_path in detail_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            continue
            
        stations = data.get("stations", [])
        
        for st in stations:
            stop_id = st.get("stationId")
            
            if not stop_id:
                continue
                
            stop_id = str(stop_id)
            
            # Avoid duplicate stops by storing in a map keyed by stop_id
            if stop_id not in stops_map:
                name_raw = st.get("stationName")
                stop_name = name_raw.strip() if name_raw else ""
                
                desc_raw = st.get("stationAddress")
                stop_desc = desc_raw.strip() if desc_raw else ""
                stop_lat = st.get("lat", 0.0)
                stop_lon = st.get("lng", 0.0)
                
                # Check for invalid coordinates
                if stop_lat == 0.0 and stop_lon == 0.0:
                    continue
                    
                stops_map[stop_id] = {
                    "stop_id": stop_id,
                    "stop_name": stop_name,
                    "stop_desc": stop_desc,
                    "stop_lat": stop_lat,
                    "stop_lon": stop_lon
                }
                
    out_path = gtfs_dir / "stops.txt"
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "stop_desc", "stop_lat", "stop_lon"])
        writer.writeheader()
        for stop in stops_map.values():
            writer.writerow(stop)
            
    print(f"Generated {len(stops_map)} unique stops to {out_path}")

if __name__ == "__main__":
    main()
