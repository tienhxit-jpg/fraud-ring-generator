# **PHẦN I - BÀI BÁO v12**

## **1\. Trạng thái 11 mâu thuẫn của v11**

**Đã sửa 10/11. Đây là vòng sửa sạch nhất từ trước tới nay.**

| **#**  | **Vấn đề v11**                                                         | **Trạng thái v12**                                                                    |
| ------ | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| B1     | Nửa sau Mục 4.1 còn số liệu v10 (\|V\|=42, c=1,02, 18 đỉnh nền, 4,31%) | Đã viết lại hoàn toàn theo c_bg, 26 đỉnh nền, 0,00002–0,014%                          |
| B2     | Bảng 5 gán trần Recall cho Cypher Optimized vốn có N_raw = 0           | Đã bỏ dòng Cypher Optimized; hai dòng còn lại đều là Cypher Pattern                   |
| B3     | Mục 4.4 và Hạn chế 2 còn quy lỗi cho heap 1 GiB                        | Đã sửa: "run chính (heap 8 GiB, timeout 120 giây), không phải cấu hình 1 GiB lịch sử" |
| B4     | Tóm tắt trích 13.439 → 1 cụm mà Mục 4.3 đã loại bỏ                     | Đã thay bằng 1.689 → 129 ở cả Tóm tắt, Mục 4.3 và Mục 4.4                             |
| B5     | Đoạn "Hệ quả trực tiếp… tức mọi mạng giao dịch thực tế"                | Đã xóa                                                                                |
| B6.1   | Tiêu đề Bảng 2 ghi "đồ thị đầy đủ"                                     | Đã đổi thành "đồ thị nền"                                                             |
| B6.2   | Mục 3.1 nói amount đã được sửa, 4.5 nói chưa                           | Đã sửa thành "mức rò rỉ còn lại sau hiệu chỉnh được đánh giá tại Mục 4.5"             |
| B6.3   | 4.5 nói chưa audit D₁–D₃ trong khi Bảng 6 đã có                        | Đã sửa thành "minh họa amount trên cả năm tập"                                        |
| B6.4   | "cả hai tập" không xác định                                            | Đã đổi thành "ở D₄ và D₅"                                                             |
| B6.6/7 | Hệ số phân mảnh số ít; từ khoá cũ                                      | Đã đổi thành FF_enum và FF_merge ở cả hai chỗ                                         |
| B6.8   | Tiêu đề "4. Kết quả" sai cấp heading                                   | Đã sửa về Heading 1                                                                   |
| B6.9   | Bảng 3 thiếu dòng D₄ với min_pair = 3                                  | Chưa làm, nhưng đã ghi nhận công khai là hạn chế cần bổ sung                          |
| B6.10  | Khẳng định GDS SCC phục hồi 5/5, 45/45, 10/10 không có bảng chống lưng | Đã hạ xuống mức cấu trúc SCC và nói rõ không có bảng P/R cho D₁–D₃                    |
| B5\*   | Hạn chế 3 phủ định đóng góp về rò rỉ tiền xử lý                        | CHƯA GIẢI QUYẾT - xem mục 3 dưới đây                                                  |

Phát hiện AUC amount đã được nâng lên đúng vị trí: đứng đầu danh sách đóng góp, đứng đầu Tóm tắt, và là "Kết quả thứ nhất" trong Kết luận, kèm câu kết luận thẳng thắn rằng D₂ và D₃ không đủ tư cách làm benchmark. Đây là quyết định biên tập đúng.

## **2\. Lỗi chặn còn lại: đóng góp số 1 không có phần phân tích trong Kết quả**

Phát hiện AUC amount nay xuất hiện ở Tóm tắt, Đóng góp và Kết luận. Nhưng Mục 4.5 - nơi duy nhất được phép trình bày nó - vẫn giữ nguyên đoạn văn của v11 và chỉ phân tích D₄–D₅. Ba dòng D₁, D₂, D₃ nằm trong Bảng 6 mà không có một câu nào diễn giải.

Cụ thể, những điều sau đây hiện không được nói ở bất kỳ đâu trong thân bài:

