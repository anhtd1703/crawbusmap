import json
import csv
from pathlib import Path

def main():
    detail_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\detail")
    gtfs_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\gtfs")
    
    # 1. Load agency.txt to map companyId or orgs to agency_id
    agency_txt = gtfs_dir / "agency.txt"
    id_to_agency = {}
    name_to_agency = {}
    
    if agency_txt.exists():
        with open(agency_txt, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_to_agency[row["agency_id"]] = row["agency_id"]
                name_to_agency[row["agency_name"]] = row["agency_id"]
                
    routes_map = {}
    
    # Process all json files
    for file_path in detail_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
            
        route_id_raw = data.get("routeId")
        if not route_id_raw:
            continue
            
        route_id = f"{route_id_raw}_hn"
        
        route_no_raw = data.get("routeNo", "")
        route_short_name = f"{route_no_raw}_hn"
        
        route_long_name = data.get("routeName", "")
        
        company_id = data.get("companyId")
        orgs = data.get("orgs")
        agency_name = orgs.strip() if orgs and str(orgs).strip() else ""
        
        # Determine agency_id
        agency_id = "unknown"
        if company_id is not None and str(company_id).strip() != "":
            cid_str = str(company_id).strip()
            if cid_str in id_to_agency:
                agency_id = cid_str
        
        if agency_id == "unknown" and agency_name in name_to_agency:
            agency_id = name_to_agency[agency_name]
            
        # Determine route_type
        is_metro = "metro" in str(route_no_raw).lower() or "metro" in str(route_long_name).lower()
        route_type = 1 if is_metro else 3
        
        # Determine colors
        color = data.get("color", "0088CC")
        if color and color.startswith("#"):
            color = color[1:]
            
        text_color = data.get("textColor", "FFFFFF")
        if text_color and text_color.startswith("#"):
            text_color = text_color[1:]
            
        routes_map[route_id] = {
            "route_id": route_id,
            "agency_id": agency_id,
            "route_short_name": route_short_name,
            "route_long_name": route_long_name,
            "route_type": route_type,
            "route_color": color,
            "route_text_color": text_color
        }
        
    out_path = gtfs_dir / "routes.txt"
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"])
        writer.writeheader()
        for route in routes_map.values():
            writer.writerow(route)
            
    print(f"Generated {len(routes_map)} routes to {out_path}")

if __name__ == "__main__":
    main()
