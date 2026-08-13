"""Crop problem specialist agent.

This specialist focuses on crop‑related queries such as disease identification,
pest control advice, and agronomic recommendations. It uses the same voice
pipeline as the main agent but can expose additional domain‑specific tools in
the future.
"""

import logging
from livekit.agents import Agent, function_tool, RunContext

logger = logging.getLogger("crop_specialist")

SYSTEM_PROMPT = """You are **Kisan Mitra – Crop Problem Specialist**. Your mission is to help farmers troubleshoot crop‑related issues, diagnose diseases, suggest pest‑management strategies, and provide agronomic advice. Keep responses concise, friendly, and without emojis or Markdown.
"""

class CropSpecialist(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool
    async def dummy_tool(self, context: RunContext) -> str:
        """Placeholder for future specialist‑only tools.
        Currently just acknowledges the handoff.
        """
        logger.info("CropSpecialist dummy_tool invoked")
        return "Crop specialist ready to assist."
