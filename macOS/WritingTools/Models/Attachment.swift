import Foundation
import UniformTypeIdentifiers

public enum Attachment: Identifiable, Equatable, Sendable {
    case image(Data)
    case text(String, label: String? = nil)
    case file(URL, data: Data?)
    
    public var id: String {
        switch self {
        case .image(let data):
            return "img-\(data.count)-\(data.hashValue)"
        case .text(let content, let label):
            return "txt-\(label ?? "plain")-\(content.hashValue)"
        case .file(let url, _):
            return "file-\(url.path())"
        }
    }
    
    public var iconName: String {
        switch self {
        case .image:
            return "photo"
        case .text:
            return "doc.text"
        case .file:
            return "doc.fill"
        }
    }
    
    public var displayName: String {
        switch self {
        case .image:
            return "Image"
        case .text(_, let label):
            return label ?? "Text context"
        case .file(let url, _):
            return url.lastPathComponent
        }
    }
}
