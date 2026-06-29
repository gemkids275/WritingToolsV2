//
//  AnthropicSettingsView.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI
import AppKit

struct AnthropicSettingsView: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool
    @State private var modelSelection: AnthropicModel

    init(needsSaving: Binding<Bool>) {
        self._needsSaving = needsSaving
        // Initialize model selection from current settings to avoid flash on appear
        let currentModel = AppSettings.shared.anthropicModel
        if let knownModel = AnthropicModel(rawValue: currentModel), knownModel != .custom {
            self._modelSelection = State(initialValue: knownModel)
        } else {
            self._modelSelection = State(initialValue: .custom)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "API Configuration"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    SecureAPIKeyField(String(localized: "API Key"), text: $settings.anthropicApiKey)
                        .onChange(of: settings.anthropicApiKey) { _, _ in needsSaving = true }
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Model Selection"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    Picker(String(localized: "Model"), selection: $modelSelection) {
                        ForEach(AnthropicModel.allCases, id: \.self) { model in
                            Text(model.displayName).tag(model)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .onChange(of: modelSelection) { _, newValue in
                        if newValue != .custom {
                            settings.anthropicModel = newValue.rawValue
                        }
                        needsSaving = true
                    }
                    
                    if modelSelection == .custom {
                        TextField(String(localized: "Custom Model Name"), text: $settings.anthropicModel)
                            .textFieldStyle(.roundedBorder)
                            .font(.caption)
                            .onChange(of: settings.anthropicModel) { _, _ in needsSaving = true }
                    }
                    Text("E.g., \(AnthropicModel.claude45Haiku.rawValue), \(AnthropicModel.claude45Sonnet.rawValue), etc.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.bottom, 4)
            
            Button(String(localized: "Get Anthropic API Key")) {
                if let url = URL(string: "https://console.anthropic.com/settings/keys") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(.link)
            .help(String(localized: "Open Anthropic console to create or view your API key."))
        }
        .onAppear {
            syncModelSelection(settings.anthropicModel)
        }
        .onChange(of: settings.anthropicModel) { _, newValue in
            syncModelSelection(newValue)
        }
    }

    private func syncModelSelection(_ modelName: String) {
        if let knownModel = AnthropicModel(rawValue: modelName), knownModel != .custom {
            modelSelection = knownModel
        } else {
            modelSelection = .custom
        }
    }
}
