"""Voice input (2026-11-03): record the microphone, show its level as a moving waveform, write it out as text.

Recording uses Windows' own wave-in API (winmm, through ctypes) - nothing to install. The recording is written out
by SenseVoice, an open speech model on this computer (sherpa-onnx, models/ in the repository), or, without it, by
Windows' own speech recognizer (System.Speech), whose accuracy is modest. Nothing is sent anywhere; the composer puts
the text in the box to be read and corrected before sending.
"""

from __future__ import annotations

import base64
import ctypes
import math
import os
import struct
import subprocess
import tempfile
import threading
import time
import wave
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

RATE = 16000
CHUNK = RATE // 20  # 50 ms per buffer: the waveform moves 20 times a second
BUFFERS = 8
MAX_SECONDS = 120


class _WaveFormat(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD)]


class _WaveHdr(ctypes.Structure):
    pass


_WaveHdr._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD),
                     ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                     ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]
WHDR_DONE = 1


def available() -> bool:
    """A microphone Windows can record from."""
    try:
        return os.name == "nt" and ctypes.windll.winmm.waveInGetNumDevs() > 0
    except OSError:
        return False


class Recorder(QObject):
    """Records 16 kHz mono 16-bit audio on a worker thread; `level` (0..1) about 20 times a second."""
    level = Signal(float)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._frames: list[bytes] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.started_at = 0.0

    def start(self) -> None:
        self._frames, self._stop = [], threading.Event()
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True, name="codedoctor-voice")
        self._thread.start()

    def stop(self) -> bytes:
        """Stop and return the recorded PCM."""
        self._stop.set()
        if self._thread:
            self._thread.join(3)
        return b"".join(self._frames)

    def _run(self) -> None:
        winmm = ctypes.windll.winmm
        fmt = _WaveFormat(1, 1, RATE, RATE * 2, 2, 16, 0)
        handle = wintypes.HANDLE()
        if winmm.waveInOpen(ctypes.byref(handle), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0) != 0:  # WAVE_MAPPER
            self.failed.emit("no_mic")
            return
        buffers = [ctypes.create_string_buffer(CHUNK * 2) for _ in range(BUFFERS)]
        headers = [_WaveHdr(ctypes.cast(b, ctypes.c_void_p), CHUNK * 2, 0, 0, 0, 0, None, 0) for b in buffers]
        size = ctypes.sizeof(_WaveHdr)
        try:
            for h in headers:
                winmm.waveInPrepareHeader(handle, ctypes.byref(h), size)
                winmm.waveInAddBuffer(handle, ctypes.byref(h), size)
            winmm.waveInStart(handle)
            i = 0
            while not self._stop.is_set() and time.monotonic() - self.started_at < MAX_SECONDS:
                h = headers[i]
                if not h.dwFlags & WHDR_DONE:
                    time.sleep(0.01)
                    continue
                data = ctypes.string_at(h.lpData, h.dwBytesRecorded)
                self._frames.append(data)
                self.level.emit(rms(data))
                h.dwFlags &= ~WHDR_DONE
                winmm.waveInAddBuffer(handle, ctypes.byref(h), size)
                i = (i + 1) % BUFFERS
        finally:
            winmm.waveInStop(handle)
            winmm.waveInReset(handle)
            for h in headers:
                winmm.waveInUnprepareHeader(handle, ctypes.byref(h), size)
            winmm.waveInClose(handle)


def rms(pcm: bytes) -> float:
    """Loudness 0..1 of 16-bit PCM, on a speech-friendly curve (quiet room ~0.05, normal voice ~0.5)."""
    n = len(pcm) // 2
    if not n:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    value = math.sqrt(sum(s * s for s in samples[::4]) / max(1, len(samples[::4]))) / 32768
    return max(0.0, min(1.0, (20 * math.log10(value + 1e-6) + 55) / 40))  # -55 dB .. -15 dB -> 0..1


def write_wav(pcm: bytes, path: str) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)


CULTURES = {"zh": "zh-CN", "zh-TW": "zh-TW", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR", "fr": "fr-FR", "es": "es-ES", "de": "de-DE",
            "pt": "pt-BR", "ru": "ru-RU", "it": "it-IT"}

