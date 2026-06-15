# -*- coding: utf-8 -*-
"""
fetch_hanoi_routes.py
Script Python dùng để gọi API BusMap, giải mã dữ liệu mã hóa AES-256-CBC,
và ghi kết quả JSON vào thư mục output/.

Các API cần lấy:
1. Danh sách Region (Khu vực)
2. Danh sách tuyến của Hà Nội (regionCode = hn)
3. Chi tiết tuyến 01 và 02 của Hà Nội
4. Timeline của tuyến 01 và 02 của Hà Nội
"""

import os
import json
import sys
import binascii
from pathlib import Path

# Đảm bảo in UTF-8 trên Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Cố gắng import thư viện giải mã
try:
    import requests
except ImportError:
    print("Lỗi: Vui lòng cài đặt thư viện 'requests' bằng lệnh: pip install requests")
    sys.exit(1)

# Thử import thư viện mã hóa (hỗ trợ cả cryptography và pycryptodome)
crypto_lib = None
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    crypto_lib = "cryptography"
except ImportError:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        crypto_lib = "pycryptodome"
    except ImportError:
        print("Lỗi: Vui lòng cài đặt thư viện giải mã bằng một trong các lệnh sau:")
        print("  pip install cryptography")
        print("  hoặc: pip install pycryptodome")
        sys.exit(1)

# Cấu hình API
BASE_URL = "https://api-web.busmap.vn"
DEFAULT_KEY = b"BuSm@p2ol9#K3(y)th3BUSiNiTv3ct0r"
OUTPUT_DIR = Path(__file__).parents[1] / "output"

def get_decrypt_key() -> bytes:
    """Lấy khóa giải mã từ API, nếu lỗi sẽ sử dụng khóa mặc định."""
    url = f"{BASE_URL}/web/public/auth/decrypt_key"
    try:
        print(f"Đang lấy khóa giải mã từ: {url} ...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        key_str = resp.text.strip()
        # Loại bỏ dấu ngoặc kép thừa nếu có
        if key_str.startswith('"') and key_str.endswith('"'):
            key_str = key_str[1:-1]
        key = key_str.encode('utf-8')
        print(f"Lấy khóa thành công. Độ dài khóa: {len(key)} bytes.")
        return key
    except Exception as e:
        print(f"[CẢNH BÁO] Không thể lấy khóa từ API ({e}). Sử dụng khóa mặc định.")
        return DEFAULT_KEY

def decrypt_payload(hex_str: str, key: bytes) -> str:
    """Giải mã chuỗi Hex mã hóa AES-256-CBC."""
    if not hex_str:
        return ""
    
    # Loại bỏ dấu ngoặc kép bao quanh chuỗi hex nếu API trả về dạng raw string json
    hex_str = hex_str.strip()
    if hex_str.startswith('"') and hex_str.endswith('"'):
        hex_str = hex_str[1:-1]
        
    try:
        encrypted_data = binascii.unhexlify(hex_str)
    except Exception as e:
        # Nếu không phải là chuỗi hex hợp lệ, trả về nguyên bản
        return hex_str

    if len(encrypted_data) < 16:
        return hex_str

    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    try:
        if crypto_lib == "cryptography":
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            # Loại bỏ PKCS7 padding
            padding_len = padded_data[-1]
            if 1 <= padding_len <= 16:
                plain_data = padded_data[:-padding_len]
            else:
                plain_data = padded_data
            return plain_data.decode('utf-8')
        
        elif crypto_lib == "pycryptodome":
            cipher = AES.new(key, AES.MODE_CBC, iv)
            plain_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return plain_data.decode('utf-8')
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi giải mã: {e}")
        return hex_str

def is_hex_string(s: str) -> bool:
    """Kiểm tra xem chuỗi có phải là chuỗi hex đã mã hóa hay không."""
    s_clean = s.strip().replace('"', '')
    if len(s_clean) < 32 or len(s_clean) % 2 != 0:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s_clean)

