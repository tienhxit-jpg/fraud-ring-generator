# Cycle detection benchmark v02

## Scripts

```text
src/cycle_detection/v02/cypher_cycle_detection_v02.py
src/cycle_detection/v02/gds_cycle_detection_v02.py
src/cycle_detection/v02/hybrid_networkx_cycle_detection_v02.py
src/cycle_detection/v02/calculate_ff.py
```

## GDS SCC v02 label-blind

GDS v02 project toàn bộ cặp tài khoản, chạy SCC, lọc theo kích thước component và enrich bằng số giao dịch, tổng tiền, density. Script không có evidence projection, không chấm điểm từ nhãn đáp án và ghi toàn bộ SCC candidate ra JSONL.

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/gds_cycle_detection_v02.py \
  --limit 0 \
  --min-component-size 3 \
  --max-component-size 12 \
  --json-out data/cycledetection/gds_v02/summary.json \
  --jsonl-out data/cycledetection/gds_v02/candidates.jsonl
```

Dry-run:

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/gds_cycle_detection_v02.py --dry-run
```

Database phải đăng ký procedure `gds.graph.project.cypher`. Aura config hiện tại trả về Graph Analytics versionless nhưng chưa có procedure này, nên cần cài/bật GDS tương ứng hoặc chuyển sang Neo4j instance có GDS plugin trước khi chạy thật.

## Hybrid NetworkX v02 label-blind

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/hybrid_networkx_cycle_detection_v02.py \
  --cycle-sizes 3,5,8 \
  --limit 0 \
  --json-out data/cycledetection/hybrid_v02/summary.json \
  --raw-jsonl-out data/cycledetection/hybrid_v02/raw_candidates.jsonl \
  --merged-jsonl-out data/cycledetection/hybrid_v02/merged_candidates.jsonl
```

Phiên bản này:

- load logical edges đã aggregate trực tiếp từ Neo4j;
- không đọc answer-key properties;
- chỉ enumerate cycle size được chỉ định;
- giới hạn component bằng SCC size;
- cache group metrics;
- áp dụng `--limit` sau overlap merge;
- tự tạo output directories;
- ghi raw và merged JSONL riêng.

`--limit 0` có nghĩa là trả về toàn bộ merged candidates. Raw cycle records vẫn được ghi để tính FF bằng `calculate_ff.py`.


Script này dành cho benchmark Pure Cypher và không đọc các thuộc tính đáp án. Truy vấn chỉ sử dụng:

- topology `Account -> SENT -> Transaction -> RECEIVED_BY -> Account`;
- `amount_usd`/`amount`;
- `timestamp`;
- `Account.kyc_risk_score`;
- số lượng giao dịch nội bộ và tổng tiền.

Script không có:

```text
is_fraud
fraud_ring_member
fraud_ring_id
mode anchored
```

## Kích thước chu trình

Mặc định chạy các kích thước:

```text
3, 5, 8
```

Có thể thay đổi:

```bash
--cycle-sizes 3,5,8
```

Mỗi kích thước được chạy bằng một truy vấn cố định riêng để tránh việc `LIMIT` của chu trình 8 chiếm hết kết quả chu trình 3 hoặc 5.

`--limit 0` đã được hỗ trợ và có nghĩa là **bỏ hẳn `LIMIT $limit` khỏi từng truy vấn**, tức chạy không giới hạn số kết quả cho mỗi cycle size. Nó không bỏ các business filter và không có nghĩa là tìm mọi độ dài chu trình ngoài danh sách `--cycle-sizes`.

Ví dụ chạy toàn bộ candidate của các kích thước 3, 5 và 8:

```bash
--cycle-sizes 3,5,8 --limit 0
```

## Lọc theo nghiệp vụ

Các filter đều không dùng nhãn đáp án:

```bash
--min-pair-transactions 2
--min-pair-amount 1000
--min-internal-transactions 3
--min-total-amount 5000
```

`min-pair-*` được áp dụng trên từng cặp tài khoản trước khi candidate được giữ lại. `min-internal-*` được áp dụng trên toàn participant set sau khi thu thập các transaction nội bộ.

Không nên đặt ngưỡng chỉ để ép kết quả giống ground truth. Ngưỡng phải được cố định trước khi đánh giá hoặc được chọn từ quy tắc nghiệp vụ công khai.

## Raw và merged output

Script luôn tách hai loại kết quả:

```text
data/cycledetection/cypher_v02/raw_candidates.jsonl
 data/cycledetection/cypher_v02/merged_candidates.jsonl
```

- `raw_candidates.jsonl`: từng chu trình được Cypher phát hiện.
- `merged_candidates.jsonl`: các chu trình giao nhau được gộp bằng Union-Find.

Summary có cả:

```text
raw_result_count
merged_result_count
results_by_cycle_size
elapsed_ms
```

## Chạy dry-run

Không cần kết nối Neo4j:

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/cypher_cycle_detection_v02.py \
  --dry-run \
  --cycle-sizes 3,5,8
```

