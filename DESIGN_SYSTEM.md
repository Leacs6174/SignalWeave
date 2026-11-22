# DataMerger UI Design Rules

This project uses PySide6 6.12 Qt Widgets, Qt Fusion, QSS, and custom
`QPainter` charts. The rules below are mandatory for UI changes.

## Single Theme Entry Point

- Application startup must call `theme.apply_theme(app, APP_STYLE)`.
- Global semantic colors, the light `QPalette`, application font, common
  controls, menus, dialogs, and tooltips belong in `theme.py`.
- Screen-specific structure and QSS belong in `ui_main.py`.
- New feature code must not call `setStyle`, `setPalette`, or `setStyleSheet`
  on `QApplication`.

## Text And Surface Pairs

- Never set a menu, dialog, tooltip, list, or popup background without also
  setting its foreground color.
- Prefer semantic tokens from `theme.COLORS` over new literal colors.
- Body, heading, disabled, and muted text must remain distinguishable on their
  intended surface.
- Critical foreground/background pairs must meet WCAG AA contrast of at least
  4.5:1. `tests/test_theme.py` enforces the application palette pairs.
- Disabled, hover, selected, pressed, and focus states must all define visible
  text and background behavior.

## Native Qt Controls

- Use the Fusion style so Windows dark mode cannot leak inconsistent native
  colors into the light application theme.
- Every `QTabBar` must disable its native base line with
  `setDrawBase(False)`. `theme.enforce_design_invariants()` applies this to all
  tab bars when the main window is created.
- Do not rely on `documentMode` alone to remove the native tab baseline.
- Do not combine a fully transparent child surface with dropdown popups unless
  the popup receives its own explicit palette and QSS colors.
- Avoid fully transparent top-level windows unless a DWM backdrop is
  intentionally implemented and tested.

## Layout And Typography

- Use Microsoft YaHei UI when available, otherwise Segoe UI.
- Menu rows stay compact: approximately 22 px high, with a menu total height
  below 150 px for the current five actions.
- Standard corner radii: 7 px for controls, 10 px for charts, 14 px for cards.
- Borders are 1 px and low contrast except for drag-active or error states.
- Text is left aligned; numeric table content is right aligned.

## Charts

- Scatter charts use channel colors from `theme.CHANNEL_COLORS`.
- Samples in the same channel use the same color family with different shades.
- Different channels use different base colors.
- Preview data must come from exported values, not interpolated source points.
- CD defaults to `CD` and `G`; electrochemical data defaults to all discovered
  channels.
- Every interactive chart must provide a visible reset action. Drag-to-zoom
  must preserve the original data ranges so reset is lossless.

## Optional Frosted Appearance

Real backdrop blur must use Windows 11 DWM system backdrop APIs. QSS alone may
use translucent surfaces, gradients, borders, and shadows but cannot blur the
desktop behind a window.

When adding DWM material:

- provide a solid-color fallback;
- test with Windows transparency effects disabled;
- keep large scrolling content on an opaque or mostly opaque surface;
- never blur every small card independently;
- verify normal, disabled, focus, and high-contrast states.

## Required Checks

Before shipping a UI change:

1. Run `python -m unittest discover -s tests -p "test_*.py" -v`.
2. Open every popup and verify text is visible.
3. Check tab bars for a native baseline or black edge.
4. Capture the visible main window and inspect charts at high DPI.
5. Launch the packaged EXE with CD and electrochemical fixtures.
6. Terminate all test processes.
