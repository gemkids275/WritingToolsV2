//
//  OpenAISettingsView.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI
import AppKit

struct OpenAISettingsView: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "API Configuration"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    SecureAPIKeyField(String(localized: "API Key"), text: $settings.openAIApiKey)
                        .onChange(of: settings.openAIApiKey) { _, _ in
                            needsSaving = true
                        }
                    
                    TextField(String(localized: "Base URL"), text: $settings.openAIBaseURL)
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: settings.openAIBaseURL) { _, _ in
                            needsSaving = true
                        }
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text(String(localized: "Model Configuration"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    TextField(String(localized: "Model Name"), text: $settings.openAIModel)
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: settings.openAIModel) { _, _ in
                            needsSaving = true
                        }
                    
                    Text("OpenAI models include: gpt-4o, gpt-4o-mini, etc.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
            }
            .padding(.bottom, 4)
            
            Button(String(localized: "Get OpenAI API Key")) {
                if let url = URL(string: "https://platform.openai.com/account/api-keys") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(.link)
            .help(String(localized: "Open OpenAI dashboard to create an API key."))
        }
    }
}
