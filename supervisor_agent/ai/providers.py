"""
AI Provider abstraction and implementations for multi-model support.
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from pydantic import BaseModel

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ModelCapability(Enum):
    """Model capabilities"""
    TEXT_GENERATION = "text_generation"
    CODE_ANALYSIS = "code_analysis"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    REASONING = "reasoning"
    FAST_RESPONSE = "fast_response"


class ModelTier(Enum):
    """Model performance and cost tiers"""
    FAST = "fast"      # Low cost, fast response
    BALANCED = "balanced"  # Medium cost, good performance
    PREMIUM = "premium"    # High cost, best performance


@dataclass
class ModelInfo:
    """Information about an AI model"""
    id: str
    name: str
    provider: str
    tier: ModelTier
    capabilities: List[ModelCapability]
    context_window: int
    max_output_tokens: int
    cost_per_input_token: float  # USD per 1K tokens
    cost_per_output_token: float  # USD per 1K tokens
    requests_per_minute: int
    supports_streaming: bool = True
    supports_function_calling: bool = False


class AIMessage(BaseModel):
    """AI message structure"""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict[str, Any] = {}


class AIResponse(BaseModel):
    """AI response structure"""
    content: str
    model: str
    provider: str
    usage: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    cost_estimate: float = 0.0
    response_time_ms: int = 0


class StreamingChunk(BaseModel):
    """Streaming response chunk"""
    content: str
    done: bool = False
    metadata: Dict[str, Any] = {}


class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
        self._models: Dict[str, ModelInfo] = {}
        
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name"""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider"""
        pass
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """Generate a single response"""
        pass
    
    @abstractmethod
    async def stream_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[StreamingChunk]:
        """Stream response chunks"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> Dict[str, ModelInfo]:
        """Get available models for this provider"""
        pass
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self._client:
            await self._client.aclose()


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url or "https://api.anthropic.com")
        
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    async def initialize(self) -> None:
        """Initialize Anthropic client"""
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            timeout=60.0
        )
        
        # Define available models
        self._models = {
            "claude-3-haiku-20240307": ModelInfo(
                id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                provider=self.provider_name,
                tier=ModelTier.FAST,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.FAST_RESPONSE
                ],
                context_window=200000,
                max_output_tokens=4096,
                cost_per_input_token=0.25,
                cost_per_output_token=1.25,
                requests_per_minute=1000,
                supports_streaming=True
            ),
            "claude-3-sonnet-20240229": ModelInfo(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=self.provider_name,
                tier=ModelTier.BALANCED,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.REASONING,
                    ModelCapability.VISION
                ],
                context_window=200000,
                max_output_tokens=4096,
                cost_per_input_token=3.0,
                cost_per_output_token=15.0,
                requests_per_minute=1000,
                supports_streaming=True
            ),
            "claude-3-opus-20240229": ModelInfo(
                id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                provider=self.provider_name,
                tier=ModelTier.PREMIUM,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.FUNCTION_CALLING
                ],
                context_window=200000,
                max_output_tokens=4096,
                cost_per_input_token=15.0,
                cost_per_output_token=75.0,
                requests_per_minute=1000,
                supports_streaming=True,
                supports_function_calling=True
            )
        }
    
    async def generate_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """Generate response from Claude"""
        start_time = time.time()
        
        # Convert messages to Claude format
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Prepare request
        request_data = {
            "model": model,
            "messages": claude_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            **kwargs
        }
        
        if system_message:
            request_data["system"] = system_message
        
        try:
            response = await self._client.post(
                f"{self.base_url}/v1/messages",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()
            
            # Calculate cost
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            
            model_info = self._models.get(model)
            cost = 0.0
            if model_info:
                cost = (
                    (input_tokens / 1000) * model_info.cost_per_input_token +
                    (output_tokens / 1000) * model_info.cost_per_output_token
                )
            
            response_time = int((time.time() - start_time) * 1000)
            
            return AIResponse(
                content=data["content"][0]["text"],
                model=model,
                provider=self.provider_name,
                usage=usage,
                cost_estimate=cost,
                response_time_ms=response_time
            )
            
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
    
    async def stream_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[StreamingChunk]:
        """Stream response from Claude"""
        # Convert messages to Claude format
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Prepare request
        request_data = {
            "model": model,
            "messages": claude_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        
        if system_message:
            request_data["system"] = system_message
        
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield StreamingChunk(content="", done=True)
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if "text" in delta:
                                    yield StreamingChunk(
                                        content=delta["text"],
                                        metadata={"event_type": data.get("type")}
                                    )
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            raise
    
    def get_available_models(self) -> Dict[str, ModelInfo]:
        """Get available Claude models"""
        return self._models.copy()


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url or "https://api.openai.com")
        
    @property
    def provider_name(self) -> str:
        return "openai"
    
    async def initialize(self) -> None:
        """Initialize OpenAI client"""
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
        
        # Define available models
        self._models = {
            "gpt-3.5-turbo": ModelInfo(
                id="gpt-3.5-turbo",
                name="GPT-3.5 Turbo",
                provider=self.provider_name,
                tier=ModelTier.FAST,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.FUNCTION_CALLING
                ],
                context_window=16385,
                max_output_tokens=4096,
                cost_per_input_token=0.5,
                cost_per_output_token=1.5,
                requests_per_minute=3500,
                supports_streaming=True,
                supports_function_calling=True
            ),
            "gpt-4": ModelInfo(
                id="gpt-4",
                name="GPT-4",
                provider=self.provider_name,
                tier=ModelTier.BALANCED,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.REASONING,
                    ModelCapability.FUNCTION_CALLING
                ],
                context_window=8192,
                max_output_tokens=4096,
                cost_per_input_token=30.0,
                cost_per_output_token=60.0,
                requests_per_minute=200,
                supports_streaming=True,
                supports_function_calling=True
            ),
            "gpt-4-turbo": ModelInfo(
                id="gpt-4-turbo",
                name="GPT-4 Turbo",
                provider=self.provider_name,
                tier=ModelTier.PREMIUM,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.FUNCTION_CALLING
                ],
                context_window=128000,
                max_output_tokens=4096,
                cost_per_input_token=10.0,
                cost_per_output_token=30.0,
                requests_per_minute=500,
                supports_streaming=True,
                supports_function_calling=True
            )
        }
    
    async def generate_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """Generate response from OpenAI"""
        start_time = time.time()
        
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request
        request_data = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }
        
        try:
            response = await self._client.post(
                f"{self.base_url}/v1/chat/completions",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()
            
            # Calculate cost
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            model_info = self._models.get(model)
            cost = 0.0
            if model_info:
                cost = (
                    (input_tokens / 1000) * model_info.cost_per_input_token +
                    (output_tokens / 1000) * model_info.cost_per_output_token
                )
            
            response_time = int((time.time() - start_time) * 1000)
            
            return AIResponse(
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider=self.provider_name,
                usage=usage,
                cost_estimate=cost,
                response_time_ms=response_time
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
    
    async def stream_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[StreamingChunk]:
        """Stream response from OpenAI"""
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request
        request_data = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield StreamingChunk(content="", done=True)
                            break
                        
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                if "content" in delta:
                                    yield StreamingChunk(
                                        content=delta["content"],
                                        metadata={"finish_reason": choices[0].get("finish_reason")}
                                    )
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            raise
    
    def get_available_models(self) -> Dict[str, ModelInfo]:
        """Get available OpenAI models"""
        return self._models.copy()


class LocalProvider(AIProvider):
    """Local/self-hosted model provider (Ollama, etc.)"""
    
    def __init__(self, api_key: str = "", base_url: str = "http://localhost:11434"):
        super().__init__(api_key, base_url)
        
    @property
    def provider_name(self) -> str:
        return "local"
    
    async def initialize(self) -> None:
        """Initialize local provider"""
        self._client = httpx.AsyncClient(timeout=60.0)
        
        # Define example local models
        self._models = {
            "llama2": ModelInfo(
                id="llama2",
                name="Llama 2 7B",
                provider=self.provider_name,
                tier=ModelTier.FAST,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS
                ],
                context_window=4096,
                max_output_tokens=2048,
                cost_per_input_token=0.0,  # Free for local
                cost_per_output_token=0.0,
                requests_per_minute=10,
                supports_streaming=True
            ),
            "codellama": ModelInfo(
                id="codellama",
                name="Code Llama 7B",
                provider=self.provider_name,
                tier=ModelTier.BALANCED,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_ANALYSIS
                ],
                context_window=16384,
                max_output_tokens=4096,
                cost_per_input_token=0.0,
                cost_per_output_token=0.0,
                requests_per_minute=5,
                supports_streaming=True
            )
        }
    
    async def generate_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """Generate response from local model"""
        start_time = time.time()
        
        # Convert to single prompt for Ollama
        prompt = self._convert_messages_to_prompt(messages)
        
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or 2048
            }
        }
        
        try:
            response = await self._client.post(
                f"{self.base_url}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()
            
            response_time = int((time.time() - start_time) * 1000)
            
            return AIResponse(
                content=data.get("response", ""),
                model=model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(data.get("response", "").split())
                },
                cost_estimate=0.0,  # Free for local
                response_time_ms=response_time
            )
            
        except Exception as e:
            logger.error(f"Local model API error: {str(e)}")
            raise
    
    async def stream_response(
        self,
        messages: List[AIMessage],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[StreamingChunk]:
        """Stream response from local model"""
        prompt = self._convert_messages_to_prompt(messages)
        
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or 2048
            }
        }
        
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield StreamingChunk(
                                content=data["response"],
                                done=data.get("done", False)
                            )
                            if data.get("done"):
                                break
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Local model streaming error: {str(e)}")
            raise
    
    def get_available_models(self) -> Dict[str, ModelInfo]:
        """Get available local models"""
        return self._models.copy()
    
    def _convert_messages_to_prompt(self, messages: List[AIMessage]) -> str:
        """Convert messages to a single prompt for local models"""
        prompt_parts = []
        
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)