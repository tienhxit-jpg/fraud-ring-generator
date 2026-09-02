# Pipeline phát hiện chu trình Pure Cypher v02

## 1. Mục tiêu

Pipeline này dùng **Pure Cypher** để phát hiện các chu trình tài khoản có kích thước 3, 5 và 8 trên Neo4j. Thiết kế phục vụ thực nghiệm so sánh giữa các phương pháp, với các yêu cầu:

- không đọc nhãn đáp án trong detection;
- chạy được cả cycle size 3, 5 và 8;
- tránh bùng nổ tổ hợp do nhiều giao dịch giữa cùng một cặp tài khoản;
- lưu riêng kết quả thô và kết quả sau gộp;
- tính FF bằng một script Python độc lập;
- ground truth chỉ được sử dụng ở bước evaluation sau cùng.

Các script liên quan:

```text
src/cycle_detection/v02/cypher_cycle_detection_v02.py
src/cycle_detection/v02/calculate_ff.py
```

## 2. Nguyên tắc label-blind

Trong toàn bộ detection pipeline, Cypher không được đọc hoặc kiểm tra:

```text
Transaction.is_fraud
Transaction.fraud_ring_id
Account.fraud_ring_member
```

Pipeline cũng không có chế độ `anchored` dựa trên tài khoản đã biết là thành viên fraud ring.

Các thuộc tính được phép dùng gồm:

```text
Account.account_id
Transaction.amount_usd / Transaction.amount
Transaction.timestamp
TRANSFER_AGG.transaction_count
TRANSFER_AGG.total_amount
```

Ground truth chỉ được đọc sau khi raw và merged prediction đã được ghi ra file. Việc tính FF không cần ground truth.

## 3. Kiến trúc tổng thể

```text
Account -> Transaction -> Account
            |
            | Pure Cypher aggregation
            v
Account -[:TRANSFER_AGG]-> Account
            |
            | business-edge filtering
            v
Fixed cycle discovery: 3 -> 5 -> 8
            |
            +----------------------+
            |                      |
            v                      v
raw_candidates.jsonl      overlap merge bằng Union-Find
                                   |
                                   v
                         merged_candidates.jsonl
            |
            v
calculate_ff.py
            |
            v
ff_metrics.json
```

Pipeline gồm năm bước:

1. Import dữ liệu giao dịch vào Neo4j.
2. Dựng logical account graph bằng `TRANSFER_AGG`.
3. Chạy ba truy vấn fixed-length cho cycle size 3, 5 và 8.
4. Ghi raw candidates và gộp các candidate giao nhau.
5. Tính FF bằng script Python riêng.

## 4. Schema đầu vào

Dữ liệu gốc sử dụng transaction-node schema:

```text
(:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Account)
```

Mỗi `Transaction` có thể chứa:

```text
transaction_id
amount_usd hoặc amount
timestamp
```

Một cặp tài khoản có thể có nhiều transaction. Nếu tìm cycle trực tiếp trên transaction node, số path có thể tăng theo tích:

```text
tx(A,B) × tx(B,C) × ... × tx(X,A)
```

Đây là nguyên nhân chính làm các truy vấn cycle size 5 và 8 trước đây chạy rất lâu.

## 5. Bước 1 — dựng logical account graph

Detector tạo một relationship tổng hợp cho mỗi cặp tài khoản có giao dịch:

```text
(:Account)-[:TRANSFER_AGG]->(:Account)
```

Cypher tương đương:

```cypher
MATCH (src:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(dst:Account)
WHERE src <> dst
WITH src, dst,
     count(t) AS transaction_count,
     sum(coalesce(t.amount_usd, t.amount, 0.0)) AS total_amount,
     min(t.timestamp) AS first_timestamp,
     max(t.timestamp) AS last_timestamp
MERGE (src)-[r:TRANSFER_AGG]->(dst)
SET r.transaction_count = transaction_count,
    r.total_amount = total_amount,
    r.first_timestamp = first_timestamp,
    r.last_timestamp = last_timestamp
```

Relationship tổng hợp không chứa ground-truth label.

### Khi nào cần dựng lại?

Phải chạy lại bước này sau khi:

- import dataset mới;
- thêm, xóa hoặc sửa transaction;
- chuyển sang database khác.

Nếu dữ liệu không đổi, có thể tái sử dụng `TRANSFER_AGG` hiện có.

### Chi phí benchmark

Thời gian dựng aggregate graph phải được báo cáo riêng với thời gian detection:

```text
T_prepare
T_detection
T_total = T_prepare + T_detection
```

Không nên chỉ báo cáo `T_detection` mà bỏ qua chi phí chuẩn bị.

## 6. Bước 2 — business-edge filtering

Mỗi relationship được lọc ngay sau `MATCH`:

```cypher
MATCH (a0:Account)-[r0:TRANSFER_AGG]->(a1:Account)
WHERE r0.transaction_count >= $min_pair_transactions
  AND r0.total_amount >= $min_pair_amount

MATCH (a1:Account)-[r1:TRANSFER_AGG]->(a2:Account)
WHERE r1.transaction_count >= $min_pair_transactions
  AND r1.total_amount >= $min_pair_amount
```

