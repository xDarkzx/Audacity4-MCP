import math
import os
import struct
import tempfile
import uuid
import wave

from mcp.server.fastmcp import FastMCP

from server4.tools.effects_tools import _params


def _temp_wav_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"audacity_mcp_analyze_{uuid.uuid4().hex[:8]}.wav")


def _measure_wav(wav_path: str) -> dict | None:
    """Read a WAV file and compute audio diagnostics. Returns None on failure.
    Ported near-verbatim from v3's AudacityMCP/audacity_mcp/tools/cleanup_tools.py."""
    try:
        with wave.open(wav_path, "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            sw = wf.getsampwidth()
            if n_frames == 0:
                return None

            if sw == 2:
                fmt_char = "h"
                max_val = 32768.0
            elif sw == 4:
                fmt_char = "f"
                max_val = 1.0
            else:
                return None

            duration = round(n_frames / rate, 2)
            chunk_size = rate

            peak_abs = 0.0
            noise_sum_sq = 0.0
            noise_count = 0
            noise_target = min(int(rate * 0.5), n_frames)
            total_sum = 0.0
            total_sum_sq = 0.0
            total_count = 0
            clipped_samples = 0
            clip_threshold = max_val * 0.999

            click_count = 0
            click_threshold = max_val * 0.3
            prev_sample = 0.0

            silence_threshold = max_val * 0.001
            min_gap_samples = int(rate * 0.5)
            current_silence_run = 0
            silence_gaps = []

            second_rms_values = []
            second_sum_sq = 0.0
            second_count = 0

            frames_read = 0
            while frames_read < n_frames:
                n = min(chunk_size, n_frames - frames_read)
                raw = wf.readframes(n)
                if len(raw) < n * sw:
                    break
                samples = struct.unpack(f"<{n}{fmt_char}", raw)

                for s in samples:
                    a = abs(s)
                    if a > peak_abs:
                        peak_abs = a
                    if a >= clip_threshold:
                        clipped_samples += 1
                    total_sum += s
                    total_sum_sq += s * s
                    total_count += 1
                    delta = abs(s - prev_sample)
                    if delta > click_threshold and total_count > 1:
                        click_count += 1
                    prev_sample = s
                    if a < silence_threshold:
                        current_silence_run += 1
                    else:
                        if current_silence_run >= min_gap_samples:
                            gap_start = (frames_read + total_count - current_silence_run) / rate
                            gap_dur = current_silence_run / rate
                            silence_gaps.append((round(max(gap_start, 0), 2), round(gap_dur, 2)))
                        current_silence_run = 0
                    second_sum_sq += s * s
                    second_count += 1
                    if second_count >= rate:
                        rms = math.sqrt(second_sum_sq / second_count) / max_val
                        if rms > 1e-10:
                            second_rms_values.append(20 * math.log10(rms))
                        second_sum_sq = 0.0
                        second_count = 0

                if noise_count < noise_target:
                    take = min(n, noise_target - noise_count)
                    for s in samples[:take]:
                        noise_sum_sq += s * s
                    noise_count += take

                frames_read += n

            if current_silence_run >= min_gap_samples:
                gap_start = (n_frames - current_silence_run) / rate
                silence_gaps.append((round(max(gap_start, 0), 2), round(current_silence_run / rate, 2)))

            if second_count > rate * 0.1:
                rms = math.sqrt(second_sum_sq / second_count) / max_val
                if rms > 1e-10:
                    second_rms_values.append(20 * math.log10(rms))

            peak_linear = peak_abs / max_val
            peak_db = round(20 * math.log10(max(peak_linear, 1e-10)), 1)

            noise_db = None
            if noise_count > 0:
                rms_linear = math.sqrt(noise_sum_sq / noise_count) / max_val
                noise_db = round(20 * math.log10(max(rms_linear, 1e-10)), 1)

            overall_rms_db = None
            if total_count > 0:
                overall_rms = math.sqrt(total_sum_sq / total_count) / max_val
                overall_rms_db = round(20 * math.log10(max(overall_rms, 1e-10)), 1)

            dc_offset = round((total_sum / total_count) / max_val, 6) if total_count > 0 else 0.0

            dynamic_range_db = None
            if len(second_rms_values) >= 2:
                dynamic_range_db = round(max(second_rms_values) - min(second_rms_values), 1)

            return {
                "peak_db": peak_db,
                "noise_floor_db": noise_db,
                "overall_rms_db": overall_rms_db,
                "dc_offset": dc_offset,
                "duration": duration,
                "sample_rate": rate,
                "clipped_samples": clipped_samples,
                "click_count": click_count,
                "silence_gaps": silence_gaps[:10],
                "silence_gap_count": len(silence_gaps),
                "dynamic_range_db": dynamic_range_db,
            }
    except Exception:
        return None


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def auto_analyze_audio(content_type: str = "auto") -> dict:
        """Analyze the current project's audio and recommend a cleanup pipeline.
        Selects all audio first, exports it to a temp WAV, measures it, and returns
        peak/noise/clipping/click/silence-gap/dynamic-range diagnostics plus a
        recommendation for which pipeline to run next.

        Args:
            content_type: "speech", "music", or "auto" (default). The noise-floor,
                SNR and click tests are only meaningful for speech, where the
                quietest passage is genuine room tone. In continuous music the
                quietest passage is the music itself, so those tests report a high
                noise floor and poor SNR for practically every mix - and acting on
                that advice (noise reduction profiled from the opening moments)
                damages the material. Percussive transients likewise register as
                clicks. Pass "music" to suppress the speech-only tests, or leave on
                "auto" to pick from the measurements; the value actually used is
                returned as "content_type_used".
        """
        await bridge.call("select-all", {})

        tmp_wav = _temp_wav_path()
        measurement_error = None
        measurements = None
        try:
            await bridge.call("export-wav", {"path": tmp_wav})
            if not os.path.exists(tmp_wav):
                measurement_error = f"export-wav reported success but no file was created at {tmp_wav}"
            else:
                file_size = os.path.getsize(tmp_wav)
                if file_size < 100:
                    measurement_error = f"Exported WAV is too small ({file_size} bytes) - export may have failed"
                else:
                    measurements = _measure_wav(tmp_wav)
                    if measurements is None:
                        measurement_error = f"WAV file exists ({file_size} bytes) but could not be parsed"
        except Exception as e:
            measurement_error = f"export-wav failed: {type(e).__name__}: {e}"
        finally:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

        peak_db = measurements["peak_db"] if measurements else None
        noise_floor_db = measurements["noise_floor_db"] if measurements else None
        overall_rms_db = measurements["overall_rms_db"] if measurements else None
        dc_offset = measurements["dc_offset"] if measurements else None
        clipped_samples = measurements["clipped_samples"] if measurements else 0
        click_count = measurements["click_count"] if measurements else 0
        silence_gaps = measurements["silence_gaps"] if measurements else []
        silence_gap_count = measurements["silence_gap_count"] if measurements else 0
        dynamic_range_db = measurements["dynamic_range_db"] if measurements else None
        duration = measurements["duration"] if measurements else None

        is_clipping = peak_db is not None and peak_db >= -0.1

        # Resolve the content type before interpreting anything. Speech has real
        # pauses, so it shows silence gaps and a genuinely quiet floor between
        # phrases; continuous music has neither.
        resolved_type = (content_type or "auto").strip().lower()
        if resolved_type not in ("speech", "music", "auto"):
            resolved_type = "auto"
        if resolved_type == "auto":
            snr_est = (peak_db - noise_floor_db) if (peak_db is not None and noise_floor_db is not None) else None
            looks_like_music = (
                silence_gap_count == 0
                and snr_est is not None and snr_est < 25
                and duration is not None and duration > 20
            )
            resolved_type = "music" if looks_like_music else "speech"
        speech_like = resolved_type == "speech"

        issues = []
        if peak_db is not None:
            if peak_db < -30:
                issues.append(f"VERY QUIET: Peak is only {peak_db} dB. Run normalize (to -3 dB) first.")
            elif peak_db < -20:
                issues.append(f"QUIET: Peak is {peak_db} dB - below normal levels.")
            elif peak_db < -12:
                issues.append(f"LOW VOLUME: Peak is {peak_db} dB - slightly quiet but workable.")
            if is_clipping:
                issues.append(f"CLIPPING: Peak is {peak_db} dB with {clipped_samples} clipped samples.")

        # Speech-only: for continuous music the "noise floor" is the music itself,
        # so these would fire on virtually every mix and recommend noise reduction
        # that would damage it.
        if speech_like and noise_floor_db is not None and peak_db is not None:
            snr = peak_db - noise_floor_db
            if snr < 15:
                issues.append(f"VERY NOISY: SNR is only {round(snr, 1)} dB.")
            elif snr < 20:
                issues.append(f"NOISY: SNR is {round(snr, 1)} dB.")
            if noise_floor_db > -30:
                issues.append(f"HIGH NOISE FLOOR: {noise_floor_db} dB - needs noise reduction.")

        if dc_offset is not None and abs(dc_offset) > 0.005:
            issues.append(f"DC OFFSET: {dc_offset} - will be removed by pipeline.")

        # Percussive material trips this constantly, so music needs a far higher bar.
        click_high, click_low = (50, 10) if speech_like else (400, 150)
        if click_count > click_high:
            issues.append(f"LOTS OF CLICKS/POPS: {click_count} detected.")
        elif click_count > click_low:
            issues.append(f"SOME CLICKS/POPS: {click_count} detected.")

        if silence_gap_count > 0:
            total_silence = sum(g[1] for g in silence_gaps)
            if silence_gap_count > 5:
                issues.append(f"MANY GAPS: {silence_gap_count} gaps totalling {round(total_silence, 1)}s.")

        if dynamic_range_db is not None:
            if dynamic_range_db > 40:
                issues.append(f"EXTREME DYNAMIC RANGE: {dynamic_range_db} dB - compression strongly recommended.")
            elif dynamic_range_db > 25:
                issues.append(f"WIDE DYNAMIC RANGE: {dynamic_range_db} dB.")

        if overall_rms_db is not None and peak_db is not None:
            crest_factor = peak_db - overall_rms_db
            if crest_factor < 3 and peak_db > -6:
                issues.append(f"OVER-COMPRESSED: Crest factor only {round(crest_factor, 1)} dB.")

        if speech_like:
            menu = (
                "\n\nSpeech pipelines:"
                "\n  - Podcast/voiceover: auto_cleanup_podcast"
                "\n  - Audiobook (ACX): auto_audiobook_mastering"
                "\n  - Interview/multi-speaker: auto_cleanup_interview"
                "\n  - Solo vocal take: auto_cleanup_vocal"
                "\n  - Live/board recording: auto_cleanup_live"
                "\n  - Noise/clicks only, levels untouched: auto_cleanup_audio"
                "\n\nIf this is actually music, re-run with content_type=\"music\"."
            )
        else:
            menu = (
                "\n\nMusic pipelines:"
                "\n  - Master (style=\"edm\", \"rock\", \"acoustic\", \"hiphop\", \"jazz\", \"classical\"):"
                " auto_master_music"
                "\n  - Lo-fi character: auto_lofi_effect"
                "\n  - Noise/clicks only, levels untouched: auto_cleanup_audio"
                "\n\nNoise-floor, SNR and click checks were skipped: they assume the quiet"
                "\nparts are room tone, which is not true of continuous music. Re-run with"
                "\ncontent_type=\"speech\" if this is a voice recording."
            )

        if peak_db is not None:
            recommendation = ("ISSUES FOUND:\n" + "\n".join(f"  - {i}" for i in issues)
                               if issues else "Audio looks healthy - no issues detected.")
            recommendation += menu
        else:
            recommendation = "Could not measure audio levels." + menu

        result = {
            "peak_db": peak_db,
            "noise_floor_db": noise_floor_db,
            "overall_rms_db": overall_rms_db,
            "is_clipping": is_clipping,
            "clipped_samples": clipped_samples,
            "dc_offset": dc_offset,
            "click_pop_count": click_count,
            "silence_gaps": silence_gap_count,
            "dynamic_range_db": dynamic_range_db,
            "duration_seconds": duration,
            "issues": issues,
            "content_type_used": resolved_type,
            "recommendation": recommendation,
        }
        if measurement_error:
            result["measurement_error"] = measurement_error
        return result

    # NOTE: v3 also had analyze_contrast and analyze_plot_spectrum. Confirmed
    # via this fork's real plugin registry (known_audio_plugins.json) that
    # neither "Contrast" nor "Plot Spectrum" is registered in this build -
    # source exists upstream in au3-builtin-effects but never links into this
    # fork (same class of finding as the missing Echo/Phaser/etc. effects) -
    # not wrapped here, would return "Effect not found" if they were.
    # analyze_find_clipping is also absent from the registry - not wrapped.

    @mcp.tool()
    async def analyze_beat_finder(threshold_percent: int = 65) -> dict:
        """Find beats in the selected audio and add a label at each one.

        Adds labels to the project's label track (creating one if needed) -
        call label_list afterward to read the detected beat positions.

        Args:
            threshold_percent: Sensitivity threshold, 5-100. Lower finds more beats. Default: 65
        """
        if not 5 <= threshold_percent <= 100:
            raise ValueError("threshold_percent must be 5 to 100")
        params = _params(THRESVAL=threshold_percent)
        return await bridge.call("apply-effect", {"effect_id": "Beat finder", "params": params})

    @mcp.tool()
    async def analyze_label_sounds(
        threshold_db: float = -30.0, measurement: str = "peak",
        min_silence_duration: float = 1.0, min_label_interval: float = 1.0,
        label_type: str = "between",
    ) -> dict:
        """Detect sounds separated by silence and add a label for each one
        (or for each silence gap, depending on label_type).

        Adds labels to the project's label track (creating one if needed) -
        call label_list afterward to read the detected regions.

        Args:
            threshold_db: Level below which audio counts as silence, -100 to 0. Default: -30.0
            measurement: How to measure level - "peak", "avg", or "rms". Default: "peak"
            min_silence_duration: Minimum silence length to count as a gap, in seconds. Default: 1.0
            min_label_interval: Minimum spacing between labels, in seconds. Default: 1.0
            label_type: "before"/"after" (point at sound edge), "around" (region around
                each sound), or "between" (region between sounds - i.e. the silences). Default: "between"
        """
        measurement_map = {"peak": 0, "avg": 1, "rms": 2}
        if measurement not in measurement_map:
            raise ValueError("measurement must be one of: peak, avg, rms")
        type_map = {"before": 0, "after": 1, "around": 2, "between": 3}
        if label_type not in type_map:
            raise ValueError("label_type must be one of: before, after, around, between")
        params = _params(**{
            "THRESHOLD": threshold_db, "MEASUREMENT": measurement_map[measurement],
            "SIL-DUR": min_silence_duration, "SND-DUR": min_label_interval,
            "TYPE": type_map[label_type],
        })
        return await bridge.call("apply-effect", {"effect_id": "Label sounds", "params": params})

    @mcp.tool()
    async def analyze_sample_data_export(path: str, limit: int = 100, units: str = "dB") -> dict:
        """Export raw sample values from the selection to a text/CSV/HTML file.

        Args:
            path: Absolute output path. Extension determines format (.txt, .csv, .html).
            limit: Maximum number of samples to export, 1-1000000. Default: 100
            units: Measurement scale - "dB" or "Linear". Default: "dB"
        """
        if not 1 <= limit <= 1000000:
            raise ValueError("limit must be 1 to 1000000")
        units_map = {"dB": 0, "Linear": 1}
        if units not in units_map:
            raise ValueError('units must be "dB" or "Linear"')
        params = _params(**{"NUMBER": limit, "UNITS": units_map[units], "FILENAME": path})
        return await bridge.call("apply-effect", {"effect_id": "Sample data export", "params": params})
