**RÒ RỈ DO TIỀN XỬ LÝ VÀ CÁC CHẾ ĐỘ SUY GIẢM LIÊN QUAN GIANT SCC TRONG ĐỐI CHUẨN PHÁT HIỆN VÒNG GIAN LẬN TRÊN ĐỒ THỊ**

**Hoàng Xuân Tiên, Ngô Văn Gia Phúc, Nguyễn Thanh Tiến**

Viện Công nghệ thông tin và Điện, Điện tử, Trường Đại học Giao thông vận tải TP. Hồ Chí Minh

<tiennt@ut.edu.vn>

**_Tóm tắt_**

_Nghiên cứu thực hiện đối chuẩn bốn pipeline phát hiện vòng gian lận trên đồ thị gồm Cypher Pattern, Cypher Optimized, Hybrid NetworkX và GDS SCC trên năm tập dữ liệu tổng hợp, tập trung vào ảnh hưởng của cấu trúc dữ liệu, tiền xử lý và hậu xử lý thay vì xếp hạng hiệu năng của thuật toán. Kết quả cho thấy bốn vấn đề chính. Thứ nhất, kiểm tra rò rỉ một biến trên thuộc tính amount cho thấy D₂ và D₃ đạt AUC lần lượt 0,9999 và 1,0000: một bộ phân loại ngưỡng đơn giản trên số tiền giao dịch, không cần đồ thị, đã phân biệt gần như hoàn hảo giao dịch gian lận với giao dịch nền, một kênh rò rỉ độc lập với kênh tiền xử lý mô tả dưới đây. Thứ hai, trên D₂ và D₃, ngưỡng mặc định transaction_count ≥ 3 của Cypher Optimized làm không gian cạnh đủ điều kiện chỉ còn các tài khoản thuộc ground truth; hiện tượng leakage này không áp dụng cho ba pipeline còn lại. Thứ ba, các đồ thị nền mật độ cao hình thành Giant SCC bao phủ trên 99,9% số đỉnh nền ở bốn trong năm tập; null model đồ thị ngẫu nhiên có hướng được sử dụng như một mốc tham chiếu có điều kiện cho kích thước cấu trúc này. Thứ tư, các vị trí suy giảm khác nhau giữa các pipeline: Hybrid NetworkX và GDS SCC trả đầu ra rỗng khi Giant SCC vượt cửa sổ tiền tuyển 3–12, trong khi Cypher Pattern bị giới hạn bởi phạm vi truy vấn hoàn tất và đầu ra thay đổi độ phân giải sau bước chuẩn hóa/gộp bên ngoài; trên D₄, phép gộp giảm 1.689 participant-set phân biệt xuống còn 129 cụm mà không làm mất true-positive quan sát được trong run chính. Từ các kết quả này, nghiên cứu đề xuất một giao thức chẩn đoán benchmark gồm kiểm tra rò rỉ tiền xử lý, cấu trúc SCC, rò rỉ thuộc tính và tác động của hậu xử lý, qua đó góp phần nâng cao tính tin cậy và khả năng tái lập của các nghiên cứu phát hiện gian lận trên dữ liệu tổng hợp._

**_Từ khoá:_** _đồ thị, gian lận tài chính, vòng tròn gian lận, rò rỉ ground-truth, rò rỉ thuộc tính, thành phần liên thông mạnh, hệ số phân mảnh (FF_enum, FF_merge)._

# **1\. Đặt vấn đề**

## **_1.1. Bối cảnh_**

Gian lận tài chính là thách thức nghiêm trọng đối với hệ thống tài chính toàn cầu: 2.402 vụ gian lận nghề nghiệp trên 143 quốc gia được ghi nhận, còn mức thất thoát của chính phủ Hoa Kỳ ước tính 233-521 tỷ USD mỗi năm giai đoạn 2018-2022 (ACFE, 2026; GAO, 2024).

Vòng tròn gian lận là hình thái đặc biệt khó phát hiện: nhiều tài khoản cấu kết luân chuyển dòng tiền theo các cấu trúc khép kín (Wells, 2017). Hệ thống xét từng giao dịch độc lập không nhìn thấy quan hệ này vì mỗi giao dịch thành phần có thể bình thường khi tách riêng; chỉ khi ghép thành đồ thị thì dấu vết topo mới lộ ra dưới dạng một chu trình đơn hoặc một mạng nội bộ chứa nhiều chu trình. Vì dữ liệu ngân hàng thực gần như không thể tiếp cận kèm nhãn gian lận đáng tin cậy, phần lớn nghiên cứu trong lĩnh vực này dựa vào dữ liệu tổng hợp (Motie & Raahemi, 2024).

## **_1.2. Khoảng trống nghiên cứu_**

Việc sử dụng dữ liệu tổng hợp giúp giải quyết hạn chế về quyền truy cập và nhãn ground truth trong nghiên cứu gian lận tài chính, nhưng đồng thời tạo ra nguy cơ các đặc điểm của bộ sinh dữ liệu hoặc quy trình tiền xử lý vô tình làm đơn giản hóa bài toán phát hiện. Trong phạm vi các công trình được khảo sát trong nghiên cứu này, chúng tôi nhận thấy phần lớn đánh giá tập trung vào các chỉ số đầu ra như Precision, Recall, F1-Score hoặc AUC, trong khi các chẩn đoán về cấu trúc đồ thị sau tiền xử lý, vị trí của ground truth trong các thành phần liên thông mạnh và khả năng suy ra nhãn từ từng thuộc tính đầu vào ít được báo cáo một cách đồng thời.

Nghiên cứu này không khẳng định rằng các kiểm tra trên hoàn toàn vắng mặt trong toàn bộ tài liệu về phát hiện gian lận trên đồ thị. Thay vào đó, chúng tôi đặt câu hỏi hẹp hơn: liệu một pipeline có thể đạt chỉ số phân loại thuận lợi không phải do thuật toán tốt hơn, mà do chính dữ liệu, bước tiền xử lý hoặc bước hậu xử lý đã làm thay đổi bản chất của bài toán?

Từ câu hỏi đó, nghiên cứu tập trung vào ba nguồn sai lệch: (i) rò rỉ ground truth do tiền xử lý; (ii) mất khả năng phân giải khi Giant SCC chiếm phần lớn đồ thị; và (iii) suy giảm thông tin do giao thức chuẩn hóa và gộp ứng viên.

## **_1.3. Đóng góp_**

Nghiên cứu này không nhằm xếp hạng bốn pipeline được khảo sát, bởi chúng khác nhau về biểu diễn đồ thị, phép chiếu đầu vào, chiến lược tiền tuyển và hậu xử lý. Mục tiêu của nghiên cứu là chẩn đoán các yếu tố có thể làm sai lệch một đối chuẩn phát hiện fraud ring trên dữ liệu tổng hợp. Các đóng góp chính gồm:

