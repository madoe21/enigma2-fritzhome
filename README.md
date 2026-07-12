# FritzHome – Enigma2 Plugin

[![Built with aiflow](https://img.shields.io/badge/built%20with-aiflow-6b46c1)](https://github.com/cyber93de/aiflow)

Fritz!Box Smart Home monitor and control plugin for Enigma2. Shows all
FRITZ!DECT smart home devices with temperature, humidity, switch state and
power readings. Supports controlling sockets and adjusting thermostat target
temperatures directly from the remote. Uses the AVM AHA HTTP API.

---

## Features

| Button | Action |
|--------|--------|
| **Red** | Close / Back |
| **Green** | Refresh device list |
| **Yellow** | Open Settings |
| **Blue** | Open Information screen |
| **OK** | Open device detail / control view |

### Supported device types
- Switchable sockets (on/off + power reading)
- Thermostats / FRITZ!DECT 301 (temperature + target setpoint)
- Temperature & humidity sensors
- Dimmable lights
- Roller shutters / blinds

---

## Requirements

- AVM Fritz!Box with FRITZ!DECT smart home devices
- Fritz!Box user account with smart home access

---

## Build & deploy

```bash
# 1. Copy .env.example to .env and enter your box credentials
cp .env.example .env

# 2. Build the .ipk package
make build

# 3. Build, upload and install on the box (also pushes Fritz!Box credentials)
make install

# 4. Restart Enigma2
make restart

# 5. Or do all three steps at once
make deploy
```

The package is placed in `build/enigma2-plugin-extensions-fritzhome_1.0.0_all.ipk`.

---

## Settings / .env variables

| Variable | Description |
|----------|-------------|
| `BOX_HOST` | Enigma2 box IP or hostname |
| `BOX_USER` | SSH user (usually `root`) |
| `BOX_PORT` | SSH port (default `22`) |
| `FRITZ_HOST` | Fritz!Box hostname (default `fritz.box`) |
| `FRITZ_PORT` | Fritz!Box HTTP port (default `80`) |
| `FRITZ_USER` | Fritz!Box user |
| `FRITZ_PASSWORD` | Fritz!Box password |

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Found a bug or have a suggestion for improvement? Please create an issue or pull request.

I appreciate everyone who supports me and the project! For any requests and suggestions, feel free to provide feedback.

<p>
  <a href="https://www.buymeacoffee.com/madoe21">
    <img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" height="50" alt="Buy Me a Coffee">
  </a>

  <a href="https://ko-fi.com/madoe21">
    <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="50" alt="Ko-fi">
  </a>

  <a href="https://paypal.me/MartinD809">
    <img src="https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_111x69.jpg" height="50" alt="PayPal">
  </a>
</p>

---

## Built with aiflow

This project was built with support from **[aiflow](https://cyber93de.github.io/aiflow/)** — *built with aiflow*.
