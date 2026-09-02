
Bài của em có một mâu thuẫn số liệu ở tập D₂ mà thầy không giải được từ bên ngoài. Thầy đã thử cả hai khả năng và không khả năng nào làm toàn bộ kết quả của bài nhất quán — nghĩa là đây không phải một con số gõ nhầm, mà là dấu hiệu của thứ gì đó ở tầng sâu hơn. Thầy cần em mở dữ liệu và script ra, điền 12 ô ở Phần 1 và trả lời 4 câu ở Phần 4.
Đọc Phần 3 trước khi làm — thầy tìm được một manh mối gần như chắc chắn đúng, và nếu nó đúng thì nó thay đổi cách hiểu đóng góp chính của bài.
PHẦN 1. MƯỜI HAI Ô CẦN ĐIỀN
Điền từ dữ liệu thật, không tính lại từ bài báo:
	Số Account (đỉnh)	Số Transaction (giao dịch)	Bậc trung bình (Transaction/Account)	Tỉ lệ gian lận
D₁ (Nhỏ)	50 ?	28 ?	0,56 ?	82,1% ?
D₂ (Trung bình)	?	?	?	?
D₃ (Lớn)	100.000 ?	900.049 ?	9,0 ?	0,005% ?

Các ô có dấu "?" ở D₁ và D₃ là số thầy đọc từ bài — em vẫn xác nhận lại. Riêng D₂ thì bỏ trống hoàn toàn, vì bài đang có hai con số đánh nhau.
PHẦN 2. VÌ SAO THẦY KHÔNG ĐOÁN HỘ ĐƯỢC
	Nếu 5.525 đúng (theo bảng)	Nếu 50.572 đúng (theo Mục 4.1)
Bậc TB của D₂	5.525 / 5.225 = 1,06	50.572 / 5.225 = 9,68
Vì sao chỉ D₃ có Giant SCC?	✓ Giải thích được. D₂ bậc 1,06 vừa qua ngưỡng → SCC nhỏ. D₃ bậc 9,0 → Giant SCC.	✗ Hỏng. D₂ (9,68) còn ĐẶC HƠN D₃ (9,0), lẽ ra D₂ phải có Giant SCC nặng hơn. Nhưng nó không có.
Cypher sinh 84.420 bản ghi?	✗ Vô lý. Đồ thị bậc 1,06 gần như là cây, gần như không có chu trình nào để mà liệt kê.	✓ Hợp lý. Bậc 9,68 đủ đặc để bùng nổ tổ hợp.
Tỉ lệ gian lận trong bảng	✓ 225/5.525 = 4,07% khớp	✗ 225/50.572 = 0,44%, không phải 4,07%

Mỗi phương án giải thích được một nửa và làm hỏng nửa kia. Nếu thầy chọn đại một số, bài sẽ trông sạch nhưng sẽ sai ở một chỗ nào đó mà không ai biết trước là chỗ nào.
PHẦN 3. MANH MỐI — VÀ NÓ QUAN TRỌNG HƠN CON SỐ
Thầy thử tính ngược từ FF của Cypher. Mục 3.2.1 nói Cypher chỉ tìm chu trình độ dài k ∈ {3, 4, 5}. Bảng dữ liệu nói kích thước vòng tối đa là 8 đỉnh.
Số chu trình cơ sở độ dài k trong một đồ thị ĐẦY ĐỦ CÓ HƯỚNG trên 8 đỉnh là C(8,k) × (k−1)!:
  k=3 :  C(8,3) × 2!  =  56 × 2   =    112
  k=4 :  C(8,4) × 3!  =  70 × 6   =    420
  k=5 :  C(8,5) × 4!  =  56 × 24  =  1.344
  ─────────────────────────────────────────
  TỔNG                             =  1.876

