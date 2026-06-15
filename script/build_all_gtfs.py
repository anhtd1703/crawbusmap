import sys
import os
import json
import csv
import time
import math
import argparse
from pathlib import Path

# Thêm thư mục hiện tại vào path để import fetch_hanoi_routes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fetch_hanoi_routes

SPEED_MS = 15.0 * 1000 / 3600  # 15 km/h in m/s
FILTER_THRESHOLD = 2.0

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def distance_point_to_segment(px, py, ax, ay, bx, by):
    cos_lat = math.cos(math.radians(ay))
    x_scale = 111132.0 * cos_lat
    y_scale = 111132.0
    
    px_m = (px - ax) * x_scale
    py_m = (py - ay) * y_scale
    bx_m = (bx - ax) * x_scale
    by_m = (by - ay) * y_scale
    
    seg_len_sq = bx_m**2 + by_m**2
    if seg_len_sq == 0:
        return math.sqrt(px_m**2 + py_m**2), ax, ay, 0.0
        
    t = max(0, min(1, (px_m * bx_m + py_m * by_m) / seg_len_sq))
    proj_x_m = t * bx_m
    proj_y_m = t * by_m
    
    dist = math.sqrt((px_m - proj_x_m)**2 + (py_m - proj_y_m)**2)
    dist_from_a = math.sqrt(proj_x_m**2 + proj_y_m**2)
    proj_x = ax + proj_x_m / x_scale
    proj_y = ay + proj_y_m / y_scale
    return dist, proj_x, proj_y, dist_from_a

