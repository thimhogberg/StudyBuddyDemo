"""
Bygger kunskapsgrafen i Neo4j
"""
from typing import List, Dict
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neo4j_service import Neo4jService
from src.llm_service import LLMService
from src.course_parser import CourseParser
import streamlit as st


class GraphBuilder:
    """Bygger och hanterar kunskapsgrafen"""
    
    def __init__(self):
        self.neo4j = Neo4jService()
        self.llm = LLMService()
        self.parser = CourseParser()
    
    def build_graph_for_course(self, course_code: str, show_concepts: bool = False) -> Dict[str, int]:
        """
        Bygger graf för en enskild kurs
        
        Args:
            course_code: Kurskod
            show_concepts: Om True, visa vilka koncept som skapas (för Streamlit)
            
        Returns:
            Dict med antal skapade noder och relationer
        """
        # Hämta kursinformation
        course_info = self.parser.get_course_full_info(course_code)
        if not course_info:
            return {"kurser": 0, "koncept": 0, "relationer": 0}
        
        course_details = self.parser.get_course_details(course_code)
        
        # Hämta befintlig graf
        existing_concepts = self._get_existing_concepts_summary()
        
        # Extrahera koncept med LLM
        import streamlit as st
        concepts = self.llm.extract_concepts(
            course_info, 
            existing_concepts,
            max_concepts=st.session_state.get('max_concepts', 10),
            language=st.session_state.get('language', 'Svenska')
        )
        
        if show_concepts and concepts:
            st.write(f"Hittade {len(concepts)} koncept:")
            for concept in concepts:
                st.write(f"- **{concept.get('namn', '')}**")
                if concept.get('förutsätter'):
                    st.write(f"  → Förutsätter: {', '.join(concept['förutsätter'])}")
        
        # Räknare för statistik
        new_concepts = 0
        new_relations = 0
        
        # Skapa kursnod
        with self.neo4j.driver.session() as session:
            # Hämta ytterligare kursinformation
            courses_df = self.parser.get_courses_by_program(None)  # Hämta alla kurser
            course_row = courses_df[courses_df['courseCode'] == course_code]
            
            if not course_row.empty:
                course_data = course_row.iloc[0]
                year = int(course_data.get('year', 0))
                period = int(course_data.get('period_num', 0))
                rule = course_data.get('rule', '')
            else:
                year = 0
                period = 0
                rule = ''
            
            # Skapa eller uppdatera kursnod med all information
            session.run("""
                MERGE (k:Kurs {kurskod: $kurskod})
                SET k.namn = $namn,
                    k.namn_sv = $namn_sv,
                    k.namn_en = $namn_en,
                    k.beskrivning = $beskrivning,
                    k.syfte = $syfte,
                    k.ai_sammanfattning = $ai_sammanfattning,
                    k.år = $år,
                    k.läsperiod = $läsperiod,
                    k.regel = $regel,
                    k.poäng = $poäng
            """, 
            kurskod=course_code,
            namn=course_details.get('nameAlt', ''),  # Svenskt namn som huvudnamn
            namn_sv=course_details.get('nameAlt', ''),
            namn_en=course_details.get('name', ''),
            beskrivning=course_details.get('purpose', '')[:500],
            syfte=course_details.get('purpose', ''),
            ai_sammanfattning=course_details.get('AI_summary', ''),
            år=year,
            läsperiod=period,
            regel=rule,
            poäng=course_details.get('credit', '')
            )
            
            # Skapa koncept och relationer
            for concept in concepts:
                # Kolla om konceptet redan finns
                existing_check = session.run("""
                    MATCH (c:Koncept {namn: $namn})
                    RETURN c
                """, namn=concept.get('namn', ''))
                
                concept_exists = existing_check.single() is not None
                
                if not concept_exists:
                    # Skapa nytt koncept med mastery_score och memory-egenskaper
                    import uuid
                    session.run("""
                        CREATE (c:Koncept {
                            id: $id,
                            namn: $namn, 
                            beskrivning: $beskrivning, 
                            mastery_score: 0.0,
                            retention: 1.0,
                            difficulty: 0.3,
                            interval: 1,
                            ease_factor: 2.5,
                            review_count: 0,
                            last_review: null,
                            next_review: null
                        })
                    """,
                    id=str(uuid.uuid4()),
                    namn=concept.get('namn', ''),
                    beskrivning=concept.get('beskrivning', '')
                    )
                    new_concepts += 1
                else:
                    # Uppdatera beskrivning och lägg till memory-egenskaper om de saknas
                    import uuid
                    session.run("""
                        MATCH (c:Koncept {namn: $namn})
                        SET c.beskrivning = CASE 
                            WHEN c.beskrivning IS NULL OR c.beskrivning = '' 
                            THEN $beskrivning 
                            ELSE c.beskrivning 
                        END,
                        c.mastery_score = COALESCE(c.mastery_score, 0.0),
                        c.id = COALESCE(c.id, $id),
                        c.retention = COALESCE(c.retention, 1.0),
                        c.difficulty = COALESCE(c.difficulty, 0.3),
                        c.interval = COALESCE(c.interval, 1),
                        c.ease_factor = COALESCE(c.ease_factor, 2.5),
                        c.review_count = COALESCE(c.review_count, 0)
                    """,
                    namn=concept.get('namn', ''),
                    beskrivning=concept.get('beskrivning', ''),
                    id=str(uuid.uuid4())
                    )
                
                # Skapa relation mellan kurs och koncept (om den inte redan finns)
                rel_result = session.run("""
                    MATCH (k:Kurs {kurskod: $kurskod})
                    MATCH (c:Koncept {namn: $koncept_namn})
                    MERGE (k)-[r:INNEHÅLLER]->(c)
                    RETURN r
                """,
                kurskod=course_code,
                koncept_namn=concept.get('namn', '')
                )
                if rel_result.single():
                    new_relations += 1
                
                # Skapa förutsättningar mellan koncept
                for prereq in concept.get('förutsätter', []):
                    # Skapa förutsättningskonceptet om det inte finns
                    session.run("""
                        MERGE (c:Koncept {namn: $namn})
                    """, namn=prereq)
                    
                    # Skapa FÖRUTSÄTTER-relation om den inte redan finns
                    prereq_result = session.run("""
                        MATCH (c1:Koncept {namn: $koncept_namn})
                        MATCH (c2:Koncept {namn: $prereq})
                        MERGE (c1)-[r:FÖRUTSÄTTER]->(c2)
                        RETURN r
                    """,
                    koncept_namn=concept.get('namn', ''),
                    prereq=prereq
                    )
                    if prereq_result.single():
                        new_relations += 1
        
        return {
            "kurser": 1,
            "koncept": new_concepts,
            "relationer": new_relations
        }
    
    def build_graph_for_program(self, program_code: str, selected_courses: List[str] = None, progress_callback=None) -> Dict[str, int]:
        """
        Bygger graf för valda kurser i ett program
        
        Args:
            program_code: Programkod
            selected_courses: Lista med kurskoder att inkludera (om None, bygg för alla)
            progress_callback: Funktion som anropas med (current, total) för att visa progress
            
        Returns:
            Dict med totalt antal skapade noder och relationer
        """
        # Hämta alla kurser i programmet
        courses_df = self.parser.get_courses_by_program(program_code)
        
        if courses_df.empty:
            return {"kurser": 0, "koncept": 0, "relationer": 0}
        
        # Filtrera kurser om selected_courses är angivet
        if selected_courses:
            courses_df = courses_df[courses_df['courseCode'].isin(selected_courses)]
        
        total_stats = {"kurser": 0, "koncept": 0, "relationer": 0}
        total_courses = len(courses_df)
        
        # Bygg graf för varje kurs
        for idx, (_, course) in enumerate(courses_df.iterrows()):
            if progress_callback:
                progress_callback(idx + 1, total_courses)
            
            stats = self.build_graph_for_course(course['courseCode'])
            for key in total_stats:
                total_stats[key] += stats[key]
        
        # Analysera förutsättningar mellan kurser
        self._analyze_cross_course_prerequisites(courses_df)
        
        return total_stats
    
    def _analyze_cross_course_prerequisites(self, courses_df):
        """Analyserar och skapar förutsättningar mellan koncept från olika kurser"""
        # Kurser är redan sorterade kronologiskt när de kommer hit
        
        with self.neo4j.driver.session() as session:
            for i in range(len(courses_df) - 1):
                earlier_course = courses_df.iloc[i]
                
                # Hämta koncept från tidigare kurs
                result = session.run("""
                    MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                    RETURN c.namn as namn
                """, kurskod=earlier_course['courseCode'])
                
                earlier_concepts = [r['namn'] for r in result]
                
                if not earlier_concepts:
                    continue
                
                # Analysera endast mot senare kurser (kronologisk ordning)
                for j in range(i + 1, len(courses_df)):
                    later_course = courses_df.iloc[j]
                    
                    # Hoppa över om det är för långt fram i tiden (mer än 2 år)
                    year_diff = later_course['year'] - earlier_course['year']
                    if year_diff > 2:
                        break
                    
                    # Hämta koncept från senare kurs
                    result = session.run("""
                        MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                        RETURN c.namn as namn
                    """, kurskod=later_course['courseCode'])
                    
                    later_concepts = [r['namn'] for r in result]
                    
                    if earlier_concepts and later_concepts:
                        # Använd LLM för att hitta förutsättningar
                        prerequisites = self.llm.analyze_prerequisites(
                            earlier_concepts, 
                            later_concepts
                        )
                        
                        # Skapa relationer
                        for later_concept, earlier_concept in prerequisites:
                            session.run("""
                                MATCH (c1:Koncept {namn: $earlier})
                                MATCH (c2:Koncept {namn: $later})
                                MERGE (c2)-[:FÖRUTSÄTTER]->(c1)
                            """, earlier=earlier_concept, later=later_concept)
    
    def _get_existing_concepts_summary(self) -> str:
        """
        Hämtar en sammanfattning av alla befintliga koncept i grafen
        
        Returns:
            JSON-sträng med alla befintliga koncept och deras kurser
        """
        try:
            with self.neo4j.driver.session() as session:
                # Hämta ALLA koncept med deras kurser och relationer
                query = """
                MATCH (c:Koncept)
                OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
                OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(req:Koncept)
                RETURN c.namn as koncept, 
                       c.beskrivning as beskrivning,
                       collect(DISTINCT k.kurskod) as kurser,
                       collect(DISTINCT req.namn) as förutsätter
                ORDER BY size(kurser) DESC
                """
                
                result = session.run(query)
                concepts = []
                
                for record in result:
                    concepts.append({
                        "namn": record['koncept'],
                        "beskrivning": record['beskrivning'] or "",
                        "används_i_kurser": record['kurser'],
                        "förutsätter": [x for x in record['förutsätter'] if x]
                    })
                
                # Hämta också alla kurser som redan finns
                courses_query = """
                MATCH (k:Kurs)
                RETURN k.kurskod as kurskod, k.namn as namn
                """
                courses_result = session.run(courses_query)
                courses = [{"kurskod": r['kurskod'], "namn": r['namn']} for r in courses_result]
                
                graph_summary = {
                    "antal_koncept": len(concepts),
                    "antal_kurser": len(courses),
                    "kurser": courses,
                    "koncept": concepts
                }
                
                if concepts or courses:
                    return f"Befintlig kunskapsgraf:\n{json.dumps(graph_summary, ensure_ascii=False, indent=2)}"
                else:
                    return "Grafen är tom."
                    
        except Exception as e:
            print(f"Fel vid hämtning av befintlig graf: {e}")
            return "Kunde inte hämta befintlig graf."
    
    def clear_graph(self):
        """Rensar hela grafdatabasen"""
        with self.neo4j.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def close(self):
        """Stänger databaskopplingen"""
        self.neo4j.close()