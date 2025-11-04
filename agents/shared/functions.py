"""
Shared functions available to all agents
"""
from deepgram.extensions.types.sockets import AgentV1Function

# Function definition for handing off to next agent
HANDOFF_FUNCTION = AgentV1Function(
    name="handoff_to_next_agent",
    description="""Hand off the conversation to the next agent in the workflow.

WHEN TO CALL THIS:
Call this function IMMEDIATELY after the customer confirms they want to proceed to the next step.

CORRECT PATTERN:
1. You ask: "I can connect you with [next agent]. Would that work for you?"
2. WAIT for customer response
3. Customer says: "Yes" / "Sure" / "That'd be great" / "Okay"
4. You IMMEDIATELY call this function WITHOUT generating additional text

WRONG PATTERN:
- Calling this function in the same turn as asking for confirmation
- Saying "Let me connect you now" and then calling the function
- Generating text after calling the function

The function call itself handles the transition. Do not announce or narrate it.""",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Brief reason for the handoff (e.g., 'lead qualified', 'consultation complete')"
            },
            "notes": {
                "type": "string",
                "description": "Any additional context or notes for the next agent"
            }
        },
        "required": ["reason"]
    }
)

# Function definition for ending conversation
END_CONVERSATION_FUNCTION = AgentV1Function(
    name="end_conversation",
    description="""End the conversation gracefully.

WHEN TO CALL THIS:
Call this function IMMEDIATELY after saying your final goodbye when:
- Customer says goodbye or indicates they're done ("bye", "that's all", "thanks, goodbye")
- Customer explicitly asks to end the call
- You've completed your final task and said goodbye

Do NOT call this if the customer is just saying thanks but continuing the conversation.

CORRECT PATTERN:
Customer: "Okay, thanks. Goodbye!"
You: "Thank you for your time. Have a great day!"
[IMMEDIATELY call end_conversation WITHOUT additional text]

WRONG PATTERN:
- Calling this function before saying goodbye
- Generating text after calling the function
- Calling this when customer says "thanks" mid-conversation

The function call handles ending the call. Do not announce it.""",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Reason for ending (e.g., 'customer goodbye', 'task complete')",
                "enum": ["customer_goodbye", "task_complete", "customer_request", "not_interested"]
            }
        },
        "required": ["reason"]
    }
)
