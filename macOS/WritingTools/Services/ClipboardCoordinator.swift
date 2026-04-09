import AppKit
import ImageIO
import UniformTypeIdentifiers

private let logger = AppLogger.logger("ClipboardCoordinator")

extension Notification.Name {
    static let clipboardRestoreSkipped = Notification.Name("clipboardRestoreSkipped")
}

enum ClipboardNotificationUserInfoKey {
    static let expectedChangeCount = "expectedChangeCount"
    static let actualChangeCount = "actualChangeCount"
}

@MainActor
final class ClipboardCoordinator {
    static let shared = ClipboardCoordinator()

    struct CaptureResult {
        let text: String
        let attributedText: NSAttributedString?
        let images: [Data]
        let didChange: Bool
    }

    private var isBusy = false
    private let minCopyDelay: Duration = .milliseconds(50)
    private let pollInterval: Duration = .milliseconds(5)
    private let copyTimeout: TimeInterval = 2.0

    func captureSelection(targetPid: pid_t? = nil) async -> CaptureResult? {
        guard !isBusy else {
            logger.warning("Capture ignored because clipboard operation is already in progress")
            return nil
        }

        isBusy = true
        defer { isBusy = false }

        // Try Accessibility API first — works in apps that block simulated ⌘C (e.g. VS Code, Electron apps)
        logger.debug("AXIsProcessTrusted: \(AXIsProcessTrusted())")
        if let axText = readSelectedTextViaAccessibility(pid: targetPid), !axText.isEmpty {
            logger.debug("Selected text captured via Accessibility API (\(axText.count) chars)")
            return CaptureResult(text: axText, attributedText: nil, images: [], didChange: true)
        }

        let pb = NSPasteboard.general
        let oldChangeCount = pb.changeCount
        let snapshot = pb.createSnapshot()

        triggerCopy(targetPid: targetPid)
        try? await Task.sleep(for: minCopyDelay)

        let didChange = await waitForPasteboardUpdate(
            pb,
            initialChangeCount: oldChangeCount,
            timeout: copyTimeout,
            pollInterval: pollInterval
        )

        guard didChange, pb.changeCount > oldChangeCount else {
            logger.warning("Clipboard did not change after copy trigger")
            // Restore unconditionally here — clipboard wasn't changed by our copy
            let restored = pb.restore(snapshot: snapshot)
            if !restored {
                logger.error("Failed to restore clipboard after failed capture")
            }
            return CaptureResult(text: "", attributedText: nil, images: [], didChange: false)
        }

        let images = await readImages(from: pb)
        let attributed = pb.readAttributedSelection()
        let text = attributed?.string ?? pb.string(forType: .string) ?? ""

        // Restore clipboard, but only if no external app has modified it since our copy
        let postCopyChangeCount = pb.changeCount
        let restoreOutcome = pb.restoreIfUnchanged(
            snapshot: snapshot,
            expectedChangeCount: postCopyChangeCount
        )
        switch restoreOutcome {
        case .restored:
            logger.debug("Clipboard restored after capture")
        case .skippedExternalChange(let expected, let actual):
            logger.warning("Clipboard restore skipped after capture due to external change (expected \(expected), actual \(actual))")
            NotificationCenter.default.post(
                name: .clipboardRestoreSkipped,
                object: nil,
                userInfo: [
                    ClipboardNotificationUserInfoKey.expectedChangeCount: expected,
                    ClipboardNotificationUserInfoKey.actualChangeCount: actual,
                ]
            )
        case .failedWrite:
            logger.error("Failed to restore clipboard after capture")
        }

        return CaptureResult(text: text, attributedText: attributed, images: images, didChange: true)
    }

    private func readSelectedTextViaAccessibility(pid: pid_t? = nil) -> String? {
        let element: AXUIElement
        if let pid {
            // Read directly from the target app's focused element (more reliable)
            let appElement = AXUIElementCreateApplication(pid)
            var focusedRef: CFTypeRef?
            guard AXUIElementCopyAttributeValue(appElement, kAXFocusedUIElementAttribute as CFString, &focusedRef) == .success,
                  let ref = focusedRef
            else { return nil }
            element = ref as! AXUIElement
        } else {
            let systemWide = AXUIElementCreateSystemWide()
            var focusedRef: CFTypeRef?
            guard AXUIElementCopyAttributeValue(systemWide, kAXFocusedUIElementAttribute as CFString, &focusedRef) == .success,
                  let ref = focusedRef
            else { return nil }
            element = ref as! AXUIElement
        }

        var selectedText: CFTypeRef?
        let result = AXUIElementCopyAttributeValue(element, kAXSelectedTextAttribute as CFString, &selectedText)
        guard result == .success, let text = selectedText as? String, !text.isEmpty else { return nil }
        return text
    }

    private func triggerCopy(targetPid: pid_t? = nil) {
        let src = CGEventSource(stateID: .hidSystemState)
        let keyDown = CGEvent(keyboardEventSource: src, virtualKey: 0x08, keyDown: true)
        let keyUp = CGEvent(keyboardEventSource: src, virtualKey: 0x08, keyDown: false)
        keyDown?.flags = .maskCommand
        keyUp?.flags = .maskCommand
        if let pid = targetPid {
            // Post directly to the target process — more reliable than session tap for Electron apps
            keyDown?.postToPid(pid)
            keyUp?.postToPid(pid)
        } else {
            keyDown?.post(tap: .cgSessionEventTap)
            keyUp?.post(tap: .cgSessionEventTap)
        }
    }

    private func readImages(from pb: NSPasteboard) async -> [Data] {
        var foundImages: [Data] = []

        let classes = [NSURL.self]
        let imageTypeIdentifiers = [
            UTType.image,
            UTType.png,
            UTType.jpeg,
            UTType.tiff,
            UTType.gif,
        ].map(\.identifier)

        let options: [NSPasteboard.ReadingOptionKey: Any] = [
            .urlReadingFileURLsOnly: true,
            .urlReadingContentsConformToTypes: imageTypeIdentifiers,
        ]

        if let urls = pb.readObjects(forClasses: classes, options: options) as? [URL] {
            let loadedImages = await Self.loadImageData(from: urls)
            if !loadedImages.isEmpty {
                foundImages.append(contentsOf: loadedImages)
            }
        }

        if foundImages.isEmpty {
            let supportedImageTypes: [NSPasteboard.PasteboardType] = [
                NSPasteboard.PasteboardType(UTType.png.identifier),
                NSPasteboard.PasteboardType(UTType.jpeg.identifier),
                NSPasteboard.PasteboardType(UTType.tiff.identifier),
                NSPasteboard.PasteboardType(UTType.gif.identifier),
                NSPasteboard.PasteboardType(UTType.image.identifier),
            ]

            for type in supportedImageTypes {
                if let data = pb.data(forType: type) {
                    foundImages.append(data)
                    logger.debug("Found direct image data of type: \(type.rawValue)")
                    break
                }
            }
        }

        return foundImages
    }

    nonisolated private static func loadImageData(from urls: [URL]) async -> [Data] {
        await Task.detached(priority: .userInitiated) {
            var images: [Data] = []
            images.reserveCapacity(urls.count)

            for url in urls {
                if let imageData = try? Data(contentsOf: url),
                   isValidImageData(imageData) {
                    images.append(imageData)
                    logger.debug("Loaded image data from file: \(url.lastPathComponent)")
                }
            }
            return images
        }.value
    }

    nonisolated private static func isValidImageData(_ data: Data) -> Bool {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else {
            return false
        }
        return CGImageSourceGetCount(source) > 0
    }
}