## Pure Cypher baseline không tối ưu

Script baseline giữ nguyên transaction-path expansion để làm mốc so sánh:

```text
src/cycle_detection/v02/cypher_cycle_detection_unoptimized.py
```

Chạy cycle 3, 5 và 8:

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/cypher_cycle_detection_unoptimized.py \
  --cycle-sizes 3,5,8 \
  --query-timeout 1800 \
  --cycle8-timeout 60 \
  --heartbeat-seconds 30 \
  --output-dir data/cycledetection/cypher_unoptimized
```

Baseline cố ý không dùng:

- `TRANSFER_AGG`;
- aggregate account-pair;
- canonicalization;
- `DISTINCT` participant set;
- `ORDER BY`;
- `LIMIT`;
- business-edge filter;
- ground-truth properties.

Mỗi dòng JSONL là một transaction path thô, do đó cùng một account cycle có thể xuất hiện nhiều lần theo rotation và tổ hợp Transaction node. Không dùng trực tiếp số dòng này làm số ring; cần aggregation/evaluation riêng.

Timeout mặc định:

```text
cycle 3: 900 giây
cycle 5: 900 giây khi chạy chung; có thể chạy riêng với 1800 giây
cycle 8: 60 giây
```

Kết quả đã chạy:

```text
data/cycledetection/cypher_unoptimized/summary_complete.json
data/cycledetection/cypher_unoptimized/cycle_size_3_raw.jsonl
data/cycledetection/cypher_unoptimized/cycle_size_8_raw.jsonl
data/cycledetection/cypher_unoptimized_cycle5_complete/cycle_size_5_raw.jsonl
```

Kết quả thực tế trên graph hiện tại:

| Cycle size | Trạng thái | Raw rows | Runtime |
|---:|---|---:|---:|
| 3 | completed | 111.411 | 6,54 giây |
| 5 | completed | 34.635.375 | 1.632,6 giây, khoảng 27,2 phút |
| 8 | skipped | 0 | 5,13 giây |

Cycle 8 bị Neo4j dừng vì transaction memory đạt giới hạn 716,8 MiB. Đây là trạng thái skip được ghi vào summary, không phải kết quả detection rỗng.


Lần chạy đầu tiên cần tạo lại một cạnh logic `TRANSFER_AGG` cho mỗi cặp tài khoản. Đây là bước Pure Cypher, không đọc nhãn đáp án:

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/cypher_cycle_detection_v02.py \
  --prepare-aggregates \
  --graph-mode aggregate \
  --dataset-dir data/synthetic/v03 \
  --cycle-sizes 3,5,8 \
  --limit 0 \
  --min-pair-transactions 3 \
  --progress-interval 30 \
  --raw-jsonl-out data/cycledetection/cypher_v02/raw_candidates_optimized.jsonl \
  --merged-jsonl-out data/cycledetection/cypher_v02/merged_candidates_optimized.jsonl \
  --json-out data/cycledetection/cypher_v02/summary_optimized.json
```

Các lần sau có thể bỏ `--prepare-aggregates` nếu dữ liệu giao dịch không đổi. Nếu dữ liệu được import lại, phải dựng lại aggregate graph.

Detector áp dụng filter `transaction_count` ngay sau từng `MATCH`, canonicalize đỉnh bắt đầu và không `ORDER BY` trong discovery. Chế độ cũ trên transaction node vẫn còn qua `--graph-mode transactions` để đối chiếu, nhưng không được khuyến nghị cho cycle 5/8.

## Tính FF bằng script riêng

```bash
./venv/Scripts/python.exe src/cycle_detection/v02/calculate_ff.py \
  --raw-jsonl data/cycledetection/cypher_v02/raw_candidates_optimized.jsonl \
  --json-out data/cycledetection/cypher_v02/ff_optimized.json
```

Script FF không kết nối Neo4j và không đọc ground truth. Nó báo cáo `raw_cycles`, `unique_sets`, `merged_clusters`, `ff_enumeration`, `ff_fragmentation` và `ff_total` cho toàn bộ kết quả và từng cycle size.

Ground-truth evaluation phải chạy sau đó bằng script riêng, không được đưa nhãn đáp án vào detector.

## Theo dõi truy vấn chạy lâu

Mặc định script ghi log tiến độ ra `stderr`, nên JSON summary trên `stdout` không bị trộn. Log gồm:

```text
[12:10:01] detection started (...)
[12:10:01] cycle_size=3 started (limit=all)
[12:10:08] cycle_size=3 finished (7.2s, rows=...)
[12:10:08] cycle_size=5 started (limit=all)
[12:10:38] cycle_size=5 still running (30s)
```

Heartbeat mặc định mỗi 30 giây. Có thể đổi hoặc tắt:

```bash
--progress-interval 60
--progress-interval 0
--quiet
```

## Kiểm thử

Test riêng:

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -p 'test_cypher_cycle_detection_v02.py' -q
```

Toàn bộ test hiện có:

```bash
./venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -q
```
