"""
OpenRouter client for the AI cog.

Talks to OpenRouter's OpenAI-compatible chat-completions endpoint and wraps it
in a small google-genai-shaped compatibility layer (`types.Part`,
`types.Content`, chat sessions with `send_message`) so the rest of the cog is
unchanged by the provider swap.

Reasoning ("thinking") models are supported end to end:
  * the `reasoning` request field is sent per model tier (see REASONING),
  * `reasoning` / `reasoning_details` that come back are exposed on the response
    and stored verbatim in history — OpenRouter requires the details to be
    echoed back for the model to keep its own chain of thought across
    tool-call round trips.
"""
import asyncio
import inspect
import json
import logging
import re
import typing

import aiohttp

from config import (
    AI_MAX_CONTEXT_TOKENS,
    AI_MAX_TOOL_RESULT_CHARS,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_APP_URL,
    OPENROUTER_BASE_URL,
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_TIMEOUT,
)

try:  # py3.10+: `int | None` annotations
    from types import UnionType
except ImportError:  # pragma: no cover
    UnionType = None

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# genai-shaped content primitives
# ---------------------------------------------------------------------------
class FunctionCall:
    """A tool call requested by the model."""

    def __init__(self, name: str, args: dict = None, id: str = None):
        self.name = name
        self.args = args or {}
        self.id = id

    def __repr__(self):
        return f"FunctionCall(name={self.name!r}, args={self.args!r})"


class FunctionResponse:
    """The result we hand back for a tool call."""

    def __init__(self, name: str, response: dict = None, id: str = None):
        self.name = name
        self.response = response or {}
        self.id = id

    def __repr__(self):
        return f"FunctionResponse(name={self.name!r})"


class Part:
    """One piece of a message: text, a tool call, a tool result, or an image."""

    def __init__(self, text: str = None, function_call: FunctionCall = None,
                 function_response: FunctionResponse = None, thought: str = None,
                 inline_data: dict = None, image_url: str = None):
        self.text = text
        self.function_call = function_call
        self.function_response = function_response
        self.thought = thought
        self.inline_data = inline_data
        self.image_url = image_url

    @classmethod
    def from_text(cls, text: str):
        return cls(text=text)

    @classmethod
    def from_function_response(cls, name: str, response: dict, id: str = None):
        return cls(function_response=FunctionResponse(name=name, response=response, id=id))

    @classmethod
    def from_function_call(cls, name: str, args: dict, id: str = None):
        return cls(function_call=FunctionCall(name=name, args=args, id=id))

    @classmethod
    def from_image_url(cls, url: str):
        """An image the model looks at directly (http(s) or a data: URI)."""
        return cls(image_url=url)

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str = "image/jpeg"):
        import base64
        return cls(image_url=f"data:{mime_type};base64,{base64.b64encode(data).decode()}")

    def __repr__(self):
        if self.function_call:
            return f"Part({self.function_call!r})"
        if self.function_response:
            return f"Part({self.function_response!r})"
        if self.image_url:
            return f"Part(image_url={self.image_url[:40]!r})"
        return f"Part(text={(self.text or '')[:40]!r})"


class Content:
    """A single conversation turn. `role` is 'user' or 'model' (genai naming)."""

    def __init__(self, role: str = "user", parts: list = None):
        self.role = role
        self.parts = parts or []


class Candidate:
    def __init__(self, content: Content, finish_reason: str = None):
        self.content = content
        self.finish_reason = finish_reason


class types:  # noqa: N801 - deliberately mimics `google.genai.types`
    """Namespace mirroring the small slice of `google.genai.types` we used."""

    Part = Part
    Content = Content
    Candidate = Candidate
    FunctionCall = FunctionCall
    FunctionResponse = FunctionResponse


class Response:
    """A single model reply, shaped like a genai GenerateContentResponse."""

    def __init__(self, parts: list, reasoning: str = "", raw: dict = None,
                 finish_reason: str = None, model: str = None):
        self.candidates = [Candidate(Content(role="model", parts=parts), finish_reason)]
        self.text = "".join(p.text for p in parts if p.text) or None
        self.reasoning = reasoning or ""
        self.raw = raw or {}
        self.model = model
        self.usage = (raw or {}).get('usage')

    @property
    def function_calls(self):
        return [p.function_call for p in self.candidates[0].content.parts if p.function_call]


class LLMError(RuntimeError):
    """Raised when OpenRouter refuses or fails a request."""


