import os
import json
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import zipfile
import shutil

class CodeGenerator:
    def __init__(self):
        from config import OUTPUT_DIR
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(exist_ok=True)
        self.templates = {
            "react": self._react_template,
            "nextjs": self._nextjs_template,
            "flask": self._flask_template,
            "fastapi": self._fastapi_template,
            "vanilla_html": self._vanilla_html_template,
            "android_kotlin": self._android_kotlin_template,
            "python_cli": self._python_cli_template,
            "node_express": self._node_express_template,
            "vue": self._vue_template,
            "svelte": self._svelte_template,
        }

    async def generate_project(self, project_type: str, project_name: str, description: str, features: list, ai_generated_code: dict = None) -> dict:
        project_dir = self.output_dir / f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "project_dir": str(project_dir),
            "project_name": project_name,
            "project_type": project_type,
            "files_created": [],
            "total_size": 0,
            "success": True
        }
        try:
            if project_type in self.templates:
                files = await self.templates[project_type](project_dir, project_name, description, features, ai_generated_code)
            else:
                files = await self._generic_project(project_dir, project_name, description, features, ai_generated_code)
            result["files_created"] = files
            result["total_size"] = sum(os.path.getsize(os.path.join(project_dir, f)) for f in files if os.path.exists(os.path.join(project_dir, f)))
            await self._create_readme(project_dir, project_name, description, project_type, features)
            result["files_created"].append("README.md")
            zip_path = await self._zip_project(project_dir)
            result["zip_path"] = str(zip_path)
            result["zip_size"] = os.path.getsize(str(zip_path))
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
        return result

    async def _react_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "private": True,
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-router-dom": "^6.20.0",
                "axios": "^1.6.0"
            },
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.0",
                "vite": "^5.0.0"
            }
        }
        self._write_file(project_dir / "package.json", json.dumps(pkg, indent=2))
        files.append("package.json")

        vite_config = '''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000
  }
})'''
        self._write_file(project_dir / "vite.config.js", vite_config)
        files.append("vite.config.js")

        index_html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}</title>
    <link rel="icon" type="image/svg+xml" href="/vite.svg">
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>'''
        self._write_file(project_dir / "index.html", index_html)
        files.append("index.html")

        src_dir = project_dir / "src"
        src_dir.mkdir(exist_ok=True)
        files.append("src/")

        main_jsx = '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)'''
        self._write_file(src_dir / "main.jsx", main_jsx)
        files.append("src/main.jsx")

        app_content = ai_code.get("App.jsx", "") if ai_code else ""
        if not app_content:
            features_list = "\n".join([f"        <li>{f}</li>" for f in features]) if features else "        <li>Feature principal</li>"
            app_content = f'''import React, {{ useState, useEffect }} from 'react'
import './App.css'

function App() {{
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {{
    document.title = '{name}'
  }}, [])

  return (
    <div className="app">
      <header className="header">
        <h1>{name}</h1>
        <p>{desc}</p>
      </header>
      <main className="main">
        <div className="features">
          <h2>Funcionalidades</h2>
          <ul>
{features_list}
          </ul>
        </div>
      </main>
      <footer className="footer">
        <p>&copy; 2026 {name}. Gerado por NexusAgent AI.</p>
      </footer>
    </div>
  )
}}

export default App'''
        self._write_file(src_dir / "App.jsx", app_content)
        files.append("src/App.jsx")

        css_content = ai_code.get("App.css", "") if ai_code else ""
        if not css_content:
            css_content = f''':root {{
  --primary: #6366f1;
  --primary-dark: #4f46e5;
  --bg: #0f172a;
  --bg-card: #1e293b;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --border: #334155;
  --success: #22c55e;
  --radius: 12px;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}}

.app {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}}

.header {{
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  padding: 3rem 2rem;
  text-align: center;
}}

.header h1 {{
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}}

.header p {{
  opacity: 0.9;
  font-size: 1.1rem;
}}

.main {{
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}}

.features {{
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 2rem;
  border: 1px solid var(--border);
}}

.features h2 {{
  margin-bottom: 1rem;
  color: var(--primary);
}}

.features ul {{
  list-style: none;
}}

.features li {{
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}}

.features li:last-child {{ border-bottom: none; }}

.footer {{
  text-align: center;
  padding: 1.5rem;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
  color: var(--text-muted);
}}

@media (max-width: 768px) {{
  .header h1 {{ font-size: 1.8rem; }}
  .main {{ padding: 1rem; }}
}}'''
        self._write_file(src_dir / "App.css", css_content)
        files.append("src/App.css")

        index_css = '''@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
}'''
        self._write_file(src_dir / "index.css", index_css)
        files.append("src/index.css")

        return files

    async def _nextjs_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start"
            },
            "dependencies": {
                "next": "14.2.0",
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            }
        }
        self._write_file(project_dir / "package.json", json.dumps(pkg, indent=2))
        files.append("package.json")

        next_config = '''/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
}

module.exports = nextConfig'''
        self._write_file(project_dir / "next.config.js", next_config)
        files.append("next.config.js")

        pages_dir = project_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        layout = ai_code.get("layout.jsx", "") if ai_code else f'''import '../styles/globals.css'

export default function RootLayout({{{ children }}}) {{
  return (
    <html lang="pt-BR">
      <body>{{{{children}}}}</body>
    </html>
  )
}}'''
        self._write_file(pages_dir / "_app.js", layout)
        files.append("pages/_app.js")

        index_page = ai_code.get("index.jsx", "") if ai_code else f'''export default function Home() {{
  return (
    <div style={{{{ padding: '2rem', textAlign: 'center' }}}}>
      <h1>{name}</h1>
      <p>{desc}</p>
    </div>
  )
}}'''
        self._write_file(pages_dir / "index.js", index_page)
        files.append("pages/index.js")

        styles_dir = project_dir / "styles"
        styles_dir.mkdir(exist_ok=True)
        self._write_file(styles_dir / "globals.css", "* { margin: 0; padding: 0; box-sizing: border-box; }")
        files.append("styles/globals.css")

        return files

    async def _flask_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        app_code = ai_code.get("app.py", "") if ai_code else f'''from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def health():
    return jsonify({{"status": "ok", "name": "{name}"}})

@app.route("/api/data", methods=["GET", "POST"])
def data():
    if request.method == "POST":
        return jsonify({{"received": request.json}})
    return jsonify({{"message": "API funcionando"}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)'''
        self._write_file(project_dir / "app.py", app_code)
        files.append("app.py")

        templates_dir = project_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        index_html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{name}</title>
