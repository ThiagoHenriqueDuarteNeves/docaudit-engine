"""
Text Utilities for RAG Retrieval
PT-BR tokenizer, query extraction, and term analysis
"""
import re
import unicodedata
from typing import Optional


# Portuguese stopwords (common words to ignore in sparse search)
PT_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "em", "um", "uma", "para", "com",
    "não", "nao", "que", "os", "as", "dos", "das", "na", "no", "se",
    "por", "mais", "mas", "como", "foi", "são", "sao", "ser", "tem",
    "seu", "sua", "ou", "quando", "muito", "nos", "já", "ja", "eu",
    "também", "tambem", "só", "so", "pelo", "pela", "até", "ate",
    "isso", "ela", "ele", "entre", "depois", "sem", "mesmo", "aos",
    "ter", "seus", "quem", "nas", "me", "esse", "eles", "você", "voce",
    "essa", "num", "nem", "suas", "meu", "às", "as", "minha", "têm",
    "numa", "pelos", "elas", "qual", "nós", "nos", "lhe", "deles",
    "essas", "esses", "pelas", "este", "dele", "tu", "te", "vocês",
    "vos", "lhes", "meus", "minhas", "teu", "tua", "teus", "tuas",
    "nosso", "nossa", "nossos", "nossas", "dela", "delas", "esta",
    "estes", "estas", "aquele", "aquela", "aqueles", "aquelas", "isto",
    "aquilo", "estou", "está", "esta", "estamos", "estão", "estao",
    "estive", "esteve", "estivemos", "estiveram", "estava", "estávamos",
    "estavam", "estivera", "estivéramos", "esteja", "estejamos", "estejam",
    "estivesse", "estivéssemos", "estivessem", "estiver", "estivermos",
    "estiverem", "hei", "há", "ha", "havemos", "hão", "hao", "houve",
    "houvemos", "houveram", "houvera", "houvéramos", "haja", "hajamos",
    "hajam", "houvesse", "houvéssemos", "houvessem", "houver", "houvermos",
    "houverem", "houverei", "houverá", "houveremos", "houverão", "houveria",
    "houveríamos", "houveriam", "sou", "somos", "são", "sao", "era",
    "éramos", "eram", "fui", "fomos", "foram", "fora", "fôramos",
    "seja", "sejamos", "sejam", "fosse", "fôssemos", "fossem", "for",
    "formos", "forem", "serei", "será", "sera", "seremos", "serão", "serao",
    "seria", "seríamos", "seriam", "tenho", "tem", "temos", "têm", "tem",
    "tinha", "tínhamos", "tinham", "tive", "teve", "tivemos", "tiveram",
    "tivera", "tivéramos", "tenha", "tenhamos", "tenham", "tivesse",
    "tivéssemos", "tivessem", "tiver", "tivermos", "tiverem", "terei",
    "terá", "tera", "teremos", "terão", "terao", "teria", "teríamos", "teriam",
}


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents, clean whitespace"""
    # Lowercase
    text = text.lower()
    
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    return text


def tokenize_ptbr(text: str, remove_stopwords: bool = True) -> list[str]:
    """
    Simple PT-BR tokenizer
    - Lowercase
    - Remove punctuation (keep numbers and IDs like CPF, CNPJ)
    - Optionally remove stopwords
    """
    # Normalize
    text = normalize_text(text)
    
    # Keep alphanumeric and some special chars for IDs
    # Pattern: letters, numbers, dots in numbers (3.14), hyphens in IDs (123-456)
    tokens = re.findall(r'\b[a-z0-9]+(?:[.\-][a-z0-9]+)*\b', text)
    
    # Filter short tokens and stopwords
    if remove_stopwords:
        tokens = [t for t in tokens if len(t) > 1 and t not in PT_STOPWORDS]
    else:
        tokens = [t for t in tokens if len(t) > 1]
    
    return tokens


def extract_acronyms(text: str) -> list[str]:
    """Extract acronyms (2+ uppercase letters)"""
    return re.findall(r'\b[A-Z]{2,}\b', text)


def extract_numbers(text: str) -> list[str]:
    """Extract numbers and IDs (CPF, CNPJ, codes)"""
    # Match: pure numbers, formatted numbers (123.456.789-00), codes (ABC-123)
    patterns = [
        r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',  # CPF
        r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',  # CNPJ
        r'\b\d+(?:[.,]\d+)*\b',  # Numbers
        r'\b[A-Z]{2,3}-?\d{3,}\b',  # Codes like ABC-123
    ]
    
    results = []
    for pattern in patterns:
        results.extend(re.findall(pattern, text))
    
    return list(set(results))


def extract_proper_nouns(text: str) -> list[str]:
    """Extract likely proper nouns (capitalized words not at sentence start)"""
    # Split into sentences
    sentences = re.split(r'[.!?]\s+', text)
    
    proper_nouns = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) > 1:
            # Skip first word (might be capitalized just because it starts sentence)
            for word in words[1:]:
                if word and word[0].isupper() and len(word) > 2:
                    # Clean punctuation
                    clean = re.sub(r'[^\w]', '', word)
                    if clean and clean[0].isupper():
                        proper_nouns.append(clean.lower())
    
    return list(set(proper_nouns))


def extract_sparse_query(query: str) -> str:
    """
    Extract keywords for sparse (BM25) search
    Focus on: keywords, acronyms, numbers, proper nouns
    """
    parts = []
    
    # Acronyms (high value for BM25)
    acronyms = extract_acronyms(query)
    parts.extend(acronyms)
    
    # Numbers and IDs
    numbers = extract_numbers(query)
    parts.extend(numbers)
    
    # Proper nouns
    proper_nouns = extract_proper_nouns(query)
    parts.extend(proper_nouns)
    
    # Regular tokens (no stopwords)
    tokens = tokenize_ptbr(query, remove_stopwords=True)
    parts.extend(tokens)
    
    # Dedupe while preserving order
    seen = set()
    result = []
    for p in parts:
        p_lower = p.lower()
        if p_lower not in seen:
            seen.add(p_lower)
            result.append(p_lower)
    
    return ' '.join(result)


def extract_dense_query(query: str) -> str:
    """
    Extract query for dense (embedding) search
    Keep natural language structure for semantic understanding
    """
    # Light normalization: just clean whitespace
    return ' '.join(query.split())


def must_have_terms(query: str) -> list[str]:
    """
    Extract terms that MUST appear in good results
    These are high-specificity terms: acronyms, numbers, proper nouns
    """
    must_have = []
    
    # Acronyms are almost always important
    acronyms = extract_acronyms(query)
    must_have.extend([a.lower() for a in acronyms])
    
    # Numbers/IDs are usually specific
    numbers = extract_numbers(query)
    must_have.extend([n.lower() for n in numbers])
    
    # Proper nouns in quotes are especially important
    quoted = re.findall(r'"([^"]+)"', query)
    for q in quoted:
        must_have.extend(tokenize_ptbr(q, remove_stopwords=False))
    
    return list(set(must_have))


def check_term_coverage(text: str, terms: list[str]) -> tuple[int, int]:
    """
    Check how many must-have terms appear in text
    Returns (found_count, total_terms)
    """
    if not terms:
        return (0, 0)
    
    text_lower = text.lower()
    found = sum(1 for t in terms if t in text_lower)
    
    return (found, len(terms))


def truncate_text(text: str, max_chars: int = 1600) -> str:
    """Truncate text at word boundary"""
    if len(text) <= max_chars:
        return text
    
    # Find last space before limit
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    
    if last_space > max_chars * 0.8:  # If space is reasonably close to end
        return truncated[:last_space] + "..."
    
    return truncated + "..."
