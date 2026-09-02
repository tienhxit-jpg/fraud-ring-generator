# Neo4j Data Loader v0.2

Script Python để load dữ liệu synthetic fraud detection từ CSV vào Neo4j database.

## Tính năng

- Load accounts, customers, merchants và transactions vào Neo4j
- Reset các trường fraud ring detection về giá trị mặc định:
  - `fraud_ring_member`: None
  - `is_fraud`: 0
  - `fraud_ring_id`: None
  - `cycle_num`: None
- Batch processing với progress bar
- Tạo constraints và indexes tự động
- Hỗ trợ clear database trước khi load

## Cài đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Đảm bảo Neo4j đang chạy và có thể kết nối

## Cấu trúc dữ liệu

Script yêu cầu các file CSV trong thư mục data:
- `accounts.csv`: Thông tin accounts và customers
- `merchants.csv`: Thông tin merchants
- `transactions.csv`: Thông tin transactions

## Sử dụng

### Cú pháp cơ bản

```bash
python load_data.py --uri bolt://localhost:7687 --username neo4j --password mypassword --data-dir ../../data/synthetic/v2/raw
```

### Với tùy chọn clear database

```bash
python load_data.py --uri bolt://localhost:7687 --username neo4j --password mypassword --data-dir ../../data/synthetic/v2/raw --clear
```

### Với database khác neo4j mặc định

```bash
python load_data.py --uri bolt://localhost:7687 --username neo4j --password mypassword --database fraudring --data-dir ../../data/synthetic/v2/raw
```

## Tham số

- `--uri`: URI kết nối Neo4j (bắt buộc)
- `--username`: Username Neo4j (bắt buộc)
- `--password`: Password Neo4j (bắt buộc)
- `--database`: Tên database (mặc định: neo4j)
- `--data-dir`: Thư mục chứa các file CSV (bắt buộc)
- `--clear`: Xóa toàn bộ database trước khi load (tùy chọn)

## Graph Schema

Sau khi load, graph có cấu trúc:

### Nodes
- `Customer`: Thông tin khách hàng
- `Account`: Thông tin tài khoản
- `Merchant`: Thông tin merchant
- `Transaction`: Thông tin giao dịch

### Relationships
- `(Customer)-[:OWNS]->(Account)`: Customer sở hữu Account
- `(Account)-[:SENT]->(Transaction)`: Account gửi Transaction
- `(Transaction)-[:RECEIVED_BY]->(Account)`: Transaction được nhận bởi Account

## Lưu ý

- Script reset tất cả các trường fraud detection về giá trị mặc định
- Batch size mặc định: 1000 cho accounts/merchants, 500 cho transactions
- Script sẽ tự động tạo constraints và indexes
- Sử dụng `--clear` cẩn thận vì sẽ xóa toàn bộ dữ liệu trong database
