# 🤖 RAG Chatbot - React + FastAPI + Qdrant

Um chatbot **RAG (Retrieval-Augmented Generation)** profissional de última geração, construído com uma arquitetura moderna separando Frontend e Backend. Possui memória híbrida (Qdrant + BM25), suporte multimodal (envio de imagens) e integração completa com modelos locais via **LM Studio** ou APIs compatíveis com OpenAI.

## ✨ Características Principais

- 🌐 **Frontend Moderno (React)**: Interface responsiva e rápida construída com Vite, TailwindCSS e React.
- 🚀 **Backend Robusto (FastAPI)**: API RESTful assíncrona para alta performance.
- 🧠 **Memória Híbrida Inteligente**: Combina busca vetorial (Dense) via **Qdrant** com busca lexical (BM25) para recuperação precisa de contexto.
- 📸 **Suporte Multimodal**: Envie imagens junto com texto para análise (requer modelos compatíveis com vision, ex: Llama-3.2-Vision).
- 💾 **Histórico & Persistência**: Gerenciamento completo de histórico de conversas e arquivamento.
- 🔌 **LM Studio / OpenAI**: Compatibilidade nativa com servidores locais (GGUF) ou APIs OpenAI padrão.
- 🐳 **Dockerized**: Suporte a containerização para produção.

## 🏗️ Arquitetura

O projeto evoluiu de uma aplicação monolítica Gradio para uma arquitetura micro-serviços/cliente-servidor:

```mermaid
graph TD
    User[👤 Usuário] -->|Browser| UI[💻 Frontend React (Vite)]
    UI -->|HTTP/JSON| API[⚡ Backend FastAPI]
    
    subgraph "Backend Core"
        API --> Manager[Document & Memory Manager]
        Manager -->|Busca Híbrida| Qdrant[💾 Qdrant (Vector DB)]
        Manager -->|Lexical| BM25[📝 BM25 Index]
        API -->|LLM Request| LMStudio[🤖 LM Studio / OpenAI API]
    end
    
    subgraph "Storage"
        Qdrant --> Embeddings[🔢 Embeddings]
        BM25 --> Cache[📂 File Cache]
    end
```

## 🛠️ Tech Stack

### Frontend
- **React 18** + **Vite**
- **TailwindCSS 4** (Estilização)
- **Lucide React** (Ícones)
- **React Markdown** (Renderização de respostas)

### Backend
- **FastAPI** (Python 3.11+)
- **Qdrant** (Vector Store)
- **LangChain** (Orquestração RAG)
- **Sentence Transformers** (Embeddings Locais)
- **RankBM25** (Busca Lexical)

## 📋 Pré-requisitos

- **Python 3.11+**
- **Node.js 18+** & **npm**
- **Docker** (para rodar o banco Qdrant)
- **LM Studio** (rodando localmente) ou Chave de API OpenAI

## 🚀 Quick Start (Automático)

Para ambiente Windows, fornecemos um script que sobe toda a infraestrutura:

```powershell
start_all_environments.bat
```
*Este script irá:*
1. Iniciar o container do **Qdrant**.
2. Subir a **API Backend** (Porta 8000).
3. Iniciar o servidor de desenvolvimento **Frontend** (Porta 5173).
4. Configurar túneis **Zrok** (se configurado).

---

## 💻 Instalação & Execução Manual

Se preferir rodar manualmente ou estiver no Linux/Mac:

### 1. Banco de Dados (Qdrant)
```bash
# Na raiz do projeto
docker-compose -f rag_retrieval/docker-compose.yml up -d qdrant
```

### 2. Backend (FastAPI)
```bash
# Criar e ativar ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate  # Windows
source .venv/bin/activate # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Iniciar API
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
*Acesse a documentação da API em: http://localhost:8000/docs*

### 3. Frontend (React)
```bash
cd frontend-new

# Instalar pacotes (primeira vez)
npm install

# Rodar servidor dev
npm run dev
```
*Acesse a interface em: http://localhost:5173*

## ⚙️ Configuração (.env)

O backend utiliza um arquivo `.env` na raiz. Principais variáveis:

```env
# LM Studio / LLM
LM_STUDIO_URL=http://localhost:1234/v1
# Se usar OpenAI real, adicione OPENAI_API_KEY=...

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=rag_collection

# RAG Settings
EMBEDDING_MODEL=all-MiniLM-L6-v2
USE_HYBRID_RETRIEVAL=true
```

## 📝 Primeiros Passos

1. **Abra o Frontend** (`http://localhost:5173`).
2. **Conecte o LM Studio**: Certifique-se que o servidor local do LM Studio está rodando na porta 1234.
3. **Upload de Documentos**: Vá na aba de configurações/documentos e faça upload de seus PDFs.
4. **Chat**: Inicie uma conversa. O sistema usará o RAG para buscar contexto nos seus documentos.

## 🤝 Contribuindo

1. Faça um Fork.
2. Crie uma branch (`git checkout -b feature/NovaFeature`).
3. Commit suas mudanças (`git commit -m 'Adiciona NovaFeature'`).
4. Push para a branch (`git push origin feature/NovaFeature`).
5. Abra um Pull Request.
