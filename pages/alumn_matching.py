"""
Matchningsfunktioner för alumn-modulen
"""
import streamlit as st
import json
from typing import List
from .alumn import get_knowledge_graph_as_json


def render_matching():
    """Visar matchningsfunktioner för alumner, studenter, företag etc."""
    st.subheader("Matchning")
    st.markdown("""
    Hitta relevanta kontakter baserat på din kunskapsgraf. Matcha med alumner för mentorskap,
    andra studenter för grupparbeten, eller företag för exjobb.
    """)
    
    # Viktigt meddelande om demo-data
    st.warning("""
    **OBS: Demonstrationsdata**
    
    Alla personer, företag och forskare som visas i matchningarna är påhittade exempel för att demonstrera funktionaliteten.
    
    För en verklig implementation skulle krävas:
    - En databas med riktiga alumner, studenter och företag
    - Samtycke från personer att delta i matchningstjänsten (GDPR)
    - Integration med Chalmers alumndatabas och företagsregister
    - Verifiering av användaridentiteter
    - System för att hantera kontaktförfrågningar
    
    Detta är en konceptdemonstration av hur en sådan tjänst skulle kunna fungera.
    """)
    
    # Kolla först om Neo4j är konfigurerat
    if not hasattr(st.session_state, 'neo4j_service') or not st.session_state.neo4j_service:
        st.warning("Neo4j databas är inte konfigurerad. Konfigurera databas under inställningar.")
        return
    
    # Kontrollera om användaren har en graf
    from .alumn import has_knowledge_graph
    if not has_knowledge_graph():
        st.warning("Du behöver först bygga en kunskapsgraf under fliken 'Bygg graf' för att kunna använda denna funktion.")
        return
    
    # Val av matchningstyp
    match_type = st.selectbox(
        "Vad vill du matcha mot?",
        [
            "Alumner - Hitta mentorer",
            "Studenter - Hitta gruppmedlemmar",
            "Företag - Hitta exjobbsmöjligheter",
            "Forskare - Hitta handledare"
        ]
    )
    
    if match_type == "Alumner - Hitta mentorer":
        render_alumni_matching()
    elif match_type == "Studenter - Hitta gruppmedlemmar":
        render_student_matching()
    elif match_type == "Företag - Hitta exjobbsmöjligheter":
        render_company_matching()
    elif match_type == "Forskare - Hitta handledare":
        render_researcher_matching()


def render_alumni_matching():
    """Matchar med alumner för mentorskap"""
    st.markdown("### Alumn-matchning för mentorskap")
    st.info("""
    Matcha med alumner som har liknande akademisk bakgrund men som nu arbetar inom områden
    som intresserar dig. Perfekt för karriärvägledning och mentorskap.
    """)
    
    # Mock-data för demonstration
    career_interest = st.text_input(
        "Vilket karriärområde är du intresserad av?",
        placeholder="t.ex. Machine Learning, Embedded Systems, Fintech"
    )
    
    mentorship_focus = st.multiselect(
        "Vad vill du ha hjälp med?",
        [
            "Karriärvägledning",
            "CV-granskning",
            "Intervjuförberedelse",
            "Branschkunskap",
            "Nätverkande",
            "Teknisk utveckling"
        ]
    )
    
    if career_interest and st.button("Hitta matchande alumner", type="primary"):
        find_alumni_matches(career_interest, mentorship_focus)


