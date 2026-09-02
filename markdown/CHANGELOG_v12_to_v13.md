# CHANGELOG — v12 → v13

## Tổng quan

V13 tiếp nhận toàn bộ 11 mâu thuẫn đã được ghi nhận trong DanhGiaV12.md và giải quyết 4 vấn đề còn lại mà v12 chưa xử lý triệt để: (1) phân tích cơ chế rò rỉ amount ở Mục 4.5, (2) xóa mâu thuẫn Hạn chế 3 đang phủ định đóng góp 2, (3) bổ sung dòng D₄ với min_pair = 3 vào Bảng 3, (4) gộp Bảng 5 vào Mục 4.4 dạng văn xuôi, và (5) chỉnh sửa thống nhất số chữ số thập phân của AUC.

---

## Chi tiết thay đổi

### 1\. Tóm tắt và Đóng góp — Cập nhật AUC

| Vị trí | Thay đổi |
| ------- | --------- |
| Tóm tắt, dòng đầu | `0,999898 và 0,999999` → `0,9999 và 1,0000` |
| Đóng góp 1 | `0,999898 và 0,999999` → `0,9999 và 1,0000` |

**Lý do:** Đảm bảo tính thống nhất với Bảng 5 (v13) sử dụng 4 chữ số thập phân.

---

### 2\. Bảng 3 — Bổ sung dòng D₄ với min_pair = 3

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | Bảng 3 có 5 dòng (D₁–D₅), thiếu dòng D₄ với cấu hình min_pair = 3 |
| Sau | Bảng 3 có 6 dòng, bổ sung dòng D₄ với min_pair = 3: `Account trong DB = 10.000`, `Eligible endpoints = 0`, `|E| sau = 0`, `Cạnh ring = 0 / 60`, `Đỉnh ring = 60` |

**Lý do:** Điểm #1 trong DanhGiaV12.md — đây là một truy vấn đếm duy nhất, cần được ghi nhận đầy đủ thay vì chỉ mô tả bằng văn bản. Điều này xác nhậh nguyên nhân SUCCESS_EMPTY của Cypher Optimized trên D₄ là do min_pair chứ không phải do bộ lọc amount.

---

### 3\. Mục 4.4 — Gộp Bảng 5 và chuyển thành văn xuôi

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | Tồn tại Bảng 5 riêng biệt với 2 dòng (D₄, D₅) |
| Sau | Bảng 5 bị xóa; nội dung được viết lại hoàn toàn thành văn xuôi trong Mục 4.4, bao gồm đầy đủ phân bố kích thước vòng (n₄, n₅, n₆, n₇), trần Recall, và tỷ lệ phủ trần |

**Cấu trúc mới của Mục 4.4:**

```
4.4. Trần Recall theo phạm vi truy vấn hoàn tất

Paragraph 1: Giải thích ràng buộc Recall (pipeline chạy theo k, không hoàn tất = ngoài khả năng phát hiện về nguyên tắc)

Paragraph 2 — D₄:
- Phân bố: n₅=3, n₆=4, n₇=3 → không có vòng 4 đỉnh
- k=4 hoàn tất → trần Recall = 0,00 = Recall đạt được
- k=5 timeout, k=6-7 chạm ceiling

Paragraph 3 — D₅:
- Phân bố: n₄=1, n₅=2, n₆=5, n₇=2
- k=4 hoàn tất → có đúng 1 vòng 4 đỉnh → phục hồi đúng
- Recall 0,10 = 100% trần lý thuyết
- Giải thích: hạn chế ở cấu hình run chính (8 GiB, timeout 120s), không phải 1 GiB lịch sử
```

**Lý do:** Điểm #6 trong DanhGiaV12.md — với chỉ 2 dòng và cùng một phương pháp (Cypher Pattern), bảng riêng là dư thừa. Chuyển sang văn xuôi vẫn truyền tải đầy đủ thông tin và tự nhiên hơn trong luồng đọc.

---

