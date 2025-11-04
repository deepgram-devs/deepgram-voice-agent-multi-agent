import logging
import asyncio
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class TwilioClient:
    def __init__(self, account_sid: str, auth_token: str):
        """Initialize the Twilio client with credentials."""
        self.client = Client(account_sid, auth_token)
    
    async def create_call(self, to: str, from_: str, twiml: str) -> Optional[str]:
        """Create an outbound call using the Twilio API."""
        try:
            # Use asyncio.to_thread since Twilio's client is synchronous
            call = await asyncio.to_thread(
                self.client.calls.create,
                to=to,
                from_=from_,
                twiml=twiml
            )
            logger.info(f"Call created with SID: {call.sid}")
            return call
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e}")
            return None
    
    async def create_call_async(self, to: str, from_: str, twiml: str) -> Optional[str]:
        """Create an outbound call using the Twilio API."""
        return await self.create_call(to, from_, twiml)
    
    async def update_call(self, call_sid: str, twiml: str):
        """Update an in-progress call with new TwiML."""
        try:
            # Use asyncio.to_thread since Twilio's client is synchronous
            call = await asyncio.to_thread(
                self.client.calls(call_sid).update,
                twiml=twiml
            )
            logger.info(f"Call updated with SID: {call.sid}")
            return call
        except TwilioRestException as e:
            logger.error(f"Twilio API error during call update: {e}")
            return None
    
    async def create_conference(self, conference_name, status_callback=None):
        """Create a conference with the specified name."""
        twiml = f'''
        <Response>
            <Dial>
                <Conference 
                    statusCallback="{status_callback if status_callback else ''}"
                    startConferenceOnEnter="true"
                    endConferenceOnExit="false">
                    {conference_name}
                </Conference>
            </Dial>
        </Response>
        '''
        return twiml
    
    async def add_participant_to_conference(self, call_sid, conference_name):
        """Add a participant to an existing conference."""
        twiml = f'''
        <Response>
            <Dial>
                <Conference>{conference_name}</Conference>
            </Dial>
        </Response>
        '''
        return await self.update_call(call_sid, twiml)
    
    async def put_call_on_hold(self, call_sid, hold_music_url):
        """Put a call on hold with specified hold music."""
        twiml = f'''
        <Response>
            <Play loop="0">{hold_music_url}</Play>
        </Response>
        '''
        return await self.update_call(call_sid, twiml)
    
    async def complete_call(self, call_sid):
        """End a call by updating its status to completed."""
        try:
            # Use asyncio.to_thread since Twilio's client is synchronous
            call = await asyncio.to_thread(
                self.client.calls(call_sid).update,
                status="completed"
            )
            logger.info(f"Completed call {call_sid}")
            return call
        except TwilioRestException as e:
            logger.error(f"Failed to complete call {call_sid}: {str(e)}")
            return None 