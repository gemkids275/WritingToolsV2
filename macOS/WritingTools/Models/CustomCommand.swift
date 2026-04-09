import Foundation
import Observation

private let logger = AppLogger.logger("CustomCommandsManager")

struct CustomCommand: Codable, Identifiable, Equatable {
  let id: UUID
  var name: String
  var prompt: String
  var icon: String
  var useResponseWindow: Bool

  init(
    id: UUID = UUID(),
    name: String,
    prompt: String,
    icon: String,
    useResponseWindow: Bool = false
  ) {
    self.id = id
    self.name = name
    self.prompt = prompt
    self.icon = icon
    self.useResponseWindow = useResponseWindow
  }
}

/// Legacy manager retained only for reading existing local custom commands
/// during migration to the unified CommandManager system.
@MainActor
@Observable
final class CustomCommandsManager {
  private(set) var commands: [CustomCommand] = []

  private let saveKey = "custom_commands"

  init() {
    loadLocalCommands()
  }

  // MARK: - Public API

  func addCommand(_ command: CustomCommand) {
    commands.append(command)
    saveCommands()
  }

  func updateCommand(_ command: CustomCommand) {
    if let index = commands.firstIndex(where: { $0.id == command.id }) {
      commands[index] = command
      saveCommands()
    }
  }

  func deleteCommand(_ command: CustomCommand) {
    commands.removeAll { $0.id == command.id }
    saveCommands()
  }

  func replaceCommands(with newCommands: [CustomCommand]) {
    commands = newCommands
    saveCommands()
  }

  // MARK: - Local persistence

  private func loadLocalCommands() {
    if
      let data = UserDefaults.standard.data(forKey: saveKey),
      let decoded = try? JSONDecoder().decode([CustomCommand].self, from: data)
    {
      commands = decoded
    }
  }

  private func saveCommands() {
    if let encoded = try? JSONEncoder().encode(commands) {
      UserDefaults.standard.set(encoded, forKey: saveKey)
    }
  }
}