def seconds_to_hhmmss(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def remove_accents(input_str):
    import unicodedata
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    only_ascii = only_ascii.replace('Đ', 'D').replace('đ', 'd')
    return only_ascii

def get_short_id(name, existing_ids):
    if not name:
        base = "U"
    else:
        clean_name = remove_accents(name)
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', clean_name)
        words = clean_name.replace("-", " ").split()
        base = "".join([w[0].upper() for w in words if w])[:4]
        if not base:
            base = "C"
            
    counter = 1
    while True:
        cand = f"{base}{counter}"
        if cand not in existing_ids:
            return cand
        counter += 1

def prepare_gtfs_file(file_path, fieldnames, region_code):
    existing_rows = []
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    for row in reader:
                        is_current_region = False
                        if "route_id" in row and row["route_id"]:
                            if row["route_id"].endswith(f"_{region_code}"):
                                is_current_region = True
                        if "shape_id" in row and row["shape_id"]:
                            if f"_{region_code}_" in row["shape_id"]:
                                is_current_region = True
                        if "trip_id" in row and row["trip_id"]:
                            if f"_{region_code}_" in row["trip_id"]:
                                is_current_region = True
                                
                        if not is_current_region:
                            existing_rows.append(row)
        except Exception as e:
            print(f"[CẢNH BÁO] Không thể đọc {file_path.name}: {e}. Sẽ ghi đè file mới.")
            
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if existing_rows:
            writer.writerows(existing_rows)
            
    f = open(file_path, 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    return f, writer

def main():
    parser = argparse.ArgumentParser(description="Tự động crawl và build GTFS cho một khu vực (hn, dn, sg...).")
    parser.add_argument("--region", type=str, required=True, help="Mã khu vực (vd: hn, sg, dn)")
    args = parser.parse_args()
    
    region_code = args.region.lower()
    
    base_dir = Path(r"c:\Users\TANDAITHANH.COM.VN\Downloads\map.busmap.vn")
    gtfs_dir = base_dir / "output" / "gtfs"
    gtfs_dir.mkdir(parents=True, exist_ok=True)
    
    print("1. Lấy khóa giải mã API...")
    key = fetch_hanoi_routes.get_decrypt_key()
    
    print(f"2. Tải danh sách tuyến cho Region: {region_code}...")
    routes = fetch_hanoi_routes.fetch_and_decrypt("/web/public/route/list", params={"regionCode": region_code}, key=key)
    if not routes:
        print("Không tìm thấy tuyến nào hoặc lỗi API.")
        return
        
    print(f"-> Tìm thấy {len(routes)} tuyến.")
    
    # Lưu danh sách tuyến
    list_path = base_dir / "output" / "route" / "list" / f"{region_code}.json"
    list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(list_path, 'w', encoding='utf-8') as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu danh sách tuyến -> {list_path}")
    
    # Tạo thư mục lưu chi tiết
    detail_dir = base_dir / "output" / "route" / "detail" / region_code
    detail_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"3. Tải chi tiết các tuyến và lưu vào {detail_dir}...")
    for idx, r in enumerate(routes):
        route_id_raw = r.get("routeId")
        route_no_raw = str(r.get("routeNo")).strip()
        safe_route_no = "".join([c for c in route_no_raw if c.isalnum() or c in ("-", "_")])
        detail_path = detail_dir / f"{safe_route_no}_{region_code}.json"
        
        if detail_path.exists() and detail_path.stat().st_size > 0:
            print(f"[{idx+1}/{len(routes)}] Tuyến {route_no_raw} (ID: {route_id_raw}) đã có sẵn (cached).")
            continue
            
        print(f"[{idx+1}/{len(routes)}] Đang tải chi tiết tuyến {route_no_raw} (ID: {route_id_raw})...")
        detail = fetch_hanoi_routes.fetch_and_decrypt(
            "/web/public/route/detail", 
            params={"routeId": route_id_raw, "regionCode": region_code}, 
            key=key
        )
        if detail:
            with open(detail_path, 'w', encoding='utf-8') as f:
                json.dump(detail, f, ensure_ascii=False, indent=2)
            time.sleep(0.5)  # Tránh rate limit
        else:
            print(f"[LỖI] Không tải được chi tiết tuyến {route_no_raw} (ID: {route_id_raw})")
            
    # --- DỰNG DỮ LIỆU GTFS ---
    agency_path = gtfs_dir / "agency.txt"
    stops_path = gtfs_dir / "stops.txt"
    routes_path = gtfs_dir / "routes.txt"
    shapes_path = gtfs_dir / "shapes.txt"
    trips_path = gtfs_dir / "trips.txt"
    stoptimes_path = gtfs_dir / "stop_times.txt"
    
    agency_map = {}
    if agency_path.exists():
        try:
            with open(agency_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if row.get("agency_id"):
                        agency_map[row["agency_id"]] = row
        except:
            pass
            
    stops_map = {}
    if stops_path.exists():
        try:
            with open(stops_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if row.get("stop_id"):
                        stops_map[row["stop_id"]] = row
        except:
            pass
            
    print(f"\n4. Xây dựng các tệp GTFS từ thư mục chi tiết {detail_dir}...")
    detail_files = list(detail_dir.glob("*.json"))
    
    # Chuẩn bị file ghi (lọc bỏ dữ liệu cũ của vùng này nếu có)
    rf, route_writer = prepare_gtfs_file(routes_path, ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"], region_code)
    sf, shape_writer = prepare_gtfs_file(shapes_path, ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"], region_code)
    tf, trip_writer = prepare_gtfs_file(trips_path, ["route_id", "service_id", "trip_id", "shape_id", "direction_id"], region_code)
    stf, stoptime_writer = prepare_gtfs_file(stoptimes_path, ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "shape_dist_traveled"], region_code)
    
    for idx, detail_file in enumerate(detail_files):
        print(f"[{idx+1}/{len(detail_files)}] Đang xử lý file detail: {detail_file.name}")
        try:
            with open(detail_file, 'r', encoding='utf-8') as f:
                detail = json.load(f)
        except Exception as e:
            print(f"[LỖI] Đọc file {detail_file.name} thất bại: {e}")
            continue
            
        # -- 1. Xác định Agency --
        company_id = detail.get("companyId")
        orgs = detail.get("orgs")
        agency_name = orgs.strip() if orgs and str(orgs).strip() else ""
        
        agency_id = None
        if company_id is not None and str(company_id).strip() != "":
            agency_id = str(company_id).strip()
        else:
            for aid, adata in agency_map.items():
                if adata.get('agency_name') == agency_name and agency_name != "":
                    agency_id = aid
                    break
            if not agency_id:
                agency_id = get_short_id(agency_name, set(agency_map.keys()))
                
        if not agency_name: agency_name = f"Agency {agency_id}"
        
        if agency_id not in agency_map:
            agency_map[agency_id] = {
                "agency_id": agency_id,
                "agency_name": agency_name,
                "agency_url": "https://busmap.vn",
                "agency_timezone": "Asia/Ho_Chi_Minh"
            }
            
        # -- 2. Ghi Route --
        route_id_raw = detail.get("routeId")
        route_id = f"{route_id_raw}_{region_code}"
        route_no_raw = str(detail.get("routeNo", "")).strip()
        route_short_name = route_no_raw
        route_long_name = detail.get("routeName", "")
        
        is_metro = "metro" in str(route_no_raw).lower() or "metro" in str(route_long_name).lower()
        route_type = 1 if is_metro else 3
        
        color = str(detail.get("color", "0088CC")).strip('#')
        text_color = str(detail.get("textColor", "FFFFFF")).strip('#')
        
        route_writer.writerow({
            "route_id": route_id,
            "agency_id": agency_id,
            "route_short_name": route_short_name,
            "route_long_name": route_long_name,
            "route_type": route_type,
            "route_color": color,
            "route_text_color": text_color
        })
        
        # -- 3. Gom trạm (Stops) và chia hướng (Directions) --
        directions = {0: [], 1: []}
        for st in detail.get("stations", []):
            d = st.get("stationDirection", 0)
            if d in directions: directions[d].append(st)

        def parse_tt(tt_str):
            if not tt_str: return []
            if isinstance(tt_str, list): return [int(x) for x in tt_str]
            return sorted([int(x) for x in str(tt_str).split(',') if x.strip().isdigit()])
            
        tt_out = parse_tt(detail.get("timeTableOut"))
        tt_in = parse_tt(detail.get("timeTableIn"))
        
        # -- 4. Build Shapes & StopTimes --
        for d, stations in directions.items():
            if not stations: continue
            
            timetables = tt_out if d == 0 else tt_in
            if not timetables: continue # SKIP if no timetables for this direction to avoid unused_shape & stop_without_stop_time
            
            stations.sort(key=lambda x: x.get("stationOrder", 0))
            shape_id = f"shape_{route_id}_{d}"
            
            # Now add stops for this active direction to stops_map
            for st in stations:
                stop_id_raw = st.get("stationId")
                if stop_id_raw:
                    stop_id = str(stop_id_raw)
                    if stop_id not in stops_map:
                        n_raw = st.get("stationName")
                        d_raw = st.get("stationAddress")
                        stop_name = n_raw.strip() if n_raw else ""
                        stop_desc = d_raw.strip() if d_raw else ""
                        if stop_desc == stop_name:
                            stop_desc = ""
                        stops_map[stop_id] = {
                            "stop_id": stop_id,
                            "stop_name": stop_name,
                            "stop_desc": stop_desc,
                            "stop_lat": float(st.get("lat", 0.0)),
                            "stop_lon": float(st.get("lng", 0.0))
                        }
            
            raw_points = []
            for st in stations:
                pts_str = st.get("pathPoints", "")
                if pts_str and isinstance(pts_str, str):
                    for p in pts_str.strip().split(' '):
                        c = p.split(',')
                        if len(c) >= 2:
                            try: raw_points.append((float(c[1]), float(c[0])))
                            except: pass
                            
            shape_points = []
            accum_dist = 0.0
            
            for lat, lon in raw_points:
                if not shape_points:
                    shape_points.append({"lat": lat, "lon": lon, "dist": 0.0})
                else:
                    dist = haversine(shape_points[-1]["lat"], shape_points[-1]["lon"], lat, lon)
                    if dist >= FILTER_THRESHOLD:
                        accum_dist += dist
                        shape_points.append({"lat": lat, "lon": lon, "dist": accum_dist})
                        
            # Cứu cảnh nếu không có pathPoints
            if not shape_points:
                for st in stations:
                    shape_points.append({"lat": float(st.get("lat",0)), "lon": float(st.get("lng",0)), "dist": 0.0})
                    
            stop_offsets = []
            last_dist = -1.0
            start_idx = 0
            
            for st_idx, st in enumerate(stations):
                stop_id_raw = st.get('stationId')
                if not stop_id_raw: continue
                stop_id = str(stop_id_raw)
                slat, slon = float(st.get("lat", 0)), float(st.get("lng", 0))
                
                best_dist, best_accum, best_seg_idx = float('inf'), 0.0, start_idx
                best_proj_x, best_proj_y = slon, slat
                for i in range(start_idx, len(shape_points) - 1):
                    pA, pB = shape_points[i], shape_points[i+1]
                    dist, px, py, dist_from_a = distance_point_to_segment(slon, slat, pA["lon"], pA["lat"], pB["lon"], pB["lat"])
                    if dist < best_dist:
                        best_dist = dist
                        best_accum = pA["dist"] + dist_from_a
                        best_seg_idx = i
                        best_proj_x, best_proj_y = px, py
                
                if len(shape_points) == 1: best_accum = 0.0
                if best_accum <= last_dist: best_accum = last_dist + 0.1
                
                # Snap the stop coordinates to the shape to prevent stop_too_far_from_shape warning if within 100 meters
                if best_dist < 100.0 and stop_id in stops_map:
                    stops_map[stop_id]["stop_lat"] = round(best_proj_y, 6)
                    stops_map[stop_id]["stop_lon"] = round(best_proj_x, 6)
                
                stop_offsets.append({"stop_id": stop_id, "sequence": st_idx + 1, "dist": best_accum})
                last_dist = best_accum
                start_idx = best_seg_idx
                
            if stop_offsets and shape_points:
                if shape_points[-1]["dist"] < stop_offsets[-1]["dist"]:
                    shape_points[-1]["dist"] = stop_offsets[-1]["dist"]
                    
            for idx_sp, pt in enumerate(shape_points):
                shape_writer.writerow({
                    "shape_id": shape_id,
                    "shape_pt_lat": round(pt["lat"], 6),
                    "shape_pt_lon": round(pt["lon"], 6),
                    "shape_pt_sequence": idx_sp + 1,
                    "shape_dist_traveled": round(pt["dist"], 2)
                })
                
            timetables = tt_out if d == 0 else tt_in
            for t_idx, start_seconds in enumerate(timetables):
                trip_id = f"trip_{route_id}_{d}_{t_idx}"
                trip_writer.writerow({
                    "route_id": route_id,
                    "service_id": "service_1",
                    "trip_id": trip_id,
                    "shape_id": shape_id,
                    "direction_id": d
                })
                for so in stop_offsets:
                    offset_sec = int(so["dist"] / SPEED_MS)
                    arr_dep_time = seconds_to_hhmmss(start_seconds + offset_sec)
                    stoptime_writer.writerow({
                        "trip_id": trip_id,
                        "arrival_time": arr_dep_time,
                        "departure_time": arr_dep_time,
                        "stop_id": so["stop_id"],
                        "stop_sequence": so["sequence"],
                        "shape_dist_traveled": round(so["dist"], 2)
                    })

    rf.close(); sf.close(); tf.close(); stf.close()
    
    # -- Rewrite Agencies & Stops to ensure deduplication --
    with open(agency_path, 'w', newline='', encoding='utf-8') as f:
        aw = csv.DictWriter(f, fieldnames=["agency_id", "agency_name", "agency_url", "agency_timezone"])
        aw.writeheader()
        for a in agency_map.values(): aw.writerow(a)
        
    with open(stops_path, 'w', newline='', encoding='utf-8') as f:
        sw = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "stop_desc", "stop_lat", "stop_lon"])
        sw.writeheader()
        for s in stops_map.values(): sw.writerow(s)

    # -- Write calendar.txt and feed_info.txt --
    calendar_path = gtfs_dir / "calendar.txt"
    print("Ghi calendar.txt...")
    with open(calendar_path, 'w', newline='', encoding='utf-8') as f:
        cw = csv.DictWriter(f, fieldnames=["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"])
        cw.writeheader()
        cw.writerow({
            "service_id": "service_1",
            "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 1, "sunday": 1,
            "start_date": "20260101",
            "end_date": "20271231"
        })

    feed_info_path = gtfs_dir / "feed_info.txt"
    print("Ghi feed_info.txt...")
    with open(feed_info_path, 'w', newline='', encoding='utf-8') as f:
        fw = csv.DictWriter(f, fieldnames=["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_start_date", "feed_end_date", "feed_version", "feed_contact_email", "feed_contact_url"])
        fw.writeheader()
        fw.writerow({
            "feed_publisher_name": "BusMap",
            "feed_publisher_url": "https://busmap.vn",
            "feed_lang": "vi",
            "feed_start_date": "20260101",
            "feed_end_date": "20271231",
            "feed_version": "1.0",
            "feed_contact_email": "support@busmap.vn",
            "feed_contact_url": "https://busmap.vn"
        })

    print(f"\nHOÀN THÀNH TÍCH HỢP CHO REGION: {region_code}")

if __name__ == "__main__":
    main()
