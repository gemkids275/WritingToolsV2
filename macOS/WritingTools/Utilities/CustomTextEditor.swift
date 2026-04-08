import SwiftUI
import AppKit

/// NSTextView-backed text editor with a thin overlay scrollbar.
struct CustomTextEditor: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String = ""
    var onSubmit: (() -> Void)? = nil

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, onSubmit: onSubmit)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true
        scrollView.scrollerStyle = .overlay
        scrollView.verticalScroller?.controlSize = .mini
        scrollView.drawsBackground = false
        scrollView.borderType = .noBorder

        let textView = PasteAwareTextView()
        textView.isEditable = true
        textView.isSelectable = true
        textView.allowsUndo = true
        textView.isRichText = false
        textView.font = .systemFont(ofSize: 14)
        textView.backgroundColor = .clear
        textView.drawsBackground = false
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(width: 0, height: CGFloat.greatestFiniteMagnitude)
        textView.delegate = context.coordinator
        textView.onSubmit = onSubmit
        context.coordinator.textView = textView

        scrollView.documentView = textView
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? PasteAwareTextView else { return }
        if textView.string != text {
            let selected = textView.selectedRanges
            textView.string = text
            textView.selectedRanges = selected
        }
        textView.onSubmit = onSubmit
        context.coordinator.updatePlaceholder(textView, placeholder: placeholder, text: text)
    }

    class Coordinator: NSObject, NSTextViewDelegate {
        @Binding var text: String
        let onSubmit: (() -> Void)?
        weak var textView: NSTextView?
        private var placeholderLabel: NSTextField?

        init(text: Binding<String>, onSubmit: (() -> Void)?) {
            _text = text
            self.onSubmit = onSubmit
        }

        func textDidChange(_ notification: Notification) {
            guard let tv = notification.object as? NSTextView else { return }
            text = tv.string
            updatePlaceholder(tv, placeholder: "", text: tv.string)
        }

        func updatePlaceholder(_ textView: NSTextView, placeholder: String, text: String) {
            // Use textView's superview (NSClipView) area for placeholder
            if text.isEmpty && !placeholder.isEmpty {
                if placeholderLabel == nil {
                    let label = NSTextField(labelWithString: placeholder)
                    label.font = .systemFont(ofSize: 14)
                    label.textColor = .placeholderTextColor
                    label.isEditable = false
                    label.isBordered = false
                    label.backgroundColor = .clear
                    label.translatesAutoresizingMaskIntoConstraints = false
                    textView.addSubview(label)
                    NSLayoutConstraint.activate([
                        label.leadingAnchor.constraint(equalTo: textView.leadingAnchor, constant: 4),
                        label.topAnchor.constraint(equalTo: textView.topAnchor, constant: 0),
                    ])
                    placeholderLabel = label
                }
                placeholderLabel?.stringValue = placeholder
                placeholderLabel?.isHidden = false
            } else {
                placeholderLabel?.isHidden = true
            }
        }
    }
}

// MARK: - Paste-aware NSTextView

private class PasteAwareTextView: NSTextView {
    var onSubmit: (() -> Void)?

    override func validateMenuItem(_ menuItem: NSMenuItem) -> Bool {
        if menuItem.action == #selector(paste(_:)) {
            let pb = NSPasteboard.general
            if pb.data(forType: .tiff) != nil || pb.data(forType: .png) != nil {
                return true
            }
            if let urls = pb.readObjects(forClasses: [NSURL.self], options: nil) as? [URL], !urls.isEmpty {
                return true
            }
        }
        return super.validateMenuItem(menuItem)
    }

    override func keyDown(with event: NSEvent) {
        let isReturn = event.keyCode == 36 // Return key
        let isAltPressed = event.modifierFlags.contains(.option)

        if isReturn {
            let isShiftPressed = event.modifierFlags.contains(.shift)
            if isAltPressed || isShiftPressed {
                insertNewline(nil)
            } else {
                onSubmit?()
            }
            return
        }
        super.keyDown(with: event)
    }

    override func paste(_ sender: Any?) {
        let pb = NSPasteboard.general

        // Image from clipboard (screenshot, drag-drop copy, etc.)
        if let imageData = pb.data(forType: .tiff) ?? pb.data(forType: .png) {
            // Convert TIFF → PNG for consistent handling
            let data: Data
            if let tiff = pb.data(forType: .tiff),
               let rep = NSBitmapImageRep(data: tiff),
               let png = rep.representation(using: .png, properties: [:]) {
                data = png
            } else {
                data = imageData
            }
            Task { @MainActor in
                AppState.shared.customAttachments.append(.image(data))
            }
            return
        }

        // Image file URL (e.g. drag a file from Finder then paste)
        if let urls = pb.readObjects(forClasses: [NSURL.self], options: nil) as? [URL], !urls.isEmpty {
            Task { @MainActor in
                let rejected = urls.filter { !AppState.shared.addAttachment(from: $0) }.map { $0.lastPathComponent }
                if !rejected.isEmpty {
                    let alert = NSAlert()
                    alert.messageText = "Unsupported File(s)"
                    alert.informativeText = "\(rejected.joined(separator: ", "))\n\nOnly images and plain text files are supported."
                    alert.alertStyle = .warning
                    alert.runModal()
                }
            }
            return
        }

        // Default: plain text paste
        super.paste(sender)
    }
}
