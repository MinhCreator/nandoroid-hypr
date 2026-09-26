import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── Constants ──

MOD_SEPARATORS = set(" +")

CATEGORY_RULES = {
    "Window": [
        "killactive", "forcekillactive", "closewindow", "killwindow",
        "togglefloating", "setfloating", "settiled", "pin",
        "fullscreen", "fullscreenstate", "fakefullscreen",
        "movewindow", "movewindowpixel", "resizewindow", "resizewindowpixel",
        "resizeactive", "moveactive", "swapwindow", "swapnext",
        "splitratio", "centerwindow", "cyclenext", "cycleprev", "focuswindow",
        "changegroupactive", "togglegroup", "movewindoworgroup",
        "bringactivetotop", "alterzorder", "focusurgentorlast",
        "focuscurrentorlast", "setprop",
    ],
    "Workspace": [
        "workspace", "renameworkspace", "movetoworkspace",
        "movetoworkspacesilent", "focusworkspaceoncurrentmonitor",
        "moveworkspacetomonitor", "movecurrentworkspacetomonitor",
        "togglespecialworkspace", "workspaceopt",
    ],
    "Execute": ["exec", "execr", "exec_raw", "spawn"],
    "System": ["exit", "dpms", "forceidle", "forcerendererreload"],
    "Focus": [
        "movefocus", "focusmonitor", "focuswindowbyclass",
    ],
    "Layout": [
        "layoutmsg", "layout", "pseudo",
    ],
    "Group": [
        "togglegroup", "changegroupactive", "movegroupwindow",
        "moveintogroup", "moveoutofgroup", "movewindoworgroup",
        "moveintoorcreategroup", "setignoregrouplock", "denywindowfromgroup",
        "lockgroups", "lockactivegroup",
    ],
    "Input": [
        "pass", "sendshortcut", "sendkeystate", "mouse",
        "movecursortocorner", "movecursor",
    ],
    "Cursor": ["movecursor", "movecursortocorner"],
    "Misc": ["signal", "signalwindow", "event", "global", "submap"],
}

DISPATCHER_TO_CATEGORY = {}
for _cat, _dispatchers in CATEGORY_RULES.items():
    for _d in _dispatchers:
        DISPATCHER_TO_CATEGORY[_d] = _cat

BIND_FLAGS_MAP = {
    "l": "locked",
    "e": "repeat",
    "r": "release",
    "n": "non-consuming",
    "m": "mouse",
    "t": "transparent",
    "i": "ignore-mods",
    "s": "separate",
    "d": "description",
    "o": "long-press",
}


# ── Config Detection ──

def get_hypr_config_dir() -> Path:
    """Return ~/.config/hypr/"""
    return Path.home() / ".config" / "hypr"


def get_override_path(is_lua: bool) -> Path:
    """Return the user override file path."""
    base = get_hypr_config_dir() / "nandoroid"
    ext = ".lua" if is_lua else ".conf"
    return base / f"binds-user{ext}"


def detect_lua_format(config_dir: Path) -> bool:
    """Detect if the main config is Lua format."""
    for name in ["hyprland.lua", "hypr.conf"]:
        p = config_dir / name
        if p.exists():
            return name.endswith(".lua")
    # Check for any .lua file
    for f in config_dir.glob("*.lua"):
        return True
    return False


def get_main_config_path(config_dir: Path, is_lua: bool) -> Path | None:
    """Find the main hyprland config file."""
    if is_lua:
        lua_path = config_dir / "hyprland.lua"
        if lua_path.exists():
            return lua_path
    else:
        conf_path = config_dir / "hyprland.conf"
        if conf_path.exists():
            return conf_path
    # Fallback: any .conf or .lua
    ext = "*.lua" if is_lua else "*.conf"
    for f in sorted(config_dir.glob(ext)):
        if f.name not in ("binds-user.lua", "binds-user.conf"):
            return f
    return None


# ── Key Parsing ──

def parse_mods_and_key(mods_str: str, key: str) -> str:
    """Combine mods + key into canonical form like 'Super+Shift+A'."""
    parts = []
    if mods_str.strip():
        for mod in re.split(r'[+\s]+', mods_str.strip()):
            mod = mod.strip()
            if mod:
                parts.append(canonicalize_key(mod))
    parts.append(canonicalize_key(key.strip()))
    return "+".join(parts)


def canonicalize_key(key: str) -> str:
    """Normalize a single key part."""
    k = key.strip()
    low = k.lower()
    mapping = {
        "super": "Super", "mod4": "Super", "mainmod": "Super",
        "ctrl": "Ctrl", "control": "Ctrl",
        "shift": "Shift",
        "alt": "Alt", "mod1": "Alt",
    }
    if low in mapping:
        return mapping[low]
    # Scroll wheel normalization
    scroll_map = {
        "mouse_down": "mouse_down",
        "mouse_up": "mouse_up",
        "mouse:272": "mouse_down",
        "mouse:273": "mouse_up",
    }
    if low in scroll_map:
        return scroll_map[low]
    if len(k) == 1:
        return k.upper()
    return k


def format_key_display(key: str) -> str:
    """Format key for display: 'Super+Shift+A' → 'Super + Shift + A'."""
    return key.replace("+", " + ")


# ── Config Parsing ──

