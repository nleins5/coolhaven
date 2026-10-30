# CoolHaven — tối ưu vị trí điểm tránh nóng bằng thuật toán di truyền

## Câu hỏi của project

Một thành phố chỉ đủ nguồn lực mở năm điểm tránh nóng. Chọn địa điểm nào để người dân dễ tiếp cận, khu vực ít được phục vụ vẫn có phương án và chi phí không vượt ngân sách? Nếu một điểm đóng cửa giữa đợt nắng nóng, kế hoạch có còn tốt không?

CoolHaven mô phỏng câu hỏi đó bằng **bộ gene nhị phân và thuật toán di truyền đa mục tiêu NSGA-II**. Điểm nhấn nằm ở sự kết hợp giữa vị trí cơ sở, mức phục vụ thấp nhất theo khu vực và kiểm tra đóng cửa từng điểm. Đây là một ứng dụng học tập có thực nghiệm, không phải tuyên bố phát minh thuật toán mới.

## Liên hệ với bài đọc

Tài liệu nền: *Step-by-Step Genetic Algorithm*, AI VIET NAM, All-in-One Course 2026, do Anh-Khoi Nguyen, Yen-Linh Vu, Dinh-Thang Duong và Quang-Vinh Dinh biên soạn. Tệp đọc gồm 20 trang, được cung cấp riêng; project không phân phối lại PDF.

| Nội dung trong bài đọc | Cách dùng trong project |
|---|---|
| Bộ gene nhị phân, One-Max (trang 3, 9) | 24 bit ứng với 24 địa điểm; bit 1 nghĩa là mở điểm |
| Khởi tạo quần thể (trang 4, 9) | Lấy ngẫu nhiên đúng số điểm và sửa vi phạm ngân sách |
| Fitness phụ thuộc ngữ cảnh (trang 4–5) | Ba mục tiêu: tiếp cận khi có sự cố, mức phục vụ thấp nhất và chi phí |
| Tournament selection (trang 5–6) | Chọn cha mẹ bằng Pareto rank, sau đó crowding distance |
| Uniform crossover (trang 7, 13–14) | Chọn từng bit từ hai cha mẹ bằng mặt nạ xác suất 0,5 |
| Mutation (trang 7–8, 15) | Hoán đổi một điểm được chọn với một điểm chưa được chọn |
| Elitism (trang 9, 11) | Giữ cá thể tốt từ tập cha mẹ và con, lưu thêm Pareto archive |
| Điều kiện dừng (trang 8) | Dừng sau số thế hệ cấu hình trước |

One-Max khuyến khích bật tất cả bit. Ở đây, bật tất cả là không hợp lệ vì số điểm và ngân sách có giới hạn. Vì thế không thể thay fitness bằng tổng bit; cần xây dựng mô hình cho đúng bài toán.

## Dữ liệu và biến quyết định

Bộ dữ liệu mặc định hoàn toàn **mô phỏng**, gồm 72 cụm dân cư, sáu khu vực và 24 địa điểm ứng viên. Vị trí dùng hệ tọa độ km giả lập; ngân sách 210 đơn vị quy hoạch; cần chọn đúng năm điểm. Không sử dụng dữ liệu dân cư, y tế hay thời tiết quan trắc thực tế.

Mỗi cụm có dân số, hệ số dễ bị tổn thương và hệ số phơi nhiễm nhiệt. Trọng số của cụm là:

```text
trọng số = dân số × (1 + hệ số dễ bị tổn thương) × hệ số nhiệt
```

Điểm tiếp cận giảm tuyến tính theo khoảng cách, về 0 tại giới hạn đi bộ. Mỗi cụm dùng điểm đang hoạt động có mức tiếp cận tốt nhất. **Điểm tiếp cận 53% không có nghĩa là 53% người dân được bảo vệ về sức khỏe.** Đây là một chỉ số toán học chưa hiệu chuẩn thực nghiệm.

