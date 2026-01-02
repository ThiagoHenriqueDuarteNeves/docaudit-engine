import os
import lmstudio as lms
import re
from pathlib import Path
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

# Imports do Core
from core import config, llm, memory, documents
from core.memory import extract_identity_from_memory

# Hybrid Retrieval (experimental)
try:
    from core.hybrid_adapter import is_hybrid_enabled, hybrid_search, format_hybrid_snips_for_context, get_available_documents
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False
    def is_hybrid_enabled(): return False
    def get_available_documents(): return []

# Imports Legados (por enquanto)
# from document_manager import DocumentManager # Removido
from tools import DocumentSearchTool, MemorySearchTool
from router import classify_query_simple

# Inicializar Gerenciadores
doc_manager = documents.get_doc_manager()

# Tools
doc_tool = DocumentSearchTool(doc_manager)
mem_tool = MemorySearchTool(memory.get_memory_instance())

# System Prompt - Simplificado para modelos pequenos
# System Prompt - Anti-Hallucination RAG
SYSTEM_PROMPT = """Você é Aurora.

OBJETIVO
Ajudar o usuário com respostas úteis, corretas e verificáveis, usando memória híbrida e RAG. Você deve maximizar precisão sem perder clareza.

REGRAS DE IDENTIDADE E TOM
1) IDENTIDADE: Você é Aurora. Não diga que é "assistente", "modelo", "IA" ou termos similares.
2) TOM: Natural, direto e amigável. Sem floreios excessivos. Respeite pronomes e preferências do usuário.
3) ROLEPLAY: Se o usuário pedir interpretação de personagem, adote a persona solicitada, mantendo segurança e fatos do contexto.

POLÍTICA DE FONTES (PRIORIDADE)
Use as fontes nesta ordem:
A) <context_data> (memória + documentos recuperados) = fonte principal.
B) <chat_history> (continuidade da conversa) = apoio.
C) Conhecimento geral (raciocínio e conceitos comuns) = permitido SOMENTE para explicar termos e preencher lacunas sem inventar fatos específicos.
Se houver conflito entre A e B, priorize A e sinalize o conflito.

FIDELIDADE E ANTI-ALUCINAÇÃO
4) Você NÃO deve inventar detalhes (nomes, datas, números, procedimentos) que não estejam em <context_data> ou <chat_history>.
5) Se a pergunta exigir informação que não está no contexto:
   - diga explicitamente o que está faltando
   - ofereça 1–3 caminhos objetivos para obter a informação (ex.: "buscar mais documentos", "rodar nova consulta", "ajustar filtro")
   - se possível, responda parcialmente com o que existe no contexto.
6) Quando a evidência for fraca, use linguagem de incerteza ("pelo que aparece no trecho...", "não há confirmação no contexto...").

MEMÓRIA HÍBRIDA (COMO TRATAR)
7) Trate "INFORMAÇÕES DA MEMÓRIA" como fatos lembrados, mas sujeitos a erro/atualização.
   - Se uma memória contradiz documentos, prefira documentos.
   - Se memórias forem vagas, peça ou sugira confirmação.
8) Nunca exponha identificadores internos do banco ou embeddings. Use apenas o texto dos snippets.

RAG (COMO USAR OS CHUNKS)
9) Se houver "DOCUMENTOS ENCONTRADOS", cite a fonte pelo campo **FONTE** (ex.: "Documentação LM Studio.pdf") e referencie o trecho usado.
10) Evite colar trechos grandes. Prefira resumir e, quando necessário, citar frases curtas.

FORMATO DE RESPOSTA (PADRÃO)
11) Responda em português claro e direto.
12) Estrutura sugerida:
   - Resposta objetiva (1–6 linhas)
   - Evidências (bullets curtos com "Fonte: ..." + trecho/paráfrase)
   - Próximos passos (se faltar algo ou se houver ambiguidade)"""

# Prompt Template
prompt = ChatPromptTemplate.from_template("""
<system_instruction>
{system_prompt}
</system_instruction>

<context_data>
{context}
</context_data>

<chat_history>
{chat_history}
</chat_history>

<user_query>
{question}
</user_query>

<response_guidance>
- Use <context_data> como base principal.
- Se precisar usar conhecimento geral, deixe claro que é explicação conceitual, não fato do documento.
- Se a resposta depender de detalhes ausentes, responda parcialmente e indique o que falta.
</response_guidance>
""")