def fetch_and_decrypt(endpoint: str, params: dict = None, key: bytes = DEFAULT_KEY):
    """Gửi request GET tới API, tự động giải mã nếu phản hồi là chuỗi Hex mã hóa."""
    url = f"{BASE_URL}{endpoint}"
    try:
        print(f"Đang gọi API: {url} với tham số {params} ...")
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw_text = resp.text.strip()
        
        if is_hex_string(raw_text):
            decrypted_text = decrypt_payload(raw_text, key)
            try:
                return json.loads(decrypted_text)
            except json.JSONDecodeError:
                return decrypted_text
        else:
            try:
                return resp.json()
            except ValueError:
                return raw_text
    except Exception as e:
        print(f"[LỖI] Lỗi khi gọi API {url}: {e}")
        return None

def save_output(data, filename: str):
    """Lưu dữ liệu dưới dạng JSON đẹp vào thư mục output/."""
    file_path = OUTPUT_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu kết quả -> {file_path}")

def main():
    print(f"--- BẮT ĐẦU TEST API BUSMAP (Sử dụng thư viện: {crypto_lib}) ---")
    
    # Lấy khóa giải mã từ API
    key = get_decrypt_key()
    
    # 1. Lấy danh sách Region (Khu vực)
    print("\n[Tác vụ 1] Lấy danh sách Region...")
    regions = fetch_and_decrypt("/web/public/region/list", key=key)
    if regions:
        save_output(regions, "region/list.json")
    else:
        print("Không thể lấy danh sách Region.")

    # 2. Lấy danh sách tuyến đường của Hà Nội (hn)
    print("\n[Tác vụ 2] Lấy danh sách tuyến của Hà Nội (hn)...")
    routes = fetch_and_decrypt("/web/public/route/list", params={"regionCode": "hn"}, key=key)
    if routes:
        save_output(routes, "route/list.json")
        
        # Lọc tuyến 01 và 02 của Hà Nội
        target_route_nos = {"01", "02"}
        target_routes = [r for r in routes if str(r.get("routeNo")).zfill(2) in target_route_nos or str(r.get("routeName")).startswith("01 ") or str(r.get("routeName")).startswith("02 ")]
        
        if not target_routes:
            # Dự phòng lọc theo tên hoặc số hiệu gần đúng
            target_routes = [r for r in routes if "01" in str(r.get("routeNo")) or "02" in str(r.get("routeNo"))]
            
        print(f"Tìm thấy {len(target_routes)} tuyến khớp với yêu cầu (01, 02).")
        
        for route in target_routes:
            route_id = route.get("routeId")
            route_no = str(route.get("routeNo")).zfill(2)
            route_name = route.get("routeName")
            
            print(f"\n--- Xử lý Tuyến {route_no} (ID: {route_id}) - {route_name} ---")
            
            # 3. Lấy chi tiết tuyến (Stations, path...)
            print(f"Lấy chi tiết tuyến {route_no}...")
            detail = fetch_and_decrypt("/web/public/route/detail", params={"routeId": route_id, "regionCode": "hn"}, key=key)
            if detail:
                save_output(detail, f"route/detail/{route_no}.json")
            else:
                print(f"Lỗi: Không lấy được chi tiết tuyến {route_no}")

            # 4. Lấy timeline của tuyến ( weekday=1 biểu thị thứ hai, time="08:00" )
            print(f"Lấy timeline tuyến {route_no}...")
            timeline = fetch_and_decrypt("/web/public/route/timeline", params={
                "routeId": route_id,
                "regionCode": "hn",
                "weekday": 1,
                "time": "08:00"
            }, key=key)
            if timeline:
                save_output(timeline, f"route/timeline/{route_no}.json")
            else:
                print(f"Lỗi: Không lấy được timeline tuyến {route_no}")
    else:
        print("Không thể lấy danh sách tuyến đường Hà Nội.")

    print("\n--- HOÀN THÀNH TÁC VỤ ---")

if __name__ == "__main__":
    main()
