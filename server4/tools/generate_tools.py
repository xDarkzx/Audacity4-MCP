from mcp.server.fastmcp import FastMCP

# Generator effect IDs from the running Audacity 4
_GENERATORS = {
    "noise": "Effect_Audacity_Audacity_Noise_Built-in Effect: Noise",
    "silence": "Effect_Audacity_Audacity_Silence_Built-in Effect: Silence",
    "tone": "Effect_Audacity_Audacity_Tone_Built-in Effect: Tone",
    "chirp": "Effect_Audacity_Audacity_Chirp_Built-in Effect: Chirp",
    "dtmf": "Effect_Audacity_Audacity_DTMF Tones_Built-in Effect: DTMF Tones",
}


def _open_effect(effect_id: str) -> str:
    return f"action://effects/open?effectId={effect_id}"


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def generate_silence() -> dict:
        """Open the generate silence dialog."""
        return await bridge.dispatch(_open_effect(_GENERATORS["silence"]))

    @mcp.tool()
    async def generate_tone() -> dict:
        """Open the generate tone dialog to create a test tone."""
        return await bridge.dispatch(_open_effect(_GENERATORS["tone"]))

    @mcp.tool()
    async def generate_noise() -> dict:
        """Open the generate noise dialog to create white/pink/brown noise."""
        return await bridge.dispatch(_open_effect(_GENERATORS["noise"]))

    @mcp.tool()
    async def generate_chirp() -> dict:
        """Open the chirp generator dialog (frequency sweep tone)."""
        return await bridge.dispatch(_open_effect(_GENERATORS["chirp"]))

    @mcp.tool()
    async def generate_dtmf_tones() -> dict:
        """Open the DTMF tones generator dialog (phone dial tones)."""
        return await bridge.dispatch(_open_effect(_GENERATORS["dtmf"]))
