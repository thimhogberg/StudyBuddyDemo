"""
Alumn-modul för StudyBuddy Studio
Hanterar alumners behov av att matcha sina kunskaper mot jobbmarknaden
"""
import streamlit as st
import json
from typing import Dict, Optional, List
from datetime import datetime
import PyPDF2
import io
import uuid


def render():
    """Renderar alumn-sidan"""
    # Lazy initialization - bara initiera det som behövs
    if 'graph_filter' not in st.session_state:
        st.session_state.graph_filter = "Alla noder"
    
    if 'selected_node' not in st.session_state:
        st.session_state.selected_node = None
    
    st.markdown("### Alumn & Karriär")
    st.markdown("Matcha din kunskapsgraf mot jobbmarknaden")
    
    # Skapa underflikar
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Jobbannonsmatchning", "Uppdatera graf", "Upskill", "Kompetensportfölj", "Karriärvägar", "Kompetens-gap", "Matchning"])
    
    with tab1:
        render_job_matching()
    
    with tab2:
        render_graph_update()
    
    with tab3:
        render_upskill()
    
    with tab4:
        render_competence_portfolio()
    
    with tab5:
        render_career_paths()
    
    with tab6:
        render_competence_gap()
    
    with tab7:
        from .alumn_matching import render_matching
        render_matching()


def render_job_matching():
    """Visar jobbmatchningsfunktionen"""
    st.subheader("Jobbannonsmatchning")
    st.markdown("""
    Analysera hur väl dina kunskaper från utbildningen matchar en specifik jobbannons.
    Systemet använder AI för att jämföra din kunskapsgraf med jobbkraven.
    """)
    
    # Kolla först om Neo4j är konfigurerat innan vi kör queries
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    st.markdown("#### Ladda jobbannonsen")
    
    # Val av inmatningsmetod
    input_method = st.radio(
        "Välj inmatningsmetod:",
        ["Klistra in text", "Ladda upp fil"],
        horizontal=True
    )
    
    job_description = None
    
    if input_method == "Klistra in text":
        job_description = st.text_area(
            "Klistra in jobbannonsen här:",
            height=300,
            placeholder="""Exempel:
Vi söker en erfaren Backend-utvecklare med kunskaper inom:
- Python och Java
- Databaser (SQL, NoSQL)
- Molntjänster (AWS/Azure)
- Algoritmer och datastrukturer
- Agile/Scrum
..."""
        )
    
    else:  # Ladda upp fil
        uploaded_file = st.file_uploader(
            "Välj fil med jobbannonsen",
            type=["txt", "pdf", "docx"],
            help="Stödda format: TXT, PDF, DOCX"
        )
        
        if uploaded_file is not None:
            job_description = process_uploaded_file(uploaded_file)
            if job_description:
                with st.expander("Visa inläst jobbannons"):
                    st.text(job_description[:1000] + "..." if len(job_description) > 1000 else job_description)
    
    # Analysknapp - visa alltid, men kräv innehåll för att köra analys
    if st.button("Analysera matchning", type="primary", use_container_width=True):
        if job_description and job_description.strip():
            perform_job_match_analysis(job_description)
        else:
            st.warning("Vänligen ange en jobbannons att analysera.")


def has_knowledge_graph() -> bool:
    """Kontrollerar om användaren har en kunskapsgraf"""
    # Caching av resultatet för att undvika upprepade databasfrågor
    if 'has_knowledge_graph_cache' in st.session_state:
        return st.session_state.has_knowledge_graph_cache
    
    try:
        if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
            st.session_state.has_knowledge_graph_cache = False
            return False
            
        with st.session_state.neo4j_service.driver.session(database="neo4j") as session:
            # Optimerad query som bara kollar om det finns minst en nod
            result = session.run("""
                MATCH (n)
                WHERE n:Kurs OR n:Koncept
                RETURN n
                LIMIT 1
            """)
            has_graph = result.single() is not None
            st.session_state.has_knowledge_graph_cache = has_graph
            return has_graph
    except:
        st.session_state.has_knowledge_graph_cache = False
        return False


def process_uploaded_file(uploaded_file) -> Optional[str]:
    """Bearbetar uppladdad fil och extraherar text"""
    try:
        if uploaded_file.type == "text/plain":
            return str(uploaded_file.read(), "utf-8")
        
        elif uploaded_file.type == "application/pdf":
            # För PDF behöver vi en PDF-läsare
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e:
                st.error(f"Kunde inte läsa PDF: {str(e)}")
                return None
        
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # För DOCX behöver vi python-docx
            st.error("DOCX-filer stöds inte än. Använd TXT eller PDF format.")
            return None
        
        else:
            st.error(f"Filtyp {uploaded_file.type} stöds inte")
            return None
            
    except Exception as e:
        st.error(f"Fel vid filbearbetning: {str(e)}")
        return None


def get_knowledge_graph_as_json() -> Dict:
    """Hämtar användarens kunskapsgraf som JSON för LLM-analys"""
    try:
        with st.session_state.neo4j_service.driver.session(database="neo4j") as session:
            # Hämta alla kurser med deras koncept
            courses_result = session.run("""
                MATCH (k:Kurs)
                OPTIONAL MATCH (k)-[:INNEHÅLLER]->(c:Koncept)
                RETURN k.kurskod as code, 
                       k.namn as name,
                       k.nameAlt as name_en,
                       k.syfte as purpose,
                       k.AI_summary as ai_summary,
                       collect(DISTINCT {
                           namn: c.namn,
                           beskrivning: c.beskrivning,
                           mastery_score: c.mastery_score
                       }) as concepts
            """)
            
            courses = []
            all_concepts = {}
            
            for record in courses_result:
                course = {
                    'code': record['code'],
                    'name': record['name'],
                    'name_en': record['name_en'],
                    'purpose': record['purpose'],
                    'ai_summary': record['ai_summary'],
                    'concepts': []
                }
                
                for concept in record['concepts']:
                    if concept['namn']:  # Kontrollera att konceptet har ett namn
                        course['concepts'].append(concept['namn'])
                        all_concepts[concept['namn']] = {
                            'beskrivning': concept['beskrivning'],
                            'mastery_score': concept['mastery_score'] or 0
                        }
                
                courses.append(course)
            
            # Hämta konceptrelationer
            relations_result = session.run("""
                MATCH (c1:Koncept)-[:FÖRUTSÄTTER]->(c2:Koncept)
                RETURN c1.namn as from_concept, c2.namn as to_concept
            """)
            
            prerequisites = []
            for record in relations_result:
                prerequisites.append({
                    'from': record['from_concept'],
                    'to': record['to_concept']
                })
            
            # Hämta studentens övergripande mastery
            mastery_result = session.run("""
                MATCH (c:Koncept)
                WHERE c.mastery_score IS NOT NULL
                RETURN avg(c.mastery_score) as avg_mastery,
                       count(c) as total_concepts,
                       sum(CASE WHEN c.mastery_score >= 0.7 THEN 1 ELSE 0 END) as mastered_concepts
            """)
            
            mastery_record = mastery_result.single()
            
            return {
                'courses': courses,
                'concepts': all_concepts,
                'prerequisites': prerequisites,
                'student_mastery': {
                    'average': mastery_record['avg_mastery'] or 0,
                    'total_concepts': mastery_record['total_concepts'] or 0,
                    'mastered_concepts': mastery_record['mastered_concepts'] or 0
                }
            }
            
    except Exception as e:
        error_msg = str(e)
        if "NotALeader" in error_msg or "Unable to route" in error_msg:
            st.error("""
            **Databaskopplingsfel:** Neo4j-klustret har problem med routing.
            
            **Möjliga lösningar:**
            1. Kontrollera att Neo4j-databasen körs
            2. Starta om databasen
            3. Kontrollera din Neo4j URI i konfigurationen
            """)
        else:
            st.error(f"Fel vid hämtning av kunskapsgraf: {error_msg}")
        
        return {
            'courses': [],
            'concepts': {},
            'prerequisites': [],
            'student_mastery': {
                'average': 0,
                'total_concepts': 0,
                'mastered_concepts': 0
            }
        }


