"""
Context summarization using Groq for agent handoffs
"""
import os
import logging
from typing import List, Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class ContextSummarizer:
    """Summarize conversation history for agent handoffs using Groq"""

    def __init__(self):
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not set in environment")

        self.client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = os.getenv("GROQ_LLM", "llama-3.3-70b-versatile")

    def summarize_for_handoff(
        self,
        conversation_history: List[Dict[str, str]],
        from_agent: str,
        to_agent: str
    ) -> Dict[str, any]:
        """
        Summarize conversation for handoff between agents

        Args:
            conversation_history: List of {role, content} dicts
            from_agent: Source agent type (e.g., "qualifier")
            to_agent: Target agent type (e.g., "advisor")

        Returns:
            Dict with summary, extracted_data, and context string
        """
        if not conversation_history:
            return {
                "summary": "No prior conversation.",
                "extracted_data": {},
                "context": ""
            }

        # Build conversation text
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history
        ])

        # Create summarization prompt based on agent transition
        prompt = self._build_summarization_prompt(from_agent, to_agent, history_text)

        try:
            logger.info(f"Summarizing conversation for handoff: {from_agent} → {to_agent}")

            # Use sync API (we'll wrap in async if needed)
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a conversation summarization expert. Provide concise, accurate summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3  # Lower temperature for more consistent summaries
            )

            summary = completion.choices[0].message.content.strip()
            logger.info(f"Generated summary: {summary[:100]}...")

            # Extract structured data from conversation
            extracted_data = self._extract_data(conversation_history, from_agent)

            # Build context string for next agent's system prompt
            context = self._build_context_string(summary, extracted_data, from_agent)

            return {
                "summary": summary,
                "extracted_data": extracted_data,
                "context": context
            }

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback to basic summary
            return {
                "summary": f"Previous conversation with {from_agent} agent.",
                "extracted_data": {},
                "context": ""
            }

    def _build_summarization_prompt(self, from_agent: str, to_agent: str, history_text: str) -> str:
        """Build appropriate summarization prompt based on agent transition"""

        if from_agent == "qualifier" and to_agent == "advisor":
            return f"""Summarize this qualification call for the ADVISOR who will provide consultation.

Conversation:
{history_text}

Extract and format as a conversational briefing (2-3 sentences):
- Customer's name and location (if mentioned)
- Their specific need or pain point
- Any urgency indicators or timeline mentioned
- Why they're a qualified lead

Focus on what the advisor needs to provide relevant consultation.
Write as if briefing a colleague, not as bullet points.

Summary:"""

        elif from_agent == "advisor" and to_agent == "closer":
            return f"""Summarize this advisory consultation for the CLOSER who will schedule follow-up and gather feedback.

Conversation:
{history_text}

Extract and format as a conversational briefing (2-3 sentences):
- Solutions or recommendations discussed
- Customer's interest level and buying signals
- Any objections or concerns raised
- Next steps agreed upon

Focus on what the closer needs to schedule effectively and gauge satisfaction.
Write as if briefing a colleague, not as bullet points.

Summary:"""

        else:
            return f"""Summarize this conversation for handoff from {from_agent} to {to_agent}.

Conversation:
{history_text}

Provide a brief 2-3 sentence summary of key points and current status.
Write as a conversational briefing, not as bullet points.

Summary:"""

    def _extract_data(self, conversation_history: List[Dict[str, str]], from_agent: str) -> Dict[str, any]:
        """Extract structured data from conversation"""

        extracted = {}

        # Simple pattern matching for common data points
        full_text = " ".join([msg['content'].lower() for msg in conversation_history])

        # Extract name (very basic - could be improved)
        for msg in conversation_history:
            if msg['role'] == 'user':
                words = msg['content'].split()
                # Look for capitalized words that might be names
                potential_names = [w for w in words if w[0].isupper() and len(w) > 2]
                if potential_names:
                    extracted['customer_name'] = potential_names[0]
                    break

        # Track engagement level
        if 'yes' in full_text or 'interested' in full_text:
            extracted['engagement'] = 'high'
        elif 'maybe' in full_text or 'not sure' in full_text:
            extracted['engagement'] = 'medium'
        else:
            extracted['engagement'] = 'unknown'

        return extracted

    def _build_context_string(self, summary: str, extracted_data: Dict, from_agent: str) -> str:
        """Build context string to inject into next agent's system prompt"""

        context_parts = [f"Previous conversation summary: {summary}"]

        if extracted_data.get('customer_name'):
            context_parts.append(f"Customer name: {extracted_data['customer_name']}")

        if extracted_data.get('engagement'):
            context_parts.append(f"Engagement level: {extracted_data['engagement']}")

        return "\n".join(context_parts)


# Singleton instance
_summarizer = None

def get_summarizer() -> ContextSummarizer:
    """Get or create singleton summarizer instance"""
    global _summarizer
    if _summarizer is None:
        _summarizer = ContextSummarizer()
    return _summarizer
