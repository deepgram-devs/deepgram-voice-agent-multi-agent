# Multi-Agent Voice System

A reference implementation demonstrating **multi-agent voice conversation architecture** using Deepgram's Voice Agent API, where specialized agents handle different phases of customer interactions through seamless handoffs.

## Why Multi-Agent Architecture?

Traditional single-agent voice systems face fundamental limitations as complexity grows. This implementation demonstrates how to overcome these challenges by treating the conversation as a sequence of specialized phases/states, where each phase has its own:
- **System instructions** (the agent's prompt)
- **Transformed context** (summarized from previous conversation)
- **Specific tools** (2-4 focused functions per agent)

This approach solves critical problems:
- **Context Management**: Each agent starts fresh rather than accumulating entire conversation history
- **Focused Responsibility**: Agents excel at their specific task instead of juggling everything
- **Better Reliability**: Fewer functions per agent means clearer decision-making for the LLM
- **Easier Debugging**: Issues are isolated to specific agents and transitions

## Architecture Overview

```
┌─────────────────────────────────────────┐
│      Twilio Phone Call (Persistent)     │
│         WebSocket Connection            │
└──────────────────┬──────────────────────┘
                   │ Audio Stream
         ┌─────────▼──────────┐
         │  CallOrchestrator  │ ← Central coordinator
         │ ┌────────────────┐ │
         │ │ Audio Forward  │ │ ← Persistent task
         │ │     Task       │ │
         │ └────────────────┘ │
         └─────────┬──────────┘
                   │ Manages lifecycle
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│Qualifier│──►│ Advisor │──►│ Closer  │
│  Agent  │   │  Agent  │   │  Agent  │  ← Ephemeral Voice Agent sessions
└─────────┘   └─────────┘   └─────────┘
    │              │              │
    └──────────────┼──────────────┘
                   │
            Groq API (Llama 3.3 70B by default)
          Context Summarization
```

**Key Architecture Points**:
- **Persistent**: Twilio WebSocket and audio forwarding task remain active throughout
- **Ephemeral**: Voice Agent sessions are created/destroyed per agent
- **Orchestration**: CallOrchestrator manages all transitions and state
- **Context Transfer**: A small and fast LLM (via Groq API) summarizes conversation between agents

## Key Technical Concepts

### Session-Based Agent Switching
This implementation creates separate Voice Agent sessions for each specialized agent. The `CallOrchestrator` (orchestrator/call_orchestrator.py) manages these transitions while maintaining the Twilio connection.

### Audio Task Persistence Pattern
A critical implementation detail: the audio forwarding task starts once and persists throughout all agent transitions. This ensures the Twilio WebSocket remains active while agents switch:

```python
# Audio task starts ONCE and persists
if not self.audio_task or self.audio_task.done():
    self.audio_task = asyncio.create_task(self.forward_twilio_audio())
```

### Context Manager Lifecycle
Voice Agent connections are async context managers that require manual lifecycle management:

```python
# Creating connection
self.current_agent_context = self.current_client.agent.v1.connect()
self.current_agent_connection = await self.current_agent_context.__aenter__()

# Closing connection (keep audio task alive during transitions)
await self.close_current_agent(keep_audio_task=True)
```

### Function Call Response Pattern
Functions must be called with proper timing to maintain conversation flow:

```python
# 1. Send response to current agent
response = AgentV1FunctionCallResponseMessage(...)
await self.current_agent_connection.send_function_call_response(response)

# 2. Brief pause for processing
await asyncio.sleep(0.5)

# 3. Then perform the action (e.g., transition)
await self.transition_to_agent(next_agent)
```

## The Three Agents

Each agent represents a distinct conversation phase with focused responsibilities:

### 1. Qualifier Agent (`agents/qualifier/config.py`)
- **Purpose**: Initial contact and lead qualification
- **Functions**: `handoff_to_next_agent`, `end_conversation`
- **Collects**: Name, location, specific needs

### 2. Advisor Agent (`agents/advisor/config.py`)
- **Purpose**: Provide consultation and recommendations
- **Functions**: `handoff_to_next_agent`, `end_conversation`
- **Context**: Receives summary from qualifier

### 3. Closer Agent (`agents/closer/config.py`)
- **Purpose**: Schedule follow-up and gather feedback
- **Functions**: `schedule_followup`, `record_satisfaction`, `end_conversation`
- **Context**: Receives summary from advisor

## Implementation Details

### How Agent Transitions Work

When an agent calls `handoff_to_next_agent`, the orchestrator:

1. **Summarizes** the current conversation using Groq AI
2. **Closes** the current Voice Agent session (but keeps audio task running)
3. **Starts** a new Voice Agent session with the summarized context
4. **Continues** audio forwarding to the new agent seamlessly

### Creating an Agent Configuration

Each agent is configured with settings for STT, LLM, TTS, and functions:

```python
from deepgram.extensions.types.sockets import AgentV1SettingsMessage

def get_qualifier_config(context: str = "") -> AgentV1SettingsMessage:
    return AgentV1SettingsMessage(
        audio=AgentV1AudioConfig(...),  # Audio encoding settings
        agent=AgentV1Agent(
            listen=AgentV1Listen(...),   # Deepgram Flux STT
            think=AgentV1Think(           # LLM configuration
                model="gpt-4o-mini",
                prompt=QUALIFIER_PROMPT,
                functions=QUALIFIER_FUNCTIONS
            ),
            speak=AgentV1SpeakProviderConfig(...),  # Deepgram Aura TTS
            greeting="Hi, this is Alex..."
        )
    )
```

### Function Definitions

Functions include detailed descriptions to guide the LLM's behavior. See `agents/shared/functions.py` for examples. For comprehensive function definition best practices, refer to [docs/FUNCTION_GUIDE.md](docs/FUNCTION_GUIDE.md).

Key pattern: Functions should wait for customer confirmation:

```python
HANDOFF_FUNCTION = AgentV1Function(
    name="handoff_to_next_agent",
    description="""...
    CORRECT PATTERN:
    1. You ask: "I can connect you with [next agent]. Would that work?"
    2. WAIT for customer response
    3. Customer says: "Yes"
    4. You IMMEDIATELY call this function WITHOUT additional text
    """
)
```

## Quick Start

### Prerequisites

- Python 3.8+
- Twilio account with phone number (with outbound calling enabled)
- Deepgram API key
- Groq API key (free tier available at https://console.groq.com/)
- Public tunnel (ngrok, zrok, etc.)

### 1. Install Dependencies

This implementation uses the Deepgram Python SDK:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

The key environment variables (`config.py` manages these):
- `DEEPGRAM_API_KEY` - Your Deepgram API key
- `GROQ_API_KEY` - Groq API key for conversation summarization
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` - Twilio credentials
- `LEAD_SERVER_EXTERNAL_URL` - Your public tunnel URL
- `LEAD_PHONE_NUMBER` - Phone number to call

### 3. Start Public Tunnel

```bash
# Using zrok (free, easy)
zrok share public localhost:8000

# Or ngrok
ngrok http 8000 --scheme=ws
```

Copy the public URL and update `LEAD_SERVER_EXTERNAL_URL` in your `.env` file.

### 4. Run the System

```bash
python main.py
```

The system will:
1. Start a WebSocket server on port 8000
2. Initiate an outbound call to `LEAD_PHONE_NUMBER`
3. Begin the conversation with the Qualifier agent


## Example Conversation Flow

Here's a simplified flow showing agent transitions and function calls:

### Phase 1: Qualifier Agent
```
Agent: "Hi, this is Alex calling from our advisory services.
        Is now a good time to chat briefly?"
Customer: "Sure, I have a few minutes"
Agent: "Great! May I get your name?"
Customer: "John Smith"
Agent: "Where are you located?"
Customer: "Seattle"
Agent: "What brings you to call us today?"
Customer: "I need help with retirement planning"
Agent: "I can connect you with one of our advisors. Would that work?"
Customer: "Yes, that'd be great"
[Agent calls handoff_to_next_agent function]
```

### Transition
- Groq summarizes: "John Smith from Seattle needs retirement planning advice"
- Qualifier session closes
- Advisor session starts with context

### Phase 2: Advisor Agent
```
Agent: "Hi John! I understand you're interested in retirement planning.
        How can I help?"
Customer: "I'm 45 and want to retire by 60"
Agent: "Based on your timeline, I recommend a formal consultation.
        Can I connect you with our team to schedule that?"
Customer: "Yes please"
[Agent calls handoff_to_next_agent function]
```

### Transition
- Groq summarizes: "John Smith from Seattle would like to schedule a formal consultation"
- Advisor session closes
- Closer session starts with context

### Phase 3: Closer Agent
```
Agent: "Thanks for speaking with our advisor.
        When would work best for your consultation?"
Customer: "Next Wednesday afternoon"
[Agent calls schedule_followup function]
Agent: "Perfect! How would you rate your experience today from 1 to 5?"
Customer: "5"
[Agent calls record_satisfaction function]
Agent: "Thank you! Have a great day!"
[Agent calls end_conversation function]
```

## Project Structure

```
multi-agent-sales-lead/
├── main.py                      # Entry point - starts server, initiates calls
├── config.py                    # Environment variable management
│
├── orchestrator/
│   └── call_orchestrator.py    # Core orchestration logic
│
├── agents/
│   ├── shared/
│   │   └── functions.py        # Shared function definitions
│   ├── qualifier/               # Qualifier agent configuration
│   ├── advisor/                 # Advisor agent configuration
│   └── closer/                  # Closer agent configuration
│
├── utils/
│   └── context_summarizer.py   # Groq-based summarization
│
├── call_handling/
│   └── twilio_client.py        # Twilio API wrapper
│
└── docs/
    ├── ARCHITECTURE.md          # Deep technical dive
    ├── PROMPT_GUIDE.md          # Voice agent prompt best practices
    └── FUNCTION_GUIDE.md        # Function definition best practices
```


## Customization

### Modify Agent Behavior

Edit the prompts in each agent's config file:

**Qualifier** (`agents/qualifier/config.py`):
- Change greeting message
- Adjust information gathering flow
- Modify qualification criteria

**Advisor** (`agents/advisor/config.py`):
- Customize consultation approach
- Change expertise area (retirement, investments, etc.)
- Adjust handoff triggers

**Closer** (`agents/closer/config.py`):
- Modify scheduling questions
- Change satisfaction survey format
- Customize closing message

**Important**: See `docs/PROMPT_GUIDE.md` for voice-specific prompt engineering best practices.

### Add New Agents

See `docs/ARCHITECTURE.md` section "Extending the System" for detailed instructions.

Quick overview:
1. Create `agents/your_agent/config.py` with agent configuration
2. Update `orchestrator/call_orchestrator.py` transition logic
3. Add agent-specific function handlers if needed

### Change Summarization

Edit `utils/context_summarizer.py` to:
- Switch LLM models (currently Llama 3.3 70B on Groq). See [other available Groq models](https://console.groq.com/docs/models).
- Modify summarization prompts for better context extraction
- Change which data points are captured

## Additional Resources

- **[docs/PROMPT_GUIDE.md](docs/PROMPT_GUIDE.md)** - Voice agent prompt engineering best practices
- **[docs/FUNCTION_GUIDE.md](docs/FUNCTION_GUIDE.md)** - Function definition best practices
