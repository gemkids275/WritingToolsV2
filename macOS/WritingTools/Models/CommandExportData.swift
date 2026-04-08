import Foundation

struct CommandExportData: Codable {
    let version: Int
    let exportDate: Date
    let commands: [CommandModel]
    let customInstruction: CommandModel?
    
    // Add a signature to verify this is a valid Vyn export
    let appIdentifier: String
    
    init(commands: [CommandModel], customInstruction: CommandModel? = nil) {
        self.version = 1
        self.exportDate = Date()
        self.commands = commands
        self.customInstruction = customInstruction
        self.appIdentifier = "VynWritingTools"
    }
}