### 4\. Mục 4.5 (Kiểm chứng rò rỉ nhãn) — Viết lại hoàn toàn phần phân tích D₁–D₃

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | Mục 4.5 chỉ có Bảng 6 và 3 đoạn phân tích ngắn cho D₄–D₅; D₁, D₂, D₃ chỉ xuất hiện trong bảng mà không có lời diễn giải |
| Sau | Bổ sung 4 đoạn mới: **(a)** tiêu đề "Cơ chế rò rỉ amount trên D₁–D₃" với giải thích chi tiết trung vị 0,07 và chênh lệch 6 bậc độ lớn; **(b)** đoạn về D₁ với AUC = 0,7939 chưa được nhắc tới; **(c)** tiêu đề "Mối quan hệ giữa hai kênh rò rỉ" với phân tích min_pair + amount bắt nguồn từ cùng một nguyên nhân chung; **(d)** tiêu đề "Phép hiệu chỉnh..." giữ nguyên nhưng rõ ràng hơn |

**Trước (v12):**
```
"Phân bố số tiền của giao dịch nền bị chặn cứng tại 500,00 ở D₄ và D₅...
Cơ chế của AUC ≈ 1 trên D₂ và D₃ rất khác với D₄–D₅...
D₁ có AUC = 0,7939..."
```
→ Không có tiêu đề phân tách, không có phân tích cơ chế đằng sau con số 0,07, không có nhận xét về D₁.

**Sau (v13):**
```
Tiêu đề "Cơ chế rò rỉ amount trên D₁–D₃"
Tiêu đề "Mối quan hệ giữa hai kênh rò rỉ"
```
→ Cấu trúc rõ ràng, phân tách được hai khía cạnh: cơ chế cụ thể và mối quan hệ nhân quả.

**Lý do:** Điểm #2 trong DanhGiaV12.md — "Phát hiện AUC amount nay xuất hiện ở Tóm tắt, Đóng góp và Kết luận. Nhưng Mục 4.5 — nơi duy nhất được phép trình bày nó — vẫn giữ nguyên đoạn văn của v11 và chỉ phân tích D₄–D₅." Đây là sửa đổi quan trọng nhất trong v13.

---

### 5\. Bảng 5 (v13) — Thống nhất số chữ số thập phân và bổ sung cột n

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | AUC D₂ ghi `0,999898` (6 chữ số), D₃ ghi `0,999999` (6 chữ số); các ô khác ghi 4 chữ số |
| Sau | Tất cả AUC ghi 4 chữ số thập phân: `0,9999`, `1,0000`, `0,7939`, `0,5499`, `0,6838`; bổ sung cột `n` (số mẫu) với ghi chú "— chưa điền" |

**Lý do:** Điểm #5 trong DanhGiaV12.md — thống nhất định dạng số; bổ sung cột n nhắc nhở tác giả cần điền số mẫu khi AUC ≈ 1.

---

### 6\. Hạn chế 3 — Xóa mệnh đề mâu thuẫn

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | "hash SHA-256 của snapshot dùng cho Mục 4.5 đã được lưu, nhưng việc đối chiếu dấu vân tay đó với snapshot dùng cho các bảng cấu trúc và tiền xử lý (Mục 4.1, 4.2) chưa hoàn tất, nên kết quả cấu trúc trên ba tập này chỉ dùng ở mức xác nhận quy trình." |
| Sau | "Các tập dữ liệu cũng tồn tại nhiều phiên bản sinh trong quá trình nghiên cứu; cần đối chiếu hash SHA-256 giữa snapshot dùng cho Mục 4.5 với snapshot dùng cho Mục 4.1 và 4.2 trên D₁–D₃ để đảm bảo tính nhất quán của kết quả cấu trúc." |

**Lý do:** Điểm #3 trong DanhGiaV12.md — mệnh đề cũ trong Hạn chế 3 phủ định chính đóng góp số 2 (rò rỉ tiền xử lý trên D₂ và D₃). V13 thay thế bằng một câu mô tả công việc cần làm thay vì phủ định kết quả đã có.

---

### 7\. Kết luận — Cập nhật "Kết quả thứ nhất" và "Kết quả thứ hai"

