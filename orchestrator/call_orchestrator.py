"""
Call Orchestrator - Manages agent transitions while maintaining Twilio connection
"""
import asyncio
import logging
from typing import Optional, Dict, List
import websockets

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import (
    AgentV1SettingsAppliedEvent,
    AgentV1FunctionCallRequestEvent,
)

from agents.qualifier.config import get_qualifier_config
from agents.advisor.config import get_advisor_config
from agents.closer.config import get_closer_config
from utils.context_summarizer import get_summarizer

logger = logging.getLogger(__name__)


class CallOrchestrator:
    """
    Orchestrates multi-agent voice conversation flow

    Manages:
    - Twilio WebSocket connection (persistent)
    - Voice Agent sessions (created/destroyed per agent)
    - Conversation history and context
    - Agent transitions
    """

    def __init__(self, twilio_ws: websockets.WebSocketServerProtocol, call_sid: str, stream_sid: str, twilio_client=None):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.twilio_client = twilio_client

        # Current agent state
        self.current_agent_type = None
        self.current_agent_connection = None
        self.current_agent_context = None  # Add context manager reference
        self.current_client = None

        # Conversation tracking
        self.conversation_history: List[Dict[str, str]] = []
        self.agent_contexts: Dict[str, str] = {}  # Store context per agent

        # Event for coordinating handoffs
        self.handoff_in_progress = False
        self.settings_applied = asyncio.Event()
        self.cleanup_done = False  # Prevent double-cleanup

        # Context summarizer
        self.summarizer = get_summarizer()

        # Tasks
        self.listen_task = None
        self.audio_task = None

    async def start_conversation(self):
        """Start the conversation with the qualifier agent"""
        logger.info(f"[ORCHESTRATOR] Starting conversation for call {self.call_sid}")
        await self.start_agent("qualifier")

    async def start_agent(self, agent_type: str, context: str = ""):
        """
        Start a new agent session

        Args:
            agent_type: Type of agent ("qualifier", "advisor", "closer")
            context: Optional context from previous agent
        """
        logger.info(f"[ORCHESTRATOR] Starting {agent_type} agent")

        # Get agent configuration
        if agent_type == "qualifier":
            config = get_qualifier_config(context)
        elif agent_type == "advisor":
            config = get_advisor_config(context)
        elif agent_type == "closer":
            config = get_closer_config(context)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Create new Deepgram client and connect
        self.current_client = AsyncDeepgramClient()
        # Connect to Voice Agent - this returns a context manager
        self.current_agent_context = self.current_client.agent.v1.connect()

        # Enter the async context to establish the connection
        self.current_agent_connection = await self.current_agent_context.__aenter__()

        logger.info(f"[ORCHESTRATOR] Connected to Voice Agent API for {agent_type}")

        # Reset event
        self.settings_applied.clear()

        # Set up event handlers
        def on_message(message):
            if isinstance(message, AgentV1SettingsAppliedEvent):
                self.settings_applied.set()

            # Track conversation text for context
            if hasattr(message, 'role') and hasattr(message, 'content'):
                self.conversation_history.append({
                    "role": message.role,
                    "content": message.content
                })

            # Handle all messages
            asyncio.create_task(
                self.handle_agent_message(message)
            )

        self.current_agent_connection.on(EventType.MESSAGE, on_message)
        self.current_agent_connection.on(EventType.ERROR, lambda e: logger.error(f"[{agent_type.upper()}] Error: {e}"))
        self.current_agent_connection.on(EventType.CLOSE, lambda _: logger.info(f"[{agent_type.upper()}] Closed"))

        # Start listening
        self.listen_task = asyncio.create_task(self.current_agent_connection.start_listening())

        # Send settings
        await self.current_agent_connection.send_settings(config)

        # Wait for settings to be applied
        try:
            await asyncio.wait_for(self.settings_applied.wait(), timeout=5.0)
            logger.info(f"[ORCHESTRATOR] {agent_type} agent settings applied")
        except asyncio.TimeoutError:
            logger.error(f"[ORCHESTRATOR] Timeout waiting for {agent_type} settings")
            raise

        # Start forwarding audio from Twilio to agent (ONLY if not already running)
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self.forward_twilio_audio())
            logger.info(f"[ORCHESTRATOR] Started audio forwarding task")

        # Update current agent type
        self.current_agent_type = agent_type

    async def handle_agent_message(self, message):
        """Handle messages from the current Voice Agent"""
        import base64
        import json
        from deepgram.extensions.types.sockets import (
            AgentV1ConversationTextEvent,
            AgentV1UserStartedSpeakingEvent,
            AgentV1AgentAudioDoneEvent,
            AgentV1ErrorEvent,
            AgentV1WarningEvent,
        )

        agent_type = self.current_agent_type.upper() if self.current_agent_type else "UNKNOWN"

        try:
            # Binary audio - forward to Twilio
            if isinstance(message, bytes):
                audio_payload = base64.b64encode(message).decode("utf-8")
                twilio_msg = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": audio_payload}
                }
                try:
                    await self.twilio_ws.send(json.dumps(twilio_msg))
                except Exception as e:
                    if "ConnectionClosed" not in str(type(e).__name__):
                        logger.error(f"[{agent_type}] Error sending audio to Twilio: {e}")

            # Function call
            elif isinstance(message, AgentV1FunctionCallRequestEvent):
                await self.handle_function_call(message)

            # Conversation text
            elif isinstance(message, AgentV1ConversationTextEvent):
                logger.info(f"[{agent_type}] {message.role.upper()}: {message.content}")

            # User started speaking - send clear event to Twilio
            elif isinstance(message, AgentV1UserStartedSpeakingEvent):
                logger.info(f"[{agent_type}] User started speaking")

                # Send clear event to Twilio to stop any ongoing audio playback
                clear_msg = {
                    "event": "clear",
                    "streamSid": self.stream_sid
                }
                try:
                    await self.twilio_ws.send(json.dumps(clear_msg))
                except Exception as e:
                    if "ConnectionClosed" not in str(type(e).__name__):
                        logger.error(f"[{agent_type}] Error sending clear event: {e}")

            # Agent audio done
            elif isinstance(message, AgentV1AgentAudioDoneEvent):
                logger.info(f"[{agent_type}] Agent finished speaking")
            elif isinstance(message, AgentV1ErrorEvent):
                logger.error(f"[{agent_type}] ERROR: {message.description}")
            elif isinstance(message, AgentV1WarningEvent):
                logger.warning(f"[{agent_type}] WARNING: {message.description}")

        except Exception as e:
            logger.error(f"[{agent_type}] Error handling message: {e}")

    async def handle_function_call(self, event: AgentV1FunctionCallRequestEvent):
        """Handle function calls from agents"""
        import json
        from deepgram.extensions.types.sockets import AgentV1FunctionCallResponseMessage

        if not event.functions:
            return

        func = event.functions[0]
        function_name = func.name
        call_id = func.id
        args = json.loads(func.arguments)

        logger.info(f"[ORCHESTRATOR] Function call: {function_name} from {self.current_agent_type}")

        try:
            # Handle handoff to next agent
            if function_name == "handoff_to_next_agent":
                await self.handle_handoff(args, call_id)

            # Handle end conversation
            elif function_name == "end_conversation":
                await self.handle_end_conversation(args, call_id)

            # Handle closer-specific functions
            elif function_name == "schedule_followup":
                logger.info(f"[ORCHESTRATOR] Scheduling follow-up: {args}")
                response = AgentV1FunctionCallResponseMessage(
                    type="FunctionCallResponse",
                    name=function_name,
                    content=json.dumps({"status": "scheduled", "message": "Follow-up noted"}),
                    id=call_id
                )
                await self.current_agent_connection.send_function_call_response(response)

            elif function_name == "record_satisfaction":
                logger.info(f"[ORCHESTRATOR] Recording satisfaction: {args}")
                response = AgentV1FunctionCallResponseMessage(
                    type="FunctionCallResponse",
                    name=function_name,
                    content=json.dumps({"status": "recorded", "message": "Thank you for your feedback"}),
                    id=call_id
                )
                await self.current_agent_connection.send_function_call_response(response)

            else:
                logger.warning(f"[ORCHESTRATOR] Unknown function: {function_name}")
                response = AgentV1FunctionCallResponseMessage(
                    type="FunctionCallResponse",
                    name=function_name,
                    content=json.dumps({"status": "unknown_function"}),
                    id=call_id
                )
                await self.current_agent_connection.send_function_call_response(response)

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error handling function call: {e}")

    async def handle_handoff(self, args: Dict, call_id: str):
        """Handle handoff to next agent"""
        import json
        from deepgram.extensions.types.sockets import AgentV1FunctionCallResponseMessage

        logger.info(f"[ORCHESTRATOR] Handoff requested: {args}")

        # Send success response to current agent
        response = AgentV1FunctionCallResponseMessage(
            type="FunctionCallResponse",
            name="handoff_to_next_agent",
            content=json.dumps({"status": "transferring"}),
            id=call_id
        )
        await self.current_agent_connection.send_function_call_response(response)
        logger.info(f"[ORCHESTRATOR] Sent handoff response to {self.current_agent_type}")

        # Give the agent a brief moment to process the response
        await asyncio.sleep(0.5)

        # Determine next agent
        if self.current_agent_type == "qualifier":
            next_agent = "advisor"
        elif self.current_agent_type == "advisor":
            next_agent = "closer"
        else:
            logger.error(f"[ORCHESTRATOR] No next agent after {self.current_agent_type}")
            return

        # Perform the transition
        await self.transition_to_agent(next_agent)

    async def transition_to_agent(self, next_agent: str):
        """Transition from current agent to next agent"""
        logger.info(f"[ORCHESTRATOR] Transitioning: {self.current_agent_type} → {next_agent}")

        self.handoff_in_progress = True

        # Step 1: Summarize conversation
        context = await self.summarize_conversation(self.current_agent_type, next_agent)

        # Step 2: Close current agent session (but keep audio task alive)
        await self.close_current_agent(keep_audio_task=True)

        # Step 3: Start new agent with context
        await self.start_agent(next_agent, context)

        # Step 4: Reset conversation history for new agent
        self.conversation_history = []

        self.handoff_in_progress = False
        logger.info(f"[ORCHESTRATOR] Transition complete: now on {next_agent}")

    async def summarize_conversation(self, from_agent: str, to_agent: str) -> str:
        """Summarize conversation for handoff"""
        if not self.conversation_history:
            return ""

        try:
            # summarize_for_handoff is now sync, so we run it in a thread
            result = await asyncio.to_thread(
                self.summarizer.summarize_for_handoff,
                self.conversation_history,
                from_agent,
                to_agent
            )
            return result['context']
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Summarization failed: {e}")
            return f"Previous conversation with {from_agent}"

    async def close_current_agent(self, keep_audio_task=False):
        """Close the current agent session

        Args:
            keep_audio_task: If True, don't cancel the audio forwarding task (for handoffs)
        """
        # Check if we actually have a connection to close
        if not self.current_agent_connection:
            return

        logger.info(f"[ORCHESTRATOR] Closing {self.current_agent_type} agent")

        # Cancel audio task ONLY if not doing a handoff
        if not keep_audio_task and self.audio_task and not self.audio_task.done():
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass
            self.audio_task = None

        # Always cancel the listen task (agent-specific)
        if self.listen_task and not self.listen_task.done():
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
            self.listen_task = None

        # Close connection using the context manager
        try:
            if self.current_agent_context:
                await self.current_agent_context.__aexit__(None, None, None)
                self.current_agent_context = None
        except websockets.exceptions.ConnectionClosed:
            # Expected during transitions - suppress this specific error
            logger.debug(f"[ORCHESTRATOR] WebSocket closed during {self.current_agent_type} cleanup (expected)")
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error closing agent: {e}")

        # Clear references
        self.current_agent_connection = None
        self.current_client = None

    async def handle_end_conversation(self, args: Dict, call_id: str):
        """Handle conversation end"""
        import json
        from deepgram.extensions.types.sockets import AgentV1FunctionCallResponseMessage

        logger.info(f"[ORCHESTRATOR] Ending conversation: {args}")

        # Send success response
        response = AgentV1FunctionCallResponseMessage(
            type="FunctionCallResponse",
            name="end_conversation",
            content=json.dumps({"status": "conversation_ended"}),
            id=call_id
        )
        await self.current_agent_connection.send_function_call_response(response)

        # Give agent time to say goodbye (3 seconds to ensure full playback)
        await asyncio.sleep(3)

        # Hang up the Twilio call
        if self.twilio_client:
            logger.info(f"[ORCHESTRATOR] Hanging up call {self.call_sid}")
            await self.twilio_client.complete_call(self.call_sid)
        else:
            logger.warning("[ORCHESTRATOR] No twilio_client available to hang up call")

        # Close everything
        await self.cleanup()

    async def forward_twilio_audio(self):
        """Forward audio from Twilio to current Voice Agent"""
        import base64
        import json

        try:
            logger.info(f"[ORCHESTRATOR] Starting audio forwarding for {self.current_agent_type}")
            async for message in self.twilio_ws:
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get("event") == "media":
                        payload = data["media"]["payload"]
                        chunk = base64.b64decode(payload)
                        if self.current_agent_connection:
                            await self.current_agent_connection.send_media(chunk)
                    elif data.get("event") == "stop":
                        logger.info("[ORCHESTRATOR] Twilio stream stopped")
                        break
        except asyncio.CancelledError:
            logger.info(f"[ORCHESTRATOR] Audio forwarding cancelled for {self.current_agent_type}")
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error forwarding audio: {e}")

    async def cleanup(self):
        """Clean up all resources"""
        if self.cleanup_done:
            logger.info("[ORCHESTRATOR] Cleanup already done, skipping")
            return

        logger.info("[ORCHESTRATOR] Cleaning up")
        self.cleanup_done = True

        # Only close if we're not in the middle of a handoff
        # (handoff already handles closing the current agent)
        if not self.handoff_in_progress:
            await self.close_current_agent()
        logger.info("[ORCHESTRATOR] Cleanup complete")
