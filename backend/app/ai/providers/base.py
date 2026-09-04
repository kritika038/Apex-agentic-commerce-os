from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.schemas.ai import ChatMessage

class LLMProvider(ABC):
    @abstractmethod
    def generate_chat_response(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None
    ) -> ChatMessage:
        """Generate response from LLM."""
        pass
