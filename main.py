"""
Multi-Agent Sales Lead Demo
Demonstrates multi-agent voice conversations with context handoff
"""
import asyncio
import json
import logging
import websockets
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from twilio.twiml.voice_response import VoiceResponse
from call_handling.twilio_client import TwilioClient
from orchestrator.call_orchestrator import CallOrchestrator
from config import (
    LEAD_SERVER_HOST,
    LEAD_SERVER_PORT,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    LEAD_SERVER_EXTERNAL_URL,
    LEAD_PHONE_NUMBER,
    DEEPGRAM_API_KEY
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s:%(name)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Validate config
logger.info(f"✓ Config loaded - DG Key: {'✓' if DEEPGRAM_API_KEY else '❌'}, Twilio: {'✓' if TWILIO_ACCOUNT_SID else '❌'}")

# Twilio client
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


async def place_outbound_call():
    """Initiate call to lead"""
    clean_url = LEAD_SERVER_EXTERNAL_URL.replace('wss://', '').replace('https://', '').replace('http://', '')
    twiml = f'''
    <Response>
        <Connect>
            <Stream url='wss://{clean_url}/twilio'/>
        </Connect>
    </Response>
    '''

    call = await twilio_client.create_call(
        to=LEAD_PHONE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        twiml=twiml
    )
    return call.sid


async def handle_customer_stream(websocket: websockets.WebSocketServerProtocol, path: str):
    """
    Handle customer stream with multi-agent orchestration
    """
    call_sid = None
    stream_sid = None
    orchestrator = None

    try:
        # Wait for initial Twilio message
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("event") == "start":
                    call_sid = data["start"].get("callSid")
                    stream_sid = data["start"].get("streamSid")
                    logger.info(f"[MAIN] Call started - CallSid: {call_sid}")
                    break
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Twilio message: {e}")
                continue

        if not call_sid:
            logger.error("No CallSid received from Twilio")
            return

        # Create orchestrator and start conversation
        orchestrator = CallOrchestrator(websocket, call_sid, stream_sid, twilio_client)
        await orchestrator.start_conversation()

        # Wait for orchestrator to complete
        # The orchestrator manages all agent transitions internally
        if orchestrator.listen_task:
            await orchestrator.listen_task

    except Exception as e:
        logger.error(f"[MAIN] Stream error: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        if orchestrator:
            await orchestrator.cleanup()
        logger.info(f"[MAIN] Call {call_sid} ended")


async def route_websocket_connection(websocket: websockets.WebSocketServerProtocol, path: str):
    """Route WebSocket connections"""
    try:
        logger.info(f"WebSocket connected: {path}")

        if path == "/twilio":
            await handle_customer_stream(websocket, path)
        else:
            logger.warning(f"Invalid path: {path}")
            await websocket.close(code=4001, reason="Invalid path")
    except Exception as e:
        logger.error(f"Exception in WebSocket router: {e}")
        logger.exception("Full traceback:")


async def process_request(path, request_headers):
    """Log incoming WebSocket requests"""
    logger.info(f"🔍 Incoming WebSocket: {path}")
    return None


async def main():
    """Start server and place call"""
    server = await websockets.serve(
        route_websocket_connection,
        LEAD_SERVER_HOST,
        LEAD_SERVER_PORT,
        ping_interval=20,
        ping_timeout=60,
        process_request=process_request
    )

    logger.info(f"✓ Server listening on {LEAD_SERVER_HOST}:{LEAD_SERVER_PORT}")
    logger.info(f"✓ External URL: {LEAD_SERVER_EXTERNAL_URL}")

    try:
        call_sid = await place_outbound_call()
        logger.info(f"✓ Call initiated: {call_sid}")
    except Exception as e:
        logger.error(f"❌ Failed to place call: {str(e)}")
        logger.exception("Full traceback:")
        raise

    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
