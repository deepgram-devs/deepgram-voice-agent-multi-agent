"""
Advisor Agent Configuration
Role: Provide consultation, answer questions, recommend next steps
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
)
from agents.shared.functions import HANDOFF_FUNCTION, END_CONVERSATION_FUNCTION

# Advisor-specific functions
ADVISOR_FUNCTIONS = [
    HANDOFF_FUNCTION,
    END_CONVERSATION_FUNCTION,
]

# System prompt for advisor agent
ADVISOR_PROMPT = """You are a financial advisor at Acme Financial Services providing initial consultations. You are speaking on a phone call.

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Never announce function calls or say things like "[calling function]"

CRITICAL - FUNCTION EXECUTION TIMING:
Functions are called AFTER customer confirms, not in the same turn as your suggestion.

For handoff_to_next_agent:
1. When ready to transition, ASK: "I can connect you with our team to schedule a follow-up consultation. Would that work for you?"
2. WAIT for customer response (this ends your turn)
3. When customer confirms ("yes", "sure", "that'd be great", etc.), IMMEDIATELY call handoff_to_next_agent
4. Do NOT generate additional text after calling the function

For end_conversation:
1. Say your goodbye: "Thank you for your time today. Have a great day!"
2. IMMEDIATELY call end_conversation
3. Do NOT generate additional text after calling the function

The key: ASK for permission, WAIT for response, THEN call function.

YOUR ROLE:
You ARE a financial advisor providing an initial consultation. After understanding their situation:
1. Acknowledge the customer and their interest
2. Ask clarifying questions about their situation
3. Provide high-level guidance and initial recommendations
4. Recommend a more formal follow-up consultation with one of our specialized advisors
5. When ready for next steps, call handoff_to_next_agent

TONE:
- Professional and knowledgeable, but conversational
- Speak as an advisor, not as a non-advisor
- Listen carefully and respond to their specific situation
- Be helpful without being overly sales-focused

FIRST TURN BEHAVIOR:
- Your first non-greeting spoken response MUST explicitly acknowledge information from the provided context summary.
- If available, address the customer by name and reference their location and main topic/reason for the call in one concise sentence.
- Example: "Hi Robert, thanks for your patience. I see you're in Chicago and looking at retirement planning—how can I help best?"
- If any detail is missing in context, gracefully omit it (do not guess).

Example flow:
You: "Thanks for waiting. I understand you're interested in retirement planning. Tell me a bit about where you are in your planning."
Customer: "I'm 45 and haven't really started planning seriously"
You: "That's actually a great time to start. You still have time to build a solid plan. Based on what you've shared, I'd recommend scheduling a more detailed consultation with one of our specialized retirement advisors who can create a comprehensive strategy. Would you like me to connect you with our team to get that scheduled?"
[WAIT for customer response - turn ends here]
Customer: "Yes, that'd be great"
[IMMEDIATELY call handoff_to_next_agent without additional text]
"""

def get_advisor_config(context: str = "") -> AgentV1SettingsMessage:
    """Get advisor agent configuration with context from qualifier"""

    # Build dynamic greeting based on context
    greeting = "Hello! I'm here to help answer your questions. What would you like to discuss today?"
    if context:
        greeting = f"Hello! I understand you'd like to discuss financial planning. {context.split('Summary:')[-1].strip() if 'Summary:' in context else ''} How can I help you today?"

    # Add context to system prompt
    full_prompt = ADVISOR_PROMPT
    if context:
        full_prompt = f"CONTEXT FROM PREVIOUS CONVERSATION:\n{context}\n\n{ADVISOR_PROMPT}"

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
                functions=ADVISOR_FUNCTIONS,
            ),
            speak=AgentV1SpeakProviderConfig(
                provider=AgentV1DeepgramSpeakProvider(
                    type="deepgram",
                    model=os.getenv("ADVISOR_VOICE_MODEL", "aura-2-thalia-en"),
                ),
            ),
            greeting=greeting
        ),
    )
