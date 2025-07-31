"""
Analys-sida för Chalmers Knowledge Graph Builder
"""
import streamlit as st
import pandas as pd
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.session import init_session_state
from components.network_vis import NetworkVisualizer
from src.llm_service import LLMService
from config import LITELLM_MODEL


def render():
    """Renderar analyssidan"""
    init_session_state()
    
    st.markdown("### Analys")
    st.markdown("Analysera kurser och koncept i detalj")
    
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
    
    # Analysflikar
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "AI-insikter",
        "Kurslista", 
        "Konceptanalys", 
        "Kursberoenden",
        "Likhetsanalys"
    ])
    
    with tab1:
        render_ai_insights()
    
    with tab2:
        render_course_list()
    
    with tab3:
        render_concept_analysis()
    
    with tab4:
        render_course_dependencies()
    
    with tab5:
        render_similarity_analysis()


def render_course_list():
    """Renderar kurslistan"""
    st.markdown("#### Alla kurser i kunskapsgrafen")
    
    # Hämta kurslista
    df = st.session_state.neo4j_service.get_courses_list()
    
    if not df.empty:
        # Sökfunktion
        search = st.text_input("Sök kurser", placeholder="Sök på kurskod eller kursnamn...")
        
        if search:
            mask = (df['kurskod'].str.contains(search, case=False, na=False) | 
                   df['kursnamn'].str.contains(search, case=False, na=False))
            df = df[mask]
        
        # Visa statistik
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Antal kurser", len(df))
        with col2:
            avg_concepts = df['antal_koncept'].mean()
            st.metric("Genomsnitt koncept per kurs", f"{avg_concepts:.1f}")
        
        # Visa tabell
        st.dataframe(
            df[['kurskod', 'kursnamn', 'antal_koncept', 'koncept']],
            use_container_width=True,
            height=400
        )
        
        # Export
        csv = df.to_csv(index=False)
        st.download_button(
            label="Ladda ner som CSV",
            data=csv,
            file_name="kurslista.csv",
            mime="text/csv"
        )
    else:
        st.info("Inga kurser hittades i databasen")


def render_concept_analysis():
    """Renderar konceptanalys"""
    st.markdown("#### Konceptanalys")
    
    # Hämta konceptdata
    prereq_df, depends_df, all_df = st.session_state.neo4j_service.get_concept_dependencies()
    
    if not all_df.empty:
        # Välj koncept att analysera
        concepts = all_df['koncept'].tolist()
        selected_concept = st.selectbox(
            "Välj koncept att analysera",
            [""] + concepts,
            index=0
        )
        
        if selected_concept:
            # Hämta information om valt koncept
            concept_info = all_df[all_df['koncept'] == selected_concept].iloc[0]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Kurser som innehåller", len(concept_info['kurser']))
                if concept_info['kurser']:
                    st.markdown("**Kurser:**")
                    for course in concept_info['kurser']:
                        st.markdown(f"- {course}")
            
            with col2:
                st.metric("Förutsätter", concept_info['kräver_antal'])
                if concept_info['kräver']:
                    st.markdown("**Förutsätter:**")
                    for req in concept_info['kräver']:
                        st.markdown(f"- {req}")
            
            with col3:
                st.metric("Förutsätts av", concept_info['krävs_av_antal'])
                if concept_info['krävs_av']:
                    st.markdown("**Förutsätts av:**")
                    for dep in concept_info['krävs_av']:
                        st.markdown(f"- {dep}")
            
            # Visualisera konceptgrafen
            st.markdown("#### Konceptrelationer")
            
            graph_data = st.session_state.graph_utils.create_concept_graph(selected_concept)
            
            if graph_data['nodes']:
                visualizer = NetworkVisualizer()
                visualizer.display_graph(
                    nodes=graph_data['nodes'],
                    edges=graph_data['edges'],
                    height="400px",
                    physics_enabled=True,
                    custom_physics={
                        "solver": "barnesHut",
                        "barnesHut": {
                            "gravitationalConstant": -8000,
                            "centralGravity": 0.3,
                            "springLength": 120
                        }
                    },
                    key="concept_graph"
                )
            else:
                st.info("Inga relationer att visa för detta koncept")
        
        # Visa topplista
        st.markdown("#### Mest centrala koncept")
        
        importance_df = st.session_state.graph_utils.analyze_concept_importance()
        if not importance_df.empty:
            st.dataframe(
                importance_df.head(20),
                use_container_width=True,
                height=300
            )
    else:
        st.info("Inga koncept hittades i databasen")