- Trung vị số tiền giao dịch nền của D₂ và D₃ là 0,07, trong khi trung vị giao dịch gian lận là 151.246 và 139.440 - chênh sáu bậc độ lớn. Đây mới là cơ chế của AUC ≈ 1, và nó là dấu hiệu của một lỗi trong bộ sinh chứ không phải một lựa chọn thiết kế: số tiền giao dịch nền gần bằng không là bất thường.
- D₁ có AUC = 0,7939 - cũng rò rỉ đáng kể, không được nhắc tới lần nào.
- Quan hệ giữa hai kênh rò rỉ. Cạnh nền có ~1 giao dịch còn cạnh ring có 7–17 giao dịch, nên min_pair ≥ 3 là bộ phân loại ring/nền hoàn hảo. Cùng lúc, số tiền của ring lớn hơn nền sáu bậc. Hai kênh không độc lập về nguyên nhân: cả hai đều bắt nguồn từ việc bộ sinh D₁–D₃ đặt ring vào một chế độ tham số hoàn toàn tách rời nền. Bài hiện gọi chúng là "cơ chế tách biệt", đúng ở mức kênh quan sát nhưng bỏ lỡ nguyên nhân chung - vốn là phát biểu mạnh hơn.

**Một reviewer sẽ đọc thấy đóng góp số 1 được tuyên bố ba lần nhưng chỉ được chứng minh bằng hai ô trong một bảng. Cần khoảng một trang bổ sung vào Mục 4.5. Đây là việc viết, không phải việc chạy lại thí nghiệm.**

## **3\. Hạn chế thứ ba vẫn đang phủ định đóng góp số 2**

Hạn chế 3 nay viết: hash SHA-256 của snapshot dùng cho Mục 4.5 đã được lưu, "nhưng việc đối chiếu dấu vân tay đó với snapshot dùng cho các bảng cấu trúc và tiền xử lý (Mục 4.1, 4.2) chưa hoàn tất, nên kết quả cấu trúc trên ba tập này chỉ dùng ở mức xác nhận quy trình."

Mục 4.2 chính là nơi trình bày rò rỉ min_pair trên D₂ và D₃ - tức đóng góp số 2, và là "Kết quả thứ hai" trong Kết luận. Bài đang tuyên bố một đóng góp rồi ở phần Hạn chế nói rằng số liệu sinh ra nó chỉ dùng để xác nhận quy trình.

**Cách xử lý rẻ nhất: tính SHA-256 của cùng ba file CSV đã dùng cho Mục 4.5 và kiểm tra xem đó có phải file đã dùng cho Mục 4.1–4.2 không. Nếu trùng - nhiều khả năng là trùng, vì cùng một thư mục dữ liệu - thì xóa hẳn mệnh đề này và ghi bảng hash vào phụ lục. Nếu không trùng thì phải chạy lại 4.1–4.2 trên snapshot đã có hash. Ước lượng: dưới hai giờ ở kịch bản thứ nhất.**

## **4\. Các điểm còn lại**

| **#** | **Vị trí** | **Nhận xét**                                                                                                                                                                                                                                                            |
| ----- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Bảng 3     | Vẫn thiếu dòng D₄ với min_pair = 3. Bài đã tự nêu là hạn chế, nhưng đây là một truy vấn đếm duy nhất. Reviewer sẽ hỏi vì sao ghi nhận thay vì chạy. Nên chạy.                                                                                                           |
| 2     | Mục 2      | Vẫn không có bằng chứng khảo sát cho khoảng trống nghiên cứu. Chấp nhận được ở hội thảo trong nước; không chấp nhận được ở tạp chí Scopus.                                                                                                                              |
| 3     | Toàn bài   | Vẫn chưa có mục công khai mã và dữ liệu. Bài khuyến nghị người khác báo cáo đầy đủ để tái lập được, nhưng bản thân chưa cung cấp repo, DOI hay lệnh chạy.                                                                                                               |
| 4     | Mục 3.5    | "File cấu hình bộ sinh hiện có khai báo seed 42, nhưng chưa đủ bằng chứng gắn seed đó với mọi snapshot" - trung thực, nhưng có nghĩa là toàn bộ thí nghiệm chưa tái lập được. Cần sinh lại ít nhất một tập với seed xác định để chứng minh quy trình tái lập hoạt động. |
| 5     | Bảng 6     | AUC ghi tới 6 chữ số thập phân (0,999999) trong khi các cột khác ghi 4 chữ số (0,5499). Nên thống nhất, và với AUC ≈ 1 thì nên ghi kèm số mẫu.                                                                                                                          |
| 6     | Bảng 5     | Chỉ còn hai dòng và cả hai đều là Cypher Pattern. Với quy mô đó, có thể gộp vào Mục 4.4 dưới dạng văn xuôi thay vì giữ một bảng riêng.                                                                                                                                  |