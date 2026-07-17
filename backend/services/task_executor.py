import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from services.ai_orchestrator import ai_orchestrator
from engines.file_processor import file_processor
from engines.code_generator import code_generator

class TaskExecutor:
    def __init__(self):
        self.task_handlers = {
            "code_generation": self._handle_code_generation,
            "code_review": self._handle_code_review,
            "website_creation": self._handle_website_creation,
            "app_creation": self._handle_app_creation,
            "apk_creation": self._handle_apk_creation,
            "file_analysis": self._handle_file_analysis,
            "data_processing": self._handle_data_processing,
            "general_task": self._handle_general_task,
            "code_refactor": self._handle_code_refactor,
            "bug_fix": self._handle_bug_fix,
            "api_design": self._handle_api_design,
            "database_design": self._handle_database_design,
            "documentation": self._handle_documentation,
            "testing": self._handle_testing,
            "deployment": self._handle_deployment,
            "optimization": self._handle_optimization,
            "security_review": self._handle_security_review,
            "ui_design": self._handle_ui_design,
        }

    async def execute(self, task_type: str, description: str, user_id: int, user_api_keys: dict,
                      files: list = None, context: dict = None, preferred_model: str = None) -> dict:
        start_time = time.time()
        if task_type not in self.task_handlers:
            task_type = "general_task"
        handler = self.task_handlers[task_type]
        try:
            result = await handler(description, user_id, user_api_keys, files, context, preferred_model)
            result["execution_time_ms"] = int((time.time() - start_time) * 1000)
            result["task_type"] = task_type
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_type": task_type,
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "content": "",
                "provider": None,
                "model": None,
                "tokens_input": 0,
                "tokens_output": 0
            }

    def _build_system_prompt(self, task_type: str, context: dict = None) -> str:
        base = """Você é NexusAgent, um agente autônomo de programação extremamente avançado.
Você é especialista em criar, revisar, otimizar e gerenciar código em todas as linguagens.
Responda SEMPRE em português brasileiro.
Seja preciso, completo e forneça código funcional sempre que possível.
Não use markdown ``` no início e fim quando fornecer código para copiar direto."""
        type_prompts = {
            "code_generation": f"{base}\n\nTarefa: Gerar código. Forneça o código completo, funcional e bem documentado.",
            "code_review": f"{base}\n\nTarefa: Revisar código. Identifique bugs, melhorias de performance, segurança e boas práticas.",
            "website_creation": f"{base}\n\nTarefa: Criar um website completo e funcional. Gere HTML, CSS e JavaScript prontos para uso.",
            "app_creation": f"{base}\n\nTarefa: Criar um aplicativo. Forneça toda a estrutura e código necessários.",
            "apk_creation": f"{base}\n\nTarefa: Criar um APK Android. Forneça o projeto Kotlin/Java completo com layouts XML.",
            "file_analysis": f"{base}\n\nTarefa: Analisar arquivo fornecido. Extraia insights, padrões e forneça resumo detalhado.",
            "data_processing": f"{base}\n\nTarefa: Processar dados. Forneça scripts para processar, limpar e analisar dados.",
            "code_refactor": f"{base}\n\nTarefa: Refatorar código. Melhore a estrutura, legibilidade e mantenibilidade.",
            "bug_fix": f"{base}\n\nTarefa: Corrigir bug. Identifique o problema e forneça a correção completa.",
            "api_design": f"{base}\n\nTarefa: Projetar API REST/GraphQL. Forneça endpoints, schemas e documentação.",
            "database_design": f"{base}\n\nTarefa: Projetar banco de dados. Forneça schemas SQL, migrations e modelos.",
            "documentation": f"{base}\n\nTarefa: Criar documentação técnica completa e clara.",
            "testing": f"{base}\n\nTarefa: Criar testes. Forneça testes unitários, de integração e E2E completos.",
            "deployment": f"{base}\n\nTarefa: Configurar deploy. Forneça Dockerfiles, CI/CD e configs de produção.",
            "optimization": f"{base}\n\nTarefa: Otimizar código. Melhore performance, memória e速度.",
            "security_review": f"{base}\n\nTarefa: Revisão de segurança. Identifique vulnerabilidades e forneça correções.",
            "ui_design": f"{base}\n\nTarefa: Criar UI/UX. Forneça código HTML/CSS/React bonito e responsivo.",
            "general_task": f"{base}\n\nTarefa: Completar a tarefa solicitada da melhor forma possível.",
        }
        return type_prompts.get(task_type, type_prompts["general_task"])

    def _build_messages(self, system_prompt: str, description: str, files_content: str = None, context: dict = None) -> list:
        messages = [{"role": "system", "content": system_prompt}]
        user_content = description
        if files_content:
            user_content += f"\n\n--- CONTEÚDO DOS ARQUIVOS ---\n{files_content}\n--- FIM DOS ARQUIVOS ---"
        if context:
            user_content += f"\n\n--- CONTEXTO ADICIONAL ---\n{json.dumps(context, ensure_ascii=False, indent=2)}\n--- FIM DO CONTEXTO ---"
        messages.append({"role": "user", "content": user_content})
        return messages

    async def _process_files(self, files: list, user_id: int) -> str:
        if not files:
            return ""
        results = []
        for file_path in files:
            try:
                result = await file_processor.process_file(file_path, user_id)
                content_preview = result.get("content", "")[:10000]
                results.append(f"Arquivo: {result['filename']} ({result['file_type']}, {result['file_size_human']})\n{content_preview}")
            except Exception as e:
                results.append(f"Arquivo: {file_path} - Erro: {str(e)}")
        return "\n\n".join(results)

    async def _handle_code_generation(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("code_generation", context)
        messages = self._build_messages(system, desc, files_content, context)
        result = await ai_orchestrator.execute_task("code_generation", messages, api_keys, model)
        return result

    async def _handle_code_review(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        if not files_content:
            files_content = "Nenhum arquivo fornecido para revisão. Por favor, forneça o código."
        system = self._build_system_prompt("code_review", context)
        messages = self._build_messages(system, desc, files_content, context)
        result = await ai_orchestrator.execute_task("code_review", messages, api_keys, model)
        return result

    async def _handle_website_creation(self, desc, user_id, api_keys, files, context, model):
        enhanced_desc = f"""Crie um website COMPLETO e FUNCIONAL para: {desc}

Requisitos obrigatórios:
1. HTML5 semântico e acessível
2. CSS3 moderno (Flexbox/Grid, responsivo)
3. JavaScript funcional (interatividade completa)
4. Design profissional (cores, tipografia, espaçamento)
5. Mobile-first responsivo
6. Animações suaves
7. SEO básico (meta tags)

Forneça TODO o código HTML completo, pronto para copiar e usar."""
        system = self._build_system_prompt("website_creation", context)
        messages = self._build_messages(system, enhanced_desc, None, context)
        result = await ai_orchestrator.execute_task("web_development", messages, api_keys, model)

        if result.get("success") and result.get("content"):
            project_name = desc[:30].replace(" ", "_").lower()
            project_result = await code_generator.generate_project(
                "vanilla_html", project_name, desc,
                context.get("features", []) if context else [],
                {"index.html": result["content"]}
            )
            result["project"] = project_result
        return result

    async def _handle_app_creation(self, desc, user_id, api_keys, files, context, model):
        framework = (context or {}).get("framework", "react")
        enhanced_desc = f"""Crie um aplicativo COMPLETO usando {framework.upper()} para: {desc}

Forneça:
1. Todos os componentes necessários
2. Rotas e navegação
3. Estado gerenciado
4. Estilização completa
5. Funcionalidade real

Gere TODO o código, não apenas estrutura."""
        system = self._build_system_prompt("app_creation", context)
        messages = self._build_messages(system, enhanced_desc, None, context)
        result = await ai_orchestrator.execute_task("web_development", messages, api_keys, model)

        if result.get("success") and result.get("content"):
            project_name = desc[:30].replace(" ", "_").lower()
            project_result = await code_generator.generate_project(
                framework, project_name, desc,
                context.get("features", []) if context else [],
                {"App.jsx": result["content"]}
            )
            result["project"] = project_result
        return result

    async def _handle_apk_creation(self, desc, user_id, api_keys, files, context, model):
        enhanced_desc = f"""Crie um projeto Android COMPLETO para APK: {desc}

Forneça:
1. AndroidManifest.xml completo
2. build.gradle com todas as dependências
3. Activities Kotlin com lógica completa
4. Layouts XML responsivos e bonitos
5. Strings, colors, themes.xml
6. Todas as funcionalidades implementadas

O projeto deve ser compilável direto no Android Studio."""
        system = self._build_system_prompt("apk_creation", context)
        messages = self._build_messages(system, enhanced_desc, None, context)
        result = await ai_orchestrator.execute_task("code_generation", messages, api_keys, model)

        if result.get("success") and result.get("content"):
            project_name = desc[:30].replace(" ", "_").lower()
            project_result = await code_generator.generate_project(
                "android_kotlin", project_name, desc,
                context.get("features", []) if context else [],
                None
            )
            result["project"] = project_result
        return result

    async def _handle_file_analysis(self, desc, user_id, api_keys, files, context, model):
        if not files:
            return {"success": False, "error": "Nenhum arquivo fornecido para análise", "content": ""}
        files_content = await self._process_files(files, user_id)
        system = self._build_system_prompt("file_analysis", context)
        messages = self._build_messages(system, f"Analise detalhadamente estes arquivos:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("file_processing", messages, api_keys, model)
        return result

    async def _handle_data_processing(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("data_processing", context)
        enhanced = f"Crie scripts completos para processar dados:\n{desc}"
        messages = self._build_messages(system, enhanced, files_content, context)
        result = await ai_orchestrator.execute_task("data_analysis", messages, api_keys, model)
        return result

    async def _handle_code_refactor(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("code_refactor", context)
        messages = self._build_messages(system, f"Refatore este código:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("code_review", messages, api_keys, model)
        return result

    async def _handle_bug_fix(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("bug_fix", context)
        messages = self._build_messages(system, f"Corrija este bug:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("code_review", messages, api_keys, model)
        return result

    async def _handle_api_design(self, desc, user_id, api_keys, files, context, model):
        system = self._build_system_prompt("api_design", context)
        messages = self._build_messages(system, f"Projete uma API completa:\n{desc}", None, context)
        result = await ai_orchestrator.execute_task("code_generation", messages, api_keys, model)
        return result

    async def _handle_database_design(self, desc, user_id, api_keys, files, context, model):
        system = self._build_system_prompt("database_design", context)
        messages = self._build_messages(system, f"Projete o banco de dados:\n{desc}", None, context)
        result = await ai_orchestrator.execute_task("reasoning", messages, api_keys, model)
        return result

    async def _handle_documentation(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("documentation", context)
        messages = self._build_messages(system, f"Crie documentação completa:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("general", messages, api_keys, model)
        return result

    async def _handle_testing(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("testing", context)
        messages = self._build_messages(system, f"Crie testes completos:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("code_generation", messages, api_keys, model)
        return result

    async def _handle_deployment(self, desc, user_id, api_keys, files, context, model):
        system = self._build_system_prompt("deployment", context)
        messages = self._build_messages(system, f"Configure deploy:\n{desc}", None, context)
        result = await ai_orchestrator.execute_task("code_generation", messages, api_keys, model)
        return result

    async def _handle_optimization(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("optimization", context)
        messages = self._build_messages(system, f"Otimize este código:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("code_review", messages, api_keys, model)
        return result

    async def _handle_security_review(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("security_review", context)
        messages = self._build_messages(system, f"Faça review de segurança:\n{desc}", files_content, context)
        result = await ai_orchestrator.execute_task("reasoning", messages, api_keys, model)
        return result

    async def _handle_ui_design(self, desc, user_id, api_keys, files, context, model):
        system = self._build_system_prompt("ui_design", context)
        messages = self._build_messages(system, f"Crie UI/UX completa:\n{desc}", None, context)
        result = await ai_orchestrator.execute_task("web_development", messages, api_keys, model)
        return result

    async def _handle_general_task(self, desc, user_id, api_keys, files, context, model):
        files_content = await self._process_files(files, user_id) if files else None
        system = self._build_system_prompt("general_task", context)
        messages = self._build_messages(system, desc, files_content, context)
        result = await ai_orchestrator.execute_task("general", messages, api_keys, model)
        return result

task_executor = TaskExecutor()
