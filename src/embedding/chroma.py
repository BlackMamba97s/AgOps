import time
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader, SitemapLoader, DirectoryLoader, UnstructuredMarkdownLoader
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from openai import RateLimitError

from tqdm import tqdm
import os

BATCH_SIZE = 20
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

class ChromaSme:

    def __init__(self, db_index):
        embeddings = AzureOpenAIEmbeddings(
            api_key          = os.getenv('AZURE_API_KEY_GPT4'),
            api_version      = os.getenv('AZURE_EMBEDDING_VERSION'),
            azure_deployment = os.getenv('AZURE_EMBEDDING_MODEL'),
            azure_endpoint   = os.getenv('AZURE_ENDPOINT'),
        )

        self.db = Chroma(
            persist_directory  = os.getenv('VECTORIAL_DB_PATH'),
            embedding_function = embeddings,
            collection_name    = db_index
        )

# ================================================
    def __loadDocs(self, docs):
        print(f"Loading {len(docs)} documents")
        pbar = tqdm(range(0, len(docs), BATCH_SIZE))

        for i in pbar:
            end = min(i + BATCH_SIZE, len(docs))
            batch = docs[i:end]
            while True:
                try:
                    pbar.set_description(f"Processing {i}")
                    self.db.add_documents(batch)
                    break
                except RateLimitError:
                    pbar.set_description(f"Rate limit error, sleeping for a bit and retrying")
                    pbar.refresh()
                    time.sleep(10)

        self.db.persist()

# ================================================
    def loadWebDocument(self, url: str):
        loader = WebBaseLoader(url)
        docs = loader.load_and_split(RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP))
        self.__loadDocs(docs)

# ================================================
    def loadSiteMap(self, url: str, filter_urls: [str], parsing_function=None):
        loader = SitemapLoader(url, filter_urls=filter_urls, parsing_function=parsing_function)
        docs = loader.load_and_split(RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP))
        self.__loadDocs(docs)

# ================================================
    def loadMarkdown(self, directory: str):
        loader = DirectoryLoader(directory, glob="**/*.md", use_multithreading=True, show_progress=True, loader_cls=UnstructuredMarkdownLoader)
        docs = loader.load_and_split(RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP))
        self.__loadDocs(docs)

# ================================================
    def getDb(self):
        return self.db