-- overview.luau — workspace grid overview panel
-- Port of panels/Overview/Overview.qml (+ OverviewPopup focus/tap-outside contract
-- is host-owned: floating panel, outside-click dismiss, exclusive focus).
-- Data comes from the hypr-sync service via noctalia.state:
--   workspaces / windows / monitors / active_workspace / hypr_available.
-- Actions via hyprctl dispatch: workspace switch, focuswindow, close, movetoworkspacesilent.
-- DnD: native ui.dragSource/ui.dropZone for window → workspace moves (plugin_api 5),
-- plus keyboard-friendly select-source-then-tap-target fallback (moveAddr).
-- Thumbnails: full-fidelity live streams are unavailable (no ToplevelManager in
-- Noctalia); show_thumbnails renders grim snapshots from pluginDataDir when present
-- (see refreshSnapshot), otherwise falls back to window-chip list mode.

local columns = 5
local rows = 2
local showWallpaper = false
local showThumbnails = false

local searchQuery = ""
local selectedMatch = 1
local moveAddr = nil -- pending "move this window" address (select-then-tap)
local snapshotBusy = false

local workspaces = {}
local windows = {}
local monitors = {}
local activeWs = nil
local hyprAvailable = true
local lastError = ""

local function cfg(key, fallback)
	local v = noctalia.getConfig(key)
	if v == nil then
		return fallback
	end
	return v
end

local function loadPanelConfig()
	columns = cfg("columns", 5)
	rows = cfg("rows", 2)
	showWallpaper = cfg("show_wallpaper", false)
	showThumbnails = cfg("show_thumbnails", false)
end

-- ── Fuzzy port of Overview.qml:62-90 ──
local function fuzzyMatch(query, target)
	if #query == 0 then
		return true
	end
	local qi = 1
	for i = 1, #target do
		if string.sub(target, i, i) == string.sub(query, qi, qi) then
			qi = qi + 1
			if qi > #query then
				break
			end
		end
	end
	return qi > #query
end

