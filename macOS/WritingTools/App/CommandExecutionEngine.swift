import AppKit

private let logger = AppLogger.logger("CommandExecutionEngine")

enum CommandExecutionEngineError: LocalizedError {
  case emptyInstruction
  case captureInProgress
  case noNewCopiedContent(commandName: String)
  case emptySelection(commandName: String)
  case customProviderConfigurationIncomplete(commandName: String, missingFields: [String])

  var errorDescription: String? {
    switch self {
    case .emptyInstruction:
      return "Instruction cannot be empty."
    case .captureInProgress:
      return "Clipboard capture is already in progress."
    case .noNewCopiedContent(let commandName):
      return "No new content was copied for command: \(commandName)"
    case .emptySelection(let commandName):
      return "No text or images selected for command: \(commandName)"
    case .customProviderConfigurationIncomplete(let commandName, let missingFields):
      let fieldList = missingFields.joined(separator: ", ")
      return "Custom provider for '\(commandName)' is incomplete. Missing: \(fieldList). Update the command's custom provider settings."
    }
  }

  var missingCustomProviderFields: [String]? {
    guard case .customProviderConfigurationIncomplete(_, let missingFields) = self else {
      return nil
    }
    return missingFields
  }
}

@MainActor
final class CommandExecutionEngine {
  enum ExecutionSource {
    case popup
    case hotkey
  }

  enum ExecutionOutcome {
    case completedInline
    case openedResponseWindow
    case skippedBecauseBusy
  }

  static let shared = CommandExecutionEngine(appState: AppState.shared)

  private let appState: AppState

  private init(appState: AppState) {
    self.appState = appState
  }

  @discardableResult
  func executeCommand(
    _ command: CommandModel,
    source: ExecutionSource,
    closePopupOnInlineCompletion: (() -> Void)? = nil
  ) async throws -> ExecutionOutcome {
    guard !appState.isProcessing else {
      logger.debug("Command ignored because a request is already in progress.")
      return .skippedBecauseBusy
    }

    appState.isProcessing = true

    let input: CommandExecutionInput
    let provider: any AIProvider
    let shouldUseResponseWindow: Bool

    do {
      try await prepareSelectionIfNeeded(for: source, commandName: command.name)
      try validateCustomProviderConfiguration(for: command)
      input = try await appState.resolveCommandInput(mode: .textOrImagesWithOCRFallback)
      provider = appState.getProvider(for: command)
      shouldUseResponseWindow = command.useResponseWindow || input.source == .imageOCRFallback
    } catch {
      appState.isProcessing = false
      throw error
    }

    if shouldUseResponseWindow {
      // Response windows manage their own processing lifecycle independently,
      // so release the global isProcessing guard to allow other commands.
      appState.isProcessing = false

      let selectedText = input.source == .selectedText ? appState.selectedText : "Image selection (OCR)"
      openStreamingResponseWindow(
        title: command.name,
        selectedText: selectedText,
        provider: provider,
        systemPrompt: command.prompt,
        userPrompt: input.userPrompt,
        images: input.images,
        continuationSystemPrompt: command.prompt,
        source: source
      )
      return .openedResponseWindow
    }

    defer { appState.isProcessing = false }

    var result = try await provider.processText(
      systemPrompt: command.prompt,
      userPrompt: input.userPrompt,
      images: input.images,
      streaming: false
    )

    if input.source == .selectedText {
      result = Self.normalizedInlineReplacement(
        result,
        originalSelectedText: appState.selectedText
      )
    }

    if command.effectivePreserveFormatting, appState.selectedAttributedText != nil {
      appState.replaceSelectedTextPreservingAttributes(with: result)
    } else {
      appState.replaceSelectedText(with: result)
    }

    if source == .popup {
      closePopupOnInlineCompletion?()
    }

    return .completedInline
  }

