"""Standard Chat Completions HTTP adapter; no hidden provider fallback or free-tier claim.
A model/endpoint must support function tools. It is not a generic adapter for
provider-specific response fields or Responses-only models.
"""
import asyncio
import json
import httpx


class LLMClient:
    def __init__(self, settings):
        self.settings = settings
        if not settings.api_key or not settings.llm_model:
            raise ValueError('LLM mode requires LLM_MODEL and LLM_API_KEY (or OPENAI_API_KEY) in .env')
        base = settings.llm_base_url.rstrip('/')
        if not base.startswith(('https://', 'http://localhost:', 'http://127.0.0.1:')):
            raise ValueError('Use HTTPS for remote LLM endpoints')
        self.url = base + '/chat/completions'
        self.usage = {'input_tokens': 0, 'output_tokens': 0, 'calls': 0, 'http_attempts': 0}
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    async def close(self):
        await self.client.aclose()

    async def complete(self, messages, tools=None, required=False):
        payload = {'model': self.settings.llm_model, 'messages': messages}
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'required' if required else 'auto'
        for attempt in range(3):
            self.usage['http_attempts'] += 1
            try:
                response = await self.client.post(self.url, json=payload,
                    headers={'Authorization': 'Bearer ' + self.settings.api_key, 'Content-Type': 'application/json'})
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise RuntimeError('LLM network request failed after three attempts') from None
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            if response.is_error:
                # Never surface request headers, raw provider errors, or an API key.
                raise RuntimeError(f'LLM endpoint returned HTTP {response.status_code}; check model access, balance and endpoint compatibility.')
            body = response.json()
            if not body.get('choices'):
                raise RuntimeError('LLM endpoint returned no choices')
            usage = body.get('usage') or {}
            self.usage['input_tokens'] += int(usage.get('prompt_tokens', 0))
            self.usage['output_tokens'] += int(usage.get('completion_tokens', 0))
            self.usage['calls'] += 1
            message = body['choices'][0]['message']
            if not isinstance(message, dict):
                raise RuntimeError('Invalid LLM response format')
            return message
        raise RuntimeError('LLM request failed')

    def cost_estimate(self):
        inp, out = self.settings.llm_input_usd_per_million, self.settings.llm_output_usd_per_million
        if inp is None or out is None:
            return None
        return (self.usage['input_tokens'] * inp + self.usage['output_tokens'] * out) / 1_000_000


def function_schema(name, description, parameters):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': parameters}}


def decode_call(call):
    if call.get('type') != 'function' or not call.get('id'):
        raise ValueError('Invalid function-tool call')
    fn = call['function']
    args = json.loads(fn.get('arguments', '{}'))
    if not isinstance(args, dict):
        raise ValueError('Tool arguments must be a JSON object')
    return fn['name'], args
