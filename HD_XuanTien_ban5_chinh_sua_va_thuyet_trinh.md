**HƯỚNG DẪN CHỈNH SỬA VÀ CHUẨN BỊ THUYẾT TRÌNH**

# **0\. Hai khái niệm cần nắm**

Tài liệu này dùng hai thuật ngữ xuyên suốt. Chúng là **hai cách khác nhau để trả lời câu hỏi "dự báo này có đúng không?"** bài hiện tại đang không nói rõ nó dùng cách nào.

**Ví dụ cụ thể.** Giả sử có một vòng gian lận thật gồm 8 tài khoản: g = {a, b, c, d, e, f, g, h}. Truy vấn Cypher trong bài chỉ tìm chu trình 3-5 đỉnh, nên nó trả về một chu trình con: p = {a, b, c}.

| **Ngữ nghĩa**                | **Quy tắc**                               | **p = {a,b,c} so với g = {a…h}** | **Hệ quả**                                                         |
| ---------------------------- | ----------------------------------------- | -------------------------------- | ------------------------------------------------------------------ |
| Khớp chính xác (exact match) | p đúng khi p BẰNG một vòng thật           | {a,b,c} ≠ {a…h} ⇒ SAI (FP)       | Là thứ Mục 3.4.1 của em ĐANG MÔ TẢ ("TP = \|G ∩ P\|")              |
| Khớp bao hàm (subset match)  | p đúng khi p NẰM TRỌN trong một vòng thật | {a,b,c} ⊂ {a…h} ⇒ ĐÚNG (TP)      | Hợp lý về nghiệp vụ: điều tra viên lần theo {a,b,c} vẫn ra cả vòng |

**Vì sao nội dung này quan trọng:** nếu là khớp chính xác thì Cypher không thể đạt Precision = 1,00 trên D₂ (mọi chu trình con của vòng 8 đỉnh đều thành FP). Nếu là khớp bao hàm thì đạt được - nhưng khi đó Mục 3.4.1 đang mô tả sai code. **Phép kiểm ở Mục 3.1 sẽ trả lời. Trước khi có kết quả đó, KHÔNG được khẳng định bài mình dùng cách nào.**

**Một chỗ cần quyết định**

Bảng trên nói KHI NÀO một dự báo được tính là đúng. Nó chưa nói TP đếm cái gì.

Dưới khớp bao hàm có ít nhất hai cách, và chúng cho kết quả khác hẳn nhau:

(i) TP = số VÒNG THẬT được phủ -> Precision = 45 / (45 + số dự báo xấu)

(ii) TP = số DỰ BÁO nằm trọn trong vòng -> Precision = số dự báo tốt / tổng dự báo

Cách (i) trộn đơn vị: tử số đếm vòng, mẫu số cộng thêm dự báo. Cách (ii) nhất quán về đơn vị nhưng lại cho Recall khác. Bài của em chưa nói dùng cách nào.

Cần mở code ra, xem nó làm gì, rồi viết đúng cái đó vào Mục 3.4.1 kèm công thức.

# **1\. Điều quan trọng nhất - đổi trọng tâm bài**

**Bài của hiện tại có HAI đóng góp, và chúng không bền như nhau.**

|                                                  | **Hệ số phân mảnh (FF)**                                                                                             | **Điểm mù Giant SCC**                                          |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Bản chất                                         | Một tỉ số đo trên dữ liệu tổng hợp                                                                                   | Hệ quả của một định lý (Karp, 1990)                            |
| Treo trên                                        | Ngữ nghĩa khớp · định nghĩa N_unique · tham số mật độ vòng em tự chọn · cách sinh giao dịch nền (mà bài không mô tả) | Chỉ hai điều: bậc trung bình > 1, và bộ lọc kích thước tồn tại |
| Nếu một giả định sai                             | 348,42 và 2.747,07 đổ theo                                                                                           | Không đổ                                                       |
| Kết quả D₃ của GDS (TP=0, FP=0, FN=10, Recall=0) | \-                                                                                                                   | Đúng dưới MỌI ngữ nghĩa khớp - vì GDS không trả về gì cả       |
| Độ bền trước phản biện                           | Yếu                                                                                                                  | Rất mạnh                                                       |

**Chỉ đạo chiến lược**

Khi thuyết trình, DẪN BẰNG GIANT SCC, không dẫn bằng FF.

Kết quả D₃ của GDS - không trả về dự báo nào, Recall = 0 - miễn nhiễm với toàn bộ vấn đề nêu ở Mục 2. GDS không trả về gì thì TP = 0, FP = 0, FN = 10 dù khớp chính xác hay khớp bao hàm, dù N_unique định nghĩa ra sao, dù mật độ vòng bằng bao nhiêu. Đó là con số an toàn nhất trong cả bài.

FF thì ngược lại: treo trên bốn giả định, ít nhất hai trong số đó đang lỗi. Đưa FF lên đầu là mời người ta tấn công đúng chỗ yếu nhất.

**Không có nghĩa là bỏ FF.** FF vẫn là đóng góp, vẫn trong bài, vẫn có một slide - nhưng là đóng góp _thứ hai_, trình bày sau, ngôn ngữ dè dặt hơn.

## **1.1. Hiện tại bài đang có KẾT QUẢ ÂM - và phải biết điều đó**

Nếu dẫn bằng Giant SCC thì thông điệp trung tâm của bài là: **cả ba phương pháp đều hỏng trên topology thực tế**. Đó là một kết quả âm - không phải "chúng tôi tìm ra công cụ tốt nhất", mà "chúng tôi chỉ ra rằng công cụ đang được khuyến nghị rộng rãi có một điểm mù mang tính cấu trúc".

**Kết quả âm là kết quả tốt, nhưng phải đóng khung khác hẳn một bài benchmark:**

|                           | **Bài benchmark (bài em đang viết)** | **Bài kết quả âm (bài em nên viết)**                           |
| ------------------------- | ------------------------------------ | -------------------------------------------------------------- |
| Câu hỏi                   | Phương pháp nào tốt nhất?            | Vì sao cả lớp phương pháp này thất bại, và thất bại ở đâu?     |
| Đóng góp                  | Một bảng xếp hạng                    | Một cơ chế: bộ lọc kích thước + siêu thành phần                |
| Giá trị của việc thất bại | Là hạn chế phải xin lỗi              | LÀ kết quả - nó tiết kiệm công cho người sau                   |
| Dữ liệu tổng hợp          | Là điểm yếu chí mạng                 | Chấp nhận được: cơ chế suy ra từ định lý, dữ liệu chỉ minh hoạ |
| Người nghe nhớ gì         | "GDS nhanh hơn 9 lần"                | "Đừng lọc SCC theo kích thước trên đồ thị giao dịch"           |

**Chú ý dòng thứ tư.** Đóng khung theo kết quả âm **vô hiệu hoá** chính điểm yếu lớn nhất của bài. Nếu em nói "GDS tốt nhất, đo trên dữ liệu tổng hợp" thì phản biện đập ngay: dữ liệu giả thì xếp hạng vô nghĩa. Nhưng nếu em nói "gom SCC kèm lọc kích thước có điểm mù, và đây là **lý do cấu trúc** - bậc trung bình > 1 thì siêu thành phần gần như chắc chắn hình thành" - thì dữ liệu tổng hợp chỉ còn là **minh hoạ** cho một lập luận vốn không dựa vào dữ liệu. Không đập được.

