from typing import List, Dict, Any, Optional
from app.ai.providers.base import LLMProvider
from app.ai.providers.mock_provider import MockLLMProvider
from app.schemas.ai import ChatMessage
from app.core.config import settings

class LLMGateway:
    def __init__(self, provider: Optional[LLMProvider] = None):
        if provider:
            self.provider = provider
        elif settings.LLM_PROVIDER == "mock" or not settings.LLM_API_KEY:
            self.provider = MockLLMProvider()
        else:
            from app.ai.providers.litellm_provider import LiteLLMProvider
            self.provider = LiteLLMProvider()

    def chat(self, messages: List[ChatMessage], tools: Optional[List[Dict[str, Any]]] = None) -> ChatMessage:
        try:
            return self.provider.generate_chat_response(messages, tools=tools)
        except Exception as e:
            # Handle timeout, retry logic here in a production setup
            raise ValueError(f"LLM Gateway error: {str(e)}")
