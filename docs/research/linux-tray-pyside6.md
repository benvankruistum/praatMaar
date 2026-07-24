# Linux system tray with PySide6 / Qt 6

Research for praatMaarΓÇÖs Linux tray entrypoint when the UI is PySide6.
Primary sources only (Qt / PySide docs, FreeDesktop StatusNotifierItem, GNOME / Ubuntu packaging, Qt source).

**Ticket:** `.scratch/pyside6-migration/issues/03-linux-tray-research.md`  
**Date:** 2026-07-24

## Verdict (gist)

On Linux, PySide6ΓÇÖs supported tray API is `QSystemTrayIcon`, which speaks **D-Bus StatusNotifierItem** (and falls back to **XEmbed** on X11). That works out of the box on desktops that run a **StatusNotifierHost** (notably KDE Plasma; Ubuntu GNOME via a shipped shell extension). **Stock GNOME Shell since 3.26 does not show status icons by default**, so a tray-only entrypoint is not realistic for ΓÇ£Linux shipsΓÇ¥ on vanilla GNOME ΓÇö the app must remain usable without a tray (window / menu / notifications) and should treat tray as best-effort when `isSystemTrayAvailable()` is true.

---

## 1. Supported API: `QSystemTrayIcon` (PySide6 = Qt Widgets)

PySide6 exposes the same class and platform list as Qt Widgets.

Claims from [Qt 6 `QSystemTrayIcon`](https://doc.qt.io/qt-6/qsystemtrayicon.html) and [PySide6 `QSystemTrayIcon`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html):

| Claim | Source |
| --- | --- |
| Tray icons are supported on Linux DEs that implement D-Bus **StatusNotifierItem**, including KDE, Gnome, Xfce, LXQt, and DDE | Qt / PySide docs (platform list) |
| Also supported: X11 trays implementing the freedesktop.org **XEmbed** system tray spec | Same |
| Call `QSystemTrayIcon.isSystemTrayAvailable()` to detect a tray | Same |
| Create icon ΓåÆ `setContextMenu()` ΓåÆ `show()`; optional `showMessage()` | Same |
| If the tray appears later while the icon is visible, Qt adds the entry automatically | Same |
| Since **GNOME Shell 3.26**, not all `ActivationReason` values are supported without shell extensions | Same (explicit note) |

Implication for praatMaar: use `QSystemTrayIcon` only; do not invent a separate AppIndicator binding for the Qt UI path.

---

## 2. Protocol: FreeDesktop StatusNotifierItem

The modern Linux tray model is D-Bus StatusNotifierItem, intended as a replacement for the older XEmbed system tray.

From the [Status Notifier Item Specification](https://specifications.freedesktop.org/status-notifier-item/latest/) ([basic design](https://specifications.freedesktop.org/status-notifier-item/latest/basic-design.html)):

| Role | Responsibility |
| --- | --- |
| **StatusNotifierItem** | Application registers an item on the session bus (service name pattern `org.freedesktop.StatusNotifierItem-PID-ID` in the spec; Qt uses the KDE-compatible `org.kde.StatusNotifierItem-ΓÇª` form ΓÇö see ┬º3) |
| **StatusNotifierWatcher** | Tracks registered items; notifies hosts of add/remove |
| **StatusNotifierHost** | Visual container that displays items |

Without a registered **host** (and typically a **watcher**), items have nowhere to appear. The spec does **not** mandate that every desktop ships a host; presentation is ΓÇ£strictly implementation specific.ΓÇ¥

---

## 3. What Qt actually does on Linux

QtΓÇÖs Linux tray path is implemented in platform code, not in the public Widgets docs alone.

### 3.1 D-Bus StatusNotifier path (`QDBusTrayIcon`)

From Qt base source [`qdbustrayicon.cpp`](https://github.com/qt/qtbase/blob/dev/src/gui/platform/unix/dbustray/qdbustrayicon.cpp):

- Registers an item as `org.kde.StatusNotifierItem-<pid>-<n>`.
- Talks to watcher service `org.kde.StatusNotifierWatcher`.
- `QDBusTrayIcon::isSystemTrayAvailable()` returns whether that watcher is registered on the session bus (`isWatcherRegistered()`).
- Balloon-style `showMessage()` is forwarded via `org.freedesktop.Notifications` when StatusNotifier is active (historical commit [cec1038](https://github.com/qt/qtbase/commit/cec103897f5109c70f2fd69460d10d21fa4feded); still reflected in the same source fileΓÇÖs notification path).
- Flatpak: icon temp paths account for `FLATPAK_ID` / `/.flatpak-info` when writing pixmap fallbacks for hosts that need files on disk.

### 3.2 X11 XEmbed fallback

From [`qsystemtrayicon_x11.cpp`](https://github.com/qt/qtbase/blob/dev/src/widgets/util/qsystemtrayicon_x11.cpp):

- Prefers a `QPlatformSystemTrayIcon` from the platform theme (D-Bus path above) when present.
- Otherwise, on the `xcb` platform, looks up the XEmbed tray window (`traywindow` native resource) and embeds a small frameless widget.
- `isSystemTrayAvailable_sys()`: true if platform tray reports available, else true on xcb only if an XEmbed tray window exists.

**Wayland:** there is no XEmbed tray; availability hinges on StatusNotifierWatcher/Host in the session.

---

## 4. Desktop reality (especially GNOME)

### 4.1 Stock GNOME Shell (3.26+)

Primary GNOME sources:

- [GNOME 3.26 release notes](https://release.gnome.org/3-26/): ΓÇ£GNOME 3.26 no longer shows status icons in the bottom-left of the screenΓÇª they can be restored using the TopIcons extension.ΓÇ¥
- [Allan Day / GNOME design blog](https://blogs.gnome.org/aday/2017/08/31/status-icons-and-gnome/): from 3.26, status icons are **not shown by default**; users who need them may use a Shell extension.
- [Status Icon Migration FAQ](https://wiki.gnome.org/Initiatives/StatusIconMigration/FAQ): same policy; apps should remain usable without a visible icon.
- [Status Icon Migration Guidelines](https://wiki.gnome.org/Initiatives/StatusIconMigration/Guidelines):
  - Status icons ΓÇ£shouldn't be necessary and should be avoided if possible.ΓÇ¥
  - Even if an app uses one, it **might not be visible**; ensure the app works **with or without** the icon.
  - All functionality must be reachable from application windows; do not put actions only in the tray menu.
  - Prefer notifications (and specialized APIs such as MPRIS) for background signalling.
  - Detection tip: check whether D-Bus name `org.kde.StatusNotifierWatcher` is owned (same signal Qt uses).

QtΓÇÖs own docs align: incomplete `ActivationReason` support on GNOME Shell ΓëÑ 3.26 without extensions ([QSystemTrayIcon](https://doc.qt.io/qt-6/qsystemtrayicon.html)).

**Conclusion for stock GNOME:** `QSystemTrayIcon` may construct and register, but **`isSystemTrayAvailable()` will be false** (or the icon will not appear) unless something in the session provides StatusNotifierWatcher/Host ΓÇö which stock Shell does not.

### 4.2 Restoring a host on GNOME: AppIndicator / SNI extension

CanonicalΓÇÖs [gnome-shell-extension-appindicator](https://github.com/ubuntu/gnome-shell-extension-appindicator) ΓÇ£Adds KStatusNotifierItem support to the ShellΓÇ¥ (also AppIndicator and legacy tray). Distributed via [extensions.gnome.org #615](https://extensions.gnome.org/extension/615/appindicator-support/) and distro packages such as UbuntuΓÇÖs [`gnome-shell-extension-appindicator`](https://packages.ubuntu.com/noble/gnome-shell-extension-appindicator).

This is a **session / DE dependency**, not something an application can reliably bundle inside its own process for all GNOME users.

### 4.3 Ubuntu GNOME

[`ubuntu-desktop` on Ubuntu 24.04 (noble)](https://packages.ubuntu.com/noble/ubuntu-desktop) **Depends** on `gnome-shell-extension-appindicator`. So a default Ubuntu Desktop install ships an SNI/AppIndicator host; Qt `QSystemTrayIcon` is realistic there.

Vanilla upstream GNOME sessions (Fedora Workstation ΓÇ£GNOMEΓÇ¥, custom installs without the extension) do **not** get that dependency for free.

### 4.4 KDE Plasma and other SNI desktops

KDEΓÇÖs [KStatusNotifierItem](https://api.kde.org/kstatusnotifieritem.html) documents the Status Notifier Item D-Bus protocol; Plasma provides a system-tray **host**. Qt lists KDE among StatusNotifierItem environments ([QSystemTrayIcon](https://doc.qt.io/qt-6/qsystemtrayicon.html)). Xfce / LXQt / DDE are likewise listed by Qt when they implement the protocol ΓÇö treat as ΓÇ£works when watcher/host present,ΓÇ¥ verified at runtime via `isSystemTrayAvailable()`.

---

## 5. Is a non-tray fallback required for destination ΓÇ£Linux shipsΓÇ¥?

**Yes**, if Linux destination includes stock GNOME (or any DE without a StatusNotifierHost).

Required product behaviour (from GNOME guidelines + Qt availability API):

1. Gate tray UI on `QSystemTrayIcon.isSystemTrayAvailable()` (and optionally re-check when the watcher appears ΓÇö Qt auto-shows if already `visible`).
2. Keep a primary window / settings / quit path that does **not** depend on the tray menu.
3. Use desktop notifications (`showMessage` / FreeDesktop Notifications) for events; do not rely on tray balloons alone ([Qt docs](https://doc.qt.io/qt-6/qsystemtrayicon.html): messages may not appear).
4. Document for GNOME users that an AppIndicator/SNI shell extension restores the icon when their distro does not ship one.

A separate ΓÇ£panel appletΓÇ¥ packaged with praatMaar is **not** required by the specs; the realistic fallbacks are **in-app UI** and **optional DE extension**, not a custom panel binary.

---

## 6. Packaging implications

| Topic | Finding | Source |
| --- | --- | --- |
| App package should **not** try to ship the tray **host** | Host is a desktop component (Plasma applet, GNOME Shell extension, etc.) | SNI spec roles; Ubuntu ships host via `gnome-shell-extension-appindicator` |
| Runtime soft dependency | Session D-Bus + `org.kde.StatusNotifierWatcher` (and a host) | Qt `QDBusTrayIcon`; GNOME guidelines detection step |
| Hard Depends on the GNOME extension? | **No** for a portable Linux build ΓÇö Ubuntu already Depends via `ubuntu-desktop`; other GNOME spins may not | Ubuntu package metadata |
| Flatpak / sandbox | Tray needs session D-Bus access to watcher/item interfaces; Qt already special-cases Flatpak icon temp dirs | `qdbustrayicon.cpp` Flatpak path handling |
| Deb / AppImage / generic tarball | Document ΓÇ£tray requires DE StatusNotifier hostΓÇ¥; recommend `gnome-shell-extension-appindicator` (or distro equivalent) on GNOME | Derived from above primaries |

No need to add `libappindicator` as a PySide6 dependency: Qt implements SNI itself over D-Bus. Distro AppIndicator packages matter for *other* toolkits, not for QtΓÇÖs `QDBusTrayIcon` path.

---

## 7. Practical matrix for praatMaar

| Environment | Tray via `QSystemTrayIcon` | Notes |
| --- | --- | --- |
| KDE Plasma | Expected yes | Native SNI host |
| Ubuntu Desktop GNOME | Expected yes | Extension packaged as `ubuntu-desktop` dependency |
| Stock GNOME Shell (no extension) | No / incomplete | Policy since 3.26; fallback UI required |
| GNOME + AppIndicator/SNI extension | Yes | User or distro installs host |
| X11 WM with XEmbed tray only | Possible | Qt XEmbed fallback; not Wayland |
| Wayland without SNI host | No | No XEmbed fallback |

---

## Sources (primary)

1. [Qt 6 ΓÇö QSystemTrayIcon](https://doc.qt.io/qt-6/qsystemtrayicon.html)
2. [PySide6 ΓÇö QSystemTrayIcon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)
3. [FreeDesktop StatusNotifierItem specification](https://specifications.freedesktop.org/status-notifier-item/latest/)
4. Qt source ΓÇö [`qdbustrayicon.cpp`](https://github.com/qt/qtbase/blob/dev/src/gui/platform/unix/dbustray/qdbustrayicon.cpp), [`qsystemtrayicon_x11.cpp`](https://github.com/qt/qtbase/blob/dev/src/widgets/util/qsystemtrayicon_x11.cpp)
5. [GNOME 3.26 release notes](https://release.gnome.org/3-26/)
6. [Status Icons and GNOME (Allan Day)](https://blogs.gnome.org/aday/2017/08/31/status-icons-and-gnome/)
7. [GNOME Status Icon Migration FAQ](https://wiki.gnome.org/Initiatives/StatusIconMigration/FAQ) and [Guidelines](https://wiki.gnome.org/Initiatives/StatusIconMigration/Guidelines)
8. [ubuntu/gnome-shell-extension-appindicator](https://github.com/ubuntu/gnome-shell-extension-appindicator)
9. [Ubuntu noble ΓÇö ubuntu-desktop](https://packages.ubuntu.com/noble/ubuntu-desktop), [gnome-shell-extension-appindicator](https://packages.ubuntu.com/noble/gnome-shell-extension-appindicator)
10. [KDE KStatusNotifierItem](https://api.kde.org/kstatusnotifieritem.html)