def find_alumni_matches(career_interest: str, mentorship_focus: List[str]):
    """Hittar matchande alumner baserat på intressen"""
    from config import LITELLM_MODEL
    st.info(f"AI söker matchande alumner med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar din profil och söker matchningar..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Mock-alumner för demonstration
        mock_alumni = [
            {
                "name": "Anna Andersson",
                "graduation_year": 2020,
                "program": "Datateknik",
                "current_role": "Senior ML Engineer",
                "company": "Spotify",
                "expertise": ["Machine Learning", "Python", "Distributed Systems"]
            },
            {
                "name": "Erik Eriksson",
                "graduation_year": 2019,
                "program": "Teknisk Matematik",
                "current_role": "Data Scientist",
                "company": "Volvo Cars",
                "expertise": ["Deep Learning", "Computer Vision", "C++"]
            },
            {
                "name": "Maria Nilsson",
                "graduation_year": 2021,
                "program": "Datateknik",
                "current_role": "ML Researcher",
                "company": "Chalmers AI Lab",
                "expertise": ["NLP", "Transformers", "Research"]
            }
        ]
        
        prompt = f"""
Analysera studentens kunskapsgraf och matcha mot potentiella alumn-mentorer.

STUDENTENS KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

KARRIÄRINTRESSE: {career_interest}
MENTORSKAPSFOKUS: {', '.join(mentorship_focus)}

TILLGÄNGLIGA ALUMNER:
{json.dumps(mock_alumni, indent=2, ensure_ascii=False)}

INSTRUKTIONER:
1. Analysera studentens nuvarande kunskaper
2. Matcha mot alumner baserat på:
   - Gemensam akademisk grund
   - Alumnens expertis inom karriärintresset
   - Potential att hjälpa med mentorskapsfokus
3. Rangordna matchningar med motivering
4. Var ärlig om matchningskvalitet

FORMAT:
För varje matchning:
### [Alumnens namn] - [Matchningsgrad]%
**Roll**: [Nuvarande roll] på [Företag]
**Examen**: [Program], [År]
**Expertområden**: [Lista]

**Varför denna matchning?**
[Förklara gemensamma grunder och hur alumnen kan hjälpa]

**Gemensamma kunskapsområden**:
[Lista koncept som både student och alumn har]

**Vad alumnen kan bidra med**:
[Specifikt för studentens behov]
"""
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt)
            
            st.success("Matchningar hittade!")
            st.markdown(analysis)
            
            # Kontaktförslag
            st.divider()
            st.markdown("### Nästa steg")
            st.info("""
            **Hur du kontaktar alumner:**
            1. Använd LinkedIn för att hitta personen
            2. Skicka ett personligt meddelande där du:
               - Presenterar dig som Chalmers-student
               - Förklarar varför just denna person
               - Ber om ett kort möte (15-30 min)
            3. Var specifik med vad du vill diskutera
            """)
            
        except Exception as e:
            st.error(f"Fel vid matchning: {str(e)}")


def render_student_matching():
    """Matchar med andra studenter för grupparbeten"""
    st.markdown("### Student-matchning för grupparbeten")
    st.info("""
    Hitta studenter med kompletterande eller liknande kunskaper för grupprojekt.
    Välj om du vill ha någon som kompletterar dina svagheter eller förstärker dina styrkor.
    """)
    
    project_type = st.text_input(
        "Beskriv projektet eller kursen:",
        placeholder="t.ex. 'Webbutvecklingsprojekt i DAT076' eller 'AI-projekt med fokus på NLP'"
    )
    
    match_strategy = st.radio(
        "Matchningsstrategi:",
        [
            "Kompletterande kunskaper - Hitta någon som kan det jag inte kan",
            "Liknande kunskaper - Hitta någon på samma nivå för jämn arbetsfördelning",
            "Blandad - Några likheter, några olikheter"
        ]
    )
    
    group_size = st.number_input("Önskad gruppstorlek:", min_value=2, max_value=6, value=3)
    
    if project_type and st.button("Hitta gruppmedlemmar", type="primary"):
        find_student_matches(project_type, match_strategy, group_size)


def find_student_matches(project_type: str, match_strategy: str, group_size: int):
    """Hittar matchande studenter för grupparbete"""
    from config import LITELLM_MODEL
    st.info(f"AI söker lämpliga gruppmedlemmar med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar kunskapsprofiler..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Mock-studenter för demonstration
        mock_students = [
            {
                "id": "student_1",
                "program": "Datateknik",
                "year": 3,
                "strengths": ["Frontend", "React", "UX Design"],
                "weaknesses": ["Backend", "Databaser"],
                "average_mastery": 0.65
            },
            {
                "id": "student_2",
                "program": "Datateknik",
                "year": 3,
                "strengths": ["Backend", "Python", "Databaser"],
                "weaknesses": ["Frontend", "Design"],
                "average_mastery": 0.72
            },
            {
                "id": "student_3",
                "program": "Informationsteknik",
                "year": 2,
                "strengths": ["Fullstack", "JavaScript", "Agile"],
                "weaknesses": ["Algoritmer", "Matematik"],
                "average_mastery": 0.58
            }
        ]
        
        prompt = f"""
Analysera och matcha studenter för grupparbete.

DIN KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

PROJEKT: {project_type}
MATCHNINGSSTRATEGI: {match_strategy}
ÖNSKAD GRUPPSTORLEK: {group_size}

TILLGÄNGLIGA STUDENTER:
{json.dumps(mock_students, indent=2, ensure_ascii=False)}

INSTRUKTIONER:
1. Analysera vilka kunskaper som behövs för projektet
2. Baserat på strategin, hitta lämpliga gruppmedlemmar
3. För "Kompletterande": hitta de som är starka där du är svag
4. För "Liknande": hitta de med samma kunskapsnivå
5. Föreslå en optimal gruppsammansättning

FORMAT:
## Projektanalys
Vilka kunskaper behövs: [lista]

## Rekommenderad grupp

### Medlem 1: Student [ID]
- **Styrkor som bidrar**: [lista]
- **Matchning**: X% ([strategi]-match)
- **Bidrag till gruppen**: [förklaring]

### Gruppens samlade kompetens
- Täckta områden: [lista]
- Eventuella luckor: [lista]
- Balans: [bedömning]
"""
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt)
            
            st.success("Gruppförslag klart!")
            st.markdown(analysis)
            
        except Exception as e:
            st.error(f"Fel vid matchning: {str(e)}")


