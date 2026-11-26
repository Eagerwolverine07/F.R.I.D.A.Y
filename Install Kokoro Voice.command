#!/bin/bash
# Double-click to give F.R.I.D.A.Y her free Kokoro voice. Run "Install F.R.I.D.A.Y" first.
# It sets up a private Python just for the voice, installs Kokoro, downloads the voice model once (about 330 MB),
# starts a small helper that keeps the voice ready, plays a test sentence, and switches F.R.I.D.A.Y to it.
# A copy of this window goes to Downloads/friday-kokoro-log.txt for Claude to read.
LOG="$HOME/Downloads/friday-kokoro-log.txt"
exec > >(tee "$LOG") 2>&1
CONF="$HOME/.config/atticus"; HERE="$CONF/kokoro"; REPO="$HOME/F.R.I.D.A.Y"; AGENT="com.friday.kokoro"
PLIST="$HOME/Library/LaunchAgents/$AGENT.plist"
fail() { echo; echo "Something went wrong: $1"; echo "Tell Claude, it can read the log in Downloads."; exit 1; }
[ "$(uname -m)" = "arm64" ] || fail "Kokoro needs an Apple Silicon Mac."
[ -f "$REPO/friday_kokoro.py" ] || fail "Run Install F.R.I.D.A.Y first (it brings the voice helper)."
mkdir -p "$HERE" && chmod 700 "$CONF"

echo "Step 1 of 5: getting uv, a small tool that sets up Python…"
UV="$(command -v uv)"; [ -x "$UV" ] || UV="$HOME/.local/bin/uv"
if [ ! -x "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null || fail "couldn't download uv (check the internet)."
fi
[ -x "$UV" ] || fail "uv didn't install."

echo "Step 2 of 5: a private Python 3.12 just for the voice…"
"$UV" venv --quiet --seed --allow-existing --python 3.12 "$HERE/venv" || fail "couldn't set up Python 3.12."

echo "Step 3 of 5: installing Kokoro…"
"$UV" pip install --quiet --python "$HERE/venv/bin/python" "kokoro-mlx>=0.1.4" soundfile || fail "couldn't install Kokoro."
cp "$REPO/friday_kokoro.py" "$HERE/friday_kokoro.py"

echo "Step 4 of 5: downloading the voice model (about 330 MB, only once) and testing…"
"$HERE/venv/bin/python" "$HERE/friday_kokoro.py" --test || fail "the voice test didn't work."

echo "Step 5 of 5: starting the voice helper and switching F.R.I.D.A.Y to it…"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$AGENT</string>
  <key>ProgramArguments</key><array><string>$HERE/venv/bin/python</string><string>$HERE/friday_kokoro.py</string><string>--serve</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardErrorPath</key><string>$HERE/helper.log</string>
</dict></plist>
PLIST
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" || fail "couldn't start the voice helper."
for i in 1 2 3 4 5 6 7 8 9 10; do curl -s --max-time 1 http://127.0.0.1:3901/health >/dev/null && break; sleep 1; done
curl -s --max-time 2 http://127.0.0.1:3901/health >/dev/null || fail "the voice helper didn't start."
VOICE="af_heart"; [ -f "$CONF/kokoro.json" ] && VOICE="$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("voice","af_heart"))' "$CONF/kokoro.json" 2>/dev/null || echo af_heart)"
printf '{"on": true, "voice": "%s"}\n' "$VOICE" > "$CONF/kokoro.json" && chmod 600 "$CONF/kokoro.json"
echo
echo "Done! F.R.I.D.A.Y now speaks with Kokoro. Try: \"Friday, what Kokoro voices do you have?\""
echo "You can close this window."
