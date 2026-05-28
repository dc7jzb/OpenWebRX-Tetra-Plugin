#!/usr/bin/env python3
"""DMO DM Normal Burst (DNB) detector — krok 4a.

Sprawdza, czy w demodulowanym bit-streamie z IQ są ramki DNB (TCH/SCH-F),
po training sequence n_bits lub p_bits (ETSI EN 300 396-2 §9.4.3.3.3).
Jeśli są — krok 4b (TCH audio path) ma sens. Jeśli nie — zostają tylko
sygnałowe DSB i krok 4 odkładamy do nagrania z prawdziwym call audio.

DNB layout (470 bitów po DQPSK pre-diff decoding, ETSI EN 300 396-2 §9.4.3.3):
   0..11   preamble (j_bits typ 1 / k_bits typ 2) — 12 bits
  12..13   phase adjustment                       —  2 bits
  14..229  scrambled BLK1                         — 216 bits
 230..251  normal training seq (n_bits / p_bits)  —  22 bits  ← tu szukamy
 252..467  scrambled BLK2                         — 216 bits
 468..469  tail                                   —   2 bits

Usage: python3 dmo_dnb_detect.py <iq_file> [offset_hz]
"""
import sys, math, time, cmath
import numpy as np

# Training sequences z ETSI EN 300 396-2 §9.4.3.3.3 (zgodne z osmo-tetra-dmo)
N_BITS = np.array([1,1, 0,1, 0,0, 0,0, 1,1, 1,0, 1,0, 0,1, 1,1, 0,1, 0,0], dtype=np.int8)
P_BITS = np.array([0,1, 1,1, 1,0, 1,0, 0,1, 0,0, 0,0, 1,1, 0,1, 1,1, 1,0], dtype=np.int8)
# DSB sync training — tylko referencja, do odsiania
Y_BITS = np.array([1,1, 0,0, 0,0, 0,1, 1,0, 0,1, 1,1, 0,0, 1,1, 1,0, 1,0,
                   0,1, 1,1, 0,0, 0,0, 0,1, 1,0, 0,1, 1,1], dtype=np.int8)

DNB_TOTAL_BITS = 470
TRAIN_OFFSET_IN_DNB = 230


def demodulate(iq_path, offset_hz, seconds):
    """Re-use the same chain as dmo_burst_extract.demodulate."""
    from gnuradio import gr, blocks, analog, digital
    from gnuradio.filter import firdes

    class Tb(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            sps = 2
            nfilts = 32
            constel = digital.constellation_dqpsk().base()
            constel.gen_soft_dec_lut(8)
            algo = digital.adaptive_algorithm_cma(constel, 10e-3, 1).base()
            rrc = firdes.root_raised_cosine(nfilts, nfilts, 1.0/sps, 0.35, 11*sps*nfilts)
            self.src = blocks.file_source(gr.sizeof_gr_complex, iq_path, False)
            self.throt = blocks.throttle(gr.sizeof_gr_complex, 36000)
            self.rot = blocks.rotator_cc(-2*math.pi*offset_hz/36000.0) if offset_hz else None
            self.agc = analog.feedforward_agc_cc(8, 1)
            self.fll = digital.fll_band_edge_cc(sps, 0.35, 45, cmath.pi/100.0)
            self.cs = digital.pfb_clock_sync_ccf(sps, 2*cmath.pi/100.0, rrc, nfilts, nfilts//2, 1.5, sps)
            self.eq = digital.linear_equalizer(15, sps, algo, True, [], 'corr_est')
            self.dp = digital.diff_phasor_cc()
            self.dec = digital.constellation_decoder_cb(constel)
            self.mp = digital.map_bb(constel.pre_diff_code())
            self.un = blocks.unpack_k_bits_bb(constel.bits_per_symbol())
            self.snk = blocks.vector_sink_b()
            for i in range(1, 4):
                self.connect((self.fll, i), blocks.null_sink(gr.sizeof_float))
            chain = [self.src, self.throt]
            if self.rot: chain.append(self.rot)
            chain += [self.agc, self.fll, self.cs, self.eq, self.dp, self.dec, self.mp, self.un, self.snk]
            self.connect(*chain)

    tb = Tb()
    tb.start()
    time.sleep(seconds)
    tb.stop()
    tb.wait()
    return np.array(tb.snk.data(), dtype=np.int8)


def find_pattern(bits, pattern, max_errors=2):
    """Return sliding-window positions where pattern matches with ≤max_errors hamming.
    Also tries the inverted pattern (DQPSK pre-diff polarity flip)."""
    if len(bits) < len(pattern):
        return np.array([], dtype=np.int64)
    win = np.lib.stride_tricks.sliding_window_view(bits, len(pattern))
    neg = (1 - pattern).astype(np.int8)
    d_pos = (win != pattern).sum(axis=1)
    d_neg = (win != neg).sum(axis=1)
    d_min = np.minimum(d_pos, d_neg)
    pos = np.where(d_min <= max_errors)[0]
    # debounce: at least 50 bits apart (≪ DNB length)
    keep = []
    last = -1000
    for p in pos:
        if p - last >= 50:
            keep.append(p)
            last = p
    return np.array(keep, dtype=np.int64)


def main():
    iq_path = sys.argv[1]
    offset_hz = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    seconds = 70

    sys.stderr.write(f"[1/3] demoduluje {iq_path} (offset={offset_hz} Hz)\n")
    bits = demodulate(iq_path, offset_hz, seconds)
    sec = len(bits) / 36000.0
    sys.stderr.write(f"      {len(bits)} bitów ({sec:.1f} s)\n")

    sys.stderr.write(f"[2/3] szukam DNB training sequences\n")
    n_pos = find_pattern(bits, N_BITS, max_errors=2)
    p_pos = find_pattern(bits, P_BITS, max_errors=2)
    y_pos = find_pattern(bits, Y_BITS, max_errors=4)
    sys.stderr.write(f"      n_bits (DNB typ 1, TCH/SCH-F):   {len(n_pos):3d}  ({len(n_pos)/sec:.2f}/s)\n")
    sys.stderr.write(f"      p_bits (DNB typ 2, STCH+TCH):    {len(p_pos):3d}  ({len(p_pos)/sec:.2f}/s)\n")
    sys.stderr.write(f"      y_bits (DSB, dla porównania):    {len(y_pos):3d}  ({len(y_pos)/sec:.2f}/s)\n")

    sys.stderr.write(f"[3/3] analiza odstępów\n")
    for name, pos in [("n_bits", n_pos), ("p_bits", p_pos)]:
        if len(pos) > 1:
            gaps_ms = np.diff(pos) / 36.0
            sys.stderr.write(f"      {name}: gaps min={gaps_ms.min():.1f} median={np.median(gaps_ms):.1f} "
                            f"max={gaps_ms.max():.1f} ms\n")
            # DMO TCH gap = 56.67 ms (slot duration) lub wielokrotności
            n_slot = int(((gaps_ms >= 50) & (gaps_ms <= 65)).sum())
            n_frame = int(((gaps_ms >= 220) & (gaps_ms <= 240)).sum())
            sys.stderr.write(f"          gaps 50-65 ms (slot=56.67):  {n_slot}\n")
            sys.stderr.write(f"          gaps 220-240 ms (frame=227): {n_frame}\n")

    if len(n_pos) + len(p_pos) >= 5:
        print("DNB ramki obecne — krok 4b (TCH audio path) ma sens.")
    else:
        print("DNB ramek brak / za mało — nagranie ma chyba tylko presence (DSB).")
        print("Krok 4b odłożyć do nagrania z aktywnym DMO call.")


if __name__ == '__main__':
    main()
