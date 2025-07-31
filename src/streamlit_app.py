"""
Streamlit-app för Chalmers Course Graph
"""
import streamlit as st
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.course_parser import CourseParser
from src.graph_builder import GraphBuilder
from services.graph_utils import GraphUtils
from services.neo4j_service import Neo4jService


def main():
    st.set_page_config(
        page_title="StudyBuddy Studio",
        page_icon="🏔️",
        layout="wide"
    )
    
    st.title("StudyBuddy Studio")
    st.markdown("AI-drivet individualiserat lärande med interaktiva kunskapsgrafer för Chalmers-kurser")
    
    # Guide section
    with st.expander("Snabbguide"):
        st.markdown("""
        **1. Bygg graf** → Välj program och kurser → AI extraherar koncept → Kunskapsgraf skapas  
        **2. Graf** → Utforska interaktivt → Filtrera på kurser/koncept → Mastery-visualisering  
        **3. Analys** → AI analyserar programstruktur → Identifierar kunskapsluckor → Förbättringsförslag  
        **4. Progression** → Se din kunskapsutveckling → Visuella grafer → Manuell justering (utvecklarläge)  
        **5. Teori** → Pedagogisk bakgrund → Vetenskaplig grund → Forskningsreferenser  
        **6. Inställningar** → Se och anpassa AI-prompts → Generera demo-data → Systemkonfiguration  
        **7. Smart träning** → Optimeringsalgoritm väljer koncept → AI-genererade uppgifter → Maximerar lärande per tidsenhet  
        **8. Studera** → Välj studieväg → AI leder dig genom koncept → Sokratisk dialog/Guidat/Bedömning
        
        *Notera: Smart träning och Studera är två olika studielägen med olika pedagogiska ansatser i denna POC*  
        **9. Repetera** → Spaced repetition → SM-2 algoritm → Långsiktig inlärning  
        **10. Canvas** → Synka med Canvas LMS → Hämta kurser, moduler, filer → Chatta med kursmaterial  
        **11. Deadlines** → Se kommande uppgifter → Kalenderöversikt → Håll koll på alla inlämningar  
        **12. Alumn** → Karriärvägar → Jobbannonsmatchning → Kompetens-gap → Matchning (demo)
        
        **Visualisering:** 
        - Kurser (röda noder)
        - Koncept (färg baserat på mastery: röd=låg, gul=medium, grön=hög)
        - Relationer (grön=innehåller, orange=förutsätter)
        - Transparens visar mastery-nivå
        """)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**AI-stöd:** Individuell handledning anpassad efter din kunskapsnivå")
        with col2:
            st.success("**Mastery Learning:** Behärska koncept innan du går vidare")
        with col3:
            st.warning("**Kunskapsgrafer:** Visualiserar hur allt hänger ihop")
    
    # Initiera komponenter
    if 'parser' not in st.session_state:
        st.session_state.parser = CourseParser()
    if 'graph_builder' not in st.session_state:
        st.session_state.graph_builder = GraphBuilder()
    if 'neo4j' not in st.session_state:
        st.session_state.neo4j = Neo4jService()
    if 'neo4j_service' not in st.session_state:  # För kompatibilitet med graph.py
        st.session_state.neo4j_service = st.session_state.neo4j
    if 'graph_utils' not in st.session_state:
        st.session_state.graph_utils = GraphUtils(st.session_state.neo4j)
    if 'graph_filter' not in st.session_state:
        st.session_state.graph_filter = "Alla noder"
    if 'selected_node' not in st.session_state:
        st.session_state.selected_node = None
    
    # Sidebar är nu tom
    
    # Skapa flikar - Smart träning kommer efter Inställningar
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
        "Bygg graf", "Graf", "Analys", "Progression", "Teori", "Inställningar",
        "Smart träning", "Studera", "Repetera", "Canvas", "Deadlines", "Alumn"
    ])
    
    # Lazy loading - importera och rendera endast när fliken är aktiv
    with tab1:
        render_courses_tab()
    
    with tab2:
        if 'tab2_loaded' not in st.session_state:
            st.session_state.tab2_loaded = True
        from pages.graph import render
        render()
    
    with tab3:
        if 'tab3_loaded' not in st.session_state:
            st.session_state.tab3_loaded = True
        from pages.analytics import render as render_analytics
        render_analytics()
    
    with tab4:
        if 'tab4_loaded' not in st.session_state:
            st.session_state.tab4_loaded = True
        from pages.progression import render as render_progression
        render_progression()
    
    with tab5:
        if 'tab5_loaded' not in st.session_state:
            st.session_state.tab5_loaded = True
        from pages.theory import render as render_theory
        render_theory()
    
    with tab6:
        if 'tab6_loaded' not in st.session_state:
            st.session_state.tab6_loaded = True
        from pages.settings import render as render_settings
        render_settings()
    
    with tab7:
        if 'tab7_loaded' not in st.session_state:
            st.session_state.tab7_loaded = True
        from pages.smart_training import render as render_smart_training
        render_smart_training()
    
    with tab8:
        if 'tab8_loaded' not in st.session_state:
            st.session_state.tab8_loaded = True
        from pages.study import render as render_study
        render_study()
    
    with tab9:
        if 'tab9_loaded' not in st.session_state:
            st.session_state.tab9_loaded = True
        from pages.repetition import show_repetition_page
        show_repetition_page()
    
    with tab10:
        if 'tab10_loaded' not in st.session_state:
            st.session_state.tab10_loaded = True
        from pages.canvas import render as render_canvas
        render_canvas()
    
    with tab11:
        if 'tab11_loaded' not in st.session_state:
            st.session_state.tab11_loaded = True
        from pages.deadlines import render as render_deadlines
        render_deadlines()
    
    with tab12:
        if 'tab12_loaded' not in st.session_state:
            st.session_state.tab12_loaded = True
        from pages.alumn import render as render_alumn
        render_alumn()


