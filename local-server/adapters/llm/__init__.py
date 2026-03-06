"""
LLM service adapters for Context Studio.

This package contains adapters that implement the LLMProvider port
defined in domain/extraction/ports.py.

The LLMProvider port defines:
- complete(prompt: str, context: str) -> LLMResponse: Generate completion from LLM

Adapter implementations may use:
- OpenAI API (GPT-4, GPT-3.5-turbo)
- Anthropic API (Claude)
- Local LLMs (LLaMA, Mistral via ollama or vLLM)
- Azure OpenAI

Per rearchitecture/architecture_design.md §5.4, the current llm/ directory
contains the implementation. This adapter layer wraps that implementation
to conform to the domain port contract.

LLMResponse includes:
- completion: str (the generated text)
- stop_reason: str (full / max_tokens / stop_sequence)
- usage: dict (input_tokens, output_tokens, total_tokens)
- metadata: dict (model, temperature, top_p, etc.)
"""
