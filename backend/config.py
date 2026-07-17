import os
import secrets
from pathlib import Path

SECRET_KEY = os.getenv("AGENT_SECRET_KEY") or "nexusagent_admin_wellinton_2026_secret_key_permanent"
CSRF_SECRET = os.getenv("AGENT_CSRF_SECRET") or secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

_data_dir = os.getenv("AGENT_DATA_DIR")
if not _data_dir:
    for candidate in [Path.cwd(), Path("/tmp/nexusagent"), Path.home() / "nexusagent"]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            _data_dir = str(candidate)
            break
        except (OSError, PermissionError):
            continue
    if not _data_dir:
        _data_dir = "/tmp/nexusagent"
        Path(_data_dir).mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(_data_dir)
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "templates"
DB_PATH = BASE_DIR / "agent.db"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_SIZE = 500 * 1024 * 1024

RATE_LIMIT_LOGIN = 5
RATE_LIMIT_REGISTER = 3
RATE_LIMIT_AI = 10
RATE_LIMIT_TERMINAL = 20
RATE_LIMIT_WINDOW = 60

BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf /*", "mkfs", ":(){ :|:& };:", "dd if=", "mv / ",
    "chmod -R 777 /", "wget", "curl.*|sh", "shutdown", "reboot", "halt",
    "init 0", "init 6", "kill -9 1", "killall", "pkill -9",
    "/etc/passwd", "/etc/shadow", "/etc/sudoers", "crontab -r",
    "iptables", "nc -e", "ncat", "python.*-c.*import.*os",
    "node.*require.*child_process", "base64.*sh", "eval.*base64",
]

SSRF_BLOCKED_HOSTS = [
    "169.254.169.254", "metadata.google.internal", "localhost",
    "127.0.0.1", "0.0.0.0", "10.0.0.0/8", "172.16.0.0/12",
    "192.168.0.0/16", "169.254.0.0/16",
]

FREE_AI_PROVIDERS = {
    "groq": {
        "name": "Groq (Llama 3.3/Mixtral)",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "free_tier": True, "speed": "ultra_fast",
        "strengths": ["code", "reasoning", "general"],
        "api_key_env": "GROQ_API_KEY", "api_type": "openai",
    },
    "google_gemini": {
        "name": "Google Gemini (2.0 Flash)",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "reasoning", "general", "multilingual"],
        "api_key_env": "GOOGLE_API_KEY", "api_type": "gemini",
    },
    "deepseek": {
        "name": "DeepSeek (V3/R1)",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "reasoning", "math"],
        "api_key_env": "DEEPSEEK_API_KEY", "api_type": "openai",
    },
    "mistral": {
        "name": "Mistral AI (Free Tier)",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "models": ["mistral-tiny", "mistral-small-latest", "open-mistral-nemo"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "general", "multilingual"],
        "api_key_env": "MISTRAL_API_KEY", "api_type": "openai",
    },
    "together": {
        "name": "Together AI (Free Credits)",
        "url": "https://api.together.xyz/v1/chat/completions",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-Coder-32B-Instruct"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general"],
        "api_key_env": "TOGETHER_API_KEY", "api_type": "openai",
    },
    "openrouter": {
        "name": "OpenRouter (Free Models)",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["cohere/north-mini-code:free", "nvidia/nemotron-nano-9b-v2:free", "nousresearch/hermes-3-llama-3.1-405b:free", "meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen3-coder:free"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general", "reasoning"],
        "api_key_env": "OPENROUTER_API_KEY", "api_type": "openai",
    },
    "huggingface": {
        "name": "Hugging Face Router",
        "url": "https://router.huggingface.co/v1/chat/completions",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "general"],
        "api_key_env": "HF_TOKEN", "api_type": "openai",
    },
    "cohere": {
        "name": "Cohere (Free Tier)",
        "url": "https://api.cohere.ai/v2/chat",
        "models": ["command-r", "command-r-plus"],
        "free_tier": True, "speed": "fast",
        "strengths": ["general", "code"],
        "api_key_env": "COHERE_API_KEY", "api_type": "cohere",
    },
    "novita": {
        "name": "Novita AI (Free Credits)",
        "url": "https://api.novita.ai/v3/openai/chat/completions",
        "models": ["meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-v3-0324"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general"],
        "api_key_env": "NOVITA_API_KEY", "api_type": "openai",
    },
    "chutes": {
        "name": "Chutes AI (Free)",
        "url": "https://api.chutes.ai/v1/chat/completions",
        "models": ["deepseek-ai/DeepSeek-V3", "meta-llama/Llama-3.3-70B-Instruct"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general"],
        "api_key_env": "CHUTES_API_KEY", "api_type": "openai",
    },
    "siliconflow": {
        "name": "SiliconFlow (Free Tier)",
        "url": "https://api.siliconflow.cn/v1/chat/completions",
        "models": ["Qwen/Qwen2.5-7B-Instruct", "THUDM/glm-4-9b-chat"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general", "multilingual"],
        "api_key_env": "SILICONFLOW_API_KEY", "api_type": "openai",
    },
    "aiml": {
        "name": "AIML API (Free Trial)",
        "url": "https://api.aimlapi.com/v1/chat/completions",
        "models": ["deepseek-chat", "mistral-tiny"],
        "free_tier": True, "speed": "medium",
        "strengths": ["code", "general"],
        "api_key_env": "AIML_API_KEY", "api_type": "openai",
    },
    "cloudflare_workers_ai": {
        "name": "Cloudflare Workers AI",
        "url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/{model}",
        "models": ["meta-llama/llama-3.3-70b-instruct-fp16"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "general"],
        "api_key_env": "CF_API_TOKEN", "api_type": "cloudflare",
    },
    "github_copilot": {
        "name": "GitHub Models (Free)",
        "url": "https://models.inference.ai.azure.com/chat/completions",
        "models": ["gpt-4o-mini", "gpt-4o", "Llama-3.3-70B-Instruct"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "general", "reasoning"],
        "api_key_env": "GITHUB_TOKEN", "api_type": "openai",
    },
    "perplexity": {
        "name": "Perplexity (Free Tier)",
        "url": "https://api.perplexity.ai/chat/completions",
        "models": ["sonar", "sonar-pro"],
        "free_tier": True, "speed": "fast",
        "strengths": ["general", "research"],
        "api_key_env": "PERPLEXITY_API_KEY", "api_type": "openai",
    },
    "ollama_local": {
        "name": "Ollama Local (Sem Filtros)",
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "models": ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:1.5b", "llama3.2:1b", "phi3:mini", "gemma2:2b"],
        "free_tier": True, "speed": "slow",
        "strengths": ["code", "general", "uncensored"],
        "api_key_env": "", "api_type": "openai",
    },
    "novita": {
        "name": "Novita AI ($0.50 grátis, sem filtros)",
        "url": "https://api.novita.ai/v3/openai/chat/completions",
        "models": ["meta-llama/llama-3.1-8b-instruct", "deepseek/deepseek-r1", "mistralai/mistral-nemo"],
        "free_tier": True, "speed": "fast",
        "strengths": ["code", "general", "less_censored"],
        "api_key_env": "NOVITA_API_KEY", "api_type": "openai",
    },
    "chutes": {
        "name": "Chutes AI (TEE models)",
        "url": "https://llm.chutes.ai/v1/chat/completions",
        "models": ["Qwen/Qwen3-32B-TEE", "unsloth/Mistral-Nemo-Instruct-2407-TEE", "deepseek-ai/DeepSeek-V3.2-TEE"],
        "free_tier": False, "speed": "fast",
        "strengths": ["code", "reasoning", "general"],
        "api_key_env": "CHUTES_API_KEY", "api_type": "openai",
    },
}

TASK_ROUTING = {
    "code_generation": ["groq", "deepseek", "google_gemini", "together", "openrouter", "ollama_local"],
    "code_review": ["groq", "deepseek", "google_gemini", "github_copilot", "ollama_local"],
    "reasoning": ["deepseek", "google_gemini", "groq", "openrouter", "ollama_local"],
    "general": ["groq", "google_gemini", "mistral", "openrouter", "ollama_local"],
    "multilingual": ["google_gemini", "siliconflow", "mistral", "ollama_local"],
    "math": ["deepseek", "groq", "google_gemini", "ollama_local"],
    "web_development": ["groq", "deepseek", "github_copilot", "together", "ollama_local"],
    "file_processing": ["google_gemini", "deepseek", "groq", "ollama_local"],
    "research": ["perplexity", "google_gemini", "ollama_local"],
    "data_analysis": ["deepseek", "google_gemini", "groq", "ollama_local"],
}

COST_OPTIMIZATION_ORDER = [
    "groq", "deepseek", "google_gemini", "siliconflow", "openrouter",
    "together", "huggingface", "mistral", "cohere", "github_copilot",
    "novita", "chutes", "aiml", "cloudflare_workers_ai", "perplexity",
    "ollama_local"
]