- Phát hiện và định lượng một kênh rò rỉ ground-truth độc lập qua thuộc tính amount trên D₂ và D₃ (AUC một biến 0,9999 và 1,0000), có cơ chế tách biệt với kênh rò rỉ do tiền xử lý mô tả ở đóng góp tiếp theo. Phát hiện này cho thấy một benchmark tổng hợp có thể vô hiệu về mặt đánh giá phát hiện dựa trên thuộc tính mà tác giả bộ sinh không biết, đồng thời minh chứng giá trị của quy trình chẩn đoán bốn bước được đề xuất trong nghiên cứu.
- Chỉ ra và định lượng hiện tượng rò rỉ ground-truth do tiền xử lý trong Cypher Optimized. Trên D₂ và D₃, bộ lọc theo số lần giao dịch giữa cùng một cặp tài khoản loại bỏ toàn bộ tài khoản nền, khiến tập đỉnh còn lại trùng với tập tài khoản thuộc các fraud ring đã cấy. Kết quả này cho thấy các chỉ số phân loại quan sát được sau tiền xử lý cần được diễn giải thận trọng vì pipeline không còn phải phân biệt ground-truth vertices với background vertices.
- Phân tích vai trò của Giant SCC như một đặc trưng cấu trúc của các benchmark có mật độ liên kết cao. Kích thước Giant SCC quan sát được được đối chiếu với một mô hình đồ thị ngẫu nhiên có hướng làm null model, qua đó cung cấp một chẩn đoán định lượng về mức độ mà cấu trúc đầu vào có thể giới hạn khả năng phân giải của các phương pháp dựa trên thành phần liên thông mạnh.
- Phân biệt các vị trí suy giảm trong pipeline: suy giảm tại bước tiền tuyển thành phần ở Hybrid NetworkX/GDS SCC và thay đổi độ phân giải do hậu xử lý trên tập candidate của Cypher Pattern. Detector output, before-merge output và after-merge output được báo cáo riêng.
- Đề xuất một giao thức chẩn đoán đối chuẩn gồm: kiểm tra rò rỉ tiền xử lý; báo cáo phân bố SCC và vị trí ground truth; kiểm tra rò rỉ thuộc tính; tách dư thừa do liệt kê khỏi suy giảm phân giải do gộp; và báo cáo kết quả ở cả mức ứng viên phân biệt lẫn mức cụm sau hậu xử lý.

# **2\. Công trình liên quan**

Phát hiện bất thường trên đồ thị đã được hệ thống hoá trong các khảo sát nền tảng (Chandola và cộng sự, 2009; Akoglu và cộng sự, 2015), trong đó chu trình là dấu hiệu quan trọng của hành vi cấu kết. Về thuật toán, xác định thành phần liên thông mạnh có lời giải tuyến tính của Tarjan (1972), còn liệt kê chu trình đơn dựa trên Johnson (1975) với độ phức tạp phụ thuộc số chu trình đầu ra — đặc điểm quyết định hành vi trên đồ thị dày.

Nền tảng lý thuyết cho kích thước thành phần liên thông trên đồ thị ngẫu nhiên có hướng được thiết lập trong Newman và cộng sự (2001), Dorogovtsev và cộng sự (2001) và được hệ thống hoá trong Bollobás (2001), Newman (2018); nghiên cứu này sử dụng trực tiếp kết quả đó làm mốc đối chiếu cho các tập dữ liệu tổng hợp.

Về dữ liệu, AMLSim (Suzumura & Kanezashi, 2021) và bộ dữ liệu AML quy mô lớn của Altman và cộng sự (2023) được dùng phổ biến; gen-fraud-graph (Santander AI Lab, 2026) cho phép cấu hình độ sâu vòng gian lận và hệ số quy mô, và được dùng ở đây cho hai tập lớn. GADBench (Tang và cộng sự, 2023) chỉ ra kết quả trên dữ liệu tổng hợp nhạy cảm mạnh với cách sinh dữ liệu, nhưng chưa đề cập tác động của tiền xử lý lên chính định nghĩa bài toán.

Về độ đo, các khảo sát được tham chiếu tập trung vào Precision, Recall, F1-Score và AUC. Tỷ lệ cảnh báo trên hồ sơ điều tra là chỉ số vận hành quen thuộc trong chống rửa tiền (Europol, 2023; FATF, 2026) nhưng chưa được chuẩn hoá cho thiết lập participant-set; các hệ số phân mảnh FF_enum và FF_merge được đề xuất trong nghiên cứu này (Mục 3.3) hướng tới khoảng trống này.

# **3\. Phương pháp**

## **_3.1. Tập dữ liệu_**

D₁–D₃ do nhóm nghiên cứu sinh, với liên kết ring–nền một chiều: mỗi vòng gian lận nối với mạng nền bằng cầu nối chỉ theo một hướng. D₄–D₅ sinh bằng phiên bản hiệu chỉnh của gen-fraud-graph với hệ số quy mô 0,001 và 0,01, dùng liên kết hai chiều; cơ chế sinh số tiền đã được sửa nhằm hạn chế suy ra nhãn từ thuộc tính amount, mức rò rỉ còn lại sau hiệu chỉnh được đánh giá tại Mục 4.5.

Ground truth mỗi tập là tập hợp các participant-set, mỗi participant-set là tập tài khoản tham gia một vòng. Bảng 1 mô tả đặc trưng năm tập, đo trên phép chiếu tài khoản → tài khoản sau khử trùng cạnh.

Trong nghiên cứu này, thuật ngữ fraud ring được dùng theo nghĩa rộng để chỉ một cấu trúc giao dịch có nhiều tài khoản tham gia và được bộ sinh dữ liệu gán cùng một ground-truth participant-set. Không phải mọi fraud ring đều nhất thiết tương ứng với đúng một chu trình đơn đi qua toàn bộ tài khoản. Một số tập dữ liệu có thể chứa các motif dạng chu trình đơn, trong khi một số khác chứa cấu trúc complex_network gồm nhiều chu trình hoặc nhiều liên kết nội bộ giữa cùng một nhóm tài khoản.

Vì vậy, kích thước participant-set và độ dài của một chu trình được liệt kê là hai khái niệm khác nhau. Phép đối chiếu theo độ dài chỉ được diễn giải trực tiếp đối với các ground-truth motif đã được xác nhận là chu trình đơn.

Ký hiệu nₖ chỉ số vòng gian lận có đúng k tài khoản tham gia.

**Bảng 1. Đặc trưng năm tập dữ liệu trên phép chiếu tài khoản → tài khoản**

| **Tập** | **|V|** | **|E|** | **Bậc TB** | **Số ring** | **Đỉnh ring** | **Cạnh ring** | **Hướng cầu nối** | **Nguồn sinh** |
| ------- | --------- | --------- | ---------- | ----------- | ------------- | ------------- | ----------------- | --------------- |
| D₁      | 50        | 43        | 0,86       | 5           | 24            | 24            | một chiều         | nhóm NC         |
| D₂      | 5.225     | 48.142    | 9,21       | 45          | 225           | 684           | một chiều         | nhóm NC         |
| D₃      | 100.050   | 855.106   | 8,55       | 10          | 50            | 141           | một chiều         | nhóm NC         |
| D₄      | 10.000    | 90.018    | 9,00       | 10          | 60            | 60            | hai chiều         | gen-fraud-graph |
| D₅      | 100.000   | 830.028   | 8,30       | 10          | 58            | 58            | hai chiều         | gen-fraud-graph |

_Ghi chú: |E| là số cặp tài khoản có hướng phân biệt trên phép chiếu đầy đủ, nhỏ hơn số giao dịch do nhiều giao dịch xảy ra giữa cùng một cặp. Riêng D₅ có 830.028 cặp phân biệt trên 900.058 giao dịch gốc, mức trùng lặp cao hơn đáng kể so với D₄; nguyên nhân được nêu tại Mục 6._