def perform_job_match_analysis(job_description: str):
    """Utför jobbannonsmatchning mot kunskapsgrafen"""
    # Visa vilken modell som används
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar jobbannonsen mot din kunskapsgraf..."):
        # Hämta kunskapsgrafen
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Hämta prompt från inställningar eller använd standard
        default_prompt = """Analysera matchningen mellan en students kunskapsgraf från Chalmers och en jobbannons.

VIKTIGT: Basera din analys på studentens FAKTISKA kunskapsnivå enligt mastery_score för varje koncept:
- mastery_score 0.0-0.3: Låg behärskning (studenten har begränsad kunskap)
- mastery_score 0.3-0.7: Medel behärskning (studenten har grundläggande förståelse)
- mastery_score 0.7-1.0: Hög behärskning (studenten behärskar konceptet väl)

Om alla mastery_scores är 0 betyder det att studenten INTE har någon praktisk kunskap om dessa koncept ännu.

STUDENTENS KUNSKAPSGRAF:
{knowledge_graph}

JOBBANNONS:
{job_description}

Gör en REALISTISK analys baserad på mastery_scores:

1. ÖVERGRIPANDE MATCHNINGSGRAD (0-100%)
   - Basera detta STRIKT på mastery_scores. Om alla scores är 0, ska matchningen vara mycket låg
   - Ta hänsyn till hur många av jobbkraven som täcks av koncept med hög mastery_score

2. MATCHANDE KOMPETENSER
   - Lista ENDAST koncept med mastery_score > 0.5 som matchar jobbkraven
   - Ange mastery_score för varje matchande koncept
   - Om inga koncept har tillräcklig mastery_score, ange detta tydligt

3. SAKNADE KOMPETENSER
   - Lista både koncept som helt saknas OCH koncept med låg mastery_score (< 0.5)
   - Kategorisera som "Kritiska" eller "Önskvärda"

4. UTVECKLINGSOMRÅDEN
   - Identifiera koncept med låg mastery_score som är relevanta för jobbet
   - Ge konkreta förslag på hur dessa kan förbättras

5. REKOMMENDATIONER
   - Var ÄRLIG om studentens nuvarande kompetensnivå
   - Om mastery_scores är låga, fokusera på utvecklingsvägar
   - Undvik att överdriva studentens kompetenser

6. SAMMANFATTNING
   - Ge en ärlig bedömning baserad på faktiska mastery_scores
   - Om studenten inte är redo för jobbet, var tydlig med detta

Var extremt noggrann med att basera analysen på de faktiska mastery_scores. Överskatta INTE studentens kompetenser."""
        
        prompt_template = st.session_state.get('job_matching_prompt', default_prompt)
        
        # Förbered prompt för LLM
        prompt = prompt_template.format(
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False),
            job_description=job_description
        )
        
        try:
            # Lazy-load LLM service endast när det behövs
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt)
            
            # Visa resultat
            st.success("Analys klar!")
            
            # Visa analysen
            st.markdown("### Matchningsanalys")
            st.markdown(analysis)
            
            # Visa länk till Chalmers Upskilling Academy
            st.divider()
            st.info("**Vill du förbättra din matchning?**")
            st.markdown("""
            Kolla in [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/) 
            för att hitta kurser som kan komplettera dina kunskaper och göra dig mer attraktiv på arbetsmarknaden.
            
            Du kan också använda **Upskill-fliken** ovan för att analysera specifika kurser mot din kunskapsgraf.
            """)
            
            # Spara analysen för framtida referens
            save_analysis(job_description, knowledge_graph, analysis)
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def save_analysis(job_description: str, knowledge_graph: Dict, analysis: str):
    """Sparar analysen för framtida referens"""
    try:
        # Skapa en tidsstämpel
        timestamp = datetime.now().isoformat()
        
        # Spara i session state för denna session
        if 'job_analyses' not in st.session_state:
            st.session_state.job_analyses = []
        
        st.session_state.job_analyses.append({
            'timestamp': timestamp,
            'job_description': job_description[:200] + "..." if len(job_description) > 200 else job_description,
            'analysis': analysis
        })
        
        # Visa alternativ för att ladda ner analysen
        st.markdown("#### Ladda ner analys")
        col1, col2 = st.columns(2)
        
        with col1:
            # Ladda ner som textfil
            analysis_text = f"""JOBBANNONSMATCHNING - ANALYS
Datum: {timestamp}

JOBBANNONS:
{job_description}

ANALYS:
{analysis}
"""
            st.download_button(
                label="Ladda ner som TXT",
                data=analysis_text,
                file_name=f"jobbmatchning_{timestamp[:10]}.txt",
                mime="text/plain"
            )
        
        with col2:
            # Ladda ner som JSON (mer strukturerat)
            analysis_data = {
                'timestamp': timestamp,
                'job_description': job_description,
                'knowledge_graph_summary': {
                    'total_courses': len(knowledge_graph['courses']),
                    'total_concepts': len(knowledge_graph['concepts']),
                    'average_mastery': knowledge_graph['student_mastery']['average']
                },
                'analysis': analysis
            }
            
            st.download_button(
                label="Ladda ner som JSON",
                data=json.dumps(analysis_data, indent=2, ensure_ascii=False),
                file_name=f"jobbmatchning_{timestamp[:10]}.json",
                mime="application/json"
            )
            
    except Exception as e:
        st.error(f"Kunde inte spara analysen: {str(e)}")


