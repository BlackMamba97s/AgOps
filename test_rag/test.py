from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack.components.embedders.azure_text_embedder import AzureOpenAITextEmbedder
from haystack.utils import Secret
from haystack_integrations.components.retrievers.chroma import ChromaQueryTextRetriever
from haystack import Document

embedder = AzureOpenAITextEmbedder(azure_endpoint="https://caipiroska.openai.azure.com",azure_deployment="lime-ada002",api_key=Secret.from_token("f38c61eafdcb421b91cd5ce5ef51397e"))

def embedding_function(texts):
    embeddings = []
    for text in texts:
        result = embedder.run(text)
        embeddings.append(result["embedding"])
    return embeddings



try:
    print("Inizializzo document store...")
    # document_store = ChromaDocumentStore(
    #     collection_name="k8sindex",
    #     persist_path=".db",
    #     distance_function="cosine"
    # )
    document_store = ChromaDocumentStore(
        collection_name="k8sindex",
        persist_path=".db",
    )
    print("Document store inizializzato ✅")

    # try:
    #     count = document_store.count_documents()
    #     print(f"Documenti totali nella collection: {count}")
    # except Exception as e:
    #     print(f"❌ Errore durante count_documents: {e}")
    texts = ["Come funziona Kubernetes?", "Che cos'è un pod?"]
    embeddings = [
        [0.1] * 1536,
        [0.2] * 1536
    ]

    # 3. Crea gli oggetti Document con embedding già presenti
    docs = [
        Document(content=texts[0], embedding=embeddings[0], meta={"id": "doc1", "source": "manuale"}),
        Document(content=texts[1], embedding=embeddings[1], meta={"id": "doc2", "source": "manuale"})
    ]

    # 4. Scrivi i documenti nel document store
    document_store.write_documents(docs)

    docs = document_store.count_documents()
    print(f"Documenti trovati: {docs}")



    for doc in docs:
        print(f"Content: {doc.content}")
        print(f"Embedding: {doc.embedding[:5] if doc.embedding else 'No embedding'}")
        print(f"Meta: {doc.meta}")
        print("---")

except Exception as e:
    print(f"❌ Errore durante l'esecuzione: {e}")