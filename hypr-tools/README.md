# nandoroid/hypr-tools — Noctalia plugin

Port of NAnDoroid **Overview + Hyprland settings + Keybinds** to a Noctalia v5
plugin (one plugin, 3 entries), per `todo/port-to-noctalia-plugin.md`.

## Layout

```text
nandoroid-hypr/
  plugin.toml          # id nandoroid/hypr-tools, plugin_api 26
  service.luau         # [[service]] hypr-sync: hyprctl + keybinds poll → noctalia.state
[-][removed] overview.luau        # [[panel]] overview: workspace grid + search + move
  hypr_tools.luau      # [[panel]] hypr-tools: Visual/Layout/Input/Animations/Autostart/Keybinds
  scripts/             # bundled Python helpers (argv form, plugin_api 24)
    hyprconfigurator.py
    hypr_keybinds.py
    autostart.py
  translations/en.json, id.json
```

## Source mapping

| NAnDoroid | This plugin | Available |
|---|---|---|
| `panels/Overview/Overview.qml` grid, fuzzy (`fuzzyMatch/fuzzyScore`), keyboard nav, `movetoworkspacesilent` | `overview.luau`: Luau fuzzy port, `capture_keys` arrows/Return/Tab, `ui.dragSource/ui.dropZone` + select-then-tap move fallback | REMOVED |
| `OverviewPopup.qml` Overlay/Exclusive, tap-outside | Host-owned: floating panel + outside-click dismiss + `keyboard_focus="exclusive"` | REMOVED |
| `services/HyprlandData.qml` hyprctl poll | `service.luau` sequential `hyprctl -j` chain → `state.set` |
| `addon/Hyprland/HyprlandSettings.qml` + HyprLayout/Input/Visual/Autostart/Animations | `hypr_tools.luau` tabs; live `hyprctl keyword` + `hyprconfigurator.py --file <override> --set` / `--anim-preset` |
| `addon/services/HyprlandConfig.qml` set/setMany/reset | `hyprSet()` in `hypr_tools.luau` (BOOL_KEYS mapping lives in the Python script) |
| `addon/keybindSetting` + `KeybindsService.qml` via `hypr_keybinds.py show/set/remove/reset` | `hypr_tools.luau` Keybinds tab + `service.luau` `show` poll; parser stays Python |
| `Config.options.overview` / `Config.options.hyprland` | Re-declared as `[[setting]]`/`[[panel.setting]]` (`getConfig`); `config.json` not reused |
| Per-cell wallpaper `addon/overview/overviewWall.qml` | `noctalia.wallpaperPath(connector)` image when `show_wallpaper` (plugin_api 25) |
| Live thumbnails (`ToplevelManager`) | **Spike**: `grim` snapshot → `pluginDataDir/overview-snapshot.png` → `ui.image` when `show_thumbnails`; otherwise window-chip list mode |

## Install / dev

```bash
# dev source override (Noctalia reads path sources with .luau hot-reload)
# point your plugin source at this dir, then:
[ REMOVED ] noctalia msg panel-toggle nandoroid/hypr-tools:overview
noctalia msg panel-toggle nandoroid/hypr-tools:hypr-tools
```

Requires `hyprctl` + `python3` on PATH (declared in `dependencies`).
Override dir defaults to `~/.config/hypr/nandoroid/` (`shellConfig.lua`,
`animations.lua`); animation presets additionally need
`require("hyprland/nandoroid/animations")` in `hyprland.lua` (same as NAnDoroid).

## Verify

1. Enable via path source; toggle both panels.
2. Workspace switch / focus / close / move (`hyprctl getoption` round-trip on a Visual slider).
3. Keybind add → shows in list → remove/reset.
4. Cold start without `hyprctl`/`python3`: panels show error state, no crash.
5. Thumbnail spike: enable `show_thumbnails` with `grim` installed, hit Refresh, measure `runAsync` latency; keep list mode if too slow.
