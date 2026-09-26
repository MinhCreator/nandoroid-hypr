-- hypr_tools.luau — Hyprland settings + keybinds panel
-- Port of addon/Hyprland/HyprlandSettings.qml (HyprLayout/HyprInput/HyprVisual/
-- HyprAutostart/HyprAnimations) + addon/keybindSetting/HyprKeybinds.qml.
-- Writes go through bundled scripts/hyprconfigurator.py and
-- scripts/hypr_keybinds.py (argv form, plugin_api 24) with an immediate
-- `hyprctl keyword` for live apply. Reads of binds come from the hypr-sync
-- service via noctalia.state ("binds").

local tab = "Visual"
local TABS = { "Visual", "Layout", "Input", "Animations", "Autostart", "Keybinds" }

-- Form state (seeded from live `hyprctl getoption` on open where possible)
local F = {
	rounding = 22, blur_enabled = false, blur_size = 1, blur_passes = 3,
	active_opacity = 1.0, inactive_opacity = 0.9,
	border_size = 1, gaps_in = 2, gaps_out = 5, layout = "dwindle",
	shadow_enabled = false, shadow_range = 4, shadow_power = 3,
	kb_layout = "us", numlock = true, repeat_delay = 250, repeat_rate = 35,
	follow_mouse = 1, nat_scroll = false, disable_typing = true,
	clickfinger = false, scroll_factor = 0.7,
	anims_enabled = true, anim_preset = "normal",
	autostart_enable = false, autostart_apps = {},
}

-- Keybind tab state
local kbSearch = ""
local kbCategory = ""
local kbCats = {}
local allBinds = {}
local showNew = false
local editKey = ""
local editAction = "exec "
local editDesc = ""
local editFlags = ""
local expandedKey = ""

local function cfg(key, fallback)
	local v = noctalia.getConfig(key)
	if v == nil then
		return fallback
	end
	return v
end

local function pythonBin()
	return cfg("python_bin", "python3")
end

local function overrideDir()
	return noctalia.expandPath(cfg("override_dir", "~/.config/hypr/nandoroid"))
end

local function shellOverrideFile()
	return overrideDir() .. "/shellConfig.lua"
end

local function animOverrideFile()
	return overrideDir() .. "/animations.lua"
end

local function configurator()
	local dir = noctalia.pluginDir()
	if dir == nil then
		return "scripts/hyprconfigurator.py"
	end
	return dir .. "/scripts/hyprconfigurator.py"
end

local function keybindScript()
	local dir = noctalia.pluginDir()
	if dir == nil then
		return "scripts/hypr_keybinds.py"
	end
	return dir .. "/scripts/hypr_keybinds.py"
end

-- ── hyprctl helpers ──
local function hyprSet(key, value)
	-- Persist via configurator override file…
	noctalia.runAsync({ pythonBin(), configurator(), "--file", shellOverrideFile(), "--set", key, tostring(value) })
	-- …and apply live for the running session.
	noctalia.runAsync({ "hyprctl", "keyword", key, tostring(value) }, function(r)
		if r.exitCode ~= 0 then
			noctalia.notifyError("Hyprland", "keyword failed: " .. key)
		end
	end)
end

local function hyprGetOption(key, cb)
	noctalia.runAsync({ "hyprctl", "getoption", key, "-j" }, function(r)
		if r.exitCode ~= 0 then
			return
		end
		local ok, data = pcall(noctalia.json.decode, r.stdout)
		if ok and type(data) == "table" then
			cb(data)
		end
	end)
end

local function seedLiveValues()
	hyprGetOption("decoration:rounding", function(d)
		if d.int ~= nil then
			F.rounding = d.int
			render()
		end
	end)
	hyprGetOption("general:layout", function(d)
		if d.str ~= nil then
			F.layout = d.str
			render()
		end
	end)
	hyprGetOption("animations:enabled", function(d)
		if d.int ~= nil then
			F.anims_enabled = d.int ~= 0
			render()
		end
	end)
end

local function setAnimPreset(preset)
	F.anim_preset = preset
	noctalia.runAsync({ pythonBin(), configurator(), "--anim-preset", preset, "--anim-file", animOverrideFile() })
	noctalia.runAsync({ "hyprctl", "reload" })
