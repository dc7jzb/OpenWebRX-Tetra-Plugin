"""OpenWebRX+ TETRA DMO demodulator chain.
Author: SP8MB

Direct Mode Operation (MS-MS) chain — równoległy do TMO Tetra chain.

TETRA DMO uses π/4-DQPSK modulation, 25 kHz channel, 18 kS/s symbol rate.
IF sample rate 36 kS/s (2 sps), audio output 8 kHz PCM (ACELP — silence MVP).
"""

from csdr.chain import Chain
from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider
from pycsdr.modules import Writer, Buffer
from pycsdr.types import Format
from owrx.meta import MetaParser

import logging

logger = logging.getLogger(__name__)


class TetraDmo(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider):
    """TETRA DMO voice + signalling demodulator chain dla OpenWebRX+."""

    def __init__(self, tetra_dir: str = '/opt/openwebrx-tetra'):
        from csdr.module.tetra_dmo import TetraDmoDecoderModule
        self.decoder = TetraDmoDecoderModule(tetra_dir)
        workers = [self.decoder]
        self.metaParser = None
        super().__init__(workers)

    def getFixedIfSampleRate(self) -> int:
        return 36000

    def getFixedAudioRate(self) -> int:
        return 8000

    def setMetaWriter(self, writer: Writer) -> None:
        if self.metaParser is None:
            self.metaParser = MetaParser()
            buffer = Buffer(Format.CHAR)
            self.decoder.setMetaWriter(buffer)
            self.metaParser.setReader(buffer.getReader())
        self.metaParser.setWriter(writer)

    def supportsSquelch(self):
        return False

    def stop(self):
        if self.metaParser is not None:
            self.metaParser.stop()
        super().stop()