## **1.2. Tiêu đề đang hứa sai thứ**

"So sánh các phương pháp nhận biết vòng tròn gian lận dựa trên đồ thị" hứa một bài benchmark. Nhưng ở Mục 4.1 câu 5, thầy bảo em trả lời rằng đóng góp là **điểm mù**, còn phần so sánh chỉ là phương tiện. Hai thứ đó không khớp nhau - và người phản biện đọc tiêu đề trước tiên.

**Cân nhắc đổi thành một tiêu đề nói đúng thứ em tìm ra, ví dụ:**

\* "Diem mu cua phuong phap gom thanh phan lien thong manh trong phat hien vong tron gian lan: khi vong nam trong Sieu thanh phan"

\* "Vi sao loc thanh phan theo kich thuoc that bai tren do thi giao dich: phan tich ba phuong phap phat hien fraud ring"

**Đây là việc em bàn với thầy, không tự quyết.** Nhưng em phải hiểu vì sao nó quan trọng: tiêu đề quyết định người nghe đến với kỳ vọng gì. Đến để xem bảng xếp hạng mà nghe kết quả âm thì họ thất vọng. Đến để xem một điểm mù thì họ nhớ bài của em.

# **2\. Lỗi CHẮC CHẮN - suy ra từ chính bản thảo**

**Mười sáu lỗi, xếp theo mức nguy hiểm khi thuyết trình.** Tất cả đều **tự kiểm được bằng cách đặt hai trang cạnh nhau** - không cần chạy gì. Em hãy thử tự tìm trước khi đọc lời giải.

## **2.1. NẶNG NHẤT - bài không mô tả cách sinh 94% dữ liệu của mình**

**Mục 3.3.1 "Quy trình tạo dữ liệu" chỉ có MỘT đoạn, và nó chỉ nói về vòng gian lận.** Nhưng D₂ có 50.572 giao dịch, trong đó chỉ 3.072 là gian lận. Vậy **47.500 giao dịch nền - 94% dữ liệu - được sinh ra thế nào?** Bài không nói ở đâu cả.

**Hệ quả không hề nhỏ:**

- Lập luận Giant SCC (Mục 4.2) viện dẫn định lý Karp, mà Karp phát biểu cho đồ thị NGẪU NHIÊN. Không nói nền sinh thế nào thì trích dẫn bị hở. **Đây là lỗ hổng nhỏ, không phải mối đe doạ** - siêu thành phần vẫn hình thành trong đồ thị giao dịch thật (vốn scale-free chứ không ngẫu nhiên đều); hiện tượng thì bền, chỉ có trích dẫn là hẹp. Sửa bằng một câu: nếu nền sinh ngẫu nhiên đều thì Karp áp dụng trực tiếp; nếu không thì viện dẫn thêm một nguồn về siêu thành phần trong mạng scale-free.
- Không ai tái lập được thực nghiệm của em. Đây là bài về dữ liệu tổng hợp - mô tả bộ sinh CHÍNH LÀ phương pháp nghiên cứu.
- Mục 2.2 nói mỗi cạnh mang thuộc tính số tiền và dấu thời gian. Mục 3.3.1 không sinh hai thuộc tính đó. Chúng ở đâu ra?

**Việc phải làm:** viết lại Mục 3.3.1 thành một mục đầy đủ, có bảng tham số cho từng tập (số tài khoản thường, cách sinh cạnh nền, bậc trung bình mục tiêu, số chu kỳ lặp mỗi vòng, kích thước vòng, seed).

## **2.2. NẶNG - Mục 3.2 dùng thuộc tính mà bộ sinh không tạo ra**

**Mục 3.2, Phương pháp 2:** "…rồi chấm điểm rủi ro theo **tỉ lệ giao dịch nghi ngờ, điểm KYC** và kích thước vòng."

**Nhưng nhãn duy nhất mà Mục 3.3.1 tạo ra là:** "Toàn bộ giao dịch sinh trong vòng đều mang nhãn gian lận." Không có điểm KYC. Không có "giao dịch nghi ngờ" nào khác.

**Vậy điểm KYC ở đâu ra?**

**Hai khả năng, và em phải mở code để biết là cái nào:**

- **(a) Bộ sinh có tạo, nhưng Mục 3.3.1 không mô tả.** Khi đó đây là phần mở rộng của lỗi 2.1 - bổ sung mô tả là xong.
- **(b) "Tỉ lệ giao dịch nghi ngờ" chính là tỉ lệ giao dịch mang nhãn gian lận.** Khi đó **Phương pháp 2 dùng ground truth để chấm điểm cho chính bài toán nó phải giải** - đó là rò rỉ, và mọi con số của Hybrid không dùng được.

**Đây là câu thầy hỏi em đầu tiên khi gặp. Trả lời được ngay hôm nay.**

## **2.3. NẶNG - FF ở dạng hiện tại không tính được khi vận hành**

Mục 2.6.2 và 3.4.3 định nghĩa N_unique = **"số vòng tròn độc nhất trong KẾT QUẢ đó"**. Nghe như một phép khử trùng lặp thuần tuý, không cần biết đáp án. Nhưng em hãy tự đo - một dòng, trên kết quả thô của chính em:

\>>> len(set(preds)) # preds = ket qua tho cua Cypher tren D2

**Nếu ra 45 thì thầy sai, bỏ qua mục này.** Thầy dự đoán nó ra **hàng nghìn**, và đây là lý do: trong một vòng 8 đỉnh dày đặc, Cypher tìm được rất nhiều chu trình con 3, 4, 5 đỉnh - mỗi chu trình con là một tập người tham gia **khác nhau**. Khử trùng lặp chỉ gộp các bản ghi có _cùng_ tập người tham gia; nó không có cách nào biết {a,b,c} và {d,e,f} cùng thuộc một vòng 8 đỉnh.

**Thầy có chạy thử trên một bản tái hiện D₂ và được N_unique ≈ 1.700 thay vì 45.** Nhưng **đừng chép con số đó vào bài**: nó phụ thuộc phân bố kích thước vòng, mà Bảng 2 của em chỉ ghi "3, 5, 8 đỉnh" chứ **không nói mỗi cỡ có bao nhiêu vòng** - thầy phải tự giả định. Con số của em có thể khác. Cái _không_ đổi là bậc độ lớn: hàng nghìn, không phải 45.

**Suy ra: muốn gom hàng nghìn tập con về đúng 45, bắt buộc phải biết mỗi tập con thuộc vòng nào - tức phải có ground truth.** Mà dữ liệu ngân hàng thật **không có ground truth**. Nghĩa là FF ở dạng hiện tại **chỉ chạy được trong phòng thí nghiệm** - trong khi Mục 2.6.2 lại biện minh cho nó bằng "khối lượng công việc của điều tra viên", một lý do vận hành.