def render_company_matching():
    """Matchar med företag för exjobb"""
    st.markdown("### Företagsmatchning för exjobb")
    st.info("""
    Hitta företag som erbjuder exjobb inom dina intresseområden och som matchar din kunskapsprofil.
    """)
    
    thesis_area = st.text_input(
        "Vilket område vill du skriva exjobb inom?",
        placeholder="t.ex. 'Machine Learning inom hälsovård' eller 'Embedded systems för fordonsindustrin'"
    )
    
    company_preferences = st.multiselect(
        "Typ av företag:",
        [
            "Startup",
            "Storföretag",
            "Forskningsinstitut",
            "Konsultbolag",
            "Tech-företag",
            "Industriföretag"
        ]
    )
    
    location_pref = st.selectbox(
        "Önskad plats:",
        ["Göteborg", "Stockholm", "Malmö", "Remote", "Utomlands", "Flexibel"]
    )
    
    if thesis_area and st.button("Hitta matchande företag", type="primary"):
        find_company_matches(thesis_area, company_preferences, location_pref)


def find_company_matches(thesis_area: str, company_preferences: List[str], location: str):
    """Hittar matchande företag för exjobb"""
    from config import LITELLM_MODEL
    st.info(f"AI söker lämpliga exjobbsföretag med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar din profil mot företag..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Mock-företag för demonstration
        mock_companies = [
            {
                "name": "Volvo Cars",
                "type": "Storföretag",
                "location": "Göteborg",
                "thesis_areas": ["Autonomous Driving", "Machine Learning", "Embedded Systems"],
                "requirements": ["C++", "Python", "Control Theory"]
            },
            {
                "name": "Recorded Future",
                "type": "Tech-företag",
                "location": "Göteborg",
                "thesis_areas": ["NLP", "Threat Intelligence", "Machine Learning"],
                "requirements": ["Python", "NLP", "Security"]
            },
            {
                "name": "Einride",
                "type": "Startup",
                "location": "Göteborg/Stockholm",
                "thesis_areas": ["Autonomous Vehicles", "Fleet Optimization", "AI"],
                "requirements": ["Python", "Optimization", "Robotics"]
            }
        ]
        
        prompt = f"""
Matcha studentens profil mot företag för exjobb.

STUDENTENS KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

ÖNSKAT EXJOBBSOMRÅDE: {thesis_area}
FÖRETAGSTYP: {', '.join(company_preferences) if company_preferences else 'Alla'}
PLATS: {location}

TILLGÄNGLIGA FÖRETAG:
{json.dumps(mock_companies, indent=2, ensure_ascii=False)}

INSTRUKTIONER:
1. Analysera studentens kunskaper mot företagens behov
2. Matcha baserat på:
   - Relevans för önskat exjobbsområde
   - Studentens faktiska kunskaper (mastery_scores)
   - Företagstyp och plats
3. Var ärlig om matchningsgrad
4. Ge konkreta förslag på exjobbsämnen

FORMAT:
För varje matchande företag:

### [Företagsnamn] - [Matchning]%
**Typ**: [Företagstyp] | **Plats**: [Plats]
**Exjobbsområden**: [Lista]

**Matchningsanalys**:
- Dina relevanta kunskaper: [lista med mastery_scores]
- Saknade kunskaper: [lista]
- Matchningsgrad: [ärlig bedömning]

**Möjliga exjobbsämnen**:
1. [Konkret förslag baserat på överlapp]
2. [Annat förslag]

**Förberedelser**:
- Vad du bör läsa på om
- Kurser att ta innan
"""
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt)
            
            st.success("Företagsmatchningar klara!")
            st.markdown(analysis)
            
            # Tips för kontakt
            st.divider()
            st.markdown("### Tips för att kontakta företag")
            st.info("""
            1. Besök företagets karriärsida för exjobbsinformation
            2. Kontakta HR eller R&D-avdelningen direkt
            3. Använd LinkedIn för att hitta Chalmers-alumner på företaget
            4. Delta i företagspresentationer på campus
            5. Kontakta din programansvarige för introduktioner
            """)
            
        except Exception as e:
            st.error(f"Fel vid matchning: {str(e)}")


