import json
import re

from mcp.server.fastmcp import FastMCP

MASTER_TRACK_ID = -2

# Substring keywords matched against an effect's title+category+vendor
# (case-insensitive) to classify it into a category - not every plugin
# reports a useful "category" itself (confirmed live: third-party VST3s all
# come back with category "None" from Audacity's own discovery), so title
# text is the only reliable signal across both Builtin and VST3 effects.
_EFFECT_CATEGORY_KEYWORDS = {
    "reverb": ["reverb", "verb", "hall", "room", "plate", "space"],
    "compressor": ["compress", "dynamics"],
    "eq": ["eq", "equali", "filter curve", "graphic eq", "bass and treble"],
    "delay": ["delay", "echo"],
    "limiter": ["limit"],
    "distortion": ["distort", "satur", "drive", "overdrive"],
    "gate": ["gate"],
    "chorus": ["chorus"],
    "phaser": ["phaser"],
    "flanger": ["flange"],
    "deesser": ["de-ess", "deess", "de ess"],
}

# Soft tiebreak only, not a hard requirement - these are widely-regarded,
# commonly-owned plugin vendors (Valhalla's reverbs/delays are free and
# near-ubiquitous; FabFilter is an industry-standard for EQ/dynamics).
# "Audacity" ranks alongside them so a solid stock/builtin effect isn't
# skipped over a third-party plugin just for being third-party. Whatever
# vendor isn't in this list still gets picked when it's the only match.
_PREFERRED_VENDORS = ["Valhalla", "FabFilter", "Audacity"]


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def suggest_and_add_effect(track_id: int, category: str) -> dict:
        """Find a good installed effect for a stated goal and add it as a
        realtime effect - the "pick the right plugin for me" workflow, so the
        user doesn't have to know which of their installed VSTs does reverb,
        compression, EQ, etc. Searches every actually-installed, realtime-
        capable effect (Builtin and VST3 alike) by matching category keywords
        against its title/vendor - VST3 plugins don't reliably self-report a
        usable category (confirmed live: they all come back "None"), so text
        matching is the only signal that works across formats. "Best" here is
        a soft preference among real matches (a few well-regarded vendors,
        see _PREFERRED_VENDORS), not an objective quality ranking - there
        isn't one. Returns the alternatives too, so the choice isn't a black
        box the user can't override.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            category: One of "reverb", "compressor", "eq", "delay", "limiter",
                "distortion", "gate", "chorus", "phaser", "flanger", "deesser".
        """
        category = category.lower().strip()
        if category not in _EFFECT_CATEGORY_KEYWORDS:
            raise ValueError(f"category must be one of: {', '.join(sorted(_EFFECT_CATEGORY_KEYWORDS))}")
        keywords = _EFFECT_CATEGORY_KEYWORDS[category]

        result = await bridge.call("list-effects", {"limit": 500})
        data = json.loads(result["content"][-1]["text"])
        effects = data.get("effects", [])

        def _matches(eff: dict) -> bool:
            haystack = f"{eff.get('title', '')} {eff.get('category', '')} {eff.get('vendor', '')}"
            # Plugin titles are frequently camelCase compounds with no word
            # separator (e.g. "ValhallaVintageVerb") - split at lower->upper
            # transitions first so each real word can be matched on its own.
            split_haystack = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", haystack)
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", split_haystack)
            for kw in keywords:
                if " " in kw:
                    # Multi-word phrase (e.g. "filter curve") - a plain substring
                    # check is safe here, phrases are long/specific enough not
                    # to false-match unrelated text the way single short tokens do.
                    if kw.lower() in split_haystack.lower():
                        return True
                else:
                    # Single-token keyword: match as a PREFIX of a whole word,
                    # not a bare substring anywhere. This is deliberately
                    # word-prefix, not exact-word or unbounded substring -
                    # confirmed live that both extremes are wrong: unbounded
                    # substring false-matched "hall" inside vendor "Valhalla"
                    # (picked a delay plugin for "reverb") and "eq" inside
                    # "Freq" (ValhallaFreqEcho matching "eq"); but exact-word
                    # matching then failed to match "compress" against
                    # "Compressor" (a real, correct match - "compress" is a
                    # genuine prefix, just not the whole word). Word-prefix
                    # matching is the rule that gets both right.
                    if any(word.lower().startswith(kw.lower()) for word in words):
                        return True
            return False

        candidates = [eff for eff in effects if eff.get("isRealtimeCapable") and _matches(eff)]

        if not candidates:
            raise ValueError(
                f"No installed, realtime-capable effect matched category {category!r}. "
                "Use list_effects yourself to see what's actually installed."
            )

        def _rank(eff):
            vendor = eff.get("vendor", "")
            preferred_index = next(
                (i for i, v in enumerate(_PREFERRED_VENDORS) if v.lower() in vendor.lower()),
                len(_PREFERRED_VENDORS),
            )
            return (preferred_index, eff.get("title", ""))

        candidates.sort(key=_rank)
        chosen = candidates[0]

        add_result = await bridge.call("add-realtime-effect", {"track_id": track_id, "effect_id": chosen["id"]})

        return {
            "chosen": {
                "title": chosen["title"], "id": chosen["id"],
                "vendor": chosen.get("vendor", ""), "family": chosen.get("family", ""),
            },
            "alternatives": [
                {"title": c["title"], "vendor": c.get("vendor", "")} for c in candidates[1:6]
            ],
            "add_result": add_result,
        }

    @mcp.tool()
    async def add_realtime_effect(track_id: int, effect_id: str) -> dict:
        """Add a non-destructive realtime effect to a track's (or the Master
        bus's) effect chain. Unlike apply-effect/effect_* tools, this stays
        adjustable and removable afterward - the actual VST/plugin GUI can
        still be opened live in Audacity to tweak it, same as adding it by
        hand via the Realtime Effects panel.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            effect_id: The real PluginID, from list_effects' "id" field - NOT
                "title". Confirmed live: passing a title here fails with
                "cannot load the effect" (this path has no title fallback,
                unlike apply-effect).
        """
        return await bridge.call("add-realtime-effect", {"track_id": track_id, "effect_id": effect_id})

    @mcp.tool()
    async def list_realtime_effects(track_id: int) -> dict:
        """List the realtime effect chain on a track or the Master bus, with
        each effect's index (for remove_realtime_effect/set_realtime_effect_active),
        name, and active state.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
        """
        return await bridge.call("list-realtime-effects", {"track_id": track_id})

    @mcp.tool()
    async def remove_realtime_effect(track_id: int, index: int) -> dict:
        """Remove one effect from a track's (or the Master bus's) realtime
        effect chain by index.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("remove-realtime-effect", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def set_realtime_effect_active(track_id: int, index: int, active: bool) -> dict:
        """Enable or bypass one effect in a track's (or the Master bus's)
        realtime effect chain, without removing it.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            active: True to enable, False to bypass.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("set-realtime-effect-active", {"track_id": track_id, "index": index, "active": active})

    @mcp.tool()
    async def list_effect_parameters(track_id: int, index: int) -> dict:
        """List a realtime effect's real, plugin-reported parameters - name,
        units, min/max/default/current value, and a human-formatted current
        value string. Works uniformly across Builtin/VST3/LV2/AudioUnit
        plugins via Audacity's own parameter-extraction layer - no need to
        guess a plugin's parameter names or ranges (e.g. a reverb's actual
        "Mix"/"Decay"/"Size" parameters, a compressor's "Threshold"/"Ratio").

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("list-effect-parameters", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def set_effect_parameter(track_id: int, index: int, parameter_id: str, value: float) -> dict:
        """Set one real-time parameter on a realtime effect to an exact value -
        e.g. the actual wet/dry mix or decay time of a reverb, not just
        add/remove/bypass the whole effect.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            parameter_id: Parameter id, from list_effect_parameters' "id" field.
            value: New value within [minValue, maxValue] from list_effect_parameters.
                CONFIRMED LIVE: for VST3 plugins this range is typically
                normalized 0-1, NOT real display units, even though
                list_effect_parameters' currentValueString shows a real unit
                (e.g. "21.26 s") - after setting, re-read currentValueString
                to see the actual resulting value, don't assume the input
                scale matches it.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        if not parameter_id:
            raise ValueError("parameter_id must not be empty")
        return await bridge.call(
            "set-effect-parameter",
            {"track_id": track_id, "index": index, "parameter_id": parameter_id, "value": value},
        )

    @mcp.tool()
    async def list_effect_presets(track_id: int, index: int) -> dict:
        """List a realtime effect's real factory presets (e.g. a reverb's named
        room/hall presets), if the plugin format exposes any. Not every plugin
        has factory presets - an empty list is a normal result, not an error.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("list-effect-presets", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def apply_effect_preset(track_id: int, index: int, preset_id: str) -> dict:
        """Apply one of a realtime effect's factory presets by id.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            preset_id: Preset id, from list_effect_presets.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        if not preset_id:
            raise ValueError("preset_id must not be empty")
        return await bridge.call("apply-effect-preset", {"track_id": track_id, "index": index, "preset_id": preset_id})
