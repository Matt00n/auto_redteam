import os
import json
from typing import List, Dict, Any, Optional

# Attempt to import SDKs (graceful fallback if not installed)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# TODO: Add google-generativeai or vertexai when implementing Gemini


class LLMProvider:
    """Abstract base class for LLM interactions."""
    def generate(self, messages: List[Dict[str, str]], model: str, temperature: float = 0.7, tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self):
        if not OpenAI:
            raise ImportError("OpenAI SDK not installed. Run `pip install openai`")
        # Ensure OPENAI_API_KEY is set in environment
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def generate(self, messages: List[Dict[str, str]], model: str = "gpt-4o", temperature: float = 0.7, tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """
        messages: List of dicts, e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        tools: Optional tools array for function calling or computer use.
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message


class GeminiProvider(LLMProvider):
    def __init__(self):
        # Setup Gemini API key
        pass

    def generate(self, messages: List[Dict[str, str]], model: str = "gemini-1.5-pro", temperature: float = 0.7, tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """
        Translates OpenAI style messages to Gemini format and calls the API.
        """
        raise NotImplementedError("Gemini provider not yet implemented. Please use OpenAIProvider.")


def get_llm(provider_name: str = "openai") -> LLMProvider:
    if provider_name.lower() == "openai":
        return OpenAIProvider()
    elif provider_name.lower() == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
