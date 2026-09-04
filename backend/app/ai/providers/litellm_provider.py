import litellm
from typing import List, Dict, Any, Optional
from app.ai.providers.base import LLMProvider
from app.schemas.ai import ChatMessage
from app.core.config import settings
import json

class LiteLLMProvider(LLMProvider):
    def generate_chat_response(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None
    ) -> ChatMessage:
        if not model:
            # default mapping based on config
            model = f"{settings.LLM_PROVIDER}/gpt-4o-mini" if settings.LLM_PROVIDER == "openai" else "gemini/gemini-1.5-flash"
        
        formatted_messages = []
        for msg in messages:
            f_msg = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                f_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                f_msg["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(f_msg)

        kwargs = {
            "model": model,
            "messages": formatted_messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = litellm.completion(**kwargs)
        choice = response.choices[0].message
        
        return ChatMessage(
            role=choice.role,
            content=choice.content or "",
            tool_calls=[tc.model_dump() for tc in choice.tool_calls] if hasattr(choice, "tool_calls") and choice.tool_calls else None
        )