_SCRIPT = r"""
param([string]$Wav, [string]$Culture)
Add-Type -AssemblyName System.Speech
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$installed = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
$info = $installed | Where-Object { $_.Culture.Name -eq $Culture } | Select-Object -First 1
if ($null -eq $info) { $info = $installed | Where-Object { $_.Culture.TwoLetterISOLanguageName -eq $Culture.Substring(0,2) } | Select-Object -First 1 }
if ($null -eq $info) { $info = $installed | Select-Object -First 1 }
if ($null -eq $info) { [Console]::Out.WriteLine("ERROR=no recognizer"); exit 2 }
$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine($info)
$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$rec.SetInputToWaveFile($Wav)
$global:cdText = New-Object System.Collections.ArrayList
$global:cdDone = $false
Register-ObjectEvent -InputObject $rec -EventName SpeechRecognized -Action { [void]$global:cdText.Add($EventArgs.Result.Text) } | Out-Null
Register-ObjectEvent -InputObject $rec -EventName RecognizeCompleted -Action { $global:cdDone = $true } | Out-Null
$rec.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
$deadline = (Get-Date).AddSeconds(90)
while (-not $global:cdDone -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 50 }
[Console]::Out.WriteLine("TEXT=" + ($global:cdText -join ''))
"""


# SenseVoice (2026-11-10): Windows' recognizer heard "帮我做出来" as "播出来电着". An open speech model on this computer
# (k2-fsa's sherpa-onnx with SenseVoice, int8, about 230 MB in the repository's models/ folder) writes Chinese, English,
# Cantonese, Japanese and Korean, with punctuation, in about a second a sentence; nothing is sent anywhere. It finds the
# language by itself (Chinese is often mixed with English words). Without the model, Windows' recognizer still works.
_sense = None
_sense_lock = threading.Lock()


def sense_voice_dir() -> str | None:
    """The SenseVoice model folder: CODEDOCTOR_ASR, else the newest models/sherpa-onnx-sense-voice-* in the repository."""
    import glob
    from pathlib import Path

    folder = os.environ.get("CODEDOCTOR_ASR")
    if folder and os.path.isfile(os.path.join(folder, "tokens.txt")):
        return folder
    found = sorted(glob.glob(str(Path(__file__).resolve().parents[3] / "models" / "sherpa-onnx-sense-voice-*")))
    return next((f for f in reversed(found) if os.path.isfile(os.path.join(f, "tokens.txt"))), None)


def sense_voice_ready() -> bool:
    if not sense_voice_dir():
        return False
    try:
        import sherpa_onnx  # noqa: F401
    except ImportError:
        return False
    return True


def _recognizer():
    """Loaded once (a few seconds), then kept."""
    global _sense
    with _sense_lock:
        if _sense is None:
            import sherpa_onnx

            folder = sense_voice_dir()
            model = os.path.join(folder, "model.int8.onnx")
            if not os.path.isfile(model):
                model = os.path.join(folder, "model.onnx")
            _sense = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=model, tokens=os.path.join(folder, "tokens.txt"),
                                                                    language="auto", use_itn=True, num_threads=2)
        return _sense


def warm() -> None:
    """Load the model while the person is still speaking, so the words come right after they stop."""
    def load():
        try:
            _recognizer()
        except Exception:  # said when transcribing, which falls back to Windows' recognizer
            pass
    if _sense is None and sense_voice_ready():
        threading.Thread(target=load, daemon=True, name="voice-model").start()


def _sense_voice(pcm: bytes) -> str:
    import array

    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    rec = _recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(RATE, [s / 32768 for s in samples])
    rec.decode_stream(stream)
    return stream.result.text.strip()


def transcribe(pcm: bytes, language: str = "zh") -> str:
    """The recording as text ("" when nothing was said): SenseVoice when its model is here, else Windows' speech
    recognizer for `language`. Blocking: run it on a worker thread. RuntimeError with the reason when it cannot."""
    if len(pcm) < RATE * 2 * 0.3:  # under 0.3 s: nothing said
        return ""
    if sense_voice_ready():
        try:
            return _sense_voice(pcm)
        except Exception:  # a broken model file: the old way still answers
            pass
    if os.name != "nt":  # the fallback below is Windows' own recognizer: elsewhere only the SenseVoice model answers
        raise RuntimeError("这台电脑上语音输入需要 SenseVoice 模型（还没有装好）。")
    return _windows(pcm, language)


def _windows(pcm: bytes, language: str = "zh") -> str:
    """Windows' own recognizer (System.Speech)."""
    folder = tempfile.mkdtemp(prefix="cd-voice-")
    path = os.path.join(folder, "voice.wav")
    write_wav(pcm, path)
    script = f"& {{ {_SCRIPT} }} -Wav '{path.replace(chr(39), chr(39) * 2)}' -Culture '{CULTURES.get(language, 'zh-CN')}'"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                              "-EncodedCommand", encoded], capture_output=True, timeout=120,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"{type(e).__name__}: {e}") from None
    finally:
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass
    text = out.stdout.decode("utf-8", "replace")
    for line in text.splitlines():
        if line.startswith("TEXT="):
            return line[5:].strip()
        if line.startswith("ERROR="):
            raise RuntimeError(line[6:])
    raise RuntimeError((out.stderr.decode("utf-8", "replace") or text or "no answer").strip()[-300:])