def render_researcher_matching():
    """Matchar med forskare för handledning"""
    st.markdown("### Forskarmatchning för handledning")
    st.info("""
    Hitta forskare på Chalmers som matchar dina intressen för potentiell handledning
    av kandidat- eller masterarbete.
    """)
    
    research_interest = st.text_area(
        "Beskriv ditt forskningsintresse:",
        height=100,
        placeholder="t.ex. 'Jag är intresserad av att tillämpa maskininlärning på medicinska bilder för att upptäcka cancer i tidigt stadium'"
    )
    
    level = st.selectbox(
        "Nivå:",
        ["Kandidatarbete", "Masterarbete", "Forskningsprojekt"]
    )
    
    department_pref = st.multiselect(
        "Föredragna institutioner:",
        [
            "Data- och informationsteknik",
            "Elektroteknik",
            "Matematiska vetenskaper",
            "Fysik",
            "Kemi och kemiteknik",
            "Biologi och bioteknik"
        ]
    )
    
    if research_interest and st.button("Hitta matchande forskare", type="primary"):
        find_researcher_matches(research_interest, level, department_pref)


def find_researcher_matches(research_interest: str, level: str, departments: List[str]):
    """Hittar matchande forskare"""
    from config import LITELLM_MODEL
    st.info(f"AI söker lämpliga handledare med modell: **{LITELLM_MODEL}**")
    
    with st.spinner("Analyserar forskningsintressen..."):
        knowledge_graph = get_knowledge_graph_as_json()
        
        # Mock-forskare för demonstration
        mock_researchers = [
            {
                "name": "Prof. Lisa Svensson",
                "department": "Data- och informationsteknik",
                "research_areas": ["Machine Learning", "Medical Imaging", "Deep Learning"],
                "current_projects": ["AI for Cancer Detection", "Explainable AI in Healthcare"]
            },
            {
                "name": "Dr. Johan Berg",
                "department": "Elektroteknik",
                "research_areas": ["Signal Processing", "Medical Devices", "Embedded ML"],
                "current_projects": ["Wearable Health Monitoring", "Edge AI"]
            },
            {
                "name": "Prof. Anna Chen",
                "department": "Matematiska vetenskaper",
                "research_areas": ["Statistical Learning", "Bioinformatics", "Optimization"],
                "current_projects": ["Statistical Methods for Genomics", "ML Theory"]
            }
        ]
        
        prompt = f"""
Matcha student med forskare för handledning.

STUDENTENS KUNSKAPSGRAF:
{json.dumps(knowledge_graph, indent=2, ensure_ascii=False)}

FORSKNINGSINTRESSE: {research_interest}
NIVÅ: {level}
FÖREDRAGNA INSTITUTIONER: {', '.join(departments) if departments else 'Alla'}

TILLGÄNGLIGA FORSKARE:
{json.dumps(mock_researchers, indent=2, ensure_ascii=False)}

INSTRUKTIONER:
1. Analysera överlapp mellan studentens intresse och forskarnas områden
2. Bedöm studentens förberedelse baserat på kunskapsgraf
3. Matcha baserat på:
   - Forskningsområde
   - Studentens kunskaper
   - Nivå (kandidat/master)
4. Var ärlig om studentens beredskap

FORMAT:
För varje matchande forskare:

### [Forskarens namn] - [Matchning]%
**Institution**: [Institution]
**Forskningsområden**: [Lista]
**Pågående projekt**: [Lista]

**Matchningsanalys**:
- Överlapp med ditt intresse: [förklaring]
- Dina relevanta kunskaper: [lista med mastery_scores]
- Kunskaper att stärka: [lista]

**Möjliga forskningsriktningar**:
1. [Konkret förslag]
2. [Alternativ riktning]

**Förberedelser innan kontakt**:
- Kurser att ta: [lista]
- Papers att läsa: [förslag]
- Färdigheter att utveckla: [lista]
"""
        
        try:
            if 'llm_service' not in st.session_state:
                from src.llm_service import LLMService
                st.session_state.llm_service = LLMService()
            
            analysis = st.session_state.llm_service.query(prompt)
            
            st.success("Forskarmatchningar klara!")
            st.markdown(analysis)
            
            # Kontakttips
            st.divider()
            st.markdown("### Tips för att kontakta forskare")
            st.info("""
            1. Läs forskarens senaste publikationer
            2. Skriv ett kortfattat mail som visar:
               - Att du läst om deras forskning
               - Varför just deras område intresserar dig
               - Vad du kan bidra med
            3. Bifoga kort CV och betygsutdrag
            4. Var beredd på att diskutera konkreta idéer
            5. Boka möte via deras kalenderbokningssystem
            """)
            
        except Exception as e:
            st.error(f"Fel vid matchning: {str(e)}")