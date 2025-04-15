from __future__ import annotations
import asyncio
import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
    voice_assistant,
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai, silero
import os

from langgraph_llm import LangGraphLLM

if os.path.isfile(".env.local"):
    load_dotenv(dotenv_path=".env.local", verbose=True)
logger = logging.getLogger("my-worker")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()

    await run_multimodal_agent(ctx, participant)

    logger.info("agent started")


async def run_multimodal_agent(ctx: JobContext, participant: rtc.RemoteParticipant):
    logger.info("starting multimodal agent")

    model = openai.realtime.RealtimeModel(
        instructions=(
            "You are a front desk voice assistant who can schedule appointments. Your interface with users will be voice. "
            "You should use short and concise responses, and avoiding usage of unpronouncable punctuation. Verify if you understood the email ID correctly before sending the confirmation mail. Always send an email to the verified email ID after scheduling the appointment."
        ),
        modalities=["audio", "text"],
    )

    # create a chat context with chat history, these will be synchronized with the server
    # upon session establishment
    chat_ctx = llm.ChatContext()
    # chat_ctx.append(
    #     text="Context about the user: you are talking to a patient looking to schedule doctor's appointment."
    #     "Greet the user with a friendly greeting and ask how you can help them today.",
    #     role="assistant",
    # )

    # agent = MultimodalAgent(
    #     model=model,
    #     chat_ctx=chat_ctx,
    #     fnc_ctx=sendEmail(),
    # )
    # chat_ctx.append(
    #     text="You are a front desk voice assistant who can schedule appointments. Your interface with users will be voice. "
    #     "You should use short and concise responses, and avoiding usage of unpronouncable punctuation. Seek all teh necessary details from the caller before sending an email",
    #     role="system",
    # )
    agent = VoiceAssistant(
        vad=silero.VAD.load(),
        stt=openai.STT(),
        llm=LangGraphLLM(),
        tts=openai.TTS(),
        chat_ctx=chat_ctx,
        fnc_ctx=None,
    )
    agent.start(ctx.room, participant)
    # to enable the agent to speak first
    await agent.say("Hello there! How can I help you?", add_to_chat_ctx=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