**Hai cách xử lý - chọn một, đừng để lửng:**

- **(a) Thừa nhận thẳng.** Thêm vào Mục 2.6.2: "FF là chỉ số đánh giá (benchmark), yêu cầu có ground truth; nó không thay thế chỉ số giám sát vận hành." Rẻ, trung thực, làm em an toàn khi bị hỏi.
- **(b) Định nghĩa lại mẫu số - thầy khuyến nghị.** Thay vì đếm "số vòng thật được phủ", hãy **gộp các dự báo giao nhau lại thành cụm**, rồi đếm số cụm. Cụ thể: nếu {a,b,c} và {c,d,e} có chung phần tử c thì gộp thành một cụm {a,b,c,d,e}; lặp cho tới khi không gộp được nữa; N_unique = số cụm còn lại. Kỹ thuật chuẩn cho việc này gọi là **union-find** (hay disjoint-set) - Python có sẵn trong networkx.utils.UnionFind, khoảng 20 dòng là xong. Đại lượng này **tính được mà không cần nhãn**, và xấp xỉ đúng "số cấu trúc gian lận riêng biệt mà điều tra viên phải xem". Nếu làm được, FF mới xứng là "tiêu chí đề xuất mới" như Mục 2.6.2 tuyên bố.

## **2.4. NẶNG - Mục 3.4.2 phá huỷ lý do tồn tại của FF**

**Mục 3.4.1 (đúng):** "các bản ghi trùng lặp… đã bị gộp trước bước này và _không làm tăng FP_; khối lượng bản ghi dư thừa được đo riêng bằng Hệ số phân mảnh".

**Mục 3.4.2 (sai):** "…thì k−1 bản ghi thừa sẽ tính vào FP, _trực tiếp làm giảm Precision và F1_".

**Hai câu cách nhau MƯỜI DÒNG và nói ngược nhau.** Hệ quả: nếu 3.4.2 đúng thì F1 đã thấy phân mảnh rồi ⇒ FF thừa ⇒ bài không còn đóng góp. **Toàn bộ giá trị của bài nằm ở chỗ 3.4.1 đúng và 3.4.2 sai.** Xoá câu ở 3.4.2, thay bằng:

"Ba do do duoc tinh theo cong thuc chuan tu TP, FP, FN neu tai Muc 3.4.1."

## **2.5. NẶNG - Khuyến nghị Mục 5.1 tự bác bỏ phát hiện hay nhất của bài**

**Bullet 2:** "Đối với mạng lưới từ vài nghìn tới **100.000** tài khoản: GDS SCC là lựa chọn _bắt buộc_".

**Bullet 3:** "> 100.000 tài khoản: kết quả trên **D₃** cho thấy không phương pháp nào dùng được".

**D₃ = đúng 100.000 tài khoản.** Nó nằm trong dải bullet 2, đồng thời là bằng chứng cho bullet 3. Ở đó GDS Recall = 0.

**Vấn đề sâu hơn.** Khuyến nghị GDS dựa hoàn toàn vào D₂. Nhưng chính em viết ở Mục 5.2 rằng D₂ "thuận lợi bất thường cho phương pháp gom SCC" vì 225 tài khoản gian lận **không có cạnh nào** nối với 5.000 tài khoản thường. Và cũng chính em viết ở Mục 4.2: "Vì tài khoản gian lận thực tế luôn giao dịch với tài khoản thường, **tình huống D₃ mới là điển hình**".

**Trong cùng một bài, cách nhau hai trang: em tuyên bố D₂ không đại diện, rồi khuyến nghị vận hành dựa trên D₂.**

**Sửa: xoá bullet 2, thay bằng:**

"Nghien cuu chua xac dinh duoc nguong chuyen doi. D2 va D3 khac nhau DONG THOI o hai yeu to - quy mo (5.225 so voi 100.000 tai khoan) VA topology (vong gian lan biet lap so voi nam trong Sieu thanh phan) - nen thiet ke hien tai khong tach duoc anh huong cua hai yeu to. Tren D2, GDS SCC vuot troi; nhung loi the do den tu viec vong gian lan khong noi voi phan con lai cua do thi, dieu khong xay ra trong du lieu that."

## **2.6. Bảng 3, dòng D₁, Cypher Recall = 1,00 là bất khả thi**

**Thầy muốn em tự chứng minh lại, vì nó dạy đúng cách đọc bảng của chính mình.** Bảng 1: Cypher tìm chu trình độ dài k ∈ {3, 4, 5}. Bảng 2: D₁ có vòng cỡ **2 đến 6** đỉnh. Hỏi: truy vấn chỉ tìm chu trình 3-5 đỉnh, bắt vòng **2** tài khoản bằng cách nào?

**Không có cách nào - và đây là chỗ hai khái niệm ở Mục 0 giúp em.** Khớp chính xác: một tập 3 phần tử không thể _bằng_ một tập 2 phần tử. Khớp bao hàm: một tập 3 phần tử không thể _nằm trọn trong_ một tập 2 phần tử. **Cả hai đều không. Vòng cỡ 2 của D₁ là không thể phát hiện được về nguyên tắc.**

**⇒ Recall của Cypher trên D₁ ≤ 4/5 = 0,80. Bảng 3 ghi 1,00; Mục 4.1 còn ghi TP = 5, FP = 0, FN = 0.**

Cùng lập luận cho D₂ (vòng cỡ 8, Cypher tìm tới 5). Ở đó Cypher có thể "bắt" được vòng 8 - nhưng chỉ nếu harness khớp bao hàm, _và_ nhờ vòng dày (mật độ 0,91-1,00) nên chứa chu trình con 3-5. Nghĩa là **Recall của Cypher là hàm của mật độ vòng, không phải năng lực phương pháp** - ở mật độ thấp nó rớt ngay, đúng như D₁ cho thấy.

## **2.7. Mục 3.5 nói ba phương pháp dùng chung đồ thị - Mục 3.2 nói không phải**

**Mục 3.5:** "Ba phương pháp dùng chung: **cùng đồ thị nạp vào Neo4j**, cùng ground truth, và cùng bộ lọc nghiệp vụ".

**Mục 3.2, Phương pháp 2:** "Dùng Cypher **trích các cụm khả nghi**, nạp vào NetworkX…"

Nếu Hybrid chỉ nạp "cụm khả nghi" thì nó **không chạy trên cùng đồ thị** với hai phương pháp kia - và Mục 3.5 sai. Còn "khả nghi" định nghĩa thế nào thì bài không nói; nếu dựa trên nhãn thì lại là lỗi 2.2.

**Và chính con số của em chứng minh Mục 3.5 sai.** Số chu trình trong một đồ thị bùng nổ theo cấp số nhân với độ dài. Nền tài khoản thường của D₂ có ~5.000 đỉnh, ~47.500 cạnh, và **một siêu thành phần 5.000 đỉnh** (chính em đo được, Mục 4.2). Ước lượng số chu trình trong đó:

| **Độ dài** | **Kỳ vọng** | **Độ dài** | **Kỳ vọng** |
| ---------- | ----------- | ---------- | ----------- |
| 2          | 45          | 6          | 122.295     |
| 3          | 286         | 7          | 994.834     |
| 4          | 2.035       | 8          | 8.259.629   |
| 5          | 15.460      | Tổng 2-8   | 9.394.584   |

**Hybrid báo cáo liệt kê chu trình độ dài 2-8 và trả về 123.618 bản ghi trong 73,4 giây.** Ít hơn ước lượng **76 lần** - và nếu nó thật sự chạy trên đồ thị đầy đủ, riêng chu trình độ dài 8 đã 8,2 triệu, không thể xong trong 73 giây.

**⇒ Hybrid KHÔNG chạy trên đồ thị đầy đủ của D₂. Nó chạy trên đồ thị con "khả nghi" như Mục 3.2 nói, chứ không phải "cùng đồ thị" như Mục 3.5 và Mục 2.6 nói.**

**Ước lượng này giả định nền là đồ thị ngẫu nhiên đều - điều bài không nói (lỗi 2.1).** Nhưng chiều của lập luận thì bền: một siêu thành phần 5.000 đỉnh _theo định nghĩa_ chứa vô số chu trình, và số đó tăng khoảng 8 lần cho mỗi đơn vị độ dài. Không có cách nào để 123.618 là con số đúng trên đồ thị đầy đủ.

**Hai việc phải làm:** (1) Sửa Mục 3.5 và Mục 2.6 - nói đúng rằng Hybrid chạy trên đồ thị con, và định nghĩa "khả nghi" là gì. (2) **Bỏ so sánh thời gian Cypher-Hybrid** khỏi Mục 4.1 và Kết luận: so thời gian của một phương pháp quét toàn đồ thị với một phương pháp chạy trên đồ thị con đã lọc là vô nghĩa.

## **2.8. Tóm tắt quy sai nguyên nhân - và Mục 5.2 nói ngược lại**

**Tóm tắt:** "…không phân biệt được ba phương pháp **do được tính sau chuẩn hóa**".

**Mục 5.2:** "việc cả ba phương pháp đạt Precision = Recall = 1,0… là **hệ quả của thiết kế**".

**Hai nguyên nhân khác nhau cho cùng một hiện tượng, và Mục 5.2 mới đúng.** Chuẩn hoá giải thích vì sao **phân mảnh không hiện ra trong Precision** - tức nó là lý do cần có FF. Nó _không_ giải thích vì sao ba phương pháp **bằng nhau**; ba phương pháp bằng nhau vì dữ liệu tổng hợp không tạo ra FP cho bất kỳ phương pháp nào. Đó là hai chuyện khác nhau, và em đang trộn chúng ở câu thứ hai của Tóm tắt - câu phản biện đọc trước tiên.

## **2.9. Tóm tắt nói "ba tập dữ liệu" nhưng trên D₃ chúng KHÁC nhau**

"Thực nghiệm trên **ba tập dữ liệu** tổng hợp cho thấy Precision, Recall và F1-Score không phân biệt được ba phương pháp". Trên D₃: GDS Recall = 0, hai cái kia N/A - phân biệt rất rõ. Sửa thành **"trên D₁ và D₂"**.

## **2.10. Sáu phát biểu về không gian tìm kiếm, không cái nào khớp cái nào**

| **Phương pháp** | **Không gian tìm kiếm**            | **Nguồn trong bài** |
| --------------- | ---------------------------------- | ------------------- |
| Cypher          | độ dài 3-5                         | Bảng 1, Mục 3.2     |
| Hybrid          | tới max_cycle_length (mặc định 10) | Bảng 1              |
| Hybrid          | "mọi độ dài từ 2 đến 8"            | Mục 4.1             |
| GDS             | không giới hạn (từ 2 đỉnh)         | Bảng 1              |
| GDS             | kích thước 3-12                    | Mục 4.2             |
| "Bộ lọc chung"  | 3-8 đỉnh                           | Mục 3.5             |

**Mục 3.5 tuyên bố "cùng bộ lọc nghiệp vụ" 3-8, nhưng Bảng 1 nói Cypher 3-5 và Mục 4.2 nói GDS 3-12.** Khi em kết luận "Hybrid phân mảnh gấp 8 lần Cypher, vì Cypher chỉ tìm 3-5 còn Hybrid liệt kê 2-8" - em **đang tự nói ra rằng em đo khác biệt về không gian tìm kiếm, không phải về thuật toán**, mà không nhận ra hệ quả. Chốt một bộ lọc, áp cho cả ba, chạy lại.

## **2.11. NẶNG - "Hybrid phân mảnh gấp 8 lần Cypher" là một so sánh giả**

**Câu này đang nằm ở cả Mục 4.1, Mục 4.3 lẫn Kết luận, và em trình bày nó như một phát hiện. Nhưng hãy đọc lại chính lời giải thích của em:** "Hybrid phân mảnh gấp gần 8 lần Cypher, **vì Cypher chỉ liệt kê chu trình độ dài 3-5 còn Hybrid liệt kê mọi độ dài 2-8**".

**Em vừa tự nói ra rằng khác biệt đến từ DẢI ĐỘ DÀI, không phải từ thuật toán.** Cả hai phương pháp đều làm đúng một việc: liệt kê chu trình đơn. Cho Cypher tìm 2-8 thì nó cũng trả về xấp xỉ con số của Hybrid. Con số 8× đo "_anh hỏi bao nhiêu độ dài chu trình_", không đo "_thuật toán nào tốt hơn_".

**Hệ quả lớn hơn em nghĩ - nó gọn hoá cả bài.** Bài của em không có ba phương pháp. Nó có **HAI HỌ**:

- **Liệt kê chu trình** (Cypher và Hybrid - cùng bản chất, chỉ khác dải độ dài và nơi chạy) ⇒ phân mảnh, FF ≫ 1
- **Gom thành phần** (GDS) ⇒ mỗi đỉnh thuộc đúng một SCC ⇒ không thể phân mảnh, FF = 1 theo thiết kế

**Phát biểu đúng, gọn hơn và mạnh hơn:** "**liệt kê chu trình thì phân mảnh, gom thành phần thì không - và mức phân mảnh tỉ lệ với dải độ dài mà ta hỏi**". Câu đó không cần con số 8×, và nó đúng bất kể tham số.

**Việc phải làm:** bỏ câu "gấp 8 lần" khỏi Mục 4.1, Mục 4.3 và Kết luận. Thay bằng phát biểu hai họ ở trên. Nếu muốn giữ so sánh Cypher-Hybrid thì phải chạy lại cả hai trên **cùng dải độ dài** - khi đó FF của chúng sẽ gần bằng nhau, và đó mới là kết quả trung thực.

## **2.12. Mục 2.4.2 quy nguồn gốc phân mảnh cho một thuật toán bài không hề chạy**

**Mục 2.4.2 viết:** "thuật toán Johnson (Johnson, 1975), **nền tảng của hàm networkx.simple_cycles()**" - rồi quy hiện tượng phân mảnh cho nó.

**Nhưng tài liệu chính thức của NetworkX nói:**

