import asyncio
import subprocess
import tempfile
import os
import time

class CodeSandbox:
    LANGUAGES = {
        "python": {"ext": ".py", "cmd": ["python3"]},
        "javascript": {"ext": ".js", "cmd": ["node"]},
        "bash": {"ext": ".sh", "cmd": ["bash"]},
        "shell": {"ext": ".sh", "cmd": ["bash"]},
    }

    MAX_TIMEOUT = 30
    MAX_OUTPUT = 10 * 1024 * 1024  # 10MB

    async def execute(self, code: str, language: str = "python", timeout: int = 15) -> dict:
        if language not in self.LANGUAGES:
            return {"success": False, "error": f"Linguagem '{language}' não suportada. Use: {list(self.LANGUAGES.keys())}", "output": "", "exit_code": 1, "execution_time_ms": 0}

        timeout = min(timeout, self.MAX_TIMEOUT)
        lang = self.LANGUAGES[language]

        start = time.time()
        with tempfile.NamedTemporaryFile(mode='w', suffix=lang["ext"], delete=False, dir="/tmp") as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                *lang["cmd"], tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                elapsed = int((time.time() - start) * 1000)
                return {"success": False, "error": f"Timeout após {timeout}s", "output": "", "exit_code": -1, "execution_time_ms": elapsed}

            elapsed = int((time.time() - start) * 1000)
            stdout_str = stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]
            stderr_str = stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]

            return {
                "success": proc.returncode == 0,
                "output": stdout_str,
                "error": stderr_str,
                "exit_code": proc.returncode,
                "execution_time_ms": elapsed
            }
        finally:
            os.unlink(tmp_path)

    def get_languages(self) -> list:
        return [{"id": k, "name": k.title(), "ext": v["ext"]} for k, v in self.LANGUAGES.items()]

code_sandbox = CodeSandbox()