end

-- ── Autostart persistence (pluginDataDir; Config.qml not reused) ──
local function autostartPath()
	local dir = noctalia.pluginDataDir()
	if dir == nil then
		return nil
	end
	return dir .. "/autostart.json"
end

local function loadAutostart()
	local p = autostartPath()
	if p == nil then
		return
	end
	local raw = noctalia.readFile(p)
	if raw == nil then
		return
	end
	local ok, data = pcall(noctalia.json.decode, raw)
	if ok and type(data) == "table" then
		if data.enable ~= nil then
			F.autostart_enable = data.enable and true or false
		end
		if type(data.apps) == "table" then
			F.autostart_apps = data.apps
		end
	end
end

local function saveAutostart()
	local p = autostartPath()
	if p == nil then
		return
	end
	noctalia.writeFile(p, noctalia.json.encode({ enable = F.autostart_enable, apps = F.autostart_apps }))
end

function testAutostart()
	local dir = noctalia.pluginDir()
	local scr = (dir ~= nil) and (dir .. "/scripts/autostart.py") or "scripts/autostart.py"
	noctalia.runAsync({ pythonBin(), scr })
end

-- ── Keybind data ──
local function refreshBindsFromState(v)
	allBinds = {}
	kbCats = {}
	if type(v) ~= "table" then
		render()
		return
	end
	local binds = v.binds or v
	if type(binds) ~= "table" then
		render()
		return
	end
	for cat, list in pairs(binds) do
		if type(list) == "table" then
			table.insert(kbCats, tostring(cat))
			for _, b in ipairs(list) do
				if type(b) == "table" then
					if b.category == nil then
						b.category = tostring(cat)
					end
					table.insert(allBinds, b)
				end
			end
		end
	end
	table.sort(kbCats)
end

local function filteredBinds()
	local out = {}
	local q = string.lower(kbSearch or "")
	for _, b in ipairs(allBinds) do
		local key = string.lower(tostring(b.key or ""))
		local desc = string.lower(tostring(b.desc or ""))
		local act = string.lower(tostring(b.action or ""))
		local hit = true
		if q ~= "" then
			hit = string.find(key, q, 1, true) ~= nil or string.find(desc, q, 1, true) ~= nil or string.find(act, q, 1, true) ~= nil
		end
		if hit and (kbCategory == "" or tostring(b.category or "") == kbCategory) then
			table.insert(out, b)
		end
	end
	return out
end

local function findConflicts(keyCombo)
	local out = {}
	local n = string.lower(keyCombo or "")
	for _, b in ipairs(allBinds) do
		if string.lower(tostring(b.key or "")) == n then
			table.insert(out, b)
		end
	end
	return out
end

