Working on a fully functional english translated Version:

---

# OpenWebRX+ TETRA Plugin

**Author: SP8MB (mbbrzoza)**

TETRA (Terrestrial Trunked Radio) decoder plugin for [OpenWebRX+](https://github.com/luarvique/openwebrx). Adds full signaling extraction, voice decoding and a real-time control panel to the OpenWebRX+ web UI.

---

## EN — English

### Description
Plugin adds a **TETRA** demodulation mode to OpenWebRX+: π/4-DQPSK demod, L1/L2/L3 decoding, ACELP voice playback and a dedicated browser panel with network, call and terminal information.

### Features
- π/4-DQPSK demodulation (GNURadio)
- TETRA protocol decoding L1/L2/L3 (osmo-tetra / tetra-rx, sq5bpf fork)
- ACELP speech decoding (ETSI codec) with in-browser playback
- AFC sourced from FLL port (radians/sample → Hz)
- Real-time web panel:
  - Network: MCC, MNC, LA, color code, DL/UL, encryption, network time
  - Active calls (setup / connect / release / TX grant)
  - GSSI / ISSI with real-ISSI vs ESI-alias classification
  - Per-timeslot state (Traffic / Control / Common-Ctrl / Reserved / Unalloc) with TTL
  - Neighbour cell list (cell_id, carrier, DL freq, load)
  - Active SSI list (5 min TTL), MS Register events (LU Accept/Reject, attach/detach, auth)
  - SDS messages with protocol & delivery-status decoding
  - Floating TTT-style window with event filters, G/SSI label editor, CSV export, remote and compact modes

### Signal chain
```
IQ (36 kS/s) → tetra_demod.py (GNURadio π/4-DQPSK)
             → tetra-rx (osmo-tetra L1/L2/L3, sq5bpf fork)
             → tetra_decoder.py (TETMON parser + ACELP codec)
             → PCM audio (stdout) + JSON metadata (stderr)
             → WebSocket → tetra_panel.js (browser panel)
```

### Installation
```bash
git clone https://github.com/mbbrzoza/OpenWebRX-Tetra-Plugin.git
cd OpenWebRX-Tetra-Plugin/tetra

# Full install (deps, build, patch OpenWebRX+, frontend)
sudo bash install.sh

# Quick update of scripts and panel (no recompile)
sudo bash install.sh --update

# Verify installation
sudo bash install.sh --check

# Uninstall (restores .bak.pre-tetra backups)
sudo bash install.sh --uninstall
```

After installation a new **TETRA** demodulation mode appears in OpenWebRX+ — set it on the SDR profile or via a bookmark.

### Requirements
- OpenWebRX+ v1.2.x
- Debian / Raspberry Pi OS (aarch64 or x86_64)
- GNURadio + osmo-tetra (installed by `install.sh`)
- Internet access for the first install

### Files
```
tetra/
  install.sh              — installer (install/update/uninstall/check, .bak.pre-tetra backups)
  tetra_decoder.py        — main decoder: pipeline orchestrator + TETMON parser + meta events
  tetra_demod.py          — DQPSK demodulator (GNURadio) with optional pre-FLL rotator
  csdr_module_tetra.py    — CSDR module (PopenModule)
  csdr_chain_tetra.py     — CSDR chain (OpenWebRX+ integration)
  tetra_panel.js          — frontend (TetraMetaPanel + TTT-style window)
  tetra_panel.html        — panel HTML template
  deploy.py               — fast redeploy of decoder + panel to RPi
  update_html_css.py      — server-side HTML/CSS update
```

### Server paths after install
- `/opt/openwebrx-tetra/` — decoder binaries, scripts, optional `offset.txt`
- `/usr/lib/python3/dist-packages/` — OpenWebRX+ integration patches (modes.py, feature.py, dsp.py, csdr/*, htdocs/*)

---

## License
Open source for amateur radio use.

73 de SP8MB