# ---------------------------------------------------------------------------
# Python function -> JSON tool schema
# ---------------------------------------------------------------------------
_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

_SCHEMA_CACHE = {}


def _annotation_to_schema(ann) -> dict:
    """Best-effort JSON-Schema for a type hint. Unknown types degrade to string."""
    if ann is inspect.Parameter.empty or ann is None:
        return {"type": "string"}

    origin = typing.get_origin(ann)

    if origin is typing.Union or (UnionType is not None and origin is UnionType):
        inner = [a for a in typing.get_args(ann) if a is not type(None)]
        return _annotation_to_schema(inner[0]) if inner else {"type": "string"}

    if origin in (list, set, tuple, frozenset):
        args = typing.get_args(ann)
        item = _annotation_to_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item}

    if origin is dict:
        return {"type": "object"}

    if isinstance(ann, str):  # unresolved 'from __future__ import annotations' hint
        return {"type": _JSON_TYPES.get({'str': str, 'int': int, 'float': float, 'bool': bool}.get(ann), "string")}

    return {"type": _JSON_TYPES.get(ann, "string")}


def _parse_docstring(doc: str) -> tuple[str, dict]:
    """Split a Google-style docstring into (description, {param: description})."""
    if not doc:
        return "", {}

    doc = inspect.cleandoc(doc)
    split = re.split(r"\n\s*(?:Args|Arguments|Parameters)\s*:\s*\n", doc, maxsplit=1)
    description = split[0].strip()
    params = {}

    if len(split) > 1:
        body = re.split(r"\n\s*(?:Returns|Return|Raises|Yields|Examples?|Notes?)\s*:", split[1])[0]
        current = None
        for line in body.split("\n"):
            match = re.match(r"\s*(\*{0,2}[A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:\s*(.*)", line)
            if match:
                current = match.group(1).lstrip("*")
                params[current] = match.group(2).strip()
            elif current and line.strip():
                params[current] += " " + line.strip()

    return description, params


def build_tool_schema(func) -> dict:
    """Convert a Python tool function into an OpenAI-style tool definition."""
    cached = _SCHEMA_CACHE.get(func)
    if cached:
        return cached

    description, param_docs = _parse_docstring(func.__doc__)
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}

    properties = {}
    required = []

    for name, param in inspect.signature(func).parameters.items():
        if param.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        if name in ('self', 'cls'):
            continue

        schema = _annotation_to_schema(hints.get(name, param.annotation))
        doc = param_docs.get(name)
        if doc:
            schema['description'] = doc
        properties[name] = schema

        if param.default is inspect.Parameter.empty:
            required.append(name)

    definition = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description or func.__name__.replace('_', ' '),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
    _SCHEMA_CACHE[func] = definition
    return definition


def build_tool_schemas(funcs) -> list:
    return [build_tool_schema(f) for f in funcs or []]


# ---------------------------------------------------------------------------
# Reasoning config
# ---------------------------------------------------------------------------
def reasoning_config(effort: str):
    """
    Translate an effort string into OpenRouter's `reasoning` field.

    'none'/'off'/'' disables thinking; anything else is passed as an effort
    level (models that only understand a boolean toggle just see `enabled`).
    """
    effort = (effort or "").strip().lower()
    if effort in ("", "none", "off", "false", "disabled"):
        return {"enabled": False, "exclude": True}
    if effort not in ("low", "medium", "high"):
        effort = "medium"
    return {"enabled": True, "effort": effort}


# ---------------------------------------------------------------------------
# Context accounting
# ---------------------------------------------------------------------------
CHARS_PER_TOKEN = 4       # good enough for budgeting; we are not billing on it
IMAGE_TOKEN_COST = 800    # rough per-image cost, since the URL itself is tiny


def estimate_tokens(obj) -> int:
    """Rough token count for a message, message list, or tool schema."""
    if isinstance(obj, list):
        return sum(estimate_tokens(o) for o in obj)

    images = 0
    if isinstance(obj, dict) and isinstance(obj.get('content'), list):
        images = sum(1 for block in obj['content'] if isinstance(block, dict)
                     and block.get('type') == 'image_url')

    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    return len(text) // CHARS_PER_TOKEN + images * IMAGE_TOKEN_COST


def truncate_tool_result(text: str, limit: int = None) -> str:
    """Cap a tool result so one huge page can't dominate the rest of the chat."""
    limit = limit or AI_MAX_TOOL_RESULT_CHARS
    if not isinstance(text, str) or len(text) <= limit:
        return text
    dropped = len(text) - limit
    return text[:limit] + f"\n\n[... truncated, {dropped} more characters. Narrow the query if you need the rest.]"