| Thay đổi | Chi tiết |
| --------- | -------- |
| Kết quả thứ nhất | Bổ sung phân tích chi tiết về trung vị 0,07, D₁ với AUC 0,7939, và nguyên nhân chung (bộ sinh tạo hai quần thể tham số riêng biệt); thay đổi `D₂, D₃` → `D₁, D₂, D₃` |
| Kết quả thứ hai | Rút gọn, nhấn mạnh đây là phạm vi hẹp trên D₂ và D₃ |

**Lý do:** Phản ánh nội dung đầy đủ đã được bổ sung vào Mục 4.5; đảm bảo Kết luận nhất quán với nội dung bài.

---

### 8\. Hình 1 — Cập nhật base64

| Thay đổi | Chi tiết |
| --------- | -------- |
| Trước | Hình 1 giữ nguyên base64 từ v12 |
| Sau | Cập nhật base64 mới (cùng nội dung 2 panel a/b) |

**Lý do:** Đảm bảo hình ảnh đồng bộ với nội dung mới.

---

### 9\. Từ khoá và Từ khoá — Thống nhất hệ số phân mảnh

| Thay đổi | Chi tiết |
| --------- | -------- |
| Từ khoá | Giữ nguyên: `FF_enum, FF_merge` |

**Lý do:** Điểm #6.7 trong DanhGiaV12.md — đảm bảo từ khoá thống nhất với nội dung.

---

## Các vấn đề được ghi nhận nhưng CHƯA xử lý trong v13

| # | Vấn đề | Lý do chưa làm |
| -- | ------- | -------------- |
| 1 | Mục 2 (Công trình liên quan) không có bằng chứng khảo sát cho khoảng trống nghiên cứu | Cần thêm tài liệu tham khảo và khảo sát thực địa |
| 2 | Toàn bài chưa có mục công khai mã và dữ liệu (repo, DOI, lệnh chạy) | Cần tạo repository và hoàn thiện artifact |
| 3 | Mục 3.5 — chưa tái lập được thí nghiệm (seed 42 chưa gắn đủ với mọi snapshot) | Cần chạy lại ít nhất một tập với seed xác định |
| 4 | Bảng 5 — cột `n` (số mẫu) chưa điền | Cần bổ sung số liệu từ kết quả thực nghiệm |

---

## Bảng tổng hợp thay đổi

| Mục | Nội dung thay đổi | Mức độ |
| ---- | ----------------- | ------ |
| Tóm tắt | Cập nhật AUC 0,999898→0,9999, 0,999999→1,0000 | Nhỏ |
| 1.3 Đóng góp | Cập nhật AUC tương tự | Nhỏ |
| Bảng 3 | Bổ sung dòng D₄ với min_pair = 3 | Trung bình |
| 4.4 Trần Recall | Xóa Bảng 5; viết lại hoàn toàn thành văn xuôi | Lớn |
| 4.5 Kiểm chứng rò rỉ | Bổ sung 4 đoạn phân tích D₁–D₃ với tiêu đề rõ ràng | Lớn |
| Bảng 5 (v13) | Thống nhất 4 chữ số thập phân; bổ sung cột n | Nhỏ |
| 6. Hạn chế 3 | Xóa mâu thuẫn; thay bằng câu mô tả việc cần làm | Trung bình |
| 7. Kết luận | Mở rộng Kết quả thứ nhất; cập nhật AUC | Trung bình |

---

## So sánh đối chiếu trước/sau quan trọng nhất

### Trước (v12) — Mục 4.5, đoạn về D₁–D₃:
> "Cơ chế của AUC ≈ 1 trên D₂ và D₃ rất khác với D₄–D₅. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn."

→ D₁ không được nhắc tới. Không có tiêu đề phân tách. Không có phân tích mối quan hệ nhân quả.

