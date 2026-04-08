import SwiftUI
import AppKit

private let logger = AppLogger.logger("WindowManager")

@MainActor
class WindowManager: NSObject, NSWindowDelegate {
    static let shared = WindowManager()

    private var onboardingWindow: NSWindow?
    private var settingsWindow: NSWindow?

    // Track a single PopupWindow
    private weak var popupWindow: PopupWindow?

    enum PopupDismissSuppressionReason: Hashable {
        case commandEditorSheet
        case commandsManagerSheet
    }

    private var popupDismissSuppressionReasons: Set<PopupDismissSuppressionReason> = []
    private var popupDismissSuppressionResetTask: Task<Void, Never>?
    private let popupDismissSuppressionFailsafeDelay: Duration = .seconds(2)

    var isPopupDismissSuppressed: Bool {
        !popupDismissSuppressionReasons.isEmpty
    }

    private var responseWindows = NSHashTable<ResponseWindow>.weakObjects()

    // MARK: - Response Windows

    func addResponseWindow(_ window: ResponseWindow) {
        guard !window.isReleasedWhenClosed else {
            logger.error("Attempted to add a released window.")
            return
        }
        if !responseWindows.contains(window) {
            responseWindows.add(window)
            window.delegate = self
        }
        bringWindowToFront(window)
    }

    /// Activates the app and brings the given window to the front.
    ///
    /// Accessory apps (`NSApp.activationPolicy == .accessory`) don't appear in the
    /// Dock, so `NSApp.activate()` alone may not suffice. `orderFrontRegardless()`
    /// ensures the window appears above other apps even if activation is delayed.
    func bringWindowToFront(_ window: NSWindow) {
        NSApp.activate()
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
    }

    func removeResponseWindow(_ window: ResponseWindow) {
        responseWindows.remove(window)
    }

    // MARK: - Popup Window

    func registerPopupWindow(_ window: PopupWindow) {
        popupWindow = window
        window.delegate = self
    }

    func setPopupDismissSuppressed(
        _ isSuppressed: Bool,
        reason: PopupDismissSuppressionReason
    ) {
        if isSuppressed {
            popupDismissSuppressionReasons.insert(reason)
            schedulePopupDismissSuppressionFailsafe()
        } else {
            popupDismissSuppressionReasons.remove(reason)
            if popupDismissSuppressionReasons.isEmpty {
                popupDismissSuppressionResetTask?.cancel()
                popupDismissSuppressionResetTask = nil
            }
        }
    }

    func dismissPopup(clearImages: Bool = true) {
        clearPopupDismissSuppressionState()
        if let window = self.popupWindow {
            window.close()
            self.popupWindow = nil
        }

        if clearImages {
            AppState.shared.selectedImages = []
            AppState.shared.customAttachments = []
        }
    }

    // MARK: - Onboarding & Settings