def render_courses_tab():
    """Renderar kursfliken"""
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
    
    # Programval i två kolumner
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.header("Välj program")
        
        programs = st.session_state.parser.get_programs()
        
        if programs and len(programs) > 0:
            # programs är nu en lista av tupler (programkod, programnamn med kod)
            try:
                program_options = [name for code, name in programs]
                program_codes = [code for code, name in programs]
            except ValueError as e:
                st.error(f"Fel vid uppackning av program: {e}")
                st.write(f"Första programmet: {programs[0]}")
                st.session_state.selected_program_code = None
                return
            
            # Sökruta för program
            search_term = st.text_input(
                "Sök program (engelskt namn):",
                placeholder="Skriv programnamn eller kod...",
                key="program_search",
                help="Sök efter program genom att skriva del av namnet eller programkoden"
            )
            
            # Filtrera program baserat på sökterm
            if search_term:
                filtered_indices = []
                filtered_options = []
                filtered_codes = []
                
                for idx, (code, name) in enumerate(programs):
                    if search_term.lower() in name.lower() or search_term.lower() in code.lower():
                        filtered_indices.append(idx)
                        filtered_options.append(name)
                        filtered_codes.append(code)
                
                if filtered_options:
                    # Visa antal träffar
                    st.caption(f"Visar {len(filtered_options)} av {len(programs)} program")
                    
                    selected_index = st.selectbox(
                        "Program:",
                        range(len(filtered_options)),
                        format_func=lambda x: filtered_options[x],
                        help="Välj ett program för att se dess kurser",
                        key="main_program_selector"  # Unik nyckel
                    )
                    
                    st.session_state.selected_program_code = filtered_codes[selected_index]
                else:
                    st.warning(f"Inga program matchar sökningen '{search_term}'")
                    st.session_state.selected_program_code = None
            else:
                # Visa alla program om ingen sökning
                selected_index = st.selectbox(
                    "Program:",
                    range(len(program_options)),
                    format_func=lambda x: program_options[x],
                    help="Välj ett program för att se dess kurser",
                    key="main_program_selector"  # Unik nyckel
                )
                
                st.session_state.selected_program_code = program_codes[selected_index]
        else:
            st.warning("Inga program hittades")
            st.session_state.selected_program_code = None
        
        # Inställningar
        st.divider()
        st.subheader("Inställningar")
        
        # Max antal koncept per kurs
        st.session_state.max_concepts = st.number_input(
            "Max antal koncept per kurs",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            help="Maximalt antal koncept som ska extraheras per kurs. Obs: Om koncept redan finns i grafen räknas de inte mot denna gräns."
        )
        
        # Språkval
        st.session_state.language = st.selectbox(
            "Språk för analys",
            ["Svenska", "Engelska"],
            index=0,
            help="Välj vilket språk AI ska använda för att analysera kurser och generera koncept"
        )
        
        # Visa grafstatistik
        st.divider()
        st.subheader("Grafstatistik")
        stats = st.session_state.neo4j.get_graph_statistics()
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric("Kurser", stats['courses'])
            st.metric("Koncept", stats['concepts'])
        with metric_col2:
            st.metric("Relationer", stats['relations'])
            st.metric("Totala noder", stats['total_nodes'])
        
        # Grafhantering
        st.divider()
        if st.button("Rensa hela grafen", type="secondary", key="clear_graph_button"):
            st.session_state.graph_builder.clear_graph()
            st.rerun()
    
    # Hämta valt program från session state
    selected_program_code = st.session_state.get('selected_program_code', None)
    
    # Huvudinnehåll i höger kolumn
    with col_right:
        if selected_program_code:
            # Hämta kurser för valt program
            courses_df = st.session_state.parser.get_courses_by_program(selected_program_code)
        
            if not courses_df.empty:
                # Visa översikt
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Antal kurser", len(courses_df))
                with col2:
                    # Räkna obligatoriska kurser
                    mandatory_courses = len(courses_df[courses_df['rule'] == 'O'])
                    st.metric("Obligatoriska kurser", mandatory_courses)
                with col3:
                    total_credits = courses_df['credit'].str.replace(',', '.').astype(float).sum()
                    st.metric("Total möjlig poäng", f"{total_credits:.1f} HP")
                with col4:
                    if st.button("Bygg graf för valda kurser", type="primary", key="build_graph_tab1"):
                        build_program_graph_with_selection(selected_program_code, courses_df)
            
                # Visa kurser grupperade per år
                st.divider()
                st.header("Kurser i programmet")
                
                # Skapa container för kursval om valbara kurser finns
                if courses_df['rule'].isin(['V', 'X', 'F', 'OV']).any():
                    st.info("Välj vilka valbara kurser som ska inkluderas i grafen. Obligatoriska kurser (O) är alltid inkluderade.")
                
                for year in sorted(courses_df['year'].unique()):
                    st.subheader(f"År {year}")
                    year_courses = courses_df[courses_df['year'] == year]
                    
                    # Gruppera per läsperiod
                    for period in sorted(year_courses['period_num'].unique()):
                        if period > 0:  # Hoppa över kurser utan period
                            period_courses = year_courses[year_courses['period_num'] == period]
                            
                            st.markdown(f"**Läsperiod {period}**")
                            
                            for _, course in period_courses.iterrows():
                                # Skapa unik nyckel för varje kurs
                                course_key = f"tab1_select_{course['courseCode']}"
                                
                                # Visa kurs med checkbox för valbara kurser
                                col1, col2 = st.columns([1, 20])
                                
                                with col1:
                                    if course['rule'] == 'O':
                                        # Obligatorisk kurs - alltid vald
                                        st.markdown("✓")
                                        is_selected = True
                                    else:
                                        # Valbar kurs (V, X, etc) - checkbox
                                        is_selected = st.checkbox(
                                            "Välj",
                                            key=course_key,
                                            value=False,
                                            label_visibility="hidden"
                                        )
                                
                                with col2:
                                    if course['rule'] == 'O':
                                        rule_text = "Obligatorisk"
                                        rule_color = "green"
                                    elif course['rule'] == 'V':
                                        rule_text = "Valbar kurs"
                                        rule_color = "blue"
                                    elif course['rule'] == 'X':
                                        rule_text = "Examensarbete"
                                        rule_color = "purple"
                                    elif course['rule'] == 'F':
                                        rule_text = "Fristående kurs"
                                        rule_color = "orange"
                                    else:
                                        rule_text = f"Regel: {course['rule']}"
                                        rule_color = "orange"
                                    
                                    # Visa svenskt namn först, engelskt under
                                    with st.expander(
                                        f"{course['courseCode']} - {course['nameAlt']} ({course['credit']} HP) - :{rule_color}[{rule_text}]"
                                    ):
                                        st.markdown(f"**Engelskt namn:** {course['name']}")
                                        show_course_details(course)
            else:
                st.warning(f"Inga kurser hittades för valt program")
        else:
            st.info("Välj ett program från vänstra panelen för att börja")


