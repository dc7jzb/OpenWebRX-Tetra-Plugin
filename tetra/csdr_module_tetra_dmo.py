"""OpenWebRX+ TETRA DMO decoder module.
Author: SP8MB

Analog do csdr_module_tetra.py ale wykorzystuje tetra_dmo_decoder.py
zamiast tetra_decoder.py — Direct Mode (MS-MS) zamiast TMO.

Input: Complex float IQ samples (36 kS/s)
Output: 16-bit signed PCM audio (8 kHz, silence MVP — TCH integration TODO)
Metadata: JSON lines on stderr → meta events przez metaWriter
"""

import json
import pickle
import threading
from subprocess import Popen, PIPE

from csdr.module import PopenModule
from pycsdr.modules import Writer
from pycsdr.types import Format

import logging

logger = logging.getLogger(__name__)


class TetraDmoDecoderModule(PopenModule):
    """TETRA DMO DQPSK demodulator + DMAC/DPRES-SYNC parser + (TBD) ACELP."""

    def __init__(self, tetra_dir: str = "/opt/openwebrx-tetra"):
        self.tetra_dir = tetra_dir
        self.metaWriter = None
        self.metaThread = None
        super().__init__()

    def getCommand(self):
        return ["python3", "-u", f"{self.tetra_dir}/tetra_dmo_decoder.py"]

    def getInputFormat(self) -> Format:
        return Format.COMPLEX_FLOAT

    def getOutputFormat(self) -> Format:
        return Format.SHORT

    def _getProcess(self):
        return Popen(self.getCommand(), stdin=PIPE, stdout=PIPE, stderr=PIPE)

    def start(self):
        self.process = self._getProcess()
        self.reader.resume()

        threading.Thread(
            target=self.pump(self.reader.read, self.process.stdin.write),
            daemon=True
        ).start()

        from functools import partial
        threading.Thread(
            target=self.pump(partial(self.process.stdout.read1, 1024), self.writer.write),
            daemon=True
        ).start()

        self.metaThread = threading.Thread(target=self._readMeta, daemon=True)
        self.metaThread.start()

    def _readMeta(self):
        try:
            for line in self.process.stderr:
                if self.metaWriter is None:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    meta = json.loads(line)
                    self.metaWriter.write(pickle.dumps(meta))
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug("TETRA DMO meta parse error: %s", e)
        except (ValueError, OSError):
            pass

    def setMetaWriter(self, writer: Writer) -> None:
        self.metaWriter = writer

    def stop(self):
        super().stop()
