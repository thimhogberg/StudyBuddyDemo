"""
LLM-service för Chalmers Course Graph
Hanterar all AI-interaktion för konceptextraktion från kurser
"""
import re
import json
from typing import Dict, List, Optional, Tuple
from litellm import completion
from config import LITELLM_API_KEY, LITELLM_BASE_URL, LITELLM_MODEL


# Prompt för att bygga kunskapsgraf för kurser
COURSE_GRAPH_PROMPT = """Du är en expert på att analysera kurser från Chalmers tekniska högskola och extrahera viktiga koncept.

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

Extrahera koncept från kursen ovan. Om koncept redan finns i grafen, använd samma namn."""

# Prompt för sokratiskt lärande
SOCRATIC_LEARNING_PROMPT = """Du är en expert på sokratisk pedagogik och ska hjälpa studenten att lära sig ett koncept genom att ställa frågor som leder till djupare förståelse.

KONCEPT ATT LÄRA UT: {{concept_name}}
BESKRIVNING: {{concept_description}}
FÖRUTSÄTTNINGAR: {{prerequisites}}
STUDENTENS NUVARANDE KUNSKAPSNIVÅ: {{mastery_score}}
KONCEPT SOM BYGGER PÅ DETTA: {{dependent_concepts}}
VARFÖR DETTA ÄR VIKTIGT: {{importance_reason}}

HELA KUNSKAPSGRAFEN:
{{knowledge_graph}}

STUDENTINFORMATION:
{{student_info}}

PEDAGOGISKA PRINCIPER:
1. Använd ALLTID hela kunskapsgrafen för att se studentens kompletta kunskapsprofil
2. Anpassa frågor baserat på studentens mastery scores för relaterade koncept
3. Om studenten har hög mastery (>0.7) på relaterade koncept, använd dessa som byggstenar
4. Om studenten har låg mastery (<0.3) på förutsättningar, förklara dessa först
5. Ta hänsyn till studentens preferenser och studiemönster från studentinformationen

DYNAMISK ANPASSNING BASERAT PÅ MASTERY:
- 0.0-0.2: Mycket grundläggande, definitioner, varför konceptet existerar
- 0.2-0.4: Enkla exempel, kopplingar till vardagen, bygga intuition
- 0.4-0.6: Tillämpningar, problemlösning, jämförelser
- 0.6-0.8: Avancerade scenarier, integration med andra koncept
- 0.8-1.0: Expertfrågor, edge cases, forskningsfronten

FORMAT FÖR DITT SVAR:
1. Analysera först studentens kunskapsprofil från grafen (visa INTE denna analys)
2. Välj pedagogisk nivå baserat på FAKTISK mastery, inte bara det aktuella konceptet
3. Lägg till EN ny insikt anpassad till studentens exakta nivå
4. Koppla till koncept där studenten har hög mastery
5. Ställ EN fråga som är perfekt kalibrerad för studentens nivå

VIKTIGT: Använd ALLTID hela kunskapsgrafen för att ge maximalt personaliserad undervisning."""

