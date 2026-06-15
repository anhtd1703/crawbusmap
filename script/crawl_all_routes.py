# -*- coding: utf-8 -*-
"""
crawl_all_routes.py
Script Python lấy toàn bộ dữ liệu (detail, timeline) của tất cả các tuyến trong một khu vực (VD: Hà Nội).
Hỗ trợ cơ chế cache: Nếu file đã tồn tại thì bỏ qua, giúp resume nếu tiến trình bị gián đoạn.
"""

import os
import json
import sys
import binascii
import time
from pathlib import Path

# Đảm bảo in UTF-8 trên Windows console
sys.stdout.reconfigure(encoding='utf-8')

try:
    import requests
except ImportError:
    print("Lỗi: Vui lòng cài đặt thư viện 'requests' bằng lệnh: pip install requests")
    sys.exit(1)

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
        print("Lỗi: Vui lòng cài đặt thư viện giải mã: pip install cryptography")
        sys.exit(1)

BASE_URL = "https://api-web.busmap.vn"
DEFAULT_KEY = b"BuSm@p2ol9#K3(y)th3BUSiNiTv3ct0r"
# Thư mục gốc chứa file python
BASE_DIR = Path(__file__).parents[1]
OUTPUT_DIR = BASE_DIR / "output" / "raw"

def get_decrypt_key() -> bytes:
    url = f"{BASE_URL}/web/public/auth/decrypt_key"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        key_str = resp.text.strip()
        if key_str.startswith('"') and key_str.endswith('"'):
            key_str = key_str[1:-1]
        return key_str.encode('utf-8')
    except Exception as e:
        print(f"[CẢNH BÁO] Không thể lấy khóa từ API: {e}. Dùng khóa mặc định.")
        return DEFAULT_KEY

def decrypt_payload(hex_str: str, key: bytes) -> str:
    if not hex_str: return ""
    hex_str = hex_str.strip()
    if hex_str.startswith('"') and hex_str.endswith('"'):
        hex_str = hex_str[1:-1]
        
    try:
        encrypted_data = binascii.unhexlify(hex_str)
    except Exception:
        return hex_str

    if len(encrypted_data) < 16: return hex_str

    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    try:
        if crypto_lib == "cryptography":
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            padding_len = padded_data[-1]
            if 1 <= padding_len <= 16:
                return padded_data[:-padding_len].decode('utf-8')
            return padded_data.decode('utf-8')
        elif crypto_lib == "pycryptodome":
            cipher = AES.new(key, AES.MODE_CBC, iv)
            plain_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return plain_data.decode('utf-8')
    except Exception:
        return hex_str

def is_hex_string(s: str) -> bool:
    s_clean = s.strip().replace('"', '')
    if len(s_clean) < 32 or len(s_clean) % 2 != 0: return False
    return all(c in "0123456789abcdefABCDEF" for c in s_clean)

def fetch_and_decrypt(endpoint: str, params: dict = None, key: bytes = DEFAULT_KEY):
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw_text = resp.text.strip()
        
        if is_hex_string(raw_text):
            decrypted_text = decrypt_payload(raw_text, key)
            try: return json.loads(decrypted_text)
            except json.JSONDecodeError: return decrypted_text
        else:
            try: return resp.json()
            except ValueError: return raw_text
    except Exception as e:
        print(f"[LỖI] khi gọi API {url}: {e}")
        return None

def save_output(data, filename: str):
    file_path = OUTPUT_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_exists(filename: str) -> bool:
    file_path = OUTPUT_DIR / filename
    return file_path.exists() and file_path.stat().st_size > 0

def main():
    print(f"--- BẮT ĐẦU CRAWL DATA BUSMAP ---")
    
    key = get_decrypt_key()
    
    region_code = "hn"
    print(f"\n[1] Lấy danh sách tuyến của khu vực ({region_code})...")
    routes = fetch_and_decrypt("/web/public/route/list", params={"regionCode": region_code}, key=key)
    if not routes:
        print("Lỗi: Không lấy được danh sách tuyến.")
        return
        
    save_output(routes, "route/list.json")
    print(f"Tổng số tuyến tìm thấy: {len(routes)}")

    for index, route in enumerate(routes):
        route_id = route.get("routeId")
        # Format routeNo có thể có chữ cái (ví dụ E01, 10A, v.v.), nên lưu thẳng thay vì zfill nếu nó là string
        route_no = str(route.get("routeNo")).strip() 
        route_name = route.get("routeName")
        
        print(f"\n[{index+1}/{len(routes)}] Tuyến {route_no} (ID: {route_id}) - {route_name}")
        
        # Crawl detail
        detail_filename = f"route/detail/{route_no}_{route_id}.json"
        if not check_exists(detail_filename):
            print(f"  -> Tải detail...")
            detail = fetch_and_decrypt("/web/public/route/detail", params={"routeId": route_id, "regionCode": region_code}, key=key)
            if detail:
                save_output(detail, detail_filename)
            time.sleep(0.5) # Tránh bị rate limit
        else:
            print(f"  -> Detail đã tồn tại, bỏ qua.")
            
        # Crawl timeline (Lấy cho thứ 2, giờ từ 00:00)
        timeline_filename = f"route/timeline/{route_no}_{route_id}.json"
        if not check_exists(timeline_filename):
            print(f"  -> Tải timeline...")
            timeline = fetch_and_decrypt("/web/public/route/timeline", params={
                "routeId": route_id,
                "regionCode": region_code,
                "weekday": 1,
                "time": "00:00"
            }, key=key)
            if timeline:
                save_output(timeline, timeline_filename)
            time.sleep(0.5)
        else:
            print(f"  -> Timeline đã tồn tại, bỏ qua.")

    print("\n--- HOÀN THÀNH CRAWL ---")

if __name__ == "__main__":
    main()