def save_debug_files(user_message: str, formatted_prompt: str, llm_response: str):
    """Salva prompt e resposta em arquivos separados para análise"""
    try:
        # Usar caminho relativo ao projeto
        base_dir = Path(".").resolve()
        prompts_dir = base_dir / "prompts"
        respostas_dir = base_dir / "respostas"
        
        prompts_dir.mkdir(exist_ok=True)
        respostas_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        prompt_file = prompts_dir / f"prompt_{timestamp}.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(f"=== MENSAGEM DO USUÁRIO ===\n{user_message}\n\n")
            f.write(f"=== PROMPT COMPLETO ENVIADO AO LLM ===\n{formatted_prompt}")
        
        resposta_file = respostas_dir / f"resposta_{timestamp}.txt"
        with open(resposta_file, "w", encoding="utf-8") as f:
            f.write(f"=== PERGUNTA ===\n{user_message}\n\n")
            f.write(f"=== RESPOSTA DO LLM ===\n{llm_response}")
            
    except Exception as e:
        print(f"⚠️ [CHAT] Erro ao salvar debug: {e}")

def fix_pronoun_errors(question: str, response: str, identity_info: dict) -> str:
    """Corrige erros de pronomes na resposta do modelo."""
    question_lower = question.lower().strip()
    user_name = str(identity_info.get('user_name') or '').strip()
    assistant_name = str(identity_info.get('assistant_name') or '').strip()
    
    # "qual meu nome?"
    if any(p in question_lower for p in ['qual meu nome', 'meu nome é', 'qual o meu nome', 'meu nome', 'eu sou']):
        if user_name:
            if f"meu nome é {user_name.lower()}" in response.lower():
                response = re.sub(f"meu nome é {user_name}", f"Seu nome é {user_name}", response, flags=re.IGNORECASE)
            # Confusão: modelo diz seu nome quando deveria dizer do usuário
            if assistant_name and f"meu nome é {assistant_name.lower()}" in response.lower() and user_name.lower() not in response.lower():
                response = re.sub(f"meu nome é {assistant_name}", f"Seu nome é {user_name}", response, flags=re.IGNORECASE)
    
    # "qual seu nome?"
    elif any(p in question_lower for p in ['qual seu nome', 'qual o seu nome', 'você é', 'você se chama']):
        if assistant_name:
            if f"seu nome é {assistant_name.lower()}" in response.lower():
                response = re.sub(f"seu nome é {assistant_name}", f"Meu nome é {assistant_name}", response, flags=re.IGNORECASE)
            # Confusão: modelo diz nome do usuário quando deveria dizer seu
            if user_name and f"meu nome é {user_name.lower()}" in response.lower() and assistant_name.lower() not in response.lower():
                response = re.sub(f"meu nome é {user_name}", f"Meu nome é {assistant_name}", response, flags=re.IGNORECASE)
    
    return response

