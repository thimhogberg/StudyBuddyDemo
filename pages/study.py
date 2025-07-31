"""
Study-sida för optimerat lärande med AI-stöd
"""
import streamlit as st
import pandas as pd
from utils.session import init_session_state
from typing import Dict, List, Optional, Tuple
import json
from pyvis.network import Network
import tempfile
import time
import os
from config import LITELLM_MODEL


def render():
    """Renderar study-sidan för optimerat lärande"""
    init_session_state()
    
    st.markdown("### Studera")
    st.markdown("Lär dig koncept optimalt baserat på din kunskapsgraf")
    
    # Kontrollera om Neo4j är konfigurerad
    from config import NEO4J_URI, NEO4J_PASSWORD
    
    if not NEO4J_URI or not NEO4J_PASSWORD:
        st.error("Neo4j databas är inte konfigurerad!")
        st.markdown("""
        ### Så här konfigurerar du Neo4j:
        
        1. **Skapa en `.env` fil** i projektets rotmapp om den inte redan finns
        
        2. **Lägg till följande rader** i `.env` filen:
        ```
        NEO4J_URI=neo4j+s://din-databas-uri.neo4j.io
        NEO4J_USER=neo4j
        NEO4J_PASSWORD=ditt-databas-lösenord
        ```
        
        3. **Skapa en gratis Neo4j databas**:
           - Gå till [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/)
           - Skapa ett gratis konto
           - Skapa en ny AuraDB Free databas
           - Kopiera connection URI och lösenord till `.env` filen
        
        4. **Starta om applikationen** efter att du lagt till informationen
        
        Se README.md för mer detaljerad information.
        """)
        return
    
    if not st.session_state.neo4j_service:
        st.error("Kunde inte ansluta till Neo4j databas")
        st.info("Kontrollera att dina uppgifter är korrekta och att databasen är aktiv")
        return
    
    # Kontrollera om LiteLLM är konfigurerad
    from config import LITELLM_API_KEY, LITELLM_BASE_URL
    
    if not LITELLM_API_KEY or not LITELLM_BASE_URL:
        st.error("LiteLLM API är inte konfigurerad!")
        st.markdown("""
        ### Så här konfigurerar du LiteLLM:
        
        1. **Lägg till följande i din `.env` fil**:
        ```
        LITELLM_API_KEY=din_api_nyckel
        LITELLM_BASE_URL=din_base_url
        LITELLM_MODEL=anthropic/claude-sonnet-3.7
        ```
        
        2. **Starta om applikationen** efter att du lagt till informationen
        
        Se README.md för mer detaljerad information om LiteLLM-konfiguration.
        """)
        return
    
    # Initiera session state för study
    if 'current_concept' not in st.session_state:
        st.session_state.current_concept = None
    if 'learning_mode' not in st.session_state:
        st.session_state.learning_mode = None
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    if 'understanding_progress' not in st.session_state:
        st.session_state.understanding_progress = 0.0
    if 'study_path' not in st.session_state:
        st.session_state.study_path = None
    if 'selected_course' not in st.session_state:
        st.session_state.selected_course = None
    
    # Hämta studentens kunskapsprofil
    knowledge_profile, available_concepts = get_knowledge_profile()
    
    if not available_concepts:
        st.warning("Inga koncept hittades i grafen. Bygg först en kunskapsgraf!")
        return
    
    # Visa överblick
    col1, col2, col3 = st.columns(3)
    with col1:
        total_concepts = len(knowledge_profile)
        st.metric("Totalt antal koncept", total_concepts)
    with col2:
        mastered = sum(1 for c in knowledge_profile.values() if c.get('mastery_score', 0) >= 0.7)
        st.metric("Behärskade koncept", f"{mastered}/{total_concepts}")
    with col3:
        avg_mastery = sum(c.get('mastery_score', 0) for c in knowledge_profile.values()) / total_concepts if total_concepts > 0 else 0
        st.metric("Genomsnittlig mastery", f"{avg_mastery:.2f}")
    
    st.divider()
    
    # Välj studieväg om inte redan vald
    if not st.session_state.study_path:
        st.markdown("#### Välj din studieväg")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("##### Från grunden")
            st.info("Börja från de mest grundläggande koncepten i hela kunskapsgrafen och bygg systematiskt upp din förståelse.")
            if st.button("Välj från grunden", use_container_width=True):
                st.session_state.study_path = "from_scratch"
                st.rerun()
        
        with col2:
            st.markdown("##### Baserat på kurs")
            st.info("Välj en specifik kurs och lär dig dess koncept i optimal ordning, inklusive nödvändiga förutsättningar.")
            if st.button("Välj kursbaserat", use_container_width=True):
                st.session_state.study_path = "course_based"
                st.rerun()
        
        with col3:
            st.markdown("##### Specifikt koncept")
            st.info("Välj ett specifikt koncept du vill lära dig. Systemet säkerställer att du har rätt förutsättningar.")
            if st.button("Välj specifikt koncept", use_container_width=True):
                st.session_state.study_path = "specific_concept"
                st.rerun()
        
        return
    
    # Visa vald studieväg och möjlighet att ändra
    col1, col2 = st.columns([3, 1])
    with col1:
        path_names = {
            "from_scratch": "Från grunden",
            "course_based": "Baserat på kurs",
            "specific_concept": "Specifikt koncept"
        }
        st.info(f"Studieväg: **{path_names.get(st.session_state.study_path, st.session_state.study_path)}**")
    with col2:
        # Dropdown för att välja studieväg
        path_options = ["Från grunden", "Baserat på kurs", "Specifikt koncept"]
        current_path = path_names.get(st.session_state.study_path, "Från grunden")
        
        new_path = st.selectbox(
            "Studieväg:",
            path_options,
            index=path_options.index(current_path),
            key="study_path_selector"
        )
        
        path_map = {
            "Från grunden": "from_scratch",
            "Baserat på kurs": "course_based",
            "Specifikt koncept": "specific_concept"
        }
        
        if path_map[new_path] != st.session_state.study_path:
            st.session_state.study_path = path_map[new_path]
            st.session_state.selected_course = None
            st.session_state.current_concept = None
            st.session_state.learning_mode = None
            st.session_state.conversation_history = []
            st.session_state.understanding_progress = 0.0
            st.rerun()
    
    # Hantera olika studievägar
    if st.session_state.study_path == "course_based":
        render_course_based_learning(knowledge_profile, available_concepts)
    elif st.session_state.study_path == "specific_concept":
        render_specific_concept_learning(knowledge_profile, available_concepts)
    else:  # from_scratch
        render_from_scratch_learning(knowledge_profile, available_concepts)


def render_from_scratch_learning(knowledge_profile: Dict, available_concepts: List[Dict]):
    """Renderar lärande från grunden"""
    if not st.session_state.current_concept:
        with st.spinner(f"AI analyserar hela kunskapsgrafen för optimal lärstig...\nModell: {LITELLM_MODEL}"):
            recommendation = find_next_concept_to_learn(knowledge_profile, available_concepts)
            st.session_state.current_concept = recommendation
    
    render_concept_learning_ui(st.session_state.current_concept, knowledge_profile)


def render_course_based_learning(knowledge_profile: Dict, available_concepts: List[Dict]):
    """Renderar kursbaserat lärande"""
    if not st.session_state.selected_course:
        st.markdown("#### Välj en kurs")
        
        # Hämta alla kurser från grafen
        courses = get_all_courses()
        if not courses:
            st.warning("Inga kurser hittades i grafen.")
            return
        
        course_names = [f"{c['namn']} - {c['kurskod']}" for c in courses]
        selected_idx = st.selectbox(
            "Välj kurs att studera:",
            range(len(course_names)),
            format_func=lambda x: course_names[x]
        )
        
        if st.button("Välj denna kurs", type="primary"):
            st.session_state.selected_course = courses[selected_idx]['kurskod']
            st.rerun()
        return
    
    # Visa vald kurs med namn
    course_info = get_course_info(st.session_state.selected_course)
    if course_info:
        st.markdown(f"#### Studerar kurs: {course_info['namn']} - {course_info['kurskod']}")
    else:
        st.markdown(f"#### Studerar kurs: {st.session_state.selected_course}")
    
    # Visa kursgraf med förutsättningar
    st.markdown("##### Kursöversikt med förutsättningar")
    render_course_graph_with_prerequisites(st.session_state.selected_course)
    
    # Visa statistik om kursens koncept
    st.divider()
    st.markdown("##### Kursens koncept")
    render_course_concepts_statistics(st.session_state.selected_course)
    
    st.divider()
    
    # Hitta nästa koncept att lära sig för denna kurs
    if not st.session_state.current_concept:
        # Visa möjlighet att välja koncept manuellt
        st.markdown("##### Välj koncept att studera")
        
        # Hämta alla koncept från kursen
        course_concepts = get_course_concepts_details(st.session_state.selected_course)
        
        if course_concepts:
            # Filtrera ut koncept som inte är behärskade
            learnable_concepts = [c for c in course_concepts if c.get('mastery_score', 0) < 0.7]
            
            if learnable_concepts:
                # Skapa dropdown med AI-val som första alternativ
                concept_options = ["Låt AI välja grundläggande koncept"] + [f"{c['namn']} (Mastery: {c.get('mastery_score', 0):.2f})" for c in learnable_concepts]
                selected_option = st.selectbox(
                    "Välj koncept att studera:",
                    concept_options,
                    index=0,
                    help="AI väljer det mest fundamentala konceptet baserat på förutsättningar och din kunskapsprofil"
                )
                
                if st.button("Börja studera", type="primary"):
                    if selected_option == "Låt AI välja grundläggande koncept":
                        # Automatiskt val av mest fundamentalt koncept
                        with st.spinner(f"AI analyserar kursens koncept för att hitta det mest fundamentala...\nModell: {LITELLM_MODEL}"):
                            course_concepts_all = get_course_concepts_with_prerequisites(st.session_state.selected_course)
                            # Filtrera tillgängliga koncept till bara de som är relevanta för kursen
                            relevant_concepts = [c for c in available_concepts if c['name'] in course_concepts_all]
                            
                            if relevant_concepts:
                                # Låt LLM välja mest fundamentalt koncept
                                recommendation = find_next_concept_for_course(knowledge_profile, relevant_concepts, st.session_state.selected_course)
                                
                                # Lägg till status om konceptet är i kursen eller extern förutsättning
                                concept_in_course = any(c['namn'] == recommendation['recommended_concept'] for c in course_concepts)
                                recommendation['concept_status'] = 'i_kursen' if concept_in_course else 'förutsättning'
                                
                                st.session_state.current_concept = recommendation
                            else:
                                st.warning("Inga koncept att lära sig hittades för denna kurs")
                                return
                    else:
                        # Manuellt valt koncept
                        selected_idx = concept_options.index(selected_option) - 1  # -1 för att kompensera för AI-alternativet
                        selected_concept = learnable_concepts[selected_idx]
                        st.session_state.current_concept = {
                            'recommended_concept': selected_concept['namn'],
                            'reasoning': 'Manuellt valt koncept från kursen',
                            'prerequisites_met': selected_concept.get('prerequisites', []),
                            'prerequisites_missing': [],
                            'difficulty_level': 'medium',
                            'will_unlock': selected_concept.get('unlocks', []),
                            'concept_status': 'i_kursen'
                        }
                    st.rerun()
            else:
                st.info("Alla koncept i kursen är redan behärskade!")
        else:
            st.warning("Inga koncept hittades för kursen")
    
    # Visa koncept-specifik graf om ett koncept är valt
    if st.session_state.current_concept and st.session_state.current_concept.get('recommended_concept'):
        with st.expander("Visa konceptgraf", expanded=False):
            render_concept_graph(st.session_state.current_concept['recommended_concept'])
    
    render_concept_learning_ui(st.session_state.current_concept, knowledge_profile, course_code=st.session_state.selected_course)


