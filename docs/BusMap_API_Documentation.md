# Hướng dẫn chi tiết API BusMap & Cơ chế giải mã

Tài liệu này cung cấp thông tin toàn diện về các chức năng, endpoint API và cơ chế bảo mật (mã hóa/giải mã AES-256-CBC) được sử dụng trong dự án BusMap.

---

## 1. Cơ chế Bảo mật và Giải mã Dữ liệu (AES-256-CBC)

Hầu hết các phản hồi từ API BusMap (subdomain `api-web.busmap.vn`) được mã hóa thành các chuỗi ký tự Hex dài để bảo vệ dữ liệu. Phía client (Angular app) giải mã các chuỗi này trước khi hiển thị.

### Phân tích mã nguồn giải mã (Từ module `xxB7` trong tệp `main-es2015.js`)

Mã nguồn giải mã của BusMap được viết dưới dạng lớp Angular Service như sau:

```javascript
decryptMessage(e) {
  if (this.isReady()) {
    const i = t.from(e, "hex"),                      // Chuyển chuỗi Hex nhận được sang mảng bytes (Buffer)
          o = i.slice(0, 16),                        // 16 bytes đầu tiên làm IV (Vector khởi tạo)
          s = i.slice(16),                           // Các bytes tiếp theo là Ciphertext (Dữ liệu mã hóa)
          a = r.createDecipheriv("aes-256-cbc", this.key, o); // Khởi tạo bộ giải mã AES-256-CBC
    let c = a.update(s, void 0, "utf8");
    c += a.final("utf8");                            // Giải mã ra chuỗi text gốc
    try {
      return JSON.parse(c);                          // Chuyển đổi sang JSON object nếu có thể
    } catch (n) {
      return c;                                      // Trả về văn bản thuần nếu không phải JSON
    }
  }
  return null;
}
```

### Chi tiết các tham số giải mã:
1. **Thuật toán**: `AES-256-CBC` (Advanced Encryption Standard với khóa 256-bit, chế độ Cipher Block Chaining).
2. **Khóa giải mã (Key)**:
   - Được tải động từ endpoint: `/web/public/auth/decrypt_key`.
   - **Khóa tĩnh mặc định (Fallback)** được hardcode trong ứng dụng trong trường hợp offline: 
     `BuSm@p2ol9#K3(y)th3BUSiNiTv3ct0r` (32 bytes ASCII).
3. **Vectơ khởi tạo (IV)**:
   - Lấy trực tiếp từ **16 byte đầu tiên** (tương đương 32 ký tự Hex đầu tiên) của chuỗi Hex nhận được từ API.
4. **Dữ liệu mã hóa (Ciphertext)**:
   - Bắt đầu từ **byte thứ 17** (từ ký tự Hex thứ 33) trở đi của chuỗi phản hồi.

---

## 2. Tài liệu hóa các API & Chức năng của Dự án

Dưới đây là danh sách các API chính và chức năng đi kèm của dự án BusMap. Tất cả các API đều dùng phương thức `GET` và có URL cơ sở: `https://api-web.busmap.vn`.

### 2.1. Xác thực và Lấy Khóa Giải mã
* **Endpoint**: `/web/public/auth/decrypt_key`
* **Mô tả**: Lấy khóa giải mã AES-256-CBC dùng cho tất cả các API khác.
* **Tham số**: Không có.
* **Kiểu dữ liệu trả về**: Văn bản thô (Plain Text) chứa chuỗi khóa 32 ký tự.

### 2.2. Quản lý Region (Khu vực địa lý)
* **Endpoint**: `/web/public/region/list`
* **Mô tả**: Lấy danh sách các tỉnh thành hỗ trợ trên BusMap (Ví dụ: TP.HCM, Hà Nội, Đà Nẵng...).
* **Tham số**: Không có.
* **Định dạng kết quả sau giải mã**: 
  ```json
  [
    {
      "id": 1,
      "regionCode": "sg",
      "name": "TP. Hồ Chí Minh",
      ...
    },
    {
      "id": 2,
      "regionCode": "hn",
      "name": "Hà Nội",
      ...
    }
  ]
  ```

### 2.3. Danh sách Tuyến xe buýt (Route List)
* **Endpoint**: `/web/public/route/list`
* **Mô tả**: Lấy toàn bộ danh sách tuyến xe buýt trong khu vực chỉ định.
* **Tham số**:
  * `regionCode` (Bắt buộc): Mã khu vực (ví dụ: `hn` hoặc `sg`).
