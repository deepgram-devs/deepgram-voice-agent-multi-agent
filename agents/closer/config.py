"""
Closer Agent Configuration
Role: Schedule follow-up, conduct quick satisfaction survey, end call gracefully
"""
import os
from deepgram.extensions.types.sockets import (
    AgentV1SettingsMessage,
    AgentV1AudioConfig,
    AgentV1AudioInput,
    AgentV1AudioOutput,
    AgentV1Agent,
    AgentV1Listen,
    AgentV1ListenProvider,
    AgentV1Think,
    AgentV1OpenAiThinkProvider,
    AgentV1DeepgramSpeakProvider,
    AgentV1SpeakProviderConfig,
    AgentV1Function,
)
from agents.shared.functions import END_CONVERSATION_FUNCTION

# Closer-specific functions
SCHEDULE_FUNCTION = AgentV1Function(
    name="schedule_followup",
    description="""Note the customer's preferred timeframe for follow-up. Use this when the customer indicates when they'd like to be contacted for a formal consultation.

Extract the timeframe from natural language. Examples:
- "next week"
- "Tuesday afternoon"
- "this Friday at 3pm"
- "sometime in the next few days"

Do not announce this function call. Simply call it after confirming their preference.""",
    parameters={
        "type": "object",
        "properties": {
            "preferred_timeframe": {
                "type": "string",
                "description": "Customer's preferred timeframe extracted from their response"
            },
            "notes": {
                "type": "string",
                "description": "Any special requests or notes about scheduling"
            }
        },
        "required": ["preferred_timeframe"]
    }
)

SURVEY_FUNCTION = AgentV1Function(
    name="record_satisfaction",
    description="""Record the customer's satisfaction rating. Use this when the customer provides a rating from 1 to 5.

Listen for the number they say (one, two, three, four, or five) and convert to the integer.

Do not announce this function call. Simply call it after they provide their rating.""",
    parameters={
        "type": "object",
        "properties": {
            "rating": {
                "type": "integer",
                "description": "Satisfaction rating from 1 (very dissatisfied) to 5 (very satisfied)",
                "minimum": 1,
                "maximum": 5
            },
            "feedback": {
                "type": "string",
                "description": "Any additional feedback the customer provides (optional)"
            }
        },
        "required": ["rating"]
    }
)

CLOSER_FUNCTIONS = [
    SCHEDULE_FUNCTION,
    SURVEY_FUNCTION,
    END_CONVERSATION_FUNCTION,
]

# System prompt for closer agent
CLOSER_PROMPT = """You are a scheduling and feedback specialist at Acme Financial Services. You are speaking on a phone call.

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Never announce function calls or say things like "[calling function]"
- Never use stage directions or meta narration (no text in brackets like "[scheduling now]")

CRITICAL - FUNCTION EXECUTION TIMING:
When you call functions (schedule_followup, record_satisfaction, end_conversation):
1. After receiving customer's answer, call the function IMMEDIATELY in the SAME RESPONSE
2. Do NOT wait for additional customer acknowledgment
3. Do NOT announce that you're recording or scheduling, and do NOT include any bracketed meta text (e.g., "[scheduling now]")

WRONG pattern:
You: "I'll note that you prefer next week."
[Wait for customer response]
[Then call schedule_followup function]

RIGHT pattern:
Customer: "Next week in the afternoon"
You: "Perfect! I'll note that you prefer next week in the afternoon, and our team will reach out to confirm."
[Call schedule_followup IMMEDIATELY in same response]

FUNCTION SEQUENCING:
You must call functions in this exact order:
1. FIRST: schedule_followup (after getting their timeframe)
2. SECOND: record_satisfaction (ask for a rating right after confirming scheduling; when they provide a number, call immediately in the same response)
3. LAST: end_conversation (after thanking them)

YOUR ROLE:
1. Thank the customer for their time
2. Ask about scheduling a follow-up consultation
3. If they agree, and once a specific time is selected (either proposed by you or chosen by them), acknowledge and call schedule_followup IMMEDIATELY in the same response (no extra confirmations)
4. Immediately ask for a satisfaction rating from 1 to 5; when they answer, acknowledge and call record_satisfaction in the SAME response (no meta narration)
5. Thank them and call end_conversation

TONE:
- Warm and appreciative
- Keep it brief - they've already spoken with two agents
- Don't pressure them if they decline scheduling or the survey

FIRST TURN BEHAVIOR:
- Your first non-greeting spoken response MUST explicitly acknowledge information from the provided context summary.
- If available, address the customer by name and reference their topic/reason for the follow-up in one concise sentence.
- Example: "Hi Robert — I see you're interested in target date retirement options; let’s get next steps set up."
- If any detail is missing in context, gracefully omit it (do not guess).

SCHEDULING SUGGESTIONS:
- When discussing scheduling, proactively suggest 2-3 specific options for NEXT WEEK during business hours (9am–5pm) unless the customer already gave a timeframe.
- Offer concise options in the customer's presumed local time, for example: "Monday at 10am, Tuesday at 2pm, or Thursday at 4pm next week."
- After the customer picks an option or shares a preference, call schedule_followup IMMEDIATELY in the same response (do not announce it).

Example flow:
You: "Thank you for taking the time to speak with us today. Would you like to schedule a follow-up consultation?"
Customer: "Yes, maybe next week sometime"
You: "Perfect. How about next week on Monday at 10am, Tuesday at 2pm, or Thursday at 4pm?"
Customer: "I'd say a 4"
You: "Thank you for that feedback. We appreciate your time and look forward to working with you. Have a great day!" [Then call end_conversation silently]
"""

def get_closer_config(context: str = "") -> AgentV1SettingsMessage:
    """Get closer agent configuration with context from advisor"""

    # Build dynamic greeting
    greeting = "Thank you for speaking with our advisor. I'd like to help you with next steps and get some quick feedback."

    # Add context to system prompt
    full_prompt = CLOSER_PROMPT
    if context:
        full_prompt = f"CONTEXT FROM PREVIOUS CONVERSATION:\n{context}\n\n{CLOSER_PROMPT}"

    return AgentV1SettingsMessage(
        audio=AgentV1AudioConfig(
            input=AgentV1AudioInput(
                encoding="mulaw",
                sample_rate=8000,
            ),
            output=AgentV1AudioOutput(
                encoding="mulaw",
                sample_rate=8000,
                container="none",
            ),
        ),
        agent=AgentV1Agent(
            listen=AgentV1Listen(
                provider=AgentV1ListenProvider(
                    type="deepgram",
                    model="flux-general-en",
                    smart_format=None,
                ),
            ),
            think=AgentV1Think(
                provider=AgentV1OpenAiThinkProvider(
                    type="open_ai",
                    model="gpt-4o-mini",
                ),
                prompt=full_prompt,
                functions=CLOSER_FUNCTIONS,
            ),
            speak=AgentV1SpeakProviderConfig(
                provider=AgentV1DeepgramSpeakProvider(
                    type="deepgram",
                    model=os.getenv("CLOSER_VOICE_MODEL", "aura-2-helena-en"),
                ),
            ),
            greeting=greeting
        ),
    )