</head>
<body>
    <h1>{name}</h1>
    <p>{desc}</p>
</body>
</html>'''
        self._write_file(templates_dir / "index.html", index_html)
        files.append("templates/index.html")

        req = "flask\nflask-cors\nrequests"
        self._write_file(project_dir / "requirements.txt", req)
        files.append("requirements.txt")
        return files

    async def _fastapi_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        main_code = ai_code.get("main.py", "") if ai_code else f'''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="{name}", description="{desc}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Item(BaseModel):
    name: str
    description: Optional[str] = None

@app.get("/")
def root():
    return {{"name": "{name}", "status": "running"}}

@app.get("/api/health")
def health():
    return {{"status": "ok"}}

@app.post("/api/items")
def create_item(item: Item):
    return {{"item": item.dict(), "created": True}}

@app.get("/api/items")
def list_items():
    return {{"items": [], "count": 0}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)'''
        self._write_file(project_dir / "main.py", main_code)
        files.append("main.py")

        req = "fastapi\nuvicorn\npydantic"
        self._write_file(project_dir / "requirements.txt", req)
        files.append("requirements.txt")
        return files

    async def _vanilla_html_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        features_html = "\n".join([f'<div class="feature"><h3>{f}</h3><p>Descrição da funcionalidade {f}</p></div>' for f in features]) if features else '<div class="feature"><h3>Funcionalidade Principal</h3></div>'
        html = ai_code.get("index.html", "") if ai_code else f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}</title>
    <style>
        :root {{ --primary: #6366f1; --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --muted: #94a3b8; --border: #334155; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
        .hero {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 4rem 2rem; text-align: center; }}
        .hero h1 {{ font-size: 3rem; margin-bottom: 1rem; }}
        .hero p {{ font-size: 1.2rem; opacity: 0.9; max-width: 600px; margin: 0 auto; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        .features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 2rem; }}
        .feature {{ background: var(--card); padding: 2rem; border-radius: 12px; border: 1px solid var(--border); }}
        .feature h3 {{ color: var(--primary); margin-bottom: 0.5rem; }}
        .cta {{ text-align: center; margin-top: 3rem; }}
        .cta a {{ background: var(--primary); color: white; padding: 1rem 2rem; border-radius: 8px; text-decoration: none; font-weight: 600; }}
        footer {{ text-align: center; padding: 2rem; color: var(--muted); }}
    </style>
</head>
<body>
    <section class="hero">
        <h1>{name}</h1>
        <p>{desc}</p>
    </section>
    <div class="container">
        <div class="features">
            {features_html}
        </div>
        <div class="cta">
            <a href="#">Começar Agora</a>
        </div>
    </div>
    <footer>
        <p>&copy; 2026 {name}. Gerado por NexusAgent AI.</p>
    </footer>
</body>
</html>'''
        self._write_file(project_dir / "index.html", html)
        files.append("index.html")

        css = ai_code.get("style.css", "") if ai_code else "/* Estilos inline no HTML */"
        self._write_file(project_dir / "style.css", css)
        files.append("style.css")
        return files

    async def _android_kotlin_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.{name.lower().replace(' ', '')}.app">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="{name}"
        android:theme="@style/Theme.MaterialComponents.DayNight">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>'''
        self._write_file(project_dir / "AndroidManifest.xml", manifest)
        files.append("AndroidManifest.xml")

        build_gradle = f'''plugins {{
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}}

