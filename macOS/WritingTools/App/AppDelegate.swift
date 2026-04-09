import SwiftUI
import KeyboardShortcuts
import Carbon.HIToolbox

private let logger = AppLogger.logger("AppDelegate")

/// AppDelegate handles keyboard shortcuts, services, and popup window management.
/// Menu bar UI is handled by SwiftUI's MenuBarExtra in writing_toolsApp.swift.
@MainActor
class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var clipboardRestoreObserver: NSObjectProtocol?
    private var commandsChangedObserver: NSObjectProtocol?
    private var commandShortcutNamesById: [UUID: KeyboardShortcuts.Name] = [:]
    
    let appState = AppState.shared

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        NSApp.servicesProvider = self

        if CommandLine.arguments.contains("--reset") {
            Task { @MainActor [weak self] in
                self?.performRecoveryReset()
            }
            return
        }

        Task { @MainActor in
            if !AppSettings.shared.hasCompletedOnboarding {
                self.showOnboarding()
            }
        }

        // Register the main popup shortcut
        KeyboardShortcuts.onKeyUp(for: .showPopup) { [weak self] in
            if !AppSettings.shared.hotkeysPaused {
                self?.showPopup()
            } else {
                logger.info("Hotkeys are paused")
            }
        }

        // Set up command-specific shortcuts
        setupCommandShortcuts()

        // Register for command changes to update shortcuts
        commandsChangedObserver = NotificationCenter.default.addObserver(
            forName: NSNotification.Name("CommandsChanged"),
            object: nil,
            queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.setupCommandShortcuts()
            }
        }

        clipboardRestoreObserver = NotificationCenter.default.addObserver(
            forName: .clipboardRestoreSkipped,
            object: nil,
            queue: .main
        ) { [weak self] note in
            Task { @MainActor in
                guard let self else { return }
                let expected = note.userInfo?[ClipboardNotificationUserInfoKey.expectedChangeCount] as? Int ?? -1
                let actual = note.userInfo?[ClipboardNotificationUserInfoKey.actualChangeCount] as? Int ?? -1
                self.showClipboardRestoreSkippedWarningAlert(
                    expectedChangeCount: expected,
                    actualChangeCount: actual
                )
            }
        }
    }

    private func setupCommandShortcuts() {
        let commandsWithShortcuts = appState.commandManager.commands.filter(\.hasShortcut)
        let desiredIds = Set(commandsWithShortcuts.map(\.id))
        let registeredIds = Set(commandShortcutNamesById.keys)

        guard desiredIds != registeredIds else { return }

        let removedIds = registeredIds.subtracting(desiredIds)
        for id in removedIds {
            guard let shortcutName = commandShortcutNamesById[id] else { continue }
            KeyboardShortcuts.removeHandler(for: shortcutName)
            KeyboardShortcuts.reset(shortcutName)
            commandShortcutNamesById[id] = nil
        }

        let addedIds = desiredIds.subtracting(registeredIds)
        for commandId in addedIds {
            let shortcutName = KeyboardShortcuts.Name.commandShortcut(for: commandId)
            KeyboardShortcuts.removeHandler(for: shortcutName)
            KeyboardShortcuts.onKeyUp(for: shortcutName) { [weak self] in
                guard let self, !AppSettings.shared.hotkeysPaused else { return }
                guard let command = self.appState.commandManager.commands.first(where: { $0.id == commandId }) else {
                    logger.warning("Shortcut fired for missing command ID: \(commandId.uuidString)")
                    return
                }
                self.executeCommandDirectly(command)
            }
            commandShortcutNamesById[commandId] = shortcutName
        }
    }

    private func executeCommandDirectly(_ command: CommandModel) {
        Task { @MainActor [weak self] in
            guard let self else { return }

            do {
                _ = try await CommandExecutionEngine.shared.executeCommand(
                    command,
                    source: .hotkey
                )
            } catch let error as CommandExecutionEngineError {
                self.handleCommandExecutionError(error)
            } catch {
                logger.error("Error processing command \(command.name): \(error.localizedDescription)")
                await self.presentCommandErrorAlert(commandName: command.name, error: error)
            }
        }
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
        true
    }

    func applicationWillTerminate(_ notification: Notification) {
        // Flush any debounced keychain writes before exit
        AppSettings.shared.flushPendingKeychainWrites()

        NotificationCenter.default.removeObserver(
            self,
            name: NSNotification.Name("CommandsChanged"),
            object: nil
        )
        if let clipboardRestoreObserver {
            NotificationCenter.default.removeObserver(clipboardRestoreObserver)
            self.clipboardRestoreObserver = nil
        }
        for shortcutName in commandShortcutNamesById.values {
            KeyboardShortcuts.removeHandler(for: shortcutName)
        }
        commandShortcutNamesById.removeAll()
        WindowManager.shared.cleanupWindows()
    }

    private func performRecoveryReset() {
        guard let domain = Bundle.main.bundleIdentifier else { return }
        UserDefaults.standard.removePersistentDomain(forName: domain)

        WindowManager.shared.cleanupWindows()

        let alert = NSAlert()
        alert.messageText = "Recovery Complete"
        alert.informativeText =
            "The app has been reset to its default state."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")
        
        NSApp.activate()
        if let keyWindow = NSApp.keyWindow {
            alert.beginSheetModal(for: keyWindow)
        } else {
            alert.runModal()
        }
    }

    private func showOnboarding() {
        WindowManager.shared.showOnboarding(appState: appState)
    }

    @MainActor
    private func showPopup() {
        Task { @MainActor in
            let frontApp = NSWorkspace.shared.frontmostApplication
            if let frontApp {
                self.appState.previousApplication = frontApp
            }
            // Capture PID before closing popup — closing may shift focus away from the target app
            let targetPid = frontApp?.processIdentifier

            self.closePopupWindow()
            self.appState.customText = ""
            self.appState.customAttachments = []

            guard let capture = await ClipboardCoordinator.shared.captureSelection(targetPid: targetPid) else {
                logger.debug("Clipboard capture skipped because another operation is in progress")
                return
            }

            if !capture.didChange {
                logger.warning("Pasteboard did not change after copy; clearing selection to avoid stale context")
                if !AXIsProcessTrusted() {
                    self.showAccessibilityPermissionAlert()
                    return
                }
            }

            self.appState.selectedAttributedText = capture.attributedText
            self.appState.selectedText = capture.text
            self.appState.selectedImages = capture.images

            let window = PopupWindow(appState: self.appState)
            if !capture.text.isEmpty || !capture.images.isEmpty {
                window.setContentSize(NSSize(width: 400, height: 400))
            } else {
                window.setContentSize(NSSize(width: 400, height: 100))
            }

            window.positionNearMouse()
            NSApp.activate()
            window.makeKeyAndOrderFront(nil)
            window.orderFrontRegardless()
        }
    }

    private func handleCommandExecutionError(_ error: CommandExecutionEngineError) {
        switch error {
        case .captureInProgress:
            logger.debug("Clipboard capture skipped because another operation is in progress")
        case .noNewCopiedContent(let commandName):
            logger.warning("No new content was copied for command: \(commandName)")
        case .emptySelection(let commandName):
            logger.info("No text or images selected for command: \(commandName)")
        case .emptyInstruction:
            logger.warning("Custom instruction execution failed due to empty instruction")
        case .customProviderConfigurationIncomplete(let commandName, let missingFields):
            logger.warning(
                """
                Custom provider configuration incomplete for command \(commandName). \
                Missing fields: \(missingFields.joined(separator: ", "))
                """
            )
        }
    }

    private func presentCommandErrorAlert(commandName: String, error: Error) async {
        let alert = NSAlert()
        alert.messageText = "Command Error"
        alert.informativeText = "Failed to process '\(commandName)': \(error.localizedDescription)"
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")

        NSApp.activate()
        if let keyWindow = NSApp.keyWindow {
            await alert.beginSheetModal(for: keyWindow)
        } else {
            alert.runModal()
        }
    }

    private func closePopupWindow() {
        WindowManager.shared.dismissPopup()
    }

    private func showAccessibilityPermissionAlert() {
        let alert = NSAlert()
        alert.messageText = "Accessibility Permission Required"
        alert.informativeText =
            """
            AI Shortcuts needs Accessibility permission to read your selected text.

            Click "Request Permission" to allow it, then re-enable the toggle if needed.
            """
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Request Permission")
        alert.addButton(withTitle: "Cancel")

        NSApp.activate()
        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary
            AXIsProcessTrustedWithOptions(options)
        }
    }

    private func showClipboardRestoreSkippedWarningAlert(
        expectedChangeCount: Int,
        actualChangeCount: Int
    ) {
        let alert = NSAlert()
        alert.messageText = "Clipboard Was Updated by Another App"
        alert.informativeText =
            """
            AI Shortcuts captured your selection, but your clipboard changed before it could be restored.
            Your latest clipboard content was preserved.
            (Expected change count: \(expectedChangeCount), actual: \(actualChangeCount))
            """
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")

        NSApp.activate()
        if let keyWindow = NSApp.keyWindow {
            alert.beginSheetModal(for: keyWindow)
        } else {
            alert.runModal()
        }
    }

}

extension AppDelegate {
    override func awakeFromNib() {
        super.awakeFromNib()

        NSApp.servicesProvider = self
        NSUpdateDynamicServices()
    }
}