function kbMutate(mode)
	-- mode: "set" | "remove" | "reset"
	local args
	if mode == "set" then
		if editKey == "" or editAction == "" then
			noctalia.notifyError("Keybinds", "key and action are required")
			return
		end
		local conflicts = findConflicts(editKey)
		if #conflicts > 0 and expandedKey ~= editKey then
			noctalia.notify("Keybinds", "Overwriting " .. tostring(#conflicts) .. " conflicting bind(s)")
		end
		args = { pythonBin(), keybindScript(), "set", editKey, editAction }
		if editDesc ~= "" then
			table.insert(args, "--desc")
			table.insert(args, editDesc)
		end
		if editFlags ~= "" then
			table.insert(args, "--flags")
			table.insert(args, editFlags)
		end
	elseif mode == "remove" then
		args = { pythonBin(), keybindScript(), "remove", expandedKey }
	else
		args = { pythonBin(), keybindScript(), "reset", expandedKey }
	end
	noctalia.runAsync(args, function(r)
		if r.exitCode ~= 0 then
			noctalia.notifyError("Keybinds", (r.stderr ~= "" and r.stderr or "operation failed"))
			return
		end
		showNew = false
		expandedKey = ""
		-- Service poll will pick up the new `show` output on next tick.
	end)
end

-- ── Small ui builders ──
local function sectionTitle(glyph, text)
	return ui.row({ gap = 8, align = "center" }, {
		ui.glyph({ name = glyph, size = 18, color = "primary" }),
		ui.label({ text = text, fontSize = 15, fontWeight = "bold" }),
	})
end

local function toggleRow(label, sub, checked, onChange)
	local left = { ui.label({ text = label, fontWeight = "bold" }) }
	if sub ~= nil and sub ~= "" then
		table.insert(left, ui.label({ text = sub, fontSize = 11 }))
	end
	return ui.row({ gap = 12, align = "center", justify = "space_between" }, {
		ui.column({ gap = 2 }, left),
		ui.toggle({ checked = checked, onChange = onChange }),
	})
end

local function stepperRow(label, value, minV, maxV, step, fmt, onPick)
	return ui.row({ gap = 12, align = "center", justify = "space_between" }, {
		ui.label({ text = label, fontWeight = "bold" }),
		ui.row({ gap = 6, align = "center" }, {
			ui.button({ text = "−", controlSize = "sm", onClick = function()
				onPick(math.max(minV, value - step))
			end }),
			ui.label({ text = fmt(value), fontSize = 13 }),
			ui.button({ text = "+", controlSize = "sm", onClick = function()
				onPick(math.min(maxV, value + step))
			end }),
		}),
	})
end

-- ── Tab bodies ──
local function visualTab()
	return {
		sectionTitle("deblur", noctalia.tr("hypr.visual_title")),
		stepperRow("Rounding", F.rounding, 0, 100, 1, tostring, function(v)
			F.rounding = math.floor(v)
			hyprSet("decoration:rounding", math.floor(v))
			render()
		end),
		toggleRow("Blur", "", F.blur_enabled, function(v)
			F.blur_enabled = (v == "true")
			hyprSet("decoration:blur:enabled", F.blur_enabled and 1 or 0)
			render()
		end),
		stepperRow("Blur size", F.blur_size, 1, 20, 1, tostring, function(v)
			F.blur_size = math.floor(v)
			hyprSet("decoration:blur:size", math.floor(v))
			render()
		end),
		stepperRow("Blur passes", F.blur_passes, 1, 8, 1, tostring, function(v)
			F.blur_passes = math.floor(v)
			hyprSet("decoration:blur:passes", math.floor(v))
			render()
		end),
		stepperRow("Active opacity", F.active_opacity, 0.1, 1.0, 0.05, function(x)
			return string.format("%.2f", x)
		end, function(v)
			F.active_opacity = v
			hyprSet("decoration:active_opacity", v)
			render()
		end),
		stepperRow("Inactive opacity", F.inactive_opacity, 0.1, 1.0, 0.05, function(x)
			return string.format("%.2f", x)
		end, function(v)
			F.inactive_opacity = v
			hyprSet("decoration:inactive_opacity", v)
			render()
		end),
		stepperRow("Border size", F.border_size, 0, 10, 1, tostring, function(v)
			F.border_size = math.floor(v)
			hyprSet("general:border_size", math.floor(v))
			render()
		end),
		stepperRow("Gaps in", F.gaps_in, 0, 40, 1, tostring, function(v)
			F.gaps_in = math.floor(v)
			hyprSet("general:gaps_in", math.floor(v))
			render()
		end),
		stepperRow("Gaps out", F.gaps_out, 0, 60, 1, tostring, function(v)
			F.gaps_out = math.floor(v)
			hyprSet("general:gaps_out", math.floor(v))
			render()
		end),
		toggleRow("Shadow", "", F.shadow_enabled, function(v)
			F.shadow_enabled = (v == "true")
			hyprSet("decoration:shadow:enabled", F.shadow_enabled and 1 or 0)
			render()
		end),
		stepperRow("Shadow range", F.shadow_range, 0, 40, 1, tostring, function(v)
			F.shadow_range = math.floor(v)
			hyprSet("decoration:shadow:range", math.floor(v))
			render()
		end),
		stepperRow("Shadow power", F.shadow_power, 1, 4, 1, tostring, function(v)
			F.shadow_power = math.floor(v)
			hyprSet("decoration:shadow:render_power", math.floor(v))
			render()
		end),
	}
end

local function layoutTab()
	local opts = { "dwindle", "master", "scrolling" }
	local idx = 1
	for i, o in ipairs(opts) do
		if o == F.layout then
			idx = i
		end
	end
	return {
		sectionTitle("auto_awesome_mosaic", noctalia.tr("hypr.layout_title")),
		ui.label({ text = noctalia.tr("hypr.layout_hint"), fontSize = 12 }),
		ui.select({
			options = opts,
			selectedIndex = idx - 1,
			onChange = function(v)
				local i = tonumber(v) or 0
				F.layout = opts[i + 1] or "dwindle"
				hyprSet("general:layout", F.layout)
				render()
			end,
		}),
	}
end

local function inputTab()
	local followOpts = { "0", "1", "2", "3" }
	return {
		sectionTitle("keyboard", noctalia.tr("hypr.input_title")),
		ui.row({ gap = 8, align = "center", justify = "space_between" }, {
			ui.label({ text = "Keyboard layout", fontWeight = "bold" }),
			ui.input({ value = F.kb_layout, placeholder = "us", onSubmit = "onKbLayout" }),
		}),
		toggleRow("Numlock on boot", "", F.numlock, function(v)
			F.numlock = (v == "true")
			hyprSet("input:numlock_by_default", F.numlock and 1 or 0)
			render()
		end),
		stepperRow("Repeat delay", F.repeat_delay, 100, 1000, 10, tostring, function(v)
			F.repeat_delay = math.floor(v)
			hyprSet("input:repeat_delay", math.floor(v))
			render()
		end),
		stepperRow("Repeat rate", F.repeat_rate, 10, 100, 1, tostring, function(v)
			F.repeat_rate = math.floor(v)
			hyprSet("input:repeat_rate", math.floor(v))
			render()
		end),
		ui.row({ gap = 8, align = "center", justify = "space_between" }, {
			ui.label({ text = "Follow mouse", fontWeight = "bold" }),
			ui.select({
				options = followOpts,
				selectedIndex = F.follow_mouse,
				onChange = function(v)
					F.follow_mouse = tonumber(v) or 1
					hyprSet("input:follow_mouse", F.follow_mouse)
					render()
				end,
			}),
		}),
		sectionTitle("mouse", "Touchpad"),
		toggleRow("Natural scroll", "", F.nat_scroll, function(v)
			F.nat_scroll = (v == "true")
			hyprSet("input:touchpad:natural_scroll", F.nat_scroll and 1 or 0)
			render()
		end),
		toggleRow("Disable while typing", "", F.disable_typing, function(v)
			F.disable_typing = (v == "true")
			hyprSet("input:touchpad:disable_while_typing", F.disable_typing and 1 or 0)
			render()
		end),
		toggleRow("Clickfinger", "", F.clickfinger, function(v)
			F.clickfinger = (v == "true")
			hyprSet("input:touchpad:clickfinger_behavior", F.clickfinger and 1 or 0)
			render()
		end),
		ui.slider({
			min = 0.1,
			max = 3.0,
			step = 0.1,
			value = F.scroll_factor,
			onChange = function(v)
				F.scroll_factor = tonumber(v) or 0.7
				hyprSet("input:touchpad:scroll_factor", F.scroll_factor)
				render()
			end,
		}),
	}
end

local ANIM_PRESETS = {
	"elastic", "normal", "niri", "default", "classic", "simple",
	"diablo-1", "diablo-2", "end4", "fast", "gnome", "ja",
	"limefrenzy", "macos", "me-1", "me-2", "minimal", "moving",
	"optimized", "standard", "vertical",
}

local function animationsTab()
	local idx = 2
	for i, p in ipairs(ANIM_PRESETS) do
		if p == F.anim_preset then
			idx = i
		end
	end
	return {
		sectionTitle("animation", noctalia.tr("hypr.anims_title")),
		toggleRow("Enable animations", "", F.anims_enabled, function(v)
			F.anims_enabled = (v == "true")
			hyprSet("animations:enabled", F.anims_enabled and 1 or 0)
			render()
		end),
		ui.label({ text = "Preset", fontWeight = "bold" }),
		ui.select({
			options = ANIM_PRESETS,
			selectedIndex = idx - 1,
			onChange = function(v)
				local i = tonumber(v) or 1
				setAnimPreset(ANIM_PRESETS[i + 1] or "normal")
				render()
			end,
		}),
		ui.label({ text = 'Presets need require("hyprland/nandoroid/animations") in hyprland.lua', fontSize = 11 }),
	}
end

local function autostartTab()
	local rows = {
		sectionTitle("app_registration", noctalia.tr("hypr.autostart_title")),
		toggleRow("Enable autostart", "Launch apps on login", F.autostart_enable, function(v)
			F.autostart_enable = (v == "true")
			saveAutostart()
			render()
		end),
		ui.row({ gap = 8 }, {
			ui.button({ text = "Test run", variant = "secondary", controlSize = "sm", onClick = "testAutostart" }),
			ui.button({ text = "Add app", variant = "primary", controlSize = "sm", onClick = "addAutostart" }),
		}),
	}
	for i, app in ipairs(F.autostart_apps) do
		if type(app) == "table" then
			local n = i
			table.insert(rows, ui.row({ gap = 6, align = "center" }, {
				ui.label({ text = tostring(app.cmd or ""), flexGrow = 1 }),
				ui.label({ text = "ws " .. tostring(app.workspace or 1) .. " · " .. tostring(app.delay or 0) .. "s", fontSize = 11 }),
				ui.button({ glyph = "delete", variant = "destructive", controlSize = "sm", onClick = function()
					table.remove(F.autostart_apps, n)
					saveAutostart()
					render()
				end }),
			}))
		end
	end
	return rows
end

function addAutostart()
	table.insert(F.autostart_apps, { cmd = "firefox", workspace = 1, delay = 0 })
	saveAutostart()
	render()
end

local function keybindRow(b)
	local key = tostring(b.key or "")
	local desc = tostring(b.desc or "")
	local act = tostring(b.action or "")
	local kids = {
		ui.column({ gap = 2 }, {
			ui.label({ text = key:gsub("%+", " + "), fontWeight = "bold" }),
			ui.label({ text = (desc ~= "" and desc or act), fontSize = 11 }),
		}),
	}
	if expandedKey == key then
		table.insert(kids, ui.input({ value = editAction, placeholder = "exec …", onChange = "onEditAction" }))
		table.insert(kids, ui.input({ value = editDesc, placeholder = "description", onChange = "onEditDesc" }))
		table.insert(kids, ui.row({ gap = 6 }, {
			ui.button({ text = "Save", variant = "primary", controlSize = "sm", onClick = "onKbSave" }),
			ui.button({ text = "Remove", variant = "destructive", controlSize = "sm", onClick = "onKbRemove" }),
			ui.button({ text = "Reset", variant = "ghost", controlSize = "sm", onClick = "onKbReset" }),
			ui.button({ text = "Close", variant = "ghost", controlSize = "sm", onClick = "onKbCollapse" }),
		}))
	else
		table.insert(kids, ui.button({ text = "Edit", variant = "ghost", controlSize = "sm", onClick = function()
			expandedKey = key
			editKey = key
			editAction = act
			editDesc = desc
			editFlags = tostring(b.flags or "")
			render()
		end }))
	end
	return ui.column({ gap = 6, padding = 8, fill = "surface_variant/0.4", radius = 8 }, kids)
end

local function keybindsTab()
	local catOpts = { "" }
	for _, c in ipairs(kbCats) do
		table.insert(catOpts, c)
	end
	local selIdx = 1
	for i, c in ipairs(catOpts) do
		if c == kbCategory then
			selIdx = i
		end
	end
	local rows = {
		sectionTitle("keyboard", noctalia.tr("hypr.keybinds_title")),
		ui.row({ gap = 8, align = "center" }, {
			ui.input({ value = kbSearch, placeholder = "Search key / action / description", onChange = "onKbSearch" }),
			ui.button({ text = showNew and "Cancel" or "New", variant = "primary", controlSize = "sm", onClick = "onKbToggleNew" }),
		}),
		ui.select({
			options = catOpts,
			selectedIndex = selIdx - 1,
			placeholder = "All categories",
			onChange = "onKbCategory",
		}),
	}
	if showNew then
		table.insert(rows, ui.column({ gap = 6, padding = 8, fill = "surface_variant/0.4", radius = 8 }, {
			ui.input({ value = editKey, placeholder = "SUPER + T", onChange = "onEditKey" }),
			ui.input({ value = editAction, placeholder = "exec kitty", onChange = "onEditAction" }),
			ui.input({ value = editDesc, placeholder = "description", onChange = "onEditDesc" }),
			ui.input({ value = editFlags, placeholder = "flags (e, l, …)", onChange = "onEditFlags" }),
			ui.button({ text = "Save bind", variant = "primary", controlSize = "sm", onClick = "onKbSave" }),
		}))
	end
	local list = filteredBinds()
	for i = 1, math.min(#list, 60) do
		table.insert(rows, keybindRow(list[i]))
	end
	if #list > 60 then
		table.insert(rows, ui.label({ text = "+" .. tostring(#list - 60) .. " more — refine search", fontSize = 11 }))
	end
	if #list == 0 then
		table.insert(rows, ui.label({ text = "No binds match.", fontSize = 12 }))
	end
	return rows
end

-- ── Input callbacks (named; ui.input is uncontrolled) ──
function onKbLayout(v)
	F.kb_layout = v or "us"
	hyprSet("input:kb_layout", F.kb_layout)
	render()
end

function onKbSearch(v)
	kbSearch = v or ""
	render()
end

function onKbCategory(v)
	local i = (tonumber(v) or 0) + 1
	local catOpts = { "" }
	for _, c in ipairs(kbCats) do
		table.insert(catOpts, c)
	end
	kbCategory = catOpts[i] or ""
	render()
end

function onEditKey(v)
	editKey = v or ""
end
function onEditAction(v)
	editAction = v or ""
end
function onEditDesc(v)
	editDesc = v or ""
end
function onEditFlags(v)
	editFlags = v or ""
end

function onKbToggleNew()
	showNew = not showNew
	if showNew then
		expandedKey = ""
		editKey = ""
		editAction = "exec "
		editDesc = ""
		editFlags = ""
	end
	render()
end

function onKbSave()
	kbMutate("set")
end
function onKbRemove()
	kbMutate("remove")
end
function onKbReset()
	kbMutate("reset")
end
function onKbCollapse()
	expandedKey = ""
	render()
end

function switchTab(name)
	tab = name
	render()
end

-- ── Render ──
function render()
	local bar = {}
	for _, t in ipairs(TABS) do
		local name = t
		table.insert(bar, ui.button({
			text = name,
			variant = (tab == name) and "primary" or "ghost",
			controlSize = "sm",
			selected = tab == name,
			onClick = function()
				switchTab(name)
			end,
		}))
	end
	local body
	if tab == "Visual" then
		body = visualTab()
	elseif tab == "Layout" then
		body = layoutTab()
	elseif tab == "Input" then
		body = inputTab()
	elseif tab == "Animations" then
		body = animationsTab()
	elseif tab == "Autostart" then
		body = autostartTab()
	else
		body = keybindsTab()
	end
	table.insert(body, 1, ui.row({ gap = 6 }, bar))
	table.insert(body, ui.row({ gap = 8, align = "center", justify = "space_between" }, {
		ui.label({ text = "override: " .. overrideDir(), fontSize = 10 }),
		ui.button({ glyph = "close", variant = "ghost", controlSize = "sm", onClick = "closeMe" }),
	}))
	panel.render(ui.scroll({ padding = 16, gap = 12 }, body))
end

function closeMe()
	panel.close()
end

function onOpen(_context)
	tab = cfg("default_tab", "Visual")
	loadAutostart()
	refreshBindsFromState(noctalia.state.get("binds"))
	seedLiveValues()
	render()
end

function onClose() end

function update()
	render()
end

noctalia.state.watch("binds", function(v)
	refreshBindsFromState(v)
	if tab == "Keybinds" then
		render()
	end
end)
