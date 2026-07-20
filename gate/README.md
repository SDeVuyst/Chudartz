# Chudartz Gate Scanner

Fullscreen Raspberry Pi app that reads ticket QR codes from a USB keyboard-wedge scanner and checks them in against the Collectibles backend.

## How it works

1. The USB scanner types the QR payload and presses Enter.
2. The app parses `participant_id:{id}seed:{seed}`.
3. It `POST`s to `{base_url}/en/pokemon/gate/check-in/` with header `X-Gate-Api-Key`.
4. The screen turns green (welcome) or red (denied).

## Create a device API key

1. Log into the Collectibles Django admin.
2. Open **Gate devices** → **Add gate device**.
3. Enter a name (e.g. `Entrance Pi`) and save.
4. Copy the API key from the warning message — it is shown only once.
5. Deactivate a device in admin to revoke access.

## SSH-only Raspberry Pi setup

You can do the whole install over SSH. The HDMI screen is only needed at the door for feedback; configuration does not require touching the Pi UI.

### 1. Enable SSH + desktop auto-login (once, if needed)

On a fresh Pi (with keyboard/monitor or Raspberry Pi Imager options):

- Enable SSH
- Boot to desktop with auto-login (so the gate UI can start without a local login)

From SSH later you can set desktop auto-login with:

```bash
sudo raspi-config nonint do_boot_behaviour B4
```

(`B4` = Desktop autologin on Raspberry Pi OS.)

### 2. Install dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-tk git
```

### 3. Get the app

```bash
git clone <your-repo-url> ~/Chudartz
# or: scp -r gate/ pi@<pi-ip>:~/Chudartz/gate
cd ~/Chudartz/gate
```

### 4. Configure over SSH (no GUI)

Non-interactive (best for scripts):

```bash
python3 main.py --configure \
  --base-url https://chudartz-collectibles.com \
  --api-key 'PASTE_KEY_FROM_ADMIN' \
  --host-header chudartz-collectibles.com
```

Local Docker/nginx example:

```bash
python3 main.py --configure \
  --base-url http://192.168.86.200:81 \
  --api-key 'PASTE_KEY_FROM_ADMIN' \
  --host-header chudartz-collectibles.com
```

Interactive prompts:

```bash
python3 main.py --configure
```

Inspect / verify:

```bash
python3 main.py --show-config
python3 main.py --test
```

`--test` should print that the connection and API key look OK (a fake ticket id returns 400/404 after auth succeeds).

Config file: `~/.config/chudartz-gate/config.json`  
Override path with `CHUDARTZ_GATE_CONFIG=/path/to/config.json`.

### 5. Autostart on boot (from SSH)

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/chudartz-gate.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Chudartz Gate
Exec=/usr/bin/python3 /home/pi/Chudartz/gate/main.py
WorkingDirectory=/home/pi/Chudartz/gate
X-GNOME-Autostart-enabled=true
EOF
```

Adjust `/home/pi/...` if your username or path differs. Reboot:

```bash
sudo reboot
```

After reboot the desktop session should launch the fullscreen gate automatically.

### 6. Update config later over SSH

```bash
python3 ~/Chudartz/gate/main.py --configure --base-url https://chudartz-collectibles.com --api-key 'NEW_KEY'
# then restart the app, e.g.:
pkill -f 'Chudartz/gate/main.py' || true
# it will start again on next login/reboot, or start once:
DISPLAY=:0 python3 ~/Chudartz/gate/main.py &
```

## Manual / on-device settings

You can still open settings on the Pi display with **F2** or **Ctrl+,**.

| Setting | Example |
|---------|---------|
| API base URL | `https://chudartz-collectibles.com` or `http://192.168.x.x:81` |
| Host header | `chudartz-collectibles.com` (keep when using a LAN IP) |
| Device API key | key from Django admin |

## Scanner notes

- Use a USB HID keyboard-wedge QR scanner (scan = type text + Enter).
- Keep the gate window focused so key events reach the app.
- **Esc** exits fullscreen; Esc again quits.

## Deploy backend changes

Apply the `GateDevice` migration on the server that the Pi will call:

```bash
python manage.py migrate pokemon
```

Ensure the Pi can reach the host. When using a LAN IP, leave **Host header** as `chudartz-collectibles.com` so `DomainMiddleware` selects the Collectibles URLConf.
