import os
import csv
import json
import argparse
import requests
import polyline
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, LineString

def get_osrm_map_match(points):
    """
    Sử dụng OSRM public API để khớp điểm lên mặt đường (Map Matching).
    points: list of (lon, lat)
    """
    # OSRM chỉ nhận tối đa 100 điểm một lần, nên phải chia nhỏ (chunk)
    chunk_size = 90
    matched_points = []
    
    for i in range(0, len(points), chunk_size):
        chunk = points[i:i + chunk_size + 1] # +1 để gối đầu lên chunk tiếp theo
        coords_str = ";".join([f"{lon},{lat}" for lon, lat in chunk])
        
        # Gọi OSRM Map Matching API
        url = f"http://router.project-osrm.org/match/v1/driving/{coords_str}?geometries=polyline&overview=full"
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "matchings" in data and len(data["matchings"]) > 0:
                    for match in data["matchings"]:
                        geometry = match.get("geometry")
                        if geometry:
                            # decode polyline trả về (lat, lon)
                            decoded = polyline.decode(geometry)
                            # lưu lại dưới dạng (lon, lat)
                            matched_points.extend([(lon, lat) for lat, lon in decoded])
                else:
                    # Nếu không match được, lấy điểm gốc
                    matched_points.extend(chunk)
            else:
                matched_points.extend(chunk)
        except Exception as e:
            print(f"OSRM Error: {e}")
            matched_points.extend(chunk)
            
    # Lọc các điểm trùng lặp
    final_points = []
    for p in matched_points:
        if not final_points or final_points[-1] != p:
            final_points.append(p)
            
    return final_points

def process_shapes(gtfs_dir):
    shapes_path = Path(gtfs_dir) / "shapes.txt"
    if not shapes_path.exists():
        print(f"Không tìm thấy {shapes_path}")
        return
        
    print(f"Đang đọc {shapes_path}...")
    shapes_data = {}
    with open(shapes_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            shape_id = row['shape_id']
            if shape_id not in shapes_data:
                shapes_data[shape_id] = []
            shapes_data[shape_id].append({
                'lat': float(row['shape_pt_lat']),
                'lon': float(row['shape_pt_lon']),
                'seq': int(row['shape_pt_sequence']),
                'dist': float(row.get('shape_dist_traveled', 0.0))
            })
            
    # Sort points by sequence
    for shape_id in shapes_data:
        shapes_data[shape_id].sort(key=lambda x: x['seq'])
        
    print(f"Tìm thấy {len(shapes_data)} tuyến đường (shapes). Đang thực hiện Map Matching (snap to road)...")
    
    matched_shapes = {}
    count = 0
    for shape_id, points in shapes_data.items():
        count += 1
        print(f"Đang xử lý shape {shape_id} ({count}/{len(shapes_data)})...")
        # Extract (lon, lat)
        coords = [(p['lon'], p['lat']) for p in points]
        
        # Map Matching
        matched_coords = get_osrm_map_match(coords)
        
        # Cập nhật lại points
        new_points = []
        for seq, (lon, lat) in enumerate(matched_coords):
            new_points.append({
                'shape_id': shape_id,
                'shape_pt_lat': lat,
                'shape_pt_lon': lon,
                'shape_pt_sequence': seq + 1,
                'shape_dist_traveled': 0.0 # Bỏ qua dist trong script đơn giản này
            })
        matched_shapes[shape_id] = new_points
        
    # Ghi lại ra shapes_matched.txt
    matched_path = Path(gtfs_dir) / "shapes_matched.txt"
    print(f"Đang ghi kết quả ra {matched_path}...")
    with open(matched_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence', 'shape_dist_traveled'])
        writer.writeheader()
        for shape_id, points in matched_shapes.items():
            for pt in points:
                writer.writerow(pt)
                
    return matched_path

def export_to_shapefile(gtfs_dir, matched_shapes_path=None):
    gtfs_dir = Path(gtfs_dir)
    out_dir = gtfs_dir.parent / "shapefiles"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Xử lý Stops
    stops_path = gtfs_dir / "stops.txt"
    if stops_path.exists():
        print(f"Đang xuất Shapefile cho Trạm (Stops)...")
        stops_records = []
        with open(stops_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat = float(row['stop_lat'])
                lon = float(row['stop_lon'])
                stops_records.append({
                    'stop_id': row['stop_id'],
                    'stop_name': row.get('stop_name', ''),
                    'geometry': Point(lon, lat)
                })
        if stops_records:
            gdf_stops = gpd.GeoDataFrame(stops_records, crs="EPSG:4326")
            gdf_stops.to_file(out_dir / "stops.shp", encoding='utf-8')
            print(f" Đã lưu: {out_dir / 'stops.shp'}")

    # 2. Xử lý Shapes (đường)
    shapes_path = Path(matched_shapes_path) if matched_shapes_path else (gtfs_dir / "shapes.txt")
    if shapes_path.exists():
        print(f"Đang xuất Shapefile cho Tuyến đường (Shapes) từ {shapes_path.name}...")
        shapes_data = {}
        with open(shapes_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                shape_id = row['shape_id']
                if shape_id not in shapes_data:
                    shapes_data[shape_id] = []
                shapes_data[shape_id].append({
                    'lon': float(row['shape_pt_lon']),
                    'lat': float(row['shape_pt_lat']),
                    'seq': int(row['shape_pt_sequence'])
                })
                
        lines_records = []
        for shape_id, points in shapes_data.items():
            points.sort(key=lambda x: x['seq'])
            coords = [(p['lon'], p['lat']) for p in points]
            if len(coords) >= 2:
                lines_records.append({
                    'shape_id': shape_id,
                    'geometry': LineString(coords)
                })
                
        if lines_records:
            gdf_lines = gpd.GeoDataFrame(lines_records, crs="EPSG:4326")
            gdf_lines.to_file(out_dir / "shapes.shp", encoding='utf-8')
            print(f" Đã lưu: {out_dir / 'shapes.shp'}")
            
    print(f"Hoàn tất xuất Shapefiles tại thư mục: {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="Map Matching GTFS shapes và xuất ra Shapefile.")
    parser.add_argument("--gtfs_dir", type=str, required=True, help="Đường dẫn đến thư mục chứa các file GTFS (chứa shapes.txt và stops.txt)")
    parser.add_argument("--skip_match", action="store_true", help="Bỏ qua Map Matching, chỉ xuất Shapefile từ shapes.txt hiện tại")
    args = parser.parse_args()
    
    matched_shapes_path = None
    if not args.skip_match:
        matched_shapes_path = process_shapes(args.gtfs_dir)
        
    export_to_shapefile(args.gtfs_dir, matched_shapes_path)

if __name__ == "__main__":
    main()
