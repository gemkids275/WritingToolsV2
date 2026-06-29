import SwiftUI
import AppKit

enum AppTheme: String, CaseIterable {
    case standard
    case gradient
    case glass
    case oled
    
    var displayName: String {
        switch self {
        case .standard: return String(localized: "Standard")
        case .gradient: return String(localized: "Gradient")
        case .glass: return String(localized: "Glass")
        case .oled: return String(localized: "OLED")
        }
    }
}

struct WindowBackground: ViewModifier {
    @Environment(\.colorScheme) var colorScheme
    @Bindable private var settings = AppSettings.shared
    let useGradient: Bool
    let cornerRadius: CGFloat?

    init(useGradient: Bool, cornerRadius: CGFloat? = nil) {
        self.useGradient = useGradient
        self.cornerRadius = cornerRadius
    }

    var currentTheme: AppTheme {
        if !useGradient {
            return .standard
        }
        return settings.themeStyle
    }

    func body(content: Content) -> some View {
        content
            .background(
                Group {
                    switch currentTheme {
                    case .standard:
                        Color(.windowBackgroundColor)
                    case .gradient:
                        MeshLikeGradientBackground()
                    case .glass:
                        GlassmorphicBackground()
                    case .oled:
                        Color.black
                    }
                }
                .clipShape(.rect(cornerRadius: cornerRadius ?? 0))
            )
    }
}

struct MeshLikeGradientBackground: View {
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        LinearGradient(
            colors: colorScheme == .light
                ? [Color(hex: "d4bfff"), Color(hex: "f5e6f8")]
                : [Color(hex: "452E6B"), Color(hex: "703F3F")],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }
}

struct GlassmorphicBackground: View {
    @Environment(\.colorScheme) var colorScheme
    @Environment(\.accessibilityReduceTransparency) var reduceTransparency

    var body: some View {
        ZStack {
            if reduceTransparency {
                // Fall back to a solid, high-contrast background
                colorScheme == .light ? Color(.windowBackgroundColor) : Color.black
            } else {
                // Use native Liquid Glass effect on macOS 16.0+ (internal version 26.0)
                if #available(macOS 26.0, *) {
                    LiquidGlassBackground()
                } else {
                    // Legacy glass effect for older macOS versions
                    LegacyGlassBackground(colorScheme: colorScheme)
                }
            }
        }
    }
}

/// Native Liquid Glass effect for macOS 26.0+
@available(macOS 26.0, *)
struct LiquidGlassBackground: View {
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        // Use SwiftUI's native Liquid Glass effect with rectangular shape
        Color.clear
            .glassEffect(
                .regular.tint(
                    colorScheme == .light 
                        ? Color.blue.opacity(0.08)
                        : Color.blue.opacity(0.05)
                ),
                in: .rect(cornerRadius: 0)
            )
    }
}

/// Legacy glass effect for macOS versions before 26.0.
/// Uses a single material layer with a lightweight gradient overlay to reduce GPU compositing.
struct LegacyGlassBackground: View {
    let colorScheme: ColorScheme
    
    var body: some View {
        ZStack {
            // Core blur/translucency material
            Rectangle()
                .fill(Material.thick)

            // Single combined highlight + tint gradient
            LinearGradient(
                colors: [
                    Color.white.opacity(colorScheme == .light ? 0.25 : 0.12),
                    Color.blue.opacity(0.06),
                    Color.clear
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            // Subtle inner border to define edges of the glass
            Rectangle()
                .strokeBorder(
                    Color.white.opacity(colorScheme == .light ? 0.25 : 0.12),
                    lineWidth: 0.5
                )
        }
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

extension View {
    func windowBackground(useGradient: Bool, cornerRadius: CGFloat? = nil) -> some View {
        modifier(WindowBackground(useGradient: useGradient, cornerRadius: cornerRadius))
    }
}



#Preview {
    MeshLikeGradientBackground()
}
