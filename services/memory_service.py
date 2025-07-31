"""
Memory Service - Hanterar spaced repetition och memory curves
"""
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Tuple
import json

class MemoryService:
    def __init__(self, neo4j_service):
        self.neo4j = neo4j_service
        self.default_profile = {
            'learning_rate': 1.0,
            'forgetting_factor': 0.3,
            'avg_difficulty': 0.5,
            'initial_interval': 1,  # dagar
            'ease_factor': 2.5
        }
    
    def get_due_concepts(self, course_filter: str = None) -> List[Dict]:
        """Hämtar koncept som behöver repeteras"""
        if course_filter and course_filter != "Alla kurser":
            # Extrahera kurskod från "KURSKOD - Kursnamn"
            course_code = course_filter.split(' - ')[0] if ' - ' in course_filter else course_filter
            query = """
            MATCH (k:Kurs {kurskod: $course_code})-[:INNEHÅLLER]->(c:Koncept)
            WHERE c.id IS NOT NULL AND (c.next_review IS NULL OR datetime(c.next_review) <= datetime())
            RETURN c.id as id,
                   c.namn as name, 
                   k.kurskod + ' - ' + k.namn as course,
                   c.last_review as last_review,
                   c.retention as retention,
                   c.difficulty as difficulty,
                   c.review_count as review_count,
                   c.interval as interval,
                   c.beskrivning as description
            ORDER BY c.next_review ASC
            """
            params = {"course_code": course_code}
        else:
            # Endast koncept som tillhör en kurs
            query = """
            MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
            WHERE c.id IS NOT NULL AND (c.next_review IS NULL OR datetime(c.next_review) <= datetime())
            RETURN c.id as id,
                   c.namn as name, 
                   k.kurskod + ' - ' + k.namn as course,
                   c.last_review as last_review,
                   c.retention as retention,
                   c.difficulty as difficulty,
                   c.review_count as review_count,
                   c.interval as interval,
                   c.beskrivning as description
            ORDER BY c.next_review ASC
            """
            params = {}
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]
    
    def get_next_review_time(self) -> Optional[Dict]:
        """Hämtar nästa schemalagda repetition"""
        query = """
        MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
        WHERE c.id IS NOT NULL AND c.next_review IS NOT NULL AND datetime(c.next_review) > datetime()
        RETURN c.namn as concept,
               k.kurskod + ' - ' + k.namn as course,
               c.next_review as next_review
        ORDER BY c.next_review ASC
        LIMIT 1
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if record:
                next_review = datetime.fromisoformat(record['next_review'])
                time_until = next_review - datetime.now()
                
                if time_until.days > 0:
                    time_str = f"{time_until.days} dagar"
                else:
                    hours = time_until.seconds // 3600
                    time_str = f"{hours} timmar"
                
                return {
                    'concept': record['concept'],
                    'course': record['course'],
                    'time_until': time_str
                }
            
            return None
    
    def record_review(self, concept_id: str, quality: int):
        """
        Registrerar en repetition och uppdaterar memory curve
        quality: 0-3 (glömt helt, svårt, okej, lätt)
        """
        # Hämta nuvarande data
        query = """
        MATCH (c:Koncept {id: $concept_id})
        RETURN c.interval as interval,
               c.ease_factor as ease_factor,
               c.review_count as review_count,
               c.difficulty as difficulty
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, concept_id=concept_id)
            record = result.single()
            
            if not record:
                return
            
            # SM-2 algoritm modifierad för 4 kvalitetsnivåer
            interval = record['interval'] or 1
            ease_factor = record['ease_factor'] or 2.5
            review_count = (record['review_count'] or 0) + 1
            difficulty = record['difficulty'] or 0.3
            
            # Justera ease factor baserat på kvalitet
            if quality == 0:  # Glömt helt
                interval = 1
                ease_factor = max(1.3, ease_factor - 0.3)
                difficulty = min(0.9, difficulty + 0.1)
            elif quality == 1:  # Svårt
                interval = max(1, int(interval * 0.6))
                ease_factor = max(1.3, ease_factor - 0.15)
                difficulty = min(0.9, difficulty + 0.05)
            elif quality == 2:  # Okej
                interval = int(interval * ease_factor)
                ease_factor = ease_factor  # Oförändrad
            else:  # Lätt
                interval = int(interval * ease_factor * 1.3)
                ease_factor = min(2.8, ease_factor + 0.1)
                difficulty = max(0.1, difficulty - 0.05)
            
            # Beräkna retention baserat på glömskekurvan
            profile = self.get_user_profile()
            retention = self._calculate_retention(interval, profile['forgetting_factor'])
            
            # Uppdatera koncept
            next_review = datetime.now() + timedelta(days=interval)
            
            update_query = """
            MATCH (c:Koncept {id: $concept_id})
            SET c.last_review = $last_review,
                c.next_review = $next_review,
                c.interval = $interval,
                c.ease_factor = $ease_factor,
                c.review_count = $review_count,
                c.difficulty = $difficulty,
                c.retention = $retention,
                c.last_quality = $quality
            """
            
            session.run(update_query,
                concept_id=concept_id,
                last_review=datetime.now().isoformat(),
                next_review=next_review.isoformat(),
                interval=interval,
                ease_factor=ease_factor,
                review_count=review_count,
                difficulty=difficulty,
                retention=retention,
                quality=quality
            )
    
    def _calculate_retention(self, days_until_review: int, forgetting_factor: float) -> float:
        """Beräknar förväntad retention vid nästa repetition"""
        return np.exp(-forgetting_factor * days_until_review)
    
    def get_concepts_by_course(self) -> Dict[str, List[Dict]]:
        """Hämtar alla koncept grupperade per kurs"""
        query = """
        MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
        WHERE c.id IS NOT NULL
        RETURN k.kurskod as course_code,
               k.namn as course_name,
               k.kurskod + ' - ' + k.namn as course_full_name,
               collect({
                   id: c.id,
                   name: c.namn,
                   next_review: c.next_review,
                   retention: c.retention,
                   review_count: c.review_count,
                   difficulty: c.difficulty
               }) as concepts
        ORDER BY k.kurskod
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            
            courses_dict = {}
            for record in result:
                # Använd full name som nyckel
                courses_dict[record['course_full_name']] = record['concepts']
            
            return courses_dict
    
    def get_average_retention(self) -> float:
        """Beräknar genomsnittlig retention för alla koncept"""
        query = """
        MATCH (c:Koncept)
        WHERE c.retention IS NOT NULL
        RETURN avg(c.retention) as avg_retention
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            record = result.single()
            return record['avg_retention'] or 0
    
    def get_streak_days(self) -> int:
        """Hämtar antal dagar i rad användaren har repeterat"""
        query = """
        MATCH (s:Student)
        RETURN s
        LIMIT 1
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if not record:
                # Skapa studentnod om den inte finns
                session.run("MERGE (s:Student) SET s.streak_days = 0, s.last_review_date = null")
                return 0
            
            student = record['s']
            streak_days = student.get('streak_days', 0)
            last_review_date = student.get('last_review_date')
            
            # Kolla om streak är bruten
            if last_review_date:
                last_date = datetime.fromisoformat(last_review_date)
                days_diff = (datetime.now().date() - last_date.date()).days
                
                if days_diff > 1:
                    # Streak bruten, återställ
                    session.run("MATCH (s:Student) SET s.streak_days = 0")
                    return 0
                elif days_diff == 1:
                    # Fortsätt streak
                    new_streak = streak_days + 1
                    session.run("""
                        MATCH (s:Student) 
                        SET s.streak_days = $streak,
                            s.last_review_date = $date
                    """, streak=new_streak, date=datetime.now().isoformat())
                    return new_streak
            
            return streak_days
    
    def get_calendar_view(self, days: int = 30) -> Dict[str, int]:
        """Hämtar antal koncept per dag för kalendervy"""
        end_date = datetime.now() + timedelta(days=days)
        
        query = """
        MATCH (c:Koncept)
        WHERE c.next_review IS NOT NULL 
        AND datetime(c.next_review) >= datetime() 
        AND datetime(c.next_review) <= datetime($end_date)
        RETURN date(datetime(c.next_review)) as review_date,
               count(c) as count
        ORDER BY review_date
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, end_date=end_date.isoformat())
            
            calendar_data = {}
            for record in result:
                date_str = str(record['review_date'])
                calendar_data[date_str] = record['count']
            
            return calendar_data
    
    def get_user_profile(self) -> Dict:
        """Hämtar användarens inlärningsprofil"""
        query = """
        MATCH (s:Student)
        RETURN s.learning_rate as learning_rate,
               s.forgetting_factor as forgetting_factor,
               s.avg_difficulty as avg_difficulty,
               s.initial_interval as initial_interval,
               s.ease_factor as ease_factor
        LIMIT 1
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if record:
                profile = dict(record)
                # Fyll i default-värden för saknade fält
                for key, value in self.default_profile.items():
                    if profile.get(key) is None:
                        profile[key] = value
                return profile
            else:
                # Skapa studentprofil med defaults
                session.run("""
                    MERGE (s:Student)
                    SET s.learning_rate = $learning_rate,
                        s.forgetting_factor = $forgetting_factor,
                        s.avg_difficulty = $avg_difficulty,
                        s.initial_interval = $initial_interval,
                        s.ease_factor = $ease_factor
                """, **self.default_profile)
                return self.default_profile
    
    def update_user_profile(self, updates: Dict):
        """Uppdaterar användarens profil"""
        set_clause = ", ".join([f"s.{key} = ${key}" for key in updates.keys()])
        query = f"MATCH (s:Student) SET {set_clause}"
        
        with self.neo4j.driver.session() as session:
            session.run(query, **updates)
    
    def get_concept_question(self, concept: Dict) -> str:
        """Genererar en fråga för konceptet med LLM"""
        # Hämta mer information om konceptet
        query = """
        MATCH (c:Koncept {id: $concept_id})
        OPTIONAL MATCH (k:Kurs)-[:INNEHÅLLER]->(c)
        OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
        RETURN c.beskrivning as description,
               k.namn as course_name,
               k.kurskod as course_code,
               collect(prereq.namn) as prerequisites
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, concept_id=concept['id'])
            record = result.single()
            
            context = {
                'concept_name': concept['name'],
                'course': concept.get('course', 'okänd kurs'),
                'description': record['description'] if record else concept.get('description', ''),
                'course_name': record['course_name'] if record else '',
                'prerequisites': record['prerequisites'] if record else []
            }
            
            # Generera fråga med LLM
            prompt = f"""
            Generera en bra repetitionsfråga för konceptet "{context['concept_name']}" från kursen {context['course']}.
            
            Kontext:
            - Kursnamn: {context['course_name']}
            - Beskrivning: {context['description']}
            - Förutsättningar: {', '.join(context['prerequisites']) if context['prerequisites'] else 'Inga'}
            
            Skapa en fråga som testar förståelse, inte bara memorering. Frågan ska vara:
            1. Specifik och tydlig
            2. Fokusera på praktisk tillämpning eller djupare förståelse
            3. Vara på svenska
            4. Inte för lång (max 2-3 meningar)
            
            Returnera ENDAST frågan, ingen förklaring eller annat.
            """
            
            return self.llm.query(prompt)
    
    def get_concept_answer(self, concept: Dict) -> str:
        """Genererar ett svar för konceptet med LLM"""
        # Hämta fullständig information om konceptet
        query = """
        MATCH (c:Koncept {id: $concept_id})
        OPTIONAL MATCH (k:Kurs)-[:INNEHÅLLER]->(c)
        OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(prereq:Koncept)
        OPTIONAL MATCH (c)-[:RELATERAR_TILL]->(related:Koncept)
        RETURN c.beskrivning as description,
               k.namn as course_name,
               k.kurskod as course_code,
               k.ai_sammanfattning as course_ai_summary,
               collect(DISTINCT prereq.namn) as prerequisites,
               collect(DISTINCT related.namn) as related_concepts
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query, concept_id=concept['id'])
            record = result.single()
            
            if not record:
                return f"{concept['name']} är ett viktigt koncept inom {concept.get('course', 'kursen')}."
            
            context = {
                'concept_name': concept['name'],
                'course': concept.get('course', 'okänd kurs'),
                'description': record['description'] or '',
                'course_name': record['course_name'] or '',
                'course_ai_summary': record['course_ai_summary'] or '',
                'prerequisites': record['prerequisites'] or [],
                'related_concepts': record['related_concepts'] or []
            }
            
            # Generera svar med LLM
            prompt = f"""
            Förklara konceptet "{context['concept_name']}" från kursen {context['course']} ({context['course_name']}).
            
            Tillgänglig information:
            - Beskrivning: {context['description']}
            - Kurssammanfattning: {context['course_ai_summary'][:200]}...
            - Förutsättningar: {', '.join(context['prerequisites']) if context['prerequisites'] else 'Inga specifika'}
            - Relaterade koncept: {', '.join(context['related_concepts']) if context['related_concepts'] else 'Inga'}
            
            Skapa en förklaring som:
            1. Är pedagogisk och lättförståelig
            2. Ger konkreta exempel eller tillämpningar
            3. Förklarar varför konceptet är viktigt
            4. Är på svenska
            5. Är koncis men informativ (max 150 ord)
            
            Strukturera svaret med:
            - En kort definition
            - Huvudpoänger eller egenskaper
            - Ett konkret exempel
            - Koppling till andra koncept om relevant
            
            Returnera ENDAST förklaringen, ingen meta-text.
            """
            
            return self.llm.query(prompt)
    
    def generate_test_concepts(self) -> List[Dict]:
        """Genererar testkoncept för minnestest"""
        # Skulle generera eller välja ut lämpliga koncept för test
        # För nu returnerar vi några exempel
        return [
            {
                'id': 'test_1',
                'name': 'Testbegrepp 1',
                'definition': 'Detta är definitionen av testbegrepp 1'
            },
            {
                'id': 'test_2', 
                'name': 'Testbegrepp 2',
                'definition': 'Detta är definitionen av testbegrepp 2'
            }
        ]
    
    def get_test_results(self) -> Optional[Dict]:
        """Hämtar resultat från senaste minnestestet"""
        query = """
        MATCH (s:Student)
        RETURN s.test_results as test_results
        LIMIT 1
        """
        
        with self.neo4j.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if record and record['test_results']:
                results = json.loads(record['test_results'])
                
                # Skapa retention curve funktion
                def retention_curve(days):
                    return np.exp(-results.get('personal_forgetting_factor', 0.3) * days)
                
                results['retention_curve'] = retention_curve
                return results
            
            return None