def render_specific_concept_learning(knowledge_profile: Dict, available_concepts: List[Dict]):
    """Renderar lärande av specifikt koncept"""
    if not st.session_state.current_concept:
        st.markdown("#### Välj ett koncept")
        
        concept_names = sorted([c['name'] for c in available_concepts])
        selected_concept = st.selectbox(
            "Välj koncept att studera:",
            concept_names
        )
        
        # Visa information om valt koncept
        for c in available_concepts:
            if c['name'] == selected_concept:
                st.info(f"**Beskrivning:** {c.get('description', 'Ingen beskrivning')}")
                if c.get('prerequisites'):
                    st.warning(f"**Förutsättningar:** {', '.join(c['prerequisites'])}")
                break
        
        if st.button("Välj detta koncept", type="primary"):
            # Hitta konceptet i listan
            for c in available_concepts:
                if c['name'] == selected_concept:
                    st.session_state.current_concept = {
                        'recommended_concept': selected_concept,
                        'reasoning': 'Manuellt valt koncept',
                        'prerequisites_met': c.get('prerequisites', []),
                        'prerequisites_missing': [],
                        'difficulty_level': 'medium',
                        'will_unlock': c.get('unlocks', [])
                    }
                    break
            st.rerun()
        return
    
    render_concept_learning_ui(st.session_state.current_concept, knowledge_profile)


def render_concept_learning_ui(recommendation: Dict, knowledge_profile: Dict, course_code: str = None):
    """Renderar UI för att lära sig ett koncept"""
    if not recommendation or not recommendation.get('recommended_concept'):
        # Om vi har en kurs, filtrera koncept för bara den kursen
        if course_code:
            # Hämta koncept för kursen
            course_concepts_all = get_course_concepts_with_prerequisites(course_code)
            low_mastery_concepts = [name for name in course_concepts_all 
                                    if knowledge_profile.get(name, {}).get('mastery_score', 0) < 0.7]
            if low_mastery_concepts:
                st.warning(f"Du har {len(low_mastery_concepts)} koncept i denna kurs med mastery score under 0.7 som du kan fortsätta studera.")
                st.info("Välj ett specifikt koncept från listan ovan.")
            else:
                st.success("Utmärkt! Du har hög mastery score på alla koncept i denna kurs.")
        else:
            # Originalbeteende för icke-kursbaserat lärande
            low_mastery_concepts = [name for name, info in knowledge_profile.items() if info.get('mastery_score', 0) < 0.7]
            if low_mastery_concepts:
                st.warning(f"Du har {len(low_mastery_concepts)} koncept med mastery score under 0.7 som du kan fortsätta studera.")
                st.info("Försök välja ett specifikt koncept från listan eller byt studieväg.")
            else:
                st.success("Utmärkt! Du har hög mastery score på alla tillgängliga koncept.")
        return
    
    # Visa rekommendation
    st.markdown("#### Nästa koncept att lära sig")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(recommendation['recommended_concept'])
        
        # Visa om konceptet är i kursen eller en förutsättning
        if recommendation.get('concept_status') == 'i_kursen':
            st.success("✓ Detta koncept ingår i kursen")
        elif recommendation.get('concept_status') == 'förutsättning':
            st.warning("⚠️ Detta är en extern förutsättning för kursen")
        
        st.caption(recommendation['reasoning'])
        
        # Hämta detaljerad info om konceptet
        detailed_info = get_concept_details(recommendation['recommended_concept'])
        
        # Visa varför konceptet är viktigt
        st.markdown("**Varför lära sig detta?**")
        # Använd AI för att generera bättre förklaring
        importance_reason = get_ai_importance_reason(
            recommendation['recommended_concept'], 
            detailed_info.get('dependent_concepts', []),
            detailed_info.get('courses', [])
        )
        st.info(importance_reason)
        
        # Visa vilka kurser konceptet ingår i
        if detailed_info.get('courses'):
            st.markdown(f"**Konceptet ingår i följande kurser:** {', '.join(detailed_info['courses'])}")
        
        if detailed_info.get('dependent_concepts'):
            with st.expander(f"Koncept som bygger på detta ({len(detailed_info['dependent_concepts'])})"):
                for dep in detailed_info['dependent_concepts'][:10]:
                    st.write(f"• {dep}")
                if len(detailed_info['dependent_concepts']) > 10:
                    st.write(f"... och {len(detailed_info['dependent_concepts']) - 10} till")
        
        # Visa förutsättningar med mastery scores
        if detailed_info.get('prerequisites'):
            st.markdown("**Förutsättningar:**")
            prerequisites_with_mastery = get_prerequisites_with_mastery(detailed_info['prerequisites'])
            
            # Separera uppfyllda och ej uppfyllda förutsättningar
            fulfilled = []
            missing = []
            
            for prereq_name, mastery_score in prerequisites_with_mastery:
                if mastery_score >= 0.6:
                    fulfilled.append(f"{prereq_name} (Mastery: {mastery_score:.2f})")
                else:
                    missing.append(f"{prereq_name} (Mastery: {mastery_score:.2f})")
            
            if fulfilled:
                st.success(f"✓ Uppfyllda förutsättningar: {', '.join(fulfilled)}")
            
            if missing:
                st.warning(f"⚠️ Saknade/låga förutsättningar: {', '.join(missing)}")
                
                # Rekommendera att studera förutsättningar först
                if st.button("Studera förutsättningar först", key="study_prerequisites"):
                    # Hitta första saknade förutsättning
                    first_missing = missing[0].split(" (")[0]  # Ta bort mastery-delen
                    st.session_state.current_concept = {
                        'recommended_concept': first_missing,
                        'reasoning': f'Förutsättning för {recommendation["recommended_concept"]}',
                        'prerequisites_met': [],
                        'prerequisites_missing': [],
                        'difficulty_level': 'medium',
                        'will_unlock': [recommendation['recommended_concept']],
                        'concept_status': 'förutsättning'
                    }
                    st.rerun()
        
        # Visa svårighetsgrad
        difficulty_text = {'lätt': 'Lätt', 'medium': 'Medium', 'svår': 'Svår'}
        difficulty = recommendation.get('difficulty_level', 'medium')
        st.info(f"Svårighetsgrad: {difficulty_text.get(difficulty, 'Medium')}")
    
    with col2:
        # Visa nuvarande mastery score
        current_mastery = knowledge_profile.get(recommendation['recommended_concept'], {}).get('mastery_score', 0.0)
        color = '#FF6B6B' if current_mastery < 0.3 else '#95E1D3' if current_mastery >= 0.7 else '#4ECDC4'
        st.markdown(f"<h2 style='color: {color}; text-align: center;'>Mastery<br>{current_mastery:.2f}</h2>", unsafe_allow_html=True)
    
    # Välj lärstil om inte redan vald
    if not st.session_state.learning_mode:
        st.divider()
        st.markdown("#### Välj din lärstil")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("##### Sokratisk dialog")
            st.info("""
            AI guidar dig genom frågor som leder till djupare förståelse.
            Du svarar på frågor och bygger gradvis upp din kunskap.
            
            **Bäst för:** Djupinlärning och kritiskt tänkande
            """)
            if st.button("Välj sokratisk dialog", key="choose_socratic", type="primary", use_container_width=True):
                st.session_state.learning_mode = "socratic"
                st.session_state.conversation_history = []
                st.rerun()
        
        with col2:
            st.markdown("##### Guidat lärande")
            st.info("""
            AI förklarar konceptet direkt med exempel och analogier.
            Du får en strukturerad genomgång följt av kontrollfrågor.
            
            **Bäst för:** Snabb överblick och praktisk tillämpning
            """)
            if st.button("Välj guidat lärande", key="choose_guided", type="primary", use_container_width=True):
                st.session_state.learning_mode = "guided"
                st.rerun()
        
        with col3:
            st.markdown("##### Direkt bedömning")
            st.info("""
            AI ställer riktade frågor för att snabbt bedöma din kunskap.
            Du får direkta frågor om konceptet utan förklaringar först.
            
            **Bäst för:** Snabb kunskapskontroll och bedömning
            """)
            if st.button("Välj direkt bedömning", key="choose_assessment", type="primary", use_container_width=True):
                st.session_state.learning_mode = "assessment"
                st.rerun()
    
    # Visa vald lärstil
    else:
        # Knapp för att byta koncept eller lärstil
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("Välj annat koncept", key="change_concept"):
                st.session_state.current_concept = None
                st.session_state.learning_mode = None
                st.session_state.conversation_history = []
                st.session_state.understanding_progress = 0.0
                st.rerun()
        with col2:
            # Dropdown för att byta lärstil
            current_mode_names = {
                "socratic": "Sokratisk dialog",
                "guided": "Guidat lärande",
                "assessment": "Direkt bedömning"
            }
            current_mode = current_mode_names.get(st.session_state.learning_mode, "Välj lärstil")
            
            new_mode = st.selectbox(
                "Byt lärstil:",
                ["Sokratisk dialog", "Guidat lärande", "Direkt bedömning"],
                index=["Sokratisk dialog", "Guidat lärande", "Direkt bedömning"].index(current_mode) if current_mode != "Välj lärstil" else 0,
                key="mode_selector"
            )
            
            mode_map = {
                "Sokratisk dialog": "socratic",
                "Guidat lärande": "guided",
                "Direkt bedömning": "assessment"
            }
            
            if mode_map[new_mode] != st.session_state.learning_mode:
                st.session_state.learning_mode = mode_map[new_mode]
                st.session_state.conversation_history = []
                st.session_state.understanding_progress = 0.0
                st.session_state.assessment_questions_answered = 0
                st.session_state.assessment_score = 0
                st.rerun()
        
        with col3:
            # Manuell mastery score
            with st.expander("Sätt mastery manuellt"):
                manual_score = st.slider(
                    "Mastery score:",
                    min_value=0.0,
                    max_value=1.0,
                    value=current_mastery,
                    step=0.1,
                    key="manual_mastery"
                )
                if st.button("Uppdatera", key="update_manual_mastery"):
                    old_score, new_score = update_mastery_score(
                        recommendation['recommended_concept'], 
                        manual_score,
                        learning_rate=1.0  # 100% av nya värdet vid manuell inställning
                    )
                    # Alltid uppdatera sidan för att visa den nya poängen i grafen
                    time.sleep(0.5)  # Kort fördröjning för att visa bekräftelsen
                    st.rerun()
        
        st.divider()
        
        # Hämta konceptinformation
        concept_info = get_concept_details(recommendation['recommended_concept'])
        
        if st.session_state.learning_mode == "socratic":
            render_socratic_learning(recommendation['recommended_concept'], concept_info)
        elif st.session_state.learning_mode == "guided":
            render_guided_learning(recommendation['recommended_concept'], concept_info)
        elif st.session_state.learning_mode == "assessment":
            render_assessment_learning(recommendation['recommended_concept'], concept_info)
    
    # Visa progression
    st.divider()
    render_concept_progression(knowledge_profile)