## **_3.2. Bốn pipeline được đối chuẩn_**

Bốn pipeline khác nhau về biểu diễn dữ liệu, tiền tuyển ứng viên và hậu xử lý nên được xem là các pipeline hoàn chỉnh, thay vì các thuật toán chạy trên cùng một đầu vào.

- Cypher Pattern truy vấn trực tiếp các đường đi khép kín trên mô hình Account–Transaction–Account với độ dài k cố định; mã baseline chỉ yêu cầu các tài khoản trong chu trình khác nhau và không áp bộ lọc nghiệp vụ, khử trùng participant-set hay gộp kết quả.
- Cypher Optimized mặc định sử dụng phép chiếu TRANSFER_AGG, trong đó mỗi cặp tài khoản có hướng được rút gọn thành một cạnh logic; truy vấn yêu cầu transaction_count ≥ 3 theo cấu hình mặc định, đồng thời chuẩn hóa chu trình và gộp bắc cầu các participant-set có chung tài khoản.
- Hybrid NetworkX cũng nạp một cạnh logic cho mỗi cặp tài khoản nhưng không lọc cạnh theo amount hoặc số giao dịch khi tạo đồ thị; sau đó chỉ các SCC có kích thước 3–12 được chuyển vào nx.simple_cycles, trước khi các ứng viên chồng lấn được gộp.
- GDS SCC chiếu toàn bộ các cặp tài khoản có giao dịch, chạy gds.scc.stream và chỉ giữ SCC kích thước 3–12; amount và density chỉ được bổ sung sau bước phát hiện.

Vì vậy, nghiên cứu không sử dụng các khác biệt quan sát được để xếp hạng thuần túy giữa các thuật toán.

## **_3.3. Giao thức đánh giá và Hệ số phân mảnh_**

Detector output và evaluation output được lưu thành hai tầng riêng. Ở tầng detector, artifact giữ nguyên hành vi gốc của từng pipeline; đặc biệt, Cypher Pattern chỉ chứa transaction paths và không tự gộp. Ở tầng đánh giá, đầu ra thô của mọi pipeline có thể được đưa qua cùng giao thức chuẩn hóa để phân tích độ nhạy: mỗi bản ghi được chuyển thành participant-set, các participant-set trùng chính xác được khử trùng, rồi các tập có giao khác rỗng được nối và lấy bao đóng bắc cầu. Vì vậy, và của Cypher Pattern trong các bảng kết quả là sản phẩm của module đánh giá bên ngoài, không phải chức năng của cypher_cycle_detection_unoptimized.py.

Các metric được tính ở hai thời điểm. Mức before merge đối chiếu các participant-set phân biệt với ground truth; mức after merge đối chiếu hợp participant-set của từng overlap component. Cách tách này cho phép xác định một thay đổi metric xuất hiện trong detector, normalization hay overlap-merging. Chỉ output của các cycle size hoàn tất mới được đưa vào các metric; các dòng đã stream trước timeout được giữ để chẩn đoán nhưng bị loại khỏi đánh giá chính.

Nghiên cứu ghi nhận ba đại lượng: là số bản ghi thô do pipeline tạo ra; là số participant-set phân biệt sau khử trùng chính xác; và là số cụm sau gộp bắc cầu các participant-set giao nhau.

Để tránh gộp hai nguồn dư thừa có bản chất khác nhau vào cùng một chỉ số, nghiên cứu sử dụng hai hệ số:

phản ánh mức dư thừa do cơ chế liệt kê hoặc biểu diễn, và

phản ánh mức suy giảm độ phân giải do hậu xử lý gộp.

Khi cần mô tả tổng mức nén từ đầu ra thô tới cụm cuối cùng, có thể sử dụng:

Phân rã này cho phép phân biệt trường hợp một pipeline sinh nhiều biểu diễn lặp của cùng một candidate với trường hợp nhiều candidate thực sự khác nhau bị gộp thành một cảnh báo duy nhất.

## **_3.4. Quy trình chẩn đoán cấu trúc_**

Ngoài kết quả đối chuẩn, mỗi tập dữ liệu được phân tích độc lập về cấu trúc liên thông trước và sau tiền xử lý. Phân bố kích thước các thành phần liên thông mạnh (SCC) được xác định, đồng thời vị trí của từng ground-truth fraud ring được đối chiếu để xác định ring tồn tại như một SCC riêng, bị hấp thụ vào Giant SCC hay bị phân tách qua nhiều thành phần. Quy trình cũng ghi nhận số cạnh nội bộ ring còn lại sau lọc và khả năng rò rỉ nhãn từ các thuộc tính giao dịch.

Để có một mốc tham chiếu cho kích thước Giant SCC, nghiên cứu sử dụng mô hình không của đồ thị ngẫu nhiên có hướng. Với giả định bậc vào và bậc ra trung bình cùng xấp xỉ , gọi là tỷ lệ đỉnh thuộc thành phần khổng lồ tương ứng, được xác định bởi phương trình điểm bất động

Khi đó, kích thước Giant SCC kỳ vọng được xấp xỉ bởi

Cách đối chiếu này dựa trên lý thuyết thành phần khổng lồ trong mạng ngẫu nhiên có hướng của Newman và cộng sự (2001) và Dorogovtsev và cộng sự (2001), với cơ sở lý thuyết tổng quát về đồ thị ngẫu nhiên được trình bày trong Bollobás (2001) và Newman (2018). Công thức (1)-(2) được sử dụng như một null-model approximation, không hàm ý rằng kích thước Giant SCC của mọi mạng có hướng chỉ được quyết định bởi bậc trung bình.

Khi , phương trình (1) không có nghiệm dương khác 0; khi , một nghiệm dương xuất hiện, tương ứng với ngưỡng thẩm thấu của mô hình. Nghiên cứu giải số phương trình (1), không thay bằng , vì phép thay thế đó có thể sai lệch đáng kể gần ngưỡng.

Do mục tiêu là đánh giá cấu trúc phát sinh từ mạng nền thay vì từ các fraud ring được cấy vào, cả (c), (|V|) và kích thước Giant SCC quan sát dùng trong phép đối chiếu đều được tính trên cùng đồ thị nền sau khi loại các thành phần thuộc ground truth. Với các tập rất nhỏ hoặc nằm gần ngưỡng thẩm thấu, kết quả lý thuyết chỉ được sử dụng để diễn giải định tính thay vì đánh giá độ khớp định lượng.

## **_3.5. Môi trường thực nghiệm_**

Neo4j Enterprise 2026.06.0 (Cypher 5/25), GDS 2026.06.0, Python 3.11.9 và NetworkX 3.1 (NetworkX Developers, 2023). Run chính sử dụng Neo4j initial heap 2 GiB, max heap 8 GiB và page cache 1 GiB; Neo4j đặt dbms.memory.transaction.total.max ở 5,60 GiB, do đó lỗi chạm ngưỡng này không được diễn giải là cạn toàn bộ heap hoặc RAM vật lý.