def build_chat_context(message: str, history: list, memory_override=None, image: str = None) -> dict:
    """Constrói o contexto e o prompt final para a mensagem."""
    local_memory = memory_override if memory_override else memory.get_memory_instance()
    local_mem_tool = MemorySearchTool(local_memory) if memory_override else mem_tool
    
    chat_history_text = local_memory.format_for_langchain(limit=2)
    identity_info = extract_identity_from_memory(mem_instance=local_memory)
    labels = classify_query_simple(message)
    message_lower = message.lower()
    
    # Identidade
    identity_keywords = ['nome', 'chama', 'quem é', 'quem sou', 'você é', 'esposa', 'mulher', 'família', 'amigo', 'apresentar']
    is_identity_question = any(kw in message_lower for kw in identity_keywords)
    
    # Memória
    mem_snips = local_mem_tool.invoke(query=message, k=5)
    
    if is_identity_question:
        identity_queries = [
            "seu nome é meu nome é", "meu nome é você é", "nome chama identidade", "esposa mulher família", message
        ]
        identity_snips = []
        seen_texts = {s['text'] for s in mem_snips}
        for query in identity_queries:
            results = local_mem_tool.invoke(query=query, k=2)
            for snip in results:
                if snip['text'] not in seen_texts:
                    identity_snips.append(snip)
                    seen_texts.add(snip['text'])
        mem_snips = identity_snips + mem_snips
    
    # Filter snippets
    if mem_snips and not is_identity_question:
        filtered_snips = []
        identity_patterns = ['meu nome é', 'seu nome é', 'me chamo']
        for s in mem_snips:
            if not any(pattern in s['text'].lower() for pattern in identity_patterns):
                filtered_snips.append(s)
        mem_snips = filtered_snips

    # Format snippets
    def format_snippet(s):
        role = '[O USUÁRIO disse]' if s['source'] == 'user' else '[VOCÊ (assistente) disse]'
        return f"{role}: {s['text']}"
    
    mem_text = "\n".join([format_snippet(s) for s in mem_snips]) if mem_snips else "(Memória vazia)"
    
    # Prefixo de Identidade
    if is_identity_question:
         # Lógica simplificada se houver dados
        meta = []
        if identity_info['user_name']: meta.append(f"- USUÁRIO: {identity_info['user_name']}")
        if identity_info['assistant_name']: meta.append(f"- VOCÊ: {identity_info['assistant_name']}")
        if identity_info['spouse_name']: meta.append(f"- ESPOSA: {identity_info['spouse_name']}")
        if meta:
            mem_text = "🔑 PESSOAS IMPORTANTES:\n" + "\n".join(meta) + "\n\n" + mem_text

    # Documentos
    doc_text = ""
    
    # Usar Hybrid Retrieval se habilitado
    if HYBRID_AVAILABLE and is_hybrid_enabled():
        # Busca híbrida (dense + sparse + RRF + rerank)
        hybrid_result = hybrid_search(query=message, k_docs=5, k_memory=5)
        doc_snips = hybrid_result.get("doc_snips", [])
        
        # Merge hybrid mem_snips com os snips de identidade
        hybrid_mem = hybrid_result.get("mem_snips", [])
        if hybrid_mem:
            seen = {s['text'] for s in mem_snips}
            for hs in hybrid_mem:
                if hs['text'] not in seen:
                    mem_snips.append(hs)
                    seen.add(hs['text'])
    else:
        # Busca tradicional (apenas documentos)
        doc_snips = doc_tool.invoke(query=message, k=5)
    
    if doc_snips:
        # Listar documentos únicos encontrados
        unique_docs = set()
        doc_parts = []
        for s in doc_snips:
            doc_name = s.get('title', s.get('source', 'Documento'))
            unique_docs.add(doc_name)
            doc_parts.append(f"📄 **FONTE:** {doc_name}\n{s['text']}")
        
        docs_header = f"📚 DOCUMENTOS ENCONTRADOS: {', '.join(unique_docs)}\n"
        doc_text = docs_header + "\n---\n".join(doc_parts)

    # Contexto Final - Adicionar lista de arquivos disponíveis
    available_headlines = ""
    try:
        if HYBRID_AVAILABLE and is_hybrid_enabled():
            docs_list = get_available_documents()
            if docs_list:
                available_headlines = "📂 ARQUIVOS DISPONÍVEIS NO SISTEMA:\n" + "\n".join([f"- {d}" for d in docs_list]) + "\n\n"
    except Exception as e:
        print(f"Erro ao listar documentos: {e}")

    if doc_text:
        context = f"INFORMAÇÕES DA MEMÓRIA:\n{mem_text}\n\n{available_headlines}CONTEXTO DOS DOCUMENTOS:\n{doc_text}"
    else:
        context = f"INFORMAÇÕES DA MEMÓRIA:\n{mem_text}\n\n{available_headlines}(CONVERSA LIVRE - sem trechos relevantes encontrados)"

    formatted_prompt = prompt.format(
        system_prompt=SYSTEM_PROMPT,
        context=context,
        chat_history=chat_history_text,
        question=message
    )
    
    return {
        "formatted_prompt": formatted_prompt,
        "mem_snips": mem_snips,
        "doc_snips": doc_snips,
        "identity_info": identity_info,
        "is_identity_question": is_identity_question,
        "chat_history_text": chat_history_text,
        "labels": labels
    }