  @discardableResult
  func executeCustomInstruction(
    _ instruction: String,
    source: ExecutionSource,
    openInResponseWindow: Bool,
    closePopupOnInlineCompletion: (() -> Void)? = nil
  ) async throws -> ExecutionOutcome {
    let customCommand = AppSettings.shared.customInstructionCommand
    let trimmedInstruction = instruction.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmedInstruction.isEmpty else {
      throw CommandExecutionEngineError.emptyInstruction
    }

    guard !appState.isProcessing else {
      logger.debug("Custom instruction ignored because a request is already in progress.")
      return .skippedBecauseBusy
    }

    appState.isProcessing = true

    do {
      try await prepareSelectionIfNeeded(for: source, commandName: "Custom Instruction")
    } catch {
      appState.isProcessing = false
      throw error
    }

    // Process attachments from appState
    var combinedImages = appState.selectedImages
    var attachmentContext = ""
    
    for attachment in appState.customAttachments {
        switch attachment {
        case .image(let data):
            combinedImages.append(data)
        case .text(let text, let label):
            attachmentContext += "\n[\(label ?? "Context")]:\n\(text)\n"
        case .file(let url, let data):
            if let data, let text = String(data: data, encoding: .utf8) {
                attachmentContext += "\n[File: \(url.lastPathComponent)]:\n\(text)\n"
            }
        }
    }

    let systemPrompt = customCommand.prompt
    let openInResponseWindow = customCommand.useResponseWindow
    let provider = appState.getProvider(for: customCommand)
    let selectedText = appState.selectedText
    
    var userPrompt = selectedText.isEmpty
      ? trimmedInstruction
      : """
        User's instruction: \(trimmedInstruction)

        Text:
        \(selectedText)
        """
    
    if !attachmentContext.isEmpty {
        userPrompt += "\n\nAdditional Context:\n\(attachmentContext)"
    }

    if openInResponseWindow {
      // Response windows manage their own processing lifecycle independently.
      appState.isProcessing = false

      openStreamingResponseWindow(
        title: customCommand.name,
        selectedText: selectedText.isEmpty ? trimmedInstruction : selectedText,
        provider: provider,
        systemPrompt: systemPrompt,
        userPrompt: userPrompt,
        images: combinedImages,
        continuationSystemPrompt: systemPrompt,
        source: source
      )
      return .openedResponseWindow
    }

    defer { appState.isProcessing = false }

    var result = try await provider.processText(
      systemPrompt: systemPrompt,
      userPrompt: userPrompt,
      images: combinedImages,
      streaming: false
    )

    result = Self.normalizedInlineReplacement(
      result,
      originalSelectedText: selectedText
    )
    if appState.selectedAttributedText != nil {
      appState.replaceSelectedTextPreservingAttributes(with: result)
    } else {
      appState.replaceSelectedText(with: result)
    }

    if source == .popup {
      closePopupOnInlineCompletion?()
    }

    return .completedInline
  }

  private func prepareSelectionIfNeeded(
    for source: ExecutionSource,
    commandName: String
  ) async throws {
    guard source == .hotkey else { return }

    let previousApp = NSWorkspace.shared.frontmostApplication
    guard let capture = await ClipboardCoordinator.shared.captureSelection() else {
      throw CommandExecutionEngineError.captureInProgress
    }

    guard capture.didChange else {
      throw CommandExecutionEngineError.noNewCopiedContent(commandName: commandName)
    }

    guard !capture.text.isEmpty || !capture.images.isEmpty else {
      throw CommandExecutionEngineError.emptySelection(commandName: commandName)
    }

    logger.debug(
      """
      Captured selection for \(commandName) \
      (text length: \(capture.text.count), images: \(capture.images.count))
      """
    )

    appState.selectedImages = capture.images
    appState.selectedAttributedText = capture.attributedText
    appState.selectedText = capture.text

    if let previousApp {
      appState.previousApplication = previousApp
    }
  }

  private func validateCustomProviderConfiguration(for command: CommandModel) throws {
    guard command.providerOverride == "custom" else { return }

    let baseURL = command.customProviderBaseURL?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let model = command.customProviderModel?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let apiKey =
      KeychainManager.shared.retrieveCustomProviderApiKeySync(for: command.id)?
      .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

    guard
      let error = Self.customProviderConfigurationErrorIfIncomplete(
        commandName: command.name,
        baseURL: baseURL,
        apiKey: apiKey,
        model: model
      )
    else { return }

    logger.error(
      """
      CommandExecutionEngine: custom provider configuration incomplete for \(command.name) \
      (missing: \((error.missingCustomProviderFields ?? []).joined(separator: ", ")))
      """
    )
    throw error
  }

  nonisolated static func customProviderConfigurationErrorIfIncomplete(
    commandName: String,
    baseURL: String?,
    apiKey: String?,
    model: String?
  ) -> CommandExecutionEngineError? {
    let missingFields = missingCustomProviderFields(baseURL: baseURL, apiKey: apiKey, model: model)
    guard !missingFields.isEmpty else { return nil }
    return .customProviderConfigurationIncomplete(commandName: commandName, missingFields: missingFields)
  }

  nonisolated static func missingCustomProviderFields(baseURL: String?, apiKey: String?, model: String?) -> [String] {
    var missingFields: [String] = []
    if baseURL?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
      missingFields.append("Base URL")
    }
    if apiKey?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
      missingFields.append("API Key")
    }
    if model?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
      missingFields.append("Model")
    }
    return missingFields
  }

  /// Ensures the output preserves a trailing newline when the original text had one.
  /// Exposed as `static` for unit testing.
  nonisolated static func normalizedInlineReplacement(
    _ output: String,
    originalSelectedText: String
  ) -> String {
    guard originalSelectedText.hasSuffix("\n"), !output.hasSuffix("\n") else {
      return output
    }
    return output + "\n"
  }

  private func openStreamingResponseWindow(
    title: String,
    selectedText: String,
    provider: any AIProvider,
    systemPrompt: String,
    userPrompt: String,
    images: [Data],
    continuationSystemPrompt: String,
    source: ExecutionSource
  ) {
    let window = ResponseWindow(
      title: title,
      selectedText: selectedText,
      option: nil,
      provider: provider,
      systemPrompt: systemPrompt,
      userPrompt: userPrompt,
      images: images,
      continuationSystemPrompt: continuationSystemPrompt
    )

    if source == .popup {
      // Keep response windows frontmost when launched from popup actions.
      WindowManager.shared.dismissPopup(clearImages: false)
    }

    WindowManager.shared.addResponseWindow(window)
  }
}