def get_all_courses() -> List[Dict]:
    """Hämtar alla kurser från grafen"""
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (k:Kurs)
            RETURN k.kurskod as kurskod, k.namn as namn
            ORDER BY k.kurskod
        """)
        return [dict(record) for record in result]


def get_course_info(course_code: str) -> Dict:
    """Hämtar information om en specifik kurs"""
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (k:Kurs {kurskod: $kurskod})
            RETURN k.kurskod as kurskod, k.namn as namn
        """, kurskod=course_code)
        record = result.single()
        return dict(record) if record else None


def get_course_concepts_details(course_code: str) -> List[Dict]:
    """Hämtar detaljerad information om koncept i en kurs"""
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
            RETURN c.namn as namn,
                   c.beskrivning as beskrivning,
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   collect(DISTINCT prereq.namn) as prerequisites,
                   collect(DISTINCT dependent.namn) as unlocks
            ORDER BY c.namn
        """, kurskod=course_code)
        return [dict(record) for record in result]


def find_next_concept_for_course(knowledge_profile: Dict, available_concepts: List[Dict], course_code: str) -> Dict:
    """Hittar mest fundamentalt koncept för en kurs"""
    try:
        # Filtrera bort redan behärskade koncept
        learnable_concepts = [
            c for c in available_concepts 
            if c.get('mastery_score', 0) < 0.7
        ]
        
        if not learnable_concepts:
            return {}
        
        # Använd LLM för att hitta mest fundamentalt koncept för kursen
        llm_service = st.session_state.graph_builder.llm
        
        # Skapa kontext specifikt för kursen
        course_context = f"Hitta det mest fundamentala konceptet för kursen {course_code}. Prioritera koncept som många andra koncept bygger på."
        
        recommendation = llm_service.find_next_concept(
            knowledge_profile, 
            learnable_concepts,
            additional_context=course_context
        )
        
        return recommendation
        
    except Exception as e:
        st.error(f"Fel vid sökning efter nästa koncept: {str(e)}")
        # Fallback: välj koncept med flest beroende koncept
        best_concept = None
        max_unlocks = 0
        
        for concept in learnable_concepts:
            num_unlocks = len(concept.get('unlocks', []))
            if num_unlocks > max_unlocks:
                max_unlocks = num_unlocks
                best_concept = concept
        
        if best_concept:
            return {
                'recommended_concept': best_concept['name'],
                'reasoning': f'Fundamentalt koncept som {max_unlocks} andra koncept bygger på',
                'prerequisites_met': best_concept.get('prerequisites', []),
                'prerequisites_missing': [],
                'difficulty_level': 'medium',
                'will_unlock': best_concept.get('unlocks', [])
            }
        return {}


def render_concept_graph(concept_name: str, current_course: str = None, in_expander: bool = False):
    """Renderar en graf för ett specifikt koncept och dess relationer"""
    import streamlit.components.v1 as components
    
    # Skapa unik key baserat på konceptnamn och kontext
    unique_key = f"concept_graph_mastery_{concept_name.replace(' ', '_')}{'_expander' if in_expander else ''}"
    
    # Visa checkbox för mastery-visualisering
    use_mastery = st.checkbox(
        "Visa mastery-baserad visualisering för konceptgraf", 
        value=True,
        key=unique_key,
        help="Koncept med låg mastery blir mer transparenta, de med hög mastery får tydligare färger"
    )
    
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta konceptet och dess relationer
        result = session.run("""
            MATCH (c:Koncept {namn: $namn})
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (prereq)<-[:INNEHÅLLER]-(prereq_course:Kurs)
            OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
            OPTIONAL MATCH (dependent)<-[:INNEHÅLLER]-(dep_course:Kurs)
            OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
            WITH c, 
                 collect(DISTINCT {koncept: prereq, kurs: prereq_course}) as prerequisites_with_courses,
                 collect(DISTINCT {koncept: dependent, kurs: dep_course}) as dependents_with_courses,
                 collect(DISTINCT k) as courses
            RETURN c, prerequisites_with_courses, dependents_with_courses, courses
        """, namn=concept_name)
        
        record = result.single()
        if not record:
            st.warning("Ingen data hittades för konceptet")
            return
        
        # Om vi studerar från en kurs, hämta kursens koncept
        course_concepts = []
        if current_course:
            course_result = session.run("""
                MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                RETURN collect(c.namn) as concepts
            """, kurskod=current_course)
            course_record = course_result.single()
            if course_record:
                course_concepts = course_record['concepts']
        
        # Skapa graf med samma inställningar som huvudgrafen
        net = Network(height="400px", width="100%", bgcolor="#ffffff", font_color="#1d1d1f")
        
        # Använd hierarchical layout för att centrera konceptet
        net.set_options(json.dumps({
            "physics": {
                "enabled": False
            },
            "layout": {
                "hierarchical": {
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "shakeTowards": "roots",
                    "nodeSpacing": 200,
                    "treeSpacing": 200,
                    "levelSeparation": 150
                }
            },
            "nodes": {
                "font": {"size": 14},
                "borderWidth": 2,
                "shadow": True
            },
            "edges": {
                "width": 2,
                "shadow": True,
                "smooth": {
                    "type": "continuous",
                    "roundness": 0.5
                }
            },
            "interaction": {
                "hover": True,
                "multiselect": True,
                "navigationButtons": True,
                "keyboard": True
            }
        }))
        
        # Lägg till huvudkonceptet i centrum
        concept = record['c']
        mastery_score = concept.get('mastery_score', 0.0)
        is_in_current_course = concept['namn'] in course_concepts if current_course else False
        concept_label = concept['namn'] + f"\nMastery: {mastery_score:.2f}"
        if current_course:
            concept_label += "\n(I kursen)" if is_in_current_course else "\n(Extern förutsättning)"
        
        # Färg och transparens baserat på mastery om aktiverat
        if use_mastery:
            opacity = 0.3 + (mastery_score * 0.7)
            if mastery_score < 0.3:
                base_color = '#FF6B6B'
            elif mastery_score < 0.7:
                base_color = '#FFE66D'
            else:
                base_color = '#95E1D3'
            hex_color = base_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
            size = 25 + (mastery_score * 15)
        else:
            color = '#4ECDC4'
            size = 30
        
        net.add_node(
            concept['namn'],
            label=concept_label,
            color=color,
            size=size,
            title=f"{concept.get('beskrivning', concept['namn'])}\nMastery: {mastery_score:.2f}",
            shape='dot',
            x=0,
            y=0,
            physics=False
        )
        
        # Lägg till förutsättningar
        for prereq_info in record['prerequisites_with_courses']:
            prereq = prereq_info['koncept']
            prereq_course = prereq_info['kurs']
            if not prereq:
                continue
            prereq_mastery = prereq.get('mastery_score', 0.0)
            is_in_course = prereq['namn'] in course_concepts if current_course else False
            label = f"{prereq['namn']}\nMastery: {prereq_mastery:.2f}"
            if current_course:
                if is_in_course:
                    label += "\n(I kursen)"
                elif prereq_course:
                    label += f"\n{prereq_course['kurskod']}: {prereq_course.get('namn', '')}"
                else:
                    label += "\n(Extern)"
            else:
                # När vi inte studerar från en specifik kurs, visa alltid kursen
                if prereq_course:
                    label += f"\n{prereq_course['kurskod']}: {prereq_course.get('namn', '')}"
            
            # Färg baserat på mastery om aktiverat
            if use_mastery:
                opacity = 0.3 + (prereq_mastery * 0.7)
                if prereq_mastery < 0.3:
                    base_color = '#FF6B6B'
                elif prereq_mastery < 0.7:
                    base_color = '#FFE66D'
                else:
                    base_color = '#95E1D3'
                hex_color = base_color.lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
                size = 15 + (prereq_mastery * 10)
            else:
                color = '#FFE66D'
                size = 20
            
            net.add_node(
                prereq['namn'],
                label=label,
                color=color,
                size=size,
                title=f"Förutsättning: {prereq.get('beskrivning', prereq['namn'])}\nMastery: {prereq_mastery:.2f}",
                shape='dot'
            )
            net.add_edge(
                concept['namn'],
                prereq['namn'],
                color='#FFE66D',
                arrows='to'
            )
        
        # Lägg till beroende koncept
        for dep_info in record['dependents_with_courses']:
            dependent = dep_info['koncept']
            dep_course = dep_info['kurs']
            if not dependent:
                continue
            dep_mastery = dependent.get('mastery_score', 0.0)
            is_in_course = dependent['namn'] in course_concepts if current_course else False
            label = f"{dependent['namn']}\nMastery: {dep_mastery:.2f}"
            if current_course:
                if is_in_course:
                    label += "\n(I kursen)"
                elif dep_course:
                    label += f"\n{dep_course['kurskod']}: {dep_course.get('namn', '')}"
                else:
                    label += "\n(Ej kopplad till kurs)"
            else:
                # När vi inte studerar från en specifik kurs, visa alltid kursen
                if dep_course:
                    label += f"\n{dep_course['kurskod']}: {dep_course.get('namn', '')}"
            
            # Färg baserat på mastery om aktiverat
            if use_mastery:
                opacity = 0.3 + (dep_mastery * 0.7)
                if dep_mastery < 0.3:
                    base_color = '#FF6B6B'
                elif dep_mastery < 0.7:
                    base_color = '#FFE66D'
                else:
                    base_color = '#95E1D3'
                hex_color = base_color.lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
                size = 15 + (dep_mastery * 10)
            else:
                color = '#95E1D3'
                size = 20
            
            net.add_node(
                dependent['namn'],
                label=label,
                color=color,
                size=size,
                title=f"Bygger på detta: {dependent.get('beskrivning', dependent['namn'])}\nMastery: {dep_mastery:.2f}",
                shape='dot'
            )
            net.add_edge(
                dependent['namn'],
                concept['namn'],
                color='#95E1D3',
                arrows='to'
            )
        
        # Lägg till kurser som innehåller konceptet
        for course in record['courses']:
            is_current = course['kurskod'] == current_course if current_course else False
            color = '#808080' if is_current else '#A9A9A9'
            
            net.add_node(
                course['kurskod'],
                label=f"{course['kurskod']}\n{course['namn']}",
                color=color,
                size=25 if is_current else 20,
                title=course['namn'] + (" (Nuvarande kurs)" if is_current else ""),
                shape='dot'
            )
            net.add_edge(
                course['kurskod'],
                concept['namn'],
                color='#A8E6CF',
                arrows='to'
            )
        
        # Visa grafen
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
            net.write_html(tmp.name, notebook=False)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html = f.read()
            os.unlink(tmp.name)
        
        components.html(html, height=450)
        
        # Förklaring
        if use_mastery:
            caption = "**Mastery-visualisering aktiverad:**\n"
            caption += "- Transparens visar mastery-nivå (låg mastery = mer transparent)\n"
            caption += "- Färger: Röd = Låg mastery (<0.3) | Gul = Medium mastery (0.3-0.7) | Grön = Hög mastery (>0.7)\n"
            caption += "- Kurser = Röda noder\n"
        else:
            caption = "**Färgkoder:** Turkos = Aktuellt koncept | Gul = Förutsättningar | Grön = Beroende koncept | Röd = Kurser\n"
        
        if current_course:
            caption += "**Status:** (I kursen) = Ingår i nuvarande kurs | (Extern) = Extern förutsättning | (Kurskod) = Ingår i angiven kurs"
        st.caption(caption)


def render_assessment_learning(concept_name: str, concept_info: Dict):
    """Renderar direkt bedömning av kunskap"""
    st.markdown(f"#### Direkt bedömning: {concept_name}")
    
    # Inställningar för AI-kontext
    col1, col2 = st.columns([3, 1])
    with col1:
        include_full_graph = st.checkbox(
            "Inkludera hela kunskapsgrafen i AI-kontext",
            value=True,  # Gör detta till standardval
            key="assessment_include_graph",
            help="Om aktiverad skickas hela din kunskapsgraf till AI för mer personaliserade frågor"
        )
    with col2:
        with st.popover("Information"):
            st.markdown("""
            **Vad skickas till AI:**
            
            **Standard (utan kunskapsgraf):**
            - Aktuellt koncept och beskrivning
            - Frågenummer och svårighetsgrad
            
            **Med kunskapsgraf:**
            - Allt ovan PLUS
            - Alla dina koncept med mastery scores
            - Relationer mellan alla koncept
            - AI kan ställa frågor som relaterar till andra koncept du studerat
            """)
    
    # Initiera bedömningsvariabler
    if 'assessment_questions_answered' not in st.session_state:
        st.session_state.assessment_questions_answered = 0
    if 'assessment_score' not in st.session_state:
        st.session_state.assessment_score = 0
    if 'assessment_questions' not in st.session_state or st.session_state.get('assessment_concept') != concept_name:
        # Generera alla 3 frågor på en gång
        with st.spinner(f"AI förbereder bedömningsfrågor...\nModell: {LITELLM_MODEL}"):
            llm_service = st.session_state.graph_builder.llm
            
            # Lägg till kunskapsgraf om valt
            additional_context = None
            if include_full_graph:
                knowledge_graph = get_full_knowledge_graph()
                additional_context = f"Studentens fullständiga kunskapsgraf:\n{knowledge_graph}"
            
            questions = []
            for i in range(3):
                # Variera svårighetsgrad för varje fråga
                mastery_level = i * 0.3  # 0.0, 0.3, 0.6 för ökande svårighet
                question = llm_service.get_assessment_questions(
                    concept_name=concept_name,
                    concept_description=concept_info.get('beskrivning', ''),
                    question_number=i+1,
                    difficulty_level=mastery_level,
                    additional_context=additional_context
                )
                questions.append(question)
            st.session_state.assessment_questions = questions
            st.session_state.assessment_concept = concept_name
    
    # Visa progress
    progress = st.session_state.assessment_questions_answered / 3
    st.progress(progress, text=f"Fråga {st.session_state.assessment_questions_answered + 1} av 3")
    
    # Om bedömningen är klar
    if st.session_state.assessment_questions_answered >= 3:
        avg_score = st.session_state.assessment_score / 3
        color = '#FF6B6B' if avg_score < 0.3 else '#95E1D3' if avg_score >= 0.7 else '#4ECDC4'
        
        st.markdown(f"<h3 style='color: {color};'>Bedömning klar!</h3>", unsafe_allow_html=True)
        st.markdown(f"Din genomsnittliga förståelse: **{int(avg_score * 100)}%**")
        
        # Uppdatera mastery score med lämplig learning rate
        learning_rate = 0.15  # Lägre learning rate för gradvis förbättring
        old_score, new_score = update_mastery_score(
            concept_name,
            avg_score,
            learning_rate=learning_rate
        )
        
        if avg_score >= 0.7:
            st.success("Utmärkt! Du har god förståelse för detta koncept.")
        elif avg_score >= 0.5:
            st.warning("Bra jobbat! Du har grundläggande förståelse men kan förbättra dig.")
        else:
            st.info("Du behöver studera mer om detta koncept.")
        
        # Visa valmöjligheter
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Fortsätt studera detta koncept", type="primary", use_container_width=True):
                st.session_state.assessment_questions_answered = 0
                st.session_state.assessment_score = 0
                st.session_state.assessment_questions = None
                st.rerun()
        
        with col2:
            if st.button("Byt till Sokratisk dialog", use_container_width=True):
                st.session_state.assessment_questions_answered = 0
                st.session_state.assessment_score = 0
                st.session_state.assessment_questions = None
                st.session_state.learning_mode = "socratic"
                st.rerun()
        
        with col3:
            if avg_score >= 0.7 and st.button("Gå vidare till nästa koncept", type="secondary", use_container_width=True):
                st.session_state.assessment_questions_answered = 0
                st.session_state.assessment_score = 0
                st.session_state.assessment_questions = None
                st.session_state.current_concept = None
                st.session_state.learning_mode = None
                st.rerun()
        return
    
    # Visa aktuell fråga
    current_question = st.session_state.assessment_questions[st.session_state.assessment_questions_answered]
    
    st.markdown("**Fråga:**")
    st.info(current_question)
    
    # Svarsruta
    answer = st.text_area(
        "Ditt svar:",
        height=150,
        placeholder="Skriv ditt svar här...",
        key=f"assessment_answer_{st.session_state.assessment_questions_answered}"
    )
    
    if st.button("Skicka svar", type="primary"):
        if answer:
            with st.spinner(f"AI utvärderar ditt svar...\nModell: {LITELLM_MODEL}"):
                try:
                    llm_service = st.session_state.graph_builder.llm
                    evaluation = llm_service.evaluate_understanding(
                        concept_name=concept_name,
                        student_answer=answer
                    )
                    
                    # Kontrollera att vi fick ett giltigt svar
                    if isinstance(evaluation, dict) and 'understanding_score' in evaluation:
                        score = evaluation.get('understanding_score', 0.5)
                        st.session_state.assessment_score += score
                        st.session_state.assessment_questions_answered += 1
                        
                        # Visa feedback
                        st.divider()
                        color = '#FF6B6B' if score < 0.3 else '#95E1D3' if score >= 0.7 else '#4ECDC4'
                        st.markdown(f"<h4 style='color: {color};'>Poäng för denna fråga: {int(score * 100)}%</h4>", unsafe_allow_html=True)
                        st.markdown(evaluation.get('feedback', ''))
                        
                        # Vänta kort och uppdatera
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Kunde inte utvärdera svaret. Försök igen.")
                        
                except Exception as e:
                    st.error(f"Ett fel uppstod vid utvärdering: {str(e)}")
                    st.info("Försök igen eller byt till en annan lärstil.")
        else:
            st.warning("Vänligen skriv ett svar innan du skickar.")


def get_course_concepts_with_prerequisites(course_code: str) -> List[str]:
    """Hämtar alla koncept för en kurs inklusive nödvändiga förutsättningar"""
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta alla koncept direkt från kursen
        result = session.run("""
            MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
            WITH collect(c.namn) as direct_concepts
            
            // Hämta alla förutsättningar rekursivt
            MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
            OPTIONAL MATCH path = (c)-[:FÖRUTSÄTTER*]->(prereq:Koncept)
            WITH direct_concepts, collect(DISTINCT prereq.namn) as prerequisites
            
            RETURN direct_concepts + prerequisites as all_concepts
        """, kurskod=course_code)
        
        record = result.single()
        return record['all_concepts'] if record else []


def get_ai_importance_reason(concept_name: str, dependent_concepts: List[str], courses: List[str]) -> str:
    """Använder AI för att generera en bra förklaring till varför konceptet är viktigt att lära sig"""
    try:
        # Bygg kontext för AI
        context = f"Koncept: {concept_name}\n"
        
        if dependent_concepts:
            context += f"\nKoncept som bygger på detta: {', '.join(dependent_concepts[:5])}"
            if len(dependent_concepts) > 5:
                context += f" och {len(dependent_concepts) - 5} till"
        
        if courses:
            context += f"\nKonceptet används i kurserna: {', '.join(courses)}"
        
        prompt = f"""Analysera följande koncept och förklara kortfattat (max 3 meningar) varför det är viktigt att lära sig:

{context}

Fokusera på:
1. Praktisk användning och relevans
2. Hur det möjliggör förståelse av andra koncept
3. Dess roll i de kurser där det ingår

Svara på svenska och var konkret."""

        from litellm import completion
        llm_service = st.session_state.graph_builder.llm
        response = completion(
            model=llm_service.model,
            messages=[
                {"role": "system", "content": "Du är en pedagogisk expert som förklarar varför koncept är viktiga att lära sig."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            api_key=llm_service.api_key,
            base_url=llm_service.base_url
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        # Fallback till enkel förklaring
        if len(dependent_concepts) > 5:
            return f"Detta är ett centralt koncept som {len(dependent_concepts)} andra koncept bygger på. Att behärska det är avgörande för vidare studier."
        elif len(dependent_concepts) > 2:
            return f"Viktigt koncept som {len(dependent_concepts)} andra koncept förutsätter. Fundamental byggsten för fördjupning inom området."
        elif len(dependent_concepts) > 0:
            return f"Grundläggande koncept som behövs för {len(dependent_concepts)} andra koncept."
        else:
            return "Specialiserat koncept för fördjupning inom området."


def get_prerequisites_with_mastery(prerequisite_names: List[str]) -> List[Tuple[str, float]]:
    """Hämtar mastery scores för en lista av förutsättningar"""
    prerequisites_with_mastery = []
    
    with st.session_state.neo4j_service.driver.session() as session:
        for prereq_name in prerequisite_names:
            result = session.run("""
                MATCH (c:Koncept {namn: $namn})
                RETURN COALESCE(c.mastery_score, 0.0) as mastery_score
            """, namn=prereq_name)
            
            record = result.single()
            if record:
                prerequisites_with_mastery.append((prereq_name, record['mastery_score']))
            else:
                prerequisites_with_mastery.append((prereq_name, 0.0))
    
    return prerequisites_with_mastery


def render_course_concepts_statistics(course_code: str):
    """Visar statistik om kursens koncept"""
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta alla koncept från kursen med statistik
        result = session.run("""
            MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
            OPTIONAL MATCH (dependent)<-[:INNEHÅLLER]-(dep_course:Kurs)
            OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(other_course:Kurs)
            WHERE other_course.kurskod <> $kurskod
            WITH c, 
                 collect(DISTINCT prereq.namn) as prerequisites,
                 collect(DISTINCT {koncept: dependent.namn, kurskod: dep_course.kurskod, kursnamn: dep_course.namn}) as dependent_info,
                 collect(DISTINCT other_course.kurskod) as other_courses
            RETURN c.namn as namn,
                   c.beskrivning as beskrivning,
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   size(prerequisites) as num_prerequisites,
                   size([d IN dependent_info WHERE d.koncept IS NOT NULL]) as num_dependents,
                   prerequisites,
                   dependent_info,
                   other_courses
            ORDER BY size([d IN dependent_info WHERE d.koncept IS NOT NULL]) DESC, c.namn
        """, kurskod=course_code)
        
        concepts = list(result)
        
        if concepts:
            # Visa översikt
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Antal koncept", len(concepts))
            with col2:
                mastered = sum(1 for c in concepts if c['mastery_score'] >= 0.7)
                st.metric("Behärskade", f"{mastered}/{len(concepts)}")
            with col3:
                avg_mastery = sum(c['mastery_score'] for c in concepts) / len(concepts)
                st.metric("Genomsnittlig mastery", f"{avg_mastery:.2f}")
            
            # Visa koncept i expanders
            for concept in concepts:
                # Färgkod baserat på mastery
                if concept['mastery_score'] < 0.3:
                    color = "🔴"
                elif concept['mastery_score'] < 0.7:
                    color = "🟡"
                else:
                    color = "🟢"
                
                with st.expander(f"{color} {concept['namn']} (Mastery: {concept['mastery_score']:.2f})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Beskrivning:** {concept['beskrivning']}")
                        
                        # Visa statistik
                        st.markdown(f"**Antal koncept som bygger på detta:** {concept['num_dependents']}")
                        if concept['dependent_info']:
                            # Filtrera bort null-värden och gruppera
                            valid_deps = [d for d in concept['dependent_info'] if d['koncept']]
                            
                            if valid_deps:
                                st.markdown("**Möjliggör:**")
                                
                                # Visa första 5 beroende koncept med kursinfo
                                for i, dep in enumerate(valid_deps[:5]):
                                    if dep['kurskod'] == course_code:
                                        st.markdown(f"  - {dep['koncept']} (i denna kurs)")
                                    elif dep['kurskod']:
                                        st.markdown(f"  - {dep['koncept']} (i {dep['kurskod']} - {dep['kursnamn']})")
                                    else:
                                        st.markdown(f"  - {dep['koncept']} (ej kopplad till kurs)")
                                
                                # Visa "och X till" med möjlighet att expandera
                                if len(valid_deps) > 5:
                                    if st.button(f"Visa alla {len(valid_deps) - 5} till...", key=f"show_all_deps_{concept['namn']}"):
                                        for dep in valid_deps[5:]:
                                            if dep['kurskod'] == course_code:
                                                st.markdown(f"  - {dep['koncept']} (i denna kurs)")
                                            elif dep['kurskod']:
                                                st.markdown(f"  - {dep['koncept']} (i {dep['kurskod']} - {dep['kursnamn']})")
                                            else:
                                                st.markdown(f"  - {dep['koncept']} (ej kopplad till kurs)")
                        
                        st.markdown(f"**Antal förutsättningar:** {concept['num_prerequisites']}")
                        if concept['prerequisites']:
                            st.markdown("**Förutsätter:**")
                            for prereq in concept['prerequisites']:
                                st.markdown(f"  - {prereq}")
                        
                        if concept['other_courses']:
                            st.markdown(f"**Används även i:** {', '.join(concept['other_courses'])}")
                    
                    with col2:
                        if st.button("Studera detta", key=f"study_{concept['namn']}", type="primary"):
                            # Extrahera bara konceptnamn från dependent_info
                            dependent_names = [d['koncept'] for d in concept['dependent_info'] if d['koncept']]
                            st.session_state.current_concept = {
                                'recommended_concept': concept['namn'],
                                'reasoning': 'Manuellt valt koncept från kursen',
                                'prerequisites_met': concept['prerequisites'],
                                'prerequisites_missing': [],
                                'difficulty_level': 'medium',
                                'will_unlock': dependent_names,
                                'concept_status': 'i_kursen'
                            }
                            st.rerun()
                    
                    # Visa graf direkt i expandern
                    st.divider()
                    st.markdown("**Konceptgraf:**")
                    render_concept_graph(concept['namn'], st.session_state.selected_course, in_expander=True)
            
            # Ta bort den separata grafvisningen eftersom den nu är integrerad i expandern
        else:
            st.warning("Inga koncept hittades för kursen")


def render_course_graph_with_prerequisites(course_code: str):
    """Renderar graf för en kurs med alla förutsättningar markerade"""
    import streamlit.components.v1 as components
    
    # Visa checkbox för mastery-visualisering
    use_mastery = st.checkbox(
        "Visa mastery-baserad visualisering", 
        value=True,
        help="Koncept med låg mastery blir mer transparenta, de med hög mastery får tydligare färger"
    )
    
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta kursen och dess koncept med mastery scores
        result = session.run("""
            MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
            WITH k, collect(c) as course_concepts
            
            // Hämta alla förutsättningar
            UNWIND course_concepts as cc
            OPTIONAL MATCH path = (cc)-[:FÖRUTSÄTTER*]->(prereq:Koncept)
            WHERE NOT (k)-[:INNEHÅLLER]->(prereq)
            
            WITH k, course_concepts, collect(DISTINCT prereq) as external_prereqs
            
            // Skapa noder och relationer
            RETURN k as course,
                   course_concepts,
                   external_prereqs,
                   [(c1)-[r:FÖRUTSÄTTER]->(c2) WHERE c1 IN course_concepts + external_prereqs 
                    AND c2 IN course_concepts + external_prereqs | 
                    {from: c1.namn, to: c2.namn, from_mastery: c1.mastery_score, to_mastery: c2.mastery_score}] as prerequisites
        """, kurskod=course_code)
        
        record = result.single()
        if not record:
            st.warning("Ingen data hittades för kursen")
            return
        
        # Skapa visualisering med samma inställningar som huvudgrafen
        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#1d1d1f")
        
        # Använd EXAKT samma options som huvudgrafen men med avstängd fysik för att förhindra rotation
        net.set_options(json.dumps({
            "physics": {
                "enabled": False  # Stäng av fysik för att förhindra rotation
            },
            "nodes": {
                "font": {"size": 14},
                "borderWidth": 2,
                "shadow": True
            },
            "edges": {
                "width": 2,
                "shadow": True,
                "smooth": {
                    "type": "continuous",
                    "roundness": 0.5
                }
            },
            "interaction": {
                "hover": True,
                "multiselect": True,
                "navigationButtons": True,
                "keyboard": True
            }
        }))
        
        # Lägg till kursnod
        course = record['course']
        net.add_node(
            course['kurskod'],
            label=f"{course['kurskod']}\n{course['namn']}",
            color='#808080',
            size=35,
            title=course['namn'],
            shape='dot'
        )
        
        # Lägg till koncept från kursen
        for concept in record['course_concepts']:
            mastery_score = concept.get('mastery_score', 0.0)
            
            # Basera färg och transparens på mastery score om visualisering är aktiverad
            if use_mastery:
                # Skala transparens baserat på mastery (0.3 för låg mastery, 1.0 för hög)
                opacity = 0.3 + (mastery_score * 0.7)
                
                # Färgskala från rött (låg mastery) till grönt (hög mastery)
                if mastery_score < 0.3:
                    base_color = '#FF6B6B'  # Rött för låg mastery
                elif mastery_score < 0.7:
                    base_color = '#FFE66D'  # Gult för medium mastery
                else:
                    base_color = '#95E1D3'  # Grönt för hög mastery
                
                # Konvertera hex till rgba med opacity
                hex_color = base_color.lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
                
                # Storlek baserat på mastery
                size = 15 + (mastery_score * 15)  # 15-30 baserat på mastery
            else:
                color = '#95E1D3'
                size = 20
            
            net.add_node(
                concept['namn'],
                label=f"{concept['namn']}\nMastery: {mastery_score:.2f}",
                color=color,
                size=size,
                title=f"{concept.get('beskrivning', concept['namn'])}\nMastery: {mastery_score:.2f}",
                shape='dot'
            )
            # Länka från kurs till koncept
            net.add_edge(
                course['kurskod'], 
                concept['namn'], 
                color='#A8E6CF',
                arrows='to'
            )
        
        # Lägg till externa förutsättningar
        for prereq in record['external_prereqs']:
            mastery_score = prereq.get('mastery_score', 0.0)
            
            if use_mastery:
                opacity = 0.3 + (mastery_score * 0.7)
                if mastery_score < 0.3:
                    base_color = '#FF6B6B'
                elif mastery_score < 0.7:
                    base_color = '#FFE66D'
                else:
                    base_color = '#95E1D3'
                hex_color = base_color.lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
                size = 12 + (mastery_score * 12)
            else:
                color = '#FFE66D'
                size = 15
            
            net.add_node(
                prereq['namn'],
                label=f"{prereq['namn']}\nMastery: {mastery_score:.2f}",
                color=color,
                size=size,
                title=f"Extern förutsättning: {prereq.get('beskrivning', prereq['namn'])}\nMastery: {mastery_score:.2f}",
                shape='dot'
            )
        
        # Lägg till förutsättningsrelationer
        for rel in record['prerequisites']:
            net.add_edge(
                rel['from'], 
                rel['to'],
                color='#FFE66D',
                arrows='to'
            )
        
        # Visa grafen
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
            net.write_html(tmp.name, notebook=False)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html = f.read()
            os.unlink(tmp.name)
        
        components.html(html, height=650)
        
        # Förklaring
        if use_mastery:
            st.caption("""
            **Mastery-visualisering aktiverad:**
            - Transparens visar mastery-nivå (låg mastery = mer transparent)
            - Färger: Röd = Låg mastery (<0.3) | Gul = Medium mastery (0.3-0.7) | Grön = Hög mastery (>0.7)
            - Kursnod = Röd fyrkant
            **Linjer:** Grön = Innehåller | Gul = Förutsätter
            """)
        else:
            st.caption("""
            **Färgkoder:** Röd = Kurs | Grön = Kursens koncept | Gul = Externa förutsättningar
            **Linjer:** Grön = Innehåller | Gul = Förutsätter
            """)


# Kopiera resten av funktionerna från den gamla filen...
def get_knowledge_profile() -> Tuple[Dict, List[Dict]]:
    """Hämtar studentens kunskapsprofil och tillgängliga koncept"""
    knowledge_profile = {}
    available_concepts = []
    
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta alla koncept med deras information
        result = session.run("""
            MATCH (c:Koncept)
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
            OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
            RETURN c.namn as namn,
                   c.beskrivning as beskrivning,
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   collect(DISTINCT prereq.namn) as prerequisites,
                   collect(DISTINCT dependent.namn) as unlocks,
                   collect(DISTINCT k.kurskod) as courses
        """)
        
        for record in result:
            concept_name = record['namn']
            knowledge_profile[concept_name] = {
                'mastery_score': record['mastery_score'],
                'beskrivning': record['beskrivning'],
                'courses': record['courses']
            }
            
            available_concepts.append({
                'name': concept_name,
                'description': record['beskrivning'],
                'prerequisites': record['prerequisites'],
                'unlocks': record['unlocks'],
                'courses': record['courses'],
                'mastery_score': record['mastery_score']
            })
    
    return knowledge_profile, available_concepts


def find_next_concept_to_learn(knowledge_profile: Dict, available_concepts: List[Dict]) -> Dict:
    """Använder LLM för att hitta nästa optimala koncept"""
    try:
        # Filtrera bort redan behärskade koncept
        learnable_concepts = [
            c for c in available_concepts 
            if c.get('mastery_score', 0) < 0.7
        ]
        
        if not learnable_concepts:
            return {}
        
        # Använd LLM för att hitta bästa nästa koncept
        llm_service = st.session_state.graph_builder.llm
        recommendation = llm_service.find_next_concept(knowledge_profile, learnable_concepts)
        
        return recommendation
        
    except Exception as e:
        st.error(f"Fel vid sökning efter nästa koncept: {str(e)}")
        # Fallback: välj första konceptet med uppfyllda förutsättningar
        for concept in available_concepts:
            if concept.get('mastery_score', 0) < 0.7:
                return {
                    'recommended_concept': concept['name'],
                    'reasoning': 'Första tillgängliga konceptet',
                    'prerequisites_met': [],
                    'prerequisites_missing': [],
                    'difficulty_level': 'medium',
                    'will_unlock': []
                }
        return {}


def get_full_knowledge_graph() -> str:
    """Hämtar hela kunskapsgrafen som en JSON-representation"""
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (c:Koncept)
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
            RETURN c.namn as koncept, 
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   c.beskrivning as beskrivning,
                   collect(DISTINCT prereq.namn) as förutsätter,
                   collect(DISTINCT k.kurskod) as kurser
            ORDER BY c.namn
        """)
        
        graph_data = []
        for record in result:
            graph_data.append({
                "koncept": record['koncept'],
                "mastery_score": record['mastery_score'],
                "beskrivning": record['beskrivning'],
                "förutsätter": record['förutsätter'],
                "ingår_i_kurser": record['kurser']
            })
        
        import json
        return json.dumps(graph_data, ensure_ascii=False, indent=2)


def get_concept_details(concept_name: str) -> Dict:
    """Hämtar detaljerad information om ett koncept"""
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (c:Koncept {namn: $namn})
            OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
            OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
            OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
            RETURN c.beskrivning as beskrivning,
                   collect(DISTINCT prereq.namn) as prerequisites,
                   collect(DISTINCT k.kurskod) as courses,
                   collect(DISTINCT dependent.namn) as dependent_concepts,
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   size([(c)<-[:FÖRUTSÄTTER]-(d:Koncept) | d]) as num_dependents
        """, namn=concept_name)
        
        record = result.single()
        if record:
            data = dict(record)
            # Generera importance_reason baserat på antal beroende koncept
            num_deps = data.get('num_dependents', 0)
            if num_deps > 5:
                data['importance_reason'] = f"Detta är ett centralt koncept som {num_deps} andra koncept bygger på"
            elif num_deps > 2:
                data['importance_reason'] = f"Viktigt koncept som {num_deps} andra koncept förutsätter"
            elif num_deps > 0:
                data['importance_reason'] = f"Grundläggande koncept som behövs för {num_deps} andra koncept"
            else:
                data['importance_reason'] = "Specialiserat koncept för fördjupning inom området"
            return data
        return {}


def render_socratic_learning(concept_name: str, concept_info: Dict):
    """Renderar sokratiskt lärande med chat-interface"""
    st.markdown(f"#### Sokratisk dialog: {concept_name}")
    
    # Inställningar för AI-kontext
    col1, col2 = st.columns([3, 1])
    with col1:
        include_full_graph = st.checkbox(
            "Inkludera hela kunskapsgrafen i AI-kontext",
            value=True,  # Gör detta till standardval
            key="socratic_include_graph",
            help="Om aktiverad skickas hela din kunskapsgraf till AI för bättre personalisering"
        )
    with col2:
        with st.popover("Information"):
            st.markdown("""
            **Vad skickas till AI:**
            
            **Standard (utan kunskapsgraf):**
            - Aktuellt koncept och beskrivning
            - Dina förutsättningar för konceptet
            - Din mastery score för konceptet
            - Koncept som bygger på detta
            
            **Med kunskapsgraf:**
            - Allt ovan PLUS
            - Alla dina koncept med mastery scores
            - Relationer mellan alla koncept
            - Kursinformation för koncept
            """)
    
    # Progress bar för förståelse
    progress_col1, progress_col2 = st.columns([3, 1])
    with progress_col1:
        st.progress(st.session_state.understanding_progress, text=f"Förståelse: {int(st.session_state.understanding_progress * 100)}%")
    with progress_col2:
        if st.session_state.understanding_progress >= 0.8:
            if st.button("Avsluta och spara", key="save_progress"):
                old_score, final_score = update_mastery_score(
                    concept_name, 
                    st.session_state.understanding_progress,
                    learning_rate=0.3
                )
                st.session_state.current_concept = None
                st.session_state.learning_mode = None
                st.session_state.conversation_history = []
                st.session_state.understanding_progress = 0.0
                st.success(f"Kunskapsgrafen uppdaterad: Mastery för {concept_name} är nu {final_score:.2f} (från {old_score:.2f})")
                st.rerun()
    
    # Chat container
    chat_container = st.container()
    
    # Om ingen konversation startats, generera första frågan
    if not st.session_state.conversation_history:
        with st.spinner(f"AI förbereder första frågan...\nModell: {LITELLM_MODEL}"):
            llm_service = st.session_state.graph_builder.llm
            
            # Lägg till kunskapsgraf om valt
            additional_context = None
            if include_full_graph:
                knowledge_graph = get_full_knowledge_graph()
                additional_context = f"Studentens fullständiga kunskapsgraf:\n{knowledge_graph}"
            
            first_question = llm_service.get_socratic_question(
                concept_name=concept_name,
                concept_description=concept_info.get('beskrivning', ''),
                prerequisites=concept_info.get('prerequisites', []),
                mastery_score=concept_info.get('mastery_score', 0.0),
                dependent_concepts=concept_info.get('dependent_concepts', []),
                importance_reason=concept_info.get('importance_reason', ''),
                additional_context=additional_context
            )
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": first_question
            })
    
    # Visa konversationshistorik
    with chat_container:
        for message in st.session_state.conversation_history:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
            elif message["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.write(message["content"])
            elif message["role"] == "system":
                st.caption(message["content"])
    
    # Input för studentens svar
    user_input = st.chat_input("Skriv ditt svar här...")
    
    if user_input:
        # Lägg till studentens svar
        st.session_state.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Först: Generera sokratiskt svar (LLM1 - dialog)
        with st.spinner(f"AI formulerar svar...\nModell: {LITELLM_MODEL}"):
            llm_service = st.session_state.graph_builder.llm
            
            # Lägg till kunskapsgraf om valt
            additional_context = None
            if include_full_graph:
                knowledge_graph = get_full_knowledge_graph()
                additional_context = f"Studentens fullständiga kunskapsgraf:\n{knowledge_graph}"
            
            # Generera nästa sokratisk fråga
            next_question = llm_service.get_socratic_question(
                concept_name=concept_name,
                concept_description=concept_info.get('beskrivning', ''),
                prerequisites=concept_info.get('prerequisites', []),
                mastery_score=st.session_state.understanding_progress,
                conversation_history=st.session_state.conversation_history[-4:],
                dependent_concepts=concept_info.get('dependent_concepts', []),
                importance_reason=concept_info.get('importance_reason', ''),
                additional_context=additional_context
            )
            
            # Lägg till AI:s svar i historiken
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": next_question
            })
        
        # Sedan: Utvärdera förståelse i bakgrunden (LLM2 - bedömning)
        with st.spinner(f"Analyserar ditt svar...\nModell: {LITELLM_MODEL}"):
            evaluation = llm_service.evaluate_understanding(
                concept_name=concept_name,
                student_answer=user_input,
                key_concepts=None
            )
            
            # Debugging - visa vad vi fick från LLM
            if not isinstance(evaluation, dict):
                st.error(f"Utvärdering returnerade fel format: {type(evaluation)}")
                evaluation = {
                    "understanding_score": 0.1,
                    "strengths": [],
                    "gaps": ["Kunde inte analysera svaret"],
                    "feedback": "Ett tekniskt fel uppstod vid analys av ditt svar.",
                    "ready_to_progress": False
                }
            
            # Hämta utvärderingspoäng
            eval_score = evaluation.get('understanding_score', 0.1)
            
            # Uppdatera progress gradvis (max 0.2 ökning per svar)
            increase = min(eval_score * 0.2, 0.2)
            new_progress = min(st.session_state.understanding_progress + increase, 1.0)
            st.session_state.understanding_progress = new_progress
            
            # Uppdatera mastery score och visa kort notifikation
            if eval_score >= 0.3:
                old_score, new_mastery = update_mastery_score(
                    concept_name, 
                    new_progress,
                    learning_rate=0.15
                )
                # Lägg till systemmeddelande om uppdatering
                update_msg = f"[Mastery score uppdaterad: {old_score:.2f} → {new_mastery:.2f}. Kunskapsgrafen har uppdaterats.]"
                st.session_state.conversation_history.append({
                    "role": "system",
                    "content": update_msg
                })
            else:
                # Hämta nuvarande mastery score utan att uppdatera
                with st.session_state.neo4j_service.driver.session() as session:
                    result = session.run("""
                        MATCH (c:Koncept {namn: $namn})
                        RETURN COALESCE(c.mastery_score, 0.0) as current_score
                    """, namn=concept_name)
                    record = result.single()
                    current_mastery = record['current_score'] if record else 0.0
                
                # Lägg till systemmeddelande
                update_msg = f"[Mastery score ej uppdaterad (för låg förståelse). Nuvarande: {current_mastery:.2f}]"
                st.session_state.conversation_history.append({
                    "role": "system",
                    "content": update_msg
                })
            
            # Om redo att gå vidare, lägg till meddelande
            if evaluation.get('ready_to_progress', False) or st.session_state.understanding_progress >= 0.8:
                completion_msg = f"""Utmärkt arbete! Du verkar ha god förståelse för {concept_name}. 
                
