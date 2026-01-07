from core.memory_manager import ConversationMemory

# Instância global de memória (wrapper para manter compatibilidade)
memory = ConversationMemory()

def get_memory_instance():
    return memory

def extract_names_from_text(text: str) -> set:
    """
    Extrai nomes próprios de um texto usando heurísticas.
    Retorna conjunto de nomes capitalizados que parecem ser nomes de pessoas.
    """
    import re
    
    # Palavras comuns que não são nomes (stopwords em português)
    stopwords = {
        'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'eu', 'você', 'ele', 'ela',
        'nós', 'vocês', 'eles', 'elas', 'meu', 'minha', 'seu', 'sua', 'dele', 'dela',
        'nosso', 'nossa', 'este', 'esta', 'esse', 'essa', 'aquele', 'aquela', 'como',
        'para', 'por', 'com', 'sem', 'sobre', 'entre', 'quando', 'onde', 'porque',
        'qual', 'quem', 'como', 'estou', 'está', 'são', 'foi', 'será', 'olá', 'oi',
        'tchau', 'obrigado', 'obrigada', 'desculpe', 'prazer', 'conhecer'
    }
    
    # Encontrar palavras capitalizadas
    words = re.findall(r'\b[A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][a-zàáâãäåçèéêëìíîïñòóôõöùúûü]+\b', text)
    
    # Filtrar nomes válidos (não stopwords, 2-15 caracteres)
    names = set()
    for word in words:
        word_lower = word.lower()
        if word_lower not in stopwords and 2 <= len(word) <= 15:
            names.add(word)
    
    return names

def extract_identity_from_memory(mem_instance=None) -> dict:
    """
    Analisa memória semântica para extrair informações de identidade.
    
    Args:
        mem_instance: Instância de ConversationMemory (opcional, usa global se None)

    Returns:
        dict: {user_name, assistant_name, spouse_name, friends}
    """
    # Usar instância injetada ou global
    current_mem = mem_instance if mem_instance else memory
    
    # Inicializar variáveis locais para uso durante a análise
    user_name = None
    assistant_name = None
    spouse_name = None
    friends = set()
    
    try:
        # Tenta importar hybrid search (feature flag e função)
        try:
            from core.hybrid_adapter import hybrid_search, is_hybrid_enabled
            use_hybrid = is_hybrid_enabled()
        except ImportError:
            use_hybrid = False
            def hybrid_search(*args, **kwargs): return {}

        # 1. Buscar NOME DO USUÁRIO e ASSISTENTE (Semantic Search Padrão)
        results = current_mem.search_memory_semantic("meu nome é seu nome é", k=15)
        
        for result in results:
            text = result['text']
            text_lower = text.lower()
            
            if not user_name and 'meu nome é' in text_lower and result['source'] == 'user':
                parts = text_lower.split('meu nome é')
                if len(parts) > 1:
                    name_part = parts[1].split(',')[0].split('.')[0].strip()
                    if name_part and len(name_part) < 20:
                        user_name = name_part.title()
            
            if not assistant_name and 'seu nome é' in text_lower and result['source'] == 'user':
                parts = text_lower.split('seu nome é')
                if len(parts) > 1:
                    name_part = parts[1].split(',')[0].split('.')[0].strip()
                    if name_part and len(name_part) < 20:
                        assistant_name = name_part.title()

        # 2. Buscar AMIGOS E FAMILIARES (Hybrid Search ou Fallback)
        if use_hybrid:
             # Busca híbrida para "Friends" como solicitado:
             # Retira regex complexo, usa busca semântica/esparsa e lista os snippets encontrados.
             h_results = hybrid_search(
                 query="quem são meus amigos familiares e pessoas conhecidas?", 
                 k_memory=10, 
                 k_docs=0
             )
             
             mem_snips = h_results.get('mem_snips', [])
             
             for snip in mem_snips:
                 t = snip['text'].strip()
                 # Evitar auto-referência
                 if user_name and user_name.lower() in t.lower(): continue
                 if assistant_name and assistant_name.lower() in t.lower(): continue
                 
                 # Adiciona o texto do snippet diretamente
                 if len(t) < 100: 
                     friends.add(t)
        else:
            # Fallback (Se hybrid desativado/indisponível)
            # Mantém comportamento "vazio" ou mínimo pra não usar regex se o usuário não quer
            pass
        
    except Exception as e:
        print(f"⚠️ Erro ao buscar identidade no vectorstore: {e}")
    
    return {
        'user_name': user_name,
        'assistant_name': assistant_name,
        'spouse_name': spouse_name,
        'friends': sorted(list(friends))
    }
