import random
import time
from typing import Any, Dict, List, Optional

# Attempt to import SDKs (graceful fallback if not installed)
try:
    import openai
    from openai import OpenAI
except ImportError:
    OpenAI = None
    openai = None

# TODO: Add google-generativeai or vertexai when implementing Gemini


class LLMProvider:
    """Abstract base class for LLM interactions."""

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self):
        if not OpenAI:
            raise ImportError("OpenAI SDK not installed. Run `pip install openai`")
        # Ensure OPENAI_API_KEY is set in environment
        self.client = OpenAI(
            base_url="http://localhost:11434/v1/",
            api_key="ollama",
            # api_key=os.environ.get("OPENAI_API_KEY")
        )

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemma-heretic",
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        messages: List of dicts, e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        tools: Optional tools array for function calling or computer use.
        Includes robust retry logic with exponential backoff and jitter for transient API issues.
        """
        kwargs = {
            "model": model,
            "messages": messages,
            # "temperature": temperature,
            "max_tokens": 128000,
        }
        if tools:
            kwargs["tools"] = tools

        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message
            except Exception as e:
                # Catch typical API errors (rate limits, timeouts, service outages)
                is_transient = False
                err_msg = str(e)

                # Check for standard rate limits or server errors
                if openai and isinstance(
                    e,
                    (
                        openai.RateLimitError,
                        openai.APIConnectionError,
                        openai.InternalServerError,
                    ),
                ):
                    is_transient = True
                elif (
                    "rate limit" in err_msg.lower()
                    or "timeout" in err_msg.lower()
                    or "502" in err_msg
                    or "503" in err_msg
                    or "500" in err_msg
                ):
                    is_transient = True

                if is_transient and attempt < max_retries - 1:
                    # Exponential backoff with jitter: base_delay * 2^attempt + dynamic variance
                    delay = (base_delay * (2**attempt)) + random.uniform(0.5, 1.5)
                    print(
                        f"[LLM Retry] Transient error encountered (Attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    print(
                        f"[LLM Error] Non-recoverable or terminal API error on attempt {attempt + 1}: {e}"
                    )
                    raise e


class GeminiProvider(LLMProvider):
    def __init__(self):
        # Setup Gemini API key
        pass

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        Translates OpenAI style messages to Gemini format and calls the API.
        """
        raise NotImplementedError(
            "Gemini provider not yet implemented. Please use OpenAIProvider."
        )


def get_llm(provider_name: str = "openai") -> LLMProvider:
    if provider_name.lower() == "openai":
        return OpenAIProvider()
    elif provider_name.lower() == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
