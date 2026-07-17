import asyncio
import os
import time
from config import BLOCKED_COMMANDS, BASE_DIR as _CONFIG_BASE_DIR

class Terminal:
    BASE_DIR = str(_CONFIG_BASE_DIR)
    MAX_TIMEOUT = 30
    MAX_OUTPUT = 5 * 1024 * 1024

    def _safe_path(self, path: str) -> str:
        if not path:
            return self.BASE_DIR
        path = os.path.abspath(os.path.join(self.BASE_DIR, path))
        if not path.startswith(self.BASE_DIR):
            return self.BASE_DIR
        return path

    def _is_blocked(self, command: str) -> str:
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked.lower() in cmd_lower:
                return blocked
        return ""

    async def execute(self, command: str, timeout: int = 15) -> dict:
        blocked = self._is_blocked(command)
        if blocked:
            return {"success": False, "error": f"Comando bloqueado por segurança: contiene '{blocked}'", "output": "", "exit_code": 1, "execution_time_ms": 0}
        timeout = min(timeout, self.MAX_TIMEOUT)
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.BASE_DIR,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                elapsed = int((time.time() - start) * 1000)
                return {"success": False, "error": f"Timeout após {timeout}s", "output": "", "exit_code": -1, "execution_time_ms": elapsed}
            elapsed = int((time.time() - start) * 1000)
            return {
                "success": proc.returncode == 0,
                "output": stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT],
                "error": stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT],
                "exit_code": proc.returncode,
                "execution_time_ms": elapsed
            }
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return {"success": False, "error": str(e), "output": "", "exit_code": 1, "execution_time_ms": elapsed}

    def list_files(self, path: str = ".") -> list:
        safe = self._safe_path(path)
        try:
            entries = []
            for name in sorted(os.listdir(safe)):
                full = os.path.join(safe, name)
                is_dir = os.path.isdir(full)
                size = 0 if is_dir else os.path.getsize(full)
                entries.append({"name": name, "is_dir": is_dir, "size": size, "path": os.path.relpath(full, self.BASE_DIR)})
            return entries
        except Exception:
            return []

    def read_file(self, path: str) -> dict:
        safe = self._safe_path(path)
        try:
            with open(safe, "r", errors="replace") as f:
                content = f.read(500000)
            return {"success": True, "content": content, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        safe = self._safe_path(path)
        critical_files = ["main.py", "config.py", "database.py", "auth.py"]
        filename = os.path.basename(safe)
        if filename in critical_files and os.path.dirname(safe).endswith("backend"):
            return {"success": False, "error": f"Arquivo protegido: {filename} não pode ser modificado pelo terminal"}
        try:
            os.makedirs(os.path.dirname(safe), exist_ok=True)
            with open(safe, "w") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

terminal = Terminal()
