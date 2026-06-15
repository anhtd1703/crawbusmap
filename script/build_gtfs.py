# -*- coding: utf-8 -*-
"""
build_gtfs.py
Script đọc dữ liệu thô (đã crawl từ BusMap) để build bộ file GTFS.
"""

import os
import json
import csv
import math
import sys
from pathlib import Path

# Đảm bảo in UTF-8 trên Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình
SPEED_KMH = 15.0 # Vận tốc trung bình 15 km/h
SPEED_MS = SPEED_KMH * 1000 / 3600 # m/s

BASE_DIR = Path(__file__).parents[1]
RAW_DIR = BASE_DIR / "output" / "raw"
GTFS_DIR = BASE_DIR / "output" / "gtfs"

def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách Haversine giữa 2 điểm (m)"""
    R = 6371000 # Bán kính Trái Đất (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def seconds_to_hhmmss(seconds: int) -> str:
    """Đổi số giây thành định dạng HH:MM:SS, hỗ trợ giờ > 24 cho chuyến đêm."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def slugify(text: str) -> str:
    """Chuẩn hóa chuỗi tiếng Việt không dấu, viết thường, ngăn cách bởi dấu gạch dưới để làm agency_id."""
    import unicodedata
    import re
    if not text:
        return "unknown"
    # Chuyển về dạng chữ thường và loại bỏ khoảng trắng thừa
    text = text.lower().strip()
    # Loại bỏ dấu tiếng Việt
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # Thay thế các ký tự không phải chữ cái/số bằng dấu gạch dưới
    text = re.sub(r'[^a-z0-9]+', '_', text)
    # Loại bỏ dấu gạch dưới thừa ở đầu/cuối
    text = text.strip('_')
    return text

