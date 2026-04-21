//
//  OpenRouterSettingsView.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI
import AppKit

struct OpenRouterSettingsView: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(String(localized: "Configure OpenRouter"))
                .font(.headline)
            SecureAPIKeyField(String(localized: "API Key"), text: $settings.openRouterApiKey)
                .onChange(of: settings.openRouterApiKey) { _, _ in needsSaving = true }
            
            Picker(String(localized: "Model"), selection: $settings.openRouterModel) {
                ForEach(OpenRouterModel.allCases, id: \.self) { model in
                    Text(model.displayName).tag(model.rawValue)
                }
            }
            .pickerStyle(.menu)
            .frame(maxWidth: .infinity, alignment: .leading)
            .onChange(of: settings.openRouterModel) { _, _ in needsSaving = true }
            
            if settings.openRouterModel == OpenRouterModel.custom.rawValue {
                TextField(String(localized: "Custom Model Name"), text: $settings.openRouterCustomModel)
                    .textFieldStyle(.roundedBorder)
                    .onChange(of: settings.openRouterCustomModel) { _, _ in needsSaving = true }
                    .padding(.top, 4)
            }
            
            Button(String(localized: "Get OpenRouter API Key")) {
                if let url = URL(string: "https://openrouter.ai/keys") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(.link)
            .help(String(localized: "Open OpenRouter to retrieve your API key."))
        }
    }
}
