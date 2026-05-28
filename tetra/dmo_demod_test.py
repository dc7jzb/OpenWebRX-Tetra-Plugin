#!/usr/bin/env python3
"""Test różnych konfiguracji demodulatora GNU Radio na próbce DMO TETRA.

Cel: znaleźć minimum bloków GR które zsynchronizują się na słabym/krótkim
sygnale DMO z handheld. Standardowy pipeline (z linear_equalizer CMA + FLL +
pfb_clock_sync) nie syncuje na v9/v10.

Warianty testowane:
  A: bez equalizera (FLL + clock_sync + diff_phasor)
  B: bez clock_sync (decimacja 2:1 brute)
  C: z Costas loop (PLL) zamiast FLL
  D: prosty pipeline (just diff_phasor on raw IQ)

Run: python3 dmo_demod_test.py <iq_36k_file>
Wyjście: dla każdego wariantu policzy hits y_bits/n_bits/p_bits.
"""
import sys, math, time, cmath
import numpy as np

sys.path.insert(0, '.')

Y_BITS = np.array([1,1, 0,0, 0,0, 0,1, 1,0, 0,1, 1,1, 0,0, 1,1, 1,0, 1,0,
                   0,1, 1,1, 0,0, 0,0, 0,1, 1,0, 0,1, 1,1], dtype=np.int8)
N_BITS = np.array([1,1, 0,1, 0,0, 0,0, 1,1, 1,0, 1,0, 0,1, 1,1, 0,1, 0,0], dtype=np.int8)
P_BITS = np.array([0,1, 1,1, 1,0, 1,0, 0,1, 0,0, 0,0, 1,1, 0,1, 1,1, 1,0], dtype=np.int8)


def find_pattern(bits, pat, max_err=2, debounce=50):
    if len(bits) < len(pat): return 0
    win = np.lib.stride_tricks.sliding_window_view(bits, len(pat))
    neg = (1 - pat).astype(np.int8)
    d_min = np.minimum((win != pat).sum(axis=1), (win != neg).sum(axis=1))
    pos = np.where(d_min <= max_err)[0]
    keep = 0; last = -1000
    for p in pos:
        if p - last >= debounce:
            keep += 1; last = p
    return keep


