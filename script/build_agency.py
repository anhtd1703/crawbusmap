import json
import csv
from pathlib import Path

def get_short_id(name, counter):
    if not name:
        return f"U{counter}"
    # Generate an acronym based on uppercase initials of words
    words = name.replace("-", " ").split()
    acronym = "".join([w[0].upper() for w in words if w])
    # Keep it short, max 4 chars + counter
    acronym = acronym[:4]
    if not acronym:
        return f"C{counter}"
    return f"{acronym}{counter}"

def main():
    detail_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\route\detail")
    gtfs_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn\output\gtfs")
    gtfs_dir.mkdir(parents=True, exist_ok=True)
    
    agency_map = {}
    counter = 1
    
    # Process all json files
    for file_path in detail_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
            
        company_id = data.get("companyId")
        orgs = data.get("orgs")
        
        agency_name = orgs.strip() if orgs and str(orgs).strip() else ""
        
        # Determine agency_id
        if company_id is not None and str(company_id).strip() != "":
            agency_id = str(company_id).strip()
        else:
            # Look for existing agency by name first
            existing_id = None
            if agency_name:
                for aid, adata in agency_map.items():
                    if adata['agency_name'] == agency_name:
                        existing_id = aid
                        break
            
            if existing_id:
                agency_id = existing_id
            else:
                agency_id = get_short_id(agency_name, counter)
                counter += 1
                
        if not agency_name:
            agency_name = f"Agency {agency_id}"
            
        if agency_id not in agency_map:
            agency_map[agency_id] = {
                "agency_id": agency_id,
                "agency_name": agency_name,
                "agency_url": "https://busmap.vn",
                "agency_timezone": "Asia/Ho_Chi_Minh"
            }
        else:
            # Update name if we had a generic one before
            if agency_map[agency_id]["agency_name"].startswith("Agency ") and not agency_name.startswith("Agency "):
                agency_map[agency_id]["agency_name"] = agency_name
                
    out_path = gtfs_dir / "agency.txt"
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["agency_id", "agency_name", "agency_url", "agency_timezone"])
        writer.writeheader()
        for agency in agency_map.values():
            writer.writerow(agency)
            
    print(f"Generated {len(agency_map)} agencies to {out_path}")

if __name__ == "__main__":
    main()
