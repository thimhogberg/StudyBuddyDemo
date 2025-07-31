"""
Inställningar-sida som visar alla prompts som används i systemet
"""
import streamlit as st
from utils.session import init_session_state
import random


def generate_demo_repetition_scores():
    """Genererar demo-data för spaced repetition"""
    if not st.session_state.neo4j_service:
        st.error("Ingen databas-anslutning")
        return
    
    try:
        from datetime import datetime, timedelta
        import random
        
        with st.session_state.neo4j_service.driver.session() as session:
            # Nollställ alla repetitions-egenskaper
            session.run("""
                MATCH (c:Koncept)
                WHERE c.id IS NULL
                SET c.id = randomUUID(),
                    c.retention = 1.0,
                    c.difficulty = 0.3,
                    c.interval = 1,
                    c.ease_factor = 2.5,
                    c.review_count = 0,
                    c.last_review = null,
                    c.next_review = null
            """)
            
            # Hämta alla koncept med deras kurser
            result = session.run("""
                MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
                RETURN c.namn as name, c.id as id, k.år as year, k.läsperiod as period
            """)
            
            concept_updates = []
            now = datetime.now()
            
            for record in result:
                year = record['year'] or 1
                
                # Simulera olika repetitionsstatus baserat på år
                if year == 1:
                    # År 1 koncept - mer repetition behövs
                    review_count = random.randint(0, 3)
                    days_since_review = random.randint(7, 30)
                    retention = random.uniform(0.4, 0.7)
                    difficulty = random.uniform(0.4, 0.7)
                elif year == 2:
                    # År 2 koncept - mittemellan
                    review_count = random.randint(2, 5)
                    days_since_review = random.randint(3, 14)
                    retention = random.uniform(0.6, 0.85)
                    difficulty = random.uniform(0.3, 0.5)
                else:
                    # År 3+ koncept - mindre repetition behövs
                    review_count = random.randint(4, 8)
                    days_since_review = random.randint(1, 7)
                    retention = random.uniform(0.8, 0.95)
                    difficulty = random.uniform(0.2, 0.4)
                
                # Beräkna nästa repetition
                if retention < 0.6:
                    days_until_next = random.randint(1, 3)
                elif retention < 0.8:
                    days_until_next = random.randint(3, 7)
                else:
                    days_until_next = random.randint(7, 14)
                
                last_review = now - timedelta(days=days_since_review)
                next_review = now + timedelta(days=days_until_next)
                
                # Uppdatera konceptet
                session.run("""
                    MATCH (c:Koncept {id: $id})
                    SET c.retention = $retention,
                        c.difficulty = $difficulty,
                        c.review_count = $review_count,
                        c.last_review = $last_review,
                        c.next_review = $next_review,
                        c.interval = $interval,
                        c.ease_factor = $ease_factor
                """, 
                    id=record['id'],
                    retention=retention,
                    difficulty=difficulty,
                    review_count=review_count,
                    last_review=last_review.isoformat(),
                    next_review=next_review.isoformat(),
                    interval=days_until_next,
                    ease_factor=2.5 - difficulty
                )
                
                concept_updates.append({
                    'name': record['name'],
                    'retention': retention,
                    'next_review': days_until_next
                })
            
            st.success(f"Genererade repetitions-data för {len(concept_updates)} koncept!")
            st.info("Koncept från tidigare år behöver mer repetition, medan nyare koncept har högre retention.")
            
    except Exception as e:
        st.error(f"Fel vid generering av repetitions-data: {str(e)}")