def parse_conf_bind_line(line: str, source_file: str) -> dict | None:
    """Parse a Hyprland conf bind line: bind = MODS, KEY, dispatcher, params"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    # Match bind type (bind, binde, bindr, bindel, bindd, etc.)
    m = re.match(r'^(bind\w*)\s*=\s*(.*)', stripped)
    if not m:
        return None

    bind_type = m.group(1)
    rhs = m.group(2)

    # Extract flags from bind type (everything after "bind")
    flags = bind_type[4:] if len(bind_type) > 4 else ""

    # Check for comment-based description
    comment = ""
    if "#" in rhs:
        parts = rhs.split("#", 1)
        rhs = parts[0]
        comment = parts[1].strip()

    # Check for [hidden] — skip these
    if "[hidden]" in comment.lower():
        return None

    # Split by comma, but be careful with commas inside params
    # Format: MODS, KEY, dispatcher, params
    # For bindd: MODS, KEY, description, dispatcher, params
    has_desc = "d" in flags
    fields = [f.strip() for f in rhs.split(",")]
    if len(fields) < (4 if has_desc else 3):
        return None

    mods = fields[0]
    key = fields[1]

    if has_desc:
        if not comment:
            comment = fields[2]
        dispatcher = fields[3]
        params = ",".join(fields[4:]).strip() if len(fields) > 4 else ""
    else:
        dispatcher = fields[2]
        params = ",".join(fields[3:]).strip() if len(fields) > 3 else ""

    dispatcher = dispatcher.strip().lower()

    key_combo = parse_mods_and_key(mods, key)
    action = f"{dispatcher} {params}".strip() if params else dispatcher

    return {
        "key": key_combo,
        "action": action,
        "dispatcher": dispatcher,
        "params": params,
        "desc": comment or autogenerate_desc(dispatcher, params),
        "flags": flags,
        "source": source_file,
    }


def _parse_lua_dispatcher(expr: str) -> tuple[str, str, str]:
    """Parse a Lua dispatcher expression into (dispatcher, params, description).

    Handles:
      - hl.dsp.exec_cmd("cmd")           → ("exec", "cmd", "cmd")
      - hl.dsp.exec_raw("cmd")            → ("execr", "cmd", "cmd")
      - hl.dsp.focus({ workspace = "1" }) → ("workspace", "1", "Focus workspace 1")
      - hl.dsp.window.close()             → ("killactive", "", "Close window")
      - hl.dsp.window.move({...})         → (disambiguated based on body)
      - hl.dsp.workspace.toggle_special() → ("togglespecialworkspace", ...)
      - hl.dsp.group.toggle()             → ("togglegroup", ...)
      - hl.dsp.cursor.move({...})         → ("movecursor", ...)
      - hl.dsp.layout("togglesplit")      → ("layoutmsg", "togglesplit", ...)
      - hl.dsp.global("xxx")              → ("global", "xxx", "xxx")
      - hl.dsp.exit()                     → ("exit", "", ...)
      - hl.dsp.submap("name")             → ("submap", "name", ...)
      - function() ... end                → ("exec", "<callback>", "Run command")
    """
    expr = expr.strip()

    # ── function() ... end  (anonymous callback) ──
    if expr.startswith("function"):
        return ("exec", "<callback>", "Run command")

    # ── hl.dispatch(...)  (passthrough) ──
    m = re.match(r'hl\.dispatch\((.+)\)\s*$', expr)
    if m:
        inner = m.group(1).strip()
        return _parse_lua_dispatcher(inner)

    # ── hl.dsp.global("xxx") ──
    m = re.match(r'hl\.dsp\.global\(\s*"([^"]*)"\s*\)\s*$', expr)
    if m:
        val = m.group(1)
        return ("global", val, val)

    # ── hl.dsp.exec_cmd("cmd") or hl.dsp.exec_cmd(var .. "cmd") ──
    m = re.match(r'hl\.dsp\.exec_cmd\((.+)\)\s*$', expr)
    if m:
        raw = m.group(1).strip()
        parts = re.findall(r'"([^"]*)"', raw)
        if parts:
            cmd = ''.join(parts).strip()
            if '..' in raw:
                var_name = raw.split('..')[0].strip()
                return ("exec", cmd, f"{var_name} → {cmd}")
            return ("exec", cmd, cmd)
        return ("exec", raw, raw)

    # ── hl.dsp.exec_raw("cmd") ──
    m = re.match(r'hl\.dsp\.exec_raw\(\s*"([^"]*)"\s*\)\s*$', expr)
    if m:
        return ("execr", m.group(1), m.group(1))

    # ── hl.dsp.exit() ──
    if re.match(r'hl\.dsp\.exit\(\)\s*$', expr):
        return ("exit", "", "Exit Hyprland")

    # ── hl.dsp.submap("name") ──
    m = re.match(r'hl\.dsp\.submap\(\s*"([^"]*)"\s*\)\s*$', expr)
    if m:
        val = m.group(1)
        return ("submap", val, f"Submap: {val}" if val else "Submap")

    # ── hl.dsp.pass({...}) ──
    if re.match(r'hl\.dsp\.pass\(\s*\{?\s*\}?\s*\)\s*$', expr):
        return ("pass", "", "Pass shortcut")

    # ── hl.dsp.send_shortcut({...}) ──
    if re.match(r'hl\.dsp\.send_shortcut\(', expr):
        return ("sendshortcut", "", "Send shortcut")

    # ── hl.dsp.send_key_state({...}) ──
    if re.match(r'hl\.dsp\.send_key_state\(', expr):
        return ("sendkeystate", "", "Send key state")

    # ── hl.dsp.dpms({...}) ──
    if re.match(r'hl\.dsp\.dpms\(', expr):
        return ("dpms", "", "Toggle DPMS")

    # ── hl.dsp.event("name") ──
    m = re.match(r'hl\.dsp\.event\(\s*"([^"]*)"\s*\)\s*$', expr)
    if m:
        val = m.group(1)
        return ("event", val, f"Event: {val}" if val else "Event")

    # ── hl.dsp.focus({...}) ──
    m = re.match(r'hl\.dsp\.focus\(\s*\{([^}]*)\}\s*\)\s*$', expr)
    if m:
        body = m.group(1).strip()
        wm = re.search(r'workspace\s*=\s*"?([^",}]+)"?', body)
        if wm:
            val = wm.group(1).strip().strip('"')
            return ("workspace", val, f"Focus workspace {val}")
        mm = re.search(r'monitor\s*=\s*"?([^",}]+)"?', body)
        if mm:
            val = mm.group(1).strip().strip('"')
            return ("focusmonitor", val, f"Focus monitor {val}")
        dm = re.search(r'direction\s*=\s*"?([^",}]+)"?', body)
        if dm:
            val = dm.group(1).strip().strip('"')
            return ("movefocus", val, f"Move focus {val}")
        if "urgent_or_last" in body:
            return ("focusurgentorlast", "", "Focus urgent or last")
        if "last" in body:
            return ("focuscurrentorlast", "", "Focus current or last")
        if "window" in body:
            wm2 = re.search(r'window\s*=\s*"?([^",}]+)"?', body)
            val = wm2.group(1).strip().strip('"') if wm2 else ""
            return ("focuswindow", val, f"Focus window {val}")

    # ── hl.dsp.workspace.xxx(...) ──
    m = re.match(r'hl\.dsp\.workspace\.(\w+)\s*\((.+)\)\s*$', expr, re.DOTALL)
    if m:
        method = m.group(1).lower()
        args_str = m.group(2).strip()
        if method == "toggle_special":
            sm = re.search(r'"([^"]*)"', args_str)
            val = sm.group(1) if sm else ""
            val = val.replace("special:", "")
            return ("togglespecialworkspace", val,
                    f"Toggle special workspace {val}" if val else "Toggle special workspace")
        if method == "rename":
            wm = re.search(r'workspace\s*=\s*"?([^",}]+)"?', args_str)
            name_m = re.search(r'name\s*=\s*"([^"]*)"', args_str)
            ws = wm.group(1).strip().strip('"') if wm else ""
            name = name_m.group(1) if name_m else ""
            return ("renameworkspace", f"{ws} {name}".strip(),
                    f"Rename workspace {ws} to {name}" if name else f"Rename workspace {ws}")
        if method == "move":
            mon_m = re.search(r'monitor\s*=\s*"?([^",}]+)"?', args_str)
            mon = mon_m.group(1).strip().strip('"') if mon_m else ""
            return ("moveworkspacetomonitor", mon, f"Move workspace to monitor {mon}")
        if method == "swap_monitors":
            m1 = re.search(r'monitor1\s*=\s*"?([^",}]+)"?', args_str)
            m2 = re.search(r'monitor2\s*=\s*"?([^",}]+)"?', args_str)
            v1 = m1.group(1).strip().strip('"') if m1 else ""
            v2 = m2.group(1).strip().strip('"') if m2 else ""
            return ("swapactiveworkspaces", f"{v1} {v2}", f"Swap monitors {v1} and {v2}")
        if method == "change_id":
            id_m = re.search(r'id\s*=\s*"?([^",}]+)"?', args_str)
            val = id_m.group(1).strip().strip('"') if id_m else ""
            return ("workspace", val, f"Change workspace ID to {val}")
        return ("exec", expr, f"Workspace: {method}")

    # ── hl.dsp.group.xxx(...) ──
    m = re.match(r'hl\.dsp\.group\.(\w+)\s*\((.+)\)\s*$', expr, re.DOTALL)
    if m:
        method = m.group(1).lower()
        args_str = m.group(2).strip()
        if method == "toggle":
            return ("togglegroup", "", "Toggle group")
        if method == "next":
            return ("changegroupactive", "", "Next in group")
        if method == "prev":
            return ("changegroupactive", "", "Previous in group")
        if method == "active":
            idx_m = re.search(r'index\s*=\s*"?([^",}]+)"?', args_str)
            idx = idx_m.group(1).strip().strip('"') if idx_m else ""
            return ("changegroupactive", idx, f"Group window {idx}" if idx else "Group select")
        if method == "move_window":
            fwd = "forward" in args_str and "false" not in args_str
            return ("movegroupwindow", "fwd" if fwd else "bwd",
                    f"Move group window {'forward' if fwd else 'backward'}")
        return ("exec", expr, f"Group: {method}")

    # ── hl.dsp.cursor.xxx(...) ──
    m = re.match(r'hl\.dsp\.cursor\.(\w+)\s*\((.+)\)\s*$', expr, re.DOTALL)
    if m:
        method = m.group(1).lower()
        args_str = m.group(2).strip()
        if method == "move_to_corner":
            c_m = re.search(r'corner\s*=\s*"?([^",}]+)"?', args_str)
            corner = c_m.group(1).strip().strip('"') if c_m else ""
            return ("movecursortocorner", corner,
                    f"Cursor to corner {corner}" if corner else "Cursor to corner")
        if method == "move":
            x_m = re.search(r'x\s*=\s*"?([^",}]+)"?', args_str)
            y_m = re.search(r'y\s*=\s*"?([^",}]+)"?', args_str)
            x = x_m.group(1).strip().strip('"') if x_m else ""
            y = y_m.group(1).strip().strip('"') if y_m else ""
            return ("movecursor", f"{x},{y}", f"Cursor to ({x}, {y})" if x else "Move cursor")
        return ("exec", expr, f"Cursor: {method}")

    # ── hl.dsp.window.xxx({...})  /  hl.dsp.window.xxx() ──
    m = re.match(r'hl\.dsp\.window\.(\w+)\s*\((.+)\)\s*$', expr, re.DOTALL)
    if m:
        method = m.group(1).lower()
        args_str = m.group(2).strip()
        body_match = re.search(r'\{([^}]*)\}', args_str)
        body = body_match.group(1).strip() if body_match else ""

        window_map = {
            "close": ("killactive", "", "Close window"),
            "closewindow": ("killactive", "", "Close window"),
            "kill": ("killwindow", "", "Kill window"),
            "killwindow": ("killwindow", "", "Kill window"),
            "signal": ("signal", "", "Signal window"),
            "cycle_next": ("cyclenext", "", "Cycle window"),
            "cycleprevious": ("cycleprev", "", "Cycle prev window"),
            "cycle_prev": ("cycleprev", "", "Cycle prev window"),
            "swap_next": ("swapnext", "", "Swap next"),
            "drag": ("mouse", "drag", "Move window (mouse)"),
            "resize": ("mouse", "resize", "Resize window (mouse)"),
            "fullscreen": ("fullscreen", "", "Toggle fullscreen"),
            "fullscreen_state": ("fullscreenstate", "", "Fullscreen state"),
            "pin": ("pin", "", "Pin (all workspaces)"),
            "float": ("togglefloating", "", "Toggle floating"),
            "togglefloating": ("togglefloating", "", "Toggle floating"),
            "pseudo": ("pseudo", "", "Toggle pseudo"),
            "center": ("centerwindow", "", "Center window"),
            "set_prop": ("setprop", "", "Set property"),
            "alter_zorder": ("alterzorder", "", "Alter z-order"),
            "deny_group": ("denywindowfromgroup", "", "Deny group"),
            "lock_groups": ("lockgroups", "", "Lock groups"),
        }
        if method in window_map:
            d, p, desc = window_map[method]
            if method == "move":
                if "direction" in body:
                    dm = re.search(r'direction\s*=\s*"?([^",}]+)"?', body)
                    val = dm.group(1).strip().strip('"') if dm else ""
                    return ("movewindow", val, f"Move window {val}")
                if "workspace" in body:
                    wm = re.search(r'workspace\s*=\s*"?([^",}]+)"?', body)
                    val = wm.group(1).strip().strip('"') if wm else ""
                    return ("movetoworkspace", val, f"Move to workspace {val}")
                if "monitor" in body:
                    mm = re.search(r'monitor\s*=\s*"?([^",}]+)"?', body)
                    val = mm.group(1).strip().strip('"') if mm else ""
                    return ("movewindow", val, f"Move to monitor {val}")
                if "x" in body or "y" in body:
                    xm = re.search(r'x\s*=\s*"?([^",}]+)"?', body)
                    ym = re.search(r'y\s*=\s*"?([^",}]+)"?', body)
                    x = xm.group(1).strip().strip('"') if xm else "0"
                    y = ym.group(1).strip().strip('"') if ym else "0"
                    return ("moveactive", f"{x} {y}", f"Move to ({x}, {y})")
                if "into_or_create_group" in body:
                    gm = re.search(r'into_or_create_group\s*=\s*"?([^",}]+)"?', body)
                    val = gm.group(1).strip().strip('"') if gm else ""
                    return ("moveintoorcreategroup", val, f"Move/create group {val}")
                if "into_group" in body:
                    gm = re.search(r'into_group\s*=\s*"?([^",}]+)"?', body)
                    val = gm.group(1).strip().strip('"') if gm else ""
                    return ("moveintogroup", val, f"Move into group {val}")
                return ("movetoworkspace", "", "Move to workspace")
            if method == "fullscreen":
                am = re.search(r'mode\s*=\s*"?([^",}]+)"?', body)
                mode = am.group(1).strip().strip('"') if am else "toggle"
                return ("fullscreen", mode, f"Fullscreen {mode}")
            if method == "signal":
                sm = re.search(r'signal\s*=\s*"?([^",}]+)"?', body)
                val = sm.group(1).strip().strip('"') if sm else ""
                return ("signal", val, f"Signal {val}" if val else "Signal window")
            if method == "set_prop":
                pm = re.search(r'property\s*=\s*"([^"]*)"', body)
                val = pm.group(1) if pm else ""
                return ("setprop", val, f"Set property {val}" if val else "Set property")
            if method == "pseudo":
                am = re.search(r'action\s*=\s*"?([^",}]+)"?', body)
                val = am.group(1).strip().strip('"') if am else ""
                return ("pseudo", val, f"Pseudo {val}" if val else "Toggle pseudo")
            return (d, p, desc)
        action_str = f"hl.dsp.window.{method}({body})"
        return ("exec", action_str, f"Window: {method}")

    # ── hl.dsp.layout("xxx") ──
    m = re.match(r'hl\.dsp\.layout\(\s*"([^"]*)"\s*\)\s*$', expr)
    if m:
        val = m.group(1)
        return ("layoutmsg", val, f"Layout: {val}")

    # ── Unknown expression — fallback: show as-is ──
    return ("exec", expr, expr)


def parse_lua_bind_line(line: str, source_file: str) -> dict | None:
    """Parse a Hyprland Lua bind.

    Supports two formats:
      1. hl.bind("MODS + KEY", "dispatcher params")           — string second arg
      2. hl.bind("MODS + KEY", hl.dsp.xxx(...))              — Lua expression second arg
      3. hl.bind("MODS + KEY", hl.dsp.xxx(...), { opts })    — with options table
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("--"):
        return None

    # Strip trailing Lua comments (-- ...)
    stripped = re.sub(r'\s*--\s*.*$', '', stripped)

    # Match: hl.bind("KEY", REST...)
    m = re.match(r'hl\.bind\s*\(\s*"([^"]+)"\s*,\s*(.*)', stripped)
    if not m:
        m = re.match(r"hl\.bind\s*\(\s*'([^']+)'\s*,\s*(.*)", stripped)
    if not m:
        return None

    key_str = m.group(1)
    rest = m.group(2)

    # Parse options if present (trailing { ... })
    flags = ""
    desc = ""
    opts_match = re.search(r'\{([^}]*)\}\s*\)\s*$', stripped)
    if opts_match:
        opts_text = opts_match.group(1)
        if "locked" in opts_text and "true" in opts_text:
            flags += "l"
        if "repeating" in opts_text and "true" in opts_text:
            flags += "e"
        desc_m = re.search(r'description\s*=\s*"([^"]*)"', opts_text)
        if desc_m:
            desc = desc_m.group(1)

    # Convert " + " separated key to canonical
    key_parts = [canonicalize_key(k) for k in re.split(r'\s*\+\s*', key_str)]
    key_combo = "+".join(key_parts)

    # ── Determine dispatcher + params ──
    # Strip options table if present, then strip closing ) of hl.bind(...)
    # Handle both single-line { ... } and multi-line { ... } (where } is on next line)
    expr = re.sub(r'\s*,\s*\{[\s\S]*$', '', rest)  # strip ,{...} (greedy to handle multi-line)
    expr = expr.strip()

    # Count parentheses to determine if we need to strip trailing )
    # For single-line: rest = "hl.dsp.xxx())" → need to strip outer )
    # For multi-line: rest = "hl.dsp.xxx()" → ) is part of the function call, don't strip
    open_count = expr.count('(')
    close_count = expr.count(')')
    if close_count > open_count:
        expr = re.sub(r'\)\s*$', '', expr).strip()
    if not expr:
        return None

    # Check if second arg is a quoted string (old format) or Lua expression (new format)
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        # Old format: string arg — "dispatcher params"
        action_str = expr.strip('"').strip("'")
        action_parts = action_str.split(None, 1)
        dispatcher = action_parts[0].lower() if action_parts else ""
        params = action_parts[1] if len(action_parts) > 1 else ""
        action_display = action_str
    else:
        # New format: Lua expression — hl.dsp.xxx(...)
        dispatcher, params, _ = _parse_lua_dispatcher(expr)
        action_display = f"{dispatcher} {params}".strip() if params else dispatcher

    return {
        "key": key_combo,
        "action": action_display,
        "dispatcher": dispatcher,
        "params": params,
        "desc": desc or autogenerate_desc(dispatcher, params),
        "flags": flags,
        "source": source_file,
    }