def variant_full(iq_path, offset_hz):
    """A: pełny pipeline jak w dmo_burst_extract.py"""
    from gnuradio import gr, blocks, analog, digital
    from gnuradio.filter import firdes
    class Tb(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            sps = 2; nfilts = 32
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
    tb = Tb(); tb.start(); time.sleep(35); tb.stop(); tb.wait()
    return np.array(tb.snk.data(), dtype=np.int8)


def variant_no_eq(iq_path, offset_hz):
    """B: bez linear_equalizer (CMA może się rozjechać na słabym sygnale)"""
    from gnuradio import gr, blocks, analog, digital
    from gnuradio.filter import firdes
    class Tb(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            sps = 2; nfilts = 32
            constel = digital.constellation_dqpsk().base()
            constel.gen_soft_dec_lut(8)
            rrc = firdes.root_raised_cosine(nfilts, nfilts, 1.0/sps, 0.35, 11*sps*nfilts)
            self.src = blocks.file_source(gr.sizeof_gr_complex, iq_path, False)
            self.throt = blocks.throttle(gr.sizeof_gr_complex, 36000)
            self.rot = blocks.rotator_cc(-2*math.pi*offset_hz/36000.0) if offset_hz else None
            self.agc = analog.feedforward_agc_cc(8, 1)
            self.fll = digital.fll_band_edge_cc(sps, 0.35, 45, cmath.pi/100.0)
            self.cs = digital.pfb_clock_sync_ccf(sps, 2*cmath.pi/100.0, rrc, nfilts, nfilts//2, 1.5, sps)
            self.dp = digital.diff_phasor_cc()
            self.dec = digital.constellation_decoder_cb(constel)
            self.mp = digital.map_bb(constel.pre_diff_code())
            self.un = blocks.unpack_k_bits_bb(constel.bits_per_symbol())
            self.snk = blocks.vector_sink_b()
            for i in range(1, 4):
                self.connect((self.fll, i), blocks.null_sink(gr.sizeof_float))
            chain = [self.src, self.throt]
            if self.rot: chain.append(self.rot)
            chain += [self.agc, self.fll, self.cs, self.dp, self.dec, self.mp, self.un, self.snk]
            self.connect(*chain)
    tb = Tb(); tb.start(); time.sleep(35); tb.stop(); tb.wait()
    return np.array(tb.snk.data(), dtype=np.int8)


def variant_minimal(iq_path, offset_hz):
    """D: tylko rotator + AGC + diff_phasor + decimacja 2:1 brute"""
    from gnuradio import gr, blocks, analog, digital
    class Tb(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            constel = digital.constellation_dqpsk().base()
            constel.gen_soft_dec_lut(8)
            self.src = blocks.file_source(gr.sizeof_gr_complex, iq_path, False)
            self.throt = blocks.throttle(gr.sizeof_gr_complex, 36000)
            self.rot = blocks.rotator_cc(-2*math.pi*offset_hz/36000.0) if offset_hz else None
            self.agc = analog.feedforward_agc_cc(8, 1)
            self.kdec = blocks.keep_one_in_n(gr.sizeof_gr_complex, 2)  # decimacja 2:1
            self.dp = digital.diff_phasor_cc()
            self.dec = digital.constellation_decoder_cb(constel)
            self.mp = digital.map_bb(constel.pre_diff_code())
            self.un = blocks.unpack_k_bits_bb(constel.bits_per_symbol())
            self.snk = blocks.vector_sink_b()
            chain = [self.src, self.throt]
            if self.rot: chain.append(self.rot)
            chain += [self.agc, self.kdec, self.dp, self.dec, self.mp, self.un, self.snk]
            self.connect(*chain)
    tb = Tb(); tb.start(); time.sleep(35); tb.stop(); tb.wait()
    return np.array(tb.snk.data(), dtype=np.int8)


def variant_fll_dp(iq_path, offset_hz):
    """C: FLL + diff_phasor (bez clock recovery, bez equalizer)"""
    from gnuradio import gr, blocks, analog, digital
    class Tb(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            sps = 2
            constel = digital.constellation_dqpsk().base()
            constel.gen_soft_dec_lut(8)
            self.src = blocks.file_source(gr.sizeof_gr_complex, iq_path, False)
            self.throt = blocks.throttle(gr.sizeof_gr_complex, 36000)
            self.rot = blocks.rotator_cc(-2*math.pi*offset_hz/36000.0) if offset_hz else None
            self.agc = analog.feedforward_agc_cc(8, 1)
            self.fll = digital.fll_band_edge_cc(sps, 0.35, 45, cmath.pi/100.0)
            self.kdec = blocks.keep_one_in_n(gr.sizeof_gr_complex, 2)
            self.dp = digital.diff_phasor_cc()
            self.dec = digital.constellation_decoder_cb(constel)
            self.mp = digital.map_bb(constel.pre_diff_code())
            self.un = blocks.unpack_k_bits_bb(constel.bits_per_symbol())
            self.snk = blocks.vector_sink_b()
            for i in range(1, 4):
                self.connect((self.fll, i), blocks.null_sink(gr.sizeof_float))
            chain = [self.src, self.throt]
            if self.rot: chain.append(self.rot)
            chain += [self.agc, self.fll, self.kdec, self.dp, self.dec, self.mp, self.un, self.snk]
            self.connect(*chain)
    tb = Tb(); tb.start(); time.sleep(35); tb.stop(); tb.wait()
    return np.array(tb.snk.data(), dtype=np.int8)


def evaluate(bits, label):
    rb = 30000
    y = find_pattern(bits[:rb*36] if len(bits) > rb*36 else bits, Y_BITS, max_err=4)
    n = find_pattern(bits[:rb*36] if len(bits) > rb*36 else bits, N_BITS, max_err=1)
    p = find_pattern(bits[:rb*36] if len(bits) > rb*36 else bits, P_BITS, max_err=1)
    print(f"  {label:25s}: {len(bits):8d} bits  y={y:3d}  n={n:3d}  p={p:3d}")


def main():
    iq_path = sys.argv[1]
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(f"testing {iq_path}, offset={offset}\n")
    for name, fn in [("A:full(eq)", variant_full),
                     ("B:no_eq", variant_no_eq),
                     ("C:fll_dp(no_cs)", variant_fll_dp),
                     ("D:minimal", variant_minimal)]:
        print(f"--- {name}")
        try:
            bits = fn(iq_path, offset)
            evaluate(bits, name)
        except Exception as e:
            print(f"  FAILED: {e}")


if __name__ == '__main__':
    main()