Việc đặt filter ngay sau từng `MATCH` rất quan trọng. Nếu đợi đến khi mở rộng đủ 8 cạnh rồi mới gọi `all(...)`, Neo4j vẫn phải sinh lượng path trung gian rất lớn và có thể hết transaction memory.

Cấu hình mặc định của phiên bản tối ưu:

```text
min_pair_transactions = 3
min_pair_amount = 0
```

Trên v03, ngưỡng `transaction_count >= 3` giảm logical pair graph từ 48.142 xuống 450 cạnh. Phép kiểm cấu trúc cho thấy nó vẫn giữ cycle đúng kích thước trong 15/15 ring size 3, 20/20 ring size 5 và 10/10 ring size 8.

Tuy nhiên đây vẫn là một hyperparameter nghiệp vụ. Trong báo cáo khoa học cần:

- công khai ngưỡng;
- giải thích ý nghĩa “giao dịch lặp ít nhất ba lần”;
- giữ nguyên ngưỡng giữa các phương pháp nếu chúng dùng cùng filter;
- xác nhận lại trên tập holdout để tránh tune theo ground truth.

## 7. Bước 3 — fixed-length cycle discovery

Pipeline chạy ba truy vấn riêng và tuần tự:

```text
cycle size 3
cycle size 5
cycle size 8
```

Không sử dụng variable-length pattern kiểu:

```cypher
[:TRANSFER_AGG*3..8]
```

Việc tách truy vấn giúp:

- đo runtime riêng cho từng kích thước;
- lưu số result riêng;
- tránh cycle size 8 chiếm tài nguyên của size 3 và 5;
- dễ resume và chẩn đoán lỗi.

### Canonicalization

Đỉnh `a0` phải là account có `account_id` nhỏ nhất trong cycle:

```cypher
a0.account_id = reduce(
    min_id = a0.account_id,
    id IN [a1.account_id, a2.account_id, ...] |
    CASE WHEN id < min_id THEN id ELSE min_id END
)
```

Nhờ đó, các rotation của cùng một cycle không bị đếm nhiều lần chỉ vì khác điểm bắt đầu.

Canonicalization không gộp các thứ tự cạnh thực sự khác nhau. Hai cycle có cùng participant set nhưng thứ tự chuyển tiền khác nhau vẫn có thể xuất hiện thành hai raw cycle records; mức lặp này được phản ánh trong `FF_enumeration`.

### Không sort trong discovery

Query không dùng:

```cypher
ORDER BY total_amount
```

Khi `--limit 0`, Neo4j có thể stream kết quả mà không phải giữ và sort toàn bộ candidate trong memory.

### Ý nghĩa `--limit`

```text
--limit 0   : bỏ LIMIT, trả về toàn bộ candidate của mỗi cycle size
--limit 500 : tối đa 500 candidate cho mỗi cycle size
```

Muốn tính FF đầy đủ phải dùng `--limit 0`. FF từ một output bị giới hạn chỉ là FF trên mẫu kết quả, không phải FF toàn graph.

## 8. Bước 4 — raw và merged outputs

Detector ghi hai file độc lập.

### Raw output

```text
raw_candidates_optimized.jsonl
```

Mỗi dòng là một cycle record:

```json
{
  "participants": ["ACC_001", "ACC_002", "ACC_003"],
  "cycle_size": 3,
  "transactions": 12,
  "total_amount": 250000.0,
  "cycles": 1,
  "metrics_are_group_level": true
}
```

`transactions` và `total_amount` ở đây được tổng hợp từ các `TRANSFER_AGG` nằm trên cycle, không phải toàn bộ transaction giữa mọi cặp participant.

### Merged output

```text
merged_candidates_optimized.jsonl
```

Các cycle có participant giao nhau được gộp bằng Union-Find. Ví dụ:

```text
{A,B,C} + {C,D,E} -> {A,B,C,D,E}
```

Merged record chứa:

```text
participants
participant_count
transactions
total_amount
cycles
fragment_count
candidate_cycle_sizes
method
```

Việc merge không đọc ground truth.

## 9. Bước 5 — tính FF bằng script riêng

FF được tính sau detection bằng:

```text
src/cycle_detection/v02/calculate_ff.py
```

Script chỉ đọc raw JSONL, không kết nối Neo4j và không đọc ground truth.

Ba đại lượng trung gian:

```text
N_raw_cycles      = số raw cycle records
N_unique_sets     = số participant set khác nhau
N_merged_clusters = số cụm sau overlap merge
```

Ba chỉ số:

```text
FF_enumeration   = N_raw_cycles / N_unique_sets
FF_fragmentation = N_unique_sets / N_merged_clusters
FF_total         = N_raw_cycles / N_merged_clusters
```

Ý nghĩa:

