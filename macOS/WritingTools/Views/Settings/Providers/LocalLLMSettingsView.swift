import SwiftUI
import Observation

struct LocalLLMSettingsView: View {
    @Bindable var llmProvider: LocalModelProvider
    @Bindable private var settings = AppSettings.shared

    @State private var showingDeleteAlert = false
    @State private var showingErrorAlert = false
    @State private var selectedModelCategory: ModelCategory = .all

    enum ModelCategory: String, CaseIterable, Identifiable {
        case all = "all"
        case text = "text"
        case vision = "vision"

        var id: String { self.rawValue }

        var displayName: String {
            switch self {
            case .all: return String(localized: "All Models")
            case .text: return String(localized: "Text Models")
            case .vision: return String(localized: "Vision Models")
            }
        }
    }

    init(provider: LocalModelProvider) {
        _llmProvider = Bindable(wrappedValue: provider)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !llmProvider.isPlatformSupported {
                platformNotSupportedView
                    .accessibilityElement(children: .contain)
                    .accessibilityAddTraits(.isHeader)
            } else {
                supportedPlatformView
                    .accessibilityElement(children: .contain)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        // --- Delete Alert ---
        .alert(String(localized: "Delete Model"), isPresented: $showingDeleteAlert, presenting: llmProvider.selectedModelType) { modelType in
            Button(String(localized: "Cancel"), role: .cancel) { }
            Button(String(localized: "Delete \(modelType.displayName)")) {
                Task {
                    do {
                        try await llmProvider.deleteModel()
                    } catch {
                        llmProvider.lastError = String(localized: "Failed to delete \(modelType.displayName): \(error.localizedDescription)")
                    }
                }
            }
        } message: { modelType in
            Text(String(localized: "Are you sure you want to delete the downloaded model \(modelType.displayName)? You'll need to download it again to use it."))
        }
        // --- General Error Alert ---
        .alert(String(localized: "Local LLM Error"), isPresented: $showingErrorAlert) {
            Button(String(localized: "OK"), role: .cancel) { llmProvider.lastError = nil }
        } message: {
            Text(llmProvider.lastError ?? String(localized: "An unknown error occurred."))
        }
        .onChange(of: llmProvider.lastError) { _, newValue in
            // Show the alert if a new error is set by the provider
            if newValue != nil {
                showingErrorAlert = true
            }
        }
    }
    
    private var platformNotSupportedView: some View {
        GroupBox {
            VStack(alignment: .center, spacing: 12) {
                Image(systemName: "xmark.octagon.fill")
                    .font(.system(size: 36))
                    .foregroundStyle(.red)
                    .accessibilityHidden(true)
                
                Text(String(localized: "Apple Silicon Required"))
                    .font(.headline)
                    .accessibilityAddTraits(.isHeader)
                
                Text(String(localized: "Local LLM processing is only available on Apple Silicon (M-series) devices. Please select a different AI Provider."))
                    .font(.callout)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity)
        }
    }
    
    // Filter models based on the selected category
    private var filteredModels: [LocalModelType] {
        switch selectedModelCategory {
        case .all:
            return LocalModelType.allCases
        case .text:
            return LocalModelType.allCases.filter { !$0.isVisionModel }
        case .vision:
            return LocalModelType.allCases.filter { $0.isVisionModel }
        }
    }
    
    private var supportedPlatformView: some View {
        VStack(alignment: .leading, spacing: 10) {
            GroupBox(String(localized: "Model Configuration")) {
                VStack(alignment: .leading, spacing: 8) {
                    // Filter picker - inline
                    HStack {
                        Text(String(localized: "Filter:"))
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Picker(String(localized: "Filter"), selection: $selectedModelCategory) {
                            ForEach(ModelCategory.allCases) { category in
                                Text(category.displayName).tag(category)
                            }
                        }
                        .pickerStyle(.segmented)
                        .labelsHidden()
                        .help(String(localized: "Filter between all, text-only, and vision-capable models."))
                    }
                    
                    Divider()
                    
                    // Model selection
                    HStack {
                        Text(String(localized: "Model:"))
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Picker(String(localized: "Model"), selection: $settings.selectedLocalLLMId) {
                            Text(String(localized: "None Selected")).tag(String?.none)
                            ForEach(filteredModels) { modelType in
                                HStack {
                                    Text(modelType.displayName)
                                    if modelType.isVisionModel {
                                        Image(systemName: "camera.fill")
                                            .foregroundStyle(.blue)
                                    }
                                }
                                .tag(String?.some(modelType.id))
                            }
                        }
                        .pickerStyle(.menu)
                        .labelsHidden()
                        .help(String(localized: "Select a local model. Vision-capable models can process images."))
                    }

                    if let selectedModel = llmProvider.selectedModelType {
                        HStack(spacing: 6) {
                            if selectedModel.isVisionModel {
                                Label(String(localized: "Vision-capable"), systemImage: "camera.fill")
                                    .foregroundStyle(.blue)
                                    .font(.caption)
                            } else {
                                Label(String(localized: "Text-only"), systemImage: "text.justifyleft")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }

            if let selectedModelType = llmProvider.selectedModelType {
                GroupBox(String(localized: "Status")) {
                    VStack(alignment: .leading, spacing: 8) {
                        if !llmProvider.modelInfo.isEmpty {
                            Text(llmProvider.modelInfo)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }

                        modelActionView(for: selectedModelType)

                        if let error = llmProvider.lastError {
                            HStack(alignment: .top, spacing: 6) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundStyle(.red)
                                Text(error)
                                    .foregroundStyle(.red)
                                    .font(.caption)
                                    .lineLimit(2)
                            }
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel(String(localized: "Error: \(error)"))
                        }
                    }
                    .padding(.vertical, 4)
                }
            } else {
                Text(String(localized: "Select a model above to see its status."))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            }

            Button {
                llmProvider.revealModelsFolder()
            } label: {
                Label(String(localized: "Show Models in Finder"), systemImage: "folder")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
            .help(String(localized: "Open the folder where local models are stored."))
        }
    }
    
    @ViewBuilder
    private func modelActionView(for modelType: LocalModelType) -> some View {
        switch llmProvider.loadState {
        case .idle, .checking:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(String(localized: "Checking status..."))
                    .foregroundStyle(.secondary)
            }
            .accessibilityLabel(String(localized: "Checking model status"))

        case .needsDownload:
            HStack(spacing: 8) {
                Button(String(localized: "Download \(modelType.displayName)")) {
                    llmProvider.startDownload()
                }
                .buttonStyle(.borderedProminent)
                .disabled(llmProvider.isDownloading)
                .help(String(localized: "Download the selected model for offline use."))

                if llmProvider.lastError != nil && llmProvider.retryCount < 3 {
                    Button(String(localized: "Retry Download")) {
                        llmProvider.retryDownload()
                    }
                    .disabled(llmProvider.isDownloading)
                    .buttonStyle(.bordered)
                    .help(String(localized: "Try downloading again if the previous attempt failed."))
                }
            }

        case .downloaded, .loaded:
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text(String(localized: "\(modelType.displayName) Ready"))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button(String(localized: "Delete Model")) {
                        showingDeleteAlert = true
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                    .help(String(localized: "Remove the downloaded model from disk."))
                    .disabled(llmProvider.isDownloading || llmProvider.running)
                }
            }

        case .loading:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(String(localized: "Loading \(modelType.displayName)..."))
                    .foregroundStyle(.secondary)
            }
            .accessibilityLabel("Loading model")

        case .error:
            if llmProvider.lastError?.contains("download") == true && llmProvider.retryCount < 3 {
                Button(String(localized: "Retry Download")) {
                    llmProvider.retryDownload()
                }
                .disabled(llmProvider.isDownloading)
                .buttonStyle(.bordered)
                .help(String(localized: "Try downloading again if the previous attempt failed."))
            } else {
                Text(String(localized: "Cannot proceed due to error."))
                    .foregroundStyle(.red)
            }
        }

        if llmProvider.isDownloading {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(String(localized: "Downloading \(modelType.displayName)..."))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button(action: { llmProvider.cancelDownload() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.gray)
                            .accessibilityLabel(String(localized: "Cancel download"))
                    }
                    .buttonStyle(.plain)
                    .help(String(localized: "Cancel the current download."))
                }
                ProgressView(value: llmProvider.downloadProgress) {
                    Text("\(Int(llmProvider.downloadProgress * 100))%")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .animation(.linear, value: llmProvider.downloadProgress)
                .accessibilityLabel(String(localized: "Download progress"))
            }
        }
    }
}