"In the unbounded case, we use a nonrecursive, iterator/generator version of Johnson's algorithm. In the BOUNDED case, we use a version of the algorithm of Gupta and Suzumura."

**Bảng 1 và Mục 4.1 của em đều nói Hybrid chạy CÓ GIỚI HẠN độ dài (2-8; max_cycle_length = 10).** Có giới hạn ⇒ NetworkX **không chạy Johnson**, nó chạy Gupta-Suzumura. Bài đang quy nguồn gốc của phát hiện chính cho một thuật toán mà nó không thực thi.

**Ba việc:** (1) sửa Mục 2.4.2; (2) bổ sung Gupta & Suzumura vào TLTK - hiện không có; (3) kiểm lại Bảng 1: tham số thật của NetworkX tên là length_bound và mặc định là None (không giới hạn), không phải "max_cycle_length, mặc định 10". Nếu đó là tên tham số trong wrapper của em thì phải nói rõ.

**Điểm cộng:** Johnson (1975) và Tarjan (1972) em trích đúng cả năm lẫn nội dung. Chỉ chỗ ánh xạ sang NetworkX là sai.

## **2.13. Bảng 2 mâu thuẫn với Mục 3.3.1 về mật độ vòng**

Mục 3.3.1: mỗi vòng = 10-20 chu kỳ × 8-12 giao dịch ⇒ **80-240 giao dịch mỗi vòng**. Lấy máy tính chia thử:

| **Tập** | **Giao dịch gian lận** | **Số vòng** | **Thực tế mỗi vòng** | **Mục 3.3.1 quy định** |
| ------- | ---------------------- | ----------- | -------------------- | ---------------------- |
| D₁      | 23                     | 5           | 4,6                  | 80-240                 |
| D₂      | 3.072                  | 45          | 68,3                 | 80-240                 |
| D₃      | 49                     | 10          | 4,9                  | 80-240                 |

**D₁ và D₃ chỉ đủ cạnh cho ĐÚNG MỘT chu trình mỗi vòng, không lặp.** Ba tập được sinh bằng hai quy trình khác nhau, nhưng Mục 3.3.1 chỉ mô tả một.

**Hệ quả: FF = 348,42 và 2.747,07 là hàm của tham số "10-20 chu kỳ" mà em tự chọn, không phải đặc tính của Cypher hay NetworkX.** Bằng chứng nằm ngay trong bảng của em: trên D₁ (một chu trình/vòng) cả ba đều cho FF = 1,00. Nếu đặt 40 chu kỳ thay vì 20, FF tăng gấp đôi mà không phương pháp nào đổi.

## **2.14. Mục 2.4 hứa ba nhóm thuật toán, chỉ có hai**

"…thường vận dụng **ba nhóm thuật toán cốt lõi sau**:" rồi chỉ có 2.4.1 (Tarjan) và 2.4.2 (Johnson/DFS). **Thiếu hẳn 2.4.3.** Bổ sung nhóm thứ ba, hoặc sửa "ba" thành "hai". Người đọc thấy lỗi này trong 5 giây.

## **2.15. Mục 2.1 mang tên "Khái niệm vòng tròn gian lận" nhưng không có khái niệm nào**

Toàn mục chỉ có một câu về "mục đích thường gặp". Không định nghĩa, không trích dẫn. Định nghĩa thật lại nằm ở Mục 1.1. Chuyển nó lên đây kèm trích dẫn - Wells (2017) và FATF (2026) đang nằm không trong TLTK, dùng đúng chỗ này.

## **2.16. Năm tài liệu thừa, một tài liệu thiếu**

| **Loại**                             | **Tài liệu**                   | **Xử lý**                                                                    |
| ------------------------------------ | ------------------------------ | ---------------------------------------------------------------------------- |
| Có trong TLTK, KHÔNG trích trong bài | Akoglu và c.s. (2015)          | Trích ở Mục 2.2, hoặc xoá                                                    |
|                                      | Chandola và c.s. (2009)        | Trích ở Mục 2.2, hoặc xoá                                                    |
|                                      | Europol (2023)                 | Trích ở Mục 1.1 cùng ACFE/GAO, hoặc xoá                                      |
|                                      | FATF (2026)                    | Trích ở Mục 2.1 (ngưỡng báo cáo, xé nhỏ giao dịch) - chỗ đó đang trắng nguồn |
|                                      | Wells (2017)                   | Trích ở Mục 2.1, hoặc xoá                                                    |
| Trích trong bài, KHÔNG có trong TLTK | Zhang và c.s. (2025) - Mục 3.1 | BẮT BUỘC bổ sung. Nặng nhất nhóm này                                         |

**Năm tài liệu thừa là dấu hiệu TLTK được dựng trước khi viết.** Phản biện có kinh nghiệm nhận ra ngay.

## **2.17. Hai hình và bộ từ khoá**

**Hai hình vẽ tốt - rõ, đúng trọng tâm, Hình 1 truyền đạt phát hiện Giant SCC rất hiệu quả. Nhưng cả hai đều dính vấn đề đã nêu ở trên:**

- **Hình 1 ghi "Bộ lọc kích thước SCC: 3-12 đỉnh".** Tức hình đứng về phía Mục 4.2 và mâu thuẫn với Mục 3.5 ("3-8"). Đây là chỗ thứ ba trong bài nói khác nhau về cùng một bộ lọc (xem lỗi 2.10). Chốt một con số rồi sửa đồng loạt cả hình.
- **Hình 2 nhúng sẵn so sánh giả.** Hai cột Cypher (348,42) và Hybrid (2.747,07) đặt cạnh nhau mời người xem đọc đúng cái so sánh mà lỗi 2.11 nói là không hợp lệ. Chú thích "khối lượng hậu kiểm chênh tới 2.747 lần" cũng vậy. **Nếu em bỏ câu "gấp 8 lần" thì phải vẽ lại Hình 2**: gộp Cypher và Hybrid thành một nhóm "liệt kê chu trình", đối lập với GDS "gom thành phần". Hình mới vừa trung thực hơn vừa mạnh hơn - nó cho thấy khác biệt nằm giữa hai HỌ, không phải giữa ba công cụ.

**Từ khoá không chứa một chữ nào về hai đóng góp của bài.** Hiện tại: "đồ thị, gian lận tài chính, neo4j, phát hiện vòng tròn gian lận, phân tích mạng lưới" - toàn bộ đều chung chung. Không có **hệ số phân mảnh**, không có **thành phần liên thông mạnh**, không có **siêu thành phần**. Người tìm đúng chủ đề em nghiên cứu sẽ không tìm ra bài của em. Sửa mất 30 giây, và nó quyết định bài có được đọc hay không.

## **2.17. Lỗi nhỏ**

