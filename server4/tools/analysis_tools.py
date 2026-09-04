import math
import os
import struct
import tempfile
import uuid
import wave

from mcp.server.fastmcp import FastMCP


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
    async def auto_analyze_audio() -> dict:
        """Analyze the current project's audio and recommend a cleanup pipeline.
        Selects all audio first, exports it to a temp WAV, measures it, and returns
        peak/noise/clipping/click/silence-gap/dynamic-range diagnostics plus a
        recommendation for which pipeline to run next.
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

        if noise_floor_db is not None and peak_db is not None:
            snr = peak_db - noise_floor_db
            if snr < 15:
                issues.append(f"VERY NOISY: SNR is only {round(snr, 1)} dB.")
            elif snr < 20:
                issues.append(f"NOISY: SNR is {round(snr, 1)} dB.")
            if noise_floor_db > -30:
                issues.append(f"HIGH NOISE FLOOR: {noise_floor_db} dB - needs noise reduction.")

        if dc_offset is not None and abs(dc_offset) > 0.005:
            issues.append(f"DC OFFSET: {dc_offset} - will be removed by pipeline.")

        if click_count > 50:
            issues.append(f"LOTS OF CLICKS/POPS: {click_count} detected.")
        elif click_count > 10:
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

        if peak_db is not None:
            recommendation = ("ISSUES FOUND:\n" + "\n".join(f"  - {i}" for i in issues)
                               if issues else "Audio looks healthy - no issues detected.")
            recommendation += "\n\nChoose pipeline based on content type:\n  - Podcast/voiceover: auto_cleanup_podcast\n  - Audiobook (ACX): auto_audiobook_mastering"
        else:
            recommendation = "Could not measure audio levels.\n  - Podcast/voiceover: auto_cleanup_podcast\n  - Audiobook (ACX): auto_audiobook_mastering"

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
            "recommendation": recommendation,
        }
        if measurement_error:
            result["measurement_error"] = measurement_error
        return result
