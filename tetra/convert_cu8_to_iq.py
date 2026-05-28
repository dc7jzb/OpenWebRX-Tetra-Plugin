#!/usr/bin/env python3
"""cu8 (RTL native) → complex64 @ 36k z decymacją i estymacją carrier offset.

RTL @ 240kS/s → decimate by 240/36 = 20/3 (arbitrary, scipy resample_poly)
Estymuje carrier offset z FFT (peak power center) i raportuje go.
"""
import sys, numpy as np
from scipy.signal import resample_poly

src = sys.argv[1]
dst = sys.argv[2]
src_rate = int(sys.argv[3]) if len(sys.argv) > 3 else 240000
dst_rate = 36000

print(f"loading {src}...")
raw = np.fromfile(src, dtype=np.uint8)
n_complex = len(raw) // 2
print(f"  {n_complex} complex samples @ {src_rate}Hz = {n_complex/src_rate:.2f}s")

# cu8 → complex float32, normalize (val - 127.5) / 127.5
iq = (raw.astype(np.float32) - 127.5) / 127.5
iq_c = iq[0::2] + 1j * iq[1::2]

# Estymacja carrier offsetu (FFT, peak detection w okolicy DC ± 50kHz)
print("estymacja carrier offset (FFT)...")
N = min(len(iq_c), 1 << 20)  # 1M punktów
spec = np.fft.fftshift(np.abs(np.fft.fft(iq_c[:N] * np.hanning(N))))
freqs = np.fft.fftshift(np.fft.fftfreq(N, 1.0 / src_rate))
# wygładź — szukamy maksimum w okolicy ±50kHz
mask = np.abs(freqs) < 50000
peak_idx = np.argmax(spec[mask])
peak_freq = freqs[mask][peak_idx]
peak_power_dB = 20 * np.log10(spec[mask][peak_idx] / spec.max() + 1e-9)
median_dB = 20 * np.log10(np.median(spec[mask]) / spec.max() + 1e-9)
print(f"  estymowany carrier offset: {peak_freq:+.0f} Hz")
print(f"  peak rel: {peak_power_dB:+.1f} dB, median rel: {median_dB:+.1f} dB, snr~{peak_power_dB-median_dB:.1f} dB")

# Decimate 240k → 36k = 3/20
print(f"resample {src_rate} → {dst_rate} (poly factor 3/20)...")
# scipy resample_poly(up, down) — chcemy fr*3/20
# 240 * 3 / 20 = 36 ✓
out = resample_poly(iq_c, up=3, down=20).astype(np.complex64)
print(f"  output: {len(out)} samples = {len(out)/dst_rate:.2f}s @ {dst_rate}Hz")

out.tofile(dst)
print(f"saved → {dst}")
# Carrier offset po decymacji jest taki sam (resample nie zmienia frequency)
print(f"\nUSE: python3 dmo_dnb_detect.py {dst} {int(peak_freq):d}")