| **#** | **Vị trí**            | **Hiện trạng**                                                                                                      | **Sửa**                                                                                                                                                                                                                                                                                                                                                                                                             |
| ----- | --------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Bảng 3 - 3 nhãn hàng  | Precision / Recall / F1, mỗi cái có một dòng ghi "D₂(Large)"                                                        | "D₃ (Large)". (Dòng Runtime và FF đã ghi đúng D₃)                                                                                                                                                                                                                                                                                                                                                                   |
| 2     | Chú thích dưới Bảng 3 | "Ghi chú Bảng 2: …"                                                                                                 | "Ghi chú Bảng 3: …"                                                                                                                                                                                                                                                                                                                                                                                                 |
| 3     | Chú thích dưới Bảng 3 | "Cần phân biệt ba đại lượng…; bài dùng đại lượng thứ nhất" - không mạch lạc; FF có hai đại lượng chứ không phải một | Viết lại: nêu rõ tử số là gì, mẫu số là gì                                                                                                                                                                                                                                                                                                                                                                          |
| 4     | Mục 4.1, đoạn D₂      | Câu cụt: "…phân hóa rõ rệt. Mặc"                                                                                    | Viết trọn câu                                                                                                                                                                                                                                                                                                                                                                                                       |
| 5     | Mục 1.1               | ACFE (2026), "2.402 vụ / 143 quốc gia"                                                                              | Số này thuộc bản RTTN 2024. Sửa năm, hoặc cập nhật số nếu bản 2026 đã ra                                                                                                                                                                                                                                                                                                                                            |
| 6     | TLTK                  | Neo4j GDS Manual "v2026.06"                                                                                         | Xác minh phiên bản thật đang chạy. (NetworkX 3.6.1 thầy đã kiểm - đúng, giữ nguyên)                                                                                                                                                                                                                                                                                                                                 |
| 7     | Mục 2.6.2             | FF gọi là "tiêu chí đề xuất mới"                                                                                    | Vận hành AML đã có alert volume và alert-to-case ratio. Thêm 2-3 câu định vị FF là biến thể theo đồ thị của mối quan tâm đó, kèm trích dẫn                                                                                                                                                                                                                                                                          |
| 8     | Cấp tiêu đề           | Mục 2.3, 2.5, 2.6.1, 3.2, 3.5, 3.6 dùng đoạn in đậm; các mục khác dùng heading thật                                 | Thống nhất - nếu không, mục lục kỷ yếu sẽ vỡ                                                                                                                                                                                                                                                                                                                                                                        |
| 9     | Tóm tắt, câu cuối     | "chế độ thất bại của GDS… KHÔNG ĐẾN TỪ QUY MÔ mà từ việc lọc thành phần theo kích thước"                            | Cơ chế em chỉ ra là đúng và quan sát được. Nhưng thiết kế hiện tại không tách được quy mô khỏi topology (D₂ và D₃ khác nhau cả hai) - nên em chứng minh được cơ chế ĐỦ để giải thích thất bại, chưa chứng minh được quy mô KHÔNG phải một yếu tố. Hạ xuống: "chế độ thất bại được giải thích bằng việc lọc thành phần theo kích thước khi vòng nằm trong Siêu thành phần". Lưới D₄ sẽ cho em quyền nói câu mạnh hơn |
| 10    | Dòng tác giả          | Số điện thoại cá nhân 0906084548 in trong kỷ yếu                                                                    | Kiểm thể lệ hội thảo. Nếu không bắt buộc thì bỏ - kỷ yếu là tài liệu công khai vĩnh viễn                                                                                                                                                                                                                                                                                                                            |
| 11    | Đơn vị                | "Viện Công nghệ thông tin và điện, điện tử"                                                                         | "…và Điện, Điện tử" - viết hoa tên riêng                                                                                                                                                                                                                                                                                                                                                                            |

# **3\. Ba phép kiểm - làm trước tiên, dưới 30 phút**

Mục 2 là CHẮC CHẮN. Ba phép kiểm dưới đây trả lời phần còn lại - chạy trên D₂ **thật** mà em đang có.

## **3.1. Harness đang khớp chính xác hay khớp bao hàm?**

**Điều kiện tiên quyết:** cần **kết quả THÔ** của từng phương pháp trên D₂ - danh sách bản ghi **trước khi khử trùng lặp**. Nếu code cũ không lưu, chạy lại D₂ và lưu JSON trước. Bài học rút ra ngay: **luôn lưu output thô** - chính vì không có nó mà bây giờ thầy trò mình phải suy đoán code của chính mình đang làm gì.

import json gt = {frozenset(json.loads(l)\["participants"\]) for l in open("ground_truth_D2.jsonl")} preds = \[frozenset(x) for x in json.load(open("cypher_raw_D2.json"))\] # LIST, giu trung def exact(p, g): # Muc 3.4.1 dang mo ta cai nay u = set(p); return len(u & g), len(u - g), len(g - u), len(u) def subset(p, g): # co the code dang lam cai nay u = set(p); cov = {x for x in g if any(q <= x for q in u)} return len(cov), len({q for q in u if not any(q <= x for x in g)}), len(g - cov), len(cov) for name, f in (("exact", exact), ("subset", subset)): tp, fp, fn, nu = f(preds, gt) print(name, "TP", tp, "FP", fp, "FN", fn, "P", tp/(tp+fp) if tp+fp else None, "R", tp/(tp+fn) if tp+fn else None, "N_uniq", nu, "FF", len(preds)/nu if nu else None)

| **Kết quả**                       | **Nghĩa là**                           | **Việc phải làm**                                                                        |
| --------------------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------- |
| "subset" cho P=1,00 R=1,00 FF≈348 | Code khớp bao hàm; Mục 3.4.1 mô tả sai | Viết lại Mục 3.4.1 cho khớp code, giải thích vì sao chọn ngữ nghĩa đó. Kịch bản TỐT NHẤT |
| "exact" cho P=1,00 R=1,00 FF≈348  | Mục 3.4.1 đã đúng                      | Không phải sửa gì ở đây                                                                  |
| Không cái nào ra 348              | Bảng 3 không đến từ code này           | Nghiêm trọng. Báo thầy ngay, đừng tự xử lý                                               |

**Kết quả phép kiểm này quyết định câu trả lời của em cho câu hỏi số 1 ở Mục 4.1.** Chưa chạy thì chưa có câu trả lời.

## **3.2. Nền ngẫu nhiên có sinh ra chu trình giả không?**

Nền tài khoản thường của D₂ có ~5.000 đỉnh và ~47.500 cạnh (bậc trung bình ~9,5). **Nếu** nền là đồ thị ngẫu nhiên đều - điều bài không nói rõ, xem lỗi 2.1 - thì số chu trình ngắn xuất hiện **do tình cờ** là:

| **Độ dài** | **Kỳ vọng** |
| ---------- | ----------- |
| 3          | 286         |
| 4          | 2.035       |
| 5          | 15.460      |
| Tổng 3-5   | 17.781      |

**Đây chỉ là ước lượng, và thầy phải nói rõ giới hạn của nó:** thầy đo được rằng chính 45 vòng gian lận đã sinh ~5.039 bản ghi. Cộng lại, mô hình của thầy dự báo ~22.800 bản ghi, trong khi em báo cáo 15.679 - **lệch 46%**. Nên thầy _không_ khẳng định được 15.679 là nhiễu. Nhưng thầy khẳng định được điều này: **nền phải sinh ra hàng nghìn chu trình giả, và chúng không thể đều là TP** ⇒ Precision = 1,00 cần được giải thích.