def chat_stream(message: str, history: list, memory_override=None, image: bytes = None, image_name: str = None):
    """
    Versão Streaming do chat_response.
    Gera tokens iterativamente para manter a conexão ativa.
    """
    local_memory = memory_override if memory_override else memory.get_memory_instance()
    
    try:
        # 1. Construir Contexto
        context_data = build_chat_context(message, history, memory_override, image)
        formatted_prompt = context_data["formatted_prompt"]
        
        # 2. Verificar LLM
        if llm.llm is None:
            llm.initialize_llm()
            if llm.llm is None:
                yield "❌ Erro: LM Studio desconectado."
                return

        # 3. Inferência
        full_response = ""
        
        # Lógica de Imagem (SDK)
        if image:
             # Nota: Simplificando para usar a lógica do SDK apenas se necessário
                import re
                lm_host_match = re.match(r'https?://([^/]+)', config.LM_STUDIO_URL)
                lm_api_host = lm_host_match.group(1) if lm_host_match else "localhost:1234"
                
                print(f"🎬 [VISION] Iniciando pipeline de visão. Host: {lm_api_host}")
                
                # Yield inicial para UX
                yield "👀 Analisando imagem..."

                try:
                    lms.configure_default_client(api_host=lm_api_host)
                    lms.set_sync_api_timeout(300)
                    
                    model_name = llm.current_model or "default"
                    sdk_llm_client = lms.llm(model_name)
                    
                    image_handle = lms.prepare_image(image, name=image_name)
                    chat = lms.Chat()
                    vision_prompt = f"Olhe atentamente para esta imagem e responda: {message}"
                    chat.add_user_message(vision_prompt, images=[image_handle])
                    
                    print("🚀 [VISION] Enviando para LLM... (Aguardando resposta completa)")
                    
                    # SDK do LM Studio ainda não suporta streaming fácil via lms.llm().respond_stream() na versão atual
                    # Vamos simular "pensando" para segurar a conexão
                    import time
                    import threading
                    
                    result_container = {}
                    
                    def run_infer():
                        try:
                            result_container['data'] = sdk_llm_client.respond(chat)
                        except Exception as e:
                            result_container['error'] = str(e)
                            
                    t = threading.Thread(target=run_infer)
                    t.start()
                    
                    # Keep-alive loop
                    while t.is_alive():
                        yield " " # Keep-alive char (invisible)
                        time.sleep(1)
                        
                    if 'error' in result_container:
                        raise Exception(result_container['error'])
                        
                    result = result_container.get('data')
                    response_text = str(result)
                    
                    # Envia resposta de uma vez (já que o SDK vision é sync)
                    yield response_text
                    full_response = response_text
                    
                except Exception as vision_err:
                    error_msg = str(vision_err)
                    yield f"❌ Erro Visão: {error_msg}"
                    full_response = error_msg

        else:
            # Texto Normal (LangChain Streaming)
            # Enviar chunks reais
            for chunk in llm.llm.stream(formatted_prompt):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if content:
                    yield content
                    full_response += content

        # 4. Pós-processamento (Correções e Salvamento)
        # Nota: Correções de pronomes são aplicadas no texto final salvo, 
        # mas o usuário via streaming vê o "raw". 
        # Para UX perfeita, ideal seria bufferizar, mas add complexidade.
        # Vamos manter simples: salva corrigido, mostra raw.
        
        save_debug_files(message, formatted_prompt, full_response)
        
        # Add contadores no final do stream
        mem_c = len(context_data["mem_snips"] or [])
        doc_c = len(context_data["doc_snips"] or [])
        stats_footer = f"\n\n[Contexto: memória {mem_c}, documentos {doc_c}]"
        yield stats_footer
        
        # Salvar na memória (versão corrigida idealmente, mas usando raw por simplicidade agora)
        local_memory.save_message("user", message)
        local_memory.save_message("assistant", full_response + stats_footer)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"❌ Erro ao processar: {str(e)}"