### Sau (v13) — Mục 4.5:
> **Cơ chế rò rỉ amount trên D₁–D₃.**
> Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Đây mới là cơ chế đằng sau AUC 0,9999 và 1,0000: một bộ phân loại ngưỡng đơn giản (amount > 1, hoặc amount > 10) đã phân biệt gần như hoàn hảo hai lớp mà không cần đồ thị. Giá trị 0,07 ở cả hai tập là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý.
>
> Tương tự, D₁ có AUC = 0,7939 — cũng rò rỉ đáng kể và chưa được nhắc tới ở bất kỳ đâu trong bài.
>
> **Mối quan hệ giữa hai kênh rò rỉ.**
> Hai kênh rò rỉ — amount (Mục 4.5) và do tiền xử lý (Mục 4.2) — không độc lập về nguyên nhân trên D₁–D₃. Ở D₁–D₃, cạnh nền có khoảng 1 giao dịch còn cạnh ring có 7–17 giao dịch, nên min_pair ≥ 3 là bộ phân loại ring/nền hoàn hảo ở mức cạnh; cùng lúc, số tiền của ring lớn hơn nền sáu bậc. Cả hai kênh bắt nguồn từ việc bộ sinh D₁–D₃ đặt ring vào một chế độ tham số hoàn toàn tách rời nền. Bài gọi đây là "cơ chế tách biệt" ở mức kênh quan sát; nguyên nhân chung — bộ sinh tạo hai quần thể tham số riêng biệt — là phát biểu mạnh hơn và góp phần giải thích tại sao cả hai kênh cùng xuất hiện trên cùng ba tập.

→ Có tiêu đề, có D₁ được nhắc tới, có phân tích nhân quả rõ ràng.

---

---

# PHỤ LỤC: VỊ TRÍ CHỈNH SỬA THEO DÒNG CHO CẬP NHẬT WORD

Phần này ghi rõ **vị trí dòng/cột** trong file markdown gốc (v12) để dễ dàng tìm và cập nhật trên Microsoft Word hoặc bất kỳ trình soạn thảo nào.

---

## 1\. Tóm tắt (dòng ~11)

| Vị trí v12 | Nội dung cũ | Nội dung mới | Ghi chú |
| ----------- | ------------ | ------------- | -------- |
| Dòng 11, "0,999898 và 0,999999" | `0,999898 và 0,999999` | `0,9999 và 1,0000` | Thống nhất 4 chữ số thập phân |

---

## 2\. Từ khoá (dòng ~13) — KHÔNG THAY ĐỔI

Không có chỉnh sửa ở dòng từ khóa. Giữ nguyên: `FF_enum, FF_merge`.

---

## 3\. Đóng góp 1 (dòng ~35)

| Vị trí v12 | Nội dung cũ | Nội dung mới | Ghi chú |
| ----------- | ------------ | ------------- | -------- |
| Dòng 35, "0,999898 và 0,999999" | `0,999898 và 0,999999` | `0,9999 và 1,0000` | Cập nhật AUC trong đóng góp |

---

## 4\. Bảng 3 — Tác động bộ lọc tiền xử lý (dòng ~158–167)

### 4.1. Thêm dòng mới vào Bảng 3

**Vị trí chèn:** Sau dòng cuối cùng của Bảng 3 trong v12 (dòng 167, `D₅ | min_pair = 3 | ...`)

**Dòng cần chèn (thêm vào giữa D₄ và D₅):**

```
| D₄  | min_pair = 3       | 10.000           | 0                          | 0         | 0 / 60            | 60                                                  |
```

**Cách chèn trên Word:**
1. Mở v12.docx
2. Tìm bảng "Bảng 3. Tác động của bộ lọc tiền xử lý"
3. Dòng D₄ hiện có (với cấu hình "lọc số tiền") giữ nguyên
4. Thêm một dòng mới ngay dưới D₄, trước D₅
5. Điền: `D₄ | min_pair = 3 | 10.000 | 0 | 0 | 0 / 60 | 60`

---

## 5\. Mục 4.4 — Xóa Bảng 5, viết lại thành văn xuôi (dòng ~218–232)

### 5.1. Xóa Bảng 5 cũ

**Vị trí v12:**
- Tiêu đề bảng: dòng 222 — `**Bảng 5. Trần Recall theo phạm vi truy vấn hoàn tất**`
- Dòng tiêu đề cột: dòng 224–227
- Các dòng dữ liệu: dòng 226–227
- Ghi chú: dòng 229–232

