"""
Smart träning - AI-driven optimerad inlärning
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import plotly.graph_objects as go
from utils.session import init_session_state
from typing import Dict, List, Optional, Tuple
import math
import uuid


def get_or_create_student_profile() -> Dict:
    """Hämtar eller skapar studentprofil i Neo4j - endast EN Student-nod i hela grafen"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Först, kolla om det finns någon Student-nod överhuvudtaget
            result = session.run("""
                MATCH (s:Student)
                RETURN s
                LIMIT 1
            """)
            
            record = result.single()
            
            if record:
                # Student finns redan - använd den
                student = dict(record['s'])
                # Spara student-id i session state för framtida referens
                if 'id' in student:
                    st.session_state.student_id = student['id']
                return student
            else:
                # Skapa den ENDA Student-noden med MERGE för säkerhet
                student_id = st.session_state.get('student_id', 'main-student')
                result = session.run("""
                    MERGE (s:Student {id: $student_id})
                    ON CREATE SET 
                        s.created_at = datetime(),
                        s.custom_instructions = '',
                        s.ai_learning_profile = '{}',
                        s.preferences = '{}',
                        s.learning_history = '[]'
                    RETURN s
                """, student_id=student_id)
                
                record = result.single()
                if record:
                    st.session_state.student_id = student_id
                    return dict(record['s'])
                else:
                    return {
                        'id': student_id,
                        'custom_instructions': '',
                        'ai_learning_profile': '{}',
                        'preferences': '{}'
                    }
                    
    except Exception as e:
        st.error(f"Fel vid hantering av studentprofil: {str(e)}")
        return {
            'id': 'main-student',
            'custom_instructions': '',
            'ai_learning_profile': '{}',
            'preferences': '{}'
        }


def update_student_preferences(**kwargs) -> bool:
    """Uppdaterar studentens preferenser i Neo4j - använder den ENDA Student-noden"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Bygg SET-satser dynamiskt
            set_clauses = []
            params = {}
            
            if 'custom_instructions' in kwargs:
                set_clauses.append("s.custom_instructions = $custom_instructions")
                params['custom_instructions'] = kwargs['custom_instructions']
            
            if 'ai_learning_profile' in kwargs:
                set_clauses.append("s.ai_learning_profile = $ai_learning_profile")
                params['ai_learning_profile'] = json.dumps(kwargs['ai_learning_profile'])
            
            if 'preferences' in kwargs:
                set_clauses.append("s.preferences = $preferences")
                params['preferences'] = json.dumps(kwargs['preferences'])
            
            if set_clauses:
                query = f"""
                    MATCH (s:Student)
                    SET {', '.join(set_clauses)}, s.updated_at = datetime()
                    RETURN s
                    LIMIT 1
                """
                
                result = session.run(query, **params)
                return result.single() is not None
            
            return True
            
    except Exception as e:
        st.error(f"Fel vid uppdatering av preferenser: {str(e)}")
        return False


def render():
    """Renderar Smart träning-sidan"""
    init_session_state()
    
    st.markdown("### Smart träning")
    st.markdown("AI-optimerat lärande som automatiskt väljer vad, hur och när du ska studera")
    
    # Kontrollera konfiguration
    from config import NEO4J_URI, NEO4J_PASSWORD, LITELLM_API_KEY, LITELLM_BASE_URL
    
    if not NEO4J_URI or not NEO4J_PASSWORD:
        st.error("Neo4j databas är inte konfigurerad!")
        st.info("Se instruktioner under inställningar för att konfigurera Neo4j")
        return
    
    if not LITELLM_API_KEY or not LITELLM_BASE_URL:
        st.error("LiteLLM API är inte konfigurerad!")
        st.info("Se instruktioner under inställningar för att konfigurera LiteLLM")
        return
    
    if not st.session_state.neo4j_service:
        st.error("Kunde inte ansluta till databas")
        return
    
    # Hämta eller skapa studentprofil från Neo4j - endast när behövs
    student_profile = None
    
    # Confusion tracking sker nu via FÖRVÄXLAS_MED relationer i Neo4j
    
    # Huvudinnehåll
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("#### Nästa optimala träningsmoment")
    
    with col2:
        if st.button("Hitta nytt", help="Beräkna om nästa optimala koncept"):
            if 'current_training' in st.session_state:
                del st.session_state.current_training
    
    with col3:
        show_details = st.checkbox("Visa detaljer", value=True)
    
    # Hitta och visa optimal träning - endast när användaren klickar på "Hitta nytt" eller första gången
    if 'current_training' not in st.session_state and 'smart_training_initialized' in st.session_state:
        with st.spinner("AI analyserar din kunskapsprofil..."):
            optimal_concept, score_details = find_optimal_concept()
            if optimal_concept:
                st.session_state.current_training = {
                    'concept': optimal_concept,
                    'score_details': score_details,
                    'start_time': datetime.now()
                }
    
    # Om det är första gången användaren öppnar fliken, visa en startknapp
    if 'smart_training_initialized' not in st.session_state:
        st.info("Klicka på 'Starta smart träning' för att börja din optimerade träningssession.")
        if st.button("Starta smart träning", type="primary", use_container_width=True):
            st.session_state.smart_training_initialized = True
            st.rerun()
    
    if 'current_training' in st.session_state:
        concept_data = st.session_state.current_training['concept']
        score_details = st.session_state.current_training['score_details']
        
        # Visa konceptinfo
        st.markdown(f"### {concept_data['namn']}")
        
        # Visa score-detaljer om valt
        if show_details:
            with st.expander("Optimeringsdetaljer", expanded=False):
                # Första raden med metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Total score", 
                        f"{score_details['total_score']:.2f}",
                        help=f"""Hur optimal detta koncept är för lärande just nu.
                        
Formel: Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time

Beräkning för detta koncept:
ΔP(recall) = {score_details['recall_improvement']:.3f}
discrimination_bonus = {score_details['training_effect']:.3f}
failure_risk = {score_details.get('failure_risk', 0):.3f}
time (timmar) = {score_details['estimated_time']/60:.2f}

Score = ({score_details['recall_improvement']:.3f} + {score_details['training_effect']:.3f} - {score_details.get('failure_risk', 0):.3f}) / {score_details['estimated_time']/60:.2f} = {score_details['total_score']:.2f}

Högre score = mer effektivt för lärande per tidsenhet."""
                    )
                
                with col2:
                    st.metric(
                        "ΔP(recall)", 
                        f"+{score_details['recall_improvement']:.1%}",
                        help=f"""Förväntad förbättring i sannolikhet att minnas vid tentamen.

Baseras på forgetting curve: R(t) = e^(-t/S)
där t = tid sedan senaste repetition, S = stability

Nuvarande retention: {score_details['current_retention']:.1%}
Målretention efter träning: 90%
Förbättring: {score_details['recall_improvement']:.1%}

Detta koncept behöver repeteras eftersom retention sjunkit."""
                    )
                
                with col3:
                    st.metric(
                        "Träningseffekt", 
                        f"{score_details['training_effect']:.2f}",
                        help=f"""Interleaving-bonus för koncept som ofta förväxlas.

Baseras på FÖRVÄXLAS_MED relationer i grafen.
Ju oftare detta koncept förväxlas med andra, desto högre bonus.

Träning på dessa koncept förbättrar din förmåga att särskilja
liknande koncept, vilket är extra värdefullt för lärande.

Bonus = antal_förväxlingar × 0.1"""
                    )
                
                with col4:
                    st.metric(
                        "Success rate", 
                        f"{score_details['success_probability']:.0%}",
                        help=f"""Sannolikhet att klara övningen utan hjälp.

Formel: P(success) = mastery × (1 - difficulty) + 0.3

mastery = {concept_data.get('mastery_score', 0):.1%}
difficulty = {concept_data.get('difficulty', 0.3):.1%}
P(success) = {concept_data.get('mastery_score', 0):.2f} × (1 - {concept_data.get('difficulty', 0.3):.2f}) + 0.3 = {score_details['success_probability']:.1%}

Om < 60%: failure_risk straff appliceras i score-beräkningen."""
                    )
                
                # Andra raden med fler metrics
                col5, col6, col7, col8 = st.columns(4)
                
                with col5:
                    st.metric(
                        "Nuvarande retention", 
                        f"{score_details['current_retention']:.0%}",
                        help=f"""Sannolikhet att du minns konceptet just nu.

Beräknas med forgetting curve: R(t) = e^(-t/S)

Senaste repetition: {concept_data.get('last_review', 'Aldrig')}
Tid sedan repetition: {(datetime.now() - datetime.fromisoformat(concept_data['last_review'])).days if concept_data.get('last_review') else 'N/A'} dagar
Stability (S): {concept_data.get('retention', 1.0):.1f}

Ju lägre retention, desto mer angeläget att repetera."""
                    )
                
                with col6:
                    st.metric(
                        "Estimerad tid", 
                        f"{score_details['estimated_time']:.0f} min",
                        help=f"""Uppskattad tid för träningspasset.

Formel: tid = 5 + (difficulty × 10) minuter