## Vì sao dùng đa mục tiêu?

Ba yêu cầu có thể xung đột:

1. Tăng mức tiếp cận trung bình có trọng số trong kịch bản xấu nhất.
2. Tăng mức tiếp cận của khu vực được phục vụ ít nhất trong kịch bản xấu nhất.
3. Giảm chi phí của các điểm được chọn.

NSGA-II không cần gộp ba yêu cầu thành một fitness duy nhất khi tiến hóa. Thuật toán tìm các phương án **không bị trội**: không có phương án đã tìm được nào tốt hơn hoặc bằng ở mọi mục tiêu và tốt hơn ở ít nhất một mục tiêu.

Sau khi có tập Pareto, người dùng mới chọn ưu tiên. Chế độ Balanced dùng trọng số `(0.45, 0.40, 0.15)` trên ba mục tiêu đã chuẩn hóa. Các trọng số này là lựa chọn minh họa; không được suy ra từ khảo sát cộng đồng.

## Xử lý sự cố và ràng buộc

Mỗi phương án được đánh giá trên 26 kịch bản: đi bộ bình thường, nắng nóng làm tăng khoảng cách hiệu dụng 25%, và 24 kịch bản nắng nóng kết hợp đóng một địa điểm. Đóng địa điểm không được chọn không làm thay đổi phương án. Mô hình không giả định xác suất của kịch bản và không kiểm tra nhiều điểm cùng đóng.

Lai ghép có thể tạo ra bộ gene thừa hoặc thiếu điểm. Hàm `repair` đưa số bit 1 về đúng năm. Nếu vượt ngân sách, nó thay điểm đắt nhất đang được chọn bằng điểm rẻ nhất chưa được chọn. Do đã kiểm tra tập năm điểm rẻ nhất có thể chi trả, quá trình này sẽ kết thúc với phương án hợp lệ. Cách sửa tạo thiên lệch về điểm rẻ; báo cáo phương pháp nêu rõ điều đó.

Đột biến là hoán đổi một bit 1 với một bit 0, khác với lật bit độc lập trong One-Max. Cách này giữ nguyên số điểm, nhưng vẫn cần kiểm tra lại ngân sách.

## Kết quả đã chạy

Benchmark dùng năm seed `11, 23, 42, 71, 97`, quần thể 64 và 60 thế hệ. NSGA-II và random search đều có **3.904 lượt chấm phương án mỗi seed**, kể cả phương án lặp. Cả hai dùng cùng cơ chế sửa ràng buộc. Vì thế random search là baseline có cơ chế đề xuất tương ứng, không phải lấy mẫu đều trên mọi nghiệm hợp lệ.

Hypervolume trung bình của NSGA-II là `0.031266`, so với `0.026854` của random search, cao hơn khoảng **16,4% trên bộ dữ liệu này**. Tuy nhiên phương án cân bằng của random search có mức phục vụ thấp nhất theo khu vực cao hơn: `17,864%` so với `15,318%`. Đây là lý do cần xem cả tập Pareto thay vì kết luận một phương án thắng mọi mặt.

Thí nghiệm bỏ kịch bản đóng cửa được lưu tại `results/ablation.csv`. Khi cùng đánh giá lại dưới đầy đủ sự cố, phương án từ mô hình có xét đóng cửa đạt trung bình `15,318%` ở khu vực yếu nhất, so với `13,288%` khi bỏ đóng cửa. Đổi lại, mức tiếp cận toàn thành phố thấp hơn (`53,027%` so với `53,700%`) và chi phí cao hơn (`157` so với `154,2`). Thí nghiệm cho thấy đánh đổi của cấu hình này, không chứng minh mọi chỉ số đều tăng khi thêm kịch bản.

Số liệu thô và cấu hình nằm trong `results/`. Không có kiểm định ý nghĩa thống kê; năm seed trên một thành phố mô phỏng chưa đủ để khái quát cho địa phương khác.

