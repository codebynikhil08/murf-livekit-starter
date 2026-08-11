"""Telephony agent — handles both inbound and outbound SIP calls.

Includes:
- Dynamic Routing: Detects and handles outbound vs inbound calls.
- Safety First: Explicitly states who is calling, why, and how to stop in the first two sentences.
- Frictionless Opt-Out: Instantly hangs up if the user says "stop" or "cancel".
"""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
    UserInputTranscribedEvent,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("telephony-agent")

load_dotenv(".env.local")

# Required — create this with `lk sip outbound create` (see src/telephony/README.md).
OUTBOUND_TRUNK_ID = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

# Optional — a phone number to transfer people to when they ask for a human.
TRANSFER_TO_NUMBER = os.getenv("TRANSFER_TO_NUMBER")

# Change this prompt to change what your outbound agent does.
SYSTEM_PROMPT = """You are Kisan Mitra, a warm and helpful voice AI assistant calling on behalf of TechSeva Support. Help callers with crop advice, farming techniques, weather, or support questions. You are speaking on a phone call, so keep responses short and conversational — no formatting, emojis, or symbols. If the caller says "stop" or wants to opt-out, you must end the call immediately. If the person asks for a human, use the transfer_to_human tool. If you reach a voicemail or answering machine, use the detected_answering_machine tool. When the call is finished, use the end_call tool."""

# Safety First: Explicitly states who is calling, why, and how to stop.
OUTBOUND_GREETING = "Hi, this is Kisan Mitra calling on behalf of TechSeva Support to confirm your agricultural appointment. You can say 'stop' at any time to opt-out and end the call. Do you have a moment?"
INBOUND_GREETING = "Thanks for calling Kisan Mitra TechSeva Support! How can I help you today? You can say 'stop' at any time to end the call."

# The identity LiveKit gives the person we call. Used to transfer them later.
CALLEE_IDENTITY = "phone-user"


class TelephonyAgent(Agent):
    def __init__(self, ctx: JobContext, caller_identity: str) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.ctx = ctx
        self.caller_identity = caller_identity

    @function_tool
    async def transfer_to_human(self, context: RunContext) -> str:
        """Transfer the person to a human colleague.

        Use this when they explicitly ask for a person, or when you cannot help
        them with their request.
        """
        if not TRANSFER_TO_NUMBER:
            return "Transfers are not available on this line. Offer to have someone call back instead."

        # Tell them before transferring — the SIP transfer cuts off the audio.
        await context.session.generate_reply(
            instructions="Tell them you're connecting them to a colleague now."
        )

        logger.info("transferring call to %s", TRANSFER_TO_NUMBER)
        try:
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=self.caller_identity,
                    transfer_to=f"tel:{TRANSFER_TO_NUMBER}",
                    play_dialtone=True,
                )
            )
        except Exception:
            logger.exception("transfer failed")
            return "The transfer did not go through. Apologize and offer a call back."

        return "Transferred."

    @function_tool
    async def detected_answering_machine(self, context: RunContext) -> str:
        """Hang up because the call reached a voicemail or answering machine.

        Use this as soon as you hear a recorded greeting rather than a live person.
        """
        logger.info("answering machine detected — hanging up")
        await self._hangup()
        return "Call ended."

    @function_tool
    async def end_call(self, context: RunContext) -> str:
        """Hang up the call.

        Use this once the conversation is finished and you have said goodbye.
        """
        await context.session.generate_reply(
            instructions="Thank them for their time and say a short goodbye."
        )

        logger.info("ending call")
        await self._hangup()
        return "Call ended."

    async def _hangup(self) -> None:
        """Delete the room, which drops the SIP leg and ends the phone call."""
        await self.ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=self.ctx.room.name)
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def phone_number_from_metadata(ctx: JobContext) -> str | None:
    """Read the number to dial out of the dispatch metadata set by dial.py."""
    metadata = ctx.job.metadata
    if not metadata:
        return None
    try:
        return json.loads(metadata).get("phone_number")
    except json.JSONDecodeError:
        # Allow a bare phone number as metadata too, for quick `lk dispatch` tests.
        return metadata.strip() or None


def caller_phone_number(participant: rtc.RemoteParticipant) -> str | None:
    """The caller's phone number, if this participant arrived over SIP."""
    if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        return None
    return participant.attributes.get("sip.phoneNumber")


async def run_telephony_agent(ctx: JobContext, is_outbound: bool):
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "type": "outbound" if is_outbound else "inbound",
    }

    if is_outbound:
        phone_number = phone_number_from_metadata(ctx)
        if not phone_number:
            logger.error("no phone number in job metadata")
            ctx.shutdown()
            return
        if not OUTBOUND_TRUNK_ID:
            logger.error("LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set — cannot place calls")
            ctx.shutdown()
            return
    else:
        # Inbound call: wait for caller to join room
        await ctx.connect()
        participant = await ctx.wait_for_participant()
        phone_number = caller_phone_number(participant)
        caller_identity = participant.identity
        logger.info("inbound call answered from %s", phone_number or "unknown")

    # If outbound, we connect after verifying parameters
    if is_outbound:
        await ctx.connect()
        caller_identity = CALLEE_IDENTITY

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Frictionless Opt-Out: Instantly hangs up if the user says "stop" or "cancel"
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        text = event.transcript.strip().lower()
        if "stop" in text or "cancel" in text:
            logger.info("Frictionless opt-out triggered. Ending call.")
            asyncio.create_task(ctx.api.room.delete_room(api.DeleteRoomRequest(room=ctx.room.name)))

    session_started = asyncio.create_task(
        session.start(
            agent=TelephonyAgent(ctx, caller_identity),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # BVCTelephony is tuned for the narrow frequency range of phone audio.
                    noise_cancellation=lambda params: (
                        noise_cancellation.BVCTelephony()
                        if params.participant.kind
                        == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                        else noise_cancellation.BVC()
                    ),
                ),
            ),
        )
    )

    if is_outbound:
        logger.info("dialing %s", phone_number)
        try:
            # wait_until_answered means this returns once the call connects
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=CALLEE_IDENTITY,
                    participant_name="Phone user",
                    wait_until_answered=True,
                )
            )
        except api.TwirpError as e:
            logger.error(
                "call to %s was not answered: %s (%s)",
                phone_number,
                e.message,
                e.metadata.get("sip_status"),
            )
            session_started.cancel()
            ctx.shutdown()
            return

    await session_started

    # Greet the user first
    greeting = OUTBOUND_GREETING if is_outbound else INBOUND_GREETING
    await session.say(greeting, allow_interruptions=True)


@server.rtc_session(agent_name="outbound-agent")
async def outbound_session(ctx: JobContext):
    await run_telephony_agent(ctx, is_outbound=True)



if __name__ == "__main__":
    cli.run_app(server)