android {{
    namespace 'com.{name.lower().replace(' ', '')}.app'
    compileSdk 34

    defaultConfig {{
        applicationId "com.{name.lower().replace(' ', '')}.app"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }}

    buildTypes {{
        release {{
            minifyEnabled false
        }}
    }}

    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}

    kotlinOptions {{
        jvmTarget = '1.8'
    }}
}}

dependencies {{
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.11.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.google.code.gson:gson:2.10.1'
}}'''
        self._write_file(project_dir / "build.gradle", build_gradle)
        files.append("build.gradle")

        layout_dir = project_dir / "res" / "layout"
        layout_dir.mkdir(parents=True, exist_ok=True)
        main_layout = f'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:gravity="center"
    android:padding="24dp"
    android:background="#0F172A">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="{name}"
        android:textColor="#F1F5F9"
        android:textSize="28sp"
        android:textStyle="bold"
        android:layout_marginBottom="16dp" />

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="{desc}"
        android:textColor="#94A3B8"
        android:textSize="16sp"
        android:gravity="center"
        android:layout_marginBottom="32dp" />

    <Button
        android:id="@+id/btnStart"
        android:layout_width="match_parent"
        android:layout_height="56dp"
        android:text="Iniciar"
        android:backgroundTint="#6366F1"
        android:textColor="#FFFFFF"
        android:textSize="16sp" />

</LinearLayout>'''
        self._write_file(layout_dir / "activity_main.xml", main_layout)
        files.append("res/layout/activity_main.xml")

        return files

    async def _python_cli_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        cli_code = ai_code.get("cli.py", "") if ai_code else f'''#!/usr/bin/env python3
""" {name} - {desc} """

import argparse
import sys
import json

def main():
    parser = argparse.ArgumentParser(description="{desc}")
    parser.add_argument("--version", action="version", version="1.0.0")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    for cmd in ["start", "status", "config"]:
        subparsers.add_parser(cmd, help=f"Executa {{cmd}}")

    args = parser.parse_args()

    if args.command == "start":
        print("🚀 Iniciando {name}...")
    elif args.command == "status":
        print("✅ Status: Ativo")
    elif args.command == "config":
        print("⚙️  Configurações carregadas")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()'''
        self._write_file(project_dir / "cli.py", cli_code)
        files.append("cli.py")
        self._write_file(project_dir / "requirements.txt", "argparse\njson")
        files.append("requirements.txt")
        return files

    async def _node_express_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {
                "start": "node server.js",
                "dev": "nodemon server.js"
            },
            "dependencies": {
                "express": "^4.18.0",
                "cors": "^2.8.5",
                "dotenv": "^16.3.0"
            }
        }
        self._write_file(project_dir / "package.json", json.dumps(pkg, indent=2))
        files.append("package.json")

        server_code = ai_code.get("server.js", "") if ai_code else f'''const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {{
  res.json({{ name: '{name}', status: 'running' }});}});

app.get('/api/health', (req, res) => {{
  res.json({{ status: 'ok', uptime: process.uptime() }});}});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {{
  console.log(`🚀 ${{name}} rodando na porta ${{PORT}}`);
}});'''
        self._write_file(project_dir / "server.js", server_code)
        files.append("server.js")
        return files

    async def _vue_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"vue": "^3.4.0", "vue-router": "^4.2.0"},
            "devDependencies": {"@vitejs/plugin-vue": "^5.0.0", "vite": "^5.0.0"}
        }
        self._write_file(project_dir / "package.json", json.dumps(pkg, indent=2))
        files.append("package.json")

        app_vue = ai_code.get("App.vue", "") if ai_code else f'''<template>
  <div class="app">
    <h1>{name}</h1>
    <p>{desc}</p>
  </div>
</template>

<script setup>
</script>

<style scoped>
.app {{ padding: 2rem; text-align: center; }}
h1 {{ color: #6366f1; }}
</style>'''
        src = project_dir / "src"
        src.mkdir(exist_ok=True)
        self._write_file(src / "App.vue", app_vue)
        files.append("src/App.vue")
        return files

    async def _svelte_template(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        pkg = {
            "name": name.lower().replace(" ", "-"),
            "scripts": {"dev": "vite dev", "build": "vite build"},
            "devDependencies": {"@sveltejs/vite-plugin-svelte": "^3.0.0", "svelte": "^4.2.0", "vite": "^5.0.0"}
        }
        self._write_file(project_dir / "package.json", json.dumps(pkg, indent=2))
        files.append("package.json")

        src = project_dir / "src"
        src.mkdir(exist_ok=True)
        app_svelte = ai_code.get("App.svelte", "") if ai_code else f'''<script>
  let name = '{name}'
</script>

<main>
  <h1>{{name}}</h1>
  <p>{desc}</p>
</main>

<style>
  main {{ padding: 2rem; text-align: center; }}
  h1 {{ color: #6366f1; }}
</style>'''
        self._write_file(src / "App.svelte", app_svelte)
        files.append("src/App.svelte")
        return files

    async def _generic_project(self, project_dir, name, desc, features, ai_code=None) -> list:
        files = []
        readme = f"# {name}\n\n{desc}\n\n## Features\n"
        for f in features:
            readme += f"- {f}\n"
        self._write_file(project_dir / "README.md", readme)
        files.append("README.md")
        return files

    async def _create_readme(self, project_dir, name, desc, project_type, features):
        readme = f'''# {name}

{desc}

## Tipo do Projeto
{project_type}

## Funcionalidades
{chr(10).join([f"- {f}" for f in features]) if features else "- Funcionalidade principal"}

## Como Usar

```bash
# Instalar dependências
npm install  # ou pip install -r requirements.txt

# Rodar
npm run dev  # ou python app.py
```

## Gerado por
NexusAgent AI - Agente Autônomo
'''
        self._write_file(project_dir / "README.md", readme)

    async def _zip_project(self, project_dir: Path) -> Path:
        zip_path = project_dir.with_suffix(".zip")
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, filenames in os.walk(str(project_dir)):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    arcname = os.path.relpath(file_path, str(project_dir.parent))
                    zf.write(file_path, arcname)
        return zip_path

    def _write_file(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "w", encoding="utf-8") as f:
            f.write(content)

code_generator = CodeGenerator()