- `FF_enumeration`: một participant set tạo ra bao nhiêu cycle order khác nhau;
- `FF_fragmentation`: một candidate cluster bị chia thành bao nhiêu participant set;
- `FF_total`: tổng số raw cycle records trên mỗi candidate cluster.

FF mới được tính trên logical account graph. Nó không trực tiếp tương đương FF của query cũ nếu query cũ đếm tổ hợp transaction path.

## 10. Cách chạy pipeline

### 10.1. Lần đầu hoặc sau khi import lại dữ liệu

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/cypher_cycle_detection_v02.py \
  --prepare-aggregates \
  --graph-mode aggregate \
  --dataset-dir data/synthetic/v03 \
  --cycle-sizes 3,5,8 \
  --limit 0 \
  --min-pair-transactions 3 \
  --min-pair-amount 0 \
  --progress-interval 30 \
  --raw-jsonl-out data/cycledetection/cypher_v02/raw_candidates_optimized.jsonl \
  --merged-jsonl-out data/cycledetection/cypher_v02/merged_candidates_optimized.jsonl \
  --json-out data/cycledetection/cypher_v02/summary_optimized.json
```

Thông tin kết nối được đọc từ `neo4j.env` thông qua `src/neo4j_config.py`. Có thể ghi đè bằng các flag `--uri`, `--user`, `--password` và `--database`.

### 10.2. Khi aggregate graph đã tồn tại và dữ liệu không đổi

Bỏ `--prepare-aggregates`:

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/cypher_cycle_detection_v02.py \
  --graph-mode aggregate \
  --cycle-sizes 3,5,8 \
  --limit 0 \
  --min-pair-transactions 3
```

### 10.3. Tính FF

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/calculate_ff.py \
  --raw-jsonl data/cycledetection/cypher_v02/raw_candidates_optimized.jsonl \
  --json-out data/cycledetection/cypher_v02/ff_optimized.json
```

## 11. Log tiến độ

Log được ghi vào `stderr`, còn summary JSON được ghi ra `stdout` và file JSON.

Ví dụ:

```text
[14:10:15] detection started (cycle_sizes=3,5,8, limit=all)
[14:10:15] cycle_size=3 started (limit=all)
[14:10:16] cycle_size=3 finished (1.2s, rows=188)
[14:10:16] cycle_size=5 started (limit=all)
[14:10:17] cycle_size=5 finished (0.8s, rows=616)
[14:10:17] cycle_size=8 started (limit=all)
[14:10:19] cycle_size=8 finished (2.1s, rows=371)
```

Điều chỉnh heartbeat:

```text
--progress-interval 30
--progress-interval 0   # tắt heartbeat
--quiet                 # tắt toàn bộ progress log
```

## 12. Kết quả kiểm chứng trên v03

Lần chạy đã xác nhận:

```text
Aggregate preparation: 3,5 giây, 48.142 logical pairs
Cycle size 3:          1,2 giây, 188 raw records
Cycle size 5:          0,8 giây, 616 raw records
Cycle size 8:          2,1 giây, 371 raw records
Detection total:       4,13 giây
Raw total:             1.175 records
Merged total:          45 clusters
```

FF:

```text
N_raw_cycles:      1.175
N_unique_sets:       491
N_merged_clusters:    45
FF_enumeration:     2,393075
FF_fragmentation:  10,911111
FF_total:          26,111111
```

Các con số này là kết quả của một lần chạy thực tế trên Neo4j Aura theo config hiện tại. Khi báo cáo benchmark nên chạy lặp lại nhiều lần, nêu rõ warm/cold cache và báo cáo median hoặc phân bố runtime thay vì xem một lần chạy là kết luận cuối cùng.

## 13. Artifact đầu ra

```text
data/cycledetection/cypher_v02/raw_candidates_optimized.jsonl
data/cycledetection/cypher_v02/merged_candidates_optimized.jsonl
data/cycledetection/cypher_v02/summary_optimized.json
data/cycledetection/cypher_v02/ff_optimized.json
```

## 14. Chế độ tương thích cũ

Có thể chạy trực tiếp trên transaction nodes bằng:

```bash
--graph-mode transactions
```

Chế độ này chỉ phục vụ đối chiếu với implementation cũ. Nó có các rủi ro:

- tổ hợp transaction path;
- nhiều `EXISTS` subquery;
- enrichment và sort muộn;
- cycle size 5 hoặc 8 chạy rất lâu;
- có thể vượt memory limit.

Không dùng chế độ này làm cấu hình benchmark tối ưu chính.

## 15. Ranh giới giữa detection, FF và evaluation

Ba bước phải tách biệt:

```text
Detection:
  topology + business attributes -> predictions

FF:
  predictions -> fragmentation metrics

Evaluation:
  frozen predictions + ground truth -> TP, FP, FN, Precision, Recall, F1
```

Không được đưa ground truth ngược trở lại detection hoặc FF. Đây là điều kiện để kết quả benchmark có giá trị khoa học và có thể tái lập.
