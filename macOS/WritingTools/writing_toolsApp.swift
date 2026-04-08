import SwiftUI

@main
struct writing_toolsApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var appState = AppState.shared
    @State private var settings = AppSettings.shared
    
    var body: some Scene {
        // Menu bar extra provides the status item and dropdown menu
        MenuBarExtra("AI Shortcuts", systemImage: "pencil.circle") {
            MenuBarMenu(appState: appState, settings: settings)
        }
        .menuBarExtraStyle(.menu)
        
        // Settings scene for the preferences window
        Settings {
            SettingsView(appState: appState, showOnlyApiSetup: false)
        }
    }
}

// MARK: - Menu Bar Menu Content

struct MenuBarMenu: View {
    @Bindable var appState: AppState
    @Bindable var settings: AppSettings
    @Environment(\.openSettings) private var openSettings
    
    @State private var showResetConfirmation = false
    @State private var showResetComplete = false
    
    var body: some View {
        // Settings - use Button with openSettings to ensure proper activation
        Button("Settings") {
            openSettings()
            // For accessory apps, activate after opening so the window
            // comes to front above other applications.
            Task { @MainActor in
                await Task.yield()
                if let settingsWindow = NSApp.windows.first(where: {
                    $0.identifier?.rawValue == "com_apple_SwiftUI_Settings_window"
                        || $0.title.contains("Settings")
                }), settingsWindow.isVisible {
                    WindowManager.shared.bringWindowToFront(settingsWindow)
                }
            }
        }
        .keyboardShortcut(",", modifiers: .command)
        
        Button("About AI Shortcuts") {
            showAboutWindow()
        }
        
        Button(settings.hotkeysPaused ? "Resume Hotkeys" : "Pause Hotkeys") {
            settings.hotkeysPaused.toggle()
        }
        
        Divider()
        
        Button("Reset App") {
            showResetConfirmation = true
        }
        .dialogSeverity(.critical)
        .confirmationDialog(
            "Reset AI Shortcuts?",
            isPresented: $showResetConfirmation
        ) {
            Button("Reset", role: .destructive) {
                WindowManager.shared.cleanupWindows()
                showResetComplete = true
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will reset windows and UI state. Your commands and settings will remain.")
        }
        .alert(
            "App Reset Complete",
            isPresented: $showResetComplete
        ) {
            Button("OK") {}
        } message: {
            Text("The app has been reset. If you're still experiencing issues, try restarting the app.")
        }
        
        Divider()
        
        Button("Quit") {
            NSApplication.shared.terminate(nil)
        }
        .keyboardShortcut("q", modifiers: .command)
    }
    
    @State private var aboutWindow: NSWindow?

    private func showAboutWindow() {
        // Reuse existing window if it's still open
        if let existing = aboutWindow, existing.isVisible {
            WindowManager.shared.bringWindowToFront(existing)
            return
        }

        let aboutView = AboutView()
        let hostingView = NSHostingView(rootView: aboutView)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 400),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.identifier = NSUserInterfaceItemIdentifier("AboutWindow")
        window.isReleasedWhenClosed = false
        window.contentView = hostingView
        window.title = "About AI Shortcuts"
        window.center()

        WindowManager.shared.bringWindowToFront(window)
        aboutWindow = window
    }
}