Mỗi cấu hình được chạy một lần và runtime chỉ mang tính mô tả. Query timeout của Cypher Pattern là 120 giây; output stream trước timeout không được tính là một cycle size hoàn tất. Cấu hình 1 GiB thuộc bundle lịch sử chỉ được giữ làm artifact chẩn đoán và không phải nguồn số liệu chính của bản này. File cấu hình bộ sinh hiện có khai báo seed 42, nhưng chưa đủ bằng chứng gắn seed đó với mọi snapshot lịch sử; bài không gán seed cho snapshot khi thiếu provenance tương ứng.

# **4\. Kết quả**

## **_4.1. Cấu trúc liên thông của năm tập dữ liệu_**

Bảng 2 trình bày phép đối chiếu nhất quán trên đồ thị nền cảm sinh sau khi loại toàn bộ tài khoản ground truth và các cạnh kề chúng. Cả , , và SCC nền lớn nhất đều được tính trên cùng đồ thị. D₂-D₅ có từ 8,30 đến 9,47 và SCC nền lớn nhất bao phủ ít nhất 99,95% số đỉnh nền. D₁ có và không có SCC nền không tầm thường; trường hợp nhỏ này chỉ được diễn giải định tính.

**Bảng 2. Phân bố thành phần liên thông mạnh trên đồ thị nền**

| _Tập_ | _|V_bg|_ | _|E_bg|_ | _Bậc TB_ | _Tổng SCC_bg_ | _SCC_bg lớn nhất_ | _Độ phủ quan sát_ | _Dự đoán S²·|V_bg|_ | _Sai lệch tương đối_ | _Vị trí ground-truth ring trong full graph_ |
| ----- | ---------- | ---------- | -------- | ------------- | ----------------- | ----------------- | --------------------- | -------------------- | ------------------------------------------- |
| _D₁_  | _26_       | _9_        | _0,35_   | _26_          | _1_               | _3,85%_           | _0,00_                | _N/A_                | _5/5 là SCC độc lập_                        |
| _D₂_  | _5.000_    | _47.368_   | _9,47_   | _2_           | _4.999_           | _99,98%_          | _4.999,23_            | _−0,005%_            | _45/45 là SCC độc lập_                      |
| _D₃_  | _100.000_  | _854.945_  | _8,55_   | _38_          | _99.963_          | _99,96%_          | _99.961,21_           | _+0,002%_            | _10/10 là SCC độc lập_                      |
| _D₄_  | _9.940_    | _88.872_   | _8,94_   | _5_           | _9.936_           | _99,96%_          | _9.937,39_            | _−0,014%_            | _10/10 thuộc Giant SCC_                     |
| _D₅_  | _99.942_   | _829.027_  | _8,30_   | _51_          | _99.892_          | _99,95%_          | _99.891,98_           | _+0,00002%_          | _10/10 thuộc Giant SCC_                     |

_Ghi chú: Đồ thị nền loại mọi Account có thuộc tính ground truth và chỉ giữ các cặp Account→Account phân biệt giữa hai đầu mút nền. Dự đoán dùng nghiệm số của rồi tính ; không dùng . Với D₁, null model dự đoán không có Giant SCC; SCC đơn đỉnh quan sát được không được dùng để tính sai lệch phần trăm._

Hai kết luận rút ra. Thứ nhất, với bốn tập D₂–D₅ có c_bg từ 8,30 đến 9,47, sai lệch giữa độ phủ SCC nền lớn nhất quan sát được và dự đoán từ (2) nằm trong khoảng 0,00002%–0,014%, và độ phủ quan sát được đều vượt 99,9% (từ 99,95% đến 99,98%), tức lý thuyết mô tả tốt các tập có mật độ nền cao và độ phủ tăng nhanh theo c khi vượt ngưỡng thẩm thấu. Với D₁ có c_bg = 0,35 < 1, phương trình (1) không có nghiệm dương khác 0, tức lý thuyết dự đoán không tồn tại Giant SCC; quan sát phù hợp về mặt định tính với dự đoán này, vì toàn bộ 26 đỉnh nền của D₁ đều là thành phần liên thông mạnh đơn lẻ (Tổng SCC_bg = 26). Vì D₁ nằm dưới ngưỡng thẩm thấu, kết quả trên tập này chỉ được diễn giải định tính, như đã nêu ở Mục 3.4, và không được dùng để tính sai lệch phần trăm. Ngưỡng c_bg = 1 chỉ là điều kiện tồn tại của Giant SCC, không phải điều kiện để Giant SCC bao phủ gần trọn đồ thị. Giant SCC vì vậy là hệ quả tất yếu của mật độ giao dịch nền, tồn tại trước khi cấy vòng gian lận và có thể ước lượng từ |V_bg| và |E_bg| mà không cần chạy thuật toán.

Thứ hai, việc vòng gian lận nằm trong hay ngoài Giant SCC hoàn toàn do hướng cầu nối ring–nền quyết định, không do quy mô dữ liệu. Ở D₂ và D₃ với cầu nối một chiều, toàn bộ vòng vẫn là thành phần liên thông mạnh độc lập dù Giant SCC bao phủ 99,98% và 99,96% đồ thị nền. Ở D₄ và D₅ với cầu nối hai chiều, toàn bộ 10 vòng của mỗi tập bị hấp thụ vào Giant SCC, khiến ranh giới thành phần không còn trùng với ranh giới vòng.

Trên bốn tập có mật độ nền cao, null model cho giá trị gần quan sát, nhưng đây là một phép đối chiếu mô tả trên các snapshot cụ thể chứ không chứng minh quan hệ nhân quả phổ quát. D₁ nằm dưới ngưỡng và không có SCC nền không tầm thường, phù hợp về mặt định tính với null model. Việc các ring nằm ngoài Giant SCC ở D₂-D₃ nhưng bị hấp thụ ở D₄-D₅ là quan sát phụ thuộc cấu trúc liên kết ring–nền của các snapshot; nghiên cứu không suy rộng quan sát này thành quy luật cho mạng giao dịch thực.

![](data:image/png;base64,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)

**Hình 1. (a) Độ phủ của SCC nền lớn nhất quan sát được và giá trị tham chiếu từ nghiệm cố định trên cùng đồ thị nền. D₁ chỉ được diễn giải định tính vì ; (b) hướng liên kết ring–nền quyết định vòng gian lận là thành phần liên thông mạnh độc lập hay bị hấp thụ vào Giant SCC.**

## **_4.2. Rò rỉ ground-truth do tiền xử lý trên D₂ và D₃_**

Bảng 3 so sánh đồ thị trước và sau khi áp bộ lọc tiền xử lý của đối chuẩn.

**Bảng 3. Tác động của bộ lọc tiền xử lý**

| Tập | Cấu hình chẩn đoán | Account trong DB | Eligible endpoints sau lọc | |E| sau | Cạnh ring còn lại | Số đỉnh ring theo ground truth                      |
| --- | ------------------ | ---------------- | -------------------------- | --------- | ----------------- | --------------------------------------------------- |
| D₁  | min_pair = 3       | 50               | 0                          | 0         | 0 / 24            | 24                                                  |
| D₂  | min_pair = 3       | 5.225            | 225                        | 450       | 450 / 684         | n₃ = 15, n₅ = 20, n₈ = 10 (tổng 225 đỉnh / 45 vòng) |
| D₃  | min_pair = 3       | 100.050          | 50                         | 93        | 93 / 141          | n₃ = 3, n₅ = 5, n₈ = 2 (tổng 50 đỉnh / 10 vòng)     |
| D₄  | lọc số tiền        | 10.000           | 10.000                     | 90.018    | 60 / 60           | 60                                                  |
| D₄  | min_pair = 3       | 10.000           | 0                          | 0         | 0 / 60            | 60                                                  |
| D₅  | min_pair = 3       | 100.000          | 16                         | 8         | N/A               | 58                                                  |