def main():
    print("--- BẮT ĐẦU XÂY DỰNG GTFS ---")
    
    # 0. Xóa hết dữ liệu GTFS cũ
    if GTFS_DIR.exists():
        print(f"Đang xóa dữ liệu GTFS cũ trong thư mục: {GTFS_DIR}")
        for file in GTFS_DIR.glob("*"):
            if file.is_file():
                try:
                    file.unlink()
                except Exception as e:
                    print(f"Không thể xóa tệp {file.name}: {e}")
    else:
        GTFS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Khởi tạo các mảng dữ liệu
    routes = []
    stops = {} # stop_id: {lat, lng, name}
    shapes = []
    trips = []
    stop_times = []
    agency_map = {} # agency_id -> agency_data (để ghi ra agency.txt)
    
    detail_dir = RAW_DIR / "route" / "detail"
    timeline_dir = RAW_DIR / "route" / "timeline"
    
    if not detail_dir.exists():
        print("Lỗi: Không tìm thấy thư mục raw/route/detail")
        return
        
    for detail_file in detail_dir.glob("*.json"):
        try:
            with open(detail_file, 'r', encoding='utf-8') as f:
                detail = json.load(f)
        except Exception as e:
            print(f"Lỗi khi đọc file detail {detail_file.name}: {e}")
            continue
            
        region_id = detail.get("regionId")
        if region_id != 2:
            # Bỏ qua các tuyến không thuộc vùng Hà Nội
            continue
            
        route_id = detail.get("routeId")
        route_no = str(detail.get("routeNo")).strip()
        route_name = detail.get("routeName", f"Route {route_no}").strip()
        
        # 1. Xác định agency_id và agency_name
        company_id = detail.get("companyId")
        orgs = detail.get("orgs")
        
        if company_id is not None:
            agency_id = str(company_id)
            if orgs and orgs.strip():
                agency_name = orgs.strip()
            else:
                agency_name = agency_map.get(agency_id, {}).get("agency_name", f"Agency {agency_id}")
        else:
            if orgs and orgs.strip():
                agency_id = f"company_{slugify(orgs)}"
                agency_name = orgs.strip()
            else:
                agency_id = "unknown_agency"
                agency_name = "Unknown Agency"
                
        # Thêm mới hoặc cập nhật thông tin trong agency_map
        if agency_id not in agency_map:
            agency_map[agency_id] = {
                "agency_id": agency_id,
                "agency_name": agency_name,
                "agency_url": "https://busmap.vn",
                "agency_timezone": "Asia/Ho_Chi_Minh"
            }
        else:
            prev_name = agency_map[agency_id]["agency_name"]
            if (not prev_name or prev_name.startswith("Agency ")) and agency_name and not agency_name.startswith("Agency "):
                agency_map[agency_id]["agency_name"] = agency_name
                
        # 2. Xác định route_type (3 nếu là xe bus, 1 nếu là metro)
        is_metro = "metro" in route_no.lower() or "metro" in route_name.lower()
        route_type = 1 if is_metro else 3
        
        # Định dạng mã màu (bỏ dấu # nếu có)
        color = detail.get("color", "0088CC")
        if color and color.startswith("#"):
            color = color[1:]
        text_color = detail.get("textColor", "FFFFFF")
        if text_color and text_color.startswith("#"):
            text_color = text_color[1:]
            
        # Thêm vào routes.txt
        routes.append({
            "route_id": route_id,
            "agency_id": agency_id,
            "route_short_name": route_no,
            "route_long_name": route_name,
            "route_type": route_type,
            "route_color": color,
            "route_text_color": text_color
        })
        
        # Phân chia trạm dừng theo chiều đi/về (Direction 0 và 1)
        directions = {0: [], 1: []}
        for st in detail.get("stations", []):
            dir_id = st.get("stationDirection", 0)
            if dir_id in directions:
                directions[dir_id].append(st)
                
        # Sắp xếp lại theo stationOrder
        for d in directions:
            directions[d].sort(key=lambda x: x.get("stationOrder", 0))
            
        # 3. Lấy timeline (thời gian khởi hành)
        timeline_path = timeline_dir / detail_file.name
        in_source = None
        out_source = None
        
        if timeline_path.exists():
            try:
                with open(timeline_path, 'r', encoding='utf-8') as f:
                    tl_data = json.load(f)
                    in_source = tl_data.get("timeTableIn")
                    out_source = tl_data.get("timeTableOut")
            except Exception as e:
                print(f"[CẢNH BÁO] Không đọc được file timeline {timeline_path.name}: {e}")
                
        # Fallback về detail nếu file timeline trống hoặc lỗi
        if not in_source:
            in_source = detail.get("timeTableIn")
        if not out_source:
            out_source = detail.get("timeTableOut")
            
        def parse_timetable_str(t_source):
            if not t_source or t_source == "None":
                return []
            if isinstance(t_source, list):
                return [int(x) for x in t_source]
            if isinstance(t_source, str):
                return [int(x) for x in t_source.split(',') if x.strip().isdigit()]
            return []
            
        timetable_in = parse_timetable_str(in_source)
        timetable_out = parse_timetable_str(out_source)

        print(f"Xử lý tuyến {route_no} - {route_name}: Direction 0 ({len(directions[0])} trạm), Direction 1 ({len(directions[1])} trạm)")
        
        for d, dir_stations in directions.items():
            if not dir_stations:
                continue
            
            shape_id = f"shape_{route_id}_{d}"
            service_id = "service_1" # Mặc định dịch vụ chạy hàng ngày
            
            shape_pt_seq = 1
            accumulated_dist = 0.0
            stop_offsets = [] 
            
            for i, st in enumerate(dir_stations):
                stop_id = st.get("stationId")
                lat = float(st.get("lat", 0))
                lng = float(st.get("lng", 0))
                
                # Lưu vào stops.txt dict
                if stop_id not in stops:
                   stops[stop_id] = {
                       "stop_id": stop_id,
                       "stop_name": st.get("stationName"),
                       "stop_lat": lat,
                       "stop_lon": lng
                   }
                
                # Tính pathPoints cho shapes.txt
                path_points_str = st.get("pathPoints", "")
                
                if path_points_str and isinstance(path_points_str, str) and path_points_str.strip() != "":
                    pts = path_points_str.strip().split(' ')
                    for pt_str in pts:
                        coords = pt_str.split(',')
                        if len(coords) >= 2:
                            pt_lng = float(coords[0])
                            pt_lat = float(coords[1])
                            
                            # Tính khoảng cách từ điểm shape trước tới điểm shape này
                            if len(shapes) > 0 and shapes[-1]["shape_id"] == shape_id:
                                prev_lat = shapes[-1]["shape_pt_lat"]
                                prev_lng = shapes[-1]["shape_pt_lon"]
                                dist = haversine(prev_lat, prev_lng, pt_lat, pt_lng)
                                if dist > 0:
                                    accumulated_dist += dist
                                    shapes.append({
                                        "shape_id": shape_id,
                                        "shape_pt_lat": pt_lat,
                                        "shape_pt_lon": pt_lng,
                                        "shape_pt_sequence": shape_pt_seq,
                                        "shape_dist_traveled": round(accumulated_dist, 2)
                                    })
                                    shape_pt_seq += 1
                            else:
                                shapes.append({
                                    "shape_id": shape_id,
                                    "shape_pt_lat": pt_lat,
                                    "shape_pt_lon": pt_lng,
                                    "shape_pt_sequence": shape_pt_seq,
                                    "shape_dist_traveled": round(accumulated_dist, 2)
                                })
                                shape_pt_seq += 1
                                
                # Đảm bảo khoảng cách trạm luôn tăng (tránh lỗi Decreasing or equal shape_dist_traveled)
                current_dist = round(accumulated_dist, 2)
                fallback_used = False
                if len(stop_offsets) > 0:
                    prev_dist = stop_offsets[-1]["dist"]
                    if current_dist <= prev_dist:
                        prev_st = dir_stations[i-1]
                        prev_lat = float(prev_st.get("lat", 0))
                        prev_lng = float(prev_st.get("lng", 0))
                        direct_dist = haversine(prev_lat, prev_lng, lat, lng)
                        
                        if direct_dist < 0.01:
                            direct_dist = 0.01
                            
                        accumulated_dist += direct_dist
                        current_dist = round(accumulated_dist, 2)
                        fallback_used = True

                # Cập nhật điểm cuối của shape cho khớp với trạm nếu có gap
                if len(shapes) > 0 and shapes[-1]["shape_id"] == shape_id:
                    last_shape_lat = shapes[-1]["shape_pt_lat"]
                    last_shape_lon = shapes[-1]["shape_pt_lon"]
                    dist_to_stop = haversine(last_shape_lat, last_shape_lon, lat, lng)
                    
                    if fallback_used:
                        # Fallback đã cộng khoảng cách vào accumulated_dist, ta chỉ việc thêm điểm
                        shapes.append({
                            "shape_id": shape_id,
                            "shape_pt_lat": lat,
                            "shape_pt_lon": lng,
                            "shape_pt_sequence": shape_pt_seq,
                            "shape_dist_traveled": current_dist
                        })
                        shape_pt_seq += 1
                    elif dist_to_stop > 10.0:
                        # Nếu shape point cuối cách trạm > 10m, nối shape tới trạm để tránh lỗi geoDistanceToShape
                        accumulated_dist += dist_to_stop
                        current_dist = round(accumulated_dist, 2)
                        shapes.append({
                            "shape_id": shape_id,
                            "shape_pt_lat": lat,
                            "shape_pt_lon": lng,
                            "shape_pt_sequence": shape_pt_seq,
                            "shape_dist_traveled": current_dist
                        })
                        shape_pt_seq += 1
                elif len(shapes) == 0:
                    # Trạm đầu tiên hoặc tuyến chưa có shape
                    shapes.append({
                        "shape_id": shape_id,
                        "shape_pt_lat": lat,
                        "shape_pt_lon": lng,
                        "shape_pt_sequence": shape_pt_seq,
                        "shape_dist_traveled": current_dist
                    })
                    shape_pt_seq += 1

                # Lưu offset thời gian di chuyển (giây) cho trạm hiện tại
                offset_seconds = int(accumulated_dist / SPEED_MS)
                stop_offsets.append({
                    "stop_id": stop_id,
                    "sequence": i + 1,
                    "offset": offset_seconds,
                    "dist": current_dist
                })

            # Sinh trips và stop_times từ timetable
            timetables = timetable_out if d == 0 else timetable_in
            
            for t_idx, start_seconds in enumerate(timetables):
                trip_id = f"trip_{route_id}_{d}_{t_idx}"
                trips.append({
                    "route_id": route_id,
                    "service_id": service_id,
                    "trip_id": trip_id,
                    "shape_id": shape_id,
                    "direction_id": d
                })
                
                for so in stop_offsets:
                    arr_dep_time = seconds_to_hhmmss(start_seconds + so["offset"])
                    stop_times.append({
                        "trip_id": trip_id,
                        "arrival_time": arr_dep_time,
                        "departure_time": arr_dep_time,
                        "stop_id": so["stop_id"],
                        "stop_sequence": so["sequence"],
                        "shape_dist_traveled": so["dist"]
                    })

    # --- GHI DỮ LIỆU RA CÁC TỆP GTFS ---
    print("\n[Ghi các file GTFS...]")
    
    # 1. agency.txt
    with open(GTFS_DIR / "agency.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["agency_id", "agency_name", "agency_url", "agency_timezone"])
        writer.writeheader()
        for agency in agency_map.values():
            writer.writerow(agency)

    # 2. routes.txt
    with open(GTFS_DIR / "routes.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"])
        writer.writeheader()
        writer.writerows(routes)

    # 3. stops.txt
    with open(GTFS_DIR / "stops.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "stop_lat", "stop_lon"])
        writer.writeheader()
        writer.writerows(stops.values())

    # 4. shapes.txt
    with open(GTFS_DIR / "shapes.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"])
        writer.writeheader()
        writer.writerows(shapes)

    # 5. trips.txt
    with open(GTFS_DIR / "trips.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "service_id", "trip_id", "shape_id", "direction_id"])
        writer.writeheader()
        writer.writerows(trips)

    # 6. stop_times.txt
    with open(GTFS_DIR / "stop_times.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "shape_dist_traveled"])
        writer.writeheader()
        writer.writerows(stop_times)

    # 7. calendar.txt
    with open(GTFS_DIR / "calendar.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"])
        writer.writeheader()
        writer.writerow({
            "service_id": "service_1",
            "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 1, "sunday": 1,
            "start_date": "20260101",
            "end_date": "20271231"
        })

    # 8. feed_info.txt
    with open(GTFS_DIR / "feed_info.txt", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_start_date", "feed_end_date", "feed_version"])
        writer.writeheader()
        writer.writerow({
            "feed_publisher_name": "BusMap",
            "feed_publisher_url": "https://busmap.vn",
            "feed_lang": "vi",
            "feed_start_date": "20260101",
            "feed_end_date": "20271231",
            "feed_version": "1.0"
        })

    print("Hoàn thành sinh GTFS tại:", GTFS_DIR)

if __name__ == "__main__":
    main()
