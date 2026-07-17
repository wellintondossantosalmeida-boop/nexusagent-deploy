import os
import json
import csv
import asyncio
import subprocess
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

class FileProcessor:
    def __init__(self):
        self.supported_types = {
            "text": [".txt", ".md", ".rst", ".log"],
            "code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java", ".kt", ".swift", ".go", ".rs", ".c", ".cpp", ".h", ".rb", ".php", ".sql", ".sh", ".bat"],
            "data": [".csv", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
            "document": [".pdf", ".docx", ".xlsx", ".pptx", ".odt"],
            "archive": [".zip", ".tar", ".gz", ".rar", ".7z"],
            "config": [".env", ".gitignore", ".dockerignore", "Dockerfile", "docker-compose.yml", "Makefile"],
            "spreadsheet": [".csv", ".xlsx", ".xls", ".tsv"],
        }
        self.max_file_size = 500 * 1024 * 1024

    def get_file_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        for type_name, extensions in self.supported_types.items():
            if ext in extensions:
                return type_name
        return "unknown"

    async def process_file(self, file_path: str, user_id: int, task_description: str = "") -> dict:
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_type = self.get_file_type(filename)
        result = {
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "file_size_human": self._human_size(file_size),
            "content": "",
            "metadata": {},
            "summary": ""
        }
        try:
            if file_type == "text" or file_type == "config":
                result["content"] = self._read_text_file(file_path)
                result["summary"] = f"Arquivo de texto com {len(result['content'])} caracteres"
            elif file_type == "code":
                result["content"] = self._read_text_file(file_path)
                lines = result["content"].split("\n")
                result["metadata"] = {
                    "lines": len(lines),
                    "non_empty_lines": len([l for l in lines if l.strip()]),
                    "language": Path(filename).suffix.lstrip("."),
                    "functions": self._count_functions(result["content"], Path(filename).suffix),
                    "classes": result["content"].count("class "),
                    "imports": len([l for l in lines if l.strip().startswith("import") or l.strip().startswith("from") or l.strip().startswith("require")]),
                }
                result["summary"] = f"Código com {result['metadata']['lines']} linhas, {result['metadata']['functions']} funções, {result['metadata']['classes']} classes"
            elif file_type == "data":
                content = self._read_text_file(file_path)
                result["content"] = content
                ext = Path(filename).suffix.lower()
                if ext == ".csv":
                    result["metadata"] = self._parse_csv_metadata(file_path)
                elif ext == ".json":
                    try:
                        data = json.loads(content)
                        result["metadata"] = {
                            "type": type(data).__name__,
                            "size": len(data) if isinstance(data, (list, dict)) else 1,
                            "keys": list(data.keys())[:20] if isinstance(data, dict) else None
                        }
                    except json.JSONDecodeError:
                        pass
                result["summary"] = f"Arquivo de dados: {result['metadata']}"
            elif file_type == "archive":
                result["summary"] = f"Arquivo compactado: {filename} ({self._human_size(file_size)})"
                result["metadata"] = self._list_archive_contents(file_path)
            elif file_type == "document":
                result["content"] = self._extract_document_text(file_path)
                result["summary"] = f"Documento extraído: {len(result['content'])} caracteres"
            else:
                result["content"] = self._read_text_file(file_path)
                result["summary"] = f"Arquivo processado: {filename}"
        except Exception as e:
            result["error"] = str(e)
            result["summary"] = f"Erro ao processar: {str(e)}"
        return result

    async def process_large_file_in_chunks(self, file_path: str, chunk_size: int = 10000) -> list:
        chunks = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                chunk_num = 0
                while True:
                    content = f.read(chunk_size)
                    if not content:
                        break
                    chunks.append({
                        "chunk_id": chunk_num,
                        "content": content,
                        "size": len(content)
                    })
                    chunk_num += 1
                    if chunk_num > 100:
                        break
        except Exception as e:
            chunks.append({"chunk_id": 0, "content": f"Error reading file: {e}", "size": 0})
        return chunks

    def _read_text_file(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(500000)
        except Exception as e:
            return f"Error reading file: {e}"

    def _count_functions(self, content: str, ext: str) -> int:
        import re
        patterns = {
            ".py": r"def\s+\w+\s*\(",
            ".js": r"function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\(|=>\s*\{",
            ".ts": r"function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\(|=>\s*\{",
            ".java": r"(?:public|private|protected|static|void|int|String|boolean)\s+\w+\s*\(",
            ".go": r"func\s+(?:\([^)]*\)\s+)?\w+\s*\(",
            ".rs": r"fn\s+\w+",
            ".rb": r"def\s+\w+",
            ".php": r"function\s+\w+",
        }
        pattern = patterns.get(ext, r"function\s+\w+|def\s+\w+")
        return len(re.findall(pattern, content))

    def _parse_csv_metadata(self, file_path: str) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                row_count = sum(1 for _ in reader)
                return {"headers": headers, "row_count": row_count, "columns": len(headers)}
        except Exception:
            return {}

    def _list_archive_contents(self, file_path: str) -> dict:
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, "r") as zf:
                    names = zf.namelist()
                    return {"files": names[:50], "total_files": len(names), "total_size": sum(i.file_size for i in zf.infolist())}
        except Exception:
            pass
        return {"error": "Cannot read archive"}

    def _extract_document_text(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".pdf":
                import subprocess
                result = subprocess.run(["pdftotext", file_path, "-"], capture_output=True, text=True, timeout=30)
                return result.stdout[:200000] if result.returncode == 0 else ""
            elif ext == ".docx":
                from docx import Document
                doc = Document(file_path)
                return "\n".join([p.text for p in doc.paragraphs])[:200000]
        except Exception:
            pass
        return ""

    def _human_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

file_processor = FileProcessor()
