from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
collection_name = "default"

try:
    info = client.get_collection(collection_name)
    print(f"✅ Coleção '{collection_name}' encontrada.")
    print(f"📊 Total de pontos indexados: {info.points_count}")
    
    if info.points_count > 0:
        # Listar alguns IDs de documentos (baseado no campo 'source')
        print("\n🔍 Amostra de documentos (campo 'source'):")
        points, _ = client.scroll(
            collection_name=collection_name, 
            limit=5, 
            with_payload=True, 
            with_vectors=False
        )
        seen_docs = set()
        for p in points:
            source = p.payload.get('source', 'N/A')
            if source not in seen_docs:
                print(f"   - {source}")
                seen_docs.add(source)
    else:
        print("\n⚠️ A coleção está vazia. Você clicou em 'Processar Documentos' no Frontend?")

except Exception as e:
    print(f"❌ Erro ao acessar coleção '{collection_name}': {e}")
