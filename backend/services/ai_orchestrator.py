import aiohttp
import asyncio
import json
import time
import os
import re
from typing import Optional
from config import FREE_AI_PROVIDERS, TASK_ROUTING, COST_OPTIMIZATION_ORDER, SSRF_BLOCKED_HOSTS
from urllib.parse import urlparse

class AIOrchestrator:
    def __init__(self):
        self.providers = FREE_AI_PROVIDERS
        self.task_routing = TASK_ROUTING
        self.optimization_order = COST_OPTIMIZATION_ORDER
        self._provider_latency = {}
        self._provider_failures = {}
        self._provider_cooldown = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_available_keys(self, user_api_keys: dict) -> dict:
        available = {}
        for provider_id, config in self.providers.items():
            env_key = os.environ.get(config["api_key_env"], "") if config.get("api_key_env") else ""
            user_key = user_api_keys.get(provider_id, "")
            key = user_key or env_key
            if key or not config.get("api_key_env"):
                if provider_id == "ollama_local":
                    import socket
                    try:
                        s = socket.create_connection(("127.0.0.1", 11434), timeout=1)
                        s.close()
                    except (ConnectionRefusedError, OSError, socket.timeout):
                        continue
                available[provider_id] = key or "local"
        return available

    def _select_provider(self, task_type: str, available_keys: dict) -> list:
        preferred = self.task_routing.get(task_type, ["groq", "deepseek", "google_gemini"])
        now = time.time()
        ranked = []
        for provider_id in preferred:
            if provider_id not in available_keys:
                continue
            if provider_id in self._provider_cooldown:
                if now - self._provider_cooldown[provider_id] < 60:
                    continue
            failures = self._provider_failures.get(provider_id, 0)
            latency = self._provider_latency.get(provider_id, 1000)
            score = 100 - (failures * 20) - (latency / 100)
            if provider_id in self.optimization_order:
                score += (len(self.optimization_order) - self.optimization_order.index(provider_id)) * 2
            ranked.append((provider_id, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        result = [p for p, _ in ranked if p in available_keys]
        fallback = [p for p in self.optimization_order if p in available_keys and p not in result]
        return result + fallback

    def _is_safe_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            local_hosts = {"127.0.0.1", "localhost", "::1"}
            if hostname in local_hosts and parsed.port == 11434:
                return True
            for blocked in SSRF_BLOCKED_HOSTS:
                if "/" in blocked:
                    continue
                if hostname == blocked or hostname.endswith("." + blocked):
                    return False
            if parsed.scheme not in ("http", "https"):
                return False
            import ipaddress
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
            except ValueError:
                pass
            return True
        except Exception:
            return False

    async def _call_openai_compatible(self, url: str, api_key: str, model: str, messages: list, max_tokens: int = 4096) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key and api_key != "local":
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7}
        session = await self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    return {"success": False, "error": f"Resposta não-JSON: {text[:200]}", "model": model}
                if resp.status == 200:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    return {
                        "success": True, "content": content,
                        "tokens_input": usage.get("prompt_tokens", 0),
                        "tokens_output": usage.get("completion_tokens", 0),
                        "model": model
                    }
                else:
                    error_msg = data.get("error", {}).get("message", str(data))
                    return {"success": False, "error": error_msg, "model": model}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "model": model}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _call_google_gemini(self, api_key: str, model: str, messages: list) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]

        payload = {}
        if system_msgs:
            payload["systemInstruction"] = {"parts": [{"text": "\n".join(m["content"] for m in system_msgs)}]}

        contents = []
        for msg in user_msgs:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        payload["contents"] = contents

        session = await self._get_session()
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    return {"success": False, "error": "Resposta não-JSON do Gemini", "model": model}
                if resp.status == 200:
                    content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    usage = data.get("usageMetadata", {})
                    return {
                        "success": True, "content": content,
                        "tokens_input": usage.get("promptTokenCount", 0),
                        "tokens_output": usage.get("candidatesTokenCount", 0),
                        "model": model
                    }
                else:
                    error_msg = data.get("error", {}).get("message", str(data))
                    return {"success": False, "error": error_msg, "model": model}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "model": model}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _call_cohere(self, api_key: str, model: str, messages: list) -> dict:
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] == "user"]

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "message": user_msgs[-1]["content"] if user_msgs else "",
        }
        if system_msgs:
            preamble = "\n".join(m["content"] for m in system_msgs)
            payload["preamble"] = preamble

        session = await self._get_session()
        try:
            async with session.post("https://api.cohere.ai/v2/chat", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    return {"success": False, "error": "Resposta não-JSON do Cohere", "model": model}
                if resp.status == 200:
                    content = data.get("message", {}).get("content", [{}])[0].get("text", "")
                    return {"success": True, "content": content, "tokens_input": 0, "tokens_output": 0, "model": model}
                else:
                    error_msg = data.get("message", str(data))
                    return {"success": False, "error": error_msg, "model": model}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "model": model}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _call_huggingface(self, api_key: str, model: str, messages: list) -> dict:
        url = f"https://api-inference.huggingface.co/models/{model}"
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] == "user"]

        prompt_parts = []
        if system_msgs:
            prompt_parts.append("<|system|>\n" + "\n".join(m["content"] for m in system_msgs))
        for m in user_msgs:
            role_tag = "user" if m["role"] == "user" else "assistant"
            prompt_parts.append(f"<|{role_tag}|>\n{m['content']}")
        prompt = "\n".join(prompt_parts) + "\n<|assistant|>\n"

        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 4096, "temperature": 0.7, "return_full_text": False}}
        session = await self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    return {"success": False, "error": "Resposta não-JSON do HuggingFace", "model": model}
                if resp.status == 200:
                    if isinstance(data, list) and len(data) > 0:
                        content = data[0].get("generated_text", "")
                    else:
                        content = str(data)
                    return {"success": True, "content": content, "tokens_input": 0, "tokens_output": 0, "model": model}
                else:
                    return {"success": False, "error": str(data), "model": model}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "model": model}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _call_cloudflare(self, api_key: str, account_id: str, model: str, messages: list) -> dict:
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/{model}"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        payload = {"messages": [{"role": "user", "content": prompt}]}
        session = await self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    return {"success": False, "error": "Resposta não-JSON do Cloudflare", "model": model}
                if data.get("success"):
                    content = data.get("result", {}).get("response", "")
                    return {"success": True, "content": content, "tokens_input": 0, "tokens_output": 0, "model": model}
                else:
                    return {"success": False, "error": str(data), "model": model}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "model": model}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _call_provider(self, provider_id: str, api_key: str, messages: list, model: str = None) -> dict:
        config = self.providers[provider_id]
        if not model:
            model = config["models"][0]
        start = time.time()
        api_type = config.get("api_type", "openai")
        try:
            if api_type == "gemini":
                result = await self._call_google_gemini(api_key, model, messages)
            elif api_type == "huggingface":
                result = await self._call_huggingface(api_key, model, messages)
            elif api_type == "cohere":
                result = await self._call_cohere(api_key, model, messages)
            elif api_type == "cloudflare":
                account_id = os.environ.get("CF_ACCOUNT_ID", "")
                result = await self._call_cloudflare(api_key, account_id, model, messages)
            else:
                result = await self._call_openai_compatible(config["url"], api_key, model, messages)

            elapsed = (time.time() - start) * 1000
            self._provider_latency[provider_id] = elapsed
            if result["success"]:
                self._provider_failures[provider_id] = 0
            else:
                self._provider_failures[provider_id] = self._provider_failures.get(provider_id, 0) + 1
                if self._provider_failures[provider_id] >= 3:
                    self._provider_cooldown[provider_id] = time.time()
            result["latency_ms"] = int(elapsed)
            result["provider"] = provider_id
            return result
        except asyncio.TimeoutError:
            elapsed = (time.time() - start) * 1000
            self._provider_failures[provider_id] = self._provider_failures.get(provider_id, 0) + 1
            self._provider_cooldown[provider_id] = time.time()
            return {"success": False, "error": "Timeout", "model": model, "provider": provider_id, "latency_ms": int(elapsed)}
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._provider_failures[provider_id] = self._provider_failures.get(provider_id, 0) + 1
            return {"success": False, "error": str(e), "model": model, "provider": provider_id, "latency_ms": int(elapsed)}

    async def execute_task(self, task_type: str, messages: list, user_api_keys: dict, preferred_model: str = None, force_provider: str = None) -> dict:
        available = self._get_available_keys(user_api_keys)
        if not available:
            return {"success": False, "error": "Nenhuma API key configurada. Adicione suas chaves de API em Configurações.", "content": "", "provider": None, "model": None, "tokens_input": 0, "tokens_output": 0, "latency_ms": 0}
        if force_provider and force_provider in available:
            fallback_order = self._select_provider(task_type, available)
            provider_order = [force_provider] + [p for p in fallback_order if p != force_provider]
        else:
            provider_order = self._select_provider(task_type, available)
        if not provider_order:
            return {"success": False, "error": "Nenhum provedor disponível", "content": "", "provider": None, "model": None, "tokens_input": 0, "tokens_output": 0, "latency_ms": 0}
        last_error = None
        for provider_id in provider_order:
            if provider_id not in available:
                continue
            config = self.providers[provider_id]
            models_to_try = []
            if preferred_model and preferred_model in config["models"]:
                models_to_try.append(preferred_model)
            for m in config["models"]:
                if m not in models_to_try:
                    models_to_try.append(m)
            for model in models_to_try:
                result = await self._call_provider(provider_id, available[provider_id], messages, model)
                if result["success"]:
                    if force_provider and provider_id != force_provider:
                        result["fallback_note"] = f"{force_provider} indisponível/sem saldo. Usando {provider_id} automaticamente."
                    return result
                last_error = result.get("error", "Unknown error")
                if "rate" in str(last_error).lower() or "429" in str(last_error):
                    continue
                break
        return {"success": False, "error": f"Todos os provedores falharam. Último erro: {last_error}", "content": "", "provider": provider_order[0] if provider_order else None, "model": None, "tokens_input": 0, "tokens_output": 0, "latency_ms": 0}

    async def execute_task_stream(self, task_type: str, messages: list, user_api_keys: dict, preferred_model: str = None, force_provider: str = None):
        available = self._get_available_keys(user_api_keys)
        if not available:
            yield {"chunk": "", "error": "Nenhuma API key configurada.", "done": True}
            return
        if force_provider and force_provider in available:
            fallback_order = self._select_provider(task_type, available)
            provider_order = [force_provider] + [p for p in fallback_order if p != force_provider]
        else:
            provider_order = self._select_provider(task_type, available)
        if not provider_order:
            yield {"chunk": "", "error": "Nenhum provedor disponível.", "done": True}
            return
        last_error = None
        fallback_used = False
        for provider_id in provider_order:
            if provider_id not in available:
                continue
            config = self.providers[provider_id]
            models_to_try = []
            if preferred_model and preferred_model in config["models"]:
                models_to_try.append(preferred_model)
            for m in config["models"]:
                if m not in models_to_try:
                    models_to_try.append(m)
            for model in models_to_try:
                try:
                    result = await self._call_provider_stream(provider_id, available[provider_id], messages, model)
                    if result.get("success"):
                    if force_provider and provider_id != force_provider and not fallback_used:
                        yield {"chunk": f"[{force_provider} indisponível/sem saldo — usando {provider_id}]\n\n", "done": False}
                            fallback_used = True
                        async for chunk in result["stream"]:
                            yield chunk
                        return
                    last_error = result.get("error", "Erro desconhecido")
                except Exception as e:
                    last_error = str(e)
                if "rate" in str(last_error).lower() or "429" in str(last_error):
                    continue
                break
        yield {"chunk": "", "error": f"Todos os provedores falharam. Último erro: {last_error}", "done": True}

    async def _call_provider_stream(self, provider_id: str, api_key: str, messages: list, model: str = None) -> dict:
        config = self.providers[provider_id]
        if not model:
            model = config["models"][0]
        api_type = config.get("api_type", "openai")
        start = time.time()
        try:
            if api_type in ("huggingface", "cohere", "cloudflare"):
                result = await self._call_provider(provider_id, api_key, messages, model)
                if result.get("success"):
                    async def single_chunk_stream():
                        yield {"chunk": result["content"], "done": True}
                    return {"success": True, "stream": single_chunk_stream()}
                return result

            if api_type == "gemini":
                result = await self._call_google_gemini(api_key, model, messages)
                if result.get("success"):
                    content = result["content"]
                    async def gemini_stream():
                        words = content.split(" ")
                        for i, word in enumerate(words):
                            prefix = " " if i > 0 else ""
                            yield {"chunk": prefix + word, "done": False}
                        yield {"chunk": "", "done": True}
                    return {"success": True, "stream": gemini_stream()}
                return result

            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": messages, "max_tokens": 4096, "temperature": 0.7, "stream": True}
            session = await self._get_session()
            resp = await session.post(config["url"], json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120))
            if resp.status != 200:
                try:
                    data = await resp.json()
                    error_msg = data.get("error", {}).get("message", str(data))
                except Exception:
                    error_msg = f"HTTP {resp.status}"
                await resp.release()
                return {"success": False, "error": error_msg, "model": model, "provider": provider_id, "latency_ms": int((time.time() - start) * 1000)}

            async def stream_chunks(response):
                try:
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield {"chunk": "", "done": True}
                            return
                        try:
                            chunk_data = json.loads(data_str)
                            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield {"chunk": content, "done": False}
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
                    yield {"chunk": "", "done": True}
                finally:
                    await response.release()

            return {"success": True, "stream": stream_chunks(resp), "model": model, "provider": provider_id}
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._provider_failures[provider_id] = self._provider_failures.get(provider_id, 0) + 1
            return {"success": False, "error": str(e), "model": model, "provider": provider_id, "latency_ms": int(elapsed)}

    def get_provider_status(self, user_api_keys: dict) -> list:
        available = self._get_available_keys(user_api_keys)
        status_list = []
        for provider_id, config in self.providers.items():
            has_key = provider_id in available
            failures = self._provider_failures.get(provider_id, 0)
            latency = self._provider_latency.get(provider_id, None)
            is_cooling = provider_id in self._provider_cooldown
            status_list.append({
                "id": provider_id, "name": config["name"], "available": has_key,
                "models": config["models"], "strengths": config["strengths"],
                "speed": config["speed"], "failures": failures,
                "latency_ms": int(latency) if latency else None,
                "cooling_down": is_cooling, "configured": has_key
            })
        return status_list

ai_orchestrator = AIOrchestrator()
