"""
Session state hantering för Chalmers Course Graph
"""
import streamlit as st


def init_session_state():
    """Initialiserar session state med alla nödvändiga variabler"""
    # Initiera om de inte redan finns
    if 'graph_filter' not in st.session_state:
        st.session_state.graph_filter = "Alla noder"
    
    if 'selected_node' not in st.session_state:
        st.session_state.selected_node = None
    
    if 'highlight_course' not in st.session_state:
        st.session_state.highlight_course = None
    
    # Se till att neo4j_service finns (för bakåtkompatibilitet)
    if 'neo4j' in st.session_state and 'neo4j_service' not in st.session_state:
        st.session_state.neo4j_service = st.session_state.neo4j


def lazy_init_canvas_api():
    """Lazy-initialiserar Canvas API endast när den behövs"""
    if 'canvas_api' not in st.session_state:
        try:
            from services.canvas_api import CanvasAPI
            st.session_state.canvas_api = CanvasAPI()
        except Exception as e:
            st.session_state.canvas_api = None
            if 'canvas_error_shown' not in st.session_state:
                st.error(f"Kunde inte initiera Canvas API: {str(e)}")
                st.session_state.canvas_error_shown = True
    return st.session_state.get('canvas_api')


def lazy_init_llm_service():
    """Lazy-initialiserar LLM service endast när den behövs"""
    if 'llm_service' not in st.session_state:
        try:
            from src.llm_service import LLMService
            st.session_state.llm_service = LLMService()
        except Exception:
            st.session_state.llm_service = None
    return st.session_state.get('llm_service')