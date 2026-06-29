//
//  OllamaSettingsView.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI
import AppKit

struct OllamaSettingsView: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Connection & Model Configuration combined
            VStack(alignment: .leading, spacing: 6) {
                Text(String(localized: "Connection & Model"))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                TextField(String(localized: "Base URL"), text: $settings.ollamaBaseURL)
                    .textFieldStyle(.roundedBorder)
                    .onChange(of: settings.ollamaBaseURL) { _, _ in
                        needsSaving = true
                    }
                
                HStack(spacing: 8) {
                    TextField(String(localized: "Model"), text: $settings.ollamaModel)
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: settings.ollamaModel) { _, _ in
                            needsSaving = true
                        }
                    
                    TextField(String(localized: "Keep Alive"), text: $settings.ollamaKeepAlive)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 80)
                        .onChange(of: settings.ollamaKeepAlive) { _, _ in
                            needsSaving = true
                        }
                }
            }
            
            // Image Recognition
            VStack(alignment: .leading, spacing: 6) {
                Text(String(localized: "Image Recognition"))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                Picker(String(localized: "Image Mode"), selection: $settings.ollamaImageMode) {
                    ForEach(OllamaImageMode.allCases) { mode in
                        Text(mode.displayName).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .onChange(of: settings.ollamaImageMode) { _, _ in
                    needsSaving = true
                }
                
                Text(String(localized: "Use OCR locally or a vision-enabled model for images."))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            // Documentation
            HStack(spacing: 12) {
                LinkText()
                
                Button(String(localized: "Ollama Docs")) {
                    if let url = URL(string: "https://docs.ollama.com") {
                        NSWorkspace.shared.open(url)
                    }
                }
                .buttonStyle(.link)
                .help(String(localized: "Open Ollama download and documentation page."))
            }
        }
    }
}