def render_course_dependencies():
    """Renderar kursberoenden"""
    st.markdown("#### Kursberoenden")
    
    # Välj kurs
    courses = st.session_state.neo4j_service.get_all_courses()
    course_options = [f"{c['kurskod']} - {c['namn']}" for c in courses]
    
    selected = st.selectbox(
        "Välj kurs att analysera",
        [""] + course_options,
        index=0
    )
    
    if selected:
        kurskod = selected.split(" - ")[0]
        
        # Hämta beroenden
        dependencies = st.session_state.neo4j_service.get_course_dependencies(kurskod)
        
        if not dependencies.empty:
            st.markdown(f"**Kurser som {kurskod} bygger på:**")
            
            # Visa beroenden
            for _, dep in dependencies.iterrows():
                st.markdown(
                    f"- **{dep['kurskod']}** - {dep['kursnamn']} "
                    f"({dep['antal_koncept']} gemensamma koncept)"
                )
            
            # Visa inlärningsväg
            st.markdown("#### Rekommenderad inlärningsväg")
            path = st.session_state.graph_utils.find_learning_path(kurskod)
            
            for i, course in enumerate(path):
                if i < len(path) - 1:
                    st.markdown(f"{i+1}. {course} →")
                else:
                    st.markdown(f"{i+1}. **{course}** (målkurs)")
        else:
            st.info(f"Inga direkta beroenden hittades för {kurskod}")


def render_similarity_analysis():
    """Renderar likhetsanalys mellan kurser"""
    st.markdown("#### Likhetsanalys mellan kurser")
    
    # Välj kurser att jämföra
    courses = st.session_state.neo4j_service.get_all_courses()
    course_options = [f"{c['kurskod']} - {c['namn']}" for c in courses]
    
    col1, col2 = st.columns(2)
    
    with col1:
        kurs1 = st.selectbox(
            "Första kursen",
            [""] + course_options,
            index=0,
            key="similarity_course1"
        )
    
    with col2:
        kurs2 = st.selectbox(
            "Andra kursen",
            [""] + course_options,
            index=0,
            key="similarity_course2"
        )
    
    if kurs1 and kurs2 and kurs1 != kurs2:
        kurskod1 = kurs1.split(" - ")[0]
        kurskod2 = kurs2.split(" - ")[0]
        
        # Hämta likhetsdata
        similarity_df = st.session_state.neo4j_service.get_course_similarity()
        
        # Hitta likhet mellan valda kurser
        mask = ((similarity_df['kurs1'] == kurskod1) & (similarity_df['kurs2'] == kurskod2)) | \
               ((similarity_df['kurs1'] == kurskod2) & (similarity_df['kurs2'] == kurskod1))
        
        selected_similarity = similarity_df[mask]
        
        if not selected_similarity.empty:
            row = selected_similarity.iloc[0]
            
            # Visa likhetsmått
            st.metric(
                "Gemensamma koncept",
                row['gemensamma_koncept']
            )
            
            # Lista gemensamma koncept
            if row['koncept_lista']:
                st.markdown("**Gemensamma koncept:**")
                for koncept in row['koncept_lista']:
                    st.markdown(f"- {koncept}")
            
            # Visualisera jämförelsen
            st.markdown("#### Visuell jämförelse")
            
            graph_data = st.session_state.graph_utils.create_course_similarity_graph(kurskod1, kurskod2)
            
            if graph_data['nodes']:
                visualizer = NetworkVisualizer()
                visualizer.display_graph(
                    nodes=graph_data['nodes'],
                    edges=graph_data['edges'],
                    height="400px",
                    physics_enabled=False,
                    key="similarity_graph"
                )
                
                # Förklaring
                st.markdown("""
                **Förklaring:**
                - Blå = Första kursen
                - Grön = Andra kursen
                - Orange = Gemensamma koncept
                - Streckade linjer = Unika koncept
                """)
        else:
            st.info("Dessa kurser har inga gemensamma koncept")
    
    # Visa topplista över liknande kurser
    if st.checkbox("Visa mest liknande kurspar"):
        similarity_df = st.session_state.neo4j_service.get_course_similarity()
        
        if not similarity_df.empty:
            st.markdown("#### Mest liknande kurspar")
            
            # Formatera för visning
            display_df = similarity_df.head(20).copy()
            display_df['Kurspar'] = display_df.apply(
                lambda x: f"{x['kurs1']} ↔ {x['kurs2']}", axis=1
            )
            display_df['Koncept'] = display_df['koncept_lista'].apply(
                lambda x: ', '.join(x[:3]) + '...' if len(x) > 3 else ', '.join(x)
            )
            
            st.dataframe(
                display_df[['Kurspar', 'gemensamma_koncept', 'Koncept']],
                use_container_width=True,
                height=400
            )