def _user_content(text_bits: list, image_urls: list):
    """Build message content: a plain string, or blocks when images are present."""
    text = "\n".join(b for b in text_bits if b)
    if not image_urls:
        return text
    blocks = [{"type": "image_url", "image_url": {"url": url}} for url in image_urls]
    if text:
        blocks.insert(0, {"type": "text", "text": text})
    return blocks


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }


async def _post(payload: dict) -> dict:
    """POST a chat-completion, retrying transient failures."""
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY is not set.")

    url = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    timeout = aiohttp.ClientTimeout(total=OPENROUTER_TIMEOUT)
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=_headers(), json=payload) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        last_error = f"HTTP {resp.status}: {body[:400]}"
                        if resp.status in RETRY_STATUSES and attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        raise LLMError(last_error)
                    data = json.loads(body)
        except asyncio.TimeoutError:
            last_error = "Request to OpenRouter timed out."
            if attempt < MAX_RETRIES - 1:
                continue
            raise LLMError(last_error)
        except aiohttp.ClientError as e:
            last_error = f"Network error talking to OpenRouter: {e}"
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise LLMError(last_error)

        # OpenRouter reports upstream failures inside a 200 body too
        if isinstance(data.get('error'), dict):
            message = data['error'].get('message', 'Unknown provider error')
            code = data['error'].get('code')
            if code in RETRY_STATUSES and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise LLMError(f"OpenRouter error ({code}): {message}")

        return data

    raise LLMError(last_error or "OpenRouter request failed.")


def _message_to_parts(message: dict) -> tuple[list, str]:
    """Turn an API assistant message into (parts, reasoning_text)."""
    parts = []
    reasoning = message.get('reasoning') or ""

    if not reasoning:
        # Some providers only fill reasoning_details
        chunks = []
        for detail in message.get('reasoning_details') or []:
            text = detail.get('text') or detail.get('summary') or ""
            if text:
                chunks.append(text)
        reasoning = "\n".join(chunks)

    if reasoning:
        parts.append(Part(thought=reasoning))

    content = message.get('content')
    if isinstance(content, list):  # some providers return content blocks
        content = "".join(b.get('text', '') for b in content if isinstance(b, dict))
    if content:
        parts.append(Part(text=content))

    for call in message.get('tool_calls') or []:
        fn = call.get('function') or {}
        raw_args = fn.get('arguments') or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse tool arguments for {fn.get('name')}: {raw_args[:200]}")
            args = {}
        if not isinstance(args, dict):
            args = {}
        parts.append(Part(function_call=FunctionCall(name=fn.get('name', ''), args=args, id=call.get('id'))))

    return parts, reasoning


