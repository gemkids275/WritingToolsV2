# Kế hoạch Đa ngôn ngữ cho macOS (L10n)

Tài liệu này phác thảo các bước cần thiết để tích hợp hỗ trợ đa ngôn ngữ (Tiếng Việt, Tiếng Nhật, Tiếng Trung) cho ứng dụng trên nền tảng macOS, đảm bảo tính nhất quán với phiên bản Windows & Linux.

## 1. Phân tích hiện trạng
- **Công nghệ**: Sử dụng SwiftUI và Xcode String Catalogs (`Localizable.xcstrings`).
- **Ngôn ngữ hiện có**: Anh (en), Đức (de), Tây Ban Nha (es), Pháp (fr).
- **Ngôn ngữ cần bổ sung**: Tiếng Việt (vi), Tiếng Nhật (ja), Tiếng Trung Giản thể (zh-Hans).
- **Ghi chú**: Windows cũng có locale `it` (Tiếng Ý) nhưng **không** cần sync cho macOS lần này.

## 2. Các bước thực hiện

### Bước 1: Rà soát và bọc chuỗi trong mã nguồn Swift
Cần kiểm tra các thư mục trong `macOS/WritingTools/Views/`:
- `About/`, `Chat/`, `Commands/`, `Onboarding/`, `Popup/`, `Settings/`.
- Đảm bảo tất cả các chuỗi hiển thị đều được bọc trong các thành phần SwiftUI hỗ trợ Localization như `Text("...")`, `Label("...", systemImage: "...")`, hoặc sử dụng `String(localized: "...")`.
- **Lưu ý**: SwiftUI `Text("Literal string")` đã tự động tra cứu `.xcstrings` — chỉ cần đảm bảo chuỗi không bị nối động (string interpolation) mà không có `String(localized:)`.

### Bước 2: Đồng bộ hóa bản dịch từ Windows + Auto-translate chuỗi còn thiếu
Để đảm bảo tính nhất quán, sử dụng bản dịch đã hoàn thiện từ thư mục `Windows_and_Linux/locales/`.
- **Nguồn**: Các tệp `messages.po` tại `Windows_and_Linux/locales/{vi,ja,zh}/LC_MESSAGES/messages.po`.
- **Đích**: Tệp `macOS/WritingTools/Localizable.xcstrings`.

**Phương pháp thực hiện**:
Sử dụng script Python (`sync_macos_l10n.py`) để:
1. Đọc nội dung JSON từ `Localizable.xcstrings`.
2. Đọc các bản dịch từ tệp `.po` của Windows.
3. Ghép nối các chuỗi dựa trên `msgid` (tiếng Anh) và Key trong `.xcstrings`.
4. Với các chuỗi **không có** trong `.po` (macOS-only UI strings), **agent tự dịch** sang `vi`, `ja`, `zh-Hans`.
5. Ghi lại tệp `.xcstrings` với đầy đủ bản dịch cho 3 ngôn ngữ.

**Lưu ý quan trọng**:
- File `.po` của Windows dùng locale `zh`, trong khi `.xcstrings` cần `zh-Hans`. Script phải map đúng.
- Script cần dùng `json.dumps` với `ensure_ascii=False` và giữ nguyên thứ tự key gốc để không làm hỏng file.
- Nên có chế độ `--dry-run` để preview trước khi ghi đè.

### Bước 3: Thêm Language Picker vào Settings

**Cơ chế hoạt động**:
- App tự **detect ngôn ngữ hệ thống** làm mặc định (`Locale.current.language.languageCode`).
- Người dùng có thể **ghi đè** bằng dropdown trong Settings → lưu vào `AppSettings` (UserDefaults).
- Khi thay đổi ngôn ngữ, gọi `UserDefaults.standard.set([languageCode], forKey: "AppleLanguages")` và **restart app** để áp dụng.

**Vị trí UI**: Thêm section "Language" vào `GeneralSettingsPane.swift` (không phải `SettingsView.swift`).

**Danh sách ngôn ngữ hỗ trợ**:
```
English (en), Deutsch (de), Español (es), Français (fr),
Tiếng Việt (vi), 日本語 (ja), 中文简体 (zh-Hans)
```

**AppSettings**: Thêm property `preferredLanguage: String?` (nil = follow system).

### Bước 4: Cấu hình Project Xcode
- Thêm `vi`, `ja`, `zh-Hans` vào mục `Localizations` trong **Project settings** (file `macOS/WritingTools.xcodeproj/project.pbxproj` sẽ được cập nhật tự động khi thêm qua Xcode UI).
- Kiểm tra `Info.plist` để đảm bảo `CFBundleLocalizations` liệt kê đủ các ngôn ngữ mới.

## 3. Danh sách các tệp trọng tâm
- `macOS/WritingTools/Localizable.xcstrings`: Tệp lưu trữ bản dịch chính (~8900 dòng).
- `macOS/WritingTools/App/AppDelegate.swift`: Entry point, Menu Bar và các hội thoại hệ thống.
- `macOS/WritingTools/App/AppSettings.swift`: Thêm property `preferredLanguage`.
- `macOS/WritingTools/Views/Settings/Panes/GeneralSettingsPane.swift`: Thêm Language Picker UI.
- `macOS/WritingTools.xcodeproj/project.pbxproj`: Khai báo ngôn ngữ mới.
- `sync_macos_l10n.py` (script mới): Script đồng bộ bản dịch từ `.po` + agent tự dịch các chuỗi còn thiếu.

## 4. Dự kiến khó khăn
- **Restart app**: Thay đổi ngôn ngữ yêu cầu restart để `AppleLanguages` có hiệu lực — cần hiển thị thông báo rõ ràng cho người dùng.
- **Detect ngôn ngữ mặc định**: Nếu ngôn ngữ hệ thống không nằm trong danh sách hỗ trợ, fallback về `en`.
- **Định dạng JSON của .xcstrings**: Script phải giữ nguyên cấu trúc file Xcode, dùng `ensure_ascii=False`.
- **Số lượng chuỗi cần dịch thủ công**: Có thể lớn nếu nhiều UI macOS-only — agent cần dịch theo ngữ cảnh UI, không dịch literal.

## 5. Xác minh (Verification)
- Chạy script `sync_macos_l10n.py` và kiểm tra log: tất cả chuỗi phải có trạng thái `translated` (không còn `needs_review` hay thiếu).
- Mở tệp `.xcstrings` trong Xcode để kiểm tra các cột `vi`, `ja`, `zh-Hans` đã được điền đầy đủ.
- Trong app, chuyển ngôn ngữ sang Tiếng Việt/Nhật/Trung qua dropdown Settings → xác nhận app restart và hiển thị đúng.
- Kiểm tra fallback: đặt ngôn ngữ hệ thống về một ngôn ngữ không hỗ trợ (ví dụ: Korean) → app phải hiển thị tiếng Anh.

---
*Kế hoạch này được lập vào ngày 21/04/2026 bởi Antigravity AI. Cập nhật lần cuối: 21/04/2026.*