def render_ai_insights():
    """Renderar AI-insikter om kunskapsgrafen"""
    st.markdown("#### AI-insikter om kunskapsgrafen")
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    # Hämta grafstatistik
    stats = st.session_state.neo4j_service.get_graph_statistics()
    
    if stats['total_nodes'] == 0:
        st.warning("Kunskapsgrafen är tom. Bygg först en graf genom att lägga till kurser.")
        return
    
    # Visa aktuell grafstatus
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Kurser", stats['courses'])
    with col2:
        st.metric("Koncept", stats['concepts'])
    with col3:
        st.metric("Relationer", stats['relations'])
    with col4:
        st.metric("Totala noder", stats['total_nodes'])
    
    # Fördefinierade analysfrågor
    st.markdown("#### Välj analysfråga")
    
    analysis_options = {
        "Progression och struktur": "Analysera kursprogressionen och strukturen i grafen. Är kurserna ordnade på ett logiskt sätt? Bygger senare kurser på tidigare kurser på ett vettigt sätt?",
        "Konceptspridning": "Vilka koncept är mest centrala i utbildningen? Finns det koncept som förekommer i många kurser? Är det några viktiga koncept som saknas?",
        "Kursberoenden": "Analysera hur väl kurserna bygger på varandra. Finns det kurser som borde ha fler förutsättningar? Är några kurser isolerade?",
        "Utbildningshelhet": "Ge en övergripande analys av utbildningen. Täcker kurserna tillsammans ett sammanhängande kunskapsområde? Finns det luckor?",
        "Förbättringsförslag": "Baserat på grafen, vilka förbättringar skulle kunna göras i kursupplägget? Vilka kurser eller koncept saknas?"
    }
    
    selected_analysis = st.selectbox(
        "Välj typ av analys",
        list(analysis_options.keys())
    )
    
    # Initiera session state för AI-analys
    if 'ai_analysis_generated' not in st.session_state:
        st.session_state.ai_analysis_generated = False
    if 'ai_analysis_result' not in st.session_state:
        st.session_state.ai_analysis_result = None
    
    # Kontrollera om LiteLLM är konfigurerad
    from config import LITELLM_API_KEY, LITELLM_BASE_URL
    
    if not LITELLM_API_KEY or not LITELLM_BASE_URL:
        st.warning("LiteLLM API är inte konfigurerad - AI-analys är inte tillgänglig")
        st.markdown("""
        För att aktivera AI-analys, lägg till följande i din `.env` fil:
        ```
        LITELLM_API_KEY=din_api_nyckel
        LITELLM_BASE_URL=din_base_url
        LITELLM_MODEL=anthropic/claude-sonnet-3.7
        ```
        """)
        return
    
    # Generera endast vid knapptryck
    if st.button("Generera AI-analys", type="primary"):
        with st.spinner("AI analyserar kunskapsgrafen..."):
            try:
                # Hämta hela grafen
                graph_json = st.session_state.neo4j_service.get_existing_graph_as_json()
                
                # Bygg prompt
                prompt = f"""
Analysera följande kunskapsgraf från ett utbildningsprogram på Chalmers.

ANALYSFRÅGA: {analysis_options[selected_analysis]}

KUNSKAPSGRAF:
{graph_json}

Ge en djupgående analys på svenska. Var konkret och ge specifika exempel från grafen.
Strukturera ditt svar med tydliga rubriker.
"""
                
                # Anropa LLM
                llm_service = LLMService()
                
                from litellm import completion
                response = completion(
                    model=llm_service.model,
                    messages=[
                        {"role": "system", "content": "Du är en expert på utbildningsanalys och kursplanering på Chalmers tekniska högskola."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    api_key=llm_service.api_key,
                    base_url=llm_service.base_url
                )
                
                analysis = response.choices[0].message.content
                
                # Spara i session state
                st.session_state.ai_analysis_generated = True
                st.session_state.ai_analysis_result = analysis
                
            except Exception as e:
                st.error(f"Fel vid AI-analys: {str(e)}")
    
    # Visa sparad analys om den finns
    if st.session_state.ai_analysis_result:
        st.markdown("### AI-analys")
        st.markdown(st.session_state.ai_analysis_result)
        
        # Möjlighet att spara analysen
        st.download_button(
            label="Ladda ner analys som textfil",
            data=st.session_state.ai_analysis_result,
            file_name=f"ai_analys_{selected_analysis.lower().replace(' ', '_')}.txt",
            mime="text/plain"
        )
    
    # Egen fråga
    with st.expander("Ställ egen fråga till AI"):
        custom_question = st.text_area(
            "Skriv din fråga om kunskapsgrafen",
            placeholder="T.ex. Vilka kurser innehåller flest matematiska koncept?"
        )
        
        if custom_question and st.button("Analysera egen fråga"):
            with st.spinner("AI analyserar..."):
                try:
                    # Hämta grafen
                    graph_json = st.session_state.neo4j_service.get_existing_graph_as_json()
                    
                    # Bygg prompt
                    prompt = f"""
Svara på följande fråga om kunskapsgrafen från ett utbildningsprogram på Chalmers.

FRÅGA: {custom_question}

KUNSKAPSGRAF:
{graph_json}

Svara konkret och basera ditt svar på informationen i grafen.
"""
                    
                    # Anropa LLM
                    llm_service = LLMService()
                    
                    from litellm import completion
                    response = completion(
                        model=llm_service.model,
                        messages=[
                            {"role": "system", "content": "Du är en hjälpsam assistent som analyserar kunskapsgrafer från Chalmers."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        api_key=llm_service.api_key,
                        base_url=llm_service.base_url
                    )
                    
                    answer = response.choices[0].message.content
                    
                    st.markdown("### AI-svar")
                    st.markdown(answer)
                    
                except Exception as e:
                    st.error(f"Fel vid AI-analys: {str(e)}")


if __name__ == "__main__":
    render()