import collections
import os
import io
import re
import threading
import time
import chromadb
from docx import Document
from openai.types import embedding
from fastembed import TextEmbedding

EMBED_MODEL = "intfloat/multilingual-e5-large"
embedder = TextEmbedding(model_name=EMBED_MODEL)

chroma = chromadb.PersistentClient(path="chroma_db")
collection = chroma.get_or_create_collection(name="user_docs_5large",metadata={"hnsw:space":"cosine"})

ALLOWED_EXTENSIONS = (".docx",".txt",".md")
MAX_FILE_SIZE = 1024*1024*8
MAX_CHUNK = 150
MAX_DOCS = 5

index_lock = threading.Lock() #Отправление одного файла за раз
model_lock = threading.Lock() #Отсправление одного запроса за раз

#Декодирование полученного файла
def extract_file(file_name,data):
    if  file_name.lower().endswith(".docx"):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join([c.text.strip() for c in row.cells]))
        return "\n\n".join(p for p in parts if p.strip())

    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1251",errors="replace")


#Разбиваем текст сначала на абзацы,затем на куски по 150-250 слов
def split_for_chunks(text,max_churs = 1000,overlap = 150):
    pieces = []

    for p in re.split(r"\n\s*\n",text):
        p = p.strip()
        while len(p) > max_churs:
            pieces.append(p[:max_churs])
            p = p[max_churs - overlap:]
        if p:
            pieces.append(p)

    chunks = []
    current_chunk = ""
    for p in pieces:
        if  current_chunk and len(current_chunk) + len(p) + 2 > max_churs:
            chunks.append(current_chunk)
            current_chunk = current_chunk[-overlap:] + "\n\n" + p
        else:
            current_chunk = (current_chunk + "\n\n" + p) if current_chunk else p

    if current_chunk:
        chunks.append(current_chunk)
    return chunks

#Превращаем куски текста в наборы символов, то есть в вектора
def embed(texts):
    with model_lock:
         return [vector.tolist() for vector in embedder.embed(["passage: " + t for t in texts])]

def embed_query(text):
    with model_lock:
        vector =  list(embedder.embed(["query: " + text]))
        return vector[0].tolist()

def add_document(user_id,file_name,data):
    with index_lock:
        chuncks = split_for_chunks(extract_file(file_name,data))[:MAX_CHUNK]
        if not chuncks:
            raise ValueError("В файле нет текста")
        collection.delete(where={"$and": [{"user_id": user_id}, {"source": file_name}]})
        for start in range(0,len(chuncks),16):
            part = chuncks[start:start + 16]
            collection.upsert(ids=[f"{user_id}:{file_name}:{start + i}" for i in range(len(part))],
            documents=part,
            embeddings=embed(part),
            metadatas=[{"user_id":user_id,"source":file_name} for _ in part],
            )
        return len(chuncks)

#Проверка наличия какого либо документа
def has_documents(user_id):
    return bool(collection.get(where={"user_id":user_id},limit=1)["ids"])

#Список всех документов пользователя
def list_documents(user_id):
    res = collection.get(where={"user_id": user_id}, include=["metadatas"])
    return sorted({str(m["source"]) for m in (res["metadatas"] or [])})

#Определенный документ
def delete_document(user_id,file_name):
    collection.delete(where={"$and":[{"user_id": user_id},{"source":file_name}]})
#Все документы
def delete_documents(user_id):
    collection.delete(where={"user_id": user_id})
#Составление списка документов
def search_documents(user_id,question,k=3):
    vec = embed_query([question][0])
    response = collection.query(query_embeddings=[vec],n_results=k,where={"user_id":user_id})
    return list(zip(response["documents"][0],response["metadatas"][0]))

