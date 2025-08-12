import os
import struct
import numpy as np
from typing import List, Dict, Any
from openai import OpenAI
from services.common.db import SessionLocal
from services.common.models import CodeChunk

EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


def _to_bytes(vector: List[float]) -> bytes:
    """Convert a list of floats to bytes for storage."""
    return struct.pack(f"{len(vector)}f", *vector)


async def upsert_changed_files(repo: str, files: List[Dict[str, Any]]) -> None:
    """Create embeddings for changed files and store in database."""
    client = OpenAI()
    
    async with SessionLocal() as s:
        for f in files:
            if f.get("patch"):
                text_blob = f.get("filename", "") + "\n" + f["patch"]
                
                # Create embedding for the text
                emb = client.embeddings.create(
                    model=EMBED_MODEL,
                    input=text_blob
                ).data[0].embedding
                
                # Store code chunk with embedding
                s.add(CodeChunk(
                    repo=repo,
                    path=f["filename"],
                    start_line=1,
                    end_line=10**9,  # Large number to represent "end of file"
                    text=text_blob,
                    embedding=_to_bytes(emb)
                ))
        
        await s.commit()