Trên D₂, phép chiếu cạnh đủ điều kiện của Cypher Optimized còn đúng 225 eligible endpoints phân biệt, trùng khít tổng số tài khoản của 45 vòng gian lận; trên D₃ là 50, trùng khít 10 vòng. Các con số 225/50 không phải số Account còn trong database: database vẫn chứa tương ứng 5.225/100.050 Account. Kiểm tra vị trí từng vòng xác nhận không tài khoản ground truth nào bị mất trong không gian cạnh đủ điều kiện. Vì vậy, riêng không gian tìm kiếm của Cypher Optimized với ngưỡng mặc định không còn endpoint nền. Ba pipeline còn lại vẫn nhận đồ thị đầy đủ; không được dùng kết quả 225/50 để diễn giải Precision, Recall, runtime hoặc số ứng viên của chúng.

Hệ quả là Precision của Cypher Optimized trên D₂-D₃ không thể được diễn giải độc lập như năng lực phân biệt fraud với background: bước lọc đã làm mất lớp background ở mức đỉnh trước phát hiện. Kết luận này không áp dụng cho Cypher Pattern, Hybrid NetworkX và GDS SCC. Trong run 8 GiB, Cypher Pattern hoàn tất k=3 nhưng k=5 timeout và k=8 OOM trên D₂-D₃; trạng thái này chỉ phản ánh truy vấn transaction-path không lọc trên toàn database và không phải kiểm chứng chéo cho leakage của Cypher Optimized.

Con số D₄ ở Bảng 3 chỉ mô tả một phép lọc amount đã lưu trước đây; vì source cho phép đặt min_pair_amount và min_total_amount, phép lọc này có thể thay đổi topology. Khi chưa có ablation filtered/unfiltered trên cùng snapshot và cùng pipeline, bài không dùng nó để bác bỏ hay xác nhận nguyên nhân của kết quả cấu trúc D₄. Diễn giải bằng min_pair = 3 cho D₄ cho thấy eligible endpoints về 0 và |E| sau lọc bằng 0: nguyên nhân giống D₁ — toàn bộ eligible endpoints trên tập này bị loại, không phải do bộ lọc amount. Vì vậy Cypher Optimized với ngưỡng mặc định trả SUCCESS_EMPTY trên D₄ không phải do lọc amount mà do min_pair. Bảng 3 ghi nhận cả hai cấu hình chẩn đoán cho D₄.

Vì lý do trên, các giá trị Precision, Recall và F1-Score của Cypher Optimized trên D₂ và D₃ không được sử dụng làm bằng chứng về năng lực phân biệt fraud với background. Chỉ số của Cypher Pattern, Hybrid NetworkX và GDS SCC phải được diễn giải theo không gian tìm kiếm đầy đủ và các cơ chế tiền tuyển/hậu xử lý riêng; không được loại bỏ chỉ vì phép chẩn đoán min_pair = 3 cho kết quả 225/50.

## **_4.3. Kết quả trên D₄ và D₅ và hai cơ chế suy giảm trong Giant SCC_**

Bảng 4a trình bày run heap 8 GiB trên D₄-D₅. Với Cypher Pattern, chỉ các cycle size hoàn tất được đưa vào normalization bên ngoài: k=4 hoàn tất, k=5 timeout và k=6-7 chạm transaction-memory ceiling. Do đó các giá trị và ở hai dòng Pattern không mô tả một thao tác nằm trong detector.

**Bảng 4a. Kết quả trên D₄ và D₅**

| _Tập_ | _Phương pháp_      | _N_raw_ | _N_unique_ | _N_cluster_ | _FF_enum_ | _FF_merge_ | _Trạng thái_                       |
| ----- | ------------------ | ------- | ---------- | ----------- | --------- | ---------- | ---------------------------------- |
| _D₄_  | _Cypher Pattern_   | _6.776_ | _1.689_    | _129_       | _4,01_    | _13,09_    | _k=4 xong; k=5 timeout; k=6-7 OOM_ |
| _D₄_  | _Cypher Optimized_ | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY; min_pair=3_        |
| _D₄_  | _Hybrid NetworkX_  | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY_                    |
| _D₄_  | _GDS SCC_          | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY_                    |
| _D₅_  | _Cypher Pattern_   | _7.132_ | _1.278_    | _1.129_     | _5,58_    | _1,13_     | _k=4 xong; k=5 timeout; k=6-7 OOM_ |
| _D₅_  | _Cypher Optimized_ | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY; min_pair=3_        |
| _D₅_  | _Hybrid NetworkX_  | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY_                    |
| _D₅_  | _GDS SCC_          | _0_     | _0_        | _0_         | _N/A_     | _N/A_      | _SUCCESS_EMPTY_                    |

_Ghi chú: giá trị 0 của Hybrid NetworkX và GDS SCC là trạng thái SUCCESS_EMPTY, không phải lỗi thực thi. Với đầu ra rỗng, FF và Precision không xác định._

**Bảng 4b. Kết quả trên D₄ và D₅**

| Tập | Mức đánh giá    | TP  | FP    | FN  | Precision | Recall | F1     |
| --- | --------------- | --- | ----- | --- | --------- | ------ | ------ |
| D₄  | Before merge () | 0   | 1.689 | 10  | 0,0000    | 0,00   | 0,0000 |
| D₄  | After merge ()  | 0   | 129   | 10  | 0,0000    | 0,00   | 0,0000 |
| D₅  | Before merge () | 1   | 1.277 | 9   | 0,0008    | 0,10   | 0,0016 |
| D₅  | After merge ()  | 1   | 1.128 | 9   | 0,0009    | 0,10   | 0,0018 |

Run chính không cho thấy một true-positive của Cypher Pattern bị mất sau merge: D₄ không có TP ở mức vì chỉ k=4 hoàn tất trong khi ground truth có kích thước 5-7; D₅ giữ nguyên một TP trước và sau merge. Vì vậy, bản này không còn phát biểu rằng "pipeline Cypher Pattern mất ring do hậu xử lý". Kết luận được giới hạn ở quan sát rằng đầu ra của Cypher Pattern thay đổi độ phân giải khi áp dụng giao thức hậu xử lý chung: D₄ giảm từ 1.689 participant-set xuống 129 overlap cluster, còn D₅ giảm từ 1.278 xuống 1.129. Artifact lịch sử từng cho không được trộn vào Bảng 4 vì dùng cấu hình tài nguyên và phạm vi truy vấn khác.

Hybrid NetworkX và GDS SCC trả SUCCESS_EMPTY trên D₄-D₅ vì các ring nằm trong Giant SCC kích thước 9.996 và 99.950, vượt cửa sổ 3-12. Trên D₁-D₃, ranh giới SCC trùng khít ranh giới ring (Bảng 2, cột vị trí ground-truth: 5/5, 45/45 và 10/10 là SCC độc lập), và cơ chế lọc kích thước 3-12 của GDS SCC giữ nguyên các SCC này; bài không có bảng Precision/Recall riêng cho D₁-D₃ để xác nhận số ring được phục hồi ở mức đầu ra, nên phát biểu về D₁-D₃ chỉ dừng ở mức cấu trúc SCC, không phải mức đầu ra thuật toán.

