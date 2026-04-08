//
//  AppearanceSettingsPane.swift
//  WritingTools
//
//  Created by Arya Mirsepasi on 04.11.25.
//

import SwiftUI

struct AppearanceSettingsPane<SaveButton: View>: View {
    @Bindable var settings = AppSettings.shared
    @Binding var needsSaving: Bool
    var showOnlyApiSetup: Bool
    let saveButton: SaveButton

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Appearance Settings")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            
            VStack(alignment: .leading, spacing: 12) {
                Text("Window Style")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                Text("Choose a window appearance that matches your preferences and context.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                Picker("Theme", selection: $settings.themeStyle) {
                    ForEach(AppTheme.allCases, id: \.self) { theme in
                        Text(theme.displayName).tag(theme)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.vertical, 4)
                .accessibilityLabel("Theme")
                .accessibilityHint("Choose how AI Shortcuts windows are styled.")
                .onChange(of: settings.themeStyle) { _, _ in
                    needsSaving = true
                }
                .help("Standard uses system backgrounds. Glass respects transparency preferences. OLED uses deep blacks.")
            }
            
            Spacer()
            
            if !showOnlyApiSetup {
                saveButton
            }
        }
    }
}