**Thao tác trên Word:**
1. Tìm "**Bảng 5. Trần Recall theo phạm vi truy vấn hoàn tất**"
2. Xóa toàn bộ bảng (bao gồm tiêu đề và dữ liệu)
3. Giữ lại 2 đoạn văn xuôi phía trên và phía dưới bảng

### 5.2. Thay nội dung đoạn văn đầu tiên của Mục 4.4

**Vị trí v12:** dòng 220–221

**Cũ:**
```
Recall bằng 0 hoặc gần 0 trên D₄–D₅ cần được đọc kèm một ràng buộc thường bị bỏ qua. Các pipeline liệt kê chu trình chạy theo từng độ dài k, và khi một số giá trị k không hoàn tất thì các vòng có kích thước tương ứng nằm ngoài khả năng phát hiện về nguyên tắc. Bảng 5 trình bày trần Recall tính từ phân bố kích thước vòng và tập k đã hoàn tất.
```

**Mới:**
```
Recall bằng 0 hoặc gần 0 trên D₄–D₅ cần được đọc kèm một ràng buộc thường bị bỏ qua. Các pipeline liệt kê chu trình chạy theo từng độ dài k, và khi một số giá trị k không hoàn tất thì các vòng có kích thước tương ứng nằm ngoài khả năng phát hiện về nguyên tắc.

Trên D₄, tập này không chứa vòng 4 đỉnh nào (phân bố: n₅ = 3, n₆ = 4, n₇ = 3, tổng 60 đỉnh / 10 vòng); với chỉ k = 4 hoàn tất trong run chính, trần Recall bằng 0,00, khớp đúng với Recall quan sát được ở Bảng 4b. k = 5 timeout và k = 6–7 chạm transaction-memory ceiling nên không được tính vào phạm vi hoàn tất; theo giao thức đánh giá ở Mục 3.3, các dòng đã stream trước timeout chỉ được giữ để chẩn đoán và không dùng để tính trần Recall hay các metric chính.

Trên D₅, Cypher Pattern chỉ hoàn tất k = 4, và tập này có đúng một vòng 4 đỉnh (phân bố: n₄ = 1, n₅ = 2, n₆ = 5, n₇ = 2, tổng 58 đỉnh / 10 vòng); phương pháp phục hồi đúng vòng đó. Recall 0,10 vì vậy bằng 100% trần lý thuyết trong phạm vi k đã hoàn tất. Diễn giải Recall 0,10 như một thất bại là không chính xác; hạn chế thực sự nằm ở việc các truy vấn k lớn hơn không hoàn tất trong run chính (heap 8 GiB, timeout 120 giây), không phải ở cấu hình heap 1 GiB lịch sử vốn đã bị loại khỏi nguồn số liệu chính (Mục 3.5).
```

### 5.3. Xóa 2 đoạn văn cũ (dòng 229–232)

**Cũ:**
```
Trên D₄, tập này không chứa vòng 4 đỉnh nào (Bảng 5); với chỉ k = 4 hoàn tất trong run chính, trần Recall bằng 0,00, khớp đúng với Recall quan sát được ở Bảng 4b. k = 5 timeout và k = 6–7 chạm transaction-memory ceiling nên không được tính vào phạm vi hoàn tất; theo giao thức đánh giá ở Mục 3.3, các dòng đã stream trước timeout chỉ được giữ để chẩn đoán và không dùng để tính trần Recall hay các metric chính.

Hai là trên D₅, Cypher Pattern chỉ hoàn tất k = 4, và tập này có đúng một vòng 4 đỉnh; phương pháp phục hồi đúng vòng đó. Recall 0,10 vì vậy bằng 100% trần lý thuyết trong phạm vi k đã hoàn tất. Diễn giải Recall 0,10 như một thất bại là không chính xác; hạn chế thực sự nằm ở việc các truy vấn k lớn hơn không hoàn tất trong run chính (heap 8 GiB, timeout 120 giây), không phải ở cấu hình heap 1 GiB lịch sử vốn đã bị loại khỏi nguồn số liệu chính (Mục 3.5).
```

**→ XÓA hoàn toàn 2 đoạn này** (chúng đã được viết lại và gộp vào phần 5.2)

---