def parse_lua_unbind_line(line: str) -> str | None:
    """Parse hl.unbind("MODS + KEY") → return key combo."""
    stripped = line.strip()
    m = re.match(r'hl\.unbind\s*\(\s*"([^"]+)"\s*\)', stripped)
    if not m:
        m = re.match(r"hl\.unbind\s*\(\s*'([^']+)'\s*\)", stripped)
    if not m:
        return None
    key_str = m.group(1)
    key_parts = [canonicalize_key(k) for k in re.split(r'\s*\+\s*', key_str)]
    return "+".join(key_parts)


def autogenerate_desc(dispatcher: str, params: str) -> str:
    """Generate a human-readable description for a bind."""
    desc_map = {
        "killactive": "Close window",
        "forcekillactive": "Force close window",
        "closewindow": "Close window",
        "killwindow": "Kill window",
        "togglefloating": "Toggle floating",
        "setfloating": "Set floating",
        "settiled": "Set tiled",
        "pin": "Pin (all workspaces)",
        "fullscreen": "Toggle fullscreen",
        "fullscreenstate": "Fullscreen state",
        "fakefullscreen": "Toggle fake fullscreen",
        "splitratio": f"Split ratio {params}" if params else "Split ratio",
        "exit": "Exit Hyprland",
        "dpms": f"DPMS {params}" if params else "Toggle DPMS",
        "movefocus": f"Move focus {params}" if params else "Move focus",
        "cyclenext": "Cycle window",
        "cycleprev": "Cycle prev window",
        "swapnext": "Swap next",
        "pseudo": "Toggle pseudo",
        "togglegroup": "Toggle group",
        "changegroupactive": "Cycle group",
        "movegroupwindow": "Move in group",
        "centerwindow": "Center window",
        "bringactivetotop": "Bring to top",
        "alterzorder": "Alter z-order",
        "forcerendererreload": "Reload renderer",
        "setprop": f"Set property {params}" if params else "Set property",
        "sendshortcut": "Send shortcut",
        "sendkeystate": "Send key state",
        "pass": "Pass shortcut",
        "movecursortocorner": f"Cursor to corner {params}" if params else "Cursor to corner",
        "movecursor": f"Move cursor {params}" if params else "Move cursor",
        "renameworkspace": f"Rename workspace {params}" if params else "Rename workspace",
        "moveworkspacetomonitor": f"Move workspace to monitor {params}" if params else "Move workspace",
        "swapactiveworkspaces": "Swap active workspaces",
        "togglespecialworkspace": "Toggle special workspace",
        "denywindowfromgroup": "Deny group entry",
        "lockgroups": "Lock groups",
        "event": f"Event: {params}" if params else "Event",
        "layout": f"Layout: {params}" if params else "Layout message",
        "signal": f"Signal {params}" if params else "Signal window",
        "signalwindow": f"Signal window {params}" if params else "Signal window",
        "mouse": f"Mouse {params}" if params else "Mouse action",
    }
    if dispatcher in desc_map:
        return desc_map[dispatcher]
    if dispatcher == "workspace":
        if params in ("+1", "-1"):
            return "Focus next workspace" if params == "+1" else "Focus prev workspace"
        return f"Focus workspace {params}"
    if dispatcher == "movetoworkspace":
        if params in ("+1", "-1"):
            return "Move to next workspace" if params == "+1" else "Move to prev workspace"
        return f"Move to workspace {params}"
    if dispatcher == "movetoworkspacesilent":
        if params in ("+1", "-1"):
            return "Move to next (silent)" if params == "+1" else "Move to prev (silent)"
        return f"Move to workspace {params} (silent)"
    if dispatcher == "movewindow":
        dir_map = {"l": "left", "r": "right", "u": "up", "d": "down"}
        return f"Move window {dir_map.get(params, params)}"
    if dispatcher == "resizewindow":
        return f"Resize window {params}"
    if dispatcher == "swapwindow":
        dir_map = {"l": "left", "r": "right", "u": "up", "d": "down"}
        return f"Swap window {dir_map.get(params, params)}"
    if dispatcher == "focusmonitor":
        return f"Focus monitor {params}"
    if dispatcher in ("exec", "execr", "exec_raw", "spawn"):
        return params if params else "Run command"
    if dispatcher == "movewindowpixel":
        return f"Move window to {params}"
    if dispatcher == "resizewindowpixel":
        return f"Resize window to {params}"
    if dispatcher == "layoutmsg":
        return f"Layout: {params}"
    if dispatcher == "submap":
        return f"Submap: {params}"
    if dispatcher == "moveintogroup":
        return f"Move into group {params}" if params else "Move into group"
    if dispatcher == "moveintoorcreategroup":
        return f"Move/create group {params}" if params else "Move/create group"
    if dispatcher == "moveoutofgroup":
        return "Move out of group"
    if dispatcher == "moveactive":
        return f"Move to {params}" if params else "Move window"
    if dispatcher == "movecurrentworkspacetomonitor":
        return f"Move workspace to monitor {params}" if params else "Move workspace"
    return ""