def generate_demo_mastery_scores(semesters_completed: int):
    """Genererar rimliga mastery scores för demo-syfte"""
    if not st.session_state.neo4j_service:
        st.error("Ingen databas-anslutning")
        return
    
    try:
        with st.session_state.neo4j_service.driver.session() as session:
            # Hämta alla kurser sorterade efter termin och läsperiod
            result = session.run("""
                MATCH (k:Kurs)
                WHERE k.år IS NOT NULL AND k.läsperiod IS NOT NULL
                RETURN k.kurskod as kurskod, k.namn as namn, 
                       k.år as år, k.läsperiod as läsperiod
                ORDER BY k.år, k.läsperiod
            """)
            
            courses = list(result)
            if not courses:
                st.warning("Inga kurser hittades i databasen")
                return
            
            # Beräkna vilka kurser som ska markeras som klarade
            # Anta 2 läsperioder per termin
            courses_to_complete = semesters_completed * 2
            
            # Uppdatera mastery scores för alla koncept
            concept_updates = []
            
            for i, course in enumerate(courses):
                # Bestäm om kursen är klarad baserat på termin
                course_semester = (course['år'] - 1) * 2 + (1 if course['läsperiod'] <= 2 else 2)
                is_completed = course_semester <= semesters_completed
                
                # Hämta koncept för kursen
                concepts_result = session.run("""
                    MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                    RETURN c.namn as namn
                """, kurskod=course['kurskod'])
                
                for concept in concepts_result:
                    if is_completed:
                        # Klarade kurser: hög mastery med lite variation
                        base_score = 0.75
                        variation = random.uniform(-0.15, 0.15)
                        score = max(0.6, min(1.0, base_score + variation))
                    else:
                        # Ej klarade kurser: låg mastery
                        score = random.uniform(0.0, 0.3)
                    
                    concept_updates.append({
                        'namn': concept['namn'],
                        'score': score
                    })
            
            # Uppdatera alla mastery scores
            for update in concept_updates:
                session.run("""
                    MATCH (c:Koncept {namn: $namn})
                    SET c.mastery_score = $score
                """, namn=update['namn'], score=update['score'])
            
            st.success(f"Genererade mastery scores för {len(concept_updates)} koncept baserat på {semesters_completed} klarade terminer!")
            st.info("Klarade kurser har mastery scores mellan 0.6-0.9, medan ej klarade kurser har 0.0-0.3")
            st.rerun()
            
    except Exception as e:
        st.error(f"Fel vid generering av demo-data: {str(e)}")


