//
//  GeneralSettingsPane.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI
import KeyboardShortcuts
import AppKit

struct GeneralSettingsPane<SaveButton: View>: View {
    @Bindable var appState: AppState
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool
    @Binding var showingCommandsManager: Bool
    var showOnlyApiSetup: Bool
    let saveButton: SaveButton
    
    @State private var editingCommand: CommandModel? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(String(localized: "General Settings"))
                .font(.headline)
                .accessibilityAddTraits(.isHeader)

            ViewThatFits(in: .vertical) {
                generalContent
                    .frame(maxWidth: .infinity, alignment: .leading)

                ScrollView {
                    generalContent
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

            if !showOnlyApiSetup {
                saveButton
            }
        }
        .sheet(isPresented: $showingCommandsManager) {
            CommandsView(commandManager: appState.commandManager)
        }
    }

    private var generalContent: some View {
        VStack(alignment: .leading, spacing: 12) {
            GroupBox(String(localized: "Keyboard Shortcuts")) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Set a global shortcut to quickly activate AI Shortcuts."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack(alignment: .center, spacing: 12) {
                        Text(String(localized: "Activate AI Shortcuts:"))
                            .frame(width: 180, alignment: .leading)
                            .foregroundStyle(.primary)
                        KeyboardShortcuts.Recorder(
                            for: .showPopup,
                            onChange: { _ in
                                needsSaving = true
                            }
                        )
                        .accessibilityLabel(String(localized: "Activate AI Shortcuts shortcut"))
                        .accessibilityHint(String(localized: "Sets the global shortcut to open AI Shortcuts."))
                        .help(String(localized: "Choose a convenient key combination to bring up AI Shortcuts from anywhere."))
                    }
                    .padding(.vertical, 2)
                }
            }

            GroupBox(String(localized: "Commands")) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Manage your writing tools and assign keyboard shortcuts."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    Button(action: {
                        showingCommandsManager = true
                    }) {
                        HStack(spacing: 8) {
                            Image(systemName: "list.bullet.rectangle")
                            Text(String(localized: "Manage Commands"))
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 6)
                        .padding(.horizontal, 10)
                        .background(Color(.controlBackgroundColor))
                        .clipShape(.rect(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(String(localized: "Manage Commands"))
                    .accessibilityHint(String(localized: "Open the Commands Manager to add, edit, or remove commands."))
                    .help(String(localized: "Open the Commands Manager to add, edit, or remove commands."))

                    Toggle(isOn: $settings.openCustomCommandsInResponseWindow) {
                        VStack(alignment: .leading, spacing: 1) {
                            Text(String(localized: "Open custom prompts in response window"))
                            Text(String(localized: "When unchecked, custom prompts will replace selected text inline"))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .toggleStyle(.checkbox)
                    .accessibilityLabel(String(localized: "Open custom prompts in response window"))
                    .accessibilityHint(String(localized: "When off, custom prompts replace selected text inline."))
                    .onChange(of: settings.openCustomCommandsInResponseWindow) { _, _ in
                        needsSaving = true
                    }
                    .help(String(localized: "Choose whether custom prompts open in a separate response window or replace text inline."))

                }
            }

            GroupBox(String(localized: "Language")) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Choose your preferred language for the interface."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    Picker(String(localized: "Interface Language:"), selection: $settings.preferredLanguage) {
                        Text(String(localized: "System Default")).tag(String?.none)
                        Divider()
                        Text("English").tag(String?.some("en"))
                        Text("Deutsch").tag(String?.some("de"))
                        Text("Español").tag(String?.some("es"))
                        Text("Français").tag(String?.some("fr"))
                        Text("Tiếng Việt").tag(String?.some("vi"))
                        Text("日本語").tag(String?.some("ja"))
                        Text("中文简体").tag(String?.some("zh-Hans"))
                    }
                    .frame(width: 300)
                    .onChange(of: settings.preferredLanguage) { oldValue, newValue in
                        if oldValue != newValue {
                            showRestartAlert()
                        }
                    }
                }
            }

            GroupBox(String(localized: "Onboarding")) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(String(localized: "You can rerun the onboarding flow to review permissions and quickly configure the app."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack {
                        Button {
                            restartOnboarding()
                        } label: {
                            Label(String(localized: "Restart Onboarding"), systemImage: "arrow.counterclockwise")
                        }
                        .buttonStyle(.bordered)
                        .accessibilityLabel(String(localized: "Restart onboarding"))
                        .accessibilityHint(String(localized: "Open the onboarding window to review permissions and setup."))
                        .help(String(localized: "Open the onboarding window to set up AI Shortcuts again."))

                        Spacer()
                    }
                }
            }

            GroupBox(String(localized: "Custom AI Response")) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Customize the system instructions used when you enter a manual description in the popup."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    Button(action: {
                        editingCommand = AppSettings.shared.customInstructionCommand
                    }) {
                        HStack(spacing: 8) {
                            Image(systemName: "square.and.pencil")
                            Text(String(localized: "Edit Custom Response Prompt"))
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 6)
                        .padding(.horizontal, 10)
                        .background(Color(.controlBackgroundColor))
                        .clipShape(.rect(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(String(localized: "Edit Custom Response Prompt"))
                    .accessibilityHint(String(localized: "Open the editor to customize the AI's behavior for manual inputs."))
                    .help(String(localized: "Open the editor to customize the AI's behavior for manual inputs."))
                }
            }

            GroupBox(String(localized: "Backup & Restore")) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Backup all your commands and AI response settings to a JSON file, or restore them from a previous backup."))
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 12) {
                        Button(action: exportFullConfig) {
                            Label(String(localized: "Export All Config"), systemImage: "square.and.arrow.up")
                        }
                        .buttonStyle(.bordered)

                        Button(action: importFullConfig) {
                            Label(String(localized: "Import Full Config"), systemImage: "square.and.arrow.down")
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding(.top, 4)
                }
            }
        }
        .sheet(item: $editingCommand) { command in
            CommandEditor(
                command: Binding(
                    get: { command },
                    set: { updatedCommand in
                        AppSettings.shared.customInstructionCommand = updatedCommand
                        editingCommand = nil
                        needsSaving = true
                    }
                ),
                onSave: {
                    editingCommand = nil
                },
                onCancel: {
                    editingCommand = nil
                },
                commandManager: appState.commandManager
            )
        }
    }

    private func restartOnboarding() {
        // Mark onboarding as not completed
        settings.hasCompletedOnboarding = false
        WindowManager.shared.showOnboarding(appState: appState, title: "Onboarding")
        NSApp.keyWindow?.close()
        WindowManager.shared.closeSettingsWindow()
    }
    
    private func showRestartAlert() {
        let alert = NSAlert()
        alert.messageText = String(localized: "Restart Required")
        alert.informativeText = String(localized: "The language change will take effect after restarting the application. Would you like to restart now?")
        alert.alertStyle = .informational
        alert.addButton(withTitle: String(localized: "Restart Now"))
        alert.addButton(withTitle: String(localized: "Later"))
        
        if alert.runModal() == .alertFirstButtonReturn {
            restartApp()
        }
    }

    private func restartApp() {
        let url = Bundle.main.bundleURL
        let config = NSWorkspace.OpenConfiguration()
        config.createsNewApplicationInstance = true
        NSWorkspace.shared.openApplication(at: url, configuration: config) { _, error in
            DispatchQueue.main.async {
                if error != nil {
                    let alert = NSAlert()
                    alert.messageText = String(localized: "Restart Failed")
                    alert.informativeText = String(localized: "Could not relaunch the app. Please restart it manually.")
                    alert.alertStyle = .warning
                    alert.addButton(withTitle: String(localized: "OK"))
                    alert.runModal()
                }
                NSApp.terminate(nil)
            }
        }
    }

    // MARK: - Backup & Restore Logic

    private func exportFullConfig() {
        let savePanel = NSSavePanel()
        savePanel.allowedContentTypes = [.json]
        savePanel.canCreateDirectories = true
        savePanel.isExtensionHidden = false
        savePanel.title = String(localized: "Export Full Configuration")
        savePanel.message = String(localized: "Choose where to save your AI Shortcuts configuration backup.")
        savePanel.nameFieldStringValue = "AIShortcuts_Full_Backup.json"

        if savePanel.runModal() == .OK {
            if let url = savePanel.url {
                if let data = appState.commandManager.createExportBundle(customInstruction: settings.customInstructionCommand) {
                    do {
                        try data.write(to: url)
                        let alert = NSAlert()
                        alert.messageText = String(localized: "Export Successful")
                        alert.informativeText = String(localized: "Your configuration has been saved to \(url.lastPathComponent).")
                        alert.alertStyle = .informational
                        alert.addButton(withTitle: String(localized: "OK"))
                        alert.runModal()
                    } catch {
                        AppLogger.logger("Backup").error("Failed to write backup to \(url): \(error.localizedDescription)")
                        let alert = NSAlert()
                        alert.messageText = String(localized: "Export Failed")
                        alert.informativeText = error.localizedDescription
                        alert.alertStyle = .critical
                        alert.addButton(withTitle: String(localized: "OK"))
                        alert.runModal()
                    }
                }
            }
        }
    }

    private func importFullConfig() {
        let openPanel = NSOpenPanel()
        openPanel.allowedContentTypes = [.json]
        openPanel.allowsMultipleSelection = false
        openPanel.canChooseDirectories = false
        openPanel.canChooseFiles = true
        openPanel.title = String(localized: "Import Full Configuration")
        openPanel.message = String(localized: "Select a AI Shortcuts configuration backup file to restore.")

        if openPanel.runModal() == .OK {
            if let url = openPanel.url {
                do {
                    let data = try Data(contentsOf: url)
                    let bundle = try appState.commandManager.decodeExportBundle(data)
                    
                    // Replace all commands
                    appState.commandManager.replaceAllCommands(with: bundle.commands)
                    
                    // Update custom instruction if present
                    if let customInstruction = bundle.customInstruction {
                        settings.customInstructionCommand = customInstruction
                    }
                    
                    needsSaving = true
                    
                    let alert = NSAlert()
                    alert.messageText = String(localized: "Import Successful")
                    alert.informativeText = String(localized: "All commands and settings have been restored.")
                    alert.alertStyle = .informational
                    alert.addButton(withTitle: String(localized: "OK"))
                    alert.runModal()
                } catch {
                    AppLogger.logger("Backup").error("Failed to import backup from \(url): \(error.localizedDescription)")
                    let alert = NSAlert()
                    alert.messageText = String(localized: "Import Failed")
                    alert.informativeText = String(localized: "Could not import configuration: \(error.localizedDescription)")
                    alert.alertStyle = .critical
                    alert.addButton(withTitle: String(localized: "OK"))
                    alert.runModal()
                }
            }
        }
    }
}
