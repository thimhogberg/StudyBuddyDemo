"""
Parser för Chalmers kursinformation
"""
import json
import pandas as pd
from typing import List, Dict, Optional, Tuple
from config import COURSE_FILE


class CourseParser:
    """Hanterar parsing av kursinformation från JSON"""
    
    def __init__(self):
        self.courses = self._load_courses()
        self.programs = self._extract_programs()
    
    def _load_courses(self) -> List[Dict]:
        """Laddar kurser från JSON-fil"""
        try:
            with open(COURSE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Kunde inte hitta {COURSE_FILE}")
            return []
        except json.JSONDecodeError:
            print(f"Fel vid parsing av {COURSE_FILE}")
            return []
    
    def _extract_programs(self) -> Dict[str, str]:
        """Extraherar alla unika program från kurserna"""
        programs = {}
        for course in self.courses:
            if 'courseRounds' in course:
                for round in course['courseRounds']:
                    if 'programPlans' in round:
                        for plan in round['programPlans']:
                            prog_code = plan.get('programCode', '')
                            prog_name = plan.get('pgmName', '')
                            if prog_code and prog_name:
                                # Inkludera programkod i namnet
                                programs[prog_code] = f"{prog_name} ({prog_code})"
        return programs
    
    def get_programs(self) -> List[Tuple[str, str]]:
        """Returnerar lista med tupler (programkod, programnamn med kod)"""
        return sorted([(code, name) for code, name in self.programs.items()])
    
    def get_courses_by_program(self, program_code: str = None) -> pd.DataFrame:
        """Hämtar alla kurser för ett specifikt program eller alla kurser"""
        courses_in_program = []
        
        for course in self.courses:
            if 'courseRounds' in course:
                for round in course['courseRounds']:
                    if 'programPlans' in round:
                        for plan in round['programPlans']:
                            # Om program_code är None, ta med alla kurser
                            # Annars bara kurser som matchar programkoden
                            if program_code is None or plan.get('programCode', '') == program_code:
                                # Extrahera relevant kursinformation
                                course_info = {
                                    'courseCode': course.get('courseCode', ''),
                                    'name': course.get('name', ''),
                                    'nameAlt': course.get('nameAlt', ''),
                                    'credit': course.get('credit', ''),
                                    'eduLevel': course.get('eduLevel', ''),
                                    'grade': plan.get('grade', 0),
                                    'rule': plan.get('rule', ''),
                                    'startStudyPeriod': round.get('startStudyPeriod', ''),
                                    'purpose': course.get('purpose', ''),
                                    'goal': course.get('goal', ''),
                                    'content': course.get('content', ''),
                                    'prerequisites': course.get('prerequisites', ''),
                                    'examination': course.get('examination', ''),
                                    'AI_summary': course.get('AI_summary', '')
                                }
                                courses_in_program.append(course_info)
                                if program_code:  # Om vi söker specifikt program, bryt efter första träffen
                                    break
        
        df = pd.DataFrame(courses_in_program)
        if not df.empty:
            # Sortera efter årskurs (grade) och läsperiod
            df['year'] = df['grade'].astype(float).astype(int)
            df['period_num'] = df['startStudyPeriod'].str.extract(r'LP(\d)').fillna(0).astype(int)
            df = df.sort_values(['year', 'period_num'])
        
        return df
    
    def get_course_details(self, course_code: str) -> Optional[Dict]:
        """Hämtar detaljerad information om en specifik kurs"""
        for course in self.courses:
            if course.get('courseCode', '') == course_code:
                return course
        return None
    
    def get_course_full_info(self, course_code: str) -> str:
        """Returnerar fullständig kursinformation som text för LLM"""
        # Kolla om det är en temporär Canvas-kurs
        if hasattr(self, '_temp_canvas_course') and self._temp_canvas_course.get('courseCode') == course_code:
            course = self._temp_canvas_course
        else:
            course = self.get_course_details(course_code)
        
        if not course:
            return ""
        
        info = f"""
Kurskod: {course.get('courseCode', '')}
Kursnamn: {course.get('name', '')}
Svenskt namn: {course.get('nameAlt', '')}
Poäng: {course.get('credit', '')}
Nivå: {course.get('eduLevelName', '')}

Syfte:
{course.get('purpose', '')}

Lärandemål:
{course.get('goal', '')}

Innehåll:
{course.get('content', '')}

Förkunskapskrav:
{course.get('prerequisites', '')}

AI Sammanfattning:
{course.get('AI_summary', '')}
"""
        return info