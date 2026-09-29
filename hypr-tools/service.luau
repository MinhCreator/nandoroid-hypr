-- service.luau — hypr-sync
-- Port of services/HyprlandData.qml + addon/services/KeybindsService.qml (poll side).
-- Polls `hyprctl -j` (clients/workspaces/monitors/activeworkspace) and
-- `python scripts/hypr_keybinds.py show`, publishes plain data via noctalia.state:
--   "workspaces" (array), "windows" (array), "monitors" (array),
--   "active_workspace" (table), "binds" (table {binds=..., isLua=..., overridePath=...}),
--   "hypr_available" (bool), "last_error" (string).
-- Panels watch these keys and re-render. In-memory only; nothing persisted here.

local pollMs = 1500
local pythonBin = "python3"
local fetching = false

local function cfg(key, fallback)
	local v = noctalia.getConfig(key)
	if v == nil then
		return fallback
	end
	return v
end

local function applyConfig()
	local p = cfg("poll_ms", 1500)
	if type(p) == "number" and p >= 500 then
		pollMs = p
	end
	local pb = cfg("python_bin", "python3")
	if type(pb) == "string" and pb ~= "" then
		pythonBin = pb
	end
	noctalia.setUpdateInterval(pollMs)
end

local function scriptPath(name)
	local dir = noctalia.pluginDir()
	if dir == nil then
		return "scripts/" .. name
	end
	return dir .. "/scripts/" .. name
end

-- Sequential fetch chain so one update() tick produces one coherent snapshot.
local function fetchAll()
	if fetching then
		return
	end
	if not noctalia.commandExists("hyprctl") then
		noctalia.state.set("hypr_available", false)
		noctalia.state.set("last_error", "hyprctl not found on PATH")
		return
	end
	fetching = true
	local snap = { workspaces = {}, windows = {}, monitors = {}, active = nil }

	noctalia.runAsync({ "hyprctl", "workspaces", "-j" }, function(r1)
		if r1.exitCode == 0 and r1.stdout ~= "" then
			local ok, data = pcall(noctalia.json.decode, r1.stdout)
			if ok and type(data) == "table" then
				local clean = {}
				for _, ws in ipairs(data) do
					if type(ws) == "table" and type(ws.id) == "number" and ws.id >= 1 and ws.id <= 100 then
						table.insert(clean, ws)
					end
				end
				snap.workspaces = clean
			end
		end
		noctalia.runAsync({ "hyprctl", "clients", "-j" }, function(r2)
			if r2.exitCode == 0 and r2.stdout ~= "" then
				local ok, data = pcall(noctalia.json.decode, r2.stdout)
				if ok and type(data) == "table" then
					snap.windows = data
				end
			end
			noctalia.runAsync({ "hyprctl", "monitors", "-j" }, function(r3)
				if r3.exitCode == 0 and r3.stdout ~= "" then
					local ok, data = pcall(noctalia.json.decode, r3.stdout)
					if ok and type(data) == "table" then
						snap.monitors = data
					end
				end
				noctalia.runAsync({ "hyprctl", "activeworkspace", "-j" }, function(r4)
					if r4.exitCode == 0 and r4.stdout ~= "" then
						local ok, data = pcall(noctalia.json.decode, r4.stdout)
						if ok and type(data) == "table" then
							snap.active = data
						end
					end
					noctalia.state.set("workspaces", snap.workspaces)
					noctalia.state.set("windows", snap.windows)
					noctalia.state.set("monitors", snap.monitors)
					if snap.active ~= nil then
						noctalia.state.set("active_workspace", snap.active)
					end
					noctalia.state.set("hypr_available", true)
					noctalia.state.set("last_error", "")
					-- Keybinds are slower; refresh after hypr snapshot lands.
					fetchBinds()
				end)
			end)
		end)
	end)
end

local function trim(s)
	if type(s) ~= "string" then
		return ""
	end
	return (s:match("^%s*(.-)%s*$") or "")
end

function fetchBinds()
	if not noctalia.commandExists(pythonBin) then
		noctalia.state.set("last_error", pythonBin .. " not found on PATH")
		fetching = false
		return
	end
	local args = { pythonBin, scriptPath("hypr_keybinds.py"), "show" }
	local op = trim(cfg("keybind_override", ""))
	if op ~= "" then
		table.insert(args, "--override-path")
		table.insert(args, noctalia.expandPath(op))
	end
	local cd = trim(cfg("hypr_config_dir", ""))
	if cd ~= "" then
		table.insert(args, "--config-dir")
		table.insert(args, noctalia.expandPath(cd))
	end
	noctalia.runAsync(args, function(r)
		fetching = false
		if r.exitCode ~= 0 then
			noctalia.state.set("last_error", "keybinds show failed: " .. (r.stderr or ""))
			return
		end
		local ok, data = pcall(noctalia.json.decode, r.stdout)
		if ok and type(data) == "table" then
			noctalia.state.set("binds", data)
		else
			noctalia.state.set("last_error", "keybinds JSON parse failed")
		end
	end)
end

function update()
	fetchAll()
end

function onConfigChanged()
	applyConfig()
	fetchAll()
end

applyConfig()
fetchAll()
