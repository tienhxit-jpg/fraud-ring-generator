# Generator v03

## Mục tiêu

v03 sửa lỗi topology của v02: tài khoản trong fraud ring không còn hoàn toàn tách biệt khỏi giao dịch nền.

Thiết kế vẫn giữ kết quả detection gần v02 bằng ba nguyên tắc:

1. Giữ nguyên 5.000 tài khoản thường, 225 tài khoản fraudster, 45 ring và 3.072 giao dịch gian lận.
2. Giữ tổng ngân sách giao dịch nền là 47.500. Trong đó 90 dòng được dành cho bridge và 47.410 dòng còn lại là giao dịch thường-normal.
3. Mỗi ring chỉ có một hướng bridge:
   - ring chẵn: `fraud ring -> normal account`;
   - ring lẻ: `normal account -> fraud ring`.

Vì một ring chỉ có cạnh ra hoặc cạnh vào đối với mạng nền, nó không trở nên hai chiều với giant SCC của nền. Do đó ring vẫn giữ SCC riêng và các chu trình của ring không bị biến thành một SCC khổng lồ.

## Cấu trúc file

- `config_academic.yaml`: cấu hình v03.
- `transaction_generator.py`: sinh giao dịch nền và bridge một chiều.
- `data_generator.py`: pipeline sinh dữ liệu hoàn chỉnh, dùng lại account/ring/validator của v02.

## Tham số bridge

```yaml
background_connectivity:
  enabled: true
  bridges_per_ring: 2
  direction_strategy: alternate_by_ring
```

Các lựa chọn `direction_strategy`:

- `outbound`: mọi ring gửi ra tài khoản thường;
- `inbound`: mọi ring nhận từ tài khoản thường;
- `alternate_by_ring`: ring chẵn outbound, ring lẻ inbound; đây là mặc định.

Bridge có:

```text
is_fraud = 0
fraud_ring_id = null
transaction_type = background_bridge
```

`background_ring_id` chỉ tồn tại tạm thời trong bộ nhớ để kiểm thử và được xóa trước khi ghi CSV. Detector không được nhìn thấy thuộc tính này.

## Chạy sinh dữ liệu

Từ thư mục gốc dự án:

```bash
./venv/Scripts/python.exe src/generators/v03/data_generator.py
```

Output:

```text
data/synthetic/v03/raw/accounts.csv
data/synthetic/v03/raw/merchants.csv
data/synthetic/v03/raw/transactions.csv
data/synthetic/v03/ground_truth/fraud_rings.json
```

## Kiểm tra đã chạy

Generator v03 đã chạy thành công với kết quả:

```text
accounts       = 5,225
transactions   = 50,572
fraud tx       = 3,072
background tx  = 47,500
bridge tx      = 90
fraud rings    = 45
```

So sánh topology bằng NetworkX giữa v02 và v03:

| Chỉ số | v02 | v03 |
|---|---:|---:|
| Tổng transaction | 50.572 | 50.572 |
| Fraud transaction | 3.072 | 3.072 |
| Bridge transaction | 0 | 90 |
| Account | 5.225 | 5.225 |
| Giant SCC lớn nhất | 5.000 | 4.999 |
| Số SCC có chứa fraud participant | 45 | 45 |
| Kích thước fraud SCC lớn nhất | 8 | 8 |

Các test hành vi trong `tests/test_generator_v03.py` cũng đã pass, gồm:

- mỗi ring nhận đúng số bridge;
- bridge không mang nhãn fraud;
- mỗi ring chỉ dùng một hướng bridge;
- SCC ring không mở rộng thành SCC nền;
- bridge thay thế một phần budget thay vì làm tăng tổng transaction.

## Lưu ý khi chạy detection

Để không tái tạo lỗi rò rỉ ground truth đã phát hiện ở bước trước, không bật các chế độ dùng nhãn khi đánh giá:

```text
Không dùng --require-fraud-evidence
Không dùng --mode anchored
Không dùng --projection-scope fraud_evidence
```

Bridge chỉ thay đổi topology ngoại vi. Các kết quả detection thực tế trên Neo4j cần được chạy lại sau khi import `data/synthetic/v03` để xác nhận runtime và số candidate cuối cùng; kiểm tra hiện tại đã xác nhận rằng số ring SCC và kích thước SCC được giữ nguyên gần như v02.