Đối chiếu vét cạn toàn bộ 42.504 tổ hợp cho ra 36.660 phương án hợp lệ, Pareto frontier chính xác gồm 62 phương án và hypervolume `0.031537`. Năm lần chạy NSGA-II đạt trung bình **99,14% hypervolume chính xác**, với khoảng thiếu tương đối từ `0,15%` đến `1,57%`. Xem `results/exact_audit.json`. Độ gần về hypervolume không có nghĩa đã tìm đủ mọi nghiệm Pareto.

## Chạy và trình bày demo trong năm phút

```bash
uv sync --frozen --extra dev
uv run streamlit run app.py
```

1. Mở **Planning studio**, giải thích 24 địa điểm và năm điểm được chọn.
2. Chuyển kịch bản từ bình thường sang đóng một điểm; chỉ ra thay đổi màu của các cụm dân cư.
3. Sang **Trade-off explorer**, giải thích chi phí, mức tiếp cận và màu biểu diễn khu vực yếu nhất.
4. Đổi ưu tiên sang Equity first hoặc Lower cost. Đây là chọn lại phương án trên cùng frontier, không đổi fitness của quá trình tiến hóa.
5. Mở **Inside the algorithm** để trình bày bộ gene, các bước GA và đường hypervolume.
6. Xuất JSON hoặc CSV để chứng minh mỗi phương án có thể kiểm tra lại.

Dashboard mặc định chạy quần thể 48, 35 thế hệ để phản hồi nhanh, khác cấu hình benchmark. Có thể đổi trong Solver settings để khớp thí nghiệm đã lưu.

## Câu hỏi phản biện thường gặp

**Vì sao không dùng vét cạn?** Với bộ mặc định, 24 chọn 5 chỉ có 42.504 tổ hợp nên vét cạn vẫn khả thi và được dùng làm kiểm chứng. Khi tăng số địa điểm, không gian tổ hợp tăng nhanh. GA là cách tìm phương án tốt trong ngân sách tìm kiếm hữu hạn; project này không khẳng định GA nhanh hơn vét cạn trên mọi quy mô.

**Thuật toán có chắc ra nghiệm tối ưu không?** Không. Cùng seed và môi trường khóa phụ thuộc có thể tái lập quá trình, nhưng điều đó không phải bảo đảm tối ưu toàn cục. Script `scripts/audit_exact.py` đối chiếu bộ mặc định với toàn bộ tổ hợp; các kiểm thử nhỏ cũng so với vét cạn.

**Vì sao không dùng fitness có trọng số ngay từ đầu?** Trọng số cố định có thể bỏ qua phương án đánh đổi hữu ích. Giữ nhiều mục tiêu giúp xem các lựa chọn trước khi quyết định ưu tiên. Bước chọn cuối vẫn cần ưu tiên của người sử dụng.

**Dữ liệu có phản ánh TP.HCM không?** Không. Đây là thành phố giả lập. Muốn ứng dụng thực tế cần mạng đường đi bộ, dữ liệu vị trí cơ sở, sức chứa, giờ mở cửa, nhiệt độ và phương pháp xác định nhu cầu phù hợp.

**Điểm mới nằm ở đâu?** Ở cách xây dựng một ứng dụng có stress test đóng cửa, mục tiêu nâng mức phục vụ thấp nhất, giao diện giải thích bộ gene và quy trình thực nghiệm có baseline, ablation, vét cạn. Những thành phần thuật toán đã có trong tài liệu; không nên gọi đây là thuật toán mới.

## Hướng mở rộng

Thêm sức chứa và phân bổ nhu cầu; thay khoảng cách thẳng bằng mạng đường; kiểm tra nhiều điểm cùng đóng; chạy trên nhiều bản đồ; so sánh với mô hình tối ưu nguyên; thử các hàm giảm tiếp cận khác; đưa ưu tiên do người dùng thật cung cấp vào bước chọn phương án.