**Phép kiểm dứt điểm, 5 phút.** Trên một **bản sao** của D₂, xoá sạch tài khoản gian lận rồi chạy lại đúng truy vấn Cypher đó:

// Tren BAN SAO cua D2 MATCH (a:Account) WHERE a.account_id STARTS WITH 'F' DETACH DELETE a; // Roi chay lai DUNG truy van Cypher cu, dem so ban ghi tra ve

| **Kết quả**    | **Nghĩa là**                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Còn hàng nghìn | Nền sinh chu trình giả. Chúng phải là FP ⇒ Precision không thể = 1,00 ⇒ có một bộ lọc ở đâu đó - sang 3.3                                               |
| Còn ~0         | Nền không sinh chu trình. Thầy nhầm, và FF = 348,42 đứng vững. Nhưng khi đó phải giải thích: nền được sinh thế nào mà không có chu trình nào? (lỗi 2.1) |

## **3.3. Precision = 1,00 đến từ đâu?**

Mở truy vấn Cypher và bước trích cụm của Hybrid. Tìm mệnh đề đụng tới:

- is_fraud hoặc bất kỳ trường nào chứa nhãn → RÒ RỈ. Bỏ và chạy lại toàn bộ
- điểm KYC, tỉ lệ giao dịch nghi ngờ → xem lỗi 2.2: hai thuộc tính này Mục 3.3.1 không tạo ra. Chúng ở đâu ra?
- không có gì ngoài bộ lọc kích thước → mâu thuẫn với 3.2, phải giải thích vì sao không có FP nền

**Dù kết quả thế nào: ghi nguyên văn ba truy vấn vào phụ lục bài báo.** Bài của em so sánh ba phương pháp - người đọc phải thấy được ba truy vấn đó, nếu không thì không ai tái lập được gì.

# **4\. Chuẩn bị thuyết trình**

## **4.1. Sáu câu hỏi sẽ đến**

Xếp theo xác suất × sát thương. Mỗi câu cần một trả lời **dưới 30 giây**. Không ai chờ em suy nghĩ hai phút trên sân khấu.

**Cảnh báo về câu số 1**

Câu trả lời cho câu 1 PHỤ THUỘC kết quả phép kiểm 3.1. Em không được học thuộc

một đáp án rồi nói trên sân khấu khi chưa chạy phép kiểm - nếu harness hoá ra

khớp chính xác, đáp án đó sai và em sẽ bị bắt tại chỗ.

Và đáp án chỉ dùng được SAU KHI em đã sửa Bảng 3. Nếu slide vẫn in Recall = 1,00

trên D₁ mà miệng em nói 0,80, người nghe sẽ thấy ngay.

| **#** | **Câu hỏi**                                                                                          | **Cách trả lời**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | "Bảng 1 nói Cypher chỉ tìm chu trình 3-5. Bảng 2 nói D₂ có vòng 8 đỉnh. Vậy Recall = 1,00 kiểu gì?"  | CHỈ trả lời sau khi chạy phép kiểm 3.1. Nếu là khớp bao hàm: "Vòng 8 đỉnh trong D₂ có mật độ 0,91-1,00 nên chứa chu trình con 3-5. Harness khớp theo bao hàm - một chu trình con nằm trọn trong vòng thật được tính là phát hiện đúng, vì điều tra viên lần theo nó vẫn ra cả vòng." RỒI THỪA NHẬN NGAY: "Đó cũng là lý do Recall của Cypher là hàm của mật độ; trên D₁ vòng thưa hơn nên nó chỉ đạt 0,80 - chúng tôi đã sửa Bảng 3." Nếu là khớp chính xác: bài có lỗi số liệu, phải sửa trước khi trình bày |
| 2     | "FF = N_predicted / N_unique. Trên dữ liệu thật anh lấy N_unique ở đâu?"                             | Đừng vòng vo: "Ở dạng hiện tại FF cần ground truth, nên nó là chỉ số benchmark chứ không phải chỉ số vận hành. Chúng tôi đang định nghĩa lại mẫu số bằng số cụm sau khi gộp các dự báo giao nhau - đại lượng đó tính được không cần nhãn." Thừa nhận + hướng đi = an toàn. Chối = chết                                                                                                                                                                                                                        |
| 3     | "D₂ có 5.000 tài khoản thường bậc 9,5. Chu trình ngẫu nhiên trong đó đâu? Sao Precision = 1,00?"     | Phụ thuộc kết quả phép kiểm 3.2. PHẢI chạy trước hội thảo. Nếu nền có sinh chu trình giả thì thừa nhận và trình bày như hạn chế đã biết                                                                                                                                                                                                                                                                                                                                                                       |
| 4     | "Anh khuyến nghị GDS cho 5.000-100.000 tài khoản. Nhưng D₃ = 100.000 và GDS Recall = 0. Giải thích?" | Nếu đã sửa Mục 5.1 theo 2.5 thì câu này không đến. Nếu chưa sửa thì không có đường trả lời                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 5     | "Đóng góp của anh là so sánh ba công cụ, hay phát hiện điểm mù Giant SCC?"                           | "Là điểm mù. Phần so sánh là phương tiện để đi tới nó." Nói dứt khoát - đừng cố giữ cả hai                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 6     | "Dữ liệu tổng hợp thì kết luận có ý nghĩa gì với ngân hàng thật?"                                    | Mục 5.2 của em đã trả lời sẵn và trả lời tốt - học thuộc đoạn đó. Nhấn: lập luận Giant SCC dựa trên định lý Karp, không dựa trên dữ liệu; nó đúng với mọi đồ thị giao dịch có bậc trung bình > 1                                                                                                                                                                                                                                                                                                              |

## **4.2. Bố cục slide đề xuất**

| **Slide** | **Nội dung**                                                   | **Ghi chú**                                                                                                                 |
| --------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 1         | Tiêu đề                                                        | \-                                                                                                                          |
| 2         | Vòng tròn gian lận là gì; vì sao xét từng giao dịch không thấy | 30 giây, một hình đồ thị nhỏ                                                                                                |
| 3         | Ba phương pháp - Bảng 1                                        | Nêu rõ NGAY: ba không gian tìm kiếm khác nhau. Nói trước khi bị hỏi                                                         |
| 4         | Ba tập dữ liệu - Bảng 2 + bảng tham số sinh                    | Bảng tham số là thứ em phải bổ sung theo lỗi 2.1                                                                            |
| 5         | Kết quả D₁, D₂: F1 không phân biệt được                        | Nói NGAY rằng đây là hệ quả thiết kế, không phải phát hiện. Đừng để người ta phải hỏi                                       |
| 6         | FF - chỉ số bổ sung                                            | Đóng góp THỨ HAI. Ngôn ngữ dè dặt. Kèm luôn hạn chế: cần ground truth                                                       |
| 7-8       | GIANT SCC - trọng tâm                                          | Hình 1. Karp 1990: bậc TB > 1 ⇒ siêu thành phần gần như chắc chắn ⇒ bộ lọc kích thước loại nó ⇒ vòng bên trong bị loại theo |
| 9         | D₃: GDS trả về TP=0, FP=0, FN=10, Recall=0                     | Con số an toàn nhất trong bài. Nhấn: đúng dưới mọi cách khớp                                                                |
| 10        | "Tình huống D₃ mới là điển hình"                               | Câu quan trọng nhất của cả bài                                                                                              |
| 11        | Hạn chế                                                        | Đừng lướt. Trình bày chậm. Đây là chỗ làm người nghe tin em                                                                 |
| 12        | Hướng phát triển: tách mật độ khỏi quy mô                      | Nếu kịp chạy lưới thì đây là slide kết quả, không phải slide hứa hẹn                                                        |

