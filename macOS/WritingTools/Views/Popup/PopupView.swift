import SwiftUI
import ApplicationServices
import Observation

private let logger = AppLogger.logger("PopupView")

@MainActor
@Observable
final class PopupViewModel {
  var isEditMode: Bool = false
}

struct PopupView: View {
  @Bindable var appState: AppState
  @Bindable var viewModel: PopupViewModel
  @Bindable private var settings = AppSettings.shared
  @Environment(\.colorScheme) var colorScheme

  @State private var isCustomLoading: Bool = false
  @State private var processingCommandId: UUID? = nil
  @State private var draggingCommandId: UUID? = nil

  @State private var showingCommandsView = false
  @State private var editingCommand: CommandModel? = nil

  // Error handling
  @State private var showingErrorAlert = false
  @State private var errorMessage = ""
  
  // Track in-flight custom instruction task to prevent races
  @State private var customInstructionTask: Task<Void, Never>?
  
  // Focus management for accessibility
  @FocusState private var isTextFieldFocused: Bool
  @State private var isImporting = false

  let closeAction: () -> Void

  // Grid layout for two columns
  private let columns = [
    GridItem(.flexible(), spacing: 8),
    GridItem(.flexible(), spacing: 8),
  ]

  var body: some View {
    VStack(spacing: 16) {
      topBar
      
      if !viewModel.isEditMode {
        customInputSection
      }

      if !appState.selectedText.isEmpty || !appState.selectedImages.isEmpty {
        commandButtonsGrid
          .padding(.horizontal, 16)
      }

      editModeControls
    }
    .padding(.bottom, 8)
    .windowBackground(useGradient: settings.useGradientTheme, cornerRadius: 20)
    .overlay(
      RoundedRectangle(cornerRadius: 20)
        .strokeBorder(Color.gray.opacity(0.2), lineWidth: 1)
    )
    .clipShape(.rect(cornerRadius: 20))
    .shadow(color: Color.black.opacity(0.2), radius: 10, y: 5)
    .sheet(item: $editingCommand) { command in
      commandEditorSheet(command: command)
    }
    .sheet(isPresented: $showingCommandsView) {
      CommandsView(commandManager: appState.commandManager)
    }
    .onChange(of: editingCommand) { _, newValue in
      WindowManager.shared.setPopupDismissSuppressed(newValue != nil, reason: .commandEditorSheet)
    }
    .onChange(of: showingCommandsView) { _, newValue in
      WindowManager.shared.setPopupDismissSuppressed(newValue, reason: .commandsManagerSheet)
    }
    .alert("Error", isPresented: $showingErrorAlert) {
      Button("OK", role: .cancel) {}
    } message: {
      Text(errorMessage)
    }
    .fileImporter(
        isPresented: $isImporting,
        allowedContentTypes: [.item],
        allowsMultipleSelection: true
    ) { result in
        handleFileImport(result: result)
    }
    .onPasteCommand(of: [.item]) { _ in
        appState.handlePaste()
    }
  }

  // MARK: - Subviews (Refactored to smaller blocks)

  private var topBar: some View {
    HStack {
      Button(action: {
        if viewModel.isEditMode {
          viewModel.isEditMode = false
        } else {
          closeAction()
        }
      }) {
        Image(systemName: "xmark")
          .font(.body)
          .foregroundStyle(.secondary)
          .frame(width: 28, height: 28)
          .background(Color(.controlBackgroundColor))
          .clipShape(.circle)
      }
      .buttonStyle(.plain)
      .help(viewModel.isEditMode ? "Exit Edit Mode" : "Close")
      .padding(.top, 8)
      .padding(.leading, 8)

      Spacer()

      Button(action: {
        viewModel.isEditMode.toggle()
      }) {
        Image(systemName: viewModel.isEditMode ? "checkmark" : "square.and.pencil")
          .font(.body)
          .foregroundStyle(.secondary)
          .frame(width: 28, height: 28)
          .background(Color(.controlBackgroundColor))
          .clipShape(.circle)
      }
      .buttonStyle(.plain)
      .help(viewModel.isEditMode ? "Save Changes" : "Edit Commands")
      .padding(.top, 8)
      .padding(.trailing, 8)
    }
  }

  private var customInputSection: some View {
    VStack(spacing: 8) {
      HStack(spacing: 8) {
        CustomTextEditor(text: $appState.customText, placeholder: "Describe your change...", onSubmit: processCustomChange)
          .frame(minHeight: 100, maxHeight: 300)
          .focused($isTextFieldFocused)
          .appleStyleTextField(
            text: appState.customText,
            isLoading: isCustomLoading,
            topContent: appState.customAttachments.isEmpty ? nil : AnyView(attachmentsRow),
            onAttach: { isImporting = true },
            onSubmit: processCustomChange
          )
        
        if viewModel.isEditMode {
          Button(action: {
            editingCommand = AppSettings.shared.customInstructionCommand
          }) {
            Image(systemName: "square.and.pencil")
              .font(.system(size: 13))
              .foregroundStyle(.secondary)
              .frame(width: 24, height: 24)
              .background(Color.gray.opacity(colorScheme == .dark ? 0.3 : 0.1))
              .clipShape(.circle)
          }
          .buttonStyle(.plain)
          .padding(.bottom, 6)
          .help("Edit Custom Response Prompt")
        }
      }
      .padding(.horizontal)
    }
    .onAppear {
      Task { @MainActor in
        try? await Task.sleep(for: .milliseconds(100))
        isTextFieldFocused = true
      }
    }
  }

