from openai import OpenAI
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the repository root (two levels up from this file is the workspace, one level is local-server)  # noqa: E501
env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=str(env_path))

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise RuntimeError(f"OPENAI_API_KEY not found in environment or {env_path}")  # noqa: E501

client = OpenAI(api_key=api_key)

try:
    models = client.models.list()
    model_ids = []
    for model in models:
        # models may be returned as objects or dict-like; prefer attribute access if present  # noqa: E501
        model_id = getattr(model, 'id', None) or (model.get('id') if isinstance(model, dict) else None)  # noqa: E501
        if not model_id:
            continue
        lower = model_id.lower()

        # Exclude known non-chat/reasoning categories (images, embeddings, audio, tts, moderation, etc.)  # noqa: E501
        exclude_tokens = [
            'embedding', 'dall', 'image', 'whisper', 'tts', 'moderation', 'audio', 'codex', 'embed', 'omni-moderation'  # noqa: E501
        ]
        if any(tok in lower for tok in exclude_tokens):
            continue

        # Include tokens that indicate chat or reasoning models
        include_tokens = ['gpt', 'chat', 'davinci', 'o1', 'o3', 'o4', 'gpt-4', 'gpt-5']  # noqa: E501
        if any(tok in lower for tok in include_tokens) or lower.startswith('o'):  # noqa: E501
            model_ids.append(model_id)

    # Deduplicate and sort alphabetically
    unique_sorted = sorted(set(model_ids), key=lambda s: s.lower())
    for mid in unique_sorted:
        print(mid)
except Exception as e:
    raise RuntimeError(f"Failed to list OpenAI models: {e}")