## **4.3. Ba câu KHÔNG được nói trên sân khấu**

- **"Cả ba phương pháp đều đạt Precision và Recall tuyệt đối."** Nói vậy là mời câu hỏi 1 và 3. Luôn kèm ngay: "đó là hệ quả của thiết kế dữ liệu tổng hợp".
- **"GDS SCC là lựa chọn bắt buộc cho mạng lưới tới 100.000 tài khoản."** Câu này đang có trong bài và nó sai. Xoá khỏi bài, tuyệt đối đừng nói.
- **"FF là chỉ số mới cho vận hành."** Ở dạng hiện tại nó cần ground truth. Nói "chỉ số đánh giá", đừng nói "vận hành".

## **4.4. Chuẩn bị tinh thần**

Nếu có câu em không trả lời được, đáp án đúng là: "Đây là điểm chúng tôi chưa kiểm chứng. Anh/chị nói đúng, và chúng tôi sẽ kiểm." Rồi ghi lại câu hỏi.

**Đừng bao giờ chống chế một con số em không chắc.** Hội thảo không phải phiên toà - người hỏi thường đang giúp em, kể cả khi giọng họ nghe không giống vậy. Người mất uy tín là người bảo vệ tới cùng một thứ sai, không phải người thừa nhận.

**Em đã có sẵn thứ để dựa vào.** Mục 5.2 là phần viết tốt nhất trong cả 17 bài của hội thảo này. Em tự viết rằng Precision = Recall = 1,0 là "hệ quả của thiết kế, không phải phát hiện". Rất ít người ở giai đoạn của em dám tự tay hạ giá trị kết quả của mình. Chính đoạn đó làm thầy tin phần còn lại của bài - và nó sẽ làm người nghe tin em, nếu em trình bày nó với đúng sự thẳng thắn mà em đã viết ra.

# **5\. Nội dung công việc cần làm**

| **Thứ tự** | **Việc**                                                               |
| ---------- | ---------------------------------------------------------------------- |
| 1          | Đọc code, trả lời lỗi 2.1 và 2.2: nền sinh thế nào? điểm KYC ở đâu ra? |
| 2          | Ba phép kiểm ở Mục 3                                                   |
| 3          | Báo thầy kết quả bước 1 và 2 - ĐIỂM DỪNG BẮT BUỘC                      |
| 4          | Sửa các lỗi 2.4-2.17 (không phụ thuộc phép kiểm)                       |
| 5          | Viết lại Mục 3.3.1 đầy đủ + bảng tham số sinh cho từng tập             |
| 6          | Sửa Mục 3.4.1 theo kết quả phép kiểm 3.1; chốt xử lý FF theo 2.3       |
| 7          | \[Nếu kịp\] Lưới D₄ - nhờ Phúc chạy, em phân tích                      |
| 8          | Dựng slide theo Mục 4.2                                                |
| 9          | Tập trả lời 6 câu hỏi ở Mục 4.1 - thầy sẽ hỏi thử                      |
| 10         | Rà font bằng pdffonts trên bản render PDF, nộp                         |

**Bước 3 là điểm dừng bắt buộc.** Nếu bước 1 cho ra kết quả xấu - ví dụ Hybrid chấm điểm bằng nhãn gian lận - thì vấn đề lớn hơn mọi thứ trong tài liệu này và thầy trò mình phải bàn lại, trước khi em bỏ công dựng slide.

# **6\. Tóm tắt**

1\. ĐỔI TRỌNG TÂM. Dẫn bằng Giant SCC, không dẫn bằng FF. Kết quả D₃ của GDS

(TP=0, FP=0, FN=10) miễn nhiễm với mọi vấn đề trong tài liệu này.

2\. BÀI KHÔNG MÔ TẢ CÁCH SINH 94% DỮ LIỆU CỦA MÌNH. Mục 3.3.1 chỉ nói về vòng

gian lận; 47.500 giao dịch nền của D₂ không được mô tả ở đâu cả. Đây là

phương pháp nghiên cứu của một bài dữ liệu tổng hợp - không được thiếu.

3\. TRẢ LỜI NGAY HÔM NAY: điểm KYC ở Mục 3.2 lấy từ đâu, khi Mục 3.3.1 chỉ tạo

ra đúng một nhãn là nhãn gian lận?

4\. FF Ở DẠNG HIỆN TẠI CẦN GROUND TRUTH. Khử trùng thuần tuý cho mẫu số 1.731

chứ không phải 45. Thừa nhận, hoặc định nghĩa lại mẫu số bằng gộp cụm.

5\. XOÁ bullet 2 của Mục 5.1. D₃ = đúng 100.000, nằm trong dải mà em khuyến nghị

GDS "bắt buộc", và ở đó GDS Recall = 0.

6\. XOÁ câu ở Mục 3.4.2. Nó nói ngược Mục 3.4.1 và phá huỷ lý do tồn tại của FF.

7\. BA PHÉP KIỂM ở Mục 3, 30 phút, trên D₂ thật. Làm trước khi sửa chữ nào - và

trước khi học thuộc bất kỳ câu trả lời nào ở Mục 4.1.

8\. "HYBRID PHÂN MẢNH GẤP 8 LẦN CYPHER" là so sánh giả - nó đo dải độ dài chứ

không đo thuật toán. Bài chỉ có HAI họ: liệt kê chu trình (phân mảnh) và gom

thành phần (không). Bỏ câu 8× khỏi Mục 4.1, 4.3 và Kết luận.

9\. EM ĐANG TRÌNH BÀY MỘT KẾT QUẢ ÂM. Đóng khung đúng thì dữ liệu tổng hợp hết

là điểm yếu - vì cơ chế suy ra từ định lý, dữ liệu chỉ minh hoạ.

10\. HYBRID KHÔNG CHẠY TRÊN ĐỒ THỊ ĐẦY ĐỦ CỦA D₂ - chính con số của em chứng

minh: nền D₂ chứa ~9,4 triệu chu trình độ dài 2-8, em báo cáo 123.618. Sửa

Mục 3.5 và 2.6; bỏ so sánh thời gian Cypher-Hybrid.

11\. TỪ KHOÁ KHÔNG CÓ MỘT CHỮ NÀO về hai đóng góp của bài. Sửa mất 30 giây.

12\. GIỮ NGUYÊN VĂN PHONG MỤC 5.2. Sửa Mục 5.1 xuống, đừng nâng Mục 5.2 lên.