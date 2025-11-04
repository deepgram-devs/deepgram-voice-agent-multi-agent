# Function Definition Guide

Guidelines for writing effective function definitions for voice agents in the Deepgram Voice Agent API.

## Core Principle

Function descriptions teach the LLM when and how to call functions. Write them as instructions to a colleague, not as developer documentation.

## Function Structure

```python
AgentV1Function(
    name="function_name",
    description="What it does, when to use it, and any workflow requirements",
    parameters={
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "What it is and format requirements"
            }
        },
        "required": ["param_name"]
    }
)
```

## Writing Descriptions

**Three-part formula**: What, When, How

```python
description="""Record customer satisfaction rating. Use this when:
- Customer provides a rating from 1 to 5
- You've completed the main conversation objective

Listen for the number they say (one, two, three, four, or five) and convert
to integer. Do not announce this function call."""
```

## Voice-Specific Considerations

Voice agents hear speech, not text. Teach the LLM to parse natural language:

```python
"phone": {
    "type": "string",
    "description": "Phone number. Format as +1XXXXXXXXXX. Convert spoken to digits:
    'five five five one two three four' -> '+15551234567'
    Add +1 if not provided."
}
```

## Timing and Workflow

Be explicit about when functions should be called relative to conversation flow:

```python
description="""Hand off to the next agent.

CRITICAL TIMING:
1. Ask: "I can connect you with [next agent]. Would that work?"
2. WAIT for customer response (turn ends here)
3. When customer confirms ("yes", "sure", "okay"), IMMEDIATELY call this function
4. Do NOT generate additional text after calling the function

The function call handles the transition. Do not announce it."""
```

## Parameter Design

**Use enums** to constrain values:

```python
"reason": {
    "type": "string",
    "enum": ["customer_goodbye", "task_complete", "not_interested"]
}
```

**Be specific** about optional vs required:

```python
"required": ["preferred_timeframe"],  # Customer must provide this
# "notes" is optional
```

## Coordinating with System Prompts

Function descriptions and system prompts should reinforce each other:

**In function description:**
```python
description="...Do not announce this function call."
```

**In system prompt:**
```
When calling functions, do NOT say things like "let me record that" or
"I'm scheduling that now". Simply call the function silently.
```

## Example: Complete Function

```python
SCHEDULE_FUNCTION = AgentV1Function(
    name="schedule_followup",
    description="""Note customer's preferred timeframe for follow-up.

Use when customer indicates when they'd like to be contacted.

Extract timeframe from natural language:
- "next week" -> "next week"
- "Tuesday afternoon" -> "Tuesday afternoon"
- "this Friday at 3pm" -> "Friday 3pm"

Do not announce this function call.""",
    parameters={
        "type": "object",
        "properties": {
            "preferred_timeframe": {
                "type": "string",
                "description": "Customer's preferred timeframe"
            },
            "notes": {
                "type": "string",
                "description": "Special requests or notes about scheduling"
            }
        },
        "required": ["preferred_timeframe"]
    }
)
```

## Key Patterns

**Wait for confirmation pattern** (handoffs):
- Ask permission
- Wait for response
- Then call function

**Same-turn execution pattern** (data collection):
- Customer provides information
- Acknowledge it verbally
- Call function in same response

**Silent execution pattern** (all functions):
- Never announce "calling function" or "let me record that"
- Function calls happen behind the scenes

## See Also

- `agents/shared/functions.py` - Shared function implementations
- `agents/closer/config.py` - Agent-specific function examples
- `docs/PROMPT_GUIDE.md` - Prompt engineering best practices