FF của Cypher trên D₂ mà bài em báo cáo: 1.876,00. Khớp chính xác.
Kiểm tra chéo: 45 vòng × 1.876 = 84.420 — đúng bằng "hơn 84.000 dòng" em viết ở Mục 4.1. Và 225 giao dịch gian lận ÷ 45 vòng = 5,0 cạnh lõi mỗi vòng, tức chu trình đơn.
Kết luận thầy rút ra: FF = 1.876 KHÔNG phải là đặc tính của Cypher trên một đồ thị cỡ trung bình. Nó là đặc tính của cách script của em sinh ra các vòng gian lận. Nhiều khả năng bước (2) trong Mục 3.3.1 — "bổ sung các cạnh liên kết" — đang biến mỗi vòng thành một đồ thị đầy đủ 8 đỉnh, và các cạnh bổ sung này không được gán nhãn gian lận (nên fraud vẫn = 225 = 45 × 5 cạnh lõi).
Hệ quả — em cần hiểu rõ chỗ này:
●	Nếu đúng, thì 84.420 bản ghi của Cypher sinh ra từ mật độ BÊN TRONG vòng, không phải mật độ toàn đồ thị. Khi đó đồ thị toàn cục vẫn có thể thưa → phương án 5.525 không còn bị bác bỏ → và cách giải thích Giant SCC bằng bậc trung bình lại đứng vững. Tức là 5.525 nhiều khả năng đúng, và "50.572 giao dịch" ở Mục 4.1 mới là số sai.
●	Nhưng nó cũng có nghĩa: con số FF = 1.876 là tạo tác của bộ sinh dữ liệu, không phải phát hiện về Cypher. Đổi cách sinh vòng (ví dụ vòng chỉ có cạnh lõi, không có dây cung) thì FF tụt về gần 1,0 và toàn bộ luận điểm của bài biến mất. Đây là hạn chế phải nói thẳng ở Mục 5.2, và thầy sẽ viết lại đoạn đó nếu em xác nhận.
●	Luận điểm của bài vẫn còn giá trị nhưng phải phát biểu lại cho đúng: "khi các vòng gian lận có cấu trúc dày (nhiều dây cung), phương pháp liệt kê chu trình bùng nổ còn phương pháp gom SCC thì không" — đây là phát biểu đúng và vẫn hữu ích. Khác với phát biểu hiện tại, vốn ngầm hiểu FF là hàm của quy mô đồ thị.
Một điều thầy CHƯA giải thích được:
Nếu mỗi vòng là đồ thị đầy đủ 8 đỉnh, thì Hybrid (dùng nx.simple_cycles với max_cycle_length = 10, tức tìm mọi độ dài) phải tìm ra 16.064 chu trình mỗi vòng, cho FF ≈ 16.064. Nhưng em báo cáo FF = 246,00. Con số này không khớp với mô hình trên. Em xem lại Hybrid thực sự chạy trên cái gì — nó có bị giới hạn bởi bước trích SCC bằng Cypher trước đó không?
PHẦN 4. BỐN CÂU HỎI
#	Câu hỏi
1	Bước (2) của Mục 3.3.1 "bổ sung các cạnh liên kết" thực sự thêm bao nhiêu cạnh cho mỗi vòng? Vòng có trở thành đồ thị đầy đủ không? Các cạnh này có được gán nhãn gian lận không? Gửi thầy đoạn code sinh vòng.
2	Chạy lệnh dưới đây trên D₂ và D₃, gửi kết quả. Đây là phép đo trực tiếp cho câu hỏi Giant SCC — không cần suy luận nữa.
3	Tổng số bản ghi Cypher xuất ra trên D₂ chính xác là bao nhiêu? Có đúng 84.420 không? (Bài chỉ viết "hơn 84.000".)
4	Hybrid với max_cycle_length = 10 thực sự chạy trên đồ thị con nào? Vì sao FF của nó là 246 chứ không phải 16.064?

Lệnh cho câu 2 — phân bố kích thước SCC:
CALL gds.scc.stream($graph_name)
YIELD nodeId, componentId
RETURN componentId, count(*) AS size
ORDER BY size DESC LIMIT 10;

Lệnh lấy bốn số ở Phần 1:
MATCH (a:Account)     RETURN count(a) AS so_account;
MATCH (t:Transaction) RETURN count(t) AS so_transaction;
MATCH (t:Transaction) WHERE t.is_fraud = true
RETURN count(t) AS gd_gian_lan;
Bậc trung bình = so_transaction / so_account. Tỉ lệ gian lận = gd_gian_lan / so_transaction.

Thầy đánh giá cao bài này — nó là bài có thiết kế thực nghiệm tốt nhất trong đợt, và việc em báo cáo thẳng kết quả âm tính ở D₃ là điều đúng đắn. Chính vì vậy mà mấy con số này phải chuẩn. Có đủ dữ liệu thầy sẽ hoàn thiện bài trong một lượt, kể cả viết lại Mục 4.2 và 5.2.
Nếu em thấy phân tích ở Phần 3 sai chỗ nào, phản hồi lại kèm bằng chứng — thầy có thể nhầm.