def show_course_details(course):
    """Visar detaljerad kursinformation"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"**Regel:** {course.get('rule', 'N/A')} (O=Obligatorisk, V=Valbar)")
        
        if course.get('purpose'):
            st.markdown("**Syfte:**")
            st.markdown(course['purpose'])
        
        if course.get('AI_summary'):
            st.markdown("**AI-sammanfattning:**")
            st.info(course['AI_summary'])
    
    with col2:
        if st.button(f"Lägg till i graf", key=f"build_{course['courseCode']}"):
            build_course_graph(course['courseCode'])
        
        # Visa koncept om de finns i grafen
        with st.session_state.neo4j.driver.session() as session:
            result = session.run("""
                MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                RETURN c.namn as namn
            """, kurskod=course['courseCode'])
            
            concepts = [r['namn'] for r in result]
            if concepts:
                st.markdown("**Koncept i grafen:**")
                for concept in concepts:
                    st.markdown(f"- {concept}")


def build_course_graph(course_code):
    """Bygger graf för en enskild kurs"""
    with st.spinner(f"Bygger graf för {course_code}..."):
        try:
            # Visa vilken AI-modell som används
            from config import LITELLM_MODEL
            st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
            
            # Visa vilka koncept som extraheras
            course_info = st.session_state.parser.get_course_full_info(course_code)
            
            # Extrahera koncept med LLM och visa dem
            st.info("AI extraherar koncept...")
            concepts = st.session_state.graph_builder.llm.extract_concepts(
                course_info, 
                st.session_state.graph_builder._get_existing_concepts_summary(),
                max_concepts=st.session_state.get('max_concepts', 10),
                language=st.session_state.get('language', 'Svenska')
            )
            
            if concepts:
                st.success(f"AI hittade {len(concepts)} koncept:")
                for concept in concepts:
                    st.write(f"- **{concept.get('namn', '')}**: {concept.get('beskrivning', '')[:100]}...")
                    if concept.get('förutsätter'):
                        st.write(f"  Förutsätter: {', '.join(concept['förutsätter'])}")
            
            # Bygg graf
            stats = st.session_state.graph_builder.build_graph_for_course(course_code)
            st.success(f"Graf byggd! Skapade {stats['koncept']} nya koncept och {stats['relationer']} relationer.")
            st.rerun()
        except Exception as e:
            st.error(f"Fel vid byggande av graf: {str(e)}")


def build_program_graph_with_selection(program_code, courses_df):
    """Bygger graf för valda kurser i programmet"""
    # Samla valda kurser
    selected_courses = []
    
    for _, course in courses_df.iterrows():
        if course['rule'] == 'O':
            # Obligatoriska kurser är alltid med
            selected_courses.append(course['courseCode'])
        elif course['rule'] != 'O':
            # Kolla om valbar kurs är vald (alla som inte är O)
            course_key = f"tab1_select_{course['courseCode']}"
            if st.session_state.get(course_key, False):
                selected_courses.append(course['courseCode'])
    
    if not selected_courses:
        st.warning("Inga kurser valda. Obligatoriska kurser saknas eller inga valbara kurser valda.")
        return
    
    # VIKTIGT: Sortera kurser i kronologisk ordning
    selected_df = courses_df[courses_df['courseCode'].isin(selected_courses)].copy()
    selected_df = selected_df.sort_values(['year', 'period_num'])
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(current, total):
        progress = current / total
        progress_bar.progress(progress)
        year = selected_df.iloc[current-1]['year'] if current > 0 else 1
        period = selected_df.iloc[current-1]['period_num'] if current > 0 else 1
        course_code = selected_df.iloc[current-1]['courseCode'] if current > 0 else ""
        status_text.text(f"Bearbetar {course_code} (År {year}, LP{period})... [{current}/{total}]")
    
    try:
        # Bygg graf i kronologisk ordning
        total_stats = {"kurser": 0, "koncept": 0, "relationer": 0}
        
        st.info(f"Bygger graf för {len(selected_df)} kurser i kronologisk ordning...")
        
        # Visa vilken AI-modell som används
        from config import LITELLM_MODEL
        st.info(f"AI analyserar kurser med modell: **{LITELLM_MODEL}**")
        
        for idx, (_, course) in enumerate(selected_df.iterrows()):
            update_progress(idx + 1, len(selected_df))
            
            # Visa vilken kurs som bearbetas
            st.markdown("---")
            st.markdown(f"### Analyserar kurs {idx + 1} av {len(selected_df)}")
            st.markdown(f"**{course['courseCode']} - {course['nameAlt']}** (År {course['year']}, LP{course['period_num']})")
            
            # Visa AI-analys
            with st.container():
                st.write("AI extraherar koncept...")
                
                # Hämta kursinformation
                course_info = st.session_state.parser.get_course_full_info(course['courseCode'])
                
                # Hämta befintlig graf
                existing_concepts = st.session_state.graph_builder._get_existing_concepts_summary()
                
                # Extrahera koncept med LLM
                concepts = st.session_state.graph_builder.llm.extract_concepts(
                    course_info, 
                    existing_concepts,
                    max_concepts=st.session_state.get('max_concepts', 10),
                    language=st.session_state.get('language', 'Svenska')
                )
                
                if concepts:
                    st.success(f"AI hittade {len(concepts)} koncept:")
                    for concept in concepts:
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.write(f"**{concept.get('namn', '')}**")
                        with col2:
                            if concept.get('förutsätter'):
                                st.write(f"Förutsätter: {', '.join(concept['förutsätter'])}")
                            else:
                                st.write("Grundläggande koncept")
                else:
                    st.warning("Inga koncept hittades")
                
                # Bygg graf för kursen
                stats = st.session_state.graph_builder.build_graph_for_course(course['courseCode'])
                for key in total_stats:
                    total_stats[key] += stats[key]
        
        # Analysera förutsättningar mellan kurser (redan sorterade)
        st.info("Analyserar kopplingar mellan kurser...")
        st.session_state.graph_builder._analyze_cross_course_prerequisites(selected_df)
        
        progress_bar.empty()
        status_text.empty()
        
        st.success(
            f"Graf byggd för {len(selected_courses)} kurser! "
            f"Skapade {total_stats['kurser']} kursnoder, "
            f"{total_stats['koncept']} koncept och "
            f"{total_stats['relationer']} relationer."
        )
        st.rerun()
        
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Fel vid byggande av programgraf: {str(e)}")


if __name__ == "__main__":
    main()