* **Định dạng kết quả sau giải mã**: Mảng chứa các tuyến đường gồm số hiệu tuyến (`routeNo`), tên tuyến (`routeName`), giá vé (`normalTicket`), đơn vị vận hành (`orgs`):
  ```json
  [
    {
      "routeId": 1,
      "routeNo": "01",
      "routeName": "Bến xe Gia Lâm - Bến xe Yên Nghĩa",
      "normalTicket": 10000,
      ...
    }
  ]
  ```

### 2.4. Chi tiết Tuyến xe buýt (Route Detail)
* **Endpoint**: `/web/public/route/detail`
* **Mô tả**: Lấy chi tiết lộ trình của tuyến xe buýt, bao gồm danh sách các trạm dừng theo hai chiều đi/về và tọa độ để vẽ lộ trình trên bản đồ.
* **Tham số**:
  * `routeId` (Bắt buộc): ID của tuyến xe buýt (lấy từ Route List).
  * `regionCode` (Bắt buộc): Mã khu vực (ví dụ: `hn`).
* **Định dạng kết quả sau giải mã**:
  - `stations`: Danh sách các trạm dừng (`stationName`, `lat`, `lng`, `stationOrder`, `stationDirection` (0: chiều đi, 1: chiều về)).
  - `pathPoints`: Tọa độ các điểm nối tiếp nhau để vẽ đường chạy của xe trên bản đồ.

### 2.5. Lịch trình khởi hành (Route Timeline)
* **Endpoint**: `/web/public/route/timeline`
* **Mô tả**: Cung cấp mốc thời gian xuất phát của các chuyến xe buýt tại điểm đầu bến trong ngày theo thời gian thực.
* **Tham số**:
  * `routeId` (Bắt buộc): ID của tuyến.
  * `regionCode` (Bắt buộc): Mã khu vực (`hn`).
  * `weekday` (Bắt buộc): Ngày trong tuần (ví dụ: `1` cho Thứ Hai).
  * `time` (Bắt buộc): Mốc thời gian bắt đầu tra cứu (ví dụ: `"08:00"`).
* **Định dạng kết quả sau giải mã**: Chứa mảng các mốc thời gian khởi hành (đã quy đổi ra số giây tính từ 00:00:00 của ngày hôm đó).

### 2.6. Tìm kiếm trạm gần đây (Near Stations)
* **Endpoint**: `/web/public/station/near`
* **Mô tả**: Tìm kiếm các trạm xe buýt gần vị trí GPS hiện tại của người dùng.
* **Tham số**:
  * `lat`: Vĩ độ hiện tại.
  * `lng`: Kinh độ hiện tại.
  * `r`: Bán kính tìm kiếm bằng mét (ví dụ: `500`).
  * `regionCode`: Mã khu vực (`hn`).
* **Định dạng kết quả sau giải mã**: Danh sách các trạm dừng xung quanh cùng khoảng cách đến vị trí GPS được cung cấp.

### 2.7. Ước tính xe tới trạm (Estimate Bus to Station)
* **Endpoint**: `/web/public/station/estimate_bus_to_station_multi`
* **Mô tả**: Ước tính khoảng cách và thời gian di chuyển của các chuyến xe đang chạy tới một hoặc nhiều trạm xe buýt.
* **Tham số**:
  * `regionCode`: Mã khu vực.
  * `stations` (Bắt buộc): Mảng ID trạm xe dừng dạng chuỗi (ví dụ: `"[1749,1487]"`).

---

## 3. Hướng dẫn sử dụng công cụ Python Test API

Chúng tôi đã viết một script Python kiểm thử tự động tại `script/fetch_hanoi_routes.py` thực hiện đầy đủ luồng công việc:
1. Lấy khóa giải mã API (nếu lỗi sẽ sử dụng khóa tĩnh fallback).
2. Lấy danh sách Region và lưu vào `output/region/list.json`.
3. Lấy danh sách Tuyến xe Hà Nội và lưu vào `output/route/list.json`.
4. Tìm và trích xuất chi tiết lộ trình + thời gian khởi hành (timeline) của tuyến **01** và **02** của Hà Nội và lưu vào `output/route/detail/` và `output/route/timeline/`.

### Yêu cầu hệ thống:
Cài đặt thư viện HTTP client và thư viện giải mã:
```bash
pip install requests cryptography
```

### Thực thi:
```bash
python script/fetch_hanoi_routes.py
```

Kết quả đầu ra sẽ được lưu tại thư mục `output/` với cấu trúc JSON định dạng đẹp dễ đọc:
```
output/
├── region/
│   └── list.json
└── route/
    ├── list.json
    ├── detail/
    │   ├── 01.json
    │   └── 02.json
    └── timeline/
        ├── 01.json
        └── 02.json
```
