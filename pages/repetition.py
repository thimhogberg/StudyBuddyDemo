"""
Repetition page - Spaced repetition för memorering av koncept
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from services.memory_service import MemoryService
import json

def show_repetition_page():
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

    # Initialize memory service
    if 'memory_service' not in st.session_state:
        st.session_state.memory_service = MemoryService(st.session_state.neo4j_service)
    
    memory_service = st.session_state.memory_service
    
    # Introduktionstext
    st.markdown("### Repetera")
    st.markdown("Använd vetenskapligt beprövad spaced repetition för att memorera koncept långsiktigt")

    # Tabs för olika vyer
    tab1, tab2, tab3, tab4 = st.tabs(["Repetera nu", "Översikt", "Anpassa din inlärning", "Hur det fungerar"])
    
    with tab1:
        show_review_tab(memory_service)
    
    with tab2:
        show_overview_tab(memory_service)
    
    with tab3:
        show_personalization_tab(memory_service)
    
    with tab4:
        show_explanation_tab()

def show_review_tab(memory_service):
    """Visar koncept som behöver repeteras"""
    
    # Hämta alla kurser med koncept
    courses_concepts = memory_service.get_concepts_by_course()
    
    if not courses_concepts:
        st.info("Inga koncept har lagts till ännu. Bygg grafen för dina kurser först!")
        return
    
    # Kursfilter
    course_options = ["Alla kurser"] + list(courses_concepts.keys())
    selected_course = st.selectbox("Välj kurs att repetera", course_options)
    
    # Hämta koncept som behöver repeteras
    if selected_course == "Alla kurser":
        due_concepts = memory_service.get_due_concepts()
    else:
        due_concepts = memory_service.get_due_concepts(course_filter=selected_course)
    
    if not due_concepts:
        st.success("Bra jobbat! Du har inga koncept som behöver repeteras just nu.")
        
        # Visa nästa repetition
        next_review = memory_service.get_next_review_time()
        if next_review:
            st.info(f"Nästa repetition: {next_review['concept']} om {next_review['time_until']}")
    else:
        st.info(f"Du har {len(due_concepts)} koncept att repetera")
        
        # Välj ett koncept att repetera
        if 'current_concept_idx' not in st.session_state:
            st.session_state.current_concept_idx = 0
        
        if st.session_state.current_concept_idx < len(due_concepts):
            concept = due_concepts[st.session_state.current_concept_idx]
            
            # Visa koncept
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader(concept['name'])
                course_code = concept.get('course') or 'Okänd kurs'
                st.markdown(f"**Kurs:** {course_code}")
                
                # Visa senaste försök
                if concept.get('last_review'):
                    last_date = datetime.fromisoformat(concept['last_review'])
                    days_ago = (datetime.now() - last_date).days
                    st.caption(f"Senast repeterad: {days_ago} dagar sedan")
            
            with col2:
                retention = concept.get('retention')
                if retention is None:
                    retention = 1.0
                difficulty = concept.get('difficulty')
                if difficulty is None:
                    difficulty = 0.3
                st.metric("Retention", f"{retention:.0%}")
                st.metric("Svårighetsgrad", f"{difficulty:.2f}")
            
            # Visa fråga direkt
            st.markdown("---")
            st.markdown(f"### Förklara {concept['name']}")
            
            # Visa svar (dold först)
            with st.expander("Visa svar"):
                # Använd beskrivningen direkt från koncept-noden
                description = concept.get('description') or f"{concept['name']} är ett viktigt koncept inom {course_code}."
                st.markdown(description)
                
                # Självbedömning
                st.markdown("---")
                st.markdown("**Hur bra kunde du svaret?**")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button("Glömt helt", key="forgot"):
                        record_response(memory_service, concept, 0)
                
                with col2:
                    if st.button("Svårt", key="hard"):
                        record_response(memory_service, concept, 1)
                
                with col3:
                    if st.button("Okej", key="good"):
                        record_response(memory_service, concept, 2)
                
                with col4:
                    if st.button("Lätt", key="easy"):
                        record_response(memory_service, concept, 3)
        else:
            st.success("Du har repeterat alla koncept för denna session!")
            if st.button("Börja om"):
                st.session_state.current_concept_idx = 0
                st.rerun()

def record_response(memory_service, concept, quality):
    """Registrerar användarens svar och uppdaterar memory curve"""
    memory_service.record_review(concept['id'], quality)
    st.session_state.current_concept_idx += 1
    st.rerun()

def show_overview_tab(memory_service):
    """Visar översikt över alla koncept och när de behöver repeteras"""
    st.header("Repetitionsöversikt")
    
    # Hämta alla koncept grupperade per kurs
    courses_concepts = memory_service.get_concepts_by_course()
    
    if not courses_concepts:
        st.info("Inga koncept har lagts till ännu. Bygg grafen för dina kurser först!")
        return
    
    # Visa statistik
    col1, col2, col3, col4 = st.columns(4)
    
    total_concepts = sum(len(concepts) for concepts in courses_concepts.values())
    due_today = len(memory_service.get_due_concepts())
    avg_retention = memory_service.get_average_retention()
    streak = memory_service.get_streak_days()
    
    with col1:
        st.metric("Totalt antal koncept", total_concepts)
    
    with col2:
        st.metric("Att repetera idag", due_today)
    
    with col3:
        st.metric("Genomsnittlig retention", f"{avg_retention:.0%}")
    
    with col4:
        st.metric("Daglig streak", f"{streak} dagar")
    
    # Visa koncept per kurs
    st.markdown("---")
    st.subheader("Koncept per kurs")
    
    for course_code, concepts in courses_concepts.items():
        with st.expander(f"{course_code} ({len(concepts)} koncept)"):
            # Skapa DataFrame för koncepten
            df_data = []
            for concept in concepts:
                next_review = concept.get('next_review')
                if next_review:
                    next_date = datetime.fromisoformat(next_review)
                    days_until = (next_date - datetime.now()).days
                    status = "Försenad" if days_until < 0 else f"Om {days_until} dagar"
                else:
                    status = "Ej schemalagd"
                
                df_data.append({
                    'Koncept': concept['name'],
                    'Retention': f"{(concept.get('retention') if concept.get('retention') is not None else 1.0):.0%}",
                    'Nästa repetition': status,
                    'Antal repetitioner': concept.get('review_count', 0)
                })
            
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)
    
    # Visa kalendervy
    st.markdown("---")
    st.subheader("Repetitionskalender")
    
    # Hämta repetitioner för kommande 30 dagar
    calendar_data = memory_service.get_calendar_view(days=30)
    
    if calendar_data:
        # Skapa kalendervisualisering
        fig = go.Figure()
        
        dates = []
        counts = []
        
        for date_str, count in calendar_data.items():
            dates.append(datetime.fromisoformat(date_str))
            counts.append(count)
        
        fig.add_trace(go.Bar(
            x=dates,
            y=counts,
            text=counts,
            textposition='auto',
            marker_color='lightblue'
        ))
        
        fig.update_layout(
            title="Antal koncept att repetera per dag",
            xaxis_title="Datum",
            yaxis_title="Antal koncept",
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)

def show_personalization_tab(memory_service):
    """Låter användaren anpassa sin inlärningskurva"""
    st.header("Anpassa din inlärning")
    
    st.markdown("""
    Din inlärningskurva anpassas automatiskt baserat på dina resultat, 
    men du kan också göra manuella justeringar här.
    """)
    
    # Hämta användarens profil
    profile = memory_service.get_user_profile()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Din inlärningsprofil")
        
        # Visa nuvarande parametrar
        learning_rate = profile.get('learning_rate')
        if learning_rate is None:
            learning_rate = 1.0
        forgetting_factor = profile.get('forgetting_factor')
        if forgetting_factor is None:
            forgetting_factor = 0.3
        avg_difficulty = profile.get('avg_difficulty')
        if avg_difficulty is None:
            avg_difficulty = 0.5
            
        st.metric("Inlärningshastighet", f"{learning_rate:.2f}")
        st.metric("Glömskefaktor", f"{forgetting_factor:.2f}")
        st.metric("Genomsnittlig svårighetsgrad", f"{avg_difficulty:.2f}")
        
        # Justera parametrar
        st.markdown("---")
        st.markdown("**Justera parametrar**")
        
        new_learning_rate = st.slider(
            "Inlärningshastighet",
            min_value=0.5,
            max_value=2.0,
            value=profile.get('learning_rate') if profile.get('learning_rate') is not None else 1.0,
            step=0.1,
            help="Högre värde = snabbare inlärning men risk för överdriven självsäkerhet"
        )
        
        new_forgetting_factor = st.slider(
            "Glömskefaktor",
            min_value=0.1,
            max_value=0.5,
            value=profile.get('forgetting_factor') if profile.get('forgetting_factor') is not None else 0.3,
            step=0.05,
            help="Högre värde = snabbare glömska, kräver mer frekvent repetition"
        )
        
        if st.button("Spara ändringar"):
            memory_service.update_user_profile({
                'learning_rate': new_learning_rate,
                'forgetting_factor': new_forgetting_factor
            })
            st.success("Profil uppdaterad!")
            st.rerun()
    
    with col2:
        st.subheader("Din statistik")
        
        # Visa användarstatistik
        avg_retention = memory_service.get_average_retention()
        streak = memory_service.get_streak_days()
        
        st.metric("Genomsnittlig retention", f"{avg_retention:.0%}")
        st.metric("Daglig streak", f"{streak} dagar")
        
        st.markdown("---")
        st.markdown("""
        **Tips för bättre inlärning:**
        
        - Repetera varje dag för att bygga en streak
        - Var ärlig med dina svar för bättre anpassning
        - Fokusera på förståelse, inte memorering
        - Ta pauser mellan repetitionssessioner
        """)
        
        # Visa personlig glömskekurva baserad på faktisk data
        st.markdown("---")
        st.subheader("Din glömskekurva")
        
        fig = go.Figure()
        
        # Visa teoretisk glömskekurva med användarens parametrar
        x = np.linspace(0, 30, 100)
        y = np.exp(-profile.get('forgetting_factor', 0.3) * x / 5)
        
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines',
            name='Din beräknade kurva',
            line=dict(color='blue', width=2)
        ))
        
        # Visa genomsnittlig kurva som jämförelse
        y_avg = np.exp(-0.3 * x / 5)
        fig.add_trace(go.Scatter(
            x=x,
            y=y_avg,
            mode='lines',
            name='Genomsnittlig kurva',
            line=dict(color='gray', width=1, dash='dash')
        ))
        
        fig.update_layout(
            title="Hur snabbt du glömmer information",
            xaxis_title="Dagar sedan inlärning",
            yaxis_title="Retention (%)",
            yaxis=dict(tickformat='.0%'),
            showlegend=True,
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)


def show_explanation_tab():
    """Förklarar hur spaced repetition fungerar"""
    st.header("Så fungerar Spaced Repetition")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### Glömskekurvan (Ebbinghaus Forgetting Curve)
        
        Hermann Ebbinghaus upptäckte att vi glömmer information enligt en förutsägbar kurva.
        Utan repetition glömmer vi upp till 90% av det vi lärt oss inom en vecka.
        
        **Matematisk modell:**
        
        Retention (R) över tid (t) beskrivs av:
        
        $$R(t) = e^{-t/S}$$
        
        Där:
        - R(t) = Sannolikheten att minnas vid tid t
        - t = Tid sedan senaste repetition (dagar)
        - S = Styrkan av minnet (ökar vid varje repetition)
        
        ### Spaced Repetition Algorithm (SM-2 variant)
        
        Vi använder en modifierad version av SuperMemo SM-2 algoritmen:
        
        1. **Initial interval**: 1 dag
        2. **Vid korrekt svar**: Nytt intervall = Gammalt intervall × Ease Factor
        3. **Ease Factor** justeras baserat på svårighetsgrad (1.3 - 2.5)
        
        ### Individanpassning
        
        Systemet anpassar sig till din personliga inlärningshastighet genom att:
        
        - **Spåra din prestation**: Analyserar hur väl du minns olika typer av koncept
        - **Justera svårighetsgrad**: Koncept du har svårt för visas oftare
        - **Optimera intervaller**: Använder SM-2 algoritmen för att beräkna nästa repetition
        - **Personliga parametrar**: Justerar ease factor och intervaller baserat på dina svar
        
        ### Varför det fungerar
        
        1. **Aktiv återkallning**: Stärker neurala kopplingar
        2. **Optimal timing**: Repeterar precis innan du glömmer
        3. **Effektivitet**: Minimerar tid samtidigt som retention maximeras
        4. **Långtidsminne**: Flyttar gradvis information från korttids- till långtidsminne
        
        ### Systemets parametrar förklarade
        
        **Retention (Minnesbehållning)**
        - Visar hur stor del av informationen du fortfarande minns (0-100%)
        - Sjunker exponentiellt med tiden enligt glömskekurvan
        - Vid 100% minns du allt, vid 0% har du glömt helt
        
        **Difficulty (Svårighetsgrad)**
        - Ett värde mellan 0.1 och 0.9 som anger hur svårt konceptet är för dig
        - Börjar på 0.3 (normalsvårt) för alla koncept
        - Ökar när du svarar "Glömt helt" eller "Svårt"
        - Minskar när du svarar "Lätt"
        - Påverkar hur ofta konceptet dyker upp för repetition
        
        **Interval (Repetitionsintervall)**
        - Antal dagar till nästa schemalagda repetition
        - Börjar på 1 dag för nya koncept
        - Ökar exponentiellt vid korrekta svar (1 → 3 → 7 → 14 → 30 dagar osv)
        - Återställs till 1 dag om du glömt helt
        
        **Ease Factor (Lätthetsfaktor)**
        - En multiplikator som bestämmer hur snabbt intervallet växer
        - Värde mellan 1.3 (svårt koncept) och 2.8 (lätt koncept)
        - Standard är 2.5
        - Justeras baserat på dina svar över tid
        - Formel: Nytt intervall = Gammalt intervall × Ease Factor
        
        **Review Count (Antal repetitioner)**
        - Räknar hur många gånger du har repeterat konceptet
        - Hjälper systemet att spåra din långsiktiga prestation
        
        **Last Review / Next Review**
        - Last Review: Datum för senaste repetition
        - Next Review: Datum för nästa schemalagda repetition
        - Används för att beräkna när koncept ska visas igen
        
        **Learning Rate (Inlärningshastighet)**
        - Din personliga parameter som justerar hur snabbt du lär dig
        - Standard är 1.0
        - Högre värde = du lär dig snabbare, längre intervaller
        - Lägre värde = du behöver mer repetition, kortare intervaller
        
        **Forgetting Factor (Glömskefaktor)**
        - Hur snabbt du glömmer information (standard 0.3)
        - Högre värde = snabbare glömska
        - Används i formeln: R(t) = e^(-glömskefaktor × tid)
        - Kan kalibreras genom minnestester
        """)
    
    with col2:
        # Visa interaktiv glömskekurva
        st.markdown("### Interaktiv demonstration")
        
        # Sliders för att justera parametrar
        initial_strength = st.slider("Initial minnesstyrka", 1, 10, 5)
        forgetting_rate = st.slider("Glömskehastighet", 0.1, 1.0, 0.3)
        
        # Generera kurva
        days = np.linspace(0, 30, 100)
        retention = np.exp(-forgetting_rate * days / initial_strength)
        
        # Skapa figur
        fig = go.Figure()
        
        # Lägg till glömskekurva
        fig.add_trace(go.Scatter(
            x=days,
            y=retention,
            mode='lines',
            name='Utan repetition',
            line=dict(color='red', width=2)
        ))
        
        # Lägg till kurva med repetitioner
        rep_days = [0, 1, 3, 7, 14, 30]
        rep_retention = []
        current_strength = initial_strength
        
        for i, day in enumerate(days):
            # Kolla om det är dags för repetition
            for rep_day in rep_days:
                if abs(day - rep_day) < 0.1 and rep_day > 0:
                    current_strength *= 1.5  # Öka styrkan vid repetition
            
            ret = np.exp(-forgetting_rate * (day - max([d for d in rep_days if d <= day])) / current_strength)
            rep_retention.append(ret)
        
        fig.add_trace(go.Scatter(
            x=days,
            y=rep_retention,
            mode='lines',
            name='Med spaced repetition',
            line=dict(color='green', width=2)
        ))
        
        # Markera repetitionspunkter
        for rep_day in rep_days[1:]:
            fig.add_vline(x=rep_day, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            title="Effekten av Spaced Repetition",
            xaxis_title="Dagar",
            yaxis_title="Retention (%)",
            yaxis=dict(tickformat='.0%'),
            showlegend=True,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Visa fördelar
        st.markdown("""
        ### Fördelar med Spaced Repetition
        
        - **90% retention** efter 1 år  
        - **80% mindre tid** än traditionellt pluggande  
        - **Mindre stress** före tentor  
        - **Djupare förståelse** av materialet  
        """)

# Kör sidan om den laddas direkt
if __name__ == "__main__":
    show_repetition_page()