  private var attachmentsRow: some View {
    Group {
      if !appState.customAttachments.isEmpty {
        DraggableHScrollView {
          HStack(spacing: 8) {
            ForEach(appState.customAttachments) { attachment in
              AttachmentThumbnail(attachment: attachment) {
                appState.removeAttachment(id: attachment.id)
              }
            }
          }
          .padding(.horizontal)
        }
        .frame(height: 50)
        .transition(.move(edge: .top).combined(with: .opacity))
      }
    }
  }
  
  private var editModeControls: some View {
    Group {
      if viewModel.isEditMode {
        Button(action: { showingCommandsView = true }) {
          HStack {
            Image(systemName: "plus.circle.fill")
            Text("Manage Commands")
          }
          .frame(maxWidth: .infinity)
          .padding()
          .background(Color(.controlBackgroundColor))
          .clipShape(.rect(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 16)
      }
    }
  }

  @ViewBuilder
  private func commandEditorSheet(command: CommandModel) -> some View {
    let binding = Binding(
      get: { command },
      set: { updatedCommand in
        if updatedCommand.id == CommandModel.BuiltInID.customInstruction {
          AppSettings.shared.customInstructionCommand = updatedCommand
        } else {
          appState.commandManager.updateCommand(updatedCommand)
        }
        editingCommand = nil
      }
    )

    CommandEditor(
      command: binding,
      onSave: { editingCommand = nil },
      onCancel: { editingCommand = nil },
      commandManager: appState.commandManager
    )
  }

  // MARK: - Handlers

  private func handleFileImport(result: Result<[URL], Error>) {
    switch result {
    case .success(let urls):
      let rejected = urls.filter { !appState.addAttachment(from: $0) }.map { $0.lastPathComponent }
      if !rejected.isEmpty {
        errorMessage = "Unsupported file(s): \(rejected.joined(separator: ", "))\nOnly images and plain text files are supported."
        showingErrorAlert = true
      }
    case .failure(let error):
      logger.error("File import failed: \(error.localizedDescription)")
    }
  }

  // MARK: - Sub-structs
  
  struct AttachmentThumbnail: View {
      let attachment: Attachment
      let onRemove: () -> Void
      
      var body: some View {
          ZStack(alignment: .topTrailing) {
              Group {
                  switch attachment {
                  case .image(let data):
                      if let nsImage = NSImage(data: data) {
                          Image(nsImage: nsImage)
                              .resizable()
                              .aspectRatio(contentMode: .fill)
                      } else {
                          placeholder
                      }
                  default:
                      placeholder
                  }
              }
              .frame(width: 44, height: 44)
              .clipShape(RoundedRectangle(cornerRadius: 6))
              .overlay(
                  RoundedRectangle(cornerRadius: 6)
                      .stroke(Color.gray.opacity(0.3), lineWidth: 1)
              )
              
              Button(action: onRemove) {
                  Image(systemName: "xmark.circle.fill")
                      .symbolRenderingMode(.palette)
                      .foregroundStyle(.white, .black.opacity(0.6))
                      .font(.system(size: 14))
              }
              .buttonStyle(.plain)
              .offset(x: 6, y: -6)
          }
          .help(attachment.displayName)
      }
      
      private var placeholder: some View {
          VStack(spacing: 2) {
              Image(systemName: attachment.iconName)
                  .font(.system(size: 14))
              Text(attachment.displayName)
                  .font(.system(size: 8))
                  .lineLimit(1)
          }
          .frame(maxWidth: .infinity, maxHeight: .infinity)
          .background(Color.gray.opacity(0.1))
      }
  }

  // MARK: - Command Buttons Grid

  @ViewBuilder
  private var commandButtonsGrid: some View {
    let grid = LazyVGrid(columns: columns, spacing: 8) {
      ForEach(appState.commandManager.commands) { command in
        CommandButton(
          command: command,
          isEditing: viewModel.isEditMode,
          isLoading: processingCommandId == command.id,
          onTap: {
            processingCommandId = command.id
            Task {
              await processCommandAndCloseWhenDone(command)
            }
          },
          onEdit: {
            editingCommand = command
          },
          onDelete: {
            logger.debug("Deleting command: \(command.name)")
            appState.commandManager.deleteCommand(command)
          }
        )
        .opacity(draggingCommandId == command.id ? 0.4 : 1)
        .onDrag {
          guard viewModel.isEditMode else { return NSItemProvider() }
          draggingCommandId = command.id
          return NSItemProvider(object: command.id.uuidString as NSString)
        }
        .onDrop(
          of: [.text],
          delegate: CommandDropDelegate(
            targetCommand: command,
            commands: appState.commandManager.commands,
            draggingId: $draggingCommandId,
            onMove: { from, to in
              appState.commandManager.moveCommand(fromOffsets: from, toOffset: to)
            }
          )
        )
      }
    }

    if #available(macOS 26, *) {
      GlassEffectContainer(spacing: 0) {
        grid
      }
    } else {
      grid
    }
  }

  // Process a command asynchronously and only close the popup when done
  private func processCommandAndCloseWhenDone(_ command: CommandModel) async {
    defer { processingCommandId = nil }

    do {
      _ = try await CommandExecutionEngine.shared.executeCommand(
        command,
        source: .popup,
        closePopupOnInlineCompletion: closeAction
      )
    } catch {
      logger.error("Error processing command: \(error.localizedDescription)")
      errorMessage = error.localizedDescription
      showingErrorAlert = true
    }
  }

  private func processCustomChange() {
    let instruction = appState.customText.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !instruction.isEmpty else { return }
    customInstructionTask?.cancel()
    isCustomLoading = true
    customInstructionTask = Task {
      await processCustomInstruction(instruction)
    }
  }

  private func processCustomInstruction(_ instruction: String) async {
    defer { isCustomLoading = false }

    do {
      let outcome = try await CommandExecutionEngine.shared.executeCustomInstruction(
        instruction,
        source: .popup,
        openInResponseWindow: AppSettings.shared.openCustomCommandsInResponseWindow,
        closePopupOnInlineCompletion: closeAction
      )
      if outcome != .skippedBecauseBusy {
        appState.customText = ""
        appState.customAttachments = []
      }
    } catch {
      logger.error("Error processing text: \(error.localizedDescription)")
      errorMessage = error.localizedDescription
      showingErrorAlert = true
    }
  }
}

// MARK: - CommandDropDelegate

private struct CommandDropDelegate: DropDelegate {
  let targetCommand: CommandModel
  let commands: [CommandModel]
  @Binding var draggingId: UUID?
  let onMove: (IndexSet, Int) -> Void