def render_graph_update():
    """Visar gränssnitt för att uppdatera kunskapsgrafen baserat på erfarenheter"""
    st.subheader("Uppdatera din kunskapsgraf")
    st.markdown("""
    Ladda upp dokument som beskriver dina kunskaper och erfarenheter utöver utbildningen.
    AI kommer att analysera innehållet och uppdatera din kunskapsgraf med nya koncept och mastery scores.
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Val av dokumenttyp
    doc_type = st.selectbox(
        "Välj typ av dokument:",
        ["CV", "Projektbeskrivning", "Certifikat", "LinkedIn-profil (kommer snart)"]
    )
    
    if doc_type == "LinkedIn-profil (kommer snart)":
        st.info("LinkedIn-integration kommer i en framtida version.")
        return
    
    # Val av inmatningsmetod
    input_method = st.radio(
        "Välj inmatningsmetod:",
        ["Ladda upp fil", "Klistra in text"],
        horizontal=True
    )
    
    content = None
    
    if input_method == "Ladda upp fil":
        uploaded_file = st.file_uploader(
            f"Välj {doc_type.lower()}-fil",
            type=["txt", "pdf", "docx"],
            help="Stödda format: TXT, PDF, DOCX"
        )
        
        if uploaded_file is not None:
            content = process_uploaded_file(uploaded_file)
            if content:
                with st.expander(f"Visa inläst {doc_type.lower()}"):
                    st.text(content[:1000] + "..." if len(content) > 1000 else content)
    
    else:  # Klistra in text
        content = st.text_area(
            f"Klistra in din {doc_type.lower()} här:",
            height=300,
            placeholder=get_placeholder_text(doc_type)
        )
    
    # Analysknapp
    if st.button("Analysera och uppdatera graf", type="primary", use_container_width=True):
        if content and content.strip():
            analyze_and_update_graph(content, doc_type)
        else:
            st.warning(f"Vänligen ange innehåll från din {doc_type.lower()} att analysera.")


def get_placeholder_text(doc_type: str) -> str:
    """Returnerar lämplig placeholder-text baserat på dokumenttyp"""
    if doc_type == "CV":
        return """Exempel:
ARBETSLIVSERFARENHET
2020-2023: Senior Python-utvecklare på Tech AB
- Utvecklade mikrotjänster med FastAPI och Docker
- Arbetade med maskininlärning och NLP
- Ledde team på 5 utvecklare

TEKNISKA FÄRDIGHETER
- Python (expert), Java (avancerad)
- Machine Learning: TensorFlow, PyTorch
- Databaser: PostgreSQL, MongoDB
..."""
    elif doc_type == "Projektbeskrivning":
        return """Exempel:
PROJEKT: AI-driven chatbot för kundservice
Tid: 6 månader (2023)
Roll: Lead Developer

Utvecklade en NLP-baserad chatbot med:
- Natural Language Processing med BERT
- Real-time sentiment analysis
- Integration med CRM-system
- Microservices arkitektur

Teknologier: Python, TensorFlow, Docker, Kubernetes..."""
    else:  # Certifikat
        return """Exempel:
AWS Certified Solutions Architect - Professional
Utfärdat: Mars 2023

Google Cloud Professional Data Engineer
Utfärdat: Januari 2023

Certified Kubernetes Administrator (CKA)
Utfärdat: Oktober 2022
..."""


def analyze_and_update_graph(content: str, doc_type: str):
    """Analyserar innehåll och uppdaterar kunskapsgrafen"""
    # Visa vilken modell som används
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner(f"Analyserar {doc_type.lower()} och uppdaterar kunskapsgraf..."):
        # Hämta nuvarande kunskapsgraf
        current_graph = get_knowledge_graph_as_json()
        
        # Hämta prompt från inställningar eller använd standard
        default_prompt = """Analysera följande {doc_type} och identifiera tekniska koncept och kompetenser som personen behärskar.
Jämför med personens befintliga kunskapsgraf från utbildningen.

BEFINTLIG KUNSKAPSGRAF:
{current_graph}

{doc_type_upper} ATT ANALYSERA:
{content}

INSTRUKTIONER:
1. Identifiera tekniska koncept från {doc_type}en som personen behärskar
2. För varje koncept, bedöm mastery_score (0.0-1.0) baserat på:
   - Erfarenhetens längd och djup
   - Praktisk tillämpning
   - Ansvarsnivå
   - Certifieringar/bevis
3. Om konceptet redan finns i grafen, föreslå uppdaterad mastery_score
4. Om konceptet är nytt, föreslå att lägga till det med lämplig mastery_score
5. Håll konceptnamnen korta och koncisa (max 3-4 ord)
6. Fokusera på tekniska/yrkesmässiga färdigheter

MASTERY SCORE RIKTLINJER:
- 0.0-0.3: Grundläggande kunskap/begränsad erfarenhet
- 0.3-0.5: God förståelse med viss praktisk erfarenhet
- 0.5-0.7: Solid kompetens med betydande erfarenhet
- 0.7-0.9: Expert-nivå med djup erfarenhet
- 0.9-1.0: Mästare/branschledande expert

Svara i följande JSON-format:
```json
{{
    "nya_koncept": [
        {{
            "namn": "Konceptnamn",
            "beskrivning": "Kort beskrivning",
            "mastery_score": 0.8,
            "motivering": "Varför denna score baserat på erfarenheten"
        }}
    ],
    "uppdaterade_koncept": [
        {{
            "namn": "Befintligt konceptnamn",
            "ny_mastery_score": 0.9,
            "gammal_mastery_score": 0.5,
            "motivering": "Varför score ska uppdateras"
        }}
    ],
    "sammanfattning": "Kort sammanfattning av analysen"
}}
```"""
        
        prompt_template = st.session_state.get('graph_update_prompt', default_prompt)
        
        # Förbered prompt för LLM
        prompt = prompt_template.format(
            doc_type=doc_type,
            current_graph=json.dumps(current_graph, indent=2, ensure_ascii=False),
            doc_type_upper=doc_type.upper(),
            content=content
        )
        
        try:
            # Lazy-load LLM service
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            # Få AI-analys
            analysis = st.session_state.llm_service.query(prompt)
            
            # Parsa JSON-svar
            try:
                # Extrahera JSON från svaret
                json_start = analysis.find('```json')
                json_end = analysis.find('```', json_start + 7)
                if json_start != -1 and json_end != -1:
                    json_str = analysis[json_start + 7:json_end].strip()
                    result = json.loads(json_str)
                else:
                    # Försök parsa hela svaret som JSON
                    result = json.loads(analysis)
            except json.JSONDecodeError:
                st.error("Kunde inte tolka AI-svaret. Försök igen.")
                return
            
            # Visa resultat
            st.success("Analys klar!")
            
            # Visa sammanfattning
            if 'sammanfattning' in result:
                st.markdown("### Sammanfattning")
                st.info(result['sammanfattning'])
            
            # Visa föreslagna uppdateringar
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Nya koncept att lägga till")
                if result.get('nya_koncept'):
                    for koncept in result['nya_koncept']:
                        st.markdown(f"**{koncept['namn']}**")
                        st.caption(f"{koncept['beskrivning']}")
                        st.progress(koncept['mastery_score'], text=f"Mastery: {koncept['mastery_score']:.1%}")
                        st.caption(f"*{koncept['motivering']}*")
                        st.divider()
                else:
                    st.info("Inga nya koncept identifierades")
            
            with col2:
                st.markdown("#### Koncept att uppdatera")
                if result.get('uppdaterade_koncept'):
                    for koncept in result['uppdaterade_koncept']:
                        st.markdown(f"**{koncept['namn']}**")
                        old_score = koncept['gammal_mastery_score']
                        new_score = koncept['ny_mastery_score']
                        st.caption(f"Nuvarande: {old_score:.1%} → Föreslagen: {new_score:.1%}")
                        st.caption(f"*{koncept['motivering']}*")
                        st.divider()
                else:
                    st.info("Inga koncept behöver uppdateras")
            
            # Bekräfta uppdateringar
            if result.get('nya_koncept') or result.get('uppdaterade_koncept'):
                st.markdown("### Bekräfta uppdateringar")
                
                if st.button("Tillämpa alla uppdateringar", type="primary"):
                    apply_graph_updates(result)
                
                # Möjlighet att ladda ner analys
                st.markdown("#### Ladda ner analys")
                analysis_data = {
                    'timestamp': datetime.now().isoformat(),
                    'doc_type': doc_type,
                    'analysis_result': result
                }
                
                st.download_button(
                    label="Ladda ner analys som JSON",
                    data=json.dumps(analysis_data, indent=2, ensure_ascii=False),
                    file_name=f"graf_uppdatering_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def apply_graph_updates(updates: Dict):
    """Tillämpar uppdateringar på kunskapsgrafen i Neo4j"""
    try:
        with st.session_state.neo4j_service.driver.session(database="neo4j") as session:
            updated_concepts = 0
            new_concepts = 0
            
            # Lägg till nya koncept
            for koncept in updates.get('nya_koncept', []):
                result = session.run("""
                    CREATE (c:Koncept {
                        namn: $namn,
                        beskrivning: $beskrivning,
                        mastery_score: $mastery_score,
                        id: $id,
                        retention: 1.0,
                        difficulty: 0.3,
                        interval: 1,
                        ease_factor: 2.5,
                        review_count: 0,
                        source: 'alumn_update'
                    })
                    RETURN c
                """,
                namn=koncept['namn'],
                beskrivning=koncept['beskrivning'],
                mastery_score=koncept['mastery_score'],
                id=str(uuid.uuid4())
                )
                
                if result.single():
                    new_concepts += 1
            
            # Uppdatera befintliga koncept
            for koncept in updates.get('uppdaterade_koncept', []):
                result = session.run("""
                    MATCH (c:Koncept {namn: $namn})
                    SET c.mastery_score = $ny_mastery_score,
                        c.last_updated = $timestamp,
                        c.update_source = 'alumn_update'
                    RETURN c
                """,
                namn=koncept['namn'],
                ny_mastery_score=koncept['ny_mastery_score'],
                timestamp=datetime.now().isoformat()
                )
                
                if result.single():
                    updated_concepts += 1
            
            # Visa resultat
            st.success(f"""
            Grafen har uppdaterats!
            - {new_concepts} nya koncept tillagda
            - {updated_concepts} koncept uppdaterade
            """)
            
            # Rensa cache för kunskapsgraf
            if 'has_knowledge_graph_cache' in st.session_state:
                del st.session_state.has_knowledge_graph_cache
                
    except Exception as e:
        st.error(f"Fel vid uppdatering av graf: {str(e)}")


def render_upskill():
    """Visar gränssnitt för upskilling-kurser"""
    st.subheader("Upskill - Vidareutbildning")
    st.markdown("""
    Utforska kurser som kan komplettera din utbildning och göra dig mer attraktiv på arbetsmarknaden.
    Analysera hur väl du är förberedd för varje kurs baserat på din nuvarande kunskapsgraf.
    """)
    
    # Länk till Chalmers Upskilling Academy
    st.info("""
    **Chalmers Upskilling Academy** erbjuder flexibla kurser för yrkesverksamma.
    [Läs mer om Chalmers satsning på upskilling →](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/)
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    # Mock-kurser för demonstration
    mock_courses = [
        {
            "name": "Machine Learning för praktiker",
            "code": "DAT450",
            "credits": 3,
            "description": "Praktisk introduktion till maskininlärning med Python och scikit-learn",
            "prerequisites": ["Python programmering", "Grundläggande statistik"],
            "concepts": ["Supervised learning", "Neural networks", "Model evaluation", "Feature engineering"]
        },
        {
            "name": "Cloud Computing med AWS",
            "code": "DAT460",
            "credits": 2,
            "description": "Hands-on kurs i molntjänster med fokus på AWS",
            "prerequisites": ["Grundläggande nätverk", "Linux"],
            "concepts": ["EC2", "S3", "Lambda", "Containerization", "Infrastructure as Code"]
        },
        {
            "name": "Cybersäkerhet för utvecklare",
            "code": "DAT470",
            "credits": 2,
            "description": "Säker mjukvaruutveckling och vanliga säkerhetshot",
            "prerequisites": ["Webbutveckling", "Databaser"],
            "concepts": ["OWASP Top 10", "Secure coding", "Penetration testing", "Kryptering"]
        },
        {
            "name": "Agile projektledning",
            "code": "PPU040",
            "credits": 1,
            "description": "Scrum, Kanban och andra agila metoder",
            "prerequisites": ["Mjukvaruutveckling"],
            "concepts": ["Scrum", "Kanban", "User stories", "Sprint planning"]
        },
        {
            "name": "DevOps och CI/CD",
            "code": "DAT480",
            "credits": 3,
            "description": "Automatisering av utveckling och deployment",
            "prerequisites": ["Git", "Linux", "Docker"],
            "concepts": ["Jenkins", "GitLab CI", "Kubernetes", "Monitoring", "Infrastructure automation"]
        },
        {
            "name": "Kvantberäkning - Introduktion",
            "code": "TIF150",
            "credits": 2,
            "description": "Grunderna i kvantberäkning och kvantalgoritmer",
            "prerequisites": ["Linjär algebra", "Kvantmekanik grundkurs"],
            "concepts": ["Qubits", "Quantum gates", "Quantum algorithms", "Quantum supremacy"]
        },
        {
            "name": "Data Engineering",
            "code": "DAT490",
            "credits": 3,
            "description": "Bygga och underhålla storskaliga datapipelines",
            "prerequisites": ["Databaser", "Python", "SQL"],
            "concepts": ["ETL", "Data lakes", "Apache Spark", "Stream processing", "Data warehousing"]
        },
        {
            "name": "Blockchain-teknologi",
            "code": "DAT500",
            "credits": 2,
            "description": "Distribuerade ledgers och smarta kontrakt",
            "prerequisites": ["Kryptografi", "Distribuerade system"],
            "concepts": ["Blockchain", "Smart contracts", "Consensus algorithms", "DeFi"]
        },
        {
            "name": "UX/UI för ingenjörer",
            "code": "PPU050",
            "credits": 1,
            "description": "Användarcentrerad design för tekniska produkter",
            "prerequisites": ["Webbutveckling"],
            "concepts": ["User research", "Prototyping", "Usability testing", "Design systems"]
        },
        {
            "name": "Green Computing",
            "code": "DAT510",
            "credits": 2,
            "description": "Hållbar IT och energieffektiv mjukvara",
            "prerequisites": ["Systemdesign", "Algoritmer"],
            "concepts": ["Energy-efficient algorithms", "Carbon footprint", "Green data centers", "Sustainable IT"]
        }
    ]
    
    # Lazy loading - visa kurser endast när användaren klickar
    if 'show_upskill_courses' not in st.session_state:
        st.session_state.show_upskill_courses = False
    
    if not st.session_state.show_upskill_courses:
        if st.button("Visa tillgängliga kurser", type="primary", use_container_width=True):
            st.session_state.show_upskill_courses = True
            st.rerun()
    else:
        # Visa kurser
        st.markdown("### Tillgängliga kurser")
        
        # Skapa kolumner för kurskort
        for i in range(0, len(mock_courses), 2):
            col1, col2 = st.columns(2)
            
            with col1:
                if i < len(mock_courses):
                    render_course_card(mock_courses[i])
            
            with col2:
                if i + 1 < len(mock_courses):
                    render_course_card(mock_courses[i + 1])


def render_course_card(course: Dict):
    """Renderar ett kurskort med analysknapp"""
    with st.container():
        st.markdown(f"#### {course['name']}")
        st.caption(f"{course['code']} • {course['credits']} hp")
        st.markdown(course['description'])
        
        with st.expander("Kursinnehåll"):
            st.markdown("**Förkunskaper:**")
            for prereq in course['prerequisites']:
                st.markdown(f"- {prereq}")
            
            st.markdown("**Koncept som lärs ut:**")
            for concept in course['concepts']:
                st.markdown(f"- {concept}")
        
        if st.button(f"Analysera mot min graf", key=f"analyze_{course['code']}"):
            analyze_course_fit(course)


def analyze_course_fit(course: Dict):
    """Analyserar hur väl en kurs passar studentens kunskapsgraf"""
    # Visa vilken modell som används
    from config import LITELLM_MODEL
    st.info(f"AI analyserar kursens lämplighet med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar kursens lämplighet..."):
        # Hämta studentens kunskapsgraf
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Förbered prompt för analys
        prompt = f"""
Analysera hur väl följande upskilling-kurs passar för en student baserat på deras kunskapsgraf.

STUDENTENS KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

KURS ATT ANALYSERA:
Namn: {course['name']}
Kod: {course['code']}
Högskolepoäng: {course['credits']}
Beskrivning: {course['description']}
Förkunskaper: {', '.join(course['prerequisites'])}
Koncept som lärs ut: {', '.join(course['concepts'])}

INSTRUKTIONER:
1. Analysera om studenten har de nödvändiga förkunskaperna
2. Identifiera vilka förkunskaper som saknas eller behöver förstärkas
3. Bedöm svårighetsgraden för studenten (lätt/medium/svår)
4. Identifiera koncept studenten redan kan (och deras mastery_score)
5. Ge en rekommendation om kursen är lämplig

VIKTIGT: Basera analysen på faktiska mastery_scores. Om relevanta koncept har låg mastery_score (<0.5), 
rekommendera att studenten först förstärker dessa.

Svara med en strukturerad analys som inkluderar:
- Lämplighetsbedömning (0-100%)
- Förkunskaper som uppfylls/saknas
- Koncept som behöver förstärkas först
- Rekommendation och nästa steg
"""
        
        try:
            # Lazy-load LLM service
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            # Få AI-analys
            analysis = st.session_state.llm_service.query(prompt)
            
            # Visa resultat i en modal-liknande container
            with st.container():
                st.success("Analys klar!")
                st.markdown(f"### Analys: {course['name']}")
                st.markdown(analysis)
                
                # Länk till Chalmers Upskilling
                st.divider()
                st.markdown("""
                **Intresserad av kursen?**  
                Besök [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/) 
                för mer information om kursutbud och anmälan.
                """)
                
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def render_competence_portfolio():
    """Visar och genererar kompetensportfölj"""
    st.subheader("Kompetensportfölj")
    st.markdown("""
    Få en strukturerad sammanställning av dina akademiska kunskaper från Chalmers.
    En ärlig överblick av vad du har studerat och din förståelsenivå inom olika områden.
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    # Lazy loading - generera endast när användaren klickar
    if 'show_portfolio' not in st.session_state:
        st.session_state.show_portfolio = False
    
    if not st.session_state.show_portfolio:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generera kompetensportfölj", type="primary", use_container_width=True):
                st.session_state.show_portfolio = True
                st.rerun()
        with col2:
            st.info("En sammanställning av dina kurser och kunskaper kommer att genereras baserat på din kunskapsgraf.")
    else:
        generate_portfolio()


def generate_portfolio():
    """Genererar en kompetensportfölj med AI"""
    # Visa vilken modell som används
    from config import LITELLM_MODEL
    st.info(f"AI genererar din kompetensportfölj med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Genererar din kompetensportfölj..."):
        # Hämta kunskapsgrafen
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Hämta prompt från inställningar eller använd standard
        default_prompt = """Skapa en ärlig och realistisk sammanställning av en Chalmers-students kunskaper baserat på deras kunskapsgraf.

KUNSKAPSGRAF:
{knowledge_graph}

INSTRUKTIONER:
1. Sammanställ studentens kunskaper på ett strukturerat sätt
2. Gruppera kunskaper i naturliga kategorier (t.ex. Programmering, Matematik, Systemdesign)
3. För varje kunskapskategori:
   - Lista relevanta koncept som studenten studerat
   - Beskriv kunskapsnivån ärligt baserat på mastery_score:
     * 0.0-0.3: Introducerats till / Grundläggande förståelse
     * 0.3-0.5: Arbetat med / Praktisk erfarenhet från kurser
     * 0.5-0.7: God förståelse / Genomfört projekt inom området
     * 0.7-1.0: Djup förståelse / Omfattande kurserfarenhet
4. Inkludera endast koncept med mastery_score > 0.2
5. Var realistisk - det är en student, inte en yrkesverksam
6. Avsluta med en kort, ärlig sammanfattning av studentens profil

FORMAT:
- Skriv som en saklig kunskapssammanställning, inte en säljande text
- Använd vardagligt språk som "har studerat", "arbetat med", "god förståelse av"
- Undvik överdrifter och superlativer
- Fokusera på vad studenten faktiskt har lärt sig i sina kurser
- Var tydlig med att detta är akademiska kunskaper från utbildning"""
        
        prompt_template = st.session_state.get('portfolio_prompt', default_prompt)
        
        # Förbered prompt för portfolio-generering
        prompt = prompt_template.format(
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False)
        )
        
        try:
            # Lazy-load LLM service
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            # Generera portfolio
            portfolio = st.session_state.llm_service.query(prompt)
            
            # Visa portfolio
            st.success("Kompetensportfölj genererad!")
            
            # Portfolio-innehåll
            st.markdown("### Din kompetensportfölj")
            st.markdown(portfolio)
            
            # Export-alternativ
            st.divider()
            st.markdown("### Exportera portfölj")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Textformat
                st.download_button(
                    label="Ladda ner som TXT",
                    data=portfolio,
                    file_name=f"kompetensportfolj_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # Markdown-format
                st.download_button(
                    label="Ladda ner som MD",
                    data=portfolio,
                    file_name=f"kompetensportfolj_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown"
                )
            
            with col3:
                # JSON-format med strukturerad data
                portfolio_data = {
                    'generated_at': datetime.now().isoformat(),
                    'portfolio_text': portfolio,
                    'knowledge_graph_summary': {
                        'total_courses': len(knowledge_graph['courses']),
                        'total_concepts': len(knowledge_graph['concepts']),
                        'average_mastery': knowledge_graph['student_mastery']['average'],
                        'mastered_concepts': knowledge_graph['student_mastery']['mastered_concepts']
                    }
                }
                st.download_button(
                    label="Ladda ner som JSON",
                    data=json.dumps(portfolio_data, indent=2, ensure_ascii=False),
                    file_name=f"kompetensportfolj_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            
            # Tips för användning
            st.info("""
            **Tips för användning:**
            - Använd som underlag för att beskriva dina akademiska kunskaper
            - Komplettera med praktisk erfarenhet från projekt och extrajobb
            - Uppdatera efter varje avslutad termin
            - Kom ihåg att detta är en sammanställning av kurser, inte arbetslivserfarenhet
            """)
            
        except Exception as e:
            st.error(f"Fel vid generering av portfolio: {str(e)}")


def render_career_paths():
    """Visar karriärvägar och roadmaps"""
    st.subheader("Karriärvägar")
    st.markdown("""
    Utforska olika karriärvägar baserat på dina nuvarande kompetenser.
    Se roadmaps för att nå specifika roller och få rekommendationer om vilka kompetenser du behöver utveckla.
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    # Fördefinierade karriärvägar att välja mellan
    career_paths = {
        "Data Scientist": {
            "description": "Arbetar med dataanalys, maskininlärning och statistisk modellering",
            "key_skills": ["Python", "Machine Learning", "Statistik", "Data Visualization", "SQL", "Deep Learning"]
        },
        "DevOps Engineer": {
            "description": "Ansvarar för automation, CI/CD och infrastruktur",
            "key_skills": ["Docker", "Kubernetes", "CI/CD", "Cloud Services", "Linux", "Infrastructure as Code"]
        },
        "Full Stack Developer": {
            "description": "Utvecklar både frontend och backend för webbapplikationer",
            "key_skills": ["JavaScript", "React/Vue/Angular", "Node.js", "Databaser", "REST API", "HTML/CSS"]
        },
        "Machine Learning Engineer": {
            "description": "Implementerar och optimerar ML-modeller i produktion",
            "key_skills": ["Python", "TensorFlow/PyTorch", "MLOps", "Model Deployment", "Data Engineering", "Algorithm Optimization"]
        },
        "Cloud Architect": {
            "description": "Designar skalbar och säker molninfrastruktur",
            "key_skills": ["AWS/Azure/GCP", "Microservices", "Security", "Networking", "Containerization", "Cost Optimization"]
        },
        "Backend Developer": {
            "description": "Specialiserar sig på server-side utveckling och API:er",
            "key_skills": ["Java/Python/Go", "Databases", "API Design", "Microservices", "Message Queues", "Performance Optimization"]
        },
        "Security Engineer": {
            "description": "Säkrar system och applikationer mot hot",
            "key_skills": ["Security Testing", "Cryptography", "Network Security", "OWASP", "Incident Response", "Compliance"]
        },
        "Software Architect": {
            "description": "Designar övergripande systemarkitektur",
            "key_skills": ["System Design", "Design Patterns", "Architecture Patterns", "Technical Leadership", "Documentation", "Technology Selection"]
        }
    }
    
    # Lazy loading
    if 'selected_career_path' not in st.session_state:
        st.session_state.selected_career_path = None
    
    # Välj karriärväg
    st.markdown("### Välj en karriärväg att utforska")
    
    # Skapa karriärväg-kort i kolumner
    for i in range(0, len(career_paths), 2):
        col1, col2 = st.columns(2)
        
        career_names = list(career_paths.keys())
        
        with col1:
            if i < len(career_names):
                career = career_names[i]
                with st.container():
                    st.markdown(f"#### {career}")
                    st.caption(career_paths[career]["description"])
                    if st.button(f"Analysera väg till {career}", key=f"career_{career}"):
                        st.session_state.selected_career_path = career
                        st.rerun()
        
        with col2:
            if i + 1 < len(career_names):
                career = career_names[i + 1]
                with st.container():
                    st.markdown(f"#### {career}")
                    st.caption(career_paths[career]["description"])
                    if st.button(f"Analysera väg till {career}", key=f"career_{career}"):
                        st.session_state.selected_career_path = career
                        st.rerun()
    
    # Visa analys om karriärväg är vald
    if st.session_state.selected_career_path:
        st.divider()
        analyze_career_path(st.session_state.selected_career_path, career_paths[st.session_state.selected_career_path])


def analyze_career_path(career_name: str, career_info: Dict):
    """Analyserar en specifik karriärväg mot studentens kunskapsgraf"""
    # Visa vilken modell som används
    from config import LITELLM_MODEL
    st.info(f"AI analyserar karriärväg med modell: **{LITELLM_MODEL}**")
    
    with st.spinner(f"Analyserar din väg till {career_name}..."):
        # Hämta kunskapsgrafen
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Förbered prompt
        prompt = f"""
Analysera karriärvägen till {career_name} baserat på studentens kunskapsgraf.

KARRIÄRMÅL:
Roll: {career_name}
Beskrivning: {career_info['description']}
Nyckelkompetenser: {', '.join(career_info['key_skills'])}

STUDENTENS KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

KRITISKA INSTRUKTIONER:
1. Var EXTREMT ärlig om studentens nuvarande position
2. Om alla eller de flesta mastery_scores är 0, innebär det att studenten INTE har praktisk kunskap
3. Basera matchningsprocenten STRIKT på faktiska mastery_scores:
   - Om alla relevanta scores är 0: max 5-10% matchning
   - Om de flesta scores är under 0.3: max 15-25% matchning
   - Endast ge högre matchning om studenten faktiskt har höga scores i relevanta områden
4. Var tydlig med att låga scores betyder begränsad eller ingen praktisk erfarenhet

FORMAT:
- **Nuvarande matchning**: X% (Var ÄRLIG - om scores är låga, ska matchningen vara låg)
  - Förklara tydligt varför matchningen är som den är
  - Om studenten har 0 i mastery på relevanta områden, säg det rakt ut

- **Befintliga styrkor**: 
  - Lista ENDAST koncept med mastery_score > 0.5 som är relevanta
  - Om inga sådana finns, skriv "Inga starka områden identifierade ännu"

- **Kompetenser att utveckla**:
  - Lista ALLA nyckelkompetenser som saknas eller har låg mastery
  - Var tydlig med nuvarande nivå för varje

- **Realistisk tidslinje**:
  - Ge en ärlig uppskattning av hur lång tid det tar att nå målet
  - Ta hänsyn till att bygga kompetens tar tid

- **Nästa steg**:
  - Fokusera på grundläggande steg om mastery_scores är låga
  - Föreslå [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/) för vidareutbildning

Kom ihåg: Om studenten har 0 eller låg mastery på allt relevant, var ärlig om att de är i början av sin resa.
"""
        
        try:
            # Lazy-load LLM service
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            # Få analys
            analysis = st.session_state.llm_service.query(prompt)
            
            # Visa resultat
            st.success("Analys klar!")
            st.markdown(f"### Karriärväg: {career_name}")
            st.markdown(analysis)
            
            # Möjlighet att ladda ner analysen
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="Ladda ner karriäranalys",
                    data=analysis,
                    file_name=f"karriarvag_{career_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
            
            with col2:
                if st.button("Analysera annan karriärväg"):
                    st.session_state.selected_career_path = None
                    st.rerun()
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def render_competence_gap():
    """Visar kompetens-gap analys"""
    st.subheader("Kompetens-gap analys")
    st.markdown("""
    Jämför din kompetensprofil mot branschstandarder och identifiera utvecklingsområden.
    Få en ärlig bedömning av var du står idag och vad som krävs för olika roller.
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    # Val av analystyp
    analysis_type = st.selectbox(
        "Välj typ av gap-analys:",
        [
            "Junior Developer - Vad krävs för första jobbet?",
            "Branschstandard för mitt program",
            "Specifik roll eller företag",
            "Teknologistack-analys"
        ]
    )
    
    if analysis_type == "Junior Developer - Vad krävs för första jobbet?":
        analyze_junior_developer_gap()
    elif analysis_type == "Branschstandard för mitt program":
        analyze_program_standard_gap()
    elif analysis_type == "Specifik roll eller företag":
        analyze_specific_role_gap()
    elif analysis_type == "Teknologistack-analys":
        analyze_tech_stack_gap()


def analyze_junior_developer_gap():
    """Analyserar gap för junior developer position"""
    st.markdown("### Gap-analys: Junior Developer")
    st.info("""
    Denna analys jämför dina nuvarande kunskaper med vad som typiskt krävs för en junior developer-position.
    Analysen baseras på verkliga jobbkrav från svenska IT-företag.
    """)
    
    if st.button("Starta gap-analys", type="primary", use_container_width=True):
        perform_junior_developer_gap_analysis()


def perform_junior_developer_gap_analysis():
    """Utför gap-analys för junior developer"""
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar dina kompetenser mot junior developer-krav..."):
        # Hämta kunskapsgrafen
        knowledge_graph = get_knowledge_graph_as_json()
        
        prompt = """
Gör en ärlig gap-analys mellan studentens nuvarande kunskaper och vad som krävs för en Junior Developer position i Sverige.

STUDENTENS KUNSKAPSGRAF:
{knowledge_graph}

TYPISKA KRAV FÖR JUNIOR DEVELOPER:
- Grundläggande programmering (minst ett språk väl)
- Versionshantering (Git)
- Grundläggande webbutveckling eller systemutveckling
- Databaser (SQL grunderna)
- Problemlösning och algoritmer
- Grundläggande förståelse för mjukvaruutvecklingsprocesser

INSTRUKTIONER:
1. Var EXTREMT ärlig baserat på mastery_scores
2. Om mastery_score är 0, betyder det INGEN praktisk kunskap
3. Analysera varje kravområde separat
4. Ge en total "redo-för-jobb" procent baserat på faktiska scores
5. Var tydlig med vad som saknas

FORMAT:
## Sammanfattning
- **Redo för junior-position**: X% (var ärlig!)
- Förklara kort varför

## Detaljerad gap-analys

### ✅ Uppfyllda krav
Lista endast områden med mastery_score > 0.5

### ⚠️ Delvis uppfyllda krav  
Lista områden med mastery_score 0.3-0.5

### ❌ Saknade kompetenser
Lista områden med mastery_score < 0.3 eller som helt saknas

## Prioriterade utvecklingsområden
1. Mest kritiska gap att täcka
2. Konkreta steg för varje område
3. Tidsuppskattning

## Rekommendationer
- Specifika kurser eller projekt
- Länk till [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/)
- Andra resurser

Kom ihåg: Om studenten har låga scores överallt, var ärlig om att de behöver betydande utveckling innan de är redo.
"""
        
        prompt_formatted = prompt.format(
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False)
        )
        
        try:
            # Lazy-load LLM service
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt_formatted)
            
            # Visa resultat
            st.success("Gap-analys klar!")
            st.markdown(analysis)
            
            # Ladda ner
            st.divider()
            st.download_button(
                label="Ladda ner gap-analys",
                data=analysis,
                file_name=f"gap_analys_junior_dev_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def analyze_program_standard_gap():
    """Analyserar gap mot branschstandard för studentens program"""
    st.markdown("### Gap-analys: Branschstandard för ditt program")
    
    # Låt användaren välja eller ange sitt program
    program = st.text_input(
        "Ange ditt program (t.ex. 'Datateknik', 'Teknisk Matematik', 'Elektroteknik'):",
        placeholder="Datateknik"
    )
    
    if program and st.button("Analysera mot branschstandard", type="primary", use_container_width=True):
        perform_program_standard_gap_analysis(program)


def perform_program_standard_gap_analysis(program: str):
    """Utför gap-analys mot branschstandard för program"""
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner(f"Analyserar dina kompetenser mot branschstandard för {program}..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        prompt = """
Analysera studentens kunskaper mot vad som förväntas av en nyexaminerad från {program} på Chalmers.

STUDENTENS KUNSKAPSGRAF:
{knowledge_graph}

STUDENTENS PROGRAM: {program}

INSTRUKTIONER:
1. Identifiera kärnkompetenser som förväntas från detta program
2. Jämför mot studentens faktiska mastery_scores
3. Var ärlig - om scores är låga, säg det
4. Fokusera på programspecifika förväntningar

FORMAT:
## Programanalys: {program}

### Förväntade kärnkompetenser
Lista vad arbetsgivare förväntar sig från detta program

### Din nuvarande profil
- **Matchning mot förväntningar**: X% (baserat på mastery_scores)
- Förklaring av bedömningen

### Styrkor relativt programmet
Endast områden med mastery_score > 0.5

### Gap mot förväntningar
Områden där du ligger under förväntat

### Utvecklingsplan
Konkreta steg för att nå branschstandard

### Resurser
- [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/)
- Programspecifika rekommendationer
"""
        
        prompt_formatted = prompt.format(
            program=program,
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False)
        )
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt_formatted)
            
            st.success("Analys klar!")
            st.markdown(analysis)
            
            st.divider()
            st.download_button(
                label="Ladda ner analys",
                data=analysis,
                file_name=f"gap_analys_{program.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def analyze_specific_role_gap():
    """Analyserar gap mot specifik roll eller företag"""
    st.markdown("### Gap-analys: Specifik roll eller företag")
    
    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Företag (valfritt):", placeholder="t.ex. Volvo, Ericsson, Spotify")
    with col2:
        role = st.text_input("Roll:", placeholder="t.ex. Backend Developer, Data Engineer")
    
    requirements = st.text_area(
        "Krav från jobbannonsen eller rollbeskrivningen:",
        height=200,
        placeholder="""Klistra in specifika krav, t.ex.:
- 2+ års erfarenhet av Python
- Kunskap inom Docker och Kubernetes
- Erfarenhet av agila metoder
- ..."""
    )
    
    if role and requirements and st.button("Analysera gap", type="primary", use_container_width=True):
        perform_specific_role_gap_analysis(company, role, requirements)


def perform_specific_role_gap_analysis(company: str, role: str, requirements: str):
    """Utför gap-analys mot specifik roll"""
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner(f"Analyserar gap mot {role} på {company if company else 'vald position'}..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        prompt = """
Gör en detaljerad gap-analys mellan studentens kunskaper och kraven för rollen.

ROLL: {role}
FÖRETAG: {company}
SPECIFIKA KRAV:
{requirements}

STUDENTENS KUNSKAPSGRAF:
{knowledge_graph}

INSTRUKTIONER:
1. Matcha varje krav mot studentens kunskaper
2. Var brutal ärlig om mastery_scores
3. Om mastery är 0, säg att kompetensen saknas helt
4. Ge realistisk bedömning av hur långt studenten är från rollen

FORMAT:
## Gap-analys: {role} {company_text}

### Matchning per krav
För varje krav, ange:
- Krav: [kravet]
- Din nivå: [baserat på mastery_score eller "Saknas helt"]
- Gap: [vad som krävs]

### Total matchning: X%
Förklara bedömningen

### Kritiska gap
Vad måste åtgärdas först

### Realistisk tidsplan
Hur lång tid för att bli kvalificerad

### Utvecklingsplan
1. Omedelbara åtgärder
2. Kort sikt (3-6 månader)
3. Lång sikt (6-12 månader)

### Resurser
- [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/)
- Rollspecifika kurser/certifieringar
"""
        
        company_text = f"på {company}" if company else ""
        prompt_formatted = prompt.format(
            role=role,
            company=company or "N/A",
            company_text=company_text,
            requirements=requirements,
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False)
        )
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt_formatted)
            
            st.success("Gap-analys klar!")
            st.markdown(analysis)
            
            st.divider()
            st.download_button(
                label="Ladda ner gap-analys",
                data=analysis,
                file_name=f"gap_analys_{role.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")


def analyze_tech_stack_gap():
    """Analyserar gap mot specifik teknologistack"""
    st.markdown("### Gap-analys: Teknologistack")
    
    # Fördefinierade tech stacks
    predefined_stacks = {
        "MEAN/MERN Stack": ["MongoDB", "Express.js", "Angular/React", "Node.js"],
        "Python Data Science": ["Python", "NumPy", "Pandas", "Scikit-learn", "Jupyter"],
        "Java Enterprise": ["Java", "Spring Boot", "Hibernate", "Maven/Gradle", "Docker"],
        "Cloud Native": ["Kubernetes", "Docker", "Microservices", "CI/CD", "Cloud (AWS/Azure/GCP)"],
        "DevOps": ["Git", "Jenkins/GitLab CI", "Docker", "Kubernetes", "Terraform", "Monitoring"],
        ".NET Stack": ["C#", ".NET Core", "Entity Framework", "Azure", "SQL Server"]
    }
    
    stack_choice = st.selectbox(
        "Välj en fördefinierad stack eller skapa egen:",
        ["Välj..."] + list(predefined_stacks.keys()) + ["Egen stack"]
    )
    
    if stack_choice == "Egen stack":
        custom_stack = st.text_area(
            "Ange teknologier (en per rad):",
            height=150,
            placeholder="React\nNode.js\nPostgreSQL\nDocker\nAWS"
        )
        if custom_stack and st.button("Analysera tech stack", type="primary"):
            tech_list = [tech.strip() for tech in custom_stack.split('\n') if tech.strip()]
            perform_tech_stack_gap_analysis("Custom Stack", tech_list)
    
    elif stack_choice != "Välj..." and st.button("Analysera tech stack", type="primary"):
        perform_tech_stack_gap_analysis(stack_choice, predefined_stacks[stack_choice])


def perform_tech_stack_gap_analysis(stack_name: str, technologies: List[str]):
    """Utför gap-analys mot teknologistack"""
    from config import LITELLM_MODEL
    st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner(f"Analyserar dina kunskaper mot {stack_name}..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        prompt = """
Analysera studentens kunskaper mot en specifik teknologistack.

TEKNOLOGISTACK: {stack_name}
TEKNOLOGIER: {technologies}

STUDENTENS KUNSKAPSGRAF:
{knowledge_graph}

INSTRUKTIONER:
1. Matcha varje teknologi mot studentens kunskaper
2. Bedöm närliggande kunskaper som kan vara relevanta
3. Var ärlig om mastery-nivåer
4. Ge praktiska råd för att lära sig stacken

FORMAT:
## Tech Stack Gap-analys: {stack_name}

### Teknologi-för-teknologi genomgång
För varje teknologi:
- **[Teknologi]**: 
  - Din nivå: [Baserat på mastery eller "Ingen erfarenhet"]
  - Relaterade kunskaper: [Om några finns]
  - Inlärningsuppskattning: [Tid att lära sig grunderna]

### Sammanfattning
- **Stack-täckning**: X% (hur många teknologier du kan)
- **Inlärningskurva**: [Lätt/Medium/Svår baserat på befintliga kunskaper]

### Inlärningsplan
1. Börja här (enklaste steget)
2. Bygg vidare med...
3. Avancerade delar

### Projektidéer
Föreslå 2-3 projekt för att lära sig stacken

### Resurser
- [Chalmers Upskilling Academy](https://www.chalmers.se/aktuellt/nyheter/ny-satsning-pa-upskilling/)
- Stack-specifika kurser och tutorials
"""
        
        prompt_formatted = prompt.format(
            stack_name=stack_name,
            technologies=", ".join(technologies),
            knowledge_graph=json.dumps(knowledge_graph, indent=2, ensure_ascii=False)
        )
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt_formatted)
            
            st.success("Tech stack-analys klar!")
            st.markdown(analysis)
            
            st.divider()
            st.download_button(
                label="Ladda ner analys",
                data=analysis,
                file_name=f"tech_stack_gap_{stack_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Fel vid analys: {str(e)}")