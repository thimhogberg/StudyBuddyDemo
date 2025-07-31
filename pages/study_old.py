"""
Study-sida för optimerat lärande med AI-stöd
"""
import streamlit as st
import pandas as pd
from utils.session import init_session_state
from typing import Dict, List, Optional, Tuple
import json


def render():
    """Renderar study-sidan för optimerat lärande"""
    init_session_state()
    
    st.markdown("### Studera")
    st.markdown("Lär dig koncept optimalt baserat på din kunskapsgraf")
    
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
    
    # Hämta studentens kunskapsprofil och hitta nästa koncept
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
        if st.button("Ändra studieväg"):
            st.session_state.study_path = None
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
    # Använd befintlig logik för från grunden
    render_concept_learning(knowledge_profile, available_concepts)
    
    if recommendation and recommendation.get('recommended_concept'):
        # Visa rekommendation
        st.markdown("#### Nästa koncept att lära sig")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(recommendation['recommended_concept'])
            st.caption(recommendation['reasoning'])
            
            # Hämta detaljerad info om konceptet
            detailed_info = get_concept_details(recommendation['recommended_concept'])
            
            # Visa varför konceptet är viktigt
            st.markdown("**Varför lära sig detta?**")
            st.info(detailed_info.get('importance_reason', 'Grundläggande koncept inom området'))
            
            if detailed_info.get('dependent_concepts'):
                with st.expander(f"Koncept som bygger på detta ({len(detailed_info['dependent_concepts'])})"):
                    for dep in detailed_info['dependent_concepts'][:10]:  # Visa max 10
                        st.write(f"• {dep}")
                    if len(detailed_info['dependent_concepts']) > 10:
                        st.write(f"... och {len(detailed_info['dependent_concepts']) - 10} till")
            
            # Visa förutsättningar
            if recommendation.get('prerequisites_met'):
                st.success(f"Förutsättningar uppfyllda: {', '.join(recommendation['prerequisites_met'])}")
            if recommendation.get('prerequisites_missing'):
                st.warning(f"Saknade förutsättningar: {', '.join(recommendation['prerequisites_missing'])}")
            
            # Visa svårighetsgrad
            difficulty_colors = {'lätt': 'Lätt', 'medium': 'Medium', 'svår': 'Svår'}
            difficulty = recommendation.get('difficulty_level', 'medium')
            st.info(f"Svårighetsgrad: {difficulty_colors.get(difficulty, 'Medium')}")
        
        with col2:
            # Visa nuvarande mastery score
            current_mastery = knowledge_profile.get(recommendation['recommended_concept'], {}).get('mastery_score', 0.0)
            color = '#FF6B6B' if current_mastery == 0 else '#95E1D3' if current_mastery >= 0.7 else '#4ECDC4'
            st.markdown(f"<h2 style='color: {color}; text-align: center;'>Mastery<br>{current_mastery:.1f}</h2>", unsafe_allow_html=True)
        
        # Välj lärstil om inte redan vald
        if not st.session_state.learning_mode:
            st.divider()
            st.markdown("#### Välj din lärstil")
            
            col1, col2 = st.columns(2)
            
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
                if st.button("Byt lärstil", key="change_mode"):
                    st.session_state.learning_mode = None
                    st.session_state.conversation_history = []
                    st.session_state.understanding_progress = 0.0
                    st.rerun()
            with col3:
                if st.button("Markera som färdigt", key="mark_complete"):
                    old_score, new_score = update_mastery_score(
                        recommendation['recommended_concept'], 
                        0.8,
                        learning_rate=0.5  # 50% vikt på nya värdet vid manuell markering
                    )
                    st.session_state.current_concept = None
                    st.session_state.learning_mode = None
                    st.session_state.conversation_history = []
                    st.session_state.understanding_progress = 0.0
                    st.success(f"Kunskapsgrafen uppdaterad: Mastery för {recommendation['recommended_concept']} är nu {new_score:.2f} (från {old_score:.2f})")
                    st.rerun()
            
            st.divider()
            
            # Hämta konceptinformation
            concept_info = get_concept_details(recommendation['recommended_concept'])
            
            if st.session_state.learning_mode == "socratic":
                render_socratic_learning(recommendation['recommended_concept'], concept_info)
            elif st.session_state.learning_mode == "guided":
                render_guided_learning(recommendation['recommended_concept'], concept_info)
    
    else:
        st.info("Grattis! Du har inga nya koncept att lära dig just nu. Fortsätt öva på de koncept du redan påbörjat!")
    
    # Visa progression (konceptträd)
    st.divider()
    render_concept_progression(knowledge_profile)


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
                    learning_rate=0.3  # Större uppdatering vid avslut
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
        with st.spinner("Förbereder första frågan..."):
            llm_service = st.session_state.graph_builder.llm
            first_question = llm_service.get_socratic_question(
                concept_name=concept_name,
                concept_description=concept_info.get('beskrivning', ''),
                prerequisites=concept_info.get('prerequisites', []),
                mastery_score=concept_info.get('mastery_score', 0.0),
                dependent_concepts=concept_info.get('dependent_concepts', []),
                importance_reason=concept_info.get('importance_reason', '')
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
            else:
                with st.chat_message("assistant"):
                    st.write(message["content"])
    
    # Input för studentens svar
    user_input = st.chat_input("Skriv ditt svar här...")
    
    if user_input:
        # Lägg till studentens svar
        st.session_state.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Utvärdera förståelse
        with st.spinner("Analyserar ditt svar..."):
            llm_service = st.session_state.graph_builder.llm
            evaluation = llm_service.evaluate_understanding(
                concept_name=concept_name,
                student_answer=user_input,
                key_concepts=None  # Kan läggas till senare
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
            increase = min(eval_score * 0.2, 0.2)  # Max 20% ökning
            new_progress = min(st.session_state.understanding_progress + increase, 1.0)
            st.session_state.understanding_progress = new_progress
            
            # Visa LLMs analys av svaret
            st.markdown("**LLMs analys av ditt svar:**")
            st.markdown(f"*{evaluation.get('feedback', 'Ingen feedback tillgänglig')}*")
            
            if evaluation.get('strengths'):
                st.markdown("*Styrkor:* " + ", ".join(evaluation['strengths']))
            if evaluation.get('gaps'):
                st.markdown("*Förbättringsområden:* " + ", ".join(evaluation['gaps']))
            
            st.divider()
            
            # Uppdatera mastery score alltid och visa resultatet
            if eval_score >= 0.3:  # Uppdatera även vid lägre poäng
                old_score, new_mastery = update_mastery_score(
                    concept_name, 
                    new_progress,
                    learning_rate=0.15  # 15% uppdateringstakt
                )
                st.info(f"Kunskapsgrafen uppdaterad: Mastery för {concept_name} är nu {new_mastery:.2f} (från {old_score:.2f})")
            else:
                # Hämta nuvarande mastery score utan att uppdatera
                with st.session_state.neo4j_service.driver.session() as session:
                    result = session.run("""
                        MATCH (c:Koncept {namn: $namn})
                        RETURN COALESCE(c.mastery_score, 0.0) as current_score
                    """, namn=concept_name)
                    record = result.single()
                    current_mastery = record['current_score'] if record else 0.0
                st.info(f"Kunskapsgrafen ej uppdaterad. Nuvarande mastery för {concept_name}: {current_mastery:.2f}")
            
            # Generera nästa fråga eller feedback
            if evaluation.get('ready_to_progress', False) or st.session_state.understanding_progress >= 0.8:
                response = f"""Utmärkt arbete!

Du verkar ha god förståelse för {concept_name}. 

Vill du:
- Fortsätta med fler frågor för att fördjupa din kunskap?
- Avsluta och gå vidare till nästa koncept?

Din nuvarande förståelsenivå: {int(st.session_state.understanding_progress * 100)}%"""
            else:
                # Generera nästa sokratisk fråga
                next_question = llm_service.get_socratic_question(
                    concept_name=concept_name,
                    concept_description=concept_info.get('beskrivning', ''),
                    prerequisites=concept_info.get('prerequisites', []),
                    mastery_score=st.session_state.understanding_progress,
                    conversation_history=st.session_state.conversation_history[-4:],  # Senaste 4 meddelanden
                    dependent_concepts=concept_info.get('dependent_concepts', []),
                    importance_reason=concept_info.get('importance_reason', '')
                )
                # Behåll analysen i svaret
                response = next_question
            
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
        st.rerun()


def render_guided_learning(concept_name: str, concept_info: Dict):
    """Renderar guidat lärande med strukturerad förklaring"""
    st.markdown(f"#### Guidat lärande: {concept_name}")
    
    # Generera förklaring om den inte redan finns
    if 'guided_explanation' not in st.session_state or st.session_state.get('explained_concept') != concept_name:
        with st.spinner("Förbereder förklaring..."):
            llm_service = st.session_state.graph_builder.llm
            explanation = llm_service.get_guided_explanation(
                concept_name=concept_name,
                concept_description=concept_info.get('beskrivning', ''),
                prerequisites=concept_info.get('prerequisites', []),
                related_courses=concept_info.get('courses', []),
                mastery_score=concept_info.get('mastery_score', 0.0)
            )
            st.session_state.guided_explanation = explanation
            st.session_state.explained_concept = concept_name
    
    # Visa förklaring
    with st.container():
        st.markdown(st.session_state.guided_explanation)
    
    # Kontrollfrågor och interaktion
    st.divider()
    st.markdown("#### Testa din förståelse")
    
    user_reflection = st.text_area(
        "Förklara med egna ord vad du har lärt dig om detta koncept:",
        height=150,
        placeholder="Skriv din förklaring här..."
    )
    
    if st.button("Utvärdera min förståelse", key="evaluate_guided"):
        if user_reflection:
            with st.spinner("Utvärderar din förståelse..."):
                llm_service = st.session_state.graph_builder.llm
                evaluation = llm_service.evaluate_understanding(
                    concept_name=concept_name,
                    student_answer=user_reflection
                )
                
                # Visa utvärdering
                st.divider()
                
                # Förståelsepoäng
                score = evaluation.get('understanding_score', 0.5)
                color = '#FF6B6B' if score < 0.4 else '#95E1D3' if score >= 0.7 else '#4ECDC4'
                st.markdown(f"<h3 style='color: {color};'>Din förståelse: {int(score * 100)}%</h3>", unsafe_allow_html=True)
                
                # Feedback
                col1, col2 = st.columns(2)
                
                with col1:
                    if evaluation.get('strengths'):
                        st.success("**Styrkor:**")
                        for strength in evaluation['strengths']:
                            st.write(f"- {strength}")
                
                with col2:
                    if evaluation.get('gaps'):
                        st.warning("**Att förbättra:**")
                        for gap in evaluation['gaps']:
                            st.write(f"• {gap}")
                
                st.info(evaluation.get('feedback', ''))
                
                # Uppdatera mastery score om hög förståelse
                if score >= 0.7:
                    st.success(f"Bra jobbat! Din förståelse är {int(score * 100)}%")
                    if st.button("Spara och fortsätt", key="save_guided"):
                        old_mastery, new_mastery = update_mastery_score(
                            concept_name, 
                            score,
                            learning_rate=0.25  # 25% uppdateringstakt för guidat lärande
                        )
                        st.success(f"Kunskapsgrafen uppdaterad: Mastery för {concept_name} är nu {new_mastery:.2f} (från {old_mastery:.2f})")
                        st.session_state.current_concept = None
                        st.session_state.learning_mode = None
                        st.session_state.guided_explanation = None
                        st.rerun()
                else:
                    st.info("Läs igenom förklaringen igen och fokusera på de områden som behöver förbättras.")
        else:
            st.warning("Vänligen skriv en förklaring innan du utvärderar.")


def update_mastery_score(concept_name: str, new_score: float, learning_rate: float = 0.1):
    """Uppdaterar mastery score för ett koncept med exponentiell viktad genomsnittsformel
    
    Args:
        concept_name: Namnet på konceptet
        new_score: Ny förståelsepoäng från utvärdering
        learning_rate: Hur snabbt mastery uppdateras (0.1 = 10% av nya värdet)
    """
    with st.session_state.neo4j_service.driver.session() as session:
        # Hämta nuvarande mastery score
        result = session.run("""
            MATCH (c:Koncept {namn: $namn})
            RETURN COALESCE(c.mastery_score, 0.0) as current_score
        """, namn=concept_name)
        
        record = result.single()
        current_score = record['current_score'] if record else 0.0
        
        # Använd exponentiellt viktat genomsnitt för att uppdatera
        # Ny score = (1 - learning_rate) * current + learning_rate * new
        updated_score = (1 - learning_rate) * current_score + learning_rate * new_score
        
        # Uppdatera i databasen
        session.run("""
            MATCH (c:Koncept {namn: $namn})
            SET c.mastery_score = $score
        """, namn=concept_name, score=updated_score)
        
        return current_score, updated_score


def render_concept_progression(knowledge_profile: Dict):
    """Visar konceptprogression som ett träd eller lista"""
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
    
    # Visa i tre kolumner
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("##### Ej påbörjade")
        st.caption(f"{len(not_started)} koncept")
        with st.expander("Visa koncept"):
            for concept, score in sorted(not_started):
                st.write(f"• {concept}")
    
    with col2:
        st.markdown("##### Pågående")
        st.caption(f"{len(in_progress)} koncept")
        with st.expander("Visa koncept"):
            for concept, score in sorted(in_progress, key=lambda x: x[1], reverse=True):
                st.write(f"• {concept} ({score:.1f})")
    
    with col3:
        st.markdown("##### Behärskade")
        st.caption(f"{len(mastered)} koncept")
        with st.expander("Visa koncept"):
            for concept, score in sorted(mastered, key=lambda x: x[1], reverse=True):
                st.write(f"• {concept} ({score:.1f})")


if __name__ == "__main__":
    render()