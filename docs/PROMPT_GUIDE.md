# Voice Agent Prompt Guide

Best practices for writing prompts for voice agents in the Deepgram Voice Agent API.

## Core Principle: Voice-First Design

You're writing a script for a voice actor, not a chat interface. Every word gets synthesized into speech and played over a phone call.

**The Golden Rule**: If it sounds awkward when read aloud, it will sound awkward when spoken.

## Critical Formatting Rules

Your prompt must explicitly forbid patterns that don't work in voice:

```
VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.

NEVER use:
- Markdown formatting (no bold, italics, bullets, headers)
- Emojis or emoticons
- Brackets for stage directions [like this]
- Parenthetical asides (like this)
- Numbered or bulleted lists
- Special characters for emphasis
```

### Why This Matters

```
Bad:  "That's great! 😊"
TTS:  "That's great exclamation point smiley face"

Bad:  "**Important**: Check your email"
TTS:  "star star Important star star colon Check your email"

Bad:  "[Handoff in progress...]"
TTS:  "bracket Handoff in progress dot dot dot bracket"

Good: "That's wonderful!"
TTS:  "That's wonderful!"
```

## Voice-Friendly Patterns

**Numbers and identifiers:**
```
Bad:  "Your ID is 1234567890"
Good: "Your ID is one, two, three, four, five, six, seven, eight, nine, zero"

Bad:  "Call 555-1234"
Good: "Call five five five, one two three four"
```

**Lists:**
```
Bad:  "You have three options: 1) Basic, 2) Premium, 3) Enterprise"
Good: "You have three options. The first is Basic, then Premium, and finally Enterprise."
```

## Define Clear Identity

Establish who the agent is and their personality:

```
You are Sarah, a friendly customer service representative for Acme Financial.

PERSONALITY:
- Warm and conversational
- Professional but not stiff
- Patient and empathetic
- Brief responses (1-2 sentences per turn)
```

## Context Management

### Multi-Agent Context Handoff

When an agent receives context from a previous agent, integrate it naturally:

```python
# In get_advisor_config():
full_prompt = ADVISOR_PROMPT
if context:
    full_prompt = f"CONTEXT FROM PREVIOUS CONVERSATION:\n{context}\n\n{ADVISOR_PROMPT}"
```

**In the prompt:**
```
You will receive context about the customer from the previous agent.
Use this context naturally - you can confirm information they already provided, but don't ask questions they've already answered.
Acknowledge what you know and build on it.
```

## Conversation Behavior

**Keep responses brief:**
```
Bad:  Long explanations that take 30+ seconds to speak
Good: 1-2 sentences per turn, letting the customer respond
```

**Natural dialogue:**
```
Bad:  "I will now transfer you to the next department."
Good: "Let me connect you with someone who can help with that."
```

**Don't announce actions:**
```
Bad:  "I'm now checking your account... processing... found it!"
Good: "I found your account."
```

## Function Call Integration

Prompts should instruct when and how to call functions:

```
FUNCTION USAGE:

For handoff_to_next_agent:
1. Ask: "I can connect you with an advisor. Would that work for you?"
2. WAIT for customer response
3. When they confirm, IMMEDIATELY call handoff_to_next_agent
4. Do NOT generate text after calling the function

For data collection functions (schedule_followup, record_satisfaction):
- Call the function in the SAME turn as acknowledging the customer's input
- Do NOT announce "let me record that" or "I'm noting that down"
- Simply acknowledge and call the function silently
```

## Example: Complete Agent Prompt

```python
QUALIFIER_PROMPT = """You are Alex, a lead qualification agent for advisory services.
You are making an OUTBOUND call to someone who previously expressed interest.

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Never announce function calls

YOUR ROLE:
1. Ask if now is a good time to talk
2. If YES: Gather name, location, and what they're interested in
3. If NO: Say someone will follow up, then call end_conversation
4. Once you have the information, offer to connect them with an advisor

TONE:
- Warm and respectful (you're calling them)
- Conversational and brief
- Gracefully exit if they're not interested

FUNCTION TIMING:
For handoff_to_next_agent:
1. Ask: "I can connect you with one of our advisors. Would that work?"
2. WAIT for response
3. When confirmed, IMMEDIATELY call the function
4. Do NOT generate additional text

For end_conversation:
1. Say goodbye: "No problem. Someone will follow up. Have a great day!"
2. IMMEDIATELY call end_conversation
3. Do NOT generate additional text
"""
```

## Key Principles

**Voice-first thinking:**
- Read your prompts aloud to catch awkward phrasing
- Remember the customer can't see formatting or visual cues

**Concise instructions:**
- Long prompts dilute important points
- Be specific about critical behaviors (function timing, tone)

**Reinforce with functions:**
- Prompt and function descriptions should align
- Repeat important rules in both places

## See Also

- `agents/qualifier/config.py` - Example agent configuration
- `agents/advisor/config.py` - Agent with context from previous agent
- `docs/FUNCTION_GUIDE.md` - Function definition best practices