    func transitionFromOnboardingToSettings(appState: AppState) {
        if let existingSettingsWindow = settingsWindow, existingSettingsWindow.isVisible {
            onboardingWindow?.close()
            onboardingWindow = nil
            bringWindowToFront(existingSettingsWindow)
            return
        }

        let currentOnboardingWindow = onboardingWindow

        let newSettingsWindow = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 520),
            styleMask: [.titled, .closable, .resizable],
            backing: .buffered,
            defer: false
        )

        newSettingsWindow.title = "Complete Setup"
        newSettingsWindow.identifier = NSUserInterfaceItemIdentifier("SettingsWindow")
        newSettingsWindow.isReleasedWhenClosed = false
        newSettingsWindow.minSize = NSSize(width: 520, height: 440)

        let settingsView =
            SettingsView(appState: appState, showOnlyApiSetup: true)
        let hostingView = NSHostingView(rootView: settingsView)
        newSettingsWindow.contentView = hostingView
        newSettingsWindow.delegate = self

        settingsWindow = newSettingsWindow

        // Center window BEFORE display
        newSettingsWindow.level = .normal
        newSettingsWindow.center()
        
        currentOnboardingWindow?.close()
        onboardingWindow = nil
        
        bringWindowToFront(newSettingsWindow)
    }

    func setOnboardingWindow(
        _ window: NSWindow,
        hostingView: NSHostingView<OnboardingView>
    ) {
        onboardingWindow = window
        window.delegate = self
        window.level = .floating
        window.identifier = NSUserInterfaceItemIdentifier("OnboardingWindow")
        
        window.center()
    }

    func registerSettingsWindow(
        _ window: NSWindow,
        hostingView: NSHostingView<SettingsView>
    ) {
        settingsWindow = window
        window.delegate = self
        window.identifier = NSUserInterfaceItemIdentifier("SettingsWindow")
    }

    func closeSettingsWindow() {
        if let window = settingsWindow {
            window.close()
            settingsWindow = nil
        }
    }

    func showOnboarding(appState: AppState, title: String = "Welcome to AI Shortcuts") {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 640, height: 720),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = title
        window.isReleasedWhenClosed = false
        window.minSize = NSSize(width: 560, height: 600)

        let onboardingView = OnboardingView(appState: appState)
        let hostingView = NSHostingView(rootView: onboardingView)
        window.contentView = hostingView
        window.level = .floating

        setOnboardingWindow(window, hostingView: hostingView)
        bringWindowToFront(window)
    }

    // MARK: - Window Delegate

    func windowDidBecomeKey(_ notification: Notification) {
        guard let window = notification.object as? NSWindow else { return }
        let isOnboardingWindow = (window === onboardingWindow)
        let preferredLevel: NSWindow.Level
        if window is PopupWindow {
            preferredLevel = .popUpMenu
        } else if isOnboardingWindow {
            preferredLevel = .floating
        } else {
            preferredLevel = .normal
        }
        if window.level != preferredLevel {
            window.level = preferredLevel
        }
    }

    func windowDidResignKey(_ notification: Notification) {
        // Popup is dismissed explicitly via the X button or command execution.
    }

    func windowWillClose(_ notification: Notification) {
        guard let window = notification.object as? NSWindow else { return }

        if let popup = window as? PopupWindow {
            popup.cleanup()
            clearPopupDismissSuppressionState()
            if popupWindow === popup {
                popupWindow = nil
            }
        } else if let responseWindow = window as? ResponseWindow {
            removeResponseWindow(responseWindow)
        } else if window === onboardingWindow {
            onboardingWindow = nil
        } else if window === settingsWindow {
            settingsWindow = nil
        }

        window.delegate = nil
    }

    // MARK: - Cleanup

    func cleanupWindows() {
        let windowsToClose = getAllWindows()

        windowsToClose.forEach { window in
            // Set delegate to nil to prevent callbacks during close
            window.delegate = nil
            window.close()
        }
        clearAllWindows()
    }

    private func getAllWindows() -> [NSWindow] {
        var windows: [NSWindow] = []

        if let onboardingWindow {
            windows.append(onboardingWindow)
        }

        if let settingsWindow {
            windows.append(settingsWindow)
        }

        if let popup = popupWindow {
            windows.append(popup)
        }

        windows.append(contentsOf: responseWindows.allObjects)
        return windows
    }

    private func clearAllWindows() {
        onboardingWindow = nil
        settingsWindow = nil
        responseWindows.removeAllObjects()
        clearPopupDismissSuppressionState()
        popupWindow = nil
    }

    deinit {}
}

extension WindowManager {
    private func schedulePopupDismissSuppressionFailsafe() {
        popupDismissSuppressionResetTask?.cancel()
        popupDismissSuppressionResetTask = Task { @MainActor [weak self] in
            guard let self else { return }
            try? await Task.sleep(for: popupDismissSuppressionFailsafeDelay)
            guard !Task.isCancelled else { return }
            guard !popupDismissSuppressionReasons.isEmpty else { return }
            logger.warning("Resetting popup dismissal suppression via failsafe")
            popupDismissSuppressionReasons.removeAll()
            popupDismissSuppressionResetTask = nil
        }
    }

    private func clearPopupDismissSuppressionState() {
        popupDismissSuppressionResetTask?.cancel()
        popupDismissSuppressionResetTask = nil
        popupDismissSuppressionReasons.removeAll()
    }
}

extension WindowManager {
    enum WindowError: LocalizedError {
        case windowCreationFailed
        case invalidWindowType
        case windowNotFound

        var errorDescription: String? {
            switch self {
            case .windowCreationFailed:
                return "Failed to create window"
            case .invalidWindowType:
                return "Invalid window type"
            case .windowNotFound:
                return "Window not found"
            }
        }
    }
}
