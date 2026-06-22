import os
import csv

gtfs_dir = r"c:\Users\TANDAITHANH.COM.VN\crawbusmap\output\gtfs"
shapes_file = os.path.join(gtfs_dir, "shapes.txt")
trips_file = os.path.join(gtfs_dir, "trips.txt")
trips_temp = os.path.join(gtfs_dir, "trips_temp.txt")

# 1. Remove shapes.txt
if os.path.exists(shapes_file):
    os.remove(shapes_file)
    print(f"Removed {shapes_file}")
else:
    print(f"{shapes_file} not found.")

# 2. Remove shape_id column from trips.txt
if os.path.exists(trips_file):
    with open(trips_file, "r", encoding="utf-8") as infile, open(trips_temp, "w", encoding="utf-8", newline="") as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        try:
            header = next(reader)
            if "shape_id" in header:
                shape_id_idx = header.index("shape_id")
                # Remove shape_id from header
                new_header = [h for i, h in enumerate(header) if i != shape_id_idx]
                writer.writerow(new_header)
                
                # Write rows without shape_id
                for row in reader:
                    # Some rows might be shorter, need to handle index out of bounds just in case
                    if len(row) > shape_id_idx:
                        new_row = [val for i, val in enumerate(row) if i != shape_id_idx]
                        writer.writerow(new_row)
                    else:
                        writer.writerow(row)
                print("Successfully removed shape_id from trips.txt")
                replace_file = True
            else:
                print("shape_id column not found in trips.txt.")
                replace_file = False
        except StopIteration:
            print("trips.txt is empty.")
            replace_file = False
            
    if replace_file:
        os.replace(trips_temp, trips_file)
    else:
        os.remove(trips_temp)
else:
    print(f"{trips_file} not found.")