# ---------------------------------------------------------------------------
# Chat session
# ---------------------------------------------------------------------------
class ChatSession:
    """
    Stateful chat over OpenRouter.

    History is kept in raw OpenAI message form so tool calls and reasoning
    details survive round trips; `send_message` accepts either a plain string
    or a list of `Part`s (which is how tool results come back from the cog).
    """

    def __init__(self, model: str, history: list = None, system_instruction: str = None,
                 tools: list = None, reasoning: dict = None, temperature: float = None,
                 max_tokens: int = None, extra_body: dict = None):
        self.model = model
        self.model_name = model
        self.system_instruction = system_instruction
        self.tool_schemas = build_tool_schemas(tools)
        self.reasoning = reasoning
        self.temperature = temperature
        self.max_tokens = max_tokens or OPENROUTER_MAX_TOKENS
        self.extra_body = extra_body or {}

        self.messages = _normalize_history(history)
        self.last_reasoning = ""
        self.reasoning_log = []
        self._pending_tool_calls = []  # [{'id': ..., 'name': ...}] awaiting results

    # -- history ---------------------------------------------------------
    @property
    def history(self) -> list:
        return self.messages

    @property
    def _curated_history(self) -> list:
        return self.messages

    def _append_user_content(self, content):
        """Accepts a string, a Part, a Content, or a list of those."""
        if isinstance(content, str):
            self.messages.append({"role": "user", "content": content})
            return

        items = content if isinstance(content, (list, tuple)) else [content]
        text_bits = []
        image_urls = []

        for item in items:
            if isinstance(item, str):
                text_bits.append(item)
            elif isinstance(item, Content):
                self.messages.extend(_content_to_messages(item))
            elif isinstance(item, Part):
                if item.function_response is not None:
                    self.messages.append(self._tool_message(item.function_response))
                elif item.image_url:
                    image_urls.append(item.image_url)
                elif item.text:
                    text_bits.append(item.text)
            else:
                text_bits.append(str(item))

        if text_bits or image_urls:
            self.messages.append({"role": "user", "content": _user_content(text_bits, image_urls)})

    def _tool_message(self, fr: FunctionResponse) -> dict:
        """Match a tool result to the call it answers, by id then by name."""
        call_id = fr.id
        if not call_id:
            match = next((c for c in self._pending_tool_calls if c['name'] == fr.name), None)
            match = match or (self._pending_tool_calls[0] if self._pending_tool_calls else None)
            call_id = match['id'] if match else f"call_{fr.name}"
            if match:
                self._pending_tool_calls.remove(match)
        else:
            self._pending_tool_calls = [c for c in self._pending_tool_calls if c['id'] != call_id]

        result = fr.response.get('result', fr.response) if isinstance(fr.response, dict) else fr.response
        if not isinstance(result, str):
            result = json.dumps(result, default=str)
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": fr.name,
            "content": truncate_tool_result(result),
        }

    def _close_unanswered_tool_calls(self):
        """The API rejects an assistant tool call with no matching tool message."""
        for call in self._pending_tool_calls:
            self.messages.append({
                "role": "tool",
                "tool_call_id": call['id'],
                "name": call['name'],
                "content": "Tool call was not executed.",
            })
        self._pending_tool_calls = []

    def _history_budget(self) -> int:
        """Tokens left for the conversation after the fixed costs of a request."""
        fixed = estimate_tokens(self.tool_schemas)
        if self.system_instruction:
            fixed += estimate_tokens(self.system_instruction)
        fixed += self.max_tokens  # room for the reply itself
        return max(2000, AI_MAX_CONTEXT_TOKENS - fixed)

    def _trim_history(self):
        """
        Drop the oldest turns once the conversation outgrows its budget.

        Tool results are the bulk of it (web pages, file dumps) and paying to
        resend them forever is pointless. Two rules: a 'tool' message may never
        lead the list (it would be orphaned from the call it answers), and the
        most recent turn always survives, however big it is.
        """
        budget = self._history_budget()
        total = estimate_tokens(self.messages)
        dropped = 0

        while total > budget and len(self.messages) > 1:
            total -= estimate_tokens(self.messages.pop(0))
            dropped += 1
            while len(self.messages) > 1 and self.messages[0].get('role') == 'tool':
                total -= estimate_tokens(self.messages.pop(0))
                dropped += 1

        if dropped:
            logger.info(f"Context trim: dropped {dropped} messages, ~{total} tokens left of {budget}")

    # -- request ---------------------------------------------------------
    def _build_payload(self) -> dict:
        self._trim_history()
        messages = list(self.messages)
        if self.system_instruction:
            messages = [{"role": "system", "content": self.system_instruction}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if self.tool_schemas:
            payload['tools'] = self.tool_schemas
            payload['tool_choice'] = "auto"
        if self.reasoning:
            payload['reasoning'] = self.reasoning
        if self.temperature is not None:
            payload['temperature'] = self.temperature
        payload.update(self.extra_body)
        return payload

    async def send_message(self, content) -> Response:
        """Append `content`, call the model, store its reply, return a Response."""
        self._append_user_content(content)
        self._close_unanswered_tool_calls()

        payload = self._build_payload()
        logger.debug(f"Request ~{estimate_tokens(payload['messages'])} tokens over {len(payload['messages'])} messages")
        data = await _post(payload)

        choices = data.get('choices') or []
        if not choices:
            raise LLMError("OpenRouter returned no choices.")

        choice = choices[0]
        message = choice.get('message') or {}
        parts, reasoning = _message_to_parts(message)

        # Store the assistant turn verbatim (reasoning_details included) so the
        # model keeps its chain of thought across tool-call round trips.
        assistant_message = {"role": "assistant", "content": message.get('content') or ""}
        if message.get('tool_calls'):
            assistant_message['tool_calls'] = message['tool_calls']
        if message.get('reasoning_details'):
            assistant_message['reasoning_details'] = message['reasoning_details']
        elif message.get('reasoning'):
            assistant_message['reasoning'] = message['reasoning']
        self.messages.append(assistant_message)

        self._pending_tool_calls = [
            {'id': c.get('id'), 'name': (c.get('function') or {}).get('name', '')}
            for c in message.get('tool_calls') or []
        ]

        if reasoning:
            self.last_reasoning = reasoning
            self.reasoning_log.append(reasoning)

        usage = data.get('usage') or {}
        logger.info(
            f"OpenRouter {data.get('model', self.model)} | "
            f"finish={choice.get('finish_reason')} | tools={len(self._pending_tool_calls)} | "
            f"tokens={usage.get('prompt_tokens')}->{usage.get('completion_tokens')} | "
            f"reasoning_chars={len(reasoning)}"
        )

        return Response(
            parts=parts,
            reasoning=reasoning,
            raw=data,
            finish_reason=choice.get('finish_reason'),
            model=data.get('model', self.model),
        )


def _content_to_messages(item: Content) -> list:
    """Convert one genai Content turn into OpenAI message(s)."""
    role = "assistant" if item.role in ("model", "assistant") else "user"
    messages = []
    text_bits = []
    image_urls = []

    for part in item.parts or []:
        if part.function_response is not None:
            fr = part.function_response
            result = fr.response.get('result', fr.response) if isinstance(fr.response, dict) else fr.response
            messages.append({
                "role": "tool",
                "tool_call_id": fr.id or f"call_{fr.name}",
                "name": fr.name,
                "content": result if isinstance(result, str) else json.dumps(result, default=str),
            })
        elif part.function_call is not None:
            fc = part.function_call
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": fc.id or f"call_{fc.name}",
                    "type": "function",
                    "function": {"name": fc.name, "arguments": json.dumps(fc.args, default=str)},
                }],
            })
        elif part.image_url:
            image_urls.append(part.image_url)
        elif part.text:
            text_bits.append(part.text)

    if text_bits or image_urls:
        messages.insert(0, {"role": role, "content": _user_content(text_bits, image_urls)})
    return messages


