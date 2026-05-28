# SDR Calibration — PPM Offsets

## SDRplay RSP1 on brzoza@192.168.12.22 (User PC)

**PPM = +2.31** (potwierdzone na 2 nagraniach niezależnie: carrier offset +1 kHz na 433.400 i 438.375 MHz, data: 2026-05-26)

### Expected carrier offset on TETRA frequencies (Hz)

| Frequency (MHz) | Offset (Hz) |
|---|---|
| 380 | +878 |
| 410 | +947 |
| 433.400 | +1001 |
| 433.450 | +1001 |
| 433.500 | +1001 |
| 438.375 | +1013 |
| 440 | +1016 |
| 460 | +1063 |

Wartości obliczone jako `freq_hz × ppm × 1e-6`.

### Użycie

Dla OWRX+ z TETRA plugin na hoście używającym tego SDRplay:

```bash
echo "1000" > /opt/openwebrx-tetra/offset.txt
```

Lub przez env var:

```bash
export TETRA_OFFSET_HZ=1000
```

Wartość ~1000 Hz pasuje do całego pasma 380-470 MHz (PPM offset jest ~1 kHz w
tym zakresie z dokładnością ~13 Hz, co mieści się w FLL capture range ±25 kHz).

### RTL-SDR Blog V4 na 192.168.11.22 (wskaźnik TCXO)

**PPM = -16.89** (sesja 2026-05-28 wieczór, 50 dB SNR, 0% clip)

Pomiar: rtl_sdr -f 438375000 -s 240000 -g 30 -n 1200000, 5 sek na carrier
TETRA BS @ 438.375 MHz, peak -7403 Hz.

| Frequency (MHz) | Offset (Hz) |
|---|---|
| 380 | -6417 |
| 410 | -6924 |
| 433.400 | -7319 |
| 433.450 | -7319 |
| 438.375 | -7403 |
| 460 | -7768 |

Uwaga: -16.89 ppm to dużo dla TCXO (typowo ±1-2 ppm). Możliwe że klon RTL V4
ma zwykły XO mimo deklaracji TCXO. Niezależnie — PPM stabilny, wiarygodny do
użycia.

Dla OWRX z tym RTL:
```bash
echo "-7319" > /opt/openwebrx-tetra/offset.txt   # dla 433.400
# lub w OWRX settings: rtlsdr.ppm=-17
```

Wcześniejszy pomiar tej sesji RTL ("oryginalny") wykazał PPM=-74 — to był
inny exemplar lub klops. RTL V4 z TCXO znacznie bliżej standardu.

### SDRplay RSP1 na 192.168.11.22 — niezkalibrowane

W sesji 2026-05-28 próbowano kalibrować SDRplay przez libmirisdr na 438.375 MHz:
- Driver mirisdr SIGSEGV po ~25-50 ms streamingu (przerywa nagranie)
- Z częściowych danych: spectrum zanieczyszczone artefaktami (peaki ±3 kHz
  symetryczne to harmonic szyny zasilania / crystal mirisdr, NIE carrier BS)
- Dwa niezależne pomiary dały PPM +57 i +12 (różnica 19 kHz/s = niemożliwe
  dla stabilnego SDR) → driver buggy
- `|z|max=7` (vs typical 1.4 normalized) → saturation indicator
- **Wniosek**: SDRplay z mirisdr nie nadaje się do kalibracji 240-470 MHz.
  Potrzebne SDRplay native API (proprietary, install z sdrplay.com).
  Alternatywa: użyć SDRplay na 64-108 (FM broadcast) lub 470-960 (DVB-T).

### Notatki

- Memory `[[ppm-sdrplay-12-22]]` ma timestamp 2026-05-26 — drift termiczny
  może być, sprawdzić ponownie na 438.375 BS przed produkcyjnym wpisem
- FLL bandwith ±25 kHz, czyli błąd PPM do ±60 ppm (na 433 MHz) jest tolerowany
- offset.txt zostaje stosowany przez tetra_demod.py jako pre-FLL rotator
- Dla różnych SDR per host: każdy host powinien mieć swój offset.txt