def render():
    """Renderar inställningssidan"""
    init_session_state()
    
    st.markdown("### Systeminställningar")
    
    # Demo Data Generators
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("Generera Demo-data för Mastery Scores"):
            st.markdown("**För demosyfte:** Generera rimliga mastery scores baserat på hur många terminer som klarats av.")
            
            semesters_completed = st.selectbox(
                "Antal klarade terminer:",
                options=[0, 1, 2, 3, 4, 5, 6],
                help="Välj hur många terminer som ska markeras som klarade"
            )
            
            if st.button("Generera mastery scores", type="primary", key="gen_mastery"):
                generate_demo_mastery_scores(semesters_completed)
    
    with col2:
        with st.expander("Generera Demo-data för Spaced Repetition"):
            st.markdown("**För demosyfte:** Generera rimliga repetitionsdata för alla koncept i grafen.")
            st.markdown("""
            Detta kommer att:
            - Sätta retention baserat på kursens år
            - Simulera tidigare repetitioner
            - Schemalägga nästa repetition
            """)
            
            if st.button("Generera repetitionsdata", type="primary", key="gen_repetition"):
                generate_demo_repetition_scores()
    
    st.divider()
    
    st.markdown("### AI-prompts i systemet")
    st.info("""
    **Obs:** För att ändra prompts behöver du redigera motsvarande kodfiler direkt. 
    Filsökvägar visas för varje prompt nedan.
    """)
    
    # Prompt för konceptextraktion
    with st.expander("Prompt för Konceptextraktion från Kurser"):
        st.markdown("**Fil:** `src/llm_service.py` (rad 13-38)")
        st.markdown("**Användning:** Extraherar koncept när en kurs läggs till i grafen")
        
        st.code("""
COURSE_GRAPH_PROMPT = \"\"\"Du är en expert på att analysera kurser från Chalmers tekniska högskola och extrahera viktiga koncept.

Din uppgift är att analysera kursinformation och identifiera de viktigaste koncepten som lärs ut.

VIKTIGA REGLER:
1. Identifiera upp till {{max_concepts}} huvudkoncept från kursen
2. För varje koncept, ange vilka andra koncept det förutsätter
3. Använd {{language}} för alla namn och beskrivningar
4. Fokusera på tekniska/akademiska koncept, inte administrativa detaljer
5. Håll konceptnamnen korta och beskrivande (max 3-4 ord)

Svara i följande JSON-format:
```json
[
    {
        "namn": "Konceptnamn",
        "beskrivning": "Kort beskrivning av konceptet",
        "förutsätter": ["Koncept1", "Koncept2"]
    }
]
```

KURSINFORMATION:
{{course_info}}

Extrahera koncept från kursen ovan. Om koncept redan finns i grafen, använd samma namn.\"\"\"
        """, language="python")
    
    # Prompt för förutsättningsanalys
    with st.expander("Prompt för Analys av Förutsättningar mellan Kurser"):
        st.markdown("**Fil:** `src/llm_service.py` (rad 41-63)")
        st.markdown("**Användning:** Analyserar beroenden mellan kurser när hela program byggs")
        
        st.code("""
PREREQUISITE_ANALYSIS_PROMPT = \"\"\"Du är en expert på att analysera kunskapsberoenden mellan kurser.

Analysera följande koncept från två kurser och identifiera vilka koncept från Kurs 1 
som är förutsättningar för koncept i Kurs 2.

Koncept från Kurs 1:
{{concepts_course1}}

Koncept från Kurs 2:
{{concepts_course2}}

Svara i JSON-format:
```json
[
    {
        "koncept_kurs2": "Konceptnamn från kurs 2",
        "förutsätter_kurs1": "Konceptnamn från kurs 1"
    }
]
```

Inkludera endast tydliga förutsättningar där kunskapen från kurs 1 verkligen behövs för kurs 2.
Var konservativ - bara inkludera uppenbara beroenden.\"\"\"
        """, language="python")
    
    # Prompt för AI-insikter
    with st.expander("Prompt för AI-insikter och Analys"):
        st.markdown("**Fil:** `pages/analytics.py` (rad 366-376)")
        st.markdown("**Användning:** Genererar AI-insikter baserat på hela kunskapsgrafen")
        
        st.code("""
prompt = f\"\"\"
Analysera följande kunskapsgraf från ett utbildningsprogram på Chalmers.

ANALYSFRÅGA: {analysis_options[selected_analysis]}

KUNSKAPSGRAF:
{graph_json}

Ge en djupgående analys på svenska. Var konkret och ge specifika exempel från grafen.
Strukturera ditt svar med tydliga rubriker.
\"\"\"
        """, language="python")
        
        st.markdown("**Fördefinierade analysfrågor:**")
        st.code("""
- "Progression och struktur": Analysera kursprogressionen och strukturen i grafen. 
  Är kurserna ordnade på ett logiskt sätt? Bygger senare kurser på tidigare kurser på ett vettigt sätt?

- "Konceptspridning": Vilka koncept är mest centrala i utbildningen? Finns det koncept som 
  förekommer i många kurser? Är det några viktiga koncept som saknas?

- "Kursberoenden": Analysera hur väl kurserna bygger på varandra. Finns det kurser som 
  borde ha fler förutsättningar? Är några kurser isolerade?

- "Utbildningshelhet": Ge en övergripande analys av utbildningen. Täcker kurserna tillsammans 
  ett sammanhängande kunskapsområde? Finns det luckor?

- "Förbättringsförslag": Baserat på grafen, vilka förbättringar skulle kunna göras i 
  kursupplägget? Vilka kurser eller koncept saknas?
        """, language="text")
    
    # System prompts
    with st.expander("System Prompts för AI"):
        st.markdown("**Fil:** `pages/analytics.py` (rad 394)")
        st.markdown("**Användning:** Systemprompt för AI-insikter")
        
        st.code("""
"Du är en expert på utbildningsanalys och kursplanering på Chalmers tekniska högskola."
        """, language="text")
        
        st.markdown("**Fil:** `src/llm_service.py` (rad 126)")
        st.markdown("**Användning:** Systemprompt för konceptextraktion")
        
        st.code("""
"Du är en expert på att analysera kursinnehåll och extrahera koncept. Svara alltid med välformaterad JSON."
        """, language="text")
    
    
    # Graph queries
    with st.expander("Neo4j Graph Queries"):
        st.markdown("**Fil:** Olika filer i systemet")
        st.markdown("**Användning:** Frågor för att interagera med kunskapsgrafen")
        
        st.code("""
# Skapa nytt koncept
CREATE (c:Koncept {namn: $namn, beskrivning: $beskrivning, mastery_score: 0})

# Skapa kurs
CREATE (k:Kurs {
    kurskod: $kurskod,
    namn: $namn,
    namn_sv: $namn_sv,
    namn_en: $namn_en,
    beskrivning: $beskrivning,
    syfte: $syfte,
    ai_sammanfattning: $ai_sammanfattning,
    år: $år,
    läsperiod: $läsperiod,
    regel: $regel,
    poäng: $poäng
})

# Skapa relationer
MERGE (k)-[r:INNEHÅLLER]->(c)
MERGE (c1)-[r:FÖRUTSÄTTER]->(c2)

# Hämta grafstatistik
MATCH (n) RETURN 
    sum(CASE WHEN 'Kurs' IN labels(n) THEN 1 ELSE 0 END) as courses,
    sum(CASE WHEN 'Koncept' IN labels(n) THEN 1 ELSE 0 END) as concepts,
    size((MATCH ()-[r]->() RETURN r)) as relations,
    count(n) as total_nodes
        """, language="cypher")
    
    # Study prompts
    with st.expander("Prompts för Study-funktionen"):
        st.markdown("**Fil:** `src/llm_service.py` (rad 40-141)")
        st.markdown("**Användning:** AI-stöd för optimerat lärande")
        
        st.markdown("### Sokratisk dialog")
        st.code("""
SOCRATIC_LEARNING_PROMPT = \"\"\"Du är en expert på sokratisk pedagogik och ska hjälpa studenten att lära sig ett koncept genom att ställa frågor som leder till djupare förståelse.

KONCEPT ATT LÄRA UT: {{concept_name}}
BESKRIVNING: {{concept_description}}
FÖRUTSÄTTNINGAR: {{prerequisites}}
STUDENTENS NUVARANDE KUNSKAPSNIVÅ: {{mastery_score}}

PEDAGOGISKA PRINCIPER:
1. Börja med studentens förkunskaper och bygg vidare därifrån
2. Ställ öppna frågor som uppmuntrar till reflektion
3. Ge ledtrådar snarare än direkta svar
4. Använd konkreta exempel från studentens erfarenhet
5. Uppmuntra kritiskt tänkande och analys
6. Anpassa svårighetsgraden efter studentens svar

INSTRUKTIONER:
- Om mastery_score är 0-0.3: Börja med grundläggande frågor och definitioner
- Om mastery_score är 0.4-0.6: Fokusera på tillämpning och problemlösning
- Om mastery_score är 0.7-1.0: Utmana med avancerade scenarier och kopplingar

Ställ EN pedagogisk fråga i taget. Vänta på studentens svar innan du går vidare.
Avsluta alltid med att fråga om studenten vill ha en till fråga eller känner sig redo att gå vidare.\"\"\"
        """, language="python")
        
        st.markdown("### Guidat lärande")
        st.code("""
GUIDED_LEARNING_PROMPT = \"\"\"Du är en expert på att förklara komplexa koncept på ett tydligt och engagerande sätt.

KONCEPT ATT FÖRKLARA: {{concept_name}}
BESKRIVNING: {{concept_description}}
FÖRUTSÄTTNINGAR: {{prerequisites}}
RELATERADE KURSER: {{related_courses}}
STUDENTENS NUVARANDE KUNSKAPSNIVÅ: {{mastery_score}}

PEDAGOGISKA PRINCIPER:
1. Börja med en översikt av konceptet
2. Förklara varför konceptet är viktigt
3. Ge konkreta exempel och analogier
4. Koppla till förutsättningar som studenten redan kan
5. Visa praktiska tillämpningar
6. Sammanfatta nyckelpunkterna

INSTRUKTIONER:
- Anpassa förklaringen efter studentens kunskapsnivå (mastery_score)
- Använd svenska genomgående
- Håll förklaringen koncis men komplett (max 500 ord)
- Inkludera minst 2 konkreta exempel
- Avsluta med 2-3 kontrollfrågor för att verifiera förståelse

Ge en strukturerad förklaring som bygger på bästa pedagogiska praxis.\"\"\"
        """, language="python")
        
        st.markdown("### Direkt bedömning - Bedömningsfrågor")
        st.code("""
def get_assessment_questions(self, concept_name: str, concept_description: str,
                            question_number: int, difficulty_level: float) -> str:
    \"\"\"
    Genererar bedömningsfrågor för ett koncept
    
    Args:
        concept_name: Namnet på konceptet
        concept_description: Beskrivning av konceptet
        question_number: Vilken fråga i ordningen (1-3)
        difficulty_level: Svårighetsgrad (0.0-1.0)
        
    Returns:
        En bedömningsfråga
    \"\"\"
    difficulty_text = "lätt" if difficulty_level < 0.3 else "medium" if difficulty_level < 0.7 else "svår"
    
    prompt = f\"\"\"Du är en expert på att bedöma studenters kunskap om {concept_name}.

Konceptbeskrivning: {concept_description}

Generera fråga {question_number} av 3 med svårighetsgrad: {difficulty_text}

Frågan ska:
- Vara konkret och tydlig
- Kräva förståelse, inte bara memorering
- Kunna besvaras i 2-5 meningar
- INTE innehålla förklaringar eller ledtrådar
- Vara annorlunda än tidigare frågor

Returnera ENDAST frågan, inget annat.\"\"\"
        """, language="python")
        st.markdown("**Fil:** `src/llm_service.py` (rad 374-422)")
        st.markdown("**Användning:** Genererar unika bedömningsfrågor för direkt bedömning")
        
        st.markdown("### Utvärdering av förståelse")
        st.code("""
UNDERSTANDING_EVALUATION_PROMPT = \"\"\"Du är en expert på att bedöma studenters förståelse av tekniska koncept.

KONCEPT: {{concept_name}}
STUDENTENS SVAR: {{student_answer}}
FÖRVÄNTADE NYCKELKONCEPT: {{key_concepts}}

Analysera studentens svar och bedöm:
1. Förståelsenivå (0.0-1.0)
2. Vilka delar studenten förstår väl
3. Vilka missförstånd eller luckor som finns
4. Rekommenderad nästa steg

Svara i JSON-format:
{
    "understanding_score": 0.0-1.0,
    "strengths": ["vad studenten förstår"],
    "gaps": ["vad som saknas eller är fel"],
    "feedback": "konstruktiv feedback till studenten",
    "ready_to_progress": true/false
}\"\"\"
        """, language="python")
        
        st.markdown("### Hitta nästa koncept")
        st.code("""
NEXT_CONCEPT_PROMPT = \"\"\"Du är en expert på pedagogisk progression och ska identifiera det optimala nästa konceptet för studenten att lära sig.

STUDENTENS KUNSKAPSPROFIL:
{{knowledge_profile}}

TILLGÄNGLIGA KONCEPT:
{{available_concepts}}

PEDAGOGISKA PRINCIPER:
1. Välj koncept där alla eller de flesta förutsättningar är uppfyllda (mastery >= 0.6)
2. Prioritera koncept som är centrala för många andra koncept
3. Balansera utmaning med uppnåelighet
4. Överväg konceptets relevans för studentens kurser

Analysera och rekommendera ETT koncept som nästa steg.

Svara i JSON-format:
{
    "recommended_concept": "konceptnamn",
    "reasoning": "pedagogisk motivering",
    "prerequisites_met": ["lista på uppfyllda förutsättningar"],
    "prerequisites_missing": ["lista på saknade förutsättningar"],
    "difficulty_level": "lätt/medium/svår",
    "will_unlock": ["koncept som blir tillgängliga efter detta"]
}\"\"\"
        """, language="python")
    
    # AI-modell information
    with st.expander("AI-modell inställningar"):
        st.markdown("**Aktuell AI-modell**")
        st.info("Systemet använder för närvarande modellen: **Claude Sonnet 3.7**")
        st.caption("Kontakta administratören för att ändra modell.")
    
    # Job Matching Prompt
    with st.expander("Alumn & Karriär - Jobbannonsmatchning Prompt"):
        st.markdown("**Fil:** `pages/alumn.py`")
        st.markdown("**Rad:** 261-306")
        st.markdown("**Används för:** Matcha studentens kunskapsgraf mot jobbannons")
        
        # Default prompt
        default_job_matching_prompt = """Analysera matchningen mellan en students kunskapsgraf från Chalmers och en jobbannons.

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
        
        # Redigerbar prompt
        job_matching_prompt = st.text_area(
            "Redigera Jobbannonsmatchning Prompt:",
            value=st.session_state.get('job_matching_prompt', default_job_matching_prompt),
            height=600
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Spara Jobbannonsmatchning Prompt"):
                st.session_state.job_matching_prompt = job_matching_prompt
                st.success("Jobbannonsmatchning prompt sparad!")
        
        with col2:
            if st.button("Återställ till standard", key="reset_job_matching"):
                st.session_state.job_matching_prompt = default_job_matching_prompt
                st.success("Återställt till standardprompt")
                st.rerun()
    
    # Graf-uppdatering Prompt
    with st.expander("Alumn & Karriär - Graf-uppdatering Prompt"):
        st.markdown("**Fil:** `pages/alumn.py`")
        st.markdown("**Rad:** 511-562")
        st.markdown("**Används för:** Analysera CV/projekt/certifikat för att uppdatera kunskapsgraf")
        
        # Default prompt
        default_graph_update_prompt = """Analysera följande {doc_type} och identifiera tekniska koncept och kompetenser som personen behärskar.
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
        
        # Redigerbar prompt
        graph_update_prompt = st.text_area(
            "Redigera Graf-uppdatering Prompt:",
            value=st.session_state.get('graph_update_prompt', default_graph_update_prompt),
            height=600
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Spara Graf-uppdatering Prompt"):
                st.session_state.graph_update_prompt = graph_update_prompt
                st.success("Graf-uppdatering prompt sparad!")
        
        with col2:
            if st.button("Återställ till standard", key="reset_graph_update"):
                st.session_state.graph_update_prompt = default_graph_update_prompt
                st.success("Återställt till standardprompt")
                st.rerun()
    
    # Kompetensportfölj Prompt
    with st.expander("Alumn & Karriär - Kompetensportfölj Prompt"):
        st.markdown("**Fil:** `pages/alumn.py`")
        st.markdown("**Rad:** 1024-1050")
        st.markdown("**Används för:** Generera kompetensportfölj baserat på kunskapsgraf")
        
        # Default prompt
        default_portfolio_prompt = """Skapa en ärlig och realistisk sammanställning av en Chalmers-students kunskaper baserat på deras kunskapsgraf.

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
        
        # Redigerbar prompt
        portfolio_prompt = st.text_area(
            "Redigera Kompetensportfölj Prompt:",
            value=st.session_state.get('portfolio_prompt', default_portfolio_prompt),
            height=600
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Spara Kompetensportfölj Prompt"):
                st.session_state.portfolio_prompt = portfolio_prompt
                st.success("Kompetensportfölj prompt sparad!")
        
        with col2:
            if st.button("Återställ till standard", key="reset_portfolio"):
                st.session_state.portfolio_prompt = default_portfolio_prompt
                st.success("Återställt till standardprompt")
                st.rerun()
    
    # Canvas Chat Prompt
    with st.expander("Canvas Chat System Prompt"):
        st.markdown("**Fil:** `pages/canvas_chat.py`")
        st.markdown("**Rad:** 215-230")
        st.markdown("**Används för:** AI-assistent för Canvas kursmaterial")
        
        # Default prompt
        default_prompt = """Du är en hjälpsam AI-assistent som svarar på frågor om kursmaterial.

VIKTIGA REGLER:
1. Basera ALLTID dina svar på det tillhandahållna kursmaterialet
2. Om svaret inte finns i materialet, säg det tydligt
3. Citera relevanta delar från materialet när det är lämpligt
4. Var konkret och specifik i dina svar
5. Om frågan är oklar, be om förtydligande
6. Använd ALDRIG emojis i dina svar

När du svarar:
- Referera till vilket dokument informationen kommer från
- Ge exempel från materialet när det är relevant
- Förklara koncept med kursmaterialets egna ord
- Undvik att lägga till information som inte finns i materialet"""
        
        # Redigerbar prompt
        canvas_prompt = st.text_area(
            "Redigera Canvas Chat System Prompt:",
            value=st.session_state.get('canvas_chat_system_prompt', default_prompt),
            height=400
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Spara Canvas Chat Prompt"):
                st.session_state.canvas_chat_system_prompt = canvas_prompt
                st.success("Canvas Chat prompt sparad!")
        
        with col2:
            if st.button("Återställ till standard"):
                st.session_state.canvas_chat_system_prompt = default_prompt
                st.success("Återställt till standardprompt")
                st.rerun()
    
    # Karriärväg Prompt
    with st.expander("Alumn & Karriär - Karriärvägsanalys Prompt"):
        st.markdown("**Fil:** `pages/alumn.py`")
        st.markdown("**Rad:** 1233-1275")
        st.markdown("**Används för:** Analysera karriärväg baserat på kunskapsgraf")
        
        # Default prompt
        default_career_prompt = """Analysera karriärvägen till {career_name} baserat på studentens kunskapsgraf.

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

Kom ihåg: Om studenten har 0 eller låg mastery på allt relevant, var ärlig om att de är i början av sin resa."""
        
        # Redigerbar prompt
        career_prompt = st.text_area(
            "Redigera Karriärvägsanalys Prompt:",
            value=st.session_state.get('career_analysis_prompt', default_career_prompt),
            height=600
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Spara Karriärväg Prompt"):
                st.session_state.career_analysis_prompt = career_prompt
                st.success("Karriärvägsanalys prompt sparad!")
        
        with col2:
            if st.button("Återställ till standard", key="reset_career"):
                st.session_state.career_analysis_prompt = default_career_prompt
                st.success("Återställt till standardprompt")
                st.rerun()
    
    # Gap-analys Prompts
    with st.expander("Alumn & Karriär - Kompetens-gap Prompts"):
        st.markdown("**Fil:** `pages/alumn.py`")
        st.markdown("**Rad:** 1372-1420 (Junior Developer)")
        st.markdown("**Används för:** Olika typer av gap-analyser")
        
        # Junior Developer Gap prompt
        st.markdown("### Junior Developer Gap-analys")
        default_junior_gap_prompt = """Gör en ärlig gap-analys mellan studentens nuvarande kunskaper och vad som krävs för en Junior Developer position i Sverige.

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

Kom ihåg: Om studenten har låga scores överallt, var ärlig om att de behöver betydande utveckling innan de är redo."""
        
        junior_gap_prompt = st.text_area(
            "Redigera Junior Developer Gap-analys Prompt:",
            value=st.session_state.get('junior_gap_prompt', default_junior_gap_prompt),
            height=500
        )
        
        if st.button("Spara Junior Developer Gap Prompt"):
            st.session_state.junior_gap_prompt = junior_gap_prompt
            st.success("Junior Developer gap-analys prompt sparad!")
    
    # Tips för att ändra prompts
    with st.expander("Hur man ändrar prompts"):
        st.markdown("""
        ### Steg för att ändra prompts:
        
        1. **Öppna relevant fil** i din kodredigerare
        2. **Hitta prompten** med hjälp av radnummer som visas ovan
        3. **Redigera texten** inom trippelcitattecken `\"\"\"`
        4. **Spara filen**
        5. **Starta om applikationen** för att se ändringarna
        
        ### Tips:
        - Behåll variabelplatshållare som `{{variable}}` 
        - Testa med små ändringar först
        - Använd tydlig svenska eller engelska
        - Var specifik i dina instruktioner till AI:n
        
        ### Varning:
        - Ändring av prompts kan påverka systemets funktionalitet
        - Ta backup av originalfiler innan ändringar
        - Testa noggrant efter ändringar
        """)


if __name__ == "__main__":
    render()