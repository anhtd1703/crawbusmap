# -*- coding: utf-8 -*-
"""
prepare_map_data.py
Đọc các file GTFS và tạo file JSON tối ưu cho bản đồ web.
"""

import csv
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GTFS_DIR = Path(__file__).parents[1] / "output" / "gtfs"
OUT_PATH = Path(__file__).parents[1] / "output" / "map_data.json"


def main():
    print("--- Chuẩn bị dữ liệu bản đồ ---")

    # 1. Đọc routes.txt
    print("1. Đọc routes.txt...")
    routes = {}
    with open(GTFS_DIR / "routes.txt", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            routes[row["route_id"]] = {
                "id": row["route_id"],
                "short": row["route_short_name"],
                "long": row["route_long_name"],
                "color": row.get("route_color", ""),
                "type": int(row.get("route_type", 3)),
            }
    print(f"   -> {len(routes)} tuyến")

    # 2. Đọc trips.txt -> xác định route -> shape mapping (chỉ lấy 1 trip mỗi hướng)
    print("2. Đọc trips.txt...")
    route_shapes = defaultdict(dict)  # route_id -> {direction_id: shape_id}
    route_first_trip = defaultdict(dict)  # route_id -> {direction_id: trip_id}
    with open(GTFS_DIR / "trips.txt", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = row["route_id"]
            d = row["direction_id"]
            if d not in route_shapes[rid]:
                route_shapes[rid][d] = row["shape_id"]
                route_first_trip[rid][d] = row["trip_id"]
    print(f"   -> {len(route_shapes)} tuyến có shape")

    # 3. Đọc shapes.txt
    print("3. Đọc shapes.txt...")
    shapes = defaultdict(list)  # shape_id -> [(lat, lon), ...]
    with open(GTFS_DIR / "shapes.txt", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            shapes[row["shape_id"]].append(
                (float(row["shape_pt_lat"]), float(row["shape_pt_lon"]))
            )
    print(f"   -> {len(shapes)} shapes, {sum(len(v) for v in shapes.values())} điểm")

    # 4. Đọc stops.txt
    print("4. Đọc stops.txt...")
    stops = {}
    with open(GTFS_DIR / "stops.txt", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stops[row["stop_id"]] = {
                "name": row["stop_name"],
                "desc": row.get("stop_desc", ""),
                "lat": float(row["stop_lat"]),
                "lon": float(row["stop_lon"]),
            }
    print(f"   -> {len(stops)} trạm dừng")

    # 5. Đọc stop_times.txt -> lấy danh sách stop cho mỗi trip đầu tiên
    print("5. Đọc stop_times.txt (chỉ lấy trip đầu tiên mỗi hướng)...")
    needed_trips = set()
    for rid, dirs in route_first_trip.items():
        for d, tid in dirs.items():
            needed_trips.add(tid)

    trip_stops = defaultdict(list)  # trip_id -> [(stop_id, sequence), ...]
    with open(GTFS_DIR / "stop_times.txt", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row["trip_id"]
            if tid in needed_trips:
                trip_stops[tid].append(
                    (row["stop_id"], int(row["stop_sequence"]))
                )
    # Sắp xếp theo sequence
    for tid in trip_stops:
        trip_stops[tid].sort(key=lambda x: x[1])
    print(f"   -> {len(trip_stops)} trips đã đọc stop_times")

    # 6. Xây dựng JSON output
    print("6. Xây dựng JSON...")
    output_routes = []
    for rid, rdata in routes.items():
        directions = []
        for d_str in sorted(route_shapes.get(rid, {}).keys()):
            shape_id = route_shapes[rid][d_str]
            trip_id = route_first_trip[rid][d_str]
            shape_pts = shapes.get(shape_id, [])

            # Lấy danh sách stop_id từ trip
            stop_list = []
            for sid, seq in trip_stops.get(trip_id, []):
                s = stops.get(sid)
                if s:
                    stop_list.append({
                        "id": sid,
                        "name": s["name"],
                        "desc": s["desc"],
                        "lat": s["lat"],
                        "lon": s["lon"],
                        "seq": seq,
                    })

            directions.append({
                "dir": int(d_str),
                "shape": shape_pts,
                "stops": stop_list,
            })

        if directions:
            output_routes.append({
                "id": rid,
                "short": rdata["short"],
                "long": rdata["long"],
                "color": rdata["color"],
                "type": rdata["type"],
                "dirs": directions,
            })

    # Sắp xếp theo route_short_name
    output_routes.sort(key=lambda r: r["short"])

    print(f"   -> {len(output_routes)} tuyến có dữ liệu hình học")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_routes, f, ensure_ascii=False)

    file_size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\nHoàn thành! File: {OUT_PATH} ({file_size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
