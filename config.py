import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
CHROMA_PATH = os.getenv("CHROMA_PATH", str(BASE_DIR / ".chroma"))
MINUTEMIND_MODEL = os.getenv("MINUTEMIND_MODEL", "llama3.1:8b")
MINUTEMIND_BACKEND = os.getenv("MINUTEMIND_BACKEND", "ollama")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
PROMPTS_DIR = BASE_DIR / "prompts"
