import SwiftUI
import MarkdownView
import Observation

// MARK: - String Extension for Markdown Processing

extension String {
    /// Strips outer markdown code block wrapper if the entire response is wrapped in one.
    /// Some AI models wrap their entire response in ```markdown fences.
    fileprivate func strippingOuterCodeBlock() -> String {
        let trimmed = self.trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Only unwrap markdown wrappers so legitimate code fences (e.g. ```swift) stay intact.
        let pattern = #"^```(?:markdown|md)\s*\n([\s\S]*?)\n```$"#
        
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]),
              let match = regex.firstMatch(in: trimmed, options: [], range: NSRange(trimmed.startIndex..., in: trimmed)),
              let contentRange = Range(match.range(at: 1), in: trimmed) else {
            return self
        }
        
        return String(trimmed[contentRange])
    }
    
    /// Applies all markdown normalizations for AI responses
    fileprivate func normalizedForMarkdown() -> String {
        return self.strippingOuterCodeBlock()
    }
}

// MARK: - Chat Message Model

struct ChatMessage: Identifiable, Equatable, Sendable {
    let id: UUID
    let role: String // "user" or "assistant"
    var content: String
    let timestamp: Date
    var isStreaming: Bool
    
    init(role: String, content: String, isStreaming: Bool = false) {
        self.id = UUID()
        self.role = role
        self.content = content
        self.timestamp = Date()
        self.isStreaming = isStreaming
    }
    
    static func == (lhs: ChatMessage, rhs: ChatMessage) -> Bool {
        lhs.id == rhs.id &&
        lhs.role == rhs.role &&
        lhs.content == rhs.content &&
        lhs.timestamp == rhs.timestamp &&
        lhs.isStreaming == rhs.isStreaming
    }
}

// MARK: - Response View

struct ResponseView: View {
    @State private var viewModel: ResponseViewModel
    @Bindable private var settings = AppSettings.shared
    @Environment(\.colorScheme) var colorScheme
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var inputText: String = ""
    @State private var isRegenerating: Bool = false
    @State private var errorMessage: String?
    @State private var showError: Bool = false
    @State private var followUpAttachments: [Attachment] = []
    @State private var isImporting = false
    
    init(
        content: String,
        selectedText: String,
        option: WritingOption? = nil,
        provider: any AIProvider,
        continuationSystemPrompt: String? = nil
    ) {
        self._viewModel = State(initialValue: ResponseViewModel(
            content: content,
            selectedText: selectedText,
            option: option,
            provider: provider,
            continuationSystemPrompt: continuationSystemPrompt
        ))
    }

    /// Streaming initializer: opens immediately and streams the AI response.
    init(
        selectedText: String,
        option: WritingOption? = nil,
        provider: any AIProvider,
        systemPrompt: String,
        userPrompt: String,
        images: [Data],
        continuationSystemPrompt: String? = nil
    ) {
        self._viewModel = State(initialValue: ResponseViewModel(
            selectedText: selectedText,
            option: option,
            provider: provider,
            systemPrompt: systemPrompt,
            userPrompt: userPrompt,
            images: images,
            continuationSystemPrompt: continuationSystemPrompt
        ))
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack(spacing: 16) {
                Button(action: { viewModel.copyContent() }) {
                    Label(viewModel.showCopyConfirmation ? "Copied!" : "Copy All",
                          systemImage: viewModel.showCopyConfirmation ? "checkmark" : "doc.on.doc")
                    .frame(minWidth: 80)
                }
                .buttonStyle(.borderedProminent)
                .animation(reduceMotion ? nil : .easeInOut, value: viewModel.showCopyConfirmation)
                
                Spacer()
                
                HStack(spacing: 12) {
                    Button(action: { viewModel.fontSize -= 1 }) {
                        Label("Decrease text size", systemImage: "textformat.size.smaller")
                            .labelStyle(.iconOnly)
                    }
                    .buttonStyle(.borderless)
                    .disabled(viewModel.fontSize <= 10)
                    .keyboardShortcut("-", modifiers: .command)
                    .accessibilityLabel("Decrease text size")
                    .accessibilityHint("Makes the response text smaller")
                    
                    Button(action: { viewModel.fontSize += 1 }) {
                        Label("Increase text size", systemImage: "textformat.size.larger")
                            .labelStyle(.iconOnly)
                    }
                    .buttonStyle(.borderless)
                    .disabled(viewModel.fontSize >= 20)
                    .keyboardShortcut("+", modifiers: .command)
                    .accessibilityLabel("Increase text size")
                    .accessibilityHint("Makes the response text larger")
                    
                    Button(action: {
                        viewModel.fontSize = 14
                    }) {
                        Label("Reset Font Size", systemImage: "arrow.counterclockwise")
                            .labelStyle(.iconOnly)
                    }
                    .buttonStyle(.borderless)
                    .keyboardShortcut("0", modifiers: .command)
                    .accessibilityLabel("Reset text size")
                    .accessibilityHint("Returns text size to the default")
                }
            }
            .padding()
            .background(Color.clear)
            
            // Chat messages area
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(viewModel.messages) { message in
                            ChatMessageView(message: message, fontSize: viewModel.fontSize)
                                .id(message.id)
                                .frame(maxWidth: .infinity, alignment: message.role == "user" ? .trailing : .leading)
                        }
                        
                        // Show loading indicator only when processing and no streaming message is visible
                        if viewModel.isProcessing && !(viewModel.messages.last?.isStreaming == true) {
                            HStack(alignment: .top, spacing: 12) {
                                HStack(spacing: 8) {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                    Text("Thinking...")
                                        .font(.system(size: 14))
                                        .foregroundStyle(.secondary)
                                }
                                .padding(12)
                                .background(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .fill(Color(.controlBackgroundColor))
                                )
                                Spacer(minLength: 15)
                            }
                            .padding(.top, 4)
                        }
                    }
                    .padding()
                }
                .onChange(of: viewModel.messages) { oldValue, newValue in
                    // Only scroll if messages were added (not on initial load)
                    guard newValue.count > oldValue.count else {
                        return
                    }
                    
                    if let lastId = newValue.last?.id {
                        if reduceMotion {
                            proxy.scrollTo(lastId, anchor: .bottom)
                        } else {
                            withAnimation {
                                proxy.scrollTo(lastId, anchor: .bottom)
                            }
                        }
                    }
                }
                .onChange(of: viewModel.messages.last?.content) { _, _ in
                    guard let lastMessage = viewModel.messages.last, lastMessage.isStreaming else {
                        return
                    }

                    if reduceMotion {
                        proxy.scrollTo(lastMessage.id, anchor: .bottom)
                    } else {
                        withAnimation(.linear(duration: 0.1)) {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
            }
            
            // Input area
            VStack(spacing: 8) {
                Divider()

                HStack(spacing: 8) {
                    CustomTextEditor(
                        text: $inputText,
                        placeholder: "Ask a follow-up question...",
                        onSubmit: sendMessage
                    )
                    .frame(minHeight: 36, maxHeight: 300)
                    .appleStyleTextField(
                        text: inputText,
                        isLoading: isRegenerating,
                        topContent: followUpAttachments.isEmpty ? nil : AnyView(followUpAttachmentsRow),
                        onAttach: { isImporting = true },
                        onSubmit: sendMessage
                    )
                    .disabled(viewModel.isProcessing)
                    .accessibilityLabel("Follow-up question")
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .background(Color(.windowBackgroundColor))
            .fileImporter(
                isPresented: $isImporting,
                allowedContentTypes: [.item],
                allowsMultipleSelection: true
            ) { result in
                handleFileImport(result: result)
            }
        }
        .windowBackground(useGradient: settings.useGradientTheme)
        .alert("Error", isPresented: $showError, presenting: errorMessage) { _ in
            Button("OK") { errorMessage = nil }
        } message: { message in
            Text(message)
        }
        .onDisappear {
            viewModel.cancelOngoingTasks()
        }
    }
    
    private var followUpAttachmentsRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(followUpAttachments) { attachment in
                    PopupView.AttachmentThumbnail(attachment: attachment) {
                        followUpAttachments.removeAll { $0.id == attachment.id }
                    }
                }
            }
            .padding(.horizontal)
        }
        .frame(height: 50)
    }

    private func handleFileImport(result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            var rejected: [String] = []
            for url in urls {
                let accessing = url.startAccessingSecurityScopedResource()
                defer { if accessing { url.stopAccessingSecurityScopedResource() } }
                let values = try? url.resourceValues(forKeys: [.contentTypeKey])
                let contentType = values?.contentType
                let imageExtensions: Set<String> = ["png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "tiff", "bmp"]
                let isImage = (contentType?.conforms(to: .image) ?? false) || imageExtensions.contains(url.pathExtension.lowercased())
                if isImage, let data = try? Data(contentsOf: url) {
                    followUpAttachments.append(.image(data))
                } else if let data = try? Data(contentsOf: url), let _ = String(data: data, encoding: .utf8) {
                    followUpAttachments.append(.file(url, data: data))
                } else {
                    rejected.append(url.lastPathComponent)
                }
            }
            if !rejected.isEmpty {
                errorMessage = "Unsupported file(s): \(rejected.joined(separator: ", "))\nOnly images and plain text files are supported."
                showError = true
            }
        case .failure(let error):
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    private func sendMessage() {
        guard !inputText.isEmpty, !viewModel.isProcessing else { return }
        let question = inputText
        let attachments = followUpAttachments
        inputText = ""
        followUpAttachments = []
        isRegenerating = true

        viewModel.startFollowUpQuestion(
            question,
            attachments: attachments,
            onCompletion: {
                isRegenerating = false
            },
            onFailure: { message in
                errorMessage = message
                showError = true
            }
        )
    }
}

// MARK: - Chat Message View

struct ChatMessageView: View {
    let message: ChatMessage
    let fontSize: CGFloat
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var showCopiedFeedback: Bool = false
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            if message.role == "assistant" {
                bubbleView(role: message.role).transition(.move(edge: .leading))
                Spacer(minLength: 15)
            } else {
                Spacer(minLength: 15)
                bubbleView(role: message.role).transition(.move(edge: .trailing))
            }
        }
        .padding(.top, 4)
        .animation(reduceMotion ? nil : .spring(), value: message.role)
    }
    
    @ViewBuilder
    private func bubbleView(role: String) -> some View {
        VStack(alignment: role == "assistant" ? .leading : .trailing, spacing: 2) {
            Group {
                if message.isStreaming && role == "assistant" {
                    if !message.content.isEmpty {
                        Text(message.content)
                            .font(.system(size: fontSize))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }
                } else {
                    RichMarkdownView(text: message.content, fontSize: fontSize)
                        // Keep markdown constrained to bubble width while allowing vertical growth.
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
            }
            .chatBubbleStyle(isFromUser: message.role == "user", isEmpty: message.isStreaming && message.content.isEmpty)
            .accessibilityLabel(message.role == "user" ? "Your message" : "Assistant's response")
            .accessibilityValue(message.content)
            .contextMenu {
                Button("Copy Selection") {
                    NSApp.sendAction(#selector(NSText.copy(_:)), to: nil, from: nil)
                }
                Button("Copy Message") {
                    copyEntireMessage()
                }
            }
            
            // Timestamp, streaming indicator, and copy button
            HStack(spacing: 8) {
                if message.isStreaming {
                    // Streaming indicator
                    HStack(spacing: 4) {
                        ProgressView()
                            .scaleEffect(0.6)
                        Text("Generating...")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text(message.timestamp.formatted(.dateTime.hour().minute()))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    
                    Button(action: copyEntireMessage) {
                        if showCopiedFeedback {
                            Text("Copied")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        } else {
                            Image(systemName: "doc.on.doc")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .buttonStyle(.plain)
                    .help(showCopiedFeedback ? "" : "Copy Message")
                    .accessibilityLabel("Copy message")
                    .accessibilityHint("Copies this message to the clipboard")
                }
            }
            .padding(.bottom, 2)
        }
        .frame(maxWidth: 500, alignment: role == "assistant" ? .leading : .trailing)
    }
    
    private func copyEntireMessage() {
        let pasteboard = NSPasteboard.general
        pasteboard.prepareForNewContents(with: [])
        pasteboard.writeObjects([message.content as NSString])
        
        showCopiedFeedback = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            showCopiedFeedback = false
        }
    }
}

// MARK: - View Model

@MainActor
@Observable
final class ResponseViewModel {

    // UserDefaults key for persistent font size storage
    private static let fontSizeKey = "ResponseView.fontSize"
    private static let defaultFontSize: CGFloat = 14

    var messages: [ChatMessage] = []
    var fontSize: CGFloat = 14 {
        didSet {
            // Debounce font size saves to prevent race conditions from rapid slider changes
            scheduleFontSizeSave()
        }
    }
    var showCopyConfirmation = false
    var isProcessing = false

    private let content: String
    private let selectedText: String
    private let option: WritingOption?
    private let continuationSystemPrompt: String?
    private let provider: any AIProvider

    // Store conversation history for context
    private var conversationHistory: [(role: String, content: String)] = []

    // Debounce task for font size persistence
    @ObservationIgnored
    private var fontSizeSaveTask: Task<Void, Never>?
    @ObservationIgnored
    private var initialStreamingTask: Task<Void, Never>?
    @ObservationIgnored
    private var followUpStreamingTask: Task<Void, Never>?

    init(
        content: String,
        selectedText: String,
        option: WritingOption?,
        provider: any AIProvider,
        continuationSystemPrompt: String?
    ) {
        // 🔧 Normalize markdown content (strip outer code blocks + normalize LaTeX)
        self.content = content.normalizedForMarkdown()
        self.selectedText = selectedText
        self.option = option
        self.continuationSystemPrompt = continuationSystemPrompt ?? option?.systemPrompt
        self.provider = provider

        // Load saved font size from UserDefaults, or use default
        let savedFontSize = UserDefaults.standard.object(forKey: Self.fontSizeKey) as? CGFloat
        self.fontSize = savedFontSize ?? Self.defaultFontSize

        // Add initial assistant message
        messages.append(ChatMessage(role: "assistant", content: self.content))

        // Initialize conversation history
        if !selectedText.isEmpty {
            conversationHistory.append((role: "user", content: selectedText))
        }
        conversationHistory.append((role: "assistant", content: self.content))
    }

    /// Streaming initializer: opens with an empty streaming message and begins generating immediately.
    init(
        selectedText: String,
        option: WritingOption?,
        provider: any AIProvider,
        systemPrompt: String,
        userPrompt: String,
        images: [Data],
        continuationSystemPrompt: String?
    ) {
        self.content = ""
        self.selectedText = selectedText
        self.option = option
        self.continuationSystemPrompt = continuationSystemPrompt ?? option?.systemPrompt ?? systemPrompt
        self.provider = provider

        let savedFontSize = UserDefaults.standard.object(forKey: Self.fontSizeKey) as? CGFloat
        self.fontSize = savedFontSize ?? Self.defaultFontSize

        // Start with a streaming placeholder
        messages.append(ChatMessage(role: "assistant", content: "", isStreaming: true))
        isProcessing = true

        if !selectedText.isEmpty {
            conversationHistory.append((role: "user", content: selectedText))
        }

        startInitialStreaming(
            systemPrompt: systemPrompt,
            userPrompt: userPrompt,
            images: images
        )
    }

    private func startInitialStreaming(
        systemPrompt: String,
        userPrompt: String,
        images: [Data]
    ) {
        initialStreamingTask?.cancel()
        initialStreamingTask = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.streamInitialResponse(
                systemPrompt: systemPrompt,
                userPrompt: userPrompt,
                images: images
            )
            self.initialStreamingTask = nil
        }
    }

    func startFollowUpQuestion(
        _ question: String,
        attachments: [Attachment] = [],
        onCompletion: @escaping @MainActor () -> Void,
        onFailure: @escaping @MainActor (String) -> Void
    ) {
        followUpStreamingTask?.cancel()
        followUpStreamingTask = Task { @MainActor [weak self] in
            guard let self else {
                onCompletion()
                return
            }

            defer {
                self.followUpStreamingTask = nil
                onCompletion()
            }

            do {
                try await self.processFollowUpQuestion(question, attachments: attachments)
            } catch is CancellationError {
                return
            } catch {
                onFailure(error.localizedDescription)
            }
        }
    }

    func cancelOngoingTasks() {
        initialStreamingTask?.cancel()
        followUpStreamingTask?.cancel()
        fontSizeSaveTask?.cancel()
        initialStreamingTask = nil
        followUpStreamingTask = nil
        fontSizeSaveTask = nil
        provider.cancel()
        isProcessing = false
    }

    /// Streams the initial AI response into the first message.
    private func streamInitialResponse(systemPrompt: String, userPrompt: String, images: [Data]) async {
        // Track by message ID instead of index to avoid out-of-bounds if array mutates
        guard let messageId = messages.first?.id else { return }

        do {
            var accumulatedContent = ""
            var lastUIFlushTime = ContinuousClock.now
            let minUIFlushInterval: Duration = .milliseconds(80)

            try await provider.processTextStreaming(
                systemPrompt: systemPrompt,
                userPrompt: userPrompt,
                images: images
            ) { [weak self] chunk in
                guard let self else { return }
                accumulatedContent += chunk
                let now = ContinuousClock.now
                if now - lastUIFlushTime >= minUIFlushInterval {
                    if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                        messages[idx].content = accumulatedContent
                    }
                    lastUIFlushTime = now
                }
            }

            let normalizedResponse = accumulatedContent.normalizedForMarkdown()

            if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                messages[idx].content = normalizedResponse
                messages[idx].isStreaming = false
            }

            conversationHistory.append((role: "assistant", content: normalizedResponse))
            isProcessing = false
        } catch is CancellationError {
            if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                messages[idx].isStreaming = false
            }
            isProcessing = false
        } catch {
            // Show error in the streaming message rather than removing it
            if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                messages[idx].content = "Error: \(error.localizedDescription)"
                messages[idx].isStreaming = false
            }
            isProcessing = false
        }
    }

    /// Debounced save of font size to UserDefaults
    private func scheduleFontSizeSave() {
        fontSizeSaveTask?.cancel()
        fontSizeSaveTask = Task { @MainActor [weak self] in
            // Wait 300ms before saving to debounce rapid slider movements
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled, let self else { return }
            UserDefaults.standard.set(self.fontSize, forKey: Self.fontSizeKey)
        }
    }
    
    func processFollowUpQuestion(_ question: String, attachments: [Attachment] = []) async throws {
        // Add user message to UI
        messages.append(ChatMessage(role: "user", content: question))
        
        // Add to conversation history
        conversationHistory.append((role: "user", content: question))
        
        isProcessing = true
        
        // Create a placeholder message for streaming, tracked by ID not index
        let streamingMessage = ChatMessage(role: "assistant", content: "", isStreaming: true)
        let messageId = streamingMessage.id
        messages.append(streamingMessage)
        
        do {
            // Build context-aware system prompt
            let systemPrompt = buildSystemPrompt()
            
            // Build user prompt with conversation context
            let userPrompt = buildUserPrompt(question: question)
            
            var accumulatedContent = ""
            var lastUIFlushTime = ContinuousClock.now
            let minUIFlushInterval: Duration = .milliseconds(80)
            
            // Build images from attachments
            var images: [Data] = []
            var attachmentContext = ""
            for attachment in attachments {
                switch attachment {
                case .image(let data): images.append(data)
                case .text(let text, let label): attachmentContext += "\n[\(label ?? "Context")]:\n\(text)\n"
                case .file(let url, let data):
                    if let data, let text = String(data: data, encoding: .utf8) {
                        attachmentContext += "\n[File: \(url.lastPathComponent)]:\n\(text)\n"
                    }
                }
            }
            let finalPrompt = attachmentContext.isEmpty ? userPrompt : userPrompt + "\n\nAdditional Context:\(attachmentContext)"

            try await provider.processTextStreaming(
                systemPrompt: systemPrompt,
                userPrompt: finalPrompt,
                images: images
            ) { [weak self] chunk in
                guard let self else { return }
                accumulatedContent += chunk
                let now = ContinuousClock.now
                if now - lastUIFlushTime >= minUIFlushInterval {
                    // Throttle UI updates while streaming to reduce render pressure.
                    if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                        messages[idx].content = accumulatedContent
                    }
                    lastUIFlushTime = now
                }
            }
            
            // Normalize markdown content (strip outer code blocks + normalize LaTeX)
            let normalizedResponse = accumulatedContent.normalizedForMarkdown()
            
            // Finalize the message
            if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                messages[idx].content = normalizedResponse
                messages[idx].isStreaming = false
            }
            
            // Add to conversation history, keeping only the last 20 entries
            // to prevent unbounded memory growth in long conversations
            conversationHistory.append((role: "assistant", content: normalizedResponse))
            if conversationHistory.count > 20 {
                conversationHistory.removeFirst(conversationHistory.count - 20)
            }
            
            // Cap displayed messages to prevent unbounded UI memory growth
            if messages.count > 100 {
                messages.removeFirst(messages.count - 100)
            }
            
            isProcessing = false
        } catch {
            // Remove the streaming message on error
            if let idx = messages.firstIndex(where: { $0.id == messageId }) {
                messages.remove(at: idx)
            }
            isProcessing = false
            throw error
        }
    }
    
    private func buildSystemPrompt() -> String {
        if let continuationSystemPrompt {
            return """
            You are a helpful AI assistant continuing a conversation about text modification.
            
            Original task: \(continuationSystemPrompt)
            
            The user may ask follow-up questions or request modifications. Provide helpful, 
            contextual responses based on the conversation history. Use Markdown formatting 
            where appropriate.
            """
        } else if let option = option {
            return """
            You are a helpful AI assistant continuing a conversation about text modification.
            
            Original task: \(option.systemPrompt)
            
            The user may ask follow-up questions or request modifications. Provide helpful, 
            contextual responses based on the conversation history. Use Markdown formatting 
            where appropriate.
            """
        } else {
            return """
            You are a helpful AI assistant. Answer the user's questions thoughtfully and 
            comprehensively. Maintain context from the conversation history. Use Markdown 
            formatting where appropriate.
            """
        }
    }
    
    private func buildUserPrompt(question: String) -> String {
        // Include recent conversation history for context (last 5 exchanges)
        let recentHistory = conversationHistory.suffix(10) // Last 5 exchanges (user + assistant)
        
        var prompt = ""
        
        // Add conversation history
        if recentHistory.count > 2 { // More than just the initial exchange
            prompt += "Conversation history:\n\n"
            for (_, exchange) in recentHistory.dropLast(1).enumerated() {
                let role = exchange.role == "user" ? "User" : "Assistant"
                prompt += "\(role): \(exchange.content)\n\n"
            }
            prompt += "---\n\n"
        }
        
        // Add current question
        prompt += "User's follow-up question: \(question)"
        
        return prompt
    }
    
    func copyContent() {
        let conversationText = messages.map { message in
            return "\(message.role.capitalized): \(message.content)"
        }.joined(separator: "\n\n")
        
        let pasteboard = NSPasteboard.general
        pasteboard.prepareForNewContents(with: [])
        pasteboard.writeObjects([conversationText as NSString])
        
        showCopyConfirmation = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            self.showCopyConfirmation = false
        }
    }

    deinit {
        initialStreamingTask?.cancel()
        followUpStreamingTask?.cancel()
        fontSizeSaveTask?.cancel()
        // Ensure the provider's in-flight request is also cancelled even if
        // onDisappear didn't fire (e.g., parent dismissed the window directly).
        // deinit of a @MainActor class runs on the main actor, but the compiler
        // cannot prove it — use assumeIsolated to bridge the gap.
        MainActor.assumeIsolated {
            provider.cancel()
        }
    }
}

// MARK: - Rich Markdown View

struct RichMarkdownView: View {
    let text: String
    let fontSize: CGFloat

    var body: some View {
        MarkdownView(text)
            .markdownMathRenderingEnabled()
            // Body text (paragraphs, list items, etc.)
            .font(.system(size: fontSize), for: .body)
            // Headings - scaled relative to base font size
            .font(.system(size: fontSize * 1.4, weight: .bold), for: .h1)
            .font(.system(size: fontSize * 1.25, weight: .bold), for: .h2)
            .font(.system(size: fontSize * 1.15, weight: .semibold), for: .h3)
            .font(.system(size: fontSize * 1.1, weight: .semibold), for: .h4)
            .font(.system(size: fontSize * 1.05, weight: .medium), for: .h5)
            .font(.system(size: fontSize, weight: .medium), for: .h6)
            // Code blocks
            .font(.system(size: fontSize, design: .monospaced), for: .codeBlock)
            // Block quotes
            .font(.system(size: fontSize), for: .blockQuote)
            // Tables
            .font(.system(size: fontSize, weight: .semibold), for: .tableHeader)
            .font(.system(size: fontSize), for: .tableBody)
            // Math
            .font(.system(size: fontSize), for: .inlineMath)
            .font(.system(size: fontSize + 2), for: .displayMath)
            // Tint for inline code
            .tint(.primary, for: .inlineCodeBlock)
    }
}