# Prompt för guidat lärande
GUIDED_LEARNING_PROMPT = """Du är en expert på att förklara komplexa koncept på ett tydligt och engagerande sätt.

KONCEPT ATT FÖRKLARA: {{concept_name}}
BESKRIVNING: {{concept_description}}
FÖRUTSÄTTNINGAR: {{prerequisites}}
RELATERADE KURSER: {{related_courses}}
STUDENTENS NUVARANDE KUNSKAPSNIVÅ: {{mastery_score}}

HELA KUNSKAPSGRAFEN:
{{knowledge_graph}}

STUDENTINFORMATION:
{{student_info}}

PEDAGOGISKA PRINCIPER:
1. Analysera först hela kunskapsgrafen för att förstå studentens kompletta profil
2. Identifiera vilka relaterade koncept studenten behärskar väl (>0.7) och bygg på dessa
3. Identifiera kunskapsluckor och adressera dem proaktivt
4. Anpassa språk, exempel och förklaringsdjup baserat på studentens generella nivå

DYNAMISK ANPASSNING:
- Om studenten har låg mastery (<0.3) på de flesta koncept: Använd vardagsspråk, undvik jargong, ge många enkla exempel
- Om studenten har blandad mastery: Bygg broar mellan det kända och det okända
- Om studenten har hög mastery (>0.7) på många koncept: Använd teknisk terminologi, ge avancerade exempel

STRUKTUR ANPASSAD EFTER NIVÅ:

För nybörjare (genomsnittlig mastery <0.3):
1. Varför behöver vi detta koncept? (praktisk motivation)
2. Enkel analogi från vardagen
3. Steg-för-steg-förklaring med bilder/diagram i text
4. Två enkla exempel
5. Sammanfattning i punktform

För mellannivå (genomsnittlig mastery 0.3-0.7):
1. Snabb översikt och koppling till kända koncept
2. Teknisk förklaring med rätt terminologi
3. Jämförelse med liknande koncept
4. Praktiska tillämpningar
5. Vanliga missförstånd att undvika

För avancerade (genomsnittlig mastery >0.7):
1. Direkt teknisk definition
2. Teoretisk grund och härledning
3. Avancerade tillämpningar och edge cases
4. Kopplingar till forskningsfronten
5. Utmaningar och öppna problem

AVSLUTA MED:
- 3 frågor perfekt anpassade till studentens faktiska nivå
- Frågorna ska testa förståelse, inte bara memorering

VIKTIGT: Använd ALLTID hela kunskapsgrafen för maximal personalisering."""

# Prompt för att utvärdera studentens förståelse
UNDERSTANDING_EVALUATION_PROMPT = """Du är en expert på att bedöma studenters förståelse av tekniska koncept.

KONCEPT: {{concept_name}}
STUDENTENS SVAR: {{student_answer}}
FÖRVÄNTADE NYCKELKONCEPT: {{key_concepts}}

HELA KUNSKAPSGRAFEN:
{{knowledge_graph}}

STUDENTINFORMATION:
{{student_info}}

DYNAMISKA BEDÖMNINGSKRITERIER BASERAT PÅ STUDENTPROFIL:

1. Analysera först studentens generella kunskapsnivå från grafen
2. Justera förväntningarna baserat på var studenten befinner sig i sin lärresa

För nybörjare (genomsnittlig mastery <0.3 i grafen):
- 0.0-0.2: Helt fel eller ingen förståelse
- 0.3-0.4: Visar försök att förstå, men missuppfattningar
- 0.5-0.6: Grundläggande korrekt förståelse
- 0.7-0.8: God förståelse för nybörjarnivå
- 0.9-1.0: Exceptionell förståelse för någon på denna nivå

För mellannivå (genomsnittlig mastery 0.3-0.7):
- 0.0-0.2: Helt fel eller ingen förståelse
- 0.3-0.4: Ytlig förståelse utan djup
- 0.5-0.6: Korrekt men begränsad förståelse
- 0.7-0.8: God förståelse med exempel
- 0.9-1.0: Djup förståelse med kopplingar

För avancerade (genomsnittlig mastery >0.7):
- 0.0-0.2: Allvarliga brister i förståelse
- 0.3-0.4: Under förväntan för denna nivå
- 0.5-0.6: Acceptabel men inte imponerande
- 0.7-0.8: Förväntad nivå med god teknisk förståelse
- 0.9-1.0: Expertförståelse med innovation

VIKTIGT: 
- Ta hänsyn till studentens förutsättningar från grafen
- Bedöm framsteg relativt till studentens utgångsläge
- Var uppmuntrande för nybörjare men kräv mer av avancerade

Analysera studentens svar och bedöm:
1. Förståelsenivå (0.0-1.0) - VAR STRIKT!
2. Vilka delar studenten förstår väl
3. Vilka missförstånd eller luckor som finns
4. Rekommenderad nästa steg

Svara ENDAST med välformaterad JSON enligt följande format (inga kommentarer eller extra text):
```json
{
    "understanding_score": 0.5,
    "strengths": ["lista med vad studenten förstår väl"],
    "gaps": ["lista med vad som saknas eller är fel"],
    "feedback": "Konstruktiv feedback till studenten på svenska",
    "ready_to_progress": false
}
```

VIKTIGT: 
- understanding_score ska vara ett decimaltal mellan 0.0 och 1.0
- strengths och gaps ska vara arrayer med strängar
- feedback ska vara en sträng med konstruktiv feedback
- ready_to_progress ska vara true eller false (boolean)
- Returnera ENDAST JSON, ingen annan text"""

