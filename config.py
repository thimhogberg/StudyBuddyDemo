"""
Konfigurationsfil för Chalmers Course Graph
"""
import os
from dotenv import load_dotenv

# Ladda miljövariabler från .env
#load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env")) # Om du lagrar .env en nivå upp, annars välj ovanstående rad

# Neo4j konfiguration
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# LiteLLM konfiguration
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "anthropic/claude-opus-4")

# Canvas konfiguration
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")

# Data paths
DATA_DIR = "data"
COURSE_FILE = os.path.join(DATA_DIR, "course_summary_full.json")