local function fuzzyScore(query, target)
	if #query == 0 then
		return 0
	end
	if string.find(target, query, 1, true) then
		return 1000 + (100 - #target)
	end
	local qi = 1
	local consec = 0
	local maxConsec = 0
	local score = 0
	for i = 1, #target do
		local c = string.sub(target, i, i)
		if qi <= #query and c == string.sub(query, qi, qi) then
			qi = qi + 1
			consec = consec + 1
			if consec > maxConsec then
				maxConsec = consec
			end
			if i == 1 then
				score = score + 10
			else
				local prev = string.sub(target, i - 1, i - 1)
				if prev == " " or prev == "-" or prev == "_" then
					score = score + 10
				end
			end
		else
			consec = 0
		end
	end
	if qi > #query then
		return score + maxConsec * 5
	end
	return -1
end

local function matchingWindows()
	if searchQuery == "" then
		return {}
	end
	local q = string.lower(searchQuery)
	local scored = {}
	for _, w in ipairs(windows) do
		if type(w) == "table" then
			local title = string.lower(tostring(w.title or ""))
			local cls = string.lower(tostring(w.class or ""))
			if fuzzyMatch(q, title) or fuzzyMatch(q, cls) then
				local s = math.max(fuzzyScore(q, title), fuzzyScore(q, cls))
				table.insert(scored, { win = w, score = s })
			end
		end
	end
	table.sort(scored, function(a, b)
		return a.score > b.score
	end)
	local out = {}
	for _, e in ipairs(scored) do
		table.insert(out, e.win)
	end
	return out
end

local function windowsForWs(wsId)
	local out = {}
	for _, w in ipairs(windows) do
		if type(w) == "table" and type(w.workspace) == "table" and w.workspace.id == wsId then
			table.insert(out, w)
		end
	end
	return out
end

local function workspaceGroup()
	local activeId = 1
	if type(activeWs) == "table" and type(activeWs.id) == "number" then
		activeId = activeWs.id
	end
	return math.floor((activeId - 1) / (rows * columns))
end

-- ── Actions ──
local function dispatch(args)
	if not noctalia.commandExists("hyprctl") then
		noctalia.notifyError("Overview", "hyprctl not found")
		return
	end
	local argv = { "hyprctl", "dispatch" }
	for _, a in ipairs(args) do
		table.insert(argv, a)
	end
	noctalia.runAsync(argv)
end

function gotoWorkspace(id)
	if moveAddr ~= nil then
		dispatch({ "movetoworkspacesilent", tostring(id) .. ",address:" .. moveAddr })
		moveAddr = nil
		render()
		return
	end
	dispatch({ "workspace", tostring(id) })
end

function focusWindow(addr)
	dispatch({ "focuswindow", "address:" .. addr })
	panel.close()
end

function closeWindow(addr)
	dispatch({ "closewindow", "address:" .. addr })
end

function armMove(addr)
	moveAddr = addr
	render()
end

function cancelMove()
	moveAddr = nil
	render()
end

function onDropMove(payload, target)
	-- payload = window address, target = "ws:<id>"
	local id = string.match(target, "^ws:(%d+)$")
	if id ~= nil and payload ~= nil and payload ~= "" then
		dispatch({ "movetoworkspacesilent", id .. ",address:" .. payload })
	end
	moveAddr = nil
	render()
end

function refreshSnapshot()
	-- Spike path: capture one grim frame into pluginDataDir for ui.image cells.
	-- Falls back silently when grim is missing; list mode stays usable.
	if snapshotBusy or not showThumbnails then
		return
	end
	if not noctalia.commandExists("grim") then
		return
	end
	snapshotBusy = true
	local dir = noctalia.pluginDataDir()
	if dir == nil then
		snapshotBusy = false
		return
	end
	local dest = dir .. "/overview-snapshot.png"
	noctalia.runAsync({ "grim", dest }, function(_)
		snapshotBusy = false
		render()
	end)
end

-- ── Search input callbacks (ui.input is uncontrolled: value seeds once) ──
function onSearchChange(v)
	searchQuery = v or ""
	selectedMatch = 1
	render()
end

function onSearchSubmit(v)
	searchQuery = v or ""
	local m = matchingWindows()
	if #m > 0 then
		local idx = math.min(selectedMatch, #m)
		focusWindow(tostring(m[idx].address))
	end
end

-- ── Keyboard (capture_keys = Up/Down/Left/Right/Return/Tab) ──
function onKey(chord, pressed)
	if not pressed then
		return
	end
	local m = matchingWindows()
	if chord == "Return" then
		if #m > 0 then
			focusWindow(tostring(m[math.min(selectedMatch, #m)].address))
		end
	elseif chord == "Down" or chord == "Right" or chord == "Tab" then
		if #m > 0 then
			selectedMatch = (selectedMatch % #m) + 1
			render()
		end
	elseif chord == "Up" or chord == "Left" then
		if #m > 0 then
			selectedMatch = ((selectedMatch - 2) % #m) + 1
			render()
		end
	end
end

-- ── Render ──
local function windowChip(w, isMatch, isSelected)
	local addr = tostring(w.address or "")
	local label = tostring(w.title ~= "" and w.title or w.class or addr)
	if #label > 28 then
		label = string.sub(label, 1, 27) .. "…"
	end
	return ui.row({ gap = 4, align = "center" }, {
		ui.dragSource({
			dragType = "nandoroid-window",
			payload = addr,
			previewAncestor = 1,
		}, {
			ui.button({
				text = label,
				variant = isSelected and "primary" or "default",
				controlSize = "sm",
				onClick = function()
					focusWindow(addr)
				end,
				onRightClick = function()
					closeWindow(addr)
				end,
			}),
		}),
		ui.button({
			glyph = "move",
			variant = "ghost",
			controlSize = "sm",
			tooltip = noctalia.tr("overview.move_window"),
			selected = moveAddr == addr,
			onClick = function()
				if moveAddr == addr then
					cancelMove()
				else
					armMove(addr)
				end
			end,
		}),
	})
end

local function workspaceCell(wsId, isActive)
	local cellWindows = windowsForWs(wsId)
	local header = ui.row({ gap = 6, align = "center", justify = "space_between" }, {
		ui.label({ text = tostring(wsId), fontWeight = "bold", color = isActive and "primary" or "on_surface" }),
		ui.label({ text = tostring(#cellWindows), fontSize = 11, color = "on_surface" }),
	})
	local body = {}
	if showThumbnails then
		local dir = noctalia.pluginDataDir()
		local snap = (dir ~= nil) and (dir .. "/overview-snapshot.png") or ""
		if snap ~= "" and noctalia.fileExists(snap) then
			table.insert(body, ui.image({ path = snap, height = 64, fit = "cover", radius = 6 }))
		end
	end
	if searchQuery ~= "" then
		-- In search mode each cell only shows its matches.
		local q = string.lower(searchQuery)
		for _, w in ipairs(cellWindows) do
			local title = string.lower(tostring(w.title or ""))
			local cls = string.lower(tostring(w.class or ""))
			if fuzzyMatch(q, title) or fuzzyMatch(q, cls) then
				table.insert(body, windowChip(w, true, false))
			end
		end
	else
		for i = 1, math.min(#cellWindows, 4) do
			table.insert(body, windowChip(cellWindows[i], false, false))
		end
		if #cellWindows > 4 then
			table.insert(body, ui.label({ text = "+" .. tostring(#cellWindows - 4), fontSize = 11 }))
		end
	end
	if showWallpaper then
		local out = noctalia.focusedOutputName()
		local wp = nil
		if out ~= nil then
			wp = noctalia.wallpaperPath(out)
		end
		if type(wp) == "string" and wp ~= "" and noctalia.fileExists(wp) then
			table.insert(body, ui.image({ path = wp, height = 40, fit = "cover", radius = 6 }))
		end
	end
	local inner = ui.column({ gap = 4 }, body)
	if #body == 0 then
		inner = ui.label({ text = noctalia.tr("overview.empty"), fontSize = 11 })
	end
	return ui.dropZone({
		accepts = { "nandoroid-window" },
		value = "ws:" .. tostring(wsId),
		onDrop = "onDropMove",
	}, {
		ui.box({
			fill = isActive and "primary/0.25" or "surface_variant/0.5",
			border = isActive and "primary" or nil,
			borderWidth = isActive and 2 or 0,
			radius = 8,
			onClick = function()
				gotoWorkspace(wsId)
			end,
		}, {
			ui.column({ gap = 4, padding = 8 }, { header, inner }),
		}),
	})
end

function render()
	loadPanelConfig()
	local shown = rows * columns
	local group = workspaceGroup()
	local gridRows = {}
	for r = 0, rows - 1 do
		local cells = {}
		for c = 0, columns - 1 do
			local id = group * shown + r * columns + c + 1
			local isActive = type(activeWs) == "table" and activeWs.id == id
			table.insert(cells, workspaceCell(id, isActive))
		end
		table.insert(gridRows, ui.row({ gap = 8 }, cells))
	end
	local m = matchingWindows()
	local matchLine = ""
	if searchQuery ~= "" then
		if #m > 0 then
			matchLine = tostring(math.min(selectedMatch, #m)) .. "/" .. tostring(#m)
		else
			matchLine = "0"
		end
	end
	local hintRow = nil
	if moveAddr ~= nil then
		hintRow = ui.row({ gap = 8, align = "center" }, {
			ui.label({ text = noctalia.tr("overview.move_hint"), color = "primary" }),
			ui.button({ text = noctalia.tr("overview.cancel"), variant = "ghost", controlSize = "sm", onClick = "cancelMove" }),
		})
	end
	local errNode = nil
	if not hyprAvailable or lastError ~= "" then
		errNode = ui.label({ text = lastError ~= "" and lastError or "hyprctl unavailable", color = "#ff8a80" })
	end
	local top = {
		ui.row({ gap = 8, align = "center" }, {
			ui.input({
				value = searchQuery,
				placeholder = noctalia.tr("overview.search_placeholder"),
				focus = true,
				submitOnEnter = true,
				onChange = "onSearchChange",
				onSubmit = "onSearchSubmit",
			}),
			ui.label({ text = matchLine, fontSize = 12 }),
			ui.button({ text = noctalia.tr("overview.refresh"), variant = "ghost", controlSize = "sm", onClick = "refreshSnapshot" }),
			ui.button({ glyph = "close", variant = "ghost", controlSize = "sm", onClick = "closeMe" }),
		}),
	}
	if errNode ~= nil then
		table.insert(top, errNode)
	end
	if hintRow ~= nil then
		table.insert(top, hintRow)
	end
	table.insert(top, ui.scroll({ fill = true }, gridRows))
	panel.render(ui.column({ gap = 12, padding = 16 }, top))
end

function closeMe()
	panel.close()
end

function onOpen(_context)
	loadPanelConfig()
	searchQuery = ""
	selectedMatch = 1
	moveAddr = nil
	workspaces = noctalia.state.get("workspaces") or {}
	windows = noctalia.state.get("windows") or {}
	monitors = noctalia.state.get("monitors") or {}
	activeWs = noctalia.state.get("active_workspace")
	hyprAvailable = noctalia.state.get("hypr_available")
	if hyprAvailable == nil then
		hyprAvailable = true
	end
	lastError = noctalia.state.get("last_error") or ""
	render()
	if showThumbnails then
		refreshSnapshot()
	end
end

function onClose() end

function update()
	render()
end

noctalia.state.watch("windows", function(v)
	windows = v or {}
	render()
end)
noctalia.state.watch("workspaces", function(v)
	workspaces = v or {}
	render()
end)
noctalia.state.watch("monitors", function(v)
	monitors = v or {}
	render()
end)
noctalia.state.watch("active_workspace", function(v)
	activeWs = v
	render()
end)
noctalia.state.watch("hypr_available", function(v)
	hyprAvailable = v ~= false
	render()
end)
noctalia.state.watch("last_error", function(v)
	lastError = v or ""
	render()
end)