# Prompt för att hitta nästa koncept att lära sig
NEXT_CONCEPT_PROMPT = """Du är en expert på pedagogisk progression och ska identifiera det optimala nästa konceptet för studenten att lära sig.

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
```json
{
    "recommended_concept": "konceptnamn",
    "reasoning": "pedagogisk motivering",
    "prerequisites_met": ["lista på uppfyllda förutsättningar"],
    "prerequisites_missing": ["lista på saknade förutsättningar"],
    "difficulty_level": "lätt/medium/svår",
    "will_unlock": ["koncept som blir tillgängliga efter detta"]
}
```"""

# Prompt för att analysera förutsättningar mellan kurser
PREREQUISITE_ANALYSIS_PROMPT = """Du är en expert på att analysera kunskapsberoenden mellan kurser.

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
Var konservativ - bara inkludera uppenbara beroenden."""


class LLMService:
    """Service för att hantera LLM-interaktioner"""
    
    def __init__(self, neo4j_service=None):
        """Initialiserar LLM-servicen"""
        self.api_key = LITELLM_API_KEY
        self.base_url = LITELLM_BASE_URL
        self.model = LITELLM_MODEL
        
        # Använd neo4j_service om den skickas med, annars försök hämta från session state
        if neo4j_service:
            self.neo4j_service = neo4j_service
        else:
            try:
                import streamlit as st
                if 'neo4j_service' in st.session_state:
                    self.neo4j_service = st.session_state.neo4j_service
                else:
                    self.neo4j_service = None
            except:
                self.neo4j_service = None
    
    def _get_knowledge_graph_context(self) -> str:
        """Hämtar hela kunskapsgrafen med alla koncept och mastery scores"""
        if not self.neo4j_service:
            return "Kunskapsgraf ej tillgänglig"
        
        try:
            with self.neo4j_service.driver.session() as session:
                # Hämta alla koncept med mastery scores
                result = session.run("""
                    MATCH (c:Koncept)
                    OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dependent:Koncept)
                    OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
                    RETURN c.namn as namn, 
                           c.beskrivning as beskrivning,
                           COALESCE(c.mastery_score, 0.0) as mastery_score,
                           collect(DISTINCT prereq.namn) as förutsättningar,
                           collect(DISTINCT dependent.namn) as beroende_koncept
                    ORDER BY c.mastery_score DESC
                """)
                
                concepts = []
                for record in result:
                    concepts.append(f"- {record['namn']} (mastery: {record['mastery_score']:.2f})")
                    if record['förutsättningar']:
                        concepts.append(f"  Förutsätter: {', '.join(filter(None, record['förutsättningar']))}")
                
                return "KUNSKAPSGRAF:\n" + "\n".join(concepts)
        except Exception as e:
            return f"Kunde inte hämta kunskapsgraf: {str(e)}"
    
    def _get_student_info(self) -> str:
        """Hämtar studentinformation från grafen"""
        if not self.neo4j_service:
            return "Studentinformation ej tillgänglig"
        
        try:
            with self.neo4j_service.driver.session() as session:
                # Hämta studentnod om den finns
                result = session.run("""
                    MATCH (s:Student)
                    RETURN s
                    LIMIT 1
                """)
                
                student = result.single()
                if student:
                    props = dict(student['s'])
                    info = []
                    if 'preferred_learning_style' in props:
                        info.append(f"Föredragen lärstil: {props['preferred_learning_style']}")
                    if 'study_pace' in props:
                        info.append(f"Studietakt: {props['study_pace']}")
                    if 'focus_areas' in props:
                        info.append(f"Fokusområden: {props['focus_areas']}")
                    
                    return "STUDENTINFORMATION:\n" + "\n".join(info) if info else "Ingen specifik studentinformation"
                else:
                    return "Ingen studentprofil hittad"
        except Exception as e:
            return f"Kunde inte hämta studentinfo: {str(e)}"
    
    def query(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generell query-metod för LLM
        
        Args:
            prompt: Prompten att skicka till LLM
            temperature: Temperatur för generering (0-1)
            
        Returns:
            LLM:s svar som sträng
        """
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Fel vid LLM-query: {str(e)}")
            return f"Kunde inte generera svar: {str(e)}"
    
    def extract_json_from_response(self, llm_response: str) -> Optional[List[Dict]]:
        """
        Extraherar JSON från LLM-svar
        
        Args:
            llm_response: Svar från LLM
            
        Returns:
            Parsed JSON eller None
        """
        # Försök hitta JSON-block
        json_match = re.search(r'```(?:json)?\n(.*?)```', llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Försök hitta JSON mellan { och }
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Försök hitta JSON mellan [ och ]
                json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    # Försök använda hela svaret som JSON
                    json_str = llm_response.strip()
        
        try:
            result = json.loads(json_str)
            # Se till att vi har rätt format
            if isinstance(result, dict):
                if "koncept" in result:
                    return result["koncept"]
                elif "concepts" in result:
                    return result["concepts"]
                else:
                    # För evaluate_understanding returnera dict direkt
                    if all(key in result for key in ["understanding_score", "feedback"]):
                        return result
                    return [result]
            return result
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Försökte parsa: {json_str[:200]}...")
            return None
    
    def extract_concepts(self, course_info: str, existing_graph: str = "", max_concepts: int = 10, language: str = "Svenska") -> List[Dict[str, any]]:
        """
        Extraherar koncept från kursinformation
        
        Args:
            course_info: Fullständig kursinformation som text
            existing_graph: Befintlig graf som JSON-sträng
            
        Returns:
            Lista med koncept och deras beskrivningar
        """
        prompt = COURSE_GRAPH_PROMPT.replace("{{course_info}}", course_info)
        prompt = prompt.replace("{{existing_graph}}", existing_graph or "Grafen är tom.")
        prompt = prompt.replace("{{max_concepts}}", str(max_concepts))
        prompt = prompt.replace("{{language}}", language)
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en expert på att analysera kursinnehåll och extrahera koncept. Svara alltid med välformaterad JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Låg temperatur för mer konsistenta resultat
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            llm_response = response.choices[0].message.content
            concepts = self.extract_json_from_response(llm_response)
            
            if concepts is None:
                print("Kunde inte extrahera koncept från LLM-svar")
                return []
            
            # Validera och rensa koncept
            valid_concepts = []
            for concept in concepts:
                if isinstance(concept, dict) and "namn" in concept:
                    # Se till att förutsätter är en lista
                    if "förutsätter" not in concept:
                        concept["förutsätter"] = []
                    elif not isinstance(concept["förutsätter"], list):
                        concept["förutsätter"] = []
                    
                    valid_concepts.append(concept)
            
            # Begränsa till max_concepts
            return valid_concepts[:max_concepts]
            
        except Exception as e:
            print(f"Fel vid LLM-anrop för konceptextraktion: {str(e)}")
            return []
    
    def analyze_prerequisites(self, concepts_from_course1: List[str], 
                            concepts_from_course2: List[str]) -> List[Tuple[str, str]]:
        """
        Analyserar vilka koncept från kurs1 som förutsätts av koncept i kurs2
        
        Args:
            concepts_from_course1: Lista med konceptnamn från kurs 1
            concepts_from_course2: Lista med konceptnamn från kurs 2
            
        Returns:
            Lista med tupler (koncept_från_kurs2, förutsätter_koncept_från_kurs1)
        """
        if not concepts_from_course1 or not concepts_from_course2:
            return []
        
        # Begränsa antal koncept för att undvika för stora prompts
        concepts_from_course1 = concepts_from_course1[:20]
        concepts_from_course2 = concepts_from_course2[:20]
        
        prompt = PREREQUISITE_ANALYSIS_PROMPT.replace(
            "{{concepts_course1}}", ", ".join(concepts_from_course1)
        ).replace(
            "{{concepts_course2}}", ", ".join(concepts_from_course2)
        )
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en expert på att analysera kunskapsberoenden. Svara alltid med välformaterad JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            llm_response = response.choices[0].message.content
            relations = self.extract_json_from_response(llm_response)
            
            if relations is None:
                return []
            
            # Konvertera till tupler
            result = []
            for rel in relations:
                if isinstance(rel, dict) and "koncept_kurs2" in rel and "förutsätter_kurs1" in rel:
                    # Validera att koncepten faktiskt finns i listorna
                    if (rel["koncept_kurs2"] in concepts_from_course2 and 
                        rel["förutsätter_kurs1"] in concepts_from_course1):
                        result.append((rel["koncept_kurs2"], rel["förutsätter_kurs1"]))
            
            return result
            
        except Exception as e:
            print(f"Fel vid prerequisite-analys: {str(e)}")
            return []
    
    def validate_concept_name(self, name: str) -> bool:
        """
        Validerar att ett konceptnamn är rimligt
        
        Args:
            name: Konceptnamn att validera
            
        Returns:
            True om namnet är giltigt
        """
        if not name or not isinstance(name, str):
            return False
        
        # Kontrollera längd
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Kontrollera att det inte bara är whitespace
        if not name.strip():
            return False
        
        return True
    
    def get_assessment_questions(self, concept_name: str, concept_description: str,
                                question_number: int, difficulty_level: float,
                                additional_context: str = None) -> str:
        """
        Genererar bedömningsfrågor för ett koncept
        
        Args:
            concept_name: Namnet på konceptet
            concept_description: Beskrivning av konceptet
            question_number: Vilken fråga i ordningen (1-3)
            difficulty_level: Svårighetsgrad (0.0-1.0)
            
        Returns:
            En bedömningsfråga
        """
        difficulty_text = "lätt" if difficulty_level < 0.3 else "medium" if difficulty_level < 0.7 else "svår"
        
        # Definiera olika frågetyper för varje frågenummer för att säkerställa variation
        question_types = {
            1: {
                "lätt": "en grundläggande definitionsfråga",
                "medium": "en fråga om huvudprinciperna",
                "svår": "en fråga om teoretiska grunder"
            },
            2: {
                "lätt": "en fråga om praktisk tillämpning",
                "medium": "en problemlösningsfråga",
                "svår": "en fråga om avancerad implementation"
            },
            3: {
                "lätt": "en jämförelsefråga med relaterade koncept",
                "medium": "en analysfråga om för- och nackdelar",
                "svår": "en syntesfråga om integration med andra system"
            }
        }
        
        question_type = question_types.get(question_number, question_types[1])[difficulty_text]
        
        prompt = f"""Du är en expert på att bedöma studenters kunskap om {concept_name}.

Konceptbeskrivning: {concept_description}

Detta är fråga {question_number} av 3. Generera {question_type} med svårighetsgrad: {difficulty_text}

VIKTIGT - Frågetyper för att säkerställa variation:
- Fråga 1: Fokusera på DEFINITION/TEORI
- Fråga 2: Fokusera på TILLÄMPNING/PRAKTIK
- Fråga 3: Fokusera på ANALYS/JÄMFÖRELSE

Frågan ska:
- Vara konkret och distinkt från andra frågor
- Kräva förståelse, inte bara memorering
- Kunna besvaras i 2-5 meningar
- INTE upprepa samma aspekt som andra frågor
- Vara formulerad enligt frågetypen ovan

Returnera ENDAST frågan, inget annat."""
        
        # Lägg till kunskapsgraf om den finns
        if additional_context:
            prompt += f"\n\n{additional_context}"
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en expert på bedömning som ställer direkta frågor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Fel vid generering av bedömningsfråga: {str(e)}")
            return f"Kan du förklara vad {concept_name} innebär och ge ett exempel på hur det används?"
    
    def get_socratic_question(self, concept_name: str, concept_description: str, 
                             prerequisites: List[str], mastery_score: float, 
                             conversation_history: List[Dict] = None,
                             dependent_concepts: List[str] = None,
                             importance_reason: str = None,
                             assessment_mode: bool = False,
                             additional_context: str = None) -> str:
        """
        Genererar en sokratisk fråga för att lära ut ett koncept
        
        Args:
            concept_name: Namnet på konceptet
            concept_description: Beskrivning av konceptet
            prerequisites: Lista med förutsättningar
            mastery_score: Studentens nuvarande kunskapsnivå
            conversation_history: Tidigare konversation
            dependent_concepts: Koncept som bygger på detta
            importance_reason: Varför konceptet är viktigt
            assessment_mode: Om det är bedömningsläge
            
        Returns:
            En pedagogisk fråga eller bedömningsfråga
        """
        # Använd olika prompt för bedömningsläge
        if assessment_mode:
            prompt = f"""Du är en expert på att bedöma studenters kunskap om {concept_name}.

Konceptbeskrivning: {concept_description}

Ställ EN direkt fråga som testar studentens förståelse av detta koncept.
Frågan ska:
- Vara konkret och tydlig
- Kräva förståelse, inte bara memorering
- Kunna besvaras i 2-5 meningar
- INTE innehålla förklaringar eller ledtrådar

Ställ bara frågan, inget annat."""
            messages = [
                {"role": "system", "content": "Du är en expert på bedömning som ställer direkta frågor."},
                {"role": "user", "content": prompt}
            ]
        else:
            prompt = SOCRATIC_LEARNING_PROMPT.replace("{{concept_name}}", concept_name)
            prompt = prompt.replace("{{concept_description}}", concept_description or "")
            prompt = prompt.replace("{{prerequisites}}", ", ".join(prerequisites) if prerequisites else "Inga")
            prompt = prompt.replace("{{mastery_score}}", str(mastery_score))
            prompt = prompt.replace("{{dependent_concepts}}", ", ".join(dependent_concepts) if dependent_concepts else "Inga kända")
            prompt = prompt.replace("{{importance_reason}}", importance_reason or "Grundläggande koncept inom området")
            
            # Lägg till kunskapsgraf och studentinfo
            prompt = prompt.replace("{{knowledge_graph}}", self._get_knowledge_graph_context())
            prompt = prompt.replace("{{student_info}}", self._get_student_info())
            
            # Lägg till ytterligare kontext om den finns
            if additional_context:
                prompt += f"\n\nYTTERLIGARE KONTEXT:\n{additional_context}"
            
            messages = [
                {"role": "system", "content": "Du är en sokratisk lärare som hjälper studenter att förstå koncept genom frågor."},
                {"role": "user", "content": prompt}
            ]
            
            # Lägg till konversationshistorik om den finns
            if conversation_history:
                messages.extend(conversation_history)
        
        try:
            response = completion(
                model=self.model,
                messages=messages,
                temperature=0.7,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Fel vid generering av sokratisk fråga: {str(e)}")
            return "Kan du berätta vad du redan vet om detta koncept?"
    
    def get_guided_explanation(self, concept_name: str, concept_description: str,
                              prerequisites: List[str], related_courses: List[str],
                              mastery_score: float, additional_context: str = None) -> str:
        """
        Genererar en guidad förklaring av ett koncept
        
        Args:
            concept_name: Namnet på konceptet
            concept_description: Beskrivning av konceptet
            prerequisites: Lista med förutsättningar
            related_courses: Lista med relaterade kurser
            mastery_score: Studentens nuvarande kunskapsnivå
            
        Returns:
            En strukturerad förklaring
        """
        prompt = GUIDED_LEARNING_PROMPT.replace("{{concept_name}}", concept_name)
        prompt = prompt.replace("{{concept_description}}", concept_description or "")
        prompt = prompt.replace("{{prerequisites}}", ", ".join(prerequisites) if prerequisites else "Inga")
        prompt = prompt.replace("{{related_courses}}", ", ".join(related_courses) if related_courses else "")
        prompt = prompt.replace("{{mastery_score}}", str(mastery_score))
        
        # Lägg till kunskapsgraf och studentinfo
        prompt = prompt.replace("{{knowledge_graph}}", self._get_knowledge_graph_context())
        prompt = prompt.replace("{{student_info}}", self._get_student_info())
        
        # Lägg till ytterligare kontext om den finns
        if additional_context:
            prompt += f"\n\nYTTERLIGARE KONTEXT:\n{additional_context}"
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en pedagogisk expert som förklarar koncept tydligt."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Fel vid generering av förklaring: {str(e)}")
            return f"Kunde inte generera förklaring för {concept_name}."
    
    def evaluate_understanding(self, concept_name: str, student_answer: str,
                              key_concepts: List[str] = None) -> Dict:
        """
        Utvärderar studentens förståelse baserat på deras svar
        
        Args:
            concept_name: Namnet på konceptet
            student_answer: Studentens svar
            key_concepts: Förväntade nyckelkoncept
            
        Returns:
            Dict med bedömning
        """
        prompt = UNDERSTANDING_EVALUATION_PROMPT.replace("{{concept_name}}", concept_name)
        prompt = prompt.replace("{{student_answer}}", student_answer)
        prompt = prompt.replace("{{key_concepts}}", ", ".join(key_concepts) if key_concepts else "")
        
        # Lägg till kunskapsgraf och studentinfo
        prompt = prompt.replace("{{knowledge_graph}}", self._get_knowledge_graph_context())
        prompt = prompt.replace("{{student_info}}", self._get_student_info())
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en expert på att bedöma studenters förståelse. Du MÅSTE svara med välformaterad JSON och INGET annat. Följ exakt det format som anges i prompten."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            llm_response = response.choices[0].message.content
            print(f"LLM utvärderingssvar: {llm_response[:500]}...")  # Debug
            
            result = self.extract_json_from_response(llm_response)
            
            if result and isinstance(result, dict):
                # Validera att alla nycklar finns
                required_keys = ["understanding_score", "strengths", "gaps", "feedback", "ready_to_progress"]
                for key in required_keys:
                    if key not in result:
                        print(f"Saknar nyckel: {key}")
                        if key == "understanding_score":
                            result[key] = 0.1
                        elif key in ["strengths", "gaps"]:
                            result[key] = []
                        elif key == "feedback":
                            result[key] = "Utvärdering genomförd."
                        elif key == "ready_to_progress":
                            result[key] = False
                
                # Säkerställ korrekt datatyp för understanding_score
                try:
                    result["understanding_score"] = float(result["understanding_score"])
                    # Begränsa till intervallet 0.0-1.0
                    result["understanding_score"] = max(0.0, min(1.0, result["understanding_score"]))
                except (ValueError, TypeError):
                    result["understanding_score"] = 0.1
                
                return result
            else:
                print(f"Kunde inte parsa utvärderingsresultat")
                return {
                    "understanding_score": 0.1,
                    "strengths": [],
                    "gaps": ["Tekniskt fel vid utvärdering"],
                    "feedback": "Ett tekniskt fel uppstod vid analys av ditt svar. Försök igen.",
                    "ready_to_progress": False
                }
                
        except Exception as e:
            print(f"Fel vid utvärdering: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "understanding_score": 0.1,
                "strengths": [],
                "gaps": ["Tekniskt fel uppstod"],
                "feedback": f"Ett tekniskt fel uppstod vid analys av ditt svar. Försök igen eller kontakta support om problemet kvarstår.",
                "ready_to_progress": False
            }
    
    def find_next_concept(self, knowledge_profile: Dict, available_concepts: List[Dict], additional_context: str = None) -> Dict:
        """
        Hittar nästa optimala koncept att lära sig
        
        Args:
            knowledge_profile: Studentens kunskapsprofil
            available_concepts: Lista med tillgängliga koncept
            additional_context: Ytterligare kontext för att styra valet av koncept
            
        Returns:
            Dict med rekommendation
        """
        prompt = NEXT_CONCEPT_PROMPT.replace("{{knowledge_profile}}", json.dumps(knowledge_profile, ensure_ascii=False))
        prompt = prompt.replace("{{available_concepts}}", json.dumps(available_concepts, ensure_ascii=False))
        
        # Lägg till ytterligare kontext om det finns
        if additional_context:
            prompt += f"\n\nYtterligare kontext: {additional_context}"
        
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en expert på pedagogisk progression."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            result = self.extract_json_from_response(response.choices[0].message.content)
            if result and isinstance(result, dict):
                return result
            else:
                # Fallback: välj första konceptet med uppfyllda förutsättningar
                for concept in available_concepts:
                    if not concept.get('prerequisites') or all(
                        knowledge_profile.get(prereq, {}).get('mastery_score', 0) >= 0.6 
                        for prereq in concept['prerequisites']
                    ):
                        return {
                            "recommended_concept": concept['name'],
                            "reasoning": "Alla förutsättningar är uppfyllda",
                            "prerequisites_met": concept.get('prerequisites', []),
                            "prerequisites_missing": [],
                            "difficulty_level": "medium",
                            "will_unlock": []
                        }
                
                # Om inget koncept har alla förutsättningar uppfyllda
                return {
                    "recommended_concept": available_concepts[0]['name'] if available_concepts else "",
                    "reasoning": "Börja med grundläggande koncept",
                    "prerequisites_met": [],
                    "prerequisites_missing": [],
                    "difficulty_level": "lätt",
                    "will_unlock": []
                }
                
        except Exception as e:
            print(f"Fel vid sökning efter nästa koncept: {str(e)}")
            return {
                "recommended_concept": "",
                "reasoning": "Tekniskt fel",
                "prerequisites_met": [],
                "prerequisites_missing": [],
                "difficulty_level": "medium",
                "will_unlock": []
            }
    
    def generate_cypher_for_course(self, course_info: str, existing_graph: str) -> Tuple[str, str]:
        """
        Genererar Cypher-kod för att lägga till en Canvas-kurs i grafen
        
        Args:
            course_info: Information om kursen från Canvas
            existing_graph: Befintlig graf som JSON
            
        Returns:
            Tuple av (cypher_code, llm_response)
        """
        prompt = f"""Du är en expert på Neo4j och ska generera Cypher-kod för att lägga till en kurs i en kunskapsgraf.

UPPGIFT:
Analysera kursinformationen och generera Cypher-kod som:
1. Skapar en Kurs-nod med rätt attribut
2. Extraherar och skapar 5-10 viktiga Koncept-noder från kursen
3. Skapar INNEHÅLLER-relationer mellan kursen och koncepten
4. Identifierar och skapar FÖRUTSÄTTER-relationer mellan koncept

BEFINTLIG GRAF:
{existing_graph}

KURSINFORMATION:
{course_info}

VIKTIGA REGLER:
- Använd svenska för konceptnamn och beskrivningar
- Om ett koncept redan finns i grafen, använd MATCH istället för CREATE
- Varje koncept ska ha: namn, beskrivning, svårighetsgrad
- Kursnoden ska ha: kurskod, namn, beskrivning
- Använd MERGE för att undvika dubbletter

Svara med giltig Cypher-kod som kan köras direkt i Neo4j.
Inkludera kommentarer i koden för att förklara vad varje del gör."""

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du är en Neo4j-expert som genererar Cypher-kod."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            llm_response = response.choices[0].message.content
            
            # Extrahera Cypher-kod från svaret
            cypher_match = re.search(r'```(?:cypher|sql|neo4j)?\n(.*?)\n```', llm_response, re.DOTALL)
            if cypher_match:
                cypher_code = cypher_match.group(1).strip()
            else:
                # Om ingen kodblock hittas, anta att hela svaret är Cypher
                cypher_code = llm_response.strip()
            
            return cypher_code, llm_response
            
        except Exception as e:
            error_msg = f"Fel vid generering av Cypher: {str(e)}"
            return "", error_msg