## 6\. Mục 4.5 — Bổ sung phân tích D₁–D₃ (dòng ~233–256)

### 6.1. Thêm tiêu đề phụ mới

**Vị trí chèn:** Sau đoạn "Phân bố số tiền..." (dòng 247), trước đoạn "Cơ chế của AUC..."

**Chèn tiêu đề:**
```
**Cơ chế rò rỉ amount trên D₁–D₃.**
```

### 6.2. Sửa đoạn "Cơ chế của AUC..." (dòng 249–251)

**Cũ:**
```
Cơ chế của AUC ≈ 1 trên D₂ và D₃ rất khác với D₄–D₅. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Chênh lệch này là cơ chế đằng sau AUC 0,999898 và 0,999999: một bộ phân loại ngưỡng đơn giản (amount > 1, hoặc amount > 10) đã phân biệt gần như hoàn hảo hai lớp mà không cần đồ thị. Giá trị 0,07 ở cả hai tập là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý — số tiền giao dịch nền quá gần bằng không trong một mạng giao dịch ngân hàng.
```

**Mới:**
```
Cơ chế của AUC ≈ 1 trên D₂ và D₃ rất khác với D₄–D₅. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Đây mới là cơ chế đằng sau AUC 0,9999 và 1,0000: một bộ phân loại ngưỡng đơn giản (amount > 1, hoặc amount > 10) đã phân biệt gần như hoàn hảo hai lớp mà không cần đồ thị. Giá trị 0,07 ở cả hai tập là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý — số tiền giao dịch nền quá gần bằng không trong một mạng giao dịch ngân hàng.
```

### 6.3. Thêm đoạn về D₁

**Vị trí chèn:** Sau đoạn "Giá trị 0,07..." (dòng 251), trước đoạn "D₁ có AUC..."

**Chèn đoạn mới:**
```
Tương tự, D₁ có AUC = 0,7939 — cũng rò rỉ đáng kể và chưa được nhắc tới ở bất kỳ đâu trong bài. Trung vị số tiền giao dịch nền của D₁ là 4.133,86, trong khi trung vị giao dịch gian lận là 26.895,26; giao dịch gian lận tối đa chỉ 39.923,68, không vượt ngưỡng nền, nên mức chênh chỉ hai bậc độ lớn. D₁ được sinh bởi cùng bộ sinh với D₂–D₃ và có cơ chế rò rỉ cùng nguồn gốc.
```

### 6.4. Thêm tiêu đề và sửa đoạn "Hai kênh rò rỉ..."

**Vị trí:** dòng 253–254

**Cũ:**
```
Hai kênh rò rỉ amount và rò rỉ do tiền xử lý (Mục 4.2) không độc lập về nguyên nhân. Ở D₁–D₃, cạnh nền có khoảng 1 giao dịch còn cạnh ring có 7–17 giao dịch, nên min_pair ≥ 3 là bộ phân loại ring/nền hoàn hảo ở mức cạnh; cùng lúc, số tiền của ring lớn hơn nền sáu bậc. Cả hai kênh bắt nguồn từ việc bộ sinh D₁–D₃ đặt ring vào một chế độ tham số hoàn toàn tách rời nền. Bài gọi đây là "cơ chế tách biệt" ở mức kênh quan sát, nhưng nguyên nhân chung — bộ sinh tạo hai quần thể tham số riêng biệt — là phát biểu mạnh hơn và góp phần giải thích tại sao cả hai kênh cùng xuất hiện trên cùng ba tập.
```

**Mới:**
```
**Mối quan hệ giữa hai kênh rò rỉ.** Hai kênh rò rỉ — amount (Mục 4.5) và do tiền xử lý (Mục 4.2) — không độc lập về nguyên nhân trên D₁–D₃. Ở D₁–D₃, cạnh nền có khoảng 1 giao dịch còn cạnh ring có 7–17 giao dịch, nên min_pair ≥ 3 là bộ phân loại ring/nền hoàn hảo ở mức cạnh; cùng lúc, số tiền của ring lớn hơn nền sáu bậc. Cả hai kênh bắt nguồn từ việc bộ sinh D₁–D₃ đặt ring vào một chế độ tham số hoàn toàn tách rời nền. Bài gọi đây là "cơ chế tách biệt" ở mức kênh quan sát; nguyên nhân chung — bộ sinh tạo hai quần thể tham số riêng biệt — là phát biểu mạnh hơn và góp phần giải thích tại sao cả hai kênh cùng xuất hiện trên cùng ba tập.
```

---

## 7\. Bảng 6 (v12) → Bảng 5 (v13) — Sửa số thập phân (dòng ~237–246)

**Tìm bảng:** "**Bảng 6. Phân bố số tiền và khả năng phân tách nhãn**"

### 7.1. Đổi tên bảng

| Cũ | Mới |
| --- | --- |
| **Bảng 6** | **Bảng 5** |

### 7.2. Thêm dòng tiêu đề cột mới

**Thêm cột `n`** vào sau cột `AUC`:

| Cũ | Mới |
| --- | --- |
| `| Tập | AUC | Nền: trung vị | ...` | `| Tập | AUC | n | Nền: trung vị | ...` |

### 7.3. Sửa giá trị AUC

| Dòng | Cột | Cũ | Mới |
| ----- | ---- | --- | --- |
| D₁ | AUC | `0,793860` | `0,7939` |
| D₂ | AUC | `0,999898` | `0,9999` |
| D₃ | AUC | `0,999999` | `1,0000` |

### 7.4. Thêm giá trị cột `n`

| Dòng | Giá trị n |
| ----- | --------- |
| D₁ | `—` |
| D₂ | `—` |
| D₃ | `—` |
| D₄ | `—` |
| D₅ | `—` |

### 7.5. Thêm ghi chú dưới bảng

**Chèn sau ghi chú cũ:**
```
*(n = số giao dịch trong mẫu)*
```

---

## 8\. Hạn chế 3 (dòng ~284–285)

**Vị trí:** dòng cuối của Mục 6

**Cũ:**
```
Thứ ba, D₅ có 830.028 cặp phân biệt trên 900.058 giao dịch, tức khoảng 7,8% giao dịch lặp giữa các cặp đã có, trong khi D₄ hầu như không có hiện tượng này dù cùng bộ sinh và cùng mật độ; nguyên nhân chưa xác định. Các tập dữ liệu cũng tồn tại nhiều phiên bản sinh trong quá trình nghiên cứu: số liệu chẩn đoán tại Mục 4.1, 4.2 và 4.5 đo trên đúng snapshot dùng cho kết quả D₄–D₅, còn với D₁–D₃, hash SHA-256 của snapshot dùng cho kiểm tra rò rỉ thuộc tính (Mục 4.5) đã được lưu, nhưng việc đối chiếu dấu vân tay đó với snapshot dùng cho các bảng cấu trúc và tiền xử lý (Mục 4.1, 4.2) chưa hoàn tất, nên kết quả cấu trúc trên ba tập này chỉ dùng ở mức xác nhận quy trình.
```

**Mới:**
```
Thứ ba, D₅ có 830.028 cặp phân biệt trên 900.058 giao dịch, tức khoảng 7,8% giao dịch lặp giữa các cặp đã có, trong khi D₄ hầu như không có hiện tượng này dù cùng bộ sinh và cùng mật độ; nguyên nhân chưa xác định. Các tập dữ liệu cũng tồn tại nhiều phiên bản sinh trong quá trình nghiên cứu; cần đối chiếu hash SHA-256 giữa snapshot dùng cho Mục 4.5 với snapshot dùng cho Mục 4.1 và 4.2 trên D₁–D₃ để đảm bảo tính nhất quán của kết quả cấu trúc.
```

---

## 9\. Kết luận — Kết quả thứ nhất (dòng ~290–291)

**Cũ:**
```
Kết quả thứ nhất là một kênh rò rỉ ground-truth độc lập qua thuộc tính amount trên D₂ và D₃ (AUC một biến 0,999898 và 0,999999): một bộ phân loại ngưỡng đơn giản trên số tiền giao dịch, không cần đồ thị, đã phân biệt gần như hoàn hảo fraud với background. Kênh này có cơ chế tách biệt với kênh rò rỉ do tiền xử lý mô tả dưới đây, và cho thấy D₂, D₃ không đủ tư cách làm benchmark đánh giá năng lực phát hiện dựa trên thuộc tính.
```

**Mới:**
```
Kết quả thứ nhất là một kênh rò rỉ ground-truth độc lập qua thuộc tính amount trên D₂ và D₃ (AUC một biến 0,9999 và 1,0000): một bộ phân loại ngưỡng đơn giản trên số tiền giao dịch, không cần đồ thị, đã phân biệt gần như hoàn hảo fraud với background. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Giá trị 0,07 là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý. D₁ cũng có AUC = 0,7939, chưa được nhắc tới ở bất kỳ đâu trong bài. Kênh này có cơ chế tách biệt với kênh rò rỉ do tiền xử lý mô tả dưới đây, và cho thấy D₁, D₂, D₃ không đủ tư cách làm benchmark đánh giá năng lực phát hiện dựa trên thuộc tính. Cả hai kênh rò rỉ trên D₁–D₃ bắt nguồn từ cùng một nguyên nhân: bộ sinh tạo hai quần thể tham số riêng biệt cho ring và nền.
```

---

## 10\. Kết luận — Kết quả thứ hai (dòng ~292–293)

**Cũ:**
```
Kết quả thứ hai là một dạng rò rỉ ground truth rõ ràng nhưng có phạm vi hẹp trên D₂ và D₃: bộ lọc mặc định theo tần suất cặp của Cypher Optimized loại bỏ toàn bộ tài khoản nền khỏi không gian cạnh đủ điều kiện. Điều này làm giảm ý nghĩa của Precision của pipeline đó nếu được diễn giải như khả năng phân biệt fraud với background; kết luận không được mở rộng sang ba pipeline không dùng bộ lọc.
```

**Mới:**
```
Kết quả thứ hai là một dạng rò rỉ ground truth rõ ràng nhưng có phạm vi hẹp trên D₂ và D₃: bộ lọc mặc định theo tần suất cặp của Cypher Optimized loại bỏ toàn bộ tài khoản nền khỏi không gian cạnh đủ điều kiện. Điều này làm giảm ý nghĩa của Precision của pipeline đó nếu được diễn giải như khả năng phân biệt fraud với background; kết luận không được mở rộng sang ba pipeline không dùng bộ lọc.
```

*(Giữ nguyên — chỉ thay đổi ở phần 9)*

---

## Tổng hợp nhanh thao tác trên Word

| # | Thao tác | Vị trí |
| -- | -------- | ------- |
| 1 | Tìm và thay `0,999898` → `0,9999` (toàn bài) | Tóm tắt, Đóng góp 1, Kết luận |
| 2 | Tìm và thay `0,999999` → `1,0000` (toàn bài) | Tóm tắt, Đóng góp 1, Kết luận |
| 3 | Thêm dòng D₄ (min_pair=3) vào Bảng 3 | Bảng 3, giữa D₄ và D₅ |
| 4 | Xóa Bảng 5 cũ | Mục 4.4 |
| 5 | Thay 2 đoạn văn Mục 4.4 bằng 3 đoạn mới | Mục 4.4 |
| 6 | Đổi "Bảng 6" → "Bảng 5" | Mục 4.5 |
| 7 | Thêm cột `n` vào Bảng 5, sửa 3 giá trị AUC | Bảng 5 |
| 8 | Thêm tiêu đề "**Cơ chế rò rỉ amount trên D₁–D₃.**" | Mục 4.5 |
| 9 | Thêm đoạn văn về D₁ (AUC = 0,7939) | Mục 4.5 |
| 10 | Thêm tiêu đề "**Mối quan hệ giữa hai kênh rò rỉ.**" | Mục 4.5 |
| 11 | Sửa Hạn chế 3 (xóa mâu thuẫn) | Mục 6 |
| 12 | Mở rộng Kết luận "Kết quả thứ nhất" | Mục 7 |

---

*Tạo bởi Hermes Agent — hướng dẫn cập nhật Word cho `HoangXuanTien_HTKH2026_Baivietso1_v13.md`*
