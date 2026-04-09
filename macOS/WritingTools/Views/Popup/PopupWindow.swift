import SwiftUI

class PopupWindow: NSWindow {
  private var initialLocation: NSPoint?
  private var retainedHostingView: FirstResponderHostingView<PopupWindowContentView>?
  private var trackingArea: NSTrackingArea?
  private let appState: AppState
  private let windowWidth: CGFloat = 380

  private let viewModel = PopupViewModel()
  private var hasCompletedInitialLayout = false
  
  init(appState: AppState) {
    self.appState = appState

    super.init(
      contentRect: NSRect(x: 0, y: 0, width: windowWidth, height: 100),
      styleMask: [.borderless, .fullSizeContentView],
      backing: .buffered,
      defer: true
    )

    self.isReleasedWhenClosed = false

    configureWindow()
    setupTrackingArea()
  }

  private func configureWindow() {
    backgroundColor = .clear
    isOpaque = false
    level = .floating
    collectionBehavior = [.transient, .ignoresCycle]
    hasShadow = false

    let closeAction: () -> Void = { [weak self] in
      self?.close()
      if let bundleId = self?.appState.previousApplication?.bundleIdentifier {
        NSApp.yieldActivation(toApplicationWithBundleIdentifier: bundleId)
      }
      self?.appState.previousApplication?.activate(from: .current)
    }
    
    let swiftUIContent = PopupWindowContentView(
      appState: appState,
      viewModel: viewModel,
      closeAction: closeAction
    )

    let hostingView = FirstResponderHostingView(rootView: swiftUIContent)
    // sizingOptions = .intrinsicContentSize makes the hosting view call
    // invalidateIntrinsicContentSize() when SwiftUI content changes.
    // Auto Layout then resizes the view to the new intrinsicContentSize,
    // triggering setFrameSize — which we override to resize the window.
    hostingView.sizingOptions = .intrinsicContentSize
    hostingView.translatesAutoresizingMaskIntoConstraints = false
    hostingView.onHeightChange = { [weak self] height in
      self?.applyWindowHeight(height)
    }

    hostingView.wantsLayer = true
    hostingView.layer?.cornerRadius = 20
    hostingView.layer?.maskedCorners = [
      .layerMinXMinYCorner,
      .layerMaxXMinYCorner,
      .layerMinXMaxYCorner,
      .layerMaxXMaxYCorner,
    ]
    hostingView.layer?.masksToBounds = true

    // Use a plain container so we can pin the hosting view with Auto Layout.
    let container = NSView(frame: NSRect(x: 0, y: 0, width: windowWidth, height: 100))
    container.wantsLayer = true
    container.addSubview(hostingView)
    // No bottom constraint — hosting view sizes freely to intrinsicContentSize.
    // The window is resized separately via onHeightChange.
    NSLayoutConstraint.activate([
      hostingView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
      hostingView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
      hostingView.topAnchor.constraint(equalTo: container.topAnchor),
      hostingView.widthAnchor.constraint(equalToConstant: windowWidth),
    ])

    self.contentView = container
    retainedHostingView = hostingView

    initialFirstResponder = hostingView
    makeFirstResponder(hostingView)
    makeKey()

    WindowManager.shared.registerPopupWindow(self)
  }

  func applyWindowHeight(_ height: CGFloat) {
    guard !didCleanup else { return }
    let contentHeight = max(100, height)
    guard abs(contentHeight - frame.height) > 1 else { return }

    let animate = hasCompletedInitialLayout
    hasCompletedInitialLayout = true

    if animate {
      NSAnimationContext.runAnimationGroup({ context in
        context.duration = 0.2
        context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)

        self.animator().setContentSize(NSSize(width: self.windowWidth, height: contentHeight))

        if let screen = self.screen {
          var frame = self.frame
          frame.size.height = contentHeight

          if frame.maxY > screen.visibleFrame.maxY {
            frame.origin.y = screen.visibleFrame.maxY - frame.height
          }
          self.animator().setFrame(frame, display: true)
        }
      }, completionHandler: { [weak self] in
        self?.setupTrackingArea()
      })
    } else {
      setContentSize(NSSize(width: windowWidth, height: contentHeight))
      if let screen = self.screen {
        var frame = self.frame
        frame.size.height = contentHeight
        if frame.maxY > screen.visibleFrame.maxY {
          frame.origin.y = screen.visibleFrame.maxY - frame.height
        }
        setFrame(frame, display: true)
      }
      setupTrackingArea()
    }
  }


  private func setupTrackingArea() {
    guard let contentView = contentView else { return }

    if let existing = trackingArea {
      contentView.removeTrackingArea(existing)
    }

    trackingArea = NSTrackingArea(
      rect: contentView.bounds,
      options: [.mouseEnteredAndExited, .activeAlways, .mouseMoved],
      owner: self,
      userInfo: nil
    )

    if let trackingArea = trackingArea {
      contentView.addTrackingArea(trackingArea)
    }
  }

  private var didCleanup = false

  func cleanup() {
    guard !didCleanup else { return }
    didCleanup = true

    if let contentView = contentView, let trackingArea = trackingArea {
      contentView.removeTrackingArea(trackingArea)
      self.trackingArea = nil
    }

    if let hostingView = retainedHostingView {
      hostingView.removeFromSuperview()
      self.retainedHostingView = nil
    }

    self.contentView = nil
  }

  override func close() {
    cleanup()
    super.close()
  }

  override var canBecomeKey: Bool { true }
  override var canBecomeMain: Bool { true }

  // Mouse Event Handling
  override func mouseDown(with event: NSEvent) {
    initialLocation = event.locationInWindow
  }

  override func mouseDragged(with event: NSEvent) {
    guard contentView != nil, let initialLocation = initialLocation else { return }

    let currentLocation = event.locationInWindow
    let deltaX = currentLocation.x - initialLocation.x
    let deltaY = currentLocation.y - initialLocation.y

    var newOrigin = frame.origin
    newOrigin.x += deltaX
    newOrigin.y += deltaY

    // Use the screen the mouse is currently on to support dragging across screens
    let mouseLocation = NSEvent.mouseLocation
    let targetScreen = NSScreen.screens.first(where: { $0.frame.contains(mouseLocation) })
      ?? screen ?? NSScreen.main

    if let targetScreen {
      let padding: CGFloat = 20
      let screenFrame = targetScreen.visibleFrame
      newOrigin.x = max(
        screenFrame.minX + padding,
        min(newOrigin.x, screenFrame.maxX - frame.width - padding)
      )
      newOrigin.y = max(
        screenFrame.minY + padding,
        min(newOrigin.y, screenFrame.maxY - frame.height - padding)
      )
    }

    setFrameOrigin(newOrigin)
  }

  override func mouseUp(with event: NSEvent) {
    initialLocation = nil
  }

  // Window Positioning

  func screenAt(point: NSPoint) -> NSScreen? {
    for screen in NSScreen.screens {
      if screen.frame.contains(point) {
        return screen
      }
    }
    return nil
  }

  func positionNearMouse() {
    let mouseLocation = NSEvent.mouseLocation
    guard
      let screen = NSScreen.screens.first(where: {
        $0.frame.contains(mouseLocation)
      }) ?? NSScreen.main
    else { return }

    let padding: CGFloat = 10
    var windowFrame = frame
    windowFrame.size.width = windowWidth

    windowFrame.origin.x = mouseLocation.x - (windowWidth / 2)
    windowFrame.origin.y = mouseLocation.y - windowFrame.height - padding

    windowFrame.origin.x = max(
      screen.visibleFrame.minX + padding,
      min(
        windowFrame.origin.x,
        screen.visibleFrame.maxX - windowWidth - padding
      )
    )

    if windowFrame.minY < screen.visibleFrame.minY {
      windowFrame.origin.y = mouseLocation.y + padding
    }

    setFrame(windowFrame, display: true)
  }

  // Close via ESC Key
  override func keyDown(with event: NSEvent) {
    if event.keyCode == 53 {
      self.close()
    } else {
      super.keyDown(with: event)
    }
  }
}

// Note: Window delegate is managed by WindowManager.
// PopupWindow level is set to .popUpMenu when it becomes key (handled in WindowManager.windowDidBecomeKey).

class FirstResponderHostingView<Content: View>: NSHostingView<Content> {
  var onHeightChange: ((CGFloat) -> Void)?

  override var acceptsFirstResponder: Bool { true }
  override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

  // When sizingOptions = .intrinsicContentSize and SwiftUI content changes,
  // Auto Layout resizes this view to the new intrinsicContentSize and calls
  // setFrameSize. We intercept here to drive the window resize.
  override func setFrameSize(_ newSize: NSSize) {
    super.setFrameSize(newSize)
    guard newSize.height > 0 else { return }
    DispatchQueue.main.async { [weak self] in
      self?.onHeightChange?(newSize.height)
    }
  }
}

// MARK: - SwiftUI Wrapper

struct PopupWindowContentView: View {
  @Bindable var appState: AppState
  @Bindable var viewModel: PopupViewModel
  let closeAction: () -> Void

  var body: some View {
    PopupView(
      appState: appState,
      viewModel: viewModel,
      closeAction: closeAction
    )
  }
}
