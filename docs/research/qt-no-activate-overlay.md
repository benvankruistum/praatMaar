# Qt / PySide6: non-activating, always-on-top pill and overlay

Research for praatMaar’s status **pill** and **Meeting Buddy overlay** on
PySide6 (Qt 6): window flags/attributes that avoid stealing focus/activation,
always-on-top behaviour, and gaps vs the current Tk / Win / Mac indicator seams.

Primary sources only (Qt / Qt for Python docs, Qt source and release notes,
Microsoft Win32, Apple AppKit, FreeDesktop EWMH / Wayland).

**Ticket:** `.scratch/pyside6-migration/issues/02-qt-no-activate-research.md`  
**Date:** 2026-07-24  
**Related:** [ADR-0002](../adr/0002-macos-native-overlay-indicator.md),
[toolkit-pyside6.md](../design/toolkit-pyside6.md)

## Verdict (gist)

Use one **shared Qt flag/attribute set** for pill and overlay on all three OS’en:
`Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus`,
plus `WA_ShowWithoutActivating`, and on macOS also `WA_MacAlwaysShowToolWindow`.
On **Windows**, Qt already maps `WindowDoesNotAcceptFocus` to `WS_EX_NOACTIVATE`
(parity with today’s ctypes shim — no Win32 seam required for the common case).
On **macOS**, Qt maps `Tool` → `NSPanel` and refuses key-window via
`WindowDoesNotAcceptFocus`, but **does not** set AppKit’s
`NSWindowStyleMaskNonactivatingPanel`; keep a **thin Cocoa seam** as fallback if
runtime still activates the app (ADR-0002 behaviour). On **Linux**, X11 can
approximate via ICCCM input hints + `_NET_WM_STATE_ABOVE` (WM-dependent);
**Wayland/XDG Shell does not give clients absolute positioning or a first-class
no-activate overlay API** — treat overlay placement/stacking as best-effort unless
a compositor-specific shell (e.g. layer-shell) is added later.

---

## 1. Official Qt / PySide6 knobs

