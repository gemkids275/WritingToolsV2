//
//  GeminiSettingsView.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI

struct GeminiSettingsView: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "API Configuration"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    SecureAPIKeyField(String(localized: "API Key"), text: $settings.geminiApiKey)
                        .onChange(of: settings.geminiApiKey) { _, _ in
                            needsSaving = true
                        }
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Model Selection"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    Picker(String(localized: "Model"), selection: $settings.geminiModel) {
                        ForEach(GeminiModel.allCases, id: \.self) { model in
                            Text(model.displayName).tag(model)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .onChange(of: settings.geminiModel) { _, _ in
                        needsSaving = true
                    }
                    
                    if settings.geminiModel == .custom {
                        TextField(String(localized: "Custom Model Name"), text: $settings.geminiCustomModel)
                            .textFieldStyle(.roundedBorder)
                            .onChange(of: settings.geminiCustomModel) { _, _ in
                                needsSaving = true
                            }
                            .padding(.top, 4)
                    }
                }
            }
            .padding(.bottom, 4)
            
            Button(String(localized: "Get API Key")) {
                if let url = URL(string: "https://aistudio.google.com/app/apikey") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(.link)
            .help(String(localized: "Open Google AI Studio to generate an API key."))
        }
    }
}
