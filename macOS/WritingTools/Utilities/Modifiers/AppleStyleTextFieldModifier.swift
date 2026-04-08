import SwiftUI

struct AppleStyleTextFieldModifier: ViewModifier {
    @Environment(\.colorScheme) var colorScheme
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    let isLoading: Bool
    let text: String
    let placeholder: String
    let topContent: AnyView?
    let onAttach: (() -> Void)?
    let onSubmit: () -> Void

    @State private var isAnimating: Bool = false
    @State private var isHovered: Bool = false
    @State private var isAttachHovered: Bool = false

    private let animationDuration = 0.3
    private let animationDelay: Duration = .milliseconds(300)

    private var animation: Animation? {
        reduceMotion ? nil : .easeInOut(duration: animationDuration)
    }

    func body(content: Content) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Attachments row
            if let topContent {
                topContent
                    .padding(.top, 4)
            }

            // Text input
            content
                .font(.system(size: 14))
                .foregroundStyle(colorScheme == .dark ? .white : .primary)
                .overlay(alignment: .topLeading) {
                    if !placeholder.isEmpty && text.isEmpty {
                        Text(placeholder)
                            .font(.system(size: 14))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 4)
                            .padding(.top, 7)
                            .allowsHitTesting(false)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.top, 10)
                .padding(.bottom, 4)

            // Bottom bar: attach + send
            HStack(spacing: 0) {
                if let onAttach {
                    Button(action: onAttach) {
                        Image(systemName: "paperclip")
                            .font(.system(size: 15))
                            .foregroundStyle(.secondary)
                            .frame(width: 32, height: 32)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .onHover { isAttachHovered = $0 }
                    .opacity(isAttachHovered ? 1.0 : 0.7)
                    .help("Attach File or Link")
                }

                Spacer()

                if !text.isEmpty {
                    Button(action: performSubmitAnimation) {
                        Image(systemName: isLoading ? "hourglass" : "paperplane.fill")
                            .foregroundStyle(.white)
                            .font(.system(size: 12))
                            .frame(width: 26, height: 26)
                            .background(isLoading ? Color.gray : Color.blue)
                            .clipShape(.circle)
                            .scaleEffect(isHovered ? 1.05 : 1.0)
                            .opacity(isHovered ? 1.0 : 0.9)
                    }
                    .buttonStyle(.plain)
                    .disabled(isLoading)
                    .transition(.opacity.combined(with: .scale(scale: 0.8)))
                    .onHover { isHovered = $0 }
                    .help(isLoading ? "Processing…" : "Send message")
                    .accessibilityLabel(isLoading ? "Processing" : "Send message")
                }
            }
            .padding(.horizontal, 8)
            .padding(.bottom, 6)
        }
        .background(
            ZStack {
                if colorScheme == .dark {
                    Color.black.opacity(0.2)
                        .blur(radius: 0.5)
                } else {
                    Color(.textBackgroundColor)
                }
                if isLoading {
                    Color.gray.opacity(0.1)
                }
            }
        )
        .clipShape(.rect(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isAnimating
                        ? Color.blue.opacity(0.8)
                        : Color.gray.opacity(0.2),
                    lineWidth: isAnimating ? 2 : 0.5
                )
                .animation(animation, value: isAnimating)
        )
    }

    private func performSubmitAnimation() {
        withAnimation(animation) { isAnimating = true }
        onSubmit()
        Task { @MainActor in
            if !reduceMotion {
                try? await Task.sleep(for: animationDelay)
            }
            withAnimation(animation) { isAnimating = false }
        }
    }
}

extension View {
    func appleStyleTextField(
        text: String,
        placeholder: String = "",
        isLoading: Bool = false,
        topContent: AnyView? = nil,
        onAttach: (() -> Void)? = nil,
        onSubmit: @escaping () -> Void
    ) -> some View {
        self.modifier(AppleStyleTextFieldModifier(
            isLoading: isLoading,
            text: text,
            placeholder: placeholder,
            topContent: topContent,
            onAttach: onAttach,
            onSubmit: onSubmit
        ))
    }
}
