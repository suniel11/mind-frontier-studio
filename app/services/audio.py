import math
import random
import re
import struct
import subprocess
import wave
from pathlib import Path
from typing import Callable

import imageio_ffmpeg

from app.config import MUSIC_ENABLED, MUSIC_TRACK, MUSIC_VOLUME
from app.services.subprocess_utils import run_cancellable

SUPPORTED_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def _run(
    command: list[str],
    error_message: str,
    *,
    cancellation_check: Callable[[], bool] | None = None,
) -> None:
    completed = run_cancellable(command, cancellation_check=cancellation_check)
    if completed.returncode != 0:
        raise RuntimeError(f"{error_message}: {completed.stderr[-2200:]}")


def probe_duration(ffmpeg: str, audio_path: Path) -> float:
    completed = subprocess.run(
        [ffmpeg, "-i", str(audio_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(
        r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)",
        completed.stderr,
    )
    if not match:
        raise RuntimeError(f"Could not determine audio duration for {audio_path.name}.")

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


# Back-compat alias for the previous private name.
_probe_duration = probe_duration


def _find_music_track(project_dir: Path) -> Path | None:
    if MUSIC_TRACK:
        configured = Path(MUSIC_TRACK).expanduser()
        if not configured.is_absolute():
            configured = Path.cwd() / configured
        if not configured.exists():
            raise FileNotFoundError(f"Configured MUSIC_TRACK does not exist: {configured}")
        return configured

    search_dirs = [
        project_dir / "music",
        project_dir.parent / "assets" / "music",
        Path.cwd() / "assets" / "music",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        tracks = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS
        )
        if tracks:
            return tracks[0]
    return None


def _generate_ambient_bed(output_path: Path, duration: float) -> Path:
    sample_rate = 22050
    channels = 2
    amplitude = 32767
    total_frames = max(1, int((duration + 0.5) * sample_rate))
    randomizer = random.Random(41)

    frequencies = (73.42, 110.0, 146.83, 220.0)
    phases = [randomizer.random() * math.tau for _ in frequencies]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as audio_file:
        audio_file.setnchannels(channels)
        audio_file.setsampwidth(2)
        audio_file.setframerate(sample_rate)

        buffer = bytearray()
        for frame in range(total_frames):
            time_value = frame / sample_rate
            swell = 0.72 + 0.28 * math.sin(math.tau * time_value / 11.0)
            shimmer = 0.5 + 0.5 * math.sin(math.tau * time_value / 17.0)

            tone = (
                0.48 * math.sin(math.tau * frequencies[0] * time_value + phases[0])
                + 0.27 * math.sin(math.tau * frequencies[1] * time_value + phases[1])
                + 0.17 * math.sin(math.tau * frequencies[2] * time_value + phases[2])
                + 0.08 * shimmer * math.sin(
                    math.tau * frequencies[3] * time_value + phases[3]
                )
            )
            sample = int(amplitude * 0.18 * swell * tone)
            sample = max(-amplitude, min(amplitude, sample))
            packed = struct.pack("<h", sample)
            buffer.extend(packed)
            buffer.extend(packed)

            if len(buffer) >= 65536:
                audio_file.writeframesraw(buffer)
                buffer.clear()

        if buffer:
            audio_file.writeframesraw(buffer)

    return output_path


def master_audio(
    narration_path: Path,
    output_path: Path,
    project_dir: Path,
    music_enabled: bool | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> Path:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    duration = _probe_duration(ffmpeg, narration_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # An explicit per-project preference overrides the global config default.
    effective_music_enabled = MUSIC_ENABLED if music_enabled is None else music_enabled

    if not effective_music_enabled:
        command = [
            ffmpeg,
            "-y",
            "-i", str(narration_path),
            "-af", "highpass=f=70,lowpass=f=15500,loudnorm=I=-16:TP=-1.5:LRA=7,alimiter=limit=0.95",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]
        _run(command, "Narration mastering failed", cancellation_check=cancellation_check)
        return output_path

    music_path = _find_music_track(project_dir)
    if music_path is None:
        music_path = _generate_ambient_bed(
            output_path.parent / "generated-ambient-bed.wav",
            duration,
        )

    fade_out_start = max(0.0, duration - 1.6)
    filter_graph = (
        f"[0:a]atrim=0:{duration:.3f},asetpts=N/SR/TB,"
        f"aresample=48000,volume={MUSIC_VOLUME:.3f},"
        f"afade=t=in:st=0:d=1.2,"
        f"afade=t=out:st={fade_out_start:.3f}:d=1.6[music];"
        "[1:a]aresample=48000,highpass=f=70,lowpass=f=15500,"
        "loudnorm=I=-14:TP=-1.0:LRA=6,"
        "volume=1.8,asplit=2[voice_mix][voice_sidechain];"
        "[music][voice_sidechain]sidechaincompress="
        "threshold=0.04:ratio=8:attack=20:release=350[ducked];"
        "[voice_mix][ducked]amix="
        "inputs=2:duration=first:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95[mix]"
    )

    command = [
        ffmpeg,
        "-y",
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-i", str(narration_path),
        "-filter_complex", filter_graph,
        "-map", "[mix]",
        "-t", f"{duration:.3f}",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ]
    _run(command, "Audio mixing and mastering failed", cancellation_check=cancellation_check)
    return output_path