def _flatten_old_images(message: dict) -> dict:
    """
    Replace images in carried-over history with a text note.

    Discord attachment URLs are signed and expire, and re-sending every image
    of the conversation on every turn is a waste — the model already described
    what it saw in its reply.
    """
    content = message.get('content')
    if not isinstance(content, list):
        return message

    text_bits = []
    images = 0
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'image_url':
            images += 1
        elif block.get('type') == 'text' and block.get('text'):
            text_bits.append(block['text'])

    if images:
        text_bits.append(f"[{images} image(s) sent earlier in the conversation]")
    return {**message, 'content': "\n".join(text_bits)}


def _normalize_history(history) -> list:
    """Accept genai Content objects, raw OpenAI dicts, or a mix."""
    messages = []
    for item in history or []:
        if isinstance(item, Content):
            messages.extend(_flatten_old_images(m) for m in _content_to_messages(item))
        elif isinstance(item, dict):
            messages.append(_flatten_old_images(item))
    return messages


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class _Chats:
    def create(self, model: str, history: list = None, system_instruction: str = None,
               tools: list = None, reasoning: dict = None, temperature: float = None,
               max_tokens: int = None, **kwargs) -> ChatSession:
        return ChatSession(
            model=model,
            history=history,
            system_instruction=system_instruction,
            tools=tools,
            reasoning=reasoning,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=kwargs.get('extra_body'),
        )


class OpenRouterClient:
    """Thin entry point: `client.chats.create(...)` / `client.generate(...)`."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.chats = _Chats()
        self.aio = self  # the old genai code reached for `.aio`

    @property
    def models(self):
        return self


async def generate(model: str, messages: list, tools: list = None, reasoning: dict = None,
                   temperature: float = None, max_tokens: int = None) -> Response:
    """One-shot completion for callers that don't need a session (router, vision)."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or OPENROUTER_MAX_TOKENS,
    }
    if tools:
        payload['tools'] = build_tool_schemas(tools)
    if reasoning:
        payload['reasoning'] = reasoning
    if temperature is not None:
        payload['temperature'] = temperature

    data = await _post(payload)
    choices = data.get('choices') or []
    if not choices:
        raise LLMError("OpenRouter returned no choices.")

    parts, reasoning_text = _message_to_parts(choices[0].get('message') or {})
    return Response(
        parts=parts,
        reasoning=reasoning_text,
        raw=data,
        finish_reason=choices[0].get('finish_reason'),
        model=data.get('model', model),
    )