# ── File Reading ──

def read_config_files(config_dir: Path) -> tuple[list[str], str]:
    """Read all config files, return (lines, combined_text)."""
    lines = []
    # Read main config
    is_lua = detect_lua_format(config_dir)
    main = get_main_config_path(config_dir, is_lua)
    if main and main.exists():
        lines.extend(read_file_lines(main, config_dir))
    # Also read any other .conf/.lua files that might have binds
    for ext in ("*.conf", "*.lua"):
        for f in sorted(config_dir.glob(ext)):
            if f == main:
                continue
            if f.name.startswith("binds-user"):
                continue
            if f.name.startswith("binds-default"):
                continue
            content = f.read_text(errors="replace")
            file_lines = content.split("\n")
            for line in file_lines:
                stripped = line.strip()
                if stripped.startswith("bind") or stripped.startswith("source") or stripped.startswith("require"):
                    lines.append(f"#{f.name}:{line}")
    return lines


def read_file_lines(filepath: Path, base_dir: Path) -> list[str]:
    """Read a file, handling source/require includes."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return []

    lines = []
    is_lua = filepath.suffix == ".lua"

    for line in content.split("\n"):
        stripped = line.strip()

        if is_lua:
            # Handle require("...") for Lua
            m = re.match(r'require\s*\(\s*"([^"]+)"\s*\)', stripped)
            if m:
                module = m.group(1)
                rel = module.replace(".", "/") + ".lua"
                inc_path = base_dir / rel
                if inc_path.exists():
                    lines.extend(read_file_lines(inc_path, inc_path.parent))
                continue
        else:
            # Handle source = ... for conf
            if stripped.startswith("source"):
                parts = stripped.split("=", 1)
                if len(parts) > 1:
                    src = parts[1].strip().strip('"').strip("'")
                    inc_path = base_dir / src
                    if not inc_path.is_absolute():
                        inc_path = base_dir / src
                    if inc_path.exists():
                        lines.extend(read_file_lines(inc_path, inc_path.parent))
                    continue

        lines.append(line)

    return lines

def _join_multiline_binds(lines: list[str]) -> list[str]:
    """Join multi-line hl.bind() calls into single lines."""
    joined = []
    buf = ""
    in_bind = False
    for line in lines:
        stripped = line.strip()
        if not in_bind:
            if "hl.bind" in stripped:
                # Count parens to detect multi-line
                if stripped.count("(") > stripped.count(")"):
                    buf = stripped
                    in_bind = True
                    continue
            joined.append(line)
        else:
            buf += " " + stripped
            if buf.count("(") <= buf.count(")"):
                joined.append(buf)
                buf = ""
                in_bind = False
    if buf:
        joined.append(buf)
    return joined

def extract_binds_from_lines(lines: list[str]) -> list[dict]:
    """Extract all keybinds from config lines."""
    binds = []
    lines = _join_multiline_binds(lines)
    for line in lines:
        stripped = line.strip()

        # Skip comments (but handle #source: prefix from read_config_files)
        if stripped.startswith("#"):
            # Check if it's a source marker from our reading
            if stripped.startswith("#") and ":" in stripped:
                # This is a marker from read_config_files, skip
                pass
            continue

        

        # Check if it's a Lua bind
        if "hl.bind" in stripped:
            bind = parse_lua_bind_line(stripped, "config")
            if bind:
                binds.append(bind)
            continue
        
        if not stripped.startswith("bind"):
            continue
        # Conf format
        bind = parse_conf_bind_line(stripped, "config")
        if bind:
            binds.append(bind)

    return binds


def read_user_overrides(override_path: Path) -> dict[str, dict]:
    """Read existing user overrides. Returns dict keyed by normalized key."""
    overrides = {}
    if not override_path.exists():
        return overrides

    content = override_path.read_text(errors="replace")
    lines = content.split("\n")
    is_lua = override_path.suffix == ".lua"

    pending_unbinds = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("#"):
            continue

        if is_lua:
            # Check for unbind
            key = parse_lua_unbind_line(stripped)
            if key:
                pending_unbinds.add(key.lower())
                continue
            # Check for bind
            bind = parse_lua_bind_line(stripped, str(override_path))
            if bind:
                overrides[bind["key"].lower()] = bind
                pending_unbinds.discard(bind["key"].lower())
        else:
            # Conf format override
            if stripped.startswith("unbind"):
                parts = stripped.split("=", 1)
                if len(parts) > 1:
                    key = canonicalize_key(parts[1].strip())
                    pending_unbinds.add(key.lower())
                    continue
            bind = parse_conf_bind_line(stripped, str(override_path))
            if bind:
                overrides[bind["key"].lower()] = bind
                pending_unbinds.discard(bind["key"].lower())

    # Mark pending unbinds
    for k in pending_unbinds:
        overrides[k] = {"key": k, "action": "", "unbind": True}

    return overrides


# ── Categorize ──

def categorize_bind(dispatcher: str) -> str:
    """Categorize a bind by its dispatcher."""
    return DISPATCHER_TO_CATEGORY.get(dispatcher, "Other")


def build_output(binds: list[dict], override_path: Path, is_lua: bool) -> dict:
    """Build the JSON output structure."""
    categorized: dict[str, list[dict]] = {}
    for bind in binds:
        cat = categorize_bind(bind["dispatcher"])
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append({
            "key": bind["key"],
            "action": bind["action"],
            "desc": bind.get("desc", ""),
            "flags": bind.get("flags", ""),
            "category": cat,
        })

    # Sort categories
    cat_order = ["Window", "Workspace", "Execute", "System", "Focus",
                 "Layout", "Group", "Input", "Cursor", "Misc", "Other"]
    sorted_cats = {k: categorized[k] for k in cat_order if k in categorized}
    # Add any remaining categories
    for k in categorized:
        if k not in sorted_cats:
            sorted_cats[k] = categorized[k]

    return {
        "provider": "hyprland",
        "modKey": "Super",
        "isLua": is_lua,
        "binds": sorted_cats,
        "overridePath": str(override_path),
    }


# ── Commands ──

def cmd_show(args):
    """Parse config and output all keybinds as JSON."""
    config_dir = get_hypr_config_dir()
    is_lua = detect_lua_format(config_dir)
    override_path = get_override_path(is_lua)

    lines = read_config_files(config_dir)
    binds = extract_binds_from_lines(lines)

    # Also read overrides and overlay them
    overrides = read_user_overrides(override_path)
    override_binds = []
    for key_lower, override in overrides.items():
        if override.get("unbind"):
            # Remove the bind if it exists
            binds = [b for b in binds if b["key"].lower() != key_lower]
        else:
            # Update or add
            found = False
            for b in binds:
                if b["key"].lower() == key_lower:
                    b["action"] = override["action"]
                    b["desc"] = override.get("desc", b.get("desc", ""))
                    b["flags"] = override.get("flags", b.get("flags", ""))
                    b["source"] = "user_override"
                    found = True
                    break
            if not found:
                dispatcher_parts = override["action"].split(None, 1)
                dispatcher = dispatcher_parts[0].lower() if dispatcher_parts else ""
                override_binds.append({
                    "key": override["key"],
                    "action": override["action"],
                    "dispatcher": dispatcher,
                    "params": dispatcher_parts[1] if len(dispatcher_parts) > 1 else "",
                    "desc": override.get("desc", ""),
                    "flags": override.get("flags", ""),
                    "source": "user_override",
                })

    binds.extend(override_binds)

    output = build_output(binds, override_path, is_lua)
    print(json.dumps(output, indent=2))


def cmd_set(args):
    """Add or update a keybind override."""
    config_dir = get_hypr_config_dir()
    is_lua = detect_lua_format(config_dir)
    override_path = get_override_path(is_lua)

    # Ensure directory exists
    override_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing overrides
    overrides = read_user_overrides(override_path)

    key = args.key
    action = args.action
    desc = args.desc or ""
    flags = args.flags or ""

    # Canonicalize the key
    key_combo = key  # Already in canonical form from user

    overrides[key_combo.lower()] = {
        "key": key_combo,
        "action": action,
        "desc": desc,
        "flags": flags,
    }

    write_override_file(override_path, overrides, is_lua)
    print(json.dumps({"success": True, "key": key_combo, "action": action}))


def cmd_remove(args):
    """Remove a keybind (write unbind override)."""
    config_dir = get_hypr_config_dir()
    is_lua = detect_lua_format(config_dir)
    override_path = get_override_path(is_lua)

    override_path.parent.mkdir(parents=True, exist_ok=True)

    overrides = read_user_overrides(override_path)
    key = args.key
    overrides[key.lower()] = {"key": key, "action": "", "unbind": True}

    write_override_file(override_path, overrides, is_lua)
    print(json.dumps({"success": True, "key": key, "removed": True}))


def cmd_reset(args):
    """Reset a keybind override (revert to config default)."""
    config_dir = get_hypr_config_dir()
    is_lua = detect_lua_format(config_dir)
    override_path = get_override_path(is_lua)

    if not override_path.exists():
        print(json.dumps({"success": True, "key": args.key, "reset": True}))
        return

    overrides = read_user_overrides(override_path)
    key_lower = args.key.lower()
    if key_lower in overrides:
        del overrides[key_lower]

    write_override_file(override_path, overrides, is_lua)
    print(json.dumps({"success": True, "key": args.key, "reset": True}))


def write_override_file(path: Path, overrides: dict, is_lua: bool):
    """Write the override file."""
    if not overrides:
        path.unlink(missing_ok=True)
        return

    # Filter out unbinds that don't correspond to anything
    active = {k: v for k, v in overrides.items() if not v.get("unbind")}
    unbinds = {k: v for k, v in overrides.items() if v.get("unbind")}

    if not active and not unbinds:
        path.unlink(missing_ok=True)
        return

    lines = ["-- NAnDoroid user keybind overrides (managed by settings UI)"]

    if is_lua:
        # Write Lua format
        for key_lower, bind in sorted(active.items()):
            key_str = format_lua_key(bind["key"])
            action = bind["action"]
            opts_parts = []
            if bind.get("flags"):
                if "l" in bind["flags"]:
                    opts_parts.append("locked = true")
                if "e" in bind["flags"]:
                    opts_parts.append("repeating = true")
                if "r" in bind["flags"]:
                    opts_parts.append("release = true")
            if bind.get("desc"):
                opts_parts.append(f'description = "{escape_lua(bind["desc"])}"')

            lines.append(f'hl.unbind("{key_str}")')

            # Build valid Lua dispatcher expression from conf action
            dispatcher_expr = _conf_action_to_lua_expr(action)

            if opts_parts:
                lines.append(f'hl.bind("{key_str}", {dispatcher_expr}, {{ {", ".join(opts_parts)} }})')
            else:
                lines.append(f'hl.bind("{key_str}", {dispatcher_expr})')

        for key_lower, bind in sorted(unbinds.items()):
            key_str = format_lua_key(bind["key"])
            lines.append(f'hl.unbind("{key_str}")')
    else:
        # Write conf format
        for key_lower, bind in sorted(active.items()):
            key_str = bind["key"]
            action = bind["action"]
            flags_str = bind.get("flags", "")
            desc = bind.get("desc", "")
            bind_type = f"bind{flags_str}"
            comment = f" # {desc}" if desc else ""
            lines.append(f"{bind_type} = {key_str}, {action}{comment}")

        for key_lower, bind in sorted(unbinds.items()):
            lines.append(f"unbind = {bind['key']}")

    path.write_text("\n".join(lines) + "\n")


def format_lua_key(key: str) -> str:
    """Format key for Lua: 'Super+Shift+A' → 'SUPER SHIFT A'."""
    parts = key.split("+")
    normalized = []
    for p in parts:
        low = p.lower()
        if low in ("super", "mod4", "mainmod"):
            normalized.append("SUPER")
        elif low in ("ctrl", "control"):
            normalized.append("CTRL")
        elif low == "shift":
            normalized.append("SHIFT")
        elif low in ("alt", "mod1"):
            normalized.append("ALT")
        elif len(p) == 1:
            normalized.append(p.upper())
        else:
            normalized.append(p)
    return " + ".join(normalized)


def escape_lua(s: str) -> str:
    """Escape string for Lua."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_lua_str(s: str) -> str:
    """Escape a string for use inside Lua double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _conf_action_to_lua_expr(action: str) -> str:
    """Convert a conf-format action (e.g. 'exec firefox') back to a Lua expression.

    Examples:
      'exec firefox'          → 'hl.dsp.exec_cmd("firefox")'
      'killactive'            → 'hl.dsp.window.close()'
      'workspace 3'           → 'hl.dsp.focus({ workspace = "3" })'
      'movetoworkspace +1'    → 'hl.dsp.window.move({ workspace = "+1" })'
      'movefocus l'           → 'hl.dsp.focus({ direction = "l" })'
      'global signal:name'    → 'hl.dsp.global("signal:name")'
      'submap resize'         → 'hl.dsp.submap("resize")'
      'layoutmsg togglesplit' → 'hl.dsp.layout("togglesplit")'
      'togglefloating'        → 'hl.dsp.window.float()'
      'fullscreen'            → 'hl.dsp.window.fullscreen()'
      'pin'                   → 'hl.dsp.window.pin()'
      'cyclenext'             → 'hl.dsp.window.cycle_next()'
      'cycleprev'             → 'hl.dsp.window.cycle_prev()'
      'swapnext'              → 'hl.dsp.window.swap_next()'
      'centerwindow'          → 'hl.dsp.window.center()'
      'togglegroup'           → 'hl.dsp.group.toggle()'
      'changegroupactive'     → 'hl.dsp.group.next()'
      'movegroupwindow'       → 'hl.dsp.group.move_window({ forward = true })'
      'exit'                  → 'hl.dsp.exit()'
      'dpms toggle'           → 'hl.dsp.dpms({ action = "toggle" })'
      'event custom:data'     → 'hl.dsp.event("custom:data")'
    """
    parts = action.strip().split(None, 1)
    dispatcher = parts[0] if parts else ""
    params = parts[1] if len(parts) > 1 else ""

    # ── Exec ──
    if dispatcher in ("exec", "execr", "spawn"):
        fn = "exec_cmd" if dispatcher == "exec" else "exec_raw"
        return f'hl.dsp.{fn}("{_escape_lua_str(params)}")'

    # ── Window methods ──
    window_conf_to_lua = {
        "killactive": ("window", "close", []),
        "forcekillactive": ("window", "kill", []),
        "killwindow": ("window", "kill", []),
        "closewindow": ("window", "close", []),
        "togglefloating": ("window", "float", []),
        "setfloating": ("window", "float", [{"action": "set"}]),
        "settiled": ("window", "float", [{"action": "unset"}]),
        "pin": ("window", "pin", []),
        "fullscreen": ("window", "fullscreen", []),
        "fullscreenstate": ("window", "fullscreen_state", []),
        "fakefullscreen": ("window", "fullscreen", [{"mode": "maximized"}]),
        "pseudo": ("window", "pseudo", []),
        "cyclenext": ("window", "cycle_next", []),
        "cycleprev": ("window", "cycle_prev", []),
        "swapnext": ("window", "swap_next", []),
        "centerwindow": ("window", "center", []),
        "bringactivetotop": ("window", "alter_zorder", [{"zheight": "top"}]),
        "alterzorder": ("window", "alter_zorder", []),
        "setprop": ("window", "set_prop", []),
        "denywindowfromgroup": ("window", "deny_group", []),
        "lockgroups": ("window", "lock_groups", []),
    }
    if dispatcher in window_conf_to_lua:
        ns, method, extra_opts = window_conf_to_lua[dispatcher]
        if extra_opts and params:
            opt_str = ", ".join(f'{k} = "{v}"' for d in extra_opts for k, v in d.items())
            return f'hl.dsp.{ns}.{method}({{{opt_str}}})'
        if params:
            return f'hl.dsp.{ns}.{method}({params})'
        return f'hl.dsp.{ns}.{method}()'

    # ── movetoworkspace / movetoworkspacesilent ──
    if dispatcher in ("movetoworkspace", "movetoworkspacesilent"):
        if params.startswith("special:"):
            ws = params[len("special:"):]
            return f'hl.dsp.window.move({{ workspace = "special:{ws}" }})'
        return f'hl.dsp.window.move({{ workspace = "{params}" }})'

    # ── movewindow ──
    if dispatcher == "movewindow":
        dir_map = {"l": "left", "r": "right", "u": "up", "d": "down"}
        d = dir_map.get(params, params)
        return f'hl.dsp.window.move({{ direction = "{d}" }})'

    # ── movewindowpixel ──
    if dispatcher == "movewindowpixel":
        return f'hl.dsp.window.move({{ x = 0, y = 0, relative = true }})'

    # ── resizewindow ──
    if dispatcher == "resizewindow":
        return f'hl.dsp.window.resize({{ x = 0, y = 0 }})'

    # ── resizewindowpixel / resizeactive ──
    if dispatcher in ("resizewindowpixel", "resizeactive"):
        return f'hl.dsp.window.resize({{ x = 0, y = 0, relative = true }})'

    # ── moveactive ──
    if dispatcher == "moveactive":
        return f'hl.dsp.window.move({{ x = 0, y = 0, relative = true }})'

    # ── moveworkspacetomonitor ──
    if dispatcher == "moveworkspacetomonitor":
        parts_p = params.split()
        ws = parts_p[0] if len(parts_p) > 0 else ""
        mon = parts_p[1] if len(parts_p) > 1 else ""
        return f'hl.dsp.workspace.move({{ workspace = "{ws}", monitor = "{mon}" }})'

    # ── movecurrentworkspacetomonitor ──
    if dispatcher == "movecurrentworkspacetomonitor":
        return f'hl.dsp.workspace.move({{ monitor = "{params}" }})'

    # ── Workspace ──
    if dispatcher == "workspace":
        if params.startswith("special:"):
            name = params[len("special:"):]
            return f'hl.dsp.workspace.toggle_special("{name}")'
        return f'hl.dsp.focus({{ workspace = "{params}" }})'

    # ── Focus ──
    if dispatcher == "movefocus":
        return f'hl.dsp.focus({{ direction = "{params}" }})'
    if dispatcher == "focusmonitor":
        return f'hl.dsp.focus({{ monitor = "{params}" }})'
    if dispatcher == "focuswindow":
        return f'hl.dsp.focus({{ window = "{params}" }})'
    if dispatcher == "focusurgentorlast":
        return 'hl.dsp.focus({ urgent_or_last = true })'
    if dispatcher == "focuscurrentorlast":
        return 'hl.dsp.focus({ last = true })'

    # ── Group ──
    if dispatcher == "togglegroup":
        return 'hl.dsp.group.toggle()'
    if dispatcher == "changegroupactive":
        return 'hl.dsp.group.next()'
    if dispatcher == "movegroupwindow":
        return 'hl.dsp.group.move_window({ forward = true })'
    if dispatcher == "moveintogroup":
        dir_val = params if params else "l"
        return f'hl.dsp.window.move({{ into_group = "{dir_val}" }})'
    if dispatcher == "moveintoorcreategroup":
        dir_val = params if params else "l"
        return f'hl.dsp.window.move({{ into_or_create_group = "{dir_val}" }})'
    if dispatcher == "moveoutofgroup":
        return 'hl.dsp.window.move({ into_group = "out" })'

    # ── Layout ──
    if dispatcher == "layoutmsg":
        return f'hl.dsp.layout("{params}")'

    # ── System ──
    if dispatcher == "exit":
        return 'hl.dsp.exit()'
    if dispatcher == "dpms":
        action_val = params if params else "toggle"
        return f'hl.dsp.dpms({{ action = "{action_val}" }})'
    if dispatcher == "submap":
        return f'hl.dsp.submap("{params}")'

    # ── Input ──
    if dispatcher == "pass":
        return 'hl.dsp.pass()'
    if dispatcher == "sendshortcut":
        return 'hl.dsp.send_shortcut({})'
    if dispatcher == "sendkeystate":
        return 'hl.dsp.send_key_state({})'
    if dispatcher == "mouse":
        if params == "drag":
            return 'hl.dsp.window.drag()'
        if params == "resize":
            return 'hl.dsp.window.resize()'
        return 'hl.dsp.window.drag()'

    # ── Misc ──
    if dispatcher == "global":
        return f'hl.dsp.global("{params}")'
    if dispatcher == "event":
        return f'hl.dsp.event("{params}")'

    # ── Fallback: wrap as exec ──
    return f'hl.dsp.exec_cmd("{_escape_lua_str(action)}")'


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Hyprland keybind manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("show", help="Show all keybinds")

    set_p = subparsers.add_parser("set", help="Set a keybind override")
    set_p.add_argument("key", help="Key combo (e.g. Super+Shift+A)")
    set_p.add_argument("action", help="Dispatcher action (e.g. killactive)")
    set_p.add_argument("--desc", default="", help="Description")
    set_p.add_argument("--flags", default="", help="Bind flags (e=repeat, l=locked, r=release)")

    rm_p = subparsers.add_parser("remove", help="Remove a keybind")
    rm_p.add_argument("key", help="Key combo to remove")

    rst_p = subparsers.add_parser("reset", help="Reset a keybind to default")
    rst_p.add_argument("key", help="Key combo to reset")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args)
    elif args.command == "set":
        cmd_set(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "reset":
        cmd_reset(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()