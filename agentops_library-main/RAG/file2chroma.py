import chromadb
from tqdm import tqdm
import json
import argparse
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--destionation_path' , required=True, help='Path nel quale creare il db partendo dalla root del container')
parser.add_argument('--root_path_file' , required=True, help='Root path in cui creare il db e in cui sono presenti le repo delle collezioni contententi i file JSON embeddings')

args = parser.parse_args()

db_path = os.path.join(args.root_path_file, args.destionation_path)
if os.path.isdir(db_path):
    print("repo già esistente")
    sys.exit(1)

collection_name_list = [
    name for name in os.listdir(os.path.join(args.root_path_file))
    if os.path.isdir(os.path.join(args.root_path_file, name))
]
chroma_client_destination = chromadb.PersistentClient(path = db_path)
for collection_name_string in collection_name_list:

    destionation_path = args.destionation_path

    
    chroma_collection_destionation = chroma_client_destination.get_or_create_collection(collection_name_string)


    directory_path = os.path.join(os.path.join(args.root_path_file, collection_name_string))

    json_files = []
    for root, _, files in os.walk(directory_path):
        for filename in files:
            if filename.lower().endswith('.json'):
                json_files.append(os.path.join(root, filename))


    for file_path in tqdm(json_files, desc="Caricamento embeddings..."):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chroma_collection_destionation.add(
                ids = [data["id"]],
                embeddings = data["embeddings"],
                metadatas = data["metadatas"],
                documents = data["documents"]
                )
        except json.JSONDecodeError as e:
            print(f"Errore JSON nel file {file_path}: {e}")
        except Exception as e:
            print(f"Errore generico nel file {file_path}: {e}")