Phát biểu chính xác như sau.

**Nhận xét 1. Gọi G là một đồ thị có hướng và C là tập các participant-set được sinh từ các chu trình có hướng của G. Xây dựng đồ thị chồng lấn H, trong đó mỗi đỉnh của H tương ứng với một participant-set trong C, và hai đỉnh của H được nối nếu hai participant-set tương ứng có giao khác rỗng. Khi đó, hợp các participant-set thuộc mỗi thành phần liên thông của H nằm trọn trong một thành phần liên thông mạnh của G.**

_Chứng minh. Mọi đỉnh nằm trên cùng một chu trình có hướng đều liên thông mạnh với nhau, do đó mỗi participant-set sinh từ một chu trình nằm trọn trong một SCC của G. Nếu hai participant-set giao nhau, chúng có ít nhất một đỉnh chung. Vì mỗi đỉnh của G thuộc duy nhất một SCC, hai participant-set đó phải nằm trong cùng SCC. Áp dụng lập luận này dọc theo một đường đi trong mỗi thành phần liên thông của H, hợp của tất cả participant-set trong thành phần đó vẫn nằm trong cùng một SCC∎_

Hệ quả là phép gộp dựa trên chồng lấn không thể tạo một cụm vượt qua ranh giới giữa hai SCC khác nhau. Tuy nhiên, một SCC có thể chứa nhiều thành phần liên thông khác nhau của H. Vì vậy, từ Nhận xét 1 không thể suy ra rằng một Giant SCC tất yếu tạo ra đúng một cụm sau gộp.

Việc 1.689 participant-set trên D₄ tạo thành đúng 129 cụm là một kết quả thực nghiệm về cấu trúc chồng lấn của tập ứng viên, chứ không phải hệ quả tự động của sự tồn tại Giant SCC.

## **_4.4. Trần Recall theo phạm vi truy vấn hoàn tất_**

Recall bằng 0 hoặc gần 0 trên D₄–D₅ cần được đọc kèm một ràng buộc thường bị bỏ qua. Các pipeline liệt kê chu trình chạy theo từng độ dài k, và khi một số giá trị k không hoàn tất thì các vòng có kích thước tương ứng nằm ngoài khả năng phát hiện về nguyên tắc.

Trên D₄, tập này không chứa vòng 4 đỉnh nào (phân bố: n₅ = 3, n₆ = 4, n₇ = 3, tổng 60 đỉnh / 10 vòng); với chỉ k = 4 hoàn tất trong run chính, trần Recall bằng 0,00, khớp đúng với Recall quan sát được ở Bảng 4b. k = 5 timeout và k = 6–7 chạm transaction-memory ceiling nên không được tính vào phạm vi hoàn tất; theo giao thức đánh giá ở Mục 3.3, các dòng đã stream trước timeout chỉ được giữ để chẩn đoán và không dùng để tính trần Recall hay các metric chính.

Trên D₅, Cypher Pattern chỉ hoàn tất k = 4, và tập này có đúng một vòng 4 đỉnh (phân bố: n₄ = 1, n₅ = 2, n₆ = 5, n₇ = 2, tổng 58 đỉnh / 10 vòng); phương pháp phục hồi đúng vòng đó. Recall 0,10 vì vậy bằng 100% trần lý thuyết trong phạm vi k đã hoàn tất. Diễn giải Recall 0,10 như một thất bại là không chính xác; hạn chế thực sự nằm ở việc các truy vấn k lớn hơn không hoàn tất trong run chính (heap 8 GiB, timeout 120 giây), không phải ở cấu hình heap 1 GiB lịch sử vốn đã bị loại khỏi nguồn số liệu chính (Mục 3.5).

## **_4.5. Kiểm chứng rò rỉ nhãn qua thuộc tính số tiền_**

Kiểm tra một biến được chạy trực tiếp trên các CSV nguồn đã đóng băng. Với D₁–D₃, nhãn giao dịch là is_fraud, nhãn cặp có hướng bằng 1 nếu cặp chứa ít nhất một giao dịch gian lận, và nhãn tài khoản là fraud_ring_member. AUC được tính theo thống kê thứ hạng có xử lý giá trị đồng hạng. Hash SHA-256 của các CSV được lưu cùng artifact kiểm tra để tránh trộn phiên bản.

**Bảng 5. Phân bố số tiền và khả năng phân tách nhãn** *(n = số giao dịch trong mẫu)*

| Tập    | AUC      | n         | Nền: trung vị | Nền: Q3   | Nền: max  | GL: trung vị | GL: Q3     | GL: max    |
| ------ | -------- | --------- | ------------- | --------- | --------- | ------------ | ---------- | ---------- |
| **D₁** | 0,7939   | —         | 4.133,86      | 22.251,82 | 44.716,15 | 26.895,26    | 39.923,68  | 39.923,68  |
| **D₂** | 0,9999   | —         | 0,07          | 1.114,60  | 48.680,35 | 151.246,80   | 287.040,31 | 729.056,34 |
| **D₃** | 1,0000   | —         | 0,07          | 1.109,69  | 49.525,84 | 139.440,05   | 238.207,61 | 467.506,19 |
| **D₄** | 0,5499   | —         | 254,05        | 376,61    | 500,00    | 239,02       | 441,07     | 695,54     |
| **D₅** | 0,6838   | —         | 254,94        | 377,92    | 500,00    | 370,58       | 503,01     | 667,28     |

Phân bố số tiền của giao dịch nền bị chặn cứng tại 500,00 ở D₄ và D₅, trong khi giao dịch gian lận đạt tới 695,54 và 667,28. Trong snapshot quan sát, không có giao dịch nền nào vượt ngưỡng 500; vì vậy, các giao dịch nằm trên ngưỡng này có precision quan sát bằng 1 trong mẫu, không phải bảo đảm phân tách tuyệt đối ngoài mẫu. Ở D₅, khoảng một phần tư số giao dịch gian lận nằm trên ngưỡng này, và AUC của bộ phân loại một biến đạt 0,6838, cao hơn mức 0,5 của bộ phân loại ngẫu nhiên. Bài không dùng từ "có ý nghĩa thống kê" vì chưa thực hiện khoảng tin cậy hoặc kiểm định giả thuyết cho AUC.

**Cơ chế rò rỉ amount trên D₁–D₃.** Cơ chế của AUC ≈ 1 trên D₂ và D₃ rất khác với D₄–D₅. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Đây mới là cơ chế đằng sau AUC 0,9999 và 1,0000: một bộ phân loại ngưỡng đơn giản (amount > 1, hoặc amount > 10) đã phân biệt gần như hoàn hảo hai lớp mà không cần đồ thị. Giá trị 0,07 ở cả hai tập là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý — số tiền giao dịch nền quá gần bằng không trong một mạng giao dịch ngân hàng.

Tương tự, D₁ có AUC = 0,7939 — cũng rò rỉ đáng kể và chưa được nhắc tới ở bất kỳ đâu trong bài. Trung vị số tiền giao dịch nền của D₁ là 4.133,86, trong khi trung vị giao dịch gian lận là 26.895,26; giao dịch gian lận tối đa chỉ 39.923,68, không vượt ngưỡng nền, nên mức chênh chỉ hai bậc độ lớn. D₁ được sinh bởi cùng bộ sinh với D₂–D₃ và có cơ chế rò rỉ cùng nguồn gốc.

**Mối quan hệ giữa hai kênh rò rỉ.** Hai kênh rò rỉ — amount (Mục 4.5) và do tiền xử lý (Mục 4.2) — không độc lập về nguyên nhân trên D₁–D₃. Ở D₁–D₃, cạnh nền có khoảng 1 giao dịch còn cạnh ring có 7–17 giao dịch, nên min_pair ≥ 3 là bộ phân loại ring/nền hoàn hảo ở mức cạnh; cùng lúc, số tiền của ring lớn hơn nền sáu bậc. Cả hai kênh bắt nguồn từ việc bộ sinh D₁–D₃ đặt ring vào một chế độ tham số hoàn toàn tách rời nền. Bài gọi đây là "cơ chế tách biệt" ở mức kênh quan sát; nguyên nhân chung — bộ sinh tạo hai quần thể tham số riêng biệt — là phát biểu mạnh hơn và góp phần giải thích tại sao cả hai kênh cùng xuất hiện trên cùng ba tập.

Phép hiệu chỉnh sinh số tiền vì vậy chưa loại bỏ hoàn toàn rò rỉ nhãn. Cypher Optimized có các tham số min_pair_amount và min_total_amount; mặc định của source là 0, nhưng khi đặt giá trị dương chúng thay đổi tập cạnh hoặc tập candidate. Do đó mọi run dùng amount phải công bố command và được đối chiếu với một run không lọc trên cùng snapshot. Khi chưa có ablation đó, kết quả amount-assisted không được dùng làm bằng chứng thuần cấu trúc. Kiểm tra hiện tại minh họa amount trên cả năm tập (Bảng 5); đây chưa phải exhaustive leakage audit trên các thuộc tính khác như pair count/transaction count, kyc_risk_score hoặc monthly_transaction_count ở các tập có thuộc tính tương ứng.

# **5\. Thảo luận**

## **_5.1. Bốn kiểm tra bắt buộc khi thiết kế đối chuẩn tổng hợp_**

Từ các phát hiện trên, nghiên cứu đề xuất bốn kiểm tra nên được thực hiện và báo cáo trước khi công bố bất kỳ kết quả đối chuẩn nào trên dữ liệu tổng hợp.

- Rò rỉ do tiền xử lý: So sánh tập đỉnh và tập cạnh trước/sau tiền xử lý với ground truth. Ngoài số lượng đỉnh, cần tính tỷ lệ đỉnh ground truth trong đồ thị sau lọc và tỷ lệ background vertices còn lại.
- Cấu trúc liên thông: Báo cáo phân bố kích thước SCC, tỷ lệ đỉnh nằm trong Giant SCC và vị trí của từng ground-truth motif trước và sau preprocessing.
- Rò rỉ thuộc tính: Đánh giá từng thuộc tính cạnh và thuộc tính đỉnh bằng AUC một biến, phân bố giá trị và kiểm tra phần đuôi. AUC gần 0,5 không đủ để loại trừ leakage nếu tồn tại một khoảng giá trị chỉ xuất hiện ở một lớp.
- Độ nhạy với hậu xử lý: Báo cáo riêng kết quả trước và sau bước chuẩn hóa/gộp ứng viên. Một pipeline có thể phát hiện đúng ground-truth motif ở mức candidate nhưng mất nó sau merging; nếu chỉ báo cáo output cuối cùng, hai nguyên nhân này không thể phân biệt.

## **_5.2. Hàm ý cho phương pháp phát hiện_**

Hai hàm ý được rút ra trong phạm vi các snapshot khảo sát. Thứ nhất, phân hoạch SCC không đủ để phân giải các fraud ring khi nhiều ring cùng nằm trong một component vượt cửa sổ tiền tuyển. Thứ hai, liệt kê chu trình không tự động bảo đảm giữ được ranh giới ring sau hậu xử lý. Nhận xét 1 chỉ chứng minh rằng mỗi overlap cluster nằm trọn trong một SCC; số lượng và kích thước overlap cluster bên trong SCC phải được đo thực nghiệm. Trong run chính, phép gộp làm giảm số candidate của Cypher Pattern nhưng không làm mất true-positive quan sát được.

Hướng khắc phục khả dĩ là thay gộp bắc cầu bằng tiêu chí gộp có ràng buộc — chỉ gộp khi mức chồng lấn vượt ngưỡng tương đối — hoặc giữ nguyên ứng viên thô và xếp hạng theo điểm số. Đánh giá các phương án này nằm ngoài phạm vi bài báo.

## **_5.3. Hàm ý đối với hệ thống ngân hàng Việt Nam_**

Nghiên cứu không sử dụng dữ liệu giao dịch liên ngân hàng Việt Nam và vì vậy không thể trực tiếp ước lượng bậc trung bình, cấu trúc SCC hoặc tỷ lệ liên kết hai chiều của mạng thực. D₄–D₅ chỉ được xem như các kịch bản tổng hợp dùng để khảo sát độ nhạy của pipeline khi fraud ring nằm trong một component lớn. Hàm ý thực hành của nghiên cứu là một quy trình kiểm định: trước khi triển khai, tổ chức cần đo cấu trúc SCC trên dữ liệu nội bộ, đánh giá tác động của các ngưỡng tiền xử lý và báo cáo riêng detector output, before-merge output và after-merge output. Chỉ sau khi các đặc trưng này được xác nhận trên dữ liệu thực mới có thể suy luận về khả năng áp dụng của từng pipeline.

# **6\. Hạn chế**

Thứ nhất, kết quả dựa hoàn toàn trên dữ liệu tổng hợp; các kết luận cấu trúc chỉ chuyển sang mạng thực trong chừng mực mạng thực cũng có bậc trung bình đủ lớn để Giant SCC hình thành, thực tế là từ khoảng 3 trở lên và tài khoản gian lận có giao dịch hai chiều với mạng nền. Bốn pipeline lại chạy trên các phép chiếu đồ thị khác nhau, nên khác biệt quan sát được là khác biệt giữa các pipeline hoàn chỉnh chứ không phải giữa các thuật toán; bài báo không đưa ra kết luận xếp hạng.

Thứ hai, trần Recall ở Mục 4.4 bị giới hạn bởi cấu hình run chính: Cypher Pattern hoàn tất k=4 trên D₄–D₅ nhưng timeout ở k=5 với giới hạn 120 giây và chạm transaction-memory ceiling ở k=6–7. Trần Recall 0 trên D₄ và 0,10 trên D₅ phản ánh phạm vi truy vấn hoàn tất được, không phải khả năng nội tại của bài toán. Mỗi cấu hình chỉ chạy một lần nên runtime chỉ mang tính mô tả. Run chính dùng initial heap 2 GiB, max heap 8 GiB, page cache 1 GiB và transaction-memory ceiling 5,60 GiB; artifact lịch sử dùng 1 GiB chỉ được giữ để chẩn đoán, không phải nguồn số liệu của Bảng 4. Cần chạy lại k=5 với timeout ≥300 giây (hoặc nâng bộ nhớ) để xác định trần Recall thực sự.

