# Tổng hợp các tính năng của WritingToolsV2

WritingToolsV2 là một trợ lý viết lách AI mạnh mẽ, được tích hợp sâu vào hệ thống để hỗ trợ người dùng xử lý văn bản nhanh chóng.

## 1. Tính năng cốt lõi (Core Features)
- **Hỗ trợ đa Model AI**: Tích hợp nhiều nhà cung cấp AI như Gemini, OpenAI, Claude... thông qua hệ thống provider linh hoạt.
- **Lệnh AI theo ngữ cảnh (Contextual Commands)**: Cung cấp các lệnh có sẵn như Dịch thuật, Tóm tắt, Sửa lỗi ngữ pháp, Viết lại văn bản, v.v.
- **Phím tắt toàn cầu (Global Hotkeys)**: 
    - `Ctrl + Space` (mặc định): Mở cửa sổ ra lệnh nhanh sau khi bôi đen văn bản.
    - `Ctrl + Alt + T`: Mở cửa sổ kết quả chat gần nhất.
- **Hỗ trợ đa ngôn ngữ**: Giao diện ứng dụng hỗ trợ tiếng Việt, tiếng Anh, tiếng Nhật, tiếng Ý...

## 2. Giao diện & Trải nghiệm người dùng (UI/UX)
- **Cửa sổ Pop-up nhanh**: Giao diện tối giản, tập trung vào việc chọn lệnh và gửi yêu cầu.
- **Cửa sổ kết quả (Chat Result)**:
    - Hiển thị Markdown chuyên nghiệp (bảng, code block, định dạng văn bản).
    - Hỗ trợ Zoom In/Out và Reset Zoom cho nội dung chat.
    - Chế độ streaming (hiển thị kết quả ngay khi AI đang tạo).
- **Hỏi đáp tiếp nối (Follow-up Questions)**: Người dùng có thể chat tiếp với AI để tinh chỉnh kết quả ngay trong cửa sổ kết quả.
- **Giao diện thích ứng (Adaptive UI)**: Tự động chuyển đổi Dark/Light mode theo cài đặt của hệ điều hành.
- **Thông báo cập nhật**: Hệ thống banner nổi bật thông báo khi có phiên bản mới.

## 3. Quản lý nội dung & Đính kèm (Content & Attachments)
- **Đính kèm tệp đa năng**:
    - **Ảnh**: Hỗ trợ đính kèm ảnh (PNG, JPG, v.v.) để AI phân tích.
    - **Văn bản**: Hỗ trợ đính kèm các tệp code, tài liệu văn bản (`.txt`, `.py`, `.md`, v.v.).
- **Hỗ trợ Clipboard mạnh mẽ**:
    - Tự động lấy văn bản đang được bôi đen khi nhấn phím tắt.
    - Hỗ trợ Paste ảnh trực tiếp từ clipboard vào ô chat (Ctrl+V hoặc Menu chuột phải).
- **Xem ảnh phóng to (Image Preview)**: Click vào bất kỳ ảnh nào trong khung chat hoặc thanh đính kèm để xem ảnh ở kích thước gốc trong một cửa sổ modal.
- **Sao chép thông minh**: Nút sao chép từng đoạn hội thoại hoặc sao chép toàn bộ nội dung dưới dạng Markdown.

## 4. Quản lý & Cấu hình (Management)
- **Trình quản lý lệnh (Command Manager)**: Cho phép người dùng thêm, sửa, xóa hoặc thay đổi thứ tự các lệnh AI.
- **Cấu hình AI linh hoạt**: Cho phép ghi đè (override) provider hoặc model cho từng lệnh cụ thể.
- **Xuất/Nhập cấu hình**: Hỗ trợ sao lưu và đồng bộ cài đặt giữa các thiết bị thông qua tệp JSON.
- **Quản lý khóa API**: Giao diện bảo mật để thiết lập các API Key cho từng dịch vụ AI.