  func performDrop(info: DropInfo) -> Bool {
    draggingId = nil
    return true
  }

  func dropEntered(info: DropInfo) {
    guard
      let draggingId,
      draggingId != targetCommand.id,
      let fromIndex = commands.firstIndex(where: { $0.id == draggingId }),
      let toIndex = commands.firstIndex(where: { $0.id == targetCommand.id })
    else { return }

    let destination = toIndex > fromIndex ? toIndex + 1 : toIndex
    withAnimation(.easeInOut(duration: 0.15)) {
      onMove(IndexSet(integer: fromIndex), destination)
    }
  }

  func dropUpdated(info: DropInfo) -> DropProposal? {
    DropProposal(operation: .move)
  }

  func validateDrop(info: DropInfo) -> Bool {
    draggingId != nil && draggingId != targetCommand.id
  }
}

// MARK: - DraggableHScrollView

private struct DraggableHScrollView<Content: View>: View {
  @ViewBuilder let content: () -> Content
  @GestureState private var dragOffset: CGFloat = 0
  @State private var baseOffset: CGFloat = 0
  @State private var contentWidth: CGFloat = 0
  @State private var containerWidth: CGFloat = 0

  var body: some View {
    GeometryReader { geo in
      content()
        .fixedSize(horizontal: true, vertical: false)
        .background(GeometryReader { inner in
          Color.clear
            .onAppear { contentWidth = inner.size.width }
            .onChange(of: inner.size.width) { _, w in contentWidth = w }
        })
        .offset(x: clampedOffset(base: baseOffset + dragOffset, container: geo.size.width))
        .onAppear { containerWidth = geo.size.width }
        .onChange(of: geo.size.width) { _, w in containerWidth = w }
    }
    .clipped()
    .gesture(
      DragGesture(minimumDistance: 3)
        .updating($dragOffset) { value, state, _ in
          state = value.translation.width
        }
        .onEnded { value in
          baseOffset = clampedOffset(base: baseOffset + value.translation.width, container: containerWidth)
        }
    )
    .onContinuousHover { phase in
      switch phase {
      case .active: NSCursor.openHand.push()
      case .ended: NSCursor.pop()
      }
    }
  }

  private func clampedOffset(base: CGFloat, container: CGFloat) -> CGFloat {
    let minOffset = min(0, container - contentWidth)
    return max(minOffset, min(0, base))
  }
}

// MARK: - Preview

#Preview("Popup View - Default") {
  @Previewable @State var appState = {
    let state = AppState.shared
    state.selectedText = """
      This is some sample text that has been selected by the user. \
      It could be a paragraph from a document, an email, or any other text \
      that needs to be processed by the AI shortcuts.
      """
    return state
  }()
  
  @Previewable @State var viewModel = PopupViewModel()
  
  PopupView(
    appState: appState,
    viewModel: viewModel,
    closeAction: {
      print("Close action triggered")
    }
  )
  .frame(width: 400, height: 500)
}