Thứ ba, D₅ có 830.028 cặp phân biệt trên 900.058 giao dịch, tức khoảng 7,8% giao dịch lặp giữa các cặp đã có, trong khi D₄ hầu như không có hiện tượng này dù cùng bộ sinh và cùng mật độ; nguyên nhân chưa xác định. Các tập dữ liệu cũng tồn tại nhiều phiên bản sinh trong quá trình nghiên cứu; cần đối chiếu hash SHA-256 giữa snapshot dùng cho Mục 4.5 với snapshot dùng cho Mục 4.1 và 4.2 trên D₁–D₃ để đảm bảo tính nhất quán của kết quả cấu trúc.

# **7\. Kết luận**

Nghiên cứu đã cho thấy chất lượng của một benchmark phát hiện fraud ring không chỉ phụ thuộc vào thuật toán phát hiện mà còn phụ thuộc mạnh vào cấu trúc dữ liệu, tiền xử lý, tiêu chí tiền tuyển và hậu xử lý.

Kết quả thứ nhất là một kênh rò rỉ ground-truth độc lập qua thuộc tính amount trên D₂ và D₃ (AUC một biến 0,9999 và 1,0000): một bộ phân loại ngưỡng đơn giản trên số tiền giao dịch, không cần đồ thị, đã phân biệt gần như hoàn hảo fraud với background. Trung vị số tiền giao dịch nền của D₂ và D₃ bằng 0,07, trong khi trung vị giao dịch gian lận lần lượt là 151.246 và 139.440 — chênh sáu bậc độ lớn. Giá trị 0,07 là dấu hiệu bất thường chứ không phải lựa chọn thiết kế hợp lý. D₁ cũng có AUC = 0,7939, chưa được nhắc tới ở bất kỳ đâu trong bài. Kênh này có cơ chế tách biệt với kênh rò rỉ do tiền xử lý mô tả dưới đây, và cho thấy D₁, D₂, D₃ không đủ tư cách làm benchmark đánh giá năng lực phát hiện dựa trên thuộc tính. Cả hai kênh rò rỉ trên D₁–D₃ bắt nguồn từ cùng một nguyên nhân: bộ sinh tạo hai quần thể tham số riêng biệt cho ring và nền.

Kết quả thứ hai là một dạng rò rỉ ground truth rõ ràng nhưng có phạm vi hẹp trên D₂ và D₃: bộ lọc mặc định theo tần suất cặp của Cypher Optimized loại bỏ toàn bộ tài khoản nền khỏi không gian cạnh đủ điều kiện. Điều này làm giảm ý nghĩa của Precision của pipeline đó nếu được diễn giải như khả năng phân biệt fraud với background; kết luận không được mở rộng sang ba pipeline không dùng bộ lọc.

Kết quả thứ ba là sự xuất hiện của Giant SCC trên các benchmark có mật độ liên kết cao. Null model đồ thị ngẫu nhiên có hướng cung cấp một mốc giải thích hữu ích cho các tập được khảo sát, nhưng được sử dụng như một approximation có điều kiện thay vì một quy luật phổ quát của mạng giao dịch.

Kết quả thứ tư là vị trí suy giảm phải được xác định theo từng giai đoạn. GDS SCC và Hybrid NetworkX trả kết quả rỗng trên D₄-D₅ do Giant SCC vượt cửa sổ tiền tuyển; Cypher Pattern sinh transaction paths nhưng chỉ k=4 hoàn tất, sau đó module đánh giá bên ngoài mới thực hiện deduplication và overlap-merging. Run hiện tại cho thấy số cảnh báo thay đổi sau merge nhưng không có TP bị mất do merge. Vì vậy detector output, before-merge metrics và after-merge metrics cần được báo cáo riêng.

Từ đó, nghiên cứu khuyến nghị rằng các benchmark fraud-ring tổng hợp cần công bố không chỉ Precision, Recall và F1-Score, mà còn cấu trúc SCC trước/sau preprocessing, mức leakage của thuộc tính, output trước/sau consolidation và độ nhạy với cấu hình tài nguyên.

Công việc tiếp theo sẽ tập trung vào ba hướng: lặp lại thí nghiệm trên nhiều seed và cấu hình tài nguyên; đánh giá các chiến lược consolidation có ràng buộc thay cho gộp bắc cầu đơn giản; và kiểm chứng các chẩn đoán cấu trúc trên mạng giao dịch thực.

# **Tài liệu tham khảo**

ACFE. (2026). Occupational Fraud 2026: A Report to the Nations. Association of Certified Fraud Examiners.

Akoglu, L., Tong, H., & Koutra, D. (2015). Graph based anomaly detection and description: A survey. Data Mining and Knowledge Discovery, 29(3), 626–688.

Altman, E., Blanuša, J., von Niederhäusern, L., Egressy, B., Anghel, A., & Atasu, K. (2023). Realistic synthetic financial transactions for anti-money laundering models. Advances in Neural Information Processing Systems, 36.

Bollobás, B. (2001). Random Graphs (2nd ed.). Cambridge University Press.

Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. ACM Computing Surveys, 41(3), 1–58.

Dorogovtsev, S. N., Mendes, J. F. F., & Samukhin, A. N. (2001). Giant strongly connected component of directed networks. Physical Review E, 64(2), 025101.

Europol. (2023). The other side of the coin: An analysis of financial and economic crime. European Union Agency for Law Enforcement Cooperation.

FATF. (2026). The FATF Recommendations: International standards on combating money laundering and the financing of terrorism and proliferation. Financial Action Task Force.

GAO. (2024). Fraud risk management: 2018–2022 data show federal government could lose an estimated \$233 billion to \$521 billion annually. U.S. Government Accountability Office, GAO-24-105833.

Johnson, D. B. (1975). Finding all the elementary circuits of a directed graph. SIAM Journal on Computing, 4(1), 77–84.

Motie, S., & Raahemi, B. (2024). Financial fraud detection using graph neural networks: A systematic review. Expert Systems with Applications, 240, 122156.

NetworkX Developers. (2023). NetworkX 3.1 documentation. <https://networkx.org>

Newman, M. E. J. (2018). Networks (2nd ed.). Oxford University Press.

Newman, M. E. J., Strogatz, S. H., & Watts, D. J. (2001). Random graphs with arbitrary degree distributions and their applications. Physical Review E, 64(2), 026118.

Santander AI Lab. (2026). gen-fraud-graph: Synthetic fraud graph generator (v0.1.0, Apache-2.0). GitHub. <https://github.com/SantanderAI/gen-fraud-graph> (truy cập ngày 09/07/2026; commit f52f6bf)

Suzumura, T., & Kanezashi, H. (2021). AMLSim: A multi-agent simulator for anti-money laundering. GitHub. <https://github.com/IBM/AMLSim> (truy cập ngày 07/08/2026)

Tang, J., Hua, F., Gao, Z., Zhao, P., & Li, J. (2023). GADBench: Revisiting and benchmarking supervised graph anomaly detection. Advances in Neural Information Processing Systems, 36.

Tarjan, R. (1972). Depth-first search and linear graph algorithms. SIAM Journal on Computing, 1(2), 146–160.

Wells, J. T. (2017). Corporate Fraud Handbook: Prevention and Detection (5th ed.). John Wiley & Sons.
