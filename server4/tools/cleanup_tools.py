import asyncio
import os
import time
import uuid

from mcp.server.fastmcp import FastMCP

from server4.tools.effects_tools import _params
from server4.tools.analysis_tools import _measure_wav, _temp_wav_path

_jobs: dict[str, dict] = {}
_MAX_COMPLETED_JOBS = 50
_STALE_JOB_TIMEOUT = 600
_job_lock = asyncio.Lock()


def _cleanup_stale_jobs():
    now = time.time()
    for job_id, job in list(_jobs.items()):
        if job["status"] == "running" and (now - job["started_at"]) > _STALE_JOB_TIMEOUT:
            job["status"] = "error"
            job["error"] = "Timed out after 10 minutes"
    completed = [(k, v) for k, v in _jobs.items() if v["status"] in ("complete", "error")]
    if len(completed) > _MAX_COMPLETED_JOBS:
        completed.sort(key=lambda x: x[1].get("started_at", 0))
        for k, _ in completed[:-_MAX_COMPLETED_JOBS]:
            del _jobs[k]


def _has_running_pipeline() -> bool:
    return any(j["status"] == "running" for j in _jobs.values())


async def _create_job(pipeline_name: str):
    async with _job_lock:
        _cleanup_stale_jobs()
        if _has_running_pipeline():
            return None, None
        job_id = str(uuid.uuid4())[:8]
        job = {
            "status": "running", "pipeline": pipeline_name, "current_step": "starting",
            "steps_applied": [], "steps_failed": [], "started_at": time.time(),
            "result": None, "error": None,
        }
        _jobs[job_id] = job
        return job_id, job


def _running_job_error() -> dict:
    running = next(j for j in _jobs.values() if j["status"] == "running")
    running_id = next(k for k, v in _jobs.items() if v is running)
    return {
        "error": "A pipeline is already running. Do NOT start another one.",
        "job_id": running_id, "current_step": running["current_step"],
        "message": "Use check_pipeline_status to monitor the existing pipeline.",
    }


async def _run_step(job: dict, name: str, bridge, effect_id: str, params: str):
    job["current_step"] = name
    try:
        await bridge.call("select-all", {})
        await bridge.call("apply-effect", {"effect_id": effect_id, "params": params})
        job["steps_applied"].append(name)
    except Exception as e:
        job["steps_failed"].append(f"{name}: {e}")
    await asyncio.sleep(0.5)


async def _noise_reduction_step(job: dict, bridge, sensitivity: float, noise_gain_db: float, smoothing_bands: int):
    """Noise reduction is a TWO-CALL effect. Step 1 selects a short noise-only
    region and calls it with GetProfile=1 (matches the "Get Noise Profile" button
    in Audacity's dialog, which just sets that flag and calls Process()). Step 2
    selects everything and calls it again with GetProfile=0 plus the real
    reduction params, using the profile captured in step 1."""
    job["current_step"] = "noise profile capture"
    try:
        await bridge.call("select-time", {"start": 0, "end": 0.5})
        profile_params = _params(GetProfile=True)
        await bridge.call("apply-effect", {"effect_id": "Noise reduction", "params": profile_params})
        await asyncio.sleep(1.0)

        job["current_step"] = "noise reduction"
        await bridge.call("select-all", {})
        params = _params(**{
            "Sensitivity": sensitivity, "Noise Gain": noise_gain_db,
            "Frequency Smoothing Bands": smoothing_bands, "GetProfile": False,
        })
        await bridge.call("apply-effect", {"effect_id": "Noise reduction", "params": params})
        job["steps_applied"].append(f"noise reduction {noise_gain_db}dB")
    except Exception as e:
        job["steps_failed"].append(f"noise reduction: {e}")
    await asyncio.sleep(0.5)


async def _measure_current(bridge) -> dict | None:
    tmp_wav = _temp_wav_path()
    try:
        await bridge.call("select-all", {})
        await bridge.call("export-wav", {"path": tmp_wav, "overwrite": True})
        if not os.path.exists(tmp_wav):
            return None
        return _measure_wav(tmp_wav)
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp_wav)
        except OSError:
            pass


async def _safe_loudness_step(job: dict, bridge, target: float = -16.0, mode: str = "lufs", peak_ceiling: float = -1.0):
    """Measure first; only apply loudness normalization (LUFS or RMS mode) if it
    won't clip. Falls back to peak-only reduction (never boost) if the projected
    result would exceed peak_ceiling.

    Args:
        mode: "lufs" (NormalizeTo=0, LUFSLevel) or "rms" (NormalizeTo=1, RMSLevel) -
            values confirmed against v4's source (enum kLoudness=0, kRMS=1 in
            normalizeloudnesseffect.h), not assumed from v3.
        peak_ceiling: refuse and fall back if the projected peak would exceed this.
    """
    measured = await _measure_current(bridge)
    if measured is None or measured.get("peak_db") is None:
        job["steps_applied"].append("loudness skipped (measurement failed)")
        return

    peak_before = measured["peak_db"]
    rms_before = measured.get("overall_rms_db")

    if rms_before is not None:
        estimated_gain_db = target - rms_before
        projected_peak_db = peak_before + estimated_gain_db
        if projected_peak_db <= peak_ceiling:
            await bridge.call("select-all", {})
            if mode == "rms":
                params = _params(NormalizeTo=1, StereoIndependent=False, RMSLevel=target, DualMono=True)
            else:
                params = _params(NormalizeTo=0, StereoIndependent=False, LUFSLevel=target, DualMono=True)
            try:
                await bridge.call("apply-effect", {"effect_id": "Loudness Normalization", "params": params})
                job["steps_applied"].append(f"loudness normalized to {target} {mode.upper()}")
                return
            except Exception as e:
                job["steps_failed"].append(f"loudness normalize: {e}")

    if peak_before > -3.0:
        await bridge.call("select-all", {})
        params = _params(PeakLevel=-3.0, RemoveDcOffset=False, ApplyVolume=True, StereoIndependent=False)
        try:
            await bridge.call("apply-effect", {"effect_id": "Normalize", "params": params})
            job["steps_applied"].append(f"peaks reduced to -3dB ({mode.upper()} target would have clipped)")
        except Exception as e:
            job["steps_failed"].append(f"fallback normalize: {e}")
    else:
        job["steps_applied"].append(f"peaks already at {peak_before}dB - no change needed")


async def _safe_peak_only_step(job: dict, bridge, ceiling: float = -3.0):
    """Reduce peaks only if hot, never boost - no LUFS/RMS targeting at all.
    Used for music mastering and lo-fi, where a fixed loudness target doesn't
    make sense (genre/style expectations vary too widely for one default), but
    a safety ceiling on peaks still does. Matches v3's original _loudness_step
    for these same pipelines."""
    measured = await _measure_current(bridge)
    if measured is None or measured.get("peak_db") is None:
        job["steps_applied"].append("loudness skipped (measurement failed)")
        return

    peak_before = measured["peak_db"]
    if peak_before > ceiling:
        await bridge.call("select-all", {})
        params = _params(PeakLevel=ceiling, RemoveDcOffset=False, ApplyVolume=True, StereoIndependent=False)
        try:
            await bridge.call("apply-effect", {"effect_id": "Normalize", "params": params})
            job["steps_applied"].append(f"peaks reduced to {ceiling}dB")
        except Exception as e:
            job["steps_failed"].append(f"peak safety: {e}")
    else:
        job["steps_applied"].append(f"peaks already at {peak_before}dB (below {ceiling}dB ceiling) - no change needed")


async def _cleanup_audio_pipeline(job: dict, bridge, remove_noise: bool, remove_clicks: bool):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        # NOTE: v3's equivalent pipeline also ran a high-pass filter (80Hz) here
        # to cut rumble - skipped, since a real high/low-pass filter effect is
        # confirmed absent from this fork's registry (same finding as the 11
        # other missing v3 effects - see README's Known Gaps).

        if remove_noise:
            await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=10.0, smoothing_bands=3)

        if remove_clicks:
            await _run_step(job, "click removal", bridge, "Click removal", _params(Threshold=200, Width=20))

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Audio Cleanup: {' > '.join(job['steps_applied'])}" if job["steps_applied"] else "Audio Cleanup: no steps applied",
            "loudness": "unchanged (cleanup only)",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


async def _podcast_pipeline(job: dict, bridge, remove_noise: bool):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        if remove_noise:
            await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=12.0, smoothing_bands=3)

        await _run_step(job, "compress 4:1", bridge, "Compressor",
                         _params(thresholdDb=-18.0, compressionRatio=4.0, attackMs=3.0,
                                 releaseMs=200.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        await _safe_loudness_step(job, bridge, target=-16.0, mode="lufs", peak_ceiling=-1.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Podcast Cleanup: {' > '.join(job['steps_applied'])}",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


async def _audiobook_pipeline(job: dict, bridge, remove_noise: bool):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        if remove_noise:
            await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=12.0, smoothing_bands=3)

        # Light compression for voice consistency (long release for audiobook pacing)
        await _run_step(job, "compress 2.5:1", bridge, "Compressor",
                         _params(thresholdDb=-18.0, compressionRatio=2.5, attackMs=10.0,
                                 releaseMs=1000.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        # ACX target: RMS -23 to -18dB, -20dB is the middle of the range.
        # peak_ceiling=-3.5 gives safety margin below ACX's -3dB peak requirement.
        await _safe_loudness_step(job, bridge, target=-20.0, mode="rms", peak_ceiling=-3.5)

        # Peak cap -3.5dB as a hard backstop (ACX requires peaks below -3dB)
        await _run_step(job, "peak cap -3.5dB", bridge, "Limiter",
                         _params(thresholdDb=-6.0, makeupTargetDb=-3.5, releaseMs=20.0, kneeWidthDb=2.0))

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Audiobook Mastering (ACX): {' > '.join(job['steps_applied'])}",
            "standard": "ACX/Audible - RMS -23 to -18dB, peaks below -3dB, noise floor below -60dB",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


async def _interview_pipeline(job: dict, bridge, remove_noise: bool):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        if remove_noise:
            await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=8.0, smoothing_bands=3)

        # Light compression - preserve natural conversation dynamics
        await _run_step(job, "compress 2.5:1", bridge, "Compressor",
                         _params(thresholdDb=-20.0, compressionRatio=2.5, attackMs=20.0,
                                 releaseMs=200.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        await _safe_loudness_step(job, bridge, target=-16.0, mode="lufs", peak_ceiling=-1.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Interview Cleanup: {' > '.join(job['steps_applied'])}",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


async def _vocal_pipeline(job: dict, bridge, remove_noise: bool):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        if remove_noise:
            await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=10.0, smoothing_bands=3)

        await _run_step(job, "compress 3:1", bridge, "Compressor",
                         _params(thresholdDb=-16.0, compressionRatio=3.0, attackMs=10.0,
                                 releaseMs=500.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        # Presence EQ - treble boost for clarity, slight bass cut
        await _run_step(job, "presence EQ (treble +3dB, bass -1dB)", bridge, "Bass and Treble",
                         _params(Bass=-1.0, Treble=3.0, Gain=0.0))

        await _safe_loudness_step(job, bridge, target=-16.0, mode="lufs", peak_ceiling=-1.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Vocal Cleanup: {' > '.join(job['steps_applied'])}",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


async def _live_pipeline(job: dict, bridge):
    try:
        await _run_step(job, "remove DC offset", bridge, "Normalize",
                         _params(PeakLevel=-1.0, RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False))

        # Click removal before NR - clicks can confuse noise profiling
        await _run_step(job, "click removal", bridge, "Click removal", _params(Threshold=200, Width=20))

        # Aggressive noise reduction - always on, 12dB max to avoid artifacts
        await _noise_reduction_step(job, bridge, sensitivity=6.0, noise_gain_db=12.0, smoothing_bands=3)

        # Heavy compression to tame dynamic range of live recordings
        await _run_step(job, "compress 5:1", bridge, "Compressor",
                         _params(thresholdDb=-14.0, compressionRatio=5.0, attackMs=10.0,
                                 releaseMs=500.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        await _safe_loudness_step(job, bridge, target=-16.0, mode="lufs", peak_ceiling=-1.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Live Recording Cleanup: {' > '.join(job['steps_applied'])}",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


_MASTERING_PRESETS = {
    "edm": {"comp_threshold": -12.0, "comp_ratio": 2.5, "comp_attack": 80.0, "comp_release": 150.0,
            "bass_eq": 2.0, "treble_eq": 1.0, "label": "EDM/Electronic"},
    "hiphop": {"comp_threshold": -14.0, "comp_ratio": 2.0, "comp_attack": 100.0, "comp_release": 200.0,
               "bass_eq": 3.0, "treble_eq": 1.0, "label": "Hip-Hop/Rap"},
    "rock": {"comp_threshold": -16.0, "comp_ratio": 2.0, "comp_attack": 100.0, "comp_release": 200.0,
             "bass_eq": 0.0, "treble_eq": 1.0, "label": "Rock"},
    "pop": {"comp_threshold": -14.0, "comp_ratio": 2.0, "comp_attack": 80.0, "comp_release": 200.0,
            "bass_eq": 1.0, "treble_eq": 1.5, "label": "Pop"},
    "classical": {"comp_threshold": -24.0, "comp_ratio": 1.3, "comp_attack": 200.0, "comp_release": 500.0,
                  "bass_eq": 0.0, "treble_eq": 0.0, "label": "Classical/Orchestral"},
    "acoustic": {"comp_threshold": -20.0, "comp_ratio": 1.5, "comp_attack": 150.0, "comp_release": 300.0,
                 "bass_eq": 0.0, "treble_eq": 0.0, "label": "Acoustic/Chill"},
}


async def _mastering_pipeline(job: dict, bridge, preset: dict, noise_reduce: bool):
    try:
        await _run_step(job, "click removal", bridge, "Click removal", _params(Threshold=200, Width=20))

        if noise_reduce:
            await _noise_reduction_step(job, bridge, sensitivity=4.0, noise_gain_db=6.0, smoothing_bands=3)

        await _run_step(job, f"compress {preset['comp_ratio']}:1", bridge, "Compressor",
                         _params(thresholdDb=preset["comp_threshold"], compressionRatio=preset["comp_ratio"],
                                 attackMs=preset["comp_attack"], releaseMs=preset["comp_release"],
                                 makeupGainDb=0.0, kneeWidthDb=6.0))

        if preset["bass_eq"] != 0.0 or preset["treble_eq"] != 0.0:
            await _run_step(job, f"EQ bass+{preset['bass_eq']}dB treble+{preset['treble_eq']}dB", bridge,
                             "Bass and Treble", _params(Bass=preset["bass_eq"], Treble=preset["treble_eq"], Gain=0.0))

        # No fixed loudness target - genre expectations vary too widely (classical
        # masters much quieter than EDM/hip-hop). Only a peak safety ceiling.
        await _safe_peak_only_step(job, bridge, ceiling=-3.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Music Mastering Complete ({preset['label']}): {' > '.join(job['steps_applied'])}",
            "genre": preset["label"],
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


_LOFI_PRESETS = {
    "light": {"bass_eq": 2.0, "treble_eq": -2.0, "label": "Light Lo-Fi"},
    "medium": {"bass_eq": 4.0, "treble_eq": -4.0, "label": "Medium Lo-Fi"},
    "heavy": {"bass_eq": 6.0, "treble_eq": -6.0, "label": "Heavy Lo-Fi"},
}


async def _lofi_pipeline(job: dict, bridge, preset: dict):
    try:
        # NOTE: v3 also applied a high-pass and low-pass filter here for the
        # "cut low end / cut high end" frequency-limiting part of the lo-fi
        # sound. v4 has no standalone HPF/LPF effect - that functionality was
        # consolidated into FilterCurveEQ/GraphicEQ, which need either a named
        # preset curve or a full frequency-response point array via automation,
        # not a simple two-knob filter. Deliberately deferred - this pipeline
        # currently only does the bass/treble warmth + compression part of the
        # v3 effect, not the actual frequency cutoff filtering.
        await _run_step(job, f"warmth (bass+{preset['bass_eq']}dB treble{preset['treble_eq']}dB)", bridge,
                         "Bass and Treble", _params(Bass=preset["bass_eq"], Treble=preset["treble_eq"], Gain=0.0))

        await _run_step(job, "compress 2:1", bridge, "Compressor",
                         _params(thresholdDb=-16.0, compressionRatio=2.0, attackMs=100.0,
                                 releaseMs=300.0, makeupGainDb=0.0, kneeWidthDb=6.0))

        await _safe_peak_only_step(job, bridge, ceiling=-3.0)

        job["status"] = "complete"
        job["current_step"] = "done"
        elapsed = round(time.time() - job["started_at"], 1)
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"Lo-Fi Effect Complete ({preset['label']}): {' > '.join(job['steps_applied'])}",
            "preset": preset["label"],
            "note": "bass/treble warmth + compression only - no frequency cutoff filtering (see code comment)",
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def auto_cleanup_audio(remove_noise: bool = True, remove_clicks: bool = False) -> dict:
        """SAFE CLEANUP: Remove noise and artifacts WITHOUT changing loudness or
        dynamics. Use this when audio levels are already good and you just want
        to clean it up. Runs in background - returns a job_id immediately. Use
        check_pipeline_status to monitor.

        Pipeline: DC offset removal > noise reduction (opt) > click removal (opt).
        NO compression, NO normalize, NO LUFS. Just clean.

        Args:
            remove_noise: Apply noise reduction using the first 0.5s as a noise
                profile. Default: True. IMPORTANT: the first 0.5s should be room
                tone/silence if this is True.
            remove_clicks: Remove clicks/pops (useful for vinyl/old recordings).
                Default: False.
        """
        job_id, job = await _create_job("cleanup_audio")
        if job is None:
            return _running_job_error()
        coro = _cleanup_audio_pipeline(job, bridge, remove_noise, remove_clicks)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Audio Cleanup started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_cleanup_podcast(remove_noise: bool = True) -> dict:
        """ONE-CLICK PODCAST CLEANUP. Runs in background - returns a job_id
        immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset > noise reduction (opt) > compress 4:1 > safe LUFS
        loudness (-16 LUFS, Apple Podcasts target) with clip-safe fallback.

        Args:
            remove_noise: Apply noise reduction using the first 0.5s as a noise
                profile. Default: True. IMPORTANT: the first 0.5s should be room
                tone/silence if this is True.
        """
        job_id, job = await _create_job("podcast_cleanup")
        if job is None:
            return _running_job_error()
        coro = _podcast_pipeline(job, bridge, remove_noise)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Podcast Cleanup started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_audiobook_mastering(remove_noise: bool = True) -> dict:
        """ONE-CLICK AUDIOBOOK MASTERING: ACX/Audible compliant processing.
        Runs in background - returns a job_id immediately. Use check_pipeline_status
        to monitor.

        Pipeline: DC offset > noise reduction (opt) > compression 2.5:1 > RMS -20dB
        (safe, clip-checked) > peak cap -3.5dB.
        Targets ACX requirements: RMS -23 to -18 dB, peaks below -3 dB (capped at
        -3.5 for safety margin), noise floor below -60 dB.

        Args:
            remove_noise: Apply noise reduction using the first 0.5s as a noise
                profile. Default: True. IMPORTANT: the first 0.5s should be room
                tone/silence if this is True.
        """
        job_id, job = await _create_job("audiobook_mastering")
        if job is None:
            return _running_job_error()
        coro = _audiobook_pipeline(job, bridge, remove_noise)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Audiobook Mastering (ACX) started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_cleanup_interview(remove_noise: bool = True) -> dict:
        """ONE-CLICK INTERVIEW CLEANUP: Light-touch processing for dialogue and
        multiple speakers. Runs in background - returns a job_id immediately.
        Use check_pipeline_status to monitor.

        Pipeline: DC offset > noise reduction 8dB (opt) > compression 2.5:1 >
        safe LUFS loudness. Lighter than podcast - preserves natural conversation
        dynamics.

        Args:
            remove_noise: Apply noise reduction using the first 0.5s as a noise
                profile. Default: True. IMPORTANT: the first 0.5s should be room
                tone/silence if this is True.
        """
        job_id, job = await _create_job("interview_cleanup")
        if job is None:
            return _running_job_error()
        coro = _interview_pipeline(job, bridge, remove_noise)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Interview Cleanup started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_cleanup_vocal(remove_noise: bool = True) -> dict:
        """ONE-CLICK VOCAL CLEANUP: Professional processing for singing and
        studio vocals. Runs in background - returns a job_id immediately.
        Use check_pipeline_status to monitor.

        Pipeline: DC offset > noise reduction 10dB (opt) > compression 3:1 >
        presence EQ (treble+3dB/bass-1dB) > safe LUFS loudness.

        Args:
            remove_noise: Apply noise reduction using the first 0.5s as a noise
                profile. Default: True. IMPORTANT: the first 0.5s should be room
                tone/silence if this is True.
        """
        job_id, job = await _create_job("vocal_cleanup")
        if job is None:
            return _running_job_error()
        coro = _vocal_pipeline(job, bridge, remove_noise)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Vocal Cleanup started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_cleanup_live() -> dict:
        """ONE-CLICK LIVE RECORDING CLEANUP: Aggressive processing for noisy/field
        recordings. Runs in background - returns a job_id immediately. Use
        check_pipeline_status to monitor.

        Pipeline: DC offset > click removal > noise reduction 12dB (always on) >
        compression 5:1 > safe LUFS loudness. Designed for live performances,
        field recordings, and noisy environments.

        IMPORTANT: The first 0.5 seconds MUST be room tone / ambient noise for
        noise profiling.
        """
        job_id, job = await _create_job("live_cleanup")
        if job is None:
            return _running_job_error()
        coro = _live_pipeline(job, bridge)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": "Live Recording Cleanup started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_master_music(style: str = "edm", noise_reduce: bool = False) -> dict:
        """ONE-CLICK MUSIC MASTERING: Professionally master your music track with
        genre-tuned settings. Runs in background - returns a job_id immediately.
        Use check_pipeline_status to monitor.

        Pipeline: click removal > noise reduction (opt, off by default for
        produced music) > compression (genre-tuned) > bass/treble sweetening
        (genre-tuned) > safe peak ceiling (no fixed loudness target - genre
        expectations vary too widely).

        Args:
            style: Genre preset - "edm", "hiphop", "rock", "pop", "classical",
                "acoustic". Default: "edm"
            noise_reduce: Apply gentle noise reduction. Default: False
        """
        style = style.lower().strip()
        if style not in _MASTERING_PRESETS:
            raise ValueError(f"style must be one of: {', '.join(_MASTERING_PRESETS.keys())}")

        job_id, job = await _create_job(f"mastering_{style}")
        if job is None:
            return _running_job_error()
        preset = _MASTERING_PRESETS[style]
        coro = _mastering_pipeline(job, bridge, preset, noise_reduce)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": f"Mastering ({preset['label']}) started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def auto_lofi_effect(intensity: str = "medium") -> dict:
        """CREATIVE LO-FI EFFECT: Apply a vintage/lo-fi sound to your audio. Runs
        in background - returns a job_id immediately. Use check_pipeline_status
        to monitor.

        Pipeline: bass/treble warmth > compression 2:1 > safe peak ceiling.
        NOTE: currently warmth + compression only, not the full frequency-cutoff
        filtering v3 had (see auto_lofi_effect's result "note" field for why).

        Args:
            intensity: "light" (subtle warmth), "medium" (classic lo-fi), "heavy"
                (extreme tape sound). Default: "medium"
        """
        intensity = intensity.lower().strip()
        if intensity not in _LOFI_PRESETS:
            raise ValueError(f"intensity must be one of: {', '.join(_LOFI_PRESETS.keys())}")

        job_id, job = await _create_job(f"lofi_{intensity}")
        if job is None:
            return _running_job_error()
        preset = _LOFI_PRESETS[intensity]
        coro = _lofi_pipeline(job, bridge, preset)
        job["_task"] = asyncio.create_task(coro)
        return {
            "job_id": job_id, "status": "running",
            "message": f"Lo-Fi Effect ({preset['label']}) started. Call check_pipeline_status every 15-30s.",
        }

    @mcp.tool()
    async def check_pipeline_status(job_id: str) -> dict:
        """Check the status of a running cleanup pipeline.

        Args:
            job_id: The job ID returned by an auto_ pipeline tool.
        """
        _cleanup_stale_jobs()
        job = _jobs.get(job_id)
        if not job:
            raise ValueError(f"Unknown job_id: {job_id}")

        elapsed = round(time.time() - job["started_at"], 1)
        result = {
            "job_id": job_id, "status": job["status"], "current_step": job["current_step"],
            "steps_completed": job["steps_applied"].copy(), "elapsed_seconds": elapsed,
        }
        if job["status"] == "complete":
            result["result"] = job["result"]
        elif job["status"] == "error":
            result["error"] = job["error"]
        if job["steps_failed"]:
            result["warnings"] = job["steps_failed"].copy()
        return result
