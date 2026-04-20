# Kế hoạch Đa ngôn ngữ cho macOS (L10n)

Tài liệu này phác thảo các bước cần thiết để tích hợp hỗ trợ đa ngôn ngữ (Tiếng Việt, Tiếng Nhật, Tiếng Trung) cho ứng dụng trên nền tảng macOS, đảm bảo tính nhất quán với phiên bản Windows & Linux.

## 1. Phân tích hiện trạng
- **Công nghệ**: Sử dụng SwiftUI và Xcode String Catalogs (`Localizable.xcstrings`).
- **Ngôn ngữ hiện có**: Anh (en), Đức (de), Tây Ban Nha (es), Pháp (fr).
- **Ngôn ngữ cần bổ sung**: Tiếng Việt (vi), Tiếng Nhật (ja), Tiếng Trung (zh-Hans).

## 2. Các bước thực hiện

### Bước 1: Rà soát và bọc chuỗi trong mã nguồn Swift
Cần kiểm tra các thư mục trong `macOS/WritingTools/Views/`:
- `About/`, `Chat/`, `Commands/`, `Onboarding/`, `Popup/`, `Settings/`.
- Đảm bảo tất cả các chuỗi hiển thị đều được bọc trong các thành phần SwiftUI hỗ trợ Localization như `Text("...")`, `Label("...", systemImage: "...")`, hoặc sử dụng `String(localized: "...")`.

### Bước 2: Đồng bộ hóa bản dịch từ Windows
Để đảm bảo tính nhất quán, chúng ta sẽ sử dụng bản dịch đã hoàn thiện từ thư mục `Windows_and_Linux/locales/`.
- **Nguồn**: Các tệp `messages.po` (vi, ja, zh).
- **Đích**: Tệp `macOS/WritingTools/Localizable.xcstrings`.

**Phương pháp thực hiện**:
Sử dụng một script Python trung gian (`sync_macos_l10n.py`) để:
1. Đọc nội dung JSON từ `Localizable.xcstrings`.
2. Đọc các bản dịch từ tệp `.po` của Windows.
3. Ghép nối các chuỗi dựa trên `msgid` (tiếng Anh) và Key trong `.xcstrings`.
4. Ghi lại tệp `.xcstrings` với các ngôn ngữ mới bổ sung.

### Bước 3: Cấu hình Project Xcode
- Đảm bảo dự án Xcode đã khai báo hỗ trợ các ngôn ngữ mới trong phần `Localizations` của Project settings.
- Kiểm tra `Info.plist` để đảm bảo các quyền (Permissions) và tên ứng dụng cũng được đa ngôn ngữ hóa nếu cần.

## 3. Danh sách các tệp trọng tâm
- `macOS/WritingTools/Localizable.xcstrings`: Tệp lưu trữ bản dịch chính.
- `macOS/WritingTools/writing_toolsApp.swift`: Giao diện Menu Bar và các hội thoại hệ thống.
- `macOS/WritingTools/Views/Settings/SettingsView.swift`: Giao diện cài đặt (cần thêm dropdown chọn ngôn ngữ).

## 4. Dự kiến khó khăn
- **Định dạng JSON của .xcstrings**: Cần cẩn thận khi ghi đề file để không làm hỏng cấu trúc của Xcode.
- **Sự khác biệt về UI**: Một số chuỗi bên Windows có thể không tồn tại hoặc có tên gọi khác bên macOS (ví dụ: "Window" vs "View").

## 5. Xác minh (Verification)
- Mở tệp `.xcstrings` trong Xcode (nếu có môi trường) để kiểm tra các cột `vi`, `ja`, `zh` đã được điền đầy đủ.
- Chạy ứng dụng trên macOS (giả lập hoặc máy thật) và thay đổi ngôn ngữ hệ thống hoặc trong cài đặt ứng dụng để kiểm tra.

---
*Kế hoạch này được lập vào ngày 21/04/2026 bởi Antigravity AI.*