Du kan välja att fortsätta fördjupa dig eller gå vidare till nästa koncept via knappen ovan.

Din nuvarande förståelsenivå: {int(st.session_state.understanding_progress * 100)}%"""
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": completion_msg
                })
            
            # Kort fördröjning för att visa meddelanden
            time.sleep(1.5)
            st.rerun()


def render_guided_learning(concept_name: str, concept_info: Dict):
    """Renderar guidat lärande med strukturerad förklaring"""
    st.markdown(f"#### Guidat lärande: {concept_name}")
    
    # Initiera chat historik om den inte finns
    if 'guided_chat_history' not in st.session_state:
        st.session_state.guided_chat_history = []
    if 'guided_mastery_updates' not in st.session_state:
        st.session_state.guided_mastery_updates = 0
    
    # Inställningar för AI-kontext
    col1, col2 = st.columns([3, 1])
    with col1:
        include_full_graph = st.checkbox(
            "Inkludera hela kunskapsgrafen i AI-kontext",
            value=True,  # Gör detta till standardval
            key="guided_include_graph",
            help="Om aktiverad skickas hela din kunskapsgraf till AI för bättre personalisering"
        )
    with col2:
        with st.popover("Information"):
            st.markdown("""
            **Vad skickas till AI:**
            
            **Standard (utan kunskapsgraf):**
            - Aktuellt koncept och beskrivning
            - Dina förutsättningar för konceptet
            - Din mastery score för konceptet
            - Relaterade kurser
            
            **Med kunskapsgraf:**
            - Allt ovan PLUS
            - Alla dina koncept med mastery scores
            - Relationer mellan alla koncept
            - Kursinformation för koncept
            """)
    
    # Generera förklaring om den inte redan finns
    if 'guided_explanation' not in st.session_state or st.session_state.get('explained_concept') != concept_name:
        with st.spinner(f"AI förbereder förklaring...\nModell: {LITELLM_MODEL}"):
            llm_service = st.session_state.graph_builder.llm
            
            # Lägg till kunskapsgraf om valt
            additional_context = None
            if include_full_graph:
                knowledge_graph = get_full_knowledge_graph()
                additional_context = f"Studentens fullständiga kunskapsgraf:\n{knowledge_graph}"
            
            explanation = llm_service.get_guided_explanation(
                concept_name=concept_name,
                concept_description=concept_info.get('beskrivning', ''),
                prerequisites=concept_info.get('prerequisites', []),
                related_courses=concept_info.get('courses', []),
                mastery_score=concept_info.get('mastery_score', 0.0),
                additional_context=additional_context
            )
            st.session_state.guided_explanation = explanation
            st.session_state.explained_concept = concept_name
    
    # Visa förklaring
    with st.container():
        st.markdown(st.session_state.guided_explanation)
    
    # Chat-baserad interaktion
    st.divider()
    st.markdown("#### Fortsätt lära dig")
    
    # Visa chat-historik
    if st.session_state.guided_chat_history:
        for msg in st.session_state.guided_chat_history:
            if msg['role'] == 'user':
                with st.chat_message("user"):
                    st.write(msg['content'])
            elif msg['role'] == 'assistant':
                with st.chat_message("assistant"):
                    st.write(msg['content'])
            elif msg['role'] == 'system':
                st.caption(msg['content'])
    
    # Hämta aktuell mastery score från databasen
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (c:Koncept {namn: $namn})
            RETURN COALESCE(c.mastery_score, 0.0) as mastery_score
        """, namn=concept_name)
        record = result.single()
        current_mastery = record['mastery_score'] if record else 0.0
    
    # Visa nuvarande mastery score
    color = '#FF6B6B' if current_mastery < 0.3 else '#95E1D3' if current_mastery >= 0.7 else '#4ECDC4'
    st.markdown(f"**Nuvarande mastery score:** <span style='color: {color}'>{current_mastery:.2f}</span>", unsafe_allow_html=True)
    
    if current_mastery >= 0.7:
        st.success("Du har uppnått god förståelse! Du kan fortsätta fördjupa dig eller gå vidare till nästa koncept.")
    
    # Chat input
    user_input = st.text_area(
        "Ställ frågor, förklara vad du förstått, eller be om fler exempel:",
        height=100,
        placeholder="Skriv här...",
        key=f"guided_chat_input_{st.session_state.guided_mastery_updates}"
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Skicka", key="send_guided", type="primary"):
            if user_input:
                # Lägg till användarens meddelande
                st.session_state.guided_chat_history.append({
                    'role': 'user',
                    'content': user_input
                })
                
                # Först: Generera naturligt svar (LLM1 - dialog)
                with st.spinner(f"AI svarar...\nModell: {LITELLM_MODEL}"):
                    llm_service = st.session_state.graph_builder.llm
                    
                    # Bygga kontext för guidat lärande
                    messages = [
                        {"role": "system", "content": f"""Du är en pedagogisk AI som hjälper studenter att förstå {concept_name}. 
                        Du har redan gett en strukturerad förklaring. Nu ska du svara på studentens frågor och förklara vidare.
                        Var uppmuntrande och pedagogisk. Ge exempel och förklaringar som bygger vidare på det studenten sagt."""}
                    ]
                    
                    # Lägg till konversationshistorik
                    for msg in st.session_state.guided_chat_history[-6:]:
                        if msg['role'] in ['user', 'assistant']:
                            messages.append({"role": msg["role"], "content": msg["content"]})
                    
                    # Generera svar
                    try:
                        chat_response = llm_service.client.chat.completions.create(
                            model=LITELLM_MODEL,
                            messages=messages,
                            temperature=0.7,
                            max_tokens=300
                        )
                        ai_response = chat_response.choices[0].message.content
                    except:
                        ai_response = "Intressant fråga! Kan du utveckla lite mer vad du menar?"
                    
                    # Lägg till AI:s svar
                    st.session_state.guided_chat_history.append({
                        'role': 'assistant',
                        'content': ai_response
                    })
                
                # Sedan: Utvärdera förståelse i bakgrunden (LLM2 - bedömning)
                with st.spinner(f"Analyserar förståelse...\nModell: {LITELLM_MODEL}"):
                    evaluation = llm_service.evaluate_understanding(
                        concept_name=concept_name,
                        student_answer=user_input
                    )
                    
                    # Mastery score
                    score = evaluation.get('understanding_score', 0.5)
                    
                    # Uppdatera mastery score
                    old_mastery, new_mastery = update_mastery_score(
                        concept_name, 
                        score,
                        learning_rate=0.15
                    )
                    
                    # Lägg till systemmeddelande om uppdatering
                    update_msg = f"[Mastery score uppdaterad: {old_mastery:.2f} → {new_mastery:.2f}. Kunskapsgrafen har uppdaterats.]"
                    st.session_state.guided_chat_history.append({
                        'role': 'system',
                        'content': update_msg
                    })
                    
                    # Öka update counter för att refresha input
                    st.session_state.guided_mastery_updates += 1
                    
                    # Refresha sidan efter kort paus
                    time.sleep(0.5)
                    st.rerun()
    
    with col2:
        if st.button("Avsluta och gå vidare", key="finish_guided"):
            if st.session_state.guided_mastery_updates > 0:
                st.session_state.current_concept = None
                st.session_state.learning_mode = None
                st.session_state.guided_explanation = None
                st.session_state.guided_chat_history = []
                st.session_state.guided_mastery_updates = 0
                st.rerun()
            else:
                st.warning("Interagera med AI:n minst en gång innan du går vidare")


def update_mastery_score(concept_name: str, new_score: float, learning_rate: float = 0.1):
    """Uppdaterar mastery score för ett koncept med exponentiell viktad genomsnittsformel"""
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta nuvarande mastery score
        result = session.run("""
            MATCH (c:Koncept {namn: $namn})
            RETURN COALESCE(c.mastery_score, 0.0) as current_score
        """, namn=concept_name)
        
        record = result.single()
        current_score = record['current_score'] if record else 0.0
        
        # Använd exponentiellt viktat genomsnitt för att uppdatera
        updated_score = (1 - learning_rate) * current_score + learning_rate * new_score
        
        # Uppdatera i databasen
        session.run("""
            MATCH (c:Koncept {namn: $namn})
            SET c.mastery_score = $score
        """, namn=concept_name, score=updated_score)
        
        # Visa bekräftelse
        st.success(f"Mastery score uppdaterad för {concept_name}: {current_score:.2f} → {updated_score:.2f}")
        
        return current_score, updated_score


def render_concept_progression(knowledge_profile: Dict):
    """Visar konceptprogression som progress bars"""
    st.markdown("#### Din kunskapsprogression")
    
    # Gruppera koncept efter mastery level
    not_started = []
    in_progress = []
    mastered = []
    
    for concept, info in knowledge_profile.items():
        score = info.get('mastery_score', 0)
        if score == 0:
            not_started.append((concept, score))
        elif score < 0.7:
            in_progress.append((concept, score))
        else:
            mastered.append((concept, score))
    
    # Beräkna totalt antal koncept
    total_concepts = len(knowledge_profile)
    
    # Visa övergripande progress bars
    col1, col2 = st.columns([3, 1])
    with col1:
        # Total progress
        if total_concepts > 0:
            mastered_percentage = len(mastered) / total_concepts
            st.progress(mastered_percentage, text=f"Behärskade koncept: {len(mastered)}/{total_concepts}")
            
            # Progress för pågående
            in_progress_percentage = len(in_progress) / total_concepts
            st.progress(in_progress_percentage, text=f"Pågående koncept: {len(in_progress)}/{total_concepts}")
    
    with col2:
        # Sammanfattning
        avg_score = sum(info.get('mastery_score', 0) for info in knowledge_profile.values()) / max(total_concepts, 1)
        color = '#FF6B6B' if avg_score < 0.3 else '#95E1D3' if avg_score >= 0.7 else '#4ECDC4'
        st.markdown(f"<h3 style='color: {color}; text-align: center;'>Snitt<br>{avg_score:.2f}</h3>", unsafe_allow_html=True)
    
    # Visa detaljer i expanderare
    with st.expander("Visa detaljerad progression"):
        # Pågående koncept med individuella progress bars
        if in_progress:
            st.markdown("##### Pågående koncept")
            for concept, score in sorted(in_progress, key=lambda x: x[1], reverse=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.progress(score, text=concept)
                with col2:
                    st.markdown(f"**{score:.2f}**")
        
        # Behärskade koncept
        if mastered:
            st.markdown("##### Behärskade koncept")
            for concept, score in sorted(mastered, key=lambda x: x[1], reverse=True)[:10]:  # Visa max 10
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.success(concept)
                with col2:
                    st.markdown(f"**{score:.2f}**")
            if len(mastered) > 10:
                st.caption(f"... och {len(mastered) - 10} till")
        
        # Ej påbörjade koncept
        if not_started:
            st.markdown("##### Ej påbörjade koncept")
            st.info(f"{len(not_started)} koncept väntar på att studeras")


if __name__ == "__main__":
    render()