difficulty = {concept_data.get('difficulty', 0.3):.1%}
tid = 5 + ({concept_data.get('difficulty', 0.3):.1f} × 10) = {score_details['estimated_time']:.0f} min

Lätta koncept: ~5 min
Medelsvåra: ~8-10 min  
Svåra: ~12-15 min"""
                    )
                
                with col7:
                    mastery = concept_data.get('mastery_score', 0)
                    st.metric(
                        "Mastery level", 
                        f"{mastery:.1%}",
                        help=f"""Din behärskning av konceptet.

0-30%: Låg mastery → Guidat lärande
30-70%: Medium mastery → Övningsläge
70-100%: Hög mastery → Avancerade utmaningar

Mastery justeras baserat på dina resultat:
- Rätt svar: +10% mastery
- Osäker: +5% mastery
- Fel svar: -5% mastery

Påverkar success_probability och träningsmetod."""
                    )
                
                with col8:
                    difficulty = concept_data.get('difficulty', 0.3)
                    st.metric(
                        "Svårighetsgrad", 
                        f"{difficulty:.1%}",
                        help=f"""Konceptets inneboende svårighetsgrad.

Startvärde: 30%
Justeras dynamiskt baserat på alla studenters resultat:
- Om många misslyckas: difficulty ökar (+10%)
- Om många lyckas: difficulty minskar (-10%)

Påverkar:
- Success probability beräkning
- Estimerad tid för träning
- Failure risk i optimeringen

Aktuell difficulty används för att anpassa utmaningen."""
                    )
                
                # Visa motivering
                st.info(f"""
                **Varför detta koncept?**
                - Retention har sjunkit till {score_details['current_retention']:.0%}
                - Optimal tidpunkt för repetition
                - {score_details.get('reason', 'Maximerar lärande per tidsenhet')}
                """)
                
                # Visa fullständig formelberäkning
                st.markdown("### Fullständig beräkning")
                
                # Skapa en snygg tabell med beräkningen
                calc_data = {
                    'Komponent': ['ΔP(recall)', 'Discrimination bonus', 'Failure risk', 'Summa (täljare)', 'Tid (timmar)', 'TOTAL SCORE'],
                    'Formel': [
                        'målretention - nuvarande_retention',
                        'antal_förväxlingar × 0.1',
                        'max(0, (0.6 - success_rate) × 2)',
                        'ΔP + bonus - risk',
                        '(5 + difficulty × 10) / 60',
                        'summa / tid'
                    ],
                    'Värde': [
                        f"{score_details['recall_improvement']:.3f}",
                        f"{score_details['training_effect']:.3f}",
                        f"-{score_details.get('failure_risk', 0):.3f}",
                        f"{score_details['recall_improvement'] + score_details['training_effect'] - score_details.get('failure_risk', 0):.3f}",
                        f"{score_details['estimated_time']/60:.2f}",
                        f"{score_details['total_score']:.2f}"
                    ]
                }
                
                df = pd.DataFrame(calc_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Visa formel med faktiska värden
                st.markdown(f"""
                **Beräkning steg för steg:**
                ```
                Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time
                
                Score = ({score_details['recall_improvement']:.3f} + {score_details['training_effect']:.3f} - {score_details.get('failure_risk', 0):.3f}) / {score_details['estimated_time']/60:.2f}
                
                Score = {score_details['recall_improvement'] + score_details['training_effect'] - score_details.get('failure_risk', 0):.3f} / {score_details['estimated_time']/60:.2f}
                
                Score = {score_details['total_score']:.2f}
                ```
                """)
        
        # Välj och visa träningsmetod baserat på mastery
        mastery = concept_data.get('mastery_score', 0)
        
        if mastery < 0.3:
            show_guided_learning(concept_data)
        elif mastery < 0.7:
            show_practice_mode(concept_data)
        else:
            show_advanced_mode(concept_data)
        
        # Feedback-sektion
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Förstått!", type="primary", use_container_width=True):
                update_learning_progress(concept_data['namn'], success=True)
                st.success("Bra jobbat! Går vidare...")
                if 'current_training' in st.session_state:
                    del st.session_state.current_training
                st.rerun()
        
        with col2:
            if st.button("🤔 Osäker", use_container_width=True):
                update_learning_progress(concept_data['namn'], success=False, partial=True)
                st.info("Försöker med annan metod...")
                st.rerun()
        
        with col3:
            if st.button("❌ För svårt", use_container_width=True):
                update_learning_progress(concept_data['namn'], success=False)
                # Visa modal för att registrera förväxling
                st.session_state.show_confusion_modal = True
                st.session_state.failed_concept = concept_data['namn']
                st.rerun()
    
    # Hantera förväxlingsmodal
    if st.session_state.get('show_confusion_modal', False):
        show_confusion_modal()
    
    # Visa progress dashboard och förklaringar endast om träning är initierad
    if 'smart_training_initialized' in st.session_state:
        # Visa progress dashboard
        st.divider()
        show_progress_dashboard()
        
        # Visa förklaringar och preferenser längst ner
        st.divider()
        
        # Förklaringsruta om hur Smart träning fungerar
        with st.expander("Hur fungerar Smart träning?", expanded=False):
            st.markdown("""
            ### Smart träning använder en AI-driven optimeringsalgoritm
            
            **Optimeringsformeln:**
            ```
            Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time
            ```
            
            **Komponenter:**
            
            1. **ΔP(recall) - Förbättring i minnessannolikhet**
               - Uppskattar hur mycket repetition kommer förbättra ditt minne
               - Använder en förenklad modell av glömskekurvan
               - Prioriterar koncept du håller på att glömma
            
            2. **Discrimination bonus - Interleaving-effekt**
               - Extra poäng för koncept som ofta förväxlas med andra
               - Träning på dessa förbättrar din förmåga att särskilja liknande koncept
               - Baseras på FÖRVÄXLAS_MED relationer i kunskapsgrafen
            
            3. **Failure risk - Risk för misslyckande**
               - Undviker uppgifter som är för svåra baserat på din mastery
               - Siktar på lagom utmaning (ca 60% chans att lyckas)
               - Enkel regelbaserad anpassning
            
            4. **Time - Estimerad träningstid**
               - Algoritmen prioriterar effektivt lärande per tidsenhet
               - Kortare, effektiva sessioner prioriteras
            
            **Anpassning efter Mastery Level:**
            - **Låg mastery (< 0.3):** Guidat lärande med förklaringar
            - **Medium mastery (0.3-0.7):** Övningsläge med frågor
            - **Hög mastery (> 0.7):** Svårare uppgifter
            
            **Personliga instruktioner:**
            - Du kan ge egna instruktioner för hur AI ska förklara
            - Dessa sparas och används för att anpassa förklaringar
            - Systemet använder en enkel optimeringsformel, inte machine learning
            """)
        
        # Visa preferenser
        with st.expander("Dina träningspreferenser", expanded=False):
            st.info("AI lär sig automatiskt din inlärningsstil baserat på hur du interagerar med systemet. Du kan också ge egna instruktioner nedan.")
            
            # Lazy load student profile when preferences are expanded
            if student_profile is None:
                student_profile = get_or_create_student_profile()
            
            # Custom instructions
            col1, col2 = st.columns([3, 1])
            
            with col1:
                current_instructions = student_profile.get('custom_instructions', '')
                new_instructions = st.text_area(
                    "Egna instruktioner till AI:n",
                    value=current_instructions,
                    placeholder="T.ex: Förklara med kodexempel i Python. Jag föredrar korta förklaringar med praktiska exempel. Relatera gärna till webbutveckling.",
                    height=100,
                    help="Beskriv hur du vill att AI:n ska förklara saker för dig"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                if st.button("Spara instruktioner", use_container_width=True):
                    update_student_preferences(custom_instructions=new_instructions)
                    st.success("Instruktioner sparade!")
                    st.rerun()
            
            # Visa AI:s insikter om studenten
            if student_profile.get('ai_learning_profile') and student_profile['ai_learning_profile'] != '{}':
                try:
                    ai_profile = json.loads(student_profile['ai_learning_profile'])
                    if ai_profile and ai_profile.get('identifierad_stil'):
                        st.markdown("### AI:s insikter om din inlärning")
                        st.markdown(f"**Identifierad stil:** {ai_profile['identifierad_stil']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if ai_profile.get('styrkor'):
                                st.markdown("**Dina styrkor:**")
                                for styrka in ai_profile['styrkor']:
                                    st.markdown(f"• {styrka}")
                        
                        with col2:
                            if ai_profile.get('observerade_mönster'):
                                mönster = ai_profile['observerade_mönster']
                                st.markdown("**Observerade mönster:**")
                                if 'bästa_tid_på_dygnet' in mönster:
                                    st.markdown(f"• Bäst fokus: {mönster['bästa_tid_på_dygnet']}")
                                if 'genomsnittlig_fokustid' in mönster:
                                    st.markdown(f"• Fokustid: {mönster['genomsnittlig_fokustid']} min")
                        
                        # Visa success rate om tillgänglig
                        if ai_profile.get('average_success_rate') is not None:
                            st.markdown(f"**Din genomsnittliga success rate:** {ai_profile['average_success_rate']:.0%}")
                except:
                    pass  # Om JSON-parsing misslyckas, visa ingenting


def show_confusion_modal():
    """Visar modal för att registrera vilket koncept som förväxlades"""
    
    st.markdown("### Vad förväxlade du det med?")
    st.info("Detta hjälper systemet att ge dig bättre övningar i framtiden")
    
    # Hämta liknande koncept
    failed_concept = st.session_state.failed_concept
    similar_concepts = get_similar_concepts(failed_concept)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        confused_with = st.selectbox(
            "Jag tänkte att det var:",
            ["Inget speciellt - bara svårt"] + similar_concepts,
            key="confusion_select"
        )
    
    with col2:
        if st.button("Registrera", type="primary"):
            if confused_with != "Inget speciellt - bara svårt":
                register_confusion(failed_concept, confused_with)
            
            # Rensa modal
            st.session_state.show_confusion_modal = False
            st.session_state.failed_concept = None
            if 'current_training' in st.session_state:
                del st.session_state.current_training
            st.rerun()
        
        if st.button("Hoppa över"):
            st.session_state.show_confusion_modal = False
            st.session_state.failed_concept = None
            if 'current_training' in st.session_state:
                del st.session_state.current_training
            st.rerun()


def get_similar_concepts(concept_name: str) -> List[str]:
    """Hämtar koncept som är relaterade eller i samma kurs"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Hämta koncept från samma kurs eller med liknande namn
            result = session.run("""
                MATCH (c:Koncept {namn: $namn})<-[:INNEHÅLLER]-(k:Kurs)-[:INNEHÅLLER]->(other:Koncept)
                WHERE other.namn <> $namn
                RETURN DISTINCT other.namn as namn
                LIMIT 10
                UNION
                MATCH (c:Koncept {namn: $namn})-[:FÖRUTSÄTTER|FÖRVÄXLAS_MED]-(other:Koncept)
                RETURN DISTINCT other.namn as namn
                LIMIT 10
            """, namn=concept_name)
            
            return [record['namn'] for record in result]
            
    except:
        return []


def register_confusion(concept1: str, concept2: str):
    """Registrerar att två koncept förväxlades"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Skapa eller uppdatera FÖRVÄXLAS_MED relation
            session.run("""
                MATCH (c1:Koncept {namn: $concept1}), (c2:Koncept {namn: $concept2})
                MERGE (c1)-[r:FÖRVÄXLAS_MED]-(c2)
                ON CREATE SET r.count = 1, r.last_confusion = datetime()
                ON MATCH SET r.count = r.count + 1, r.last_confusion = datetime()
            """, concept1=concept1, concept2=concept2)
            
            st.success(f"Registrerat: {concept1} ↔ {concept2}")
            
    except Exception as e:
        st.error(f"Kunde inte registrera förväxling: {str(e)}")


def find_optimal_concept() -> Tuple[Optional[Dict], Dict]:
    """Hittar det optimala konceptet att träna på just nu"""
    
    # Hämta alla koncept med deras data
    concepts = get_all_concepts_with_memory_data()
    
    if not concepts:
        return None, {}
    
    best_concept = None
    best_score = -float('inf')
    best_details = {}
    
    for concept in concepts:
        score, details = calculate_concept_score(concept)
        
        if score > best_score:
            best_score = score
            best_concept = concept
            best_details = details
    
    return best_concept, best_details


def calculate_concept_score(concept: Dict) -> Tuple[float, Dict]:
    """Beräknar score för ett koncept enligt formeln:
    Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time
    """
    
    # Hämta konceptdata
    mastery = concept.get('mastery_score', 0)
    retention = concept.get('retention', 1.0)
    difficulty = concept.get('difficulty', 0.3)
    last_review = concept.get('last_review')
    review_count = concept.get('review_count', 0)
    
    # Beräkna tid sedan senaste repetition
    if last_review:
        time_since_review = (datetime.now() - datetime.fromisoformat(last_review)).total_seconds() / 86400
    else:
        time_since_review = 30  # Anta 30 dagar om aldrig repeterat
    
    # 1. Beräkna ΔP(recall) - förbättring i minnessannolikhet
    current_retention = retention * math.exp(-time_since_review / (retention * 10))
    optimal_retention_after = 0.9  # Målretention efter träning
    recall_improvement = max(0, optimal_retention_after - current_retention)
    
    # 2. Beräkna discrimination_bonus (interleaving effect)
    discrimination_bonus = 0
    
    # Hämta koncept som ofta förväxlas från Neo4j
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (c:Koncept {namn: $namn})-[r:FÖRVÄXLAS_MED]-(other:Koncept)
                RETURN other.namn as confused_concept, r.count as confusion_count
            """, namn=concept['namn'])
            
            for record in result:
                # Bonus baserat på hur ofta koncepten förväxlas
                discrimination_bonus += (record['confusion_count'] or 1) * 0.1
    except:
        pass  # Om inga förväxlingar finns
    
    # 3. Beräkna failure_risk
    # Estimera success probability baserat på mastery och difficulty
    success_probability = mastery * (1 - difficulty) + 0.3  # Minst 30% chans
    failure_risk = 0
    
    if success_probability < 0.6:
        failure_risk = (0.6 - success_probability) * 2  # Straffa hårt om för svårt
    
    # 4. Estimera tid (minuter)
    estimated_time = 5 + (difficulty * 10)  # 5-15 minuter beroende på svårighet
    
    # Beräkna total score
    numerator = recall_improvement + discrimination_bonus - failure_risk
    total_score = numerator / (estimated_time / 60)  # Normalisera till per timme
    
    # Lägg till bonus för koncept som är viktiga (många beroenden)
    dependency_bonus = len(concept.get('dependencies', [])) * 0.05
    total_score += dependency_bonus
    
    details = {
        'total_score': total_score,
        'recall_improvement': recall_improvement,
        'current_retention': current_retention,
        'training_effect': discrimination_bonus,
        'failure_risk': failure_risk,
        'success_probability': success_probability,
        'estimated_time': estimated_time,
        'reason': get_recommendation_reason(concept, current_retention, discrimination_bonus)
    }
    
    return total_score, details


def get_recommendation_reason(concept: Dict, retention: float, discrimination_bonus: float) -> str:
    """Genererar en förklaring för varför detta koncept rekommenderas"""
    
    reasons = []
    
    if retention < 0.5:
        reasons.append("Minnet behöver förstärkas snart")
    
    if discrimination_bonus > 0.2:
        reasons.append("Tränar viktiga gränsdragningar")
    
    if concept.get('mastery_score', 0) < 0.3:
        reasons.append("Grundläggande koncept som behöver läras")
    
    dependencies = len(concept.get('dependencies', []))
    if dependencies > 3:
        reasons.append(f"Centralt koncept ({dependencies} andra koncept bygger på detta)")
    
    return " • ".join(reasons) if reasons else "Optimalt för lärande just nu"


def show_guided_learning(concept: Dict):
    """Visar guidat lärande för låg mastery (< 0.3)"""
    
    st.markdown("#### Guidat lärande")
    st.info("Eftersom detta är nytt för dig börjar vi med en förklaring")
    
    # Generera och visa förklaring
    with st.spinner("AI genererar förklaring anpassad för dig..."):
        explanation = generate_concept_explanation(concept)
    
    # Visa förklaring
    with st.container():
        st.markdown("**Förklaring:**")
        st.markdown(explanation)
    
    # Visa exempel om det genereras
    st.markdown("#### Exempel")
    with st.spinner("Genererar exempel..."):
        example = generate_concept_example(concept)
    with st.expander("Se exempel", expanded=True):
        st.markdown(example)
    
    st.divider()
    
    # Konceptkort med interaktiva alternativ
    st.markdown("### Fördjupa din förståelse")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Välj hur du vill fortsätta lära dig:**")
    
    with col2:
        st.markdown("**Din mastery:**")
        mastery = concept.get('mastery_score', 0)
        st.metric("", f"{mastery:.0%}", label_visibility="collapsed")
    
    # Chips för olika hjälpalternativ
    chip_cols = st.columns(3)
    
    with chip_cols[0]:
        if st.button("Förklara enklare", use_container_width=True, key="explain_simpler_btn"):
            if 'show_simpler' not in st.session_state:
                st.session_state.show_simpler = True
            else:
                st.session_state.show_simpler = not st.session_state.show_simpler
        
        if st.button("Worked example (steg-för-steg)", use_container_width=True, key="worked_ex_btn"):
            if 'show_worked_example' not in st.session_state:
                st.session_state.show_worked_example = True
            else:
                st.session_state.show_worked_example = not st.session_state.show_worked_example
    
    with chip_cols[1]:
        # Knapp för jämförelse
        if st.button("Jämför med annat koncept", use_container_width=True, key="compare_btn"):
            if 'show_compare_selector' not in st.session_state:
                st.session_state.show_compare_selector = True
            else:
                st.session_state.show_compare_selector = not st.session_state.show_compare_selector
        
        if st.button("Visa visualisering", use_container_width=True, key="visualize_btn"):
            if 'show_visualization' not in st.session_state:
                st.session_state.show_visualization = True
            else:
                st.session_state.show_visualization = not st.session_state.show_visualization
    
    with chip_cols[2]:
        if st.button("Vanliga missförstånd", use_container_width=True, key="misconception_btn"):
            if 'show_misconceptions' not in st.session_state:
                st.session_state.show_misconceptions = True
            else:
                st.session_state.show_misconceptions = not st.session_state.show_misconceptions
        
        if st.button("Testa mig kort (2 frågor)", use_container_width=True, key="test_btn"):
            st.session_state.show_quick_test = True
    
    # Visa allt innehåll nedanför knapparna
    st.divider()
    
    # Enklare förklaring
    if st.session_state.get('show_simpler'):
        with st.container():
            st.markdown("#### Enklare förklaring")
            
            # Cache the content
            cache_key = f"simpler_{concept['namn']}"
            if cache_key not in st.session_state:
                with st.spinner("Genererar enklare förklaring..."):
                    st.session_state[cache_key] = generate_simpler_explanation(concept)
                
                # Spåra händelsen
                track_learning_event(
                    event_type='viewed_simpler_explanation',
                    concept_name=concept['namn'],
                    time_spent=1.0
                )
            
            st.info(st.session_state[cache_key])
    
    # Jämförelse - visa väljare först
    if st.session_state.get('show_compare_selector'):
        with st.container():
            st.markdown("#### Välj koncept att jämföra med")
            all_concepts = get_all_concepts_in_graph()
            
            # Extrahera bara namn från koncept-listan
            concept_names = [c['namn'] for c in all_concepts if c['namn'] != concept['namn']]
            
            # Lägg till möjlighet att skriva in eget koncept
            compare_options = ["Välj koncept..."] + concept_names + ["Annat (skriv själv)"]
            selected_compare = st.selectbox(
                "Välj koncept att jämföra med:",
                compare_options,
                key="compare_select"
            )
            
            if selected_compare == "Annat (skriv själv)":
                custom_concept = st.text_input("Skriv koncept att jämföra med:", key="custom_compare")
                if custom_concept and st.button("Starta jämförelse", key="start_compare_custom"):
                    st.session_state.show_comparison = True
                    st.session_state.comparison_target = custom_concept
                    st.session_state.show_compare_selector = False
            elif selected_compare != "Välj koncept...":
                if st.button(f"Jämför med {selected_compare}", key="start_compare_selected"):
                    st.session_state.show_comparison = True
                    st.session_state.comparison_target = selected_compare
                    st.session_state.show_compare_selector = False
    
    # Worked example
    if st.session_state.get('show_worked_example'):
        show_worked_example_section(concept)
    
    # Jämförelse - visa resultat
    if st.session_state.get('show_comparison') and st.session_state.get('comparison_target'):
        with st.container():
            st.markdown(f"#### Jämförelse: {concept['namn']} vs {st.session_state.comparison_target}")
            
            # Cache the comparison
            cache_key = f"comparison_{concept['namn']}_{st.session_state.comparison_target}"
            if cache_key not in st.session_state:
                with st.spinner("Genererar jämförelse..."):
                    st.session_state[cache_key] = generate_comparison(concept['namn'], st.session_state.comparison_target)
                
                # Spåra händelsen
                track_learning_event(
                    event_type='viewed_comparison',
                    concept_name=concept['namn'],
                    details={'compared_with': st.session_state.comparison_target}
                )
            
            st.markdown(st.session_state[cache_key])
    
    # Visualisering
    if st.session_state.get('show_visualization'):
        with st.container():
            st.markdown("#### Visualisering")
            
            # Cache the visualization
            cache_key = f"visualization_{concept['namn']}"
            if cache_key not in st.session_state:
                with st.spinner("Genererar visualisering..."):
                    st.session_state[cache_key] = generate_visualization(concept)
                
                # Spåra händelsen
                track_learning_event(
                    event_type='viewed_visualization',
                    concept_name=concept['namn']
                )
            
            st.markdown(st.session_state[cache_key])
    
    # Missförstånd
    if st.session_state.get('show_misconceptions'):
        with st.container():
            st.markdown("#### Vanliga missförstånd")
            
            # Cache the misconceptions
            cache_key = f"misconceptions_{concept['namn']}"
            if cache_key not in st.session_state:
                with st.spinner("Hämtar vanliga missförstånd..."):
                    st.session_state[cache_key] = generate_misconceptions(concept)
                
                # Spåra händelsen
                track_learning_event(
                    event_type='viewed_misconceptions',
                    concept_name=concept['namn']
                )
            
            st.warning(st.session_state[cache_key])
    
    # Snabbtest
    if st.session_state.get('show_quick_test'):
        show_quick_test_section(concept)


def show_practice_mode(concept: Dict):
    """Visar övningsläge för medium mastery (0.3-0.7)"""
    
    st.markdown("#### Övningsläge")
    
    # Initiera fråga om den inte finns
    if 'current_question' not in st.session_state:
        st.session_state.current_question = generate_practice_question(concept)
        st.session_state.question_answered = False
        st.session_state.question_start_time = datetime.now()
    
    # Visa fråga
    st.markdown(st.session_state.current_question['question'])
    
    # Svarsruta
    if not st.session_state.question_answered:
        answer = st.text_area("Ditt svar:", height=100)
        
        if st.button("Kontrollera svar"):
            if answer.strip():
                # Evaluera svar med AI
                evaluation = evaluate_answer(
                    concept,
                    st.session_state.current_question['question'],
                    answer
                )
                
                st.session_state.question_answered = True
                st.session_state.evaluation = evaluation
                
                # Spåra händelsen
                time_spent = (datetime.now() - st.session_state.question_start_time).total_seconds() / 60
                track_learning_event(
                    event_type='practice_question',
                    concept_name=concept['namn'],
                    success=evaluation['correct'],
                    time_spent=time_spent,
                    details={'question': st.session_state.current_question['question'], 'answer': answer}
                )
                
                st.rerun()
    else:
        # Visa utvärdering
        eval_data = st.session_state.evaluation
        
        if eval_data['correct']:
            st.success("Rätt svar!")
        else:
            # Visa ingen "Delvis rätt" ruta för "Vet ej"-svar
            pass
        
        st.markdown(f"**Feedback:** {eval_data['feedback']}")
        
        if not eval_data['correct']:
            with st.expander("Se förklaring"):
                st.markdown(eval_data['explanation'])


def show_advanced_mode(concept: Dict):
    """Visar avancerat läge för hög mastery (> 0.7)"""
    
    st.markdown("#### Avancerad träning")
    st.info("Du behärskar grunderna - dags för utmaningar!")
    
    # Generera avancerad uppgift
    if 'advanced_task' not in st.session_state:
        st.session_state.advanced_task = generate_advanced_task(concept)
    
    task = st.session_state.advanced_task
    
    # Visa uppgift
    st.markdown(f"**Uppgift:** {task['task']}")
    
    if task.get('hint'):
        with st.expander("Ledtråd"):
            st.markdown(task['hint'])
    
    # Lösningsområde
    solution = st.text_area("Din lösning:", height=200)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Visa lösning"):
            with st.expander("Lösning", expanded=True):
                st.markdown(task['solution'])


def show_progress_dashboard():
    """Visar dashboard med träningsstatistik"""
    
    st.markdown("#### Din träningsstatistik")
    
    # Hämta statistik
    stats = get_training_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Tränade idag",
            stats['concepts_today'],
            delta=f"{stats['concepts_today'] - stats['concepts_yesterday']} från igår"
        )
    
    with col2:
        st.metric(
            "Genomsnittlig retention",
            f"{stats['avg_retention']:.0%}",
            delta=f"{stats['retention_change']:+.0%}"
        )
    
    with col3:
        streak_text = "🔥" if stats['streak'] > 3 else ""
        st.metric(
            "Streak",
            f"{stats['streak']} dagar",
            delta=streak_text if streak_text else None
        )
    
    with col4:
        st.metric(
            "Total mastery",
            f"{stats['total_mastery']:.0%}",
            delta=f"{stats['mastery_change']:+.0%}"
        )
    
    # Visa kommande repetitioner
    with st.expander("Kommande repetitioner"):
        upcoming = get_upcoming_reviews()
        if upcoming:
            for concept in upcoming[:5]:
                days_until = (datetime.fromisoformat(concept['next_review']) - datetime.now()).days
                st.markdown(f"- **{concept['namn']}** om {days_until} dagar")
        else:
            st.info("Inga schemalagda repetitioner")


def get_all_concepts_with_memory_data() -> List[Dict]:
    """Hämtar alla koncept med minnesdata från databasen"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (c:Koncept)
                OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
                OPTIONAL MATCH (dependent:Koncept)-[:FÖRUTSÄTTER]->(c)
                RETURN c.namn as namn,
                       c.beskrivning as beskrivning,
                       c.mastery_score as mastery_score,
                       c.retention as retention,
                       c.difficulty as difficulty,
                       c.review_count as review_count,
                       c.last_review as last_review,
                       c.next_review as next_review,
                       collect(DISTINCT prereq.namn) as prerequisites,
                       collect(DISTINCT dependent.namn) as dependencies
            """)
            
            concepts = []
            for record in result:
                concepts.append({
                    'namn': record['namn'],
                    'beskrivning': record['beskrivning'],
                    'mastery_score': record['mastery_score'] or 0,
                    'retention': record['retention'] or 1.0,
                    'difficulty': record['difficulty'] or 0.3,
                    'review_count': record['review_count'] or 0,
                    'last_review': record['last_review'],
                    'next_review': record['next_review'],
                    'prerequisites': [p for p in record['prerequisites'] if p],
                    'dependencies': [d for d in record['dependencies'] if d]
                })
            
            return concepts
            
    except Exception as e:
        st.error(f"Fel vid hämtning av koncept: {str(e)}")
        return []


def track_learning_event(event_type: str, concept_name: str, success: bool = None, time_spent: float = None, details: Dict = None):
    """Spårar inlärningshändelser och uppdaterar studentprofilen"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Hämta den ENDA studentprofilen
            result = session.run("""
                MATCH (s:Student)
                RETURN s.ai_learning_profile as profile, s.learning_history as history
                LIMIT 1
            """)
            
            record = result.single()
            if not record:
                # Om ingen student finns, skapa en
                get_or_create_student_profile()
                return
            
            # Parsea befintlig data
            ai_profile = json.loads(record['profile'] or '{}')
            learning_history = json.loads(record['history'] or '[]')
            
            # Lägg till ny händelse
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'concept': concept_name,
                'success': success,
                'time_spent': time_spent,
                'hour_of_day': datetime.now().hour,
                'day_of_week': datetime.now().weekday(),
                'details': details or {}
            }
            learning_history.append(event)
            
            # Behåll bara senaste 1000 händelser
            if len(learning_history) > 1000:
                learning_history = learning_history[-1000:]
            
            # Uppdatera AI-profil baserat på mönster
            ai_profile = update_ai_profile(ai_profile, learning_history)
            
            # Spara tillbaka till Neo4j
            session.run("""
                MATCH (s:Student)
                SET s.ai_learning_profile = $profile,
                    s.learning_history = $history,
                    s.last_activity = datetime()
            """, 
                profile=json.dumps(ai_profile),
                history=json.dumps(learning_history)
            )
            
    except Exception as e:
        st.error(f"Fel vid spårning av händelse: {str(e)}")


def update_ai_profile(profile: Dict, history: List[Dict]) -> Dict:
    """Uppdaterar AI-profilen baserat på inlärningshistorik"""
    
    if len(history) < 10:  # Behöver minst 10 händelser för analys
        return profile
    
    # Analysera senaste 100 händelser
    recent_events = history[-100:]
    
    # Beräkna success rate
    success_events = [e for e in recent_events if e.get('success') is not None]
    if success_events:
        success_rate = sum(1 for e in success_events if e['success']) / len(success_events)
        profile['average_success_rate'] = success_rate
    
    # Analysera tid på dygnet
    hour_performance = {}
    for event in recent_events:
        if event.get('success') is not None:
            hour = event['hour_of_day']
            if hour not in hour_performance:
                hour_performance[hour] = {'success': 0, 'total': 0}
            hour_performance[hour]['total'] += 1
            if event['success']:
                hour_performance[hour]['success'] += 1
    
    # Hitta bästa tid på dygnet
    best_hour = None
    best_rate = 0
    for hour, data in hour_performance.items():
        if data['total'] >= 3:  # Minst 3 försök
            rate = data['success'] / data['total']
            if rate > best_rate:
                best_rate = rate
                best_hour = hour
    
    if best_hour is not None:
        if best_hour < 12:
            best_time = "förmiddag"
        elif best_hour < 17:
            best_time = "eftermiddag"
        else:
            best_time = "kväll"
        
        if 'observerade_mönster' not in profile:
            profile['observerade_mönster'] = {}
        profile['observerade_mönster']['bästa_tid_på_dygnet'] = best_time
    
    # Analysera genomsnittlig fokustid
    time_spent_events = [e for e in recent_events if e.get('time_spent') is not None]
    if time_spent_events:
        avg_time = sum(e['time_spent'] for e in time_spent_events) / len(time_spent_events)
        if 'observerade_mönster' not in profile:
            profile['observerade_mönster'] = {}
        profile['observerade_mönster']['genomsnittlig_fokustid'] = round(avg_time)
    
    # Identifiera inlärningsstil baserat på mönster
    if success_rate > 0.8:
        profile['identifierad_stil'] = "Snabblärare - du tar snabbt till dig nya koncept"
        profile['styrkor'] = [
            "Snabb förståelse",
            "Hög success rate",
            "Effektiv inlärning"
        ]
    elif success_rate > 0.6:
        profile['identifierad_stil'] = "Metodisk lärare - du bygger kunskap steg för steg"
        profile['styrkor'] = [
            "Stabil progression",
            "God uthållighet",
            "Balanserad approach"
        ]
    else:
        profile['identifierad_stil'] = "Grundlig lärare - du tar dig tid att förstå på djupet"
        profile['styrkor'] = [
            "Djup förståelse",
            "Noggrannhet",
            "Reflekterande"
        ]
    
    return profile


def update_learning_progress(concept_name: str, success: bool, partial: bool = False):
    """Uppdaterar inlärningsdata efter träning"""
    
    # Spåra händelsen
    time_spent = None
    if 'current_training' in st.session_state and 'start_time' in st.session_state.current_training:
        time_spent = (datetime.now() - st.session_state.current_training['start_time']).total_seconds() / 60
    
    track_learning_event(
        event_type='concept_practice',
        concept_name=concept_name,
        success=success,
        time_spent=time_spent,
        details={'partial': partial}
    )
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Hämta nuvarande data
            result = session.run("""
                MATCH (c:Koncept {namn: $namn})
                RETURN c.mastery_score as mastery,
                       c.retention as retention,
                       c.difficulty as difficulty,
                       c.review_count as review_count
            """, namn=concept_name)
            
            record = result.single()
            if record:
                mastery = record['mastery'] or 0
                retention = record['retention'] or 1.0
                difficulty = record['difficulty'] or 0.3
                review_count = record['review_count'] or 0
                
                # Uppdatera baserat på resultat
                if success:
                    # Öka mastery och retention
                    new_mastery = min(1.0, mastery + 0.1)
                    new_retention = min(2.0, retention * 1.2)
                    new_difficulty = max(0.1, difficulty * 0.9)
                elif partial:
                    # Liten ökning
                    new_mastery = min(1.0, mastery + 0.05)
                    new_retention = retention
                    new_difficulty = difficulty
                else:
                    # Minska retention, öka difficulty
                    new_mastery = max(0, mastery - 0.05)
                    new_retention = max(0.5, retention * 0.8)
                    new_difficulty = min(0.9, difficulty * 1.1)
                
                # Beräkna nästa review
                if success:
                    interval = int(new_retention * 7)  # Dagar till nästa review
                else:
                    interval = 1  # Repetera snart igen
                
                next_review = (datetime.now() + timedelta(days=interval)).isoformat()
                
                # Uppdatera i databasen
                session.run("""
                    MATCH (c:Koncept {namn: $namn})
                    SET c.mastery_score = $mastery,
                        c.retention = $retention,
                        c.difficulty = $difficulty,
                        c.review_count = $review_count,
                        c.last_review = $last_review,
                        c.next_review = $next_review
                """, 
                    namn=concept_name,
                    mastery=new_mastery,
                    retention=new_retention,
                    difficulty=new_difficulty,
                    review_count=review_count + 1,
                    last_review=datetime.now().isoformat(),
                    next_review=next_review
                )
                
    except Exception as e:
        st.error(f"Fel vid uppdatering: {str(e)}")


def generate_concept_explanation(concept: Dict) -> str:
    """Genererar förklaring anpassad efter studentprofil"""
    
    # Hämta studentprofil från Neo4j
    student_profile = get_or_create_student_profile()
    custom_instructions = student_profile.get('custom_instructions', '')
    
    prompt = f"""Förklara konceptet '{concept['namn']}' för en student.

Konceptbeskrivning: {concept.get('beskrivning', '')}

{f'Studentens egna instruktioner: {custom_instructions}' if custom_instructions else 'Använd en tydlig och pedagogisk förklaringsstil.'}

Ge en pedagogisk förklaring som är lätt att förstå."""

    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return f"**{concept['namn']}**\n\n{concept.get('beskrivning', 'Beskrivning saknas.')}"


def generate_concept_example(concept: Dict) -> str:
    """Genererar exempel för konceptet"""
    
    # Hämta studentprofil från Neo4j
    student_profile = get_or_create_student_profile()
    custom_instructions = student_profile.get('custom_instructions', '')
    
    prompt = f"""Ge ett konkret, praktiskt exempel som illustrerar konceptet '{concept['namn']}'.

Konceptbeskrivning: {concept.get('beskrivning', '')}

{f'Studentens preferenser: {custom_instructions}' if custom_instructions else ''}

Exemplet ska vara:
- Konkret och relaterbart
- Visar tydligt hur konceptet används
- Lagom detaljerat"""

    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return "Exempel kommer snart..."


def generate_practice_question(concept: Dict) -> Dict:
    """Genererar övningsfråga"""
    
    prompt = f"""Generera en övningsfråga för konceptet '{concept['namn']}'.

Konceptbeskrivning: {concept.get('beskrivning', '')}
Studentens mastery: {concept.get('mastery_score', 0)}

Frågan ska:
- Testa förståelse, inte memorering
- Vara lagom svår för mastery-nivån
- Kunna besvaras i 2-5 meningar

Returnera ENDAST frågan, ingen förklaring."""

    try:
        from src.llm_service import LLMService
        llm = LLMService()
        question = llm.query(prompt)
        
        return {
            'question': question,
            'concept': concept['namn']
        }
    except:
        return {
            'question': f"Förklara {concept['namn']} med egna ord och ge ett exempel.",
            'concept': concept['namn']
        }


def generate_advanced_task(concept: Dict) -> Dict:
    """Genererar avancerad uppgift"""
    
    prompt = f"""Skapa en avancerad uppgift för konceptet '{concept['namn']}'.

Konceptbeskrivning: {concept.get('beskrivning', '')}

Uppgiften ska:
- Kräva djup förståelse och tillämpning
- Eventuellt kombinera med relaterade koncept
- Vara utmanande men lösbar

Ge:
1. Uppgiftsbeskrivning
2. En ledtråd (om studenten behöver)
3. Fullständig lösning"""

    try:
        from src.llm_service import LLMService
        llm = LLMService()
        response = llm.query(prompt)
        
        # Enkel parsing av svaret
        parts = response.split('\n\n')
        
        return {
            'task': parts[0] if len(parts) > 0 else "Avancerad uppgift",
            'hint': parts[1] if len(parts) > 1 else "Tänk på grundprinciperna",
            'solution': parts[2] if len(parts) > 2 else "Lösning kommer..."
        }
    except:
        return {
            'task': f"Tillämpa {concept['namn']} på ett komplext problem",
            'hint': "Börja med att identifiera grundprinciperna",
            'solution': "Lösning genereras..."
        }


def evaluate_answer(concept: Dict, question: str, answer: str) -> Dict:
    """Evaluerar studentens svar"""
    
    # Kolla först om studenten svarat "vet ej" eller liknande
    answer_lower = answer.lower().strip()
    if any(phrase in answer_lower for phrase in ["vet ej", "vet inte", "ingen aning", "vet ej.", "vet inte."]):
        # Generera pedagogisk förklaring med LLM
        explanation = generate_concept_explanation(concept)
        
        return {
            'correct': False,
            'feedback': "Du svarade att du inte vet. Det är okej att inte veta! Låt oss gå igenom konceptet tillsammans.",
            'explanation': explanation
        }
    
    prompt = f"""Evaluera studentens svar på denna fråga om '{concept['namn']}':

Fråga: {question}
Studentens svar: {answer}

VIKTIGT: Om studenten svarar "vet ej", "vet inte" eller liknande, ska det ALLTID bedömas som fel.

Bedöm:
1. Är svaret korrekt? (ja/nej)
2. Ge konstruktiv feedback
3. Om fel, ge en kort förklaring

Var uppmuntrande men ärlig."""

    try:
        from src.llm_service import LLMService
        llm = LLMService()
        response = llm.query(prompt)
        
        # Enkel analys av svaret
        correct = "ja" in response.lower()[:50] or "rätt" in response.lower()[:50]
        
        return {
            'correct': correct,
            'feedback': response.split('\n')[0] if '\n' in response else response[:200],
            'explanation': response
        }
    except:
        return {
            'correct': False,
            'feedback': "Kunde inte evaluera svaret automatiskt",
            'explanation': "Jämför ditt svar med konceptbeskrivningen"
        }


def get_training_statistics() -> Dict:
    """Hämtar träningsstatistik"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Hämta dagens träning
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            result = session.run("""
                MATCH (c:Koncept)
                WHERE c.last_review IS NOT NULL
                RETURN 
                    sum(CASE WHEN date(c.last_review) = date($today) THEN 1 ELSE 0 END) as today_count,
                    sum(CASE WHEN date(c.last_review) = date($yesterday) THEN 1 ELSE 0 END) as yesterday_count,
                    avg(c.retention) as avg_retention,
                    avg(c.mastery_score) as avg_mastery
            """, today=today.isoformat(), yesterday=yesterday.isoformat())
            
            record = result.single()
            
            # Beräkna streak (förenklad)
            streak = 1  # TODO: Implementera riktig streak-beräkning
            
            return {
                'concepts_today': record['today_count'] or 0,
                'concepts_yesterday': record['yesterday_count'] or 0,
                'avg_retention': record['avg_retention'] or 0,
                'retention_change': 0.05,  # TODO: Beräkna faktisk förändring
                'streak': streak,
                'total_mastery': record['avg_mastery'] or 0,
                'mastery_change': 0.02  # TODO: Beräkna faktisk förändring
            }
            
    except Exception as e:
        return {
            'concepts_today': 0,
            'concepts_yesterday': 0,
            'avg_retention': 0,
            'retention_change': 0,
            'streak': 0,
            'total_mastery': 0,
            'mastery_change': 0
        }


def get_upcoming_reviews() -> List[Dict]:
    """Hämtar kommande schemalagda repetitioner"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (c:Koncept)
                WHERE c.next_review IS NOT NULL
                AND date(c.next_review) >= date()
                RETURN c.namn as namn, c.next_review as next_review
                ORDER BY c.next_review
                LIMIT 10
            """)
            
            return [dict(record) for record in result]
            
    except Exception:
        return []


def get_confused_concepts(concept_name: str) -> List[str]:
    """Hämtar koncept som ofta förväxlas med detta"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (c:Koncept {namn: $namn})-[r:FÖRVÄXLAS_MED]-(other:Koncept)
                RETURN other.namn as namn, r.count as count
                ORDER BY r.count DESC
                LIMIT 3
            """, namn=concept_name)
            
            return [record['namn'] for record in result]
    except:
        return []


def get_common_misconception(concept: Dict) -> str:
    """Hämtar vanligt missförstånd för konceptet"""
    
    # Detta kan senare hämtas från databasen baserat på faktiska fel
    # För nu, generera baserat på koncept
    misconceptions = {
        "derivata": "att det är samma som integral",
        "integral": "att det bara är area under kurva",
        "rekursion": "att det alltid är ineffektivt",
        "pekare": "att de är samma som variabler"
    }
    
    # Kolla om vi har ett fördefinierat missförstånd
    for key, value in misconceptions.items():
        if key.lower() in concept['namn'].lower():
            return value
    
    return None


def show_micro_chat(concept: Dict, chat_type: str, target: str = None):
    """Initierar en mikro-chatt med specifikt mål"""
    
    st.session_state.active_micro_chat = {
        'concept': concept,
        'type': chat_type,
        'target': target,
        'exchanges': 0,
        'max_exchanges': 5,
        'messages': []
    }
    
    # Spåra händelsen
    track_learning_event(
        event_type='micro_chat_started',
        concept_name=concept['namn'],
        details={'chat_type': chat_type, 'target': target}
    )


def show_active_micro_chat():
    """Visar den aktiva mikro-chatten"""
    
    chat = st.session_state.active_micro_chat
    
    # Container för chatten
    with st.container():
        st.markdown("---")
        
        # Header med stäng-knapp
        col1, col2 = st.columns([4, 1])
        with col1:
            chat_titles = {
                'explain_simpler': "Enklare förklaring",
                'worked_example': "Worked Example",
                'contrast': f"Jämför med {chat.get('target', 'annat koncept')}",
                'visualize': "Visualisering",
                'misconception': "Vanligt missförstånd",
                'quick_test': "Snabbtest"
            }
            st.markdown(f"#### {chat_titles.get(chat['type'], 'Hjälp')}")
        
        with col2:
            if st.button("❌ Stäng", key="close_micro_chat"):
                del st.session_state.active_micro_chat
                st.rerun()
        
        # Visa meddelanden
        for msg in chat.get('messages', []):
            if msg['role'] == 'assistant':
                st.info(msg['content'])
            else:
                st.markdown(f"**Du:** {msg['content']}")
        
        # Generera första meddelande om chatten just startade
        if len(chat.get('messages', [])) == 0:
            initial_message = generate_micro_chat_message(chat)
            chat['messages'].append({'role': 'assistant', 'content': initial_message})
            st.info(initial_message)
        
        # Input om vi inte nått max exchanges
        if chat['exchanges'] < chat['max_exchanges']:
            # Föreslagna svar baserat på kontext
            if chat['type'] == 'quick_test':
                # För test, visa svarsalternativ eller inputfält
                show_micro_test_input(chat)
            else:
                # För andra typer, visa föreslagna följdfrågor
                suggested_responses = get_suggested_responses(chat)
                
                col_count = len(suggested_responses)
                if col_count > 0:
                    cols = st.columns(col_count)
                    for i, suggestion in enumerate(suggested_responses):
                        with cols[i]:
                            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                                handle_micro_chat_response(chat, suggestion)
                
                # Eller skriv egen fråga
                user_input = st.text_input("Eller skriv din fråga:", key="micro_chat_input")
                if user_input and st.button("Skicka", key="send_micro_chat"):
                    handle_micro_chat_response(chat, user_input)
        else:
            # Max exchanges nått - visa avslutning
            st.success("✅ Bra jobbat! Nu är det dags att öva.")
            if st.button("Fortsätt till övning", type="primary"):
                del st.session_state.active_micro_chat
                st.session_state.show_quick_test = True
                st.rerun()


def generate_micro_chat_message(chat: Dict) -> str:
    """Genererar kontextspecifikt meddelande för mikro-chatten"""
    
    concept = chat['concept']
    chat_type = chat['type']
    
    prompts = {
        'explain_simpler': f"""Förklara {concept['namn']} på ett mycket enkelt sätt.
        Använd vardagliga ord och en konkret analogi.
        Max 3-4 meningar.""",
        
        'worked_example': f"""Visa ett worked example för {concept['namn']}.
        Steg 1: Visa problemet
        Steg 2: Förklara tankesättet
        Steg 3: Visa lösningen steg för steg""",
        
        'contrast': f"""Förklara skillnaden mellan {concept['namn']} och {chat.get('target', 'relaterat koncept')}.
        Fokusera på:
        1. Vad som är gemensamt
        2. Den kritiska skillnaden
        3. När man använder vilket""",
        
        'visualize': f"""Beskriv en visuell representation av {concept['namn']}.
        Förklara vad bilden skulle visa och hur det hjälper förståelsen.""",
        
        'misconception': f"""Förklara varför många tror att {concept['namn']} {chat.get('target', 'är något annat')}.
        Visa varför detta är fel och vad som är rätt.""",
        
        'quick_test': f"""Här kommer två snabba frågor om {concept['namn']}:
        
        Fråga 1: [Grundläggande förståelsefråga]
        Fråga 2: [Tillämpningsfråga]
        
        Svara på båda så kort som möjligt."""
    }
    
    prompt = prompts.get(chat_type, f"Hjälp studenten förstå {concept['namn']}")
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return f"Här skulle jag förklara {concept['namn']} på ett sätt anpassat för {chat_type}."


def get_suggested_responses(chat: Dict) -> List[str]:
    """Returnerar föreslagna svar baserat på chattkontext"""
    
    chat_type = chat['type']
    
    suggestions = {
        'explain_simpler': [
            "Kan du ge ett exempel?",
            "Vad betyder det i praktiken?",
            "Hur skiljer det sig från...?"
        ],
        'worked_example': [
            "Visa nästa steg",
            "Varför det steget?",
            "Kan jag prova själv?"
        ],
        'contrast': [
            "När använder jag vilket?",
            "Ge ett exempel på varje",
            "Vad händer om jag blandar?"
        ],
        'visualize': [
            "Förklara bilden mer",
            "Visa annan vinkel",
            "Hur relaterar till formeln?"
        ],
        'misconception': [
            "Varför tänker man fel?",
            "Ge motexempel",
            "Hur undviker jag detta?"
        ]
    }
    
    return suggestions.get(chat_type, ["Förklara mer", "Ge exempel", "Jag förstår"])


def handle_micro_chat_response(chat: Dict, response: str):
    """Hanterar användarens svar i mikro-chatten"""
    
    # Lägg till användarens meddelande
    chat['messages'].append({'role': 'user', 'content': response})
    chat['exchanges'] += 1
    
    # Generera AI-svar
    ai_response = generate_contextual_response(chat, response)
    chat['messages'].append({'role': 'assistant', 'content': ai_response})
    
    # Spåra händelsen
    track_learning_event(
        event_type='micro_chat_exchange',
        concept_name=chat['concept']['namn'],
        details={
            'chat_type': chat['type'],
            'exchange_num': chat['exchanges'],
            'user_response': response
        }
    )
    
    st.rerun()


def generate_contextual_response(chat: Dict, user_response: str) -> str:
    """Genererar kontextuellt svar baserat på användarens input"""
    
    # Bygg konversationshistorik
    history = "\n".join([
        f"{'AI' if msg['role'] == 'assistant' else 'Student'}: {msg['content']}"
        for msg in chat['messages']
    ])
    
    prompt = f"""Du är en mikro-coach som hjälper med konceptet '{chat['concept']['namn']}'.
    
Konversationstyp: {chat['type']}
Max utbyten: {chat['max_exchanges']}
Nuvarande utbyte: {chat['exchanges']}

Konversationshistorik:
{history}

Student säger: {user_response}

Ge ett kort, fokuserat svar (max 3-4 meningar) som:
1. Adresserar studentens fråga direkt
2. Leder mot handling/övning om vi närmar oss max utbyten
3. Håller fokus på konceptet

Svar:"""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return "Bra fråga! Låt mig förklara det på ett annat sätt..."


def show_micro_test_input(chat: Dict):
    """Visar input för snabbtest i mikro-chatten"""
    
    if 'test_questions' not in chat:
        # Generera testfrågor första gången
        chat['test_questions'] = generate_micro_test_questions(chat['concept'])
        chat['current_question'] = 0
        chat['answers'] = []
    
    questions = chat['test_questions']
    current_q = chat['current_question']
    
    if current_q < len(questions):
        st.markdown(f"**Fråga {current_q + 1}:** {questions[current_q]['question']}")
        
        answer = st.text_input("Ditt svar:", key=f"test_answer_{current_q}")
        
        if st.button("Svara", key=f"submit_test_{current_q}"):
            # Spara svaret
            chat['answers'].append(answer)
            
            # Evaluera svaret
            is_correct = evaluate_micro_test_answer(
                questions[current_q],
                answer,
                chat['concept']
            )
            
            if is_correct:
                st.success("✅ Rätt!")
            else:
                st.error(f"❌ Inte riktigt. Rätt svar: {questions[current_q]['answer']}")
            
            # Gå till nästa fråga
            chat['current_question'] += 1
            
            if chat['current_question'] >= len(questions):
                # Test klart
                correct_count = sum(1 for a in chat['answers'] if a)  # Förenkla
                st.success(f"Test klart! Du fick {correct_count}/{len(questions)} rätt.")
                
                # Uppdatera mastery baserat på resultat
                success_rate = correct_count / len(questions)
                update_learning_progress(
                    chat['concept']['namn'],
                    success=success_rate > 0.5,
                    partial=success_rate == 0.5
                )
            
            st.rerun()


def generate_micro_test_questions(concept: Dict) -> List[Dict]:
    """Genererar 2 snabba testfrågor för konceptet"""
    
    prompt = f"""Generera 2 korta testfrågor för konceptet '{concept['namn']}'.

Fråga 1: Grundläggande förståelse (kan besvaras i 1-2 meningar)
Fråga 2: Enkel tillämpning (kan besvaras i 2-3 meningar)

Format:
{{"questions": [
    {{"question": "...", "answer": "...", "type": "understanding"}},
    {{"question": "...", "answer": "...", "type": "application"}}
]}}"""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        response = llm.query(prompt)
        
        # Försök parsa JSON
        import json
        data = json.loads(response)
        return data.get('questions', [])
    except:
        # Fallback
        return [
            {
                'question': f"Vad är huvudsyftet med {concept['namn']}?",
                'answer': "Varied beroende på koncept",
                'type': 'understanding'
            },
            {
                'question': f"Ge ett exempel på när du skulle använda {concept['namn']}.",
                'answer': "Varied beroende på koncept",
                'type': 'application'
            }
        ]


def evaluate_micro_test_answer(question: Dict, answer: str, concept: Dict) -> bool:
    """Evaluerar om svaret är korrekt"""
    
    if not answer or len(answer) < 10:
        return False
    
    prompt = f"""Evaluera om studentens svar är korrekt.

Koncept: {concept['namn']}
Fråga: {question['question']}
Förväntat svar (riktlinje): {question['answer']}
Studentens svar: {answer}

Är svaret i huvudsak korrekt? Svara bara JA eller NEJ."""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        response = llm.query(prompt).strip().upper()
        return response == "JA"
    except:
        # Enkel heuristik som fallback
        return len(answer) > 20