PySide6 exposes the same enums as Qt Core ([PySide6 `Qt`](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html),
[Qt 6 `Qt` namespace](https://doc.qt.io/qt-6/qt.html)).

| Knobs | Official meaning | Citation |
| --- | --- | --- |
| `Qt.WindowDoesNotAcceptFocus` | “Informs the window system that this window should not receive the input focus.” On Windows, also prevents a taskbar entry. | [Qt WindowType](https://doc.qt.io/qt-6/qt.html#WindowType-enum), [PySide6](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html) |
| `Qt.WA_ShowWithoutActivating` | “Show the widget without making it active.” | [Qt WidgetAttribute](https://doc.qt.io/qt-6/qt.html#WidgetAttribute-enum) |
| `Qt.WindowStaysOnTopHint` | “Informs the window system that the window should stay on top of all other windows.” On some X11 WMs also needs `X11BypassWindowManagerHint`. | Same WindowType docs |
| `Qt.Tool` | Tool window; with a parent kept above it; without parent consider `WindowStaysOnTopHint`. **On macOS, tool windows correspond to `NSPanel`.** Default: hide when app inactive — override with `WA_MacAlwaysShowToolWindow`. | Same |
| `Qt.WA_MacAlwaysShowToolWindow` | On macOS, show the tool window even when the application is not active. | WidgetAttribute docs |
| `Qt.WA_X11DoNotAcceptFocus` | “Asks the window manager to not give focus to this top level window.” **No effect on non-X11.** | WidgetAttribute docs |
| `Qt.FramelessWindowHint` | Borderless window. | WindowType docs |
| `Qt.WindowTransparentForInput` | Output-only; input passes through. | WindowType docs — **not** suitable if pill/overlay must receive clicks (cancel, expand). |
| `Qt.WA_TranslucentBackground` | Alpha / translucent regions; on Windows also needs `FramelessWindowHint`; set early, avoid toggling after show. | WidgetAttribute docs |
| `Qt.WA_AlwaysStackOnTop` | Only for `QOpenGLWidget` / `QQuickWidget` stacking inside a window — **not** a desktop always-on-top hint. | WidgetAttribute docs |

`QWindow::requestActivate()` **refuses** activation when `WindowDoesNotAcceptFocus`
is set (warns and returns) — [qtbase `qwindow.cpp`](https://github.com/qt/qtbase/blob/dev/src/gui/kernel/qwindow.cpp).

Design constraint already locked: pill and Meeting Buddy overlay must not steal
focus from the active type field ([toolkit-pyside6.md](../design/toolkit-pyside6.md)).

---

## 2. Windows — Qt maps to the same Win32 styles we already use

### 2.1 Platform APIs (Microsoft)

| API | Meaning | Citation |
| --- | --- | --- |
| `WS_EX_NOACTIVATE` | Top-level window does **not** become foreground when clicked; not activated via programmatic/a11y navigation by default; **does not appear on the taskbar by default**. | [Extended Window Styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles) |
| `WS_EX_TOOLWINDOW` | Floating toolbar style; no taskbar / Alt+Tab entry. | Same |
| `WS_EX_TOPMOST` | Stay above non-topmost windows when deactivated. | Same |
| `SW_SHOWNOACTIVATE` | Show without activating. | [ShowWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindow) |

Current praatMaar Windows indicator uses `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` and
`SW_SHOWNOACTIVATE` / `SWP_NOACTIVATE` (`indicator/_win.py`).

### 2.2 What Qt’s Windows QPA does

From [qtbase `qwindowswindow.cpp` (dev)](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/windows/qwindowswindow.cpp):

- `Qt::WindowDoesNotAcceptFocus` → `exStyle |= WS_EX_NOACTIVATE`.
- `Qt::Tool` → `WS_EX_TOOLWINDOW`.
- `Qt::WindowStaysOnTopHint` (or `ToolTip`) → `SetWindowPos(..., HWND_TOPMOST, ...)` with `SWP_NOACTIVATE`.
- Show path: `Tool`, `ToolTip`, `Popup`, `WindowDoesNotAcceptFocus`, or the
  `_q_showWithoutActivating` property (backed by `WA_ShowWithoutActivating`) →
  `SW_SHOWNOACTIVATE`.

From [qtbase `qwindowscontext.cpp`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/windows/qwindowscontext.cpp):
mouse/pointer activate messages return `MA_NOACTIVATE` when
`WindowDoesNotAcceptFocus` is set.

Qt **6.9.2** release notes document that Windows now uses `WS_EX_NOACTIVATE` for
this flag and that such windows no longer get a taskbar entry
([release-note](https://code.qt.io/cgit/qt/qtreleasenotes.git/plain/qt/6.9.2/release-note.md)).
Known caveat: [QTBUG-131714](https://bugreports.qt.io/browse/QTBUG-131714) —
finishing a system move could still activate despite the flag (tracked in the
same 6.9.2 notes).

**Implication:** the shared Qt flag set gives Windows parity with the existing
shim for the normal show/click path. No separate Win32 ctypes seam is required
unless a future edge case (drag-to-move activation, foreign HWND embedding)
survives Qt’s handling on the pinned Qt version.

---

## 3. macOS — NSPanel via `Tool`, but not full ADR-0002 `nonactivatingPanel`

### 3.1 Platform APIs (Apple)

| API | Meaning | Citation |
| --- | --- | --- |
| `NSWindow.StyleMask.nonactivatingPanel` | Panel (or `NSPanel` subclass) that **does not activate the owning app**. | [Apple: `nonactivatingPanel`](https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/nonactivatingpanel?language=objc) |
| Historical `NSNonactivatingPanelMask` | Panel can receive keyboard input **without activating** the owning application; valid only for `NSPanel` (not plain `NSWindow`). | Apple NSPanel class reference (legacy PDF / AppKit) |

ADR-0002 chose a native `NSPanel` + `nonactivatingPanel` because focus theft
breaks Cmd+V paste into the target field.

### 3.2 What Qt’s Cocoa QPA does

From [qtbase `qcocoawindow.mm` (dev)](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/cocoa/qcocoawindow.mm)
and [qnswindow.mm](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/cocoa/qnswindow.mm):

| Behaviour | Qt mechanism |
| --- | --- |
| Use `NSPanel` | `Qt::Tool` (and other popup/dialog panel cases) → `QNSPanel` |
| Utility chrome | `type == Qt::Tool` → `NSWindowStyleMaskUtilityWindow` |
| Stay above normal windows | `WindowStaysOnTopHint` → window level `NSModalPanelWindowLevel` (above `NSFloatingWindowLevel` used for plain Tool) |
| Refuse key window / first responder | `WindowDoesNotAcceptFocus` (or `WindowTransparentForInput`) → `shouldRefuseKeyWindowAndFirstResponder()` → `canBecomeKeyWindow` returns `NO` |
| Show without activating | `_q_showWithoutActivating` / `WA_ShowWithoutActivating` also refuses key during `setVisible` |
| Keep visible when app inactive | `WA_MacAlwaysShowToolWindow`; otherwise Tool panels set `hidesOnDeactivate = YES` |

Important gap vs ADR-0002: `windowStyleMask()` **preserves** an existing
`NSWindowStyleMaskNonactivatingPanel` bit if already set on the native window,
but Qt’s flag→mask path **does not set** that bit from
`WindowDoesNotAcceptFocus` or any other public Qt flag. Refusal of key-window is
implemented in Qt’s `canBecomeKeyWindow` override, not via AppKit’s
nonactivating style mask.

**Implication:**

1. First implementation path: shared Qt flags + `WA_ShowWithoutActivating` +
   `WA_MacAlwaysShowToolWindow` — enough for a clickable status pill that must
   never become key.
2. Acceptance test (same as ADR-0002): while recording/transcribing, Notes /
   TextEdit stays key; Cmd+V pastes there.
3. If showing or clicking the Qt panel still activates the praatMaar app or
   steals key from other apps, add a **thin macOS seam**: after create, OR
   `NSWindowStyleMaskNonactivatingPanel` onto the `NSPanel` (via PyObjC /
   `winId()`), matching ADR-0002 — without replacing the whole Qt widget tree.

Do **not** use `WindowTransparentForInput` if the pill needs click targets.

---

## 4. Linux — X11 hints vs Wayland compositor policy

### 4.1 X11 / EWMH

Qt docs: `WA_X11DoNotAcceptFocus` asks the WM not to give focus; X11-only
([WidgetAttribute](https://doc.qt.io/qt-6/qt.html#WidgetAttribute-enum)).
`WindowStaysOnTopHint` may need `X11BypassWindowManagerHint` on some WMs
([WindowType](https://doc.qt.io/qt-6/qt.html#WindowType-enum)).

From [qtbase `qxcbwindow.cpp`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/xcb/qxcbwindow.cpp):

- `WindowDoesNotAcceptFocus` → `updateDoesNotAcceptFocus` → ICCCM
  `WM_HINTS` input flag set false (`xcb_icccm_wm_hints_set_input(..., false)`).
- `WindowStaysOnTopHint` → `_NET_WM_STATE_ABOVE` / `_NET_WM_STATE_STAYS_ON_TOP`.
- `Qt::Tool` automatically gets `_NET_WM_WINDOW_TYPE_UTILITY` (Qt attribute docs).

EWMH ([Application Window Properties](https://specifications.freedesktop.org/wm/1.5/ar01s05.html)):
`_NET_WM_STATE_ABOVE` means the window should be on top of most windows; the
spec notes ABOVE/BELOW are **mainly for user preferences** and WMs may interpret
them differently. Qt’s own window docs stress that on X11 the toolkit only
sends **hints** ([application-windows.html](https://doc.qt.io/qt-6/application-windows.html)).

**Implication:** shared Qt flags are the right X11 starting point; verify on
target WMs (Mutter, KWin, etc.). Expect imperfect always-on-top / focus
behaviour under some managers.

### 4.2 Wayland

Qt documents that under typical desktop **XDG Shell**, clients **cannot**
programmatically set/get top-level window position; Qt ignores position and
reports `(0,0)` ([Wayland peculiarities](https://doc.qt.io/qt-6/application-windows.html)).

Activation/focus is compositor-driven. Qt Wayland Client’s built-in protocol
list centres on **xdg-shell**, **xdg-activation**, decorations, etc. — not
`zwlr_layer_shell_v1` ([Qt Wayland Client](https://doc.qt.io/qt-6/qtwaylandclient-index.html)).
Custom shells require a custom shell integration / protocol codegen path
([Custom Shell example](https://doc.qt.io/qt-6/qtwaylandcompositor-custom-shell-example.html)).

**Implication for praatMaar:** on Wayland, a frameless always-on-top, precisely
placed HUD is **not** a portable Qt Widgets feature. Options:

1. Ship shared Qt flags and accept compositor-dependent stacking/placement
   (may be enough for “status visible when focused app is normal”).
2. Later: compositor-specific layer-shell (or similar) seam — out of scope for
   a single shared code path today.
3. Prefer X11 session for Linux CI/acceptance of overlay geometry if Wayland
   fails the placement contract.

---

## 5. Gaps vs current Tk / Win / Mac indicator seams

| Concern | Today | Qt 6 / PySide6 |
| --- | --- | --- |
| Windows no-activate | `WS_EX_NOACTIVATE` + `SW_SHOWNOACTIVATE` (`indicator/_win`) | Same styles via `WindowDoesNotAcceptFocus` + show path — **seam can retire** for normal cases |
| macOS no-activate | Native `NSPanel` + `nonactivatingPanel` (ADR-0002 / `indicator/_mac`) | `Tool` → `NSPanel` + refuse key via `WindowDoesNotAcceptFocus`; **nonactivatingPanel not set by Qt** — keep optional Cocoa OR-in |
| Shared contract | `indicator._contract` + per-OS window modules | Keep contract; window host becomes Qt widgets with optional thin OS shims |
| Linux | No production native pill seam today | New surface: X11 OK-ish; Wayland weak for position/stacking |
| Clickable vs click-through | Pill must receive clicks without activating | Use `WindowDoesNotAcceptFocus`, **not** `WindowTransparentForInput` |
| Always on top | Win topmost / Mac panel level | `WindowStaysOnTopHint` (+ Mac Tool level / `WA_MacAlwaysShowToolWindow`) |

---

## 6. Practical recommendation

### 6.1 Single code path (try first)

For both pill and Meeting Buddy overlay (frameless HUD):

```text
flags:
  Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
attributes:
  WA_ShowWithoutActivating
  WA_MacAlwaysShowToolWindow   # macOS only; harmless no-op elsewhere if gated
  WA_TranslucentBackground     # if alpha HUD; set before first show
focusPolicy:
  Qt.NoFocus
```

Show with `show()` only — avoid `activateWindow()` / `requestActivate()` /
unnecessary `raise_()` that reintroduce activation (platform-sensitive).

### 6.2 Thin per-OS seams (only if tests fail)

| OS | Seam |
| --- | --- |
| Windows | None expected; re-check QTBUG-131714-class activation after drag if using system move |
| macOS | After native window exists: set `NSWindowStyleMaskNonactivatingPanel` on the `NSPanel` (ADR-0002 parity) |
| Linux X11 | Optional: also set `WA_X11DoNotAcceptFocus`; only add `X11BypassWindowManagerHint` if a specific WM ignores `_NET_WM_STATE_ABOVE` (last resort — breaks WM integration) |
| Linux Wayland | No portable seam in stock Qt; document degraded overlay or defer layer-shell |

### 6.3 One stack vs two windows

Flags above apply equally to pill and overlay as separate top-levels. Whether
they share one Qt window stack is a product/layout decision (still open on the
wayfinder map); it does **not** change the no-activate / always-on-top recipe.

### 6.4 Acceptance checks (cross-platform)

1. While pill/overlay visible, focus stays in an external text field; paste
   shortcut inserts there (Win: Ctrl+V, Mac: Cmd+V).
2. Clicking pill controls does not foreground-steal the target app’s field.
3. Pill remains visible when praatMaar is not the active app (esp. macOS Tool +
   `WA_MacAlwaysShowToolWindow`).
4. Overlay remains above ordinary app windows under the primary DE under test
   (document Wayland exceptions).

---

## Sources (index)

- [Qt 6 `Qt` namespace — WindowType / WidgetAttribute](https://doc.qt.io/qt-6/qt.html)
- [PySide6 `Qt`](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html)
- [Qt Window and Dialog Widgets (X11 / Wayland peculiarities)](https://doc.qt.io/qt-6/application-windows.html)
- [Qt Wayland Client](https://doc.qt.io/qt-6/qtwaylandclient-index.html)
- [qtbase Windows QPA `qwindowswindow.cpp`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/windows/qwindowswindow.cpp)
- [qtbase Windows QPA `qwindowscontext.cpp`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/windows/qwindowscontext.cpp)
- [qtbase Cocoa QPA `qcocoawindow.mm`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/cocoa/qcocoawindow.mm)
- [qtbase Cocoa QPA `qnswindow.mm`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/cocoa/qnswindow.mm)
- [qtbase XCB QPA `qxcbwindow.cpp`](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/xcb/qxcbwindow.cpp)
- [qtbase `QWindow::requestActivate`](https://github.com/qt/qtbase/blob/dev/src/gui/kernel/qwindow.cpp)
- [Qt 6.9.2 release notes (WS_EX_NOACTIVATE)](https://code.qt.io/cgit/qt/qtreleasenotes.git/plain/qt/6.9.2/release-note.md)
- [QTBUG-131714](https://bugreports.qt.io/browse/QTBUG-131714)
- [Microsoft extended window styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles)
- [Microsoft ShowWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindow)
- [Apple `nonactivatingPanel`](https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/nonactivatingpanel?language=objc)
- [FreeDesktop EWMH — `_NET_WM_STATE_ABOVE`](https://specifications.freedesktop.org/wm/1.5/ar01s05.html)
