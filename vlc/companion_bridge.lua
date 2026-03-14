-- VLC Companion Bridge
--
-- Minimal Lua extension that exposes playback state over a local TCP socket
-- for a local CLI companion process.
--
-- Install:
--   mkdir -p ~/.local/share/vlc/lua/extensions
--   cp vlc/companion_bridge.lua ~/.local/share/vlc/lua/extensions/
--
-- Usage in VLC:
--   View -> Companion Bridge
--
-- It listens on 127.0.0.1:42142 and replies with one JSON object per
-- connection. Supported requests (single line):
--   GET_STATE\n

descriptor = {
  title = "Companion Bridge",
  version = "0.1.0",
  author = "OpenAI Codex",
  shortdesc = "Companion Bridge",
  description = "Expose VLC playback state to a local movie companion CLI.",
  capabilities = { "input-listener" }
}

local socket = nil
local server = nil
local timer_handle = nil
local host = "127.0.0.1"
local port = 42142
local last_error = nil

local function escape_json(value)
  if value == nil then return "" end
  value = tostring(value)
  value = string.gsub(value, "\\", "\\\\")
  value = string.gsub(value, '"', '\\"')
  value = string.gsub(value, "\n", "\\n")
  value = string.gsub(value, "\r", "\\r")
  value = string.gsub(value, "\t", "\\t")
  return value
end

local function status_message(message)
  if dlg then
    status_label:set_text(message)
  end
  vlc.msg.info("[companion-bridge] " .. message)
end

local function get_input_item()
  local input = vlc.object.input()
  if not input then return nil end
  return vlc.input.item()
end

local function current_state()
  local input = vlc.object.input()
  local item = get_input_item()
  local state = {
    active = input ~= nil,
    playing = false,
    paused = false,
    state = "stopped",
    title = "",
    uri = "",
    position = 0,
    length = 0,
    timestamp = 0,
    rate = 1.0,
    volume = -1,
    error = last_error
  }

  if item then
    state.title = item:name() or ""
    state.uri = item:uri() or ""
  end

  if input then
    local s = vlc.var.get(input, "state")
    local time = vlc.var.get(input, "time") or 0
    local length = vlc.var.get(input, "length") or 0
    local position = vlc.var.get(input, "position") or 0
    local rate = vlc.var.get(input, "rate") or 1.0
    local audio_volume = vlc.volume.get()

    state.timestamp = time
    state.length = length
    state.position = position
    state.rate = rate
    state.volume = audio_volume

    if s == 3 then
      state.state = "playing"
      state.playing = true
    elseif s == 4 then
      state.state = "paused"
      state.paused = true
    elseif s == 5 then
      state.state = "stopped"
    else
      state.state = tostring(s)
    end
  end

  return state
end

local function encode_state_json(state)
  return string.format(
    '{"active":%s,"playing":%s,"paused":%s,"state":"%s","title":"%s","uri":"%s","position":%.6f,"length":%d,"timestamp":%d,"rate":%.3f,"volume":%d,"error":%s}',
    tostring(state.active),
    tostring(state.playing),
    tostring(state.paused),
    escape_json(state.state),
    escape_json(state.title),
    escape_json(state.uri),
    tonumber(state.position) or 0,
    tonumber(state.length) or 0,
    tonumber(state.timestamp) or 0,
    tonumber(state.rate) or 1.0,
    tonumber(state.volume) or -1,
    state.error and ('"' .. escape_json(state.error) .. '"') or 'null'
  )
end

local function ensure_socket()
  if socket then return true end

  local ok, mod = pcall(require, "socket")
  if not ok then
    last_error = "lua-socket unavailable"
    status_message("LuaSocket unavailable; install vlc lua socket support")
    return false
  end

  socket = mod
  local tcp, err = socket.bind(host, port)
  if not tcp then
    last_error = err or "bind failed"
    status_message("Bind failed on " .. host .. ":" .. port .. " - " .. tostring(last_error))
    return false
  end

  tcp:settimeout(0)
  server = tcp
  last_error = nil
  status_message("Listening on " .. host .. ":" .. port)
  return true
end

local function close_socket()
  if server then
    pcall(function() server:close() end)
    server = nil
  end
end

local function handle_client(client)
  client:settimeout(0)
  local line = client:receive('*l')
  if line == nil or line == "" then
    line = "GET_STATE"
  end

  if line == "GET_STATE" then
    local payload = encode_state_json(current_state()) .. "\n"
    client:send(payload)
  else
    client:send('{"error":"unsupported request"}\n')
  end

  client:close()
end

local function poll_server()
  if not server then
    ensure_socket()
    return 1000
  end

  local client, err = server:accept()
  if client then
    handle_client(client)
  elseif err ~= "timeout" and err ~= "wantread" then
    last_error = err
  end

  return 250
end

function activate()
  create_dialog()
  ensure_socket()
  timer_handle = vlc.misc.timer()
  timer_handle:set(function()
    poll_server()
  end, 250, true)
end

function deactivate()
  if timer_handle then
    timer_handle:stop()
    timer_handle = nil
  end
  close_socket()
  if dlg then
    dlg:delete()
    dlg = nil
  end
end

function close()
  deactivate()
end

function input_changed()
  status_message("Input changed")
end

function meta_changed()
  status_message("Metadata changed")
end

function playing_changed()
  local state = current_state()
  status_message("Playback state: " .. state.state)
end

function create_dialog()
  dlg = vlc.dialog("Companion Bridge")
  status_label = dlg:add_label("Starting...", 1, 1, 3, 1)
  dlg:add_button("Refresh", function()
    status_message("Listening on " .. host .. ":" .. port)
  end, 1, 2, 1, 1)
  dlg:add_button("Close", function()
    deactivate()
  end, 2, 2, 1, 1)
end
