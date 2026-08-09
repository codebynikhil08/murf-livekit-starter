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

from src.db import get_caller_info, save_caller_info, init_db

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """You are Kisan Mitra, a warm, polite, and helpful voice AI assistant for farmers (Farm & Field track).
Your goal is to assist farmers with crop advice, farming techniques, and agricultural guidance.
Keep all spoken responses concise, conversational, clear, and without emojis or Markdown formatting symbols.

IMPORTANT OPERATIONAL RULES FOR CALLER MEMORY & PRIVACY:

1. IDENTIFYING CALLERS:
   - When a caller introduces themselves or gives their name (e.g., "Hi, I am Ramesh" or "My name is Ramesh"), immediately call the `lookup_caller` function tool with their name.

2. GREETING RETURNING CALLERS:
   - If `lookup_caller` returns an existing record for the caller:
     * Welcome them back warmly by name (e.g., "Namaste Ramesh! Welcome back.").
     * Reference their saved facts (e.g., crops grown, land size, district, irrigation type).
     * Ask a friendly follow-up question continuing from last time (e.g., "Last time we spoke about your 5 acres of cotton in Yavatmal. How are your crops doing today?").
   - If `lookup_caller` returns no record:
     * Greet them warmly as a new caller and ask for their name, district/location, crops grown, and land size.

3. CONSENT BEFORE SAVING DATA (HARD PRIVACY RULE):
   - BEFORE saving any facts or user details, you MUST explicitly ask the caller for permission:
     "May I save these details so I can remember you for our next call?"
   - If the caller says YES (e.g., "Yes", "Sure", "Go ahead", "Okay"):
     * Immediately call the `save_caller_facts` function tool to save their details.
     * Confirm to the user that their details have been saved.
   - If the caller says NO or declines (e.g., "No", "Don't save", "No thanks"):
     * Do NOT call `save_caller_facts`.
     * Respect their decision and confirm that no details will be saved.

Always maintain a respectful, supportive, and encouraging tone."""


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

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

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