def show_worked_example_section(concept: Dict):
    """Visar worked example med fading"""
    
    st.markdown("### Worked Example")
    
    # Generera eller hämta worked example
    if 'worked_example' not in st.session_state:
        st.session_state.worked_example = generate_worked_example(concept)
        st.session_state.fading_level = 0
    
    example = st.session_state.worked_example
    fading_level = st.session_state.fading_level
    
    # Visa example med olika grader av fading
    if fading_level == 0:
        # Full example
        st.markdown("**Komplett exempel:**")
        st.code(example['full'], language=example.get('language', 'text'))
        
        if st.button("Nästa: Delvis ifyllt →"):
            st.session_state.fading_level = 1
            st.rerun()
    
    elif fading_level == 1:
        # Partial fading
        st.markdown("**Fyll i de saknade delarna:**")
        st.code(example['partial'], language=example.get('language', 'text'))
        
        user_solution = st.text_area("Din lösning för de saknade delarna:")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Tillbaka till komplett"):
                st.session_state.fading_level = 0
                st.rerun()
        
        with col2:
            if user_solution and st.button("Nästa: Egen lösning →"):
                st.session_state.fading_level = 2
                st.rerun()
    
    else:
        # Full problem
        st.markdown("**Lös själv:**")
        st.markdown(example['problem'])
        
        user_solution = st.text_area("Din kompletta lösning:")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("← Tillbaka"):
                st.session_state.fading_level = 1
                st.rerun()
        
        with col2:
            if st.button("Visa lösning"):
                with st.expander("Lösning"):
                    st.code(example['full'], language=example.get('language', 'text'))
        
        with col3:
            if user_solution and st.button("✅ Klar"):
                # Uppdatera progress
                update_learning_progress(concept['namn'], success=True)
                st.success("Bra jobbat!")
                del st.session_state.worked_example
                del st.session_state.show_worked_example
                st.rerun()


def generate_worked_example(concept: Dict) -> Dict:
    """Genererar worked example med olika fading-nivåer"""
    
    prompt = f"""Generera ett worked example för konceptet '{concept['namn']}'.

Inkludera:
1. Full lösning med alla steg förklarade
2. Delvis ifylld version (ta bort 30-40% av lösningen)
3. Bara problemformuleringen

Format som JSON:
{{
    "problem": "problemformulering",
    "full": "komplett lösning med förklaringar",
    "partial": "delvis lösning med ___ för saknade delar",
    "language": "python/math/text"
}}"""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        response = llm.query(prompt)
        
        import json
        return json.loads(response)
    except:
        # Fallback
        return {
            'problem': f"Tillämpa {concept['namn']} på ett konkret problem",
            'full': f"Steg 1: Identifiera...\nSteg 2: Applicera {concept['namn']}...\nSteg 3: Verifiera...",
            'partial': f"Steg 1: ___\nSteg 2: Applicera {concept['namn']}...\nSteg 3: ___",
            'language': 'text'
        }


def show_quick_test_section(concept: Dict):
    """Visar 2-minuters snabbtest"""
    
    st.markdown("### 2-minuters snabbtest")
    
    # Timer
    if 'test_start_time' not in st.session_state:
        st.session_state.test_start_time = datetime.now()
    
    elapsed = (datetime.now() - st.session_state.test_start_time).seconds
    remaining = max(0, 120 - elapsed)
    
    st.progress(1 - remaining/120)
    st.caption(f"Tid kvar: {remaining//60}:{remaining%60:02d}")
    
    # Initiera test
    if 'test_questions' not in st.session_state:
        st.session_state.test_questions = generate_micro_test_questions(concept)
        st.session_state.current_question = 0
        st.session_state.test_answers = []
    
    questions = st.session_state.test_questions
    current_q = st.session_state.current_question
    
    # Visa aktuell fråga
    if current_q < len(questions):
        st.markdown(f"**Fråga {current_q + 1} av {len(questions)}:**")
        st.info(questions[current_q]['question'])
        
        # Svarsområde
        answer = st.text_area(
            "Ditt svar:",
            key=f"quick_test_answer_{current_q}",
            height=100
        )
        
        if st.button("Nästa →", type="primary", disabled=not answer):
            # Spara svaret
            st.session_state.test_answers.append({
                'question': questions[current_q]['question'],
                'answer': answer,
                'expected': questions[current_q].get('answer', '')
            })
            
            # Gå till nästa fråga
            st.session_state.current_question += 1
            
            # Om testet är klart
            if st.session_state.current_question >= len(questions):
                # Evaluera alla svar
                correct_count = 0
                for i, ans in enumerate(st.session_state.test_answers):
                    is_correct = evaluate_micro_test_answer(
                        questions[i],
                        ans['answer'],
                        concept
                    )
                    if is_correct:
                        correct_count += 1
                
                # Uppdatera mastery
                success_rate = correct_count / len(questions)
                update_learning_progress(
                    concept['namn'],
                    success=success_rate > 0.5,
                    partial=success_rate == 0.5
                )
                
                # Visa resultat
                st.success(f"Test klart! Du fick {correct_count}/{len(questions)} rätt.")
                
                # Rensa test state
                del st.session_state.test_questions
                del st.session_state.current_question
                del st.session_state.test_answers
                del st.session_state.test_start_time
                st.session_state.show_quick_test = False
            
            st.rerun()
    else:
        # Ska inte komma hit, men säkerhetskontroll
        st.info("Testet är klart!")
        if st.button("Stäng test"):
            st.session_state.show_quick_test = False
            st.rerun()


def get_all_concepts_in_graph() -> List[Dict]:
    """Hämtar alla koncept från grafen för jämförelse"""
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (c:Koncept)
                RETURN c.namn as namn, c.beskrivning as beskrivning
                ORDER BY c.namn
            """)
            
            return [{'namn': record['namn'], 'beskrivning': record['beskrivning']} for record in result]
    except Exception as e:
        st.error(f"Fel vid hämtning av koncept: {str(e)}")
        return []


def generate_simpler_explanation(concept: Dict) -> str:
    """Genererar en enklare förklaring av konceptet"""
    
    prompt = f"""Förklara konceptet '{concept['namn']}' på ett mycket enkelt sätt.
    
Använd:
- Vardagliga ord istället för facktermer
- En konkret analogi från vardagen
- Max 3-4 meningar
- Språk som en 15-åring skulle förstå

Koncept: {concept.get('beskrivning', '')}"""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return f"{concept['namn']} är som... (förklaring genereras)"


def generate_comparison(concept1: str, concept2: str) -> str:
    """Genererar jämförelse mellan två koncept"""
    
    prompt = f"""Jämför koncepten '{concept1}' och '{concept2}'.

Förklara:
1. Vad de har gemensamt (1-2 punkter)
2. Hur de skiljer sig åt (2-3 punkter)
3. När man använder vilket (konkreta exempel)

Håll det kort och tydligt."""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return f"""**Likheter:**
- Båda är viktiga koncept inom ämnet

**Skillnader:**
- {concept1} fokuserar på...
- {concept2} används för...

**När använder man vilket:**
- Använd {concept1} när...
- Använd {concept2} när..."""


def generate_visualization(concept: Dict) -> str:
    """Genererar en visualisering av konceptet"""
    
    prompt = f"""Skapa en enkel ASCII-art visualisering eller diagram som illustrerar konceptet '{concept['namn']}'.

Konceptbeskrivning: {concept.get('beskrivning', '')}

Skapa något som:
- Är enkelt att förstå
- Visar nyckelaspekterna visuellt
- Använder ASCII-tecken för att rita
- Har förklarande text

Exempel på format:
```
    [Box 1] --> [Box 2]
       |           |
       v           v
    [Result]   [Output]
```"""
    
    try:
        from src.llm_service import LLMService
        llm = LLMService()
        return llm.query(prompt)
    except:
        return f"""```
{concept['namn']}
    |
    v
[Process]
    |
    v
[Result]
```

Visualisering av {concept['namn']} kommer här..."""


def generate_misconceptions(concept: Dict) -> str:
    """Genererar vanliga missförstånd om konceptet"""
    
    # Först, kolla om vi har FÖRVÄXLAS_MED relationer i grafen
    confused_with = get_confused_concepts(concept['namn'])
    
    if confused_with:
        # Vi har faktisk data om vad som förväxlas
        misconception_text = f"**Vanligt missförstånd:**\n\n"
        misconception_text += f"Många förväxlar {concept['namn']} med {confused_with[0]}.\n\n"
        
        # Generera förklaring om varför
        prompt = f"""Förklara varför studenter ofta förväxlar '{concept['namn']}' med '{confused_with[0]}'.

Inkludera:
1. Varför förväxlingen uppstår
2. Vad den kritiska skillnaden är
3. Ett minnesknep för att hålla isär dem"""
        
        try:
            from src.llm_service import LLMService
            llm = LLMService()
            explanation = llm.query(prompt)
            misconception_text += explanation
        except:
            misconception_text += "De liknar varandra men används i olika sammanhang."
        
        return misconception_text
    else:
        # Generera vanliga missförstånd baserat på konceptet
        prompt = f"""Lista 2-3 vanliga missförstånd om konceptet '{concept['namn']}'.

För varje missförstånd:
1. Vad folk ofta tror (felaktigt)
2. Vad som faktiskt är sant
3. Varför missförståndet uppstår

Koncept: {concept.get('beskrivning', '')}"""
        
        try:
            from src.llm_service import LLMService
            llm = LLMService()
            return llm.query(prompt)
        except:
            return f"""**Vanliga missförstånd om {concept['namn']}:**

1. **Missförstånd:** "Det är samma sak som..."
   **Sanning:** Det är faktiskt...
   
2. **Missförstånd:** "Man kan alltid..."
   **Sanning:** Det beror på..."""


if __name__ == "__main__":
    render()