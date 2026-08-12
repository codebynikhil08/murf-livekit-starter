import json
import logging
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    tokenize,
    room_io,
    UserInputTranscribedEvent,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import sys
from pathlib import Path

# Ensure backend and backend/src are both on sys.path
src_dir = Path(__file__).parent
backend_dir = src_dir.parent
for p in (str(src_dir), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from src.db import get_caller_info, save_caller_info, init_db, create_escalation_record
    from src.tools import fetch_mandi_prices, fetch_district_weather
except ModuleNotFoundError:
    from db import get_caller_info, save_caller_info, init_db, create_escalation_record
    from tools import fetch_mandi_prices, fetch_district_weather

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """You are Kisan Mitra, a warm, polite, and helpful voice AI assistant for farmers (Farm & Field track).
Your goal is to assist farmers with crop advice, farming techniques, market mandi prices, weather updates, and knowing when to escalate to human experts.
Keep all spoken responses concise, conversational, clear, and without emojis or Markdown formatting symbols.

IMPORTANT OPERATIONAL RULES FOR DOMAIN LOOKUPS & TOOLS:

1. MANDI PRICE LOOKUP (`lookup_mandi_prices`):
   - When a caller asks about market rates, crop prices, mandi rates, or selling prices (e.g. "What is the price of cotton in Yavatmal?"), call `lookup_mandi_prices(crop, district)`.
   - ALWAYS state the date/time of the price data when replying (e.g., "As of today's Agmarknet update...").
   - IF THE TOOL RETURNS A FAILURE/TIMEOUT MESSAGE: State clearly and politely out loud to the caller that the market data service is temporarily offline or unavailable, and ask if they would like to create a human support request. Never invent fake rates.

2. WEATHER FORECAST LOOKUP (`get_district_weather`):
   - When a caller asks about weather, rainfall, temperature, or spraying/farming conditions (e.g. "Will it rain in Yavatmal today?"), call `get_district_weather(district)`.
   - ALWAYS state the timestamp of the forecast and provide relevant practical farming advice (e.g., whether to delay spraying pesticides).
   - IF THE TOOL RETURNS A FAILURE/TIMEOUT MESSAGE: State clearly out loud to the caller that the weather service is unreachable right now due to network issues. Never guess weather data.

3. CALLER MEMORY & PRIVACY RULES:
   - IDENTIFYING CALLERS: When a caller introduces themselves (e.g. "Hi, I am Ramesh"), call `lookup_caller(identifier)`.
   - CONSENT BEFORE SAVING DATA: BEFORE saving any facts or user details, explicitly ask: "May I save these details so I can remember you for our next call?"
   - Only call `save_caller_facts` if the user explicitly consents.

4. HUMAN HELP & ESCALATION RULES (`create_escalation`):
   - WHEN TO ESCALATE TO A HUMAN EXPERT:
     a) Severe Crop Emergency / Pest Infestation: Caller reports serious crop damage, pest infestation (e.g. Pink Bollworm, leaf yellowing, fungal blight, chemical spray damage) requiring expert inspection.
     b) Missing/Offline Data or Complex Disputes: Market/weather service is offline or caller has an unresolved dispute or complex financial/subsidy issue.
   - ASK BEFORE SHARING (MANDATORY CONSENT):
     - Before calling `create_escalation`, explain out loud: "This sounds like a serious issue that requires an agricultural officer. May I create a help request and share your name, location, and issue details with our Krishi officer?"
     - WAIT FOR THE CALLER'S ANSWER.
     - IF THEY SAY YES: Call `create_escalation(caller_name=..., issue_summary=..., urgency=..., user_permission_granted=True, ...)`.
     - IF THEY SAY NO: Respect their privacy! Politely acknowledge and DO NOT call `create_escalation`.
   - SUMMARY & NEXT STEPS:
     - Summarize only useful details: Who needs help, what happened, what was checked, urgency (low, medium, high, emergency), caller language, and contact method.
     - Never include sensitive private credentials (passwords, OTPs, PINs, bank accounts).
     - Give the caller a clear next step: Speak out the generated Reference ID (e.g., ESC-12345) clearly and state: "An agricultural officer from Krishi Vigyan Kendra will call you back on your phone within 24 hours. Your reference ID is ESC-XXXXX." Do not promise immediate callback unless true.

Always maintain a respectful, supportive, and encouraging tone."""


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool
    async def lookup_mandi_prices(self, context: RunContext, crop: str, district: str) -> str:
        """Use this tool to look up real-time market (mandi) prices for crops in a specified district or location. Always call this tool when a user asks about crop prices, market rates, mandi rates, or selling prices for produce.

        Args:
            crop: Name of the crop (e.g., 'cotton', 'wheat', 'soybean', 'onion', 'rice', 'tomato').
            district: District or market location (e.g., 'Yavatmal', 'Ludhiana', 'Nashik', 'Nagpur', 'Pune').
        """
        logger.info(f"Tool lookup_mandi_prices invoked for crop='{crop}', district='{district}'")
        return fetch_mandi_prices(crop=crop, district=district)

    @function_tool
    async def get_district_weather(self, context: RunContext, district: str) -> str:
        """Use this tool to fetch current live weather forecast and agricultural weather conditions for a specified district or city. Always call this tool when a user asks about weather, rainfall, temperature, or spraying/harvesting conditions.

        Args:
            district: Name of the district or city (e.g., 'Yavatmal', 'Ludhiana', 'Pune', 'Nashik').
        """
        logger.info(f"Tool get_district_weather invoked for district='{district}'")
        return fetch_district_weather(district=district)

    @function_tool
    async def lookup_caller(self, context: RunContext, identifier: str) -> str:
        """Use this tool to look up a caller's saved details from the database by their name or user ID.

        Args:
            identifier: The name or user ID of the caller (e.g., 'Ramesh', 'user_ramesh').
        """
        logger.info(f"Tool lookup_caller invoked for: {identifier}")
        record = get_caller_info(identifier)
        if not record:
            return f"No prior record found for caller '{identifier}'. This is a new caller."

        return f"Caller record found: {json.dumps(record)}"

    @function_tool
    async def save_caller_facts(
        self,
        context: RunContext,
        name: str,
        language_preference: str = "English",
        crops_grown: str = "",
        land_size: str = "",
        district: str = "",
        irrigation_type: str = "",
        other_facts: str = "",
    ) -> str:
        """Use this tool ONLY AFTER asking the caller for explicit permission to save their details AND receiving affirmative consent ('Yes'). Do NOT call this tool if the user declines consent.

        Args:
            name: The caller's name.
            language_preference: Preferred spoken language (e.g., 'Hindi', 'English', 'Marathi').
            crops_grown: Crops or produce grown by the farmer (e.g., 'cotton, wheat').
            land_size: Size of farm land (e.g., '5 acres').
            district: District or location (e.g., 'Yavatmal').
            irrigation_type: Type of irrigation used (e.g., 'drip irrigation', 'rainfed').
            other_facts: Any other relevant caller details discussed.
        """
        logger.info(f"Tool save_caller_facts invoked for: {name}")
        facts = {}
        if crops_grown:
            facts["crops_grown"] = crops_grown
        if land_size:
            facts["land_size"] = land_size
        if district:
            facts["district"] = district
        if irrigation_type:
            facts["irrigation_type"] = irrigation_type
        if other_facts:
            facts["other_facts"] = other_facts

        user_id = f"user_{name.lower().strip().replace(' ', '_')}"
        saved_record = save_caller_info(
            name=name,
            user_id=user_id,
            language_preference=language_preference,
            facts=facts,
        )
        return f"Successfully saved details for {name}: {json.dumps(saved_record)}"

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        caller_name: str,
        issue_summary: str,
        urgency: str = "medium",
        user_permission_granted: bool = False,
        language_preference: str = "Hindi",
        contact_method: str = "Phone Call",
        location: str = "",
    ) -> str:
        """Use this tool to create a human help escalation request when a caller needs assistance from an agricultural officer or human specialist (e.g., severe crop disease/pest outbreak, or offline market/weather data).

        CRITICAL REQUIREMENT: You MUST ask the caller for explicit permission before invoking this tool. If user_permission_granted is False, do NOT call this tool.

        Args:
            caller_name: The caller's name (e.g., 'Ramesh Pawar').
            issue_summary: Concise summary of who needs help, what happened, what was checked, urgency, and language.
            urgency: Urgency level ('low', 'medium', 'high', 'emergency').
            user_permission_granted: True if caller explicitly agreed to share their name, location, and issue details with a human expert.
            language_preference: Preferred language (e.g., 'Hindi', 'English', 'Marathi').
            contact_method: Preferred follow-up method (e.g., 'Phone Call', 'SMS', 'WhatsApp').
            location: Caller's district or village (e.g., 'Yavatmal, Maharashtra').
        """
        logger.info(f"Tool create_escalation invoked for caller='{caller_name}', granted={user_permission_granted}")
        if not user_permission_granted:
            return "ERROR: Permission denied by caller. Cannot share information or create human escalation request without explicit caller consent."

        record = create_escalation_record(
            caller_name=caller_name,
            issue_summary=issue_summary,
            urgency=urgency,
            language_preference=language_preference,
            contact_method=contact_method,
            location=location,
        )

        ref_id = record["reference_id"]
        status = record["status"]
        is_update = record.get("is_duplicate_updated", False)

        update_msg = " (Updated existing open request with new details)" if is_update else ""
        return (
            f"SUCCESS: Human escalation request recorded{update_msg}.\n"
            f"Reference ID: {ref_id}\n"
            f"Status: {status}\n"
            f"Urgency: {record['urgency'].upper()}\n"
            f"Caller: {record['caller_name']}\n"
            f"INSTRUCTIONS FOR AGENT: Inform the caller out loud that their request has been logged under Reference ID '{ref_id}'. "
            f"Tell them clearly that an agricultural officer from Krishi Vigyan Kendra will call them back via {record['contact_method']} within 24 hours."
        )




server = AgentServer()


def prewarm(proc: JobProcess):
    init_db()
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-3.5-flash-lite",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="Anisha", 
                locale="hi-IN",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Join the room and connect to the user first
    await ctx.connect()

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
