"""
Canvas API Service för StudyBuddy
"""
import os
import requests
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import streamlit as st
from bs4 import BeautifulSoup
import html
from config import CANVAS_TOKEN, CANVAS_BASE_URL


class CanvasAPI:
    def __init__(self):
        self.token = CANVAS_TOKEN or os.getenv("CANVAS_TOKEN")
        self.base_url = CANVAS_BASE_URL or os.getenv("CANVAS_BASE_URL", "https://chalmers.instructure.com/api/v1")
        
        if not self.token:
            raise ValueError("CANVAS_TOKEN saknas i miljövariabler")
        
        # Ta bort eventuell courses-del från base_url
        if "/courses" in self.base_url:
            self.base_url = self.base_url.split("/courses")[0]
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json+canvas-string-ids"
        }
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Gör en GET-request till Canvas API"""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Ogiltig Canvas-token. Kontrollera din CANVAS_TOKEN i .env-filen")
        else:
            raise Exception(f"API-fel: {response.status_code} - {response.text}")
    
    def _paginate_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Hanterar paginerade Canvas API-svar"""
        if params is None:
            params = {}
        params['per_page'] = 100
        
        all_data = []
        page = 1
        
        while True:
            params['page'] = page
            response = requests.get(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                params=params
            )
            
            if response.status_code != 200:
                break
                
            data = response.json()
            if not data:
                break
                
            all_data.extend(data)
            
            # Kolla om det finns fler sidor
            if 'Link' in response.headers:
                if 'rel="next"' not in response.headers['Link']:
                    break
            else:
                break
                
            page += 1
        
        return all_data
    
    def get_user_courses(self) -> List[Dict]:
        """Hämtar användarens kurser från Canvas"""
        params = {
            "state[]": ["all"],  # Hämta alla kurser, inte bara aktiva
            "include[]": ["syllabus_body", "term", "course_progress"]
        }
        return self._paginate_request("courses", params)
    
    def get_course_modules(self, course_id: int) -> List[Dict]:
        """Hämtar moduler för en kurs"""
        return self._paginate_request(f"courses/{course_id}/modules", {"include[]": ["items"]})
    
    def get_module_items(self, course_id: int, module_id: int) -> List[Dict]:
        """Hämtar items i en modul"""
        return self._paginate_request(f"courses/{course_id}/modules/{module_id}/items")
    
    def get_course_assignments(self, course_id: int) -> List[Dict]:
        """Hämtar uppgifter för en kurs"""
        params = {
            "include[]": ["submission", "assignment_visibility"],
            "order_by": "due_at"
        }
        return self._paginate_request(f"courses/{course_id}/assignments", params)
    
    def get_course_files(self, course_id: int) -> pd.DataFrame:
        """Hämtar filer för en kurs"""
        files = self._paginate_request(f"courses/{course_id}/files")
        
        if not files:
            return pd.DataFrame()
        
        # Konvertera till DataFrame
        df = pd.DataFrame(files)
        
        # Välj relevanta kolumner om de finns
        cols = ['id', 'display_name', 'filename', 'size', 'content-type', 
                'url', 'created_at', 'modified_at', 'folder_id']
        available_cols = [col for col in cols if col in df.columns]
        
        if available_cols:
            df = df[available_cols]
        
        # Lägg till extra kolumner för enklare hantering
        if 'display_name' in df.columns:
            df['name'] = df['display_name']
        elif 'filename' in df.columns:
            df['name'] = df['filename']
        
        if 'size' in df.columns:
            df['size_b'] = df['size']
        
        if 'content-type' in df.columns:
            df['mime'] = df['content-type']
        
        return df
    
    def get_course_folders(self, course_id: int) -> pd.DataFrame:
        """Hämtar mappstruktur för en kurs"""
        folders = self._paginate_request(f"courses/{course_id}/folders")
        
        if not folders:
            return pd.DataFrame()
        
        return pd.DataFrame(folders)
    
    def get_calendar_events(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Hämtar kalenderhändelser"""
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self._paginate_request("calendar_events", params)
    
    def get_upcoming_assignments(self) -> List[Dict]:
        """Hämtar kommande uppgifter för alla kurser"""
        assignments = []
        courses = self.get_user_courses()
        
        for course in courses:
            course_assignments = self.get_course_assignments(course['id'])
            for assignment in course_assignments:
                if assignment.get('due_at'):
                    assignment['course_name'] = course.get('name', 'Okänd kurs')
                    assignment['course_code'] = course.get('course_code', 'N/A')
                    assignments.append(assignment)
        
        # Sortera efter deadline
        assignments.sort(key=lambda x: x.get('due_at', ''))
        
        # Filtrera bara framtida deadlines
        now = datetime.now(timezone.utc)
        upcoming = []
        for a in assignments:
            if a.get('due_at'):
                try:
                    due_date = datetime.fromisoformat(a['due_at'].replace('Z', '+00:00'))
                    if due_date > now:
                        upcoming.append(a)
                except Exception:
                    pass
        
        return upcoming
    
    def fetch_syllabus(self, course_id: int) -> tuple[str, str]:
        """Hämtar kursplan för en kurs"""
        try:
            course = self._make_request(f"courses/{course_id}", {"include[]": ["syllabus_body"]})
            
            syllabus_html = course.get('syllabus_body', '')
            
            if not syllabus_html:
                return "Ingen kursplan tillgänglig", "Ingen kursplan tillgänglig"
            
            # Konvertera HTML till ren text
            soup = BeautifulSoup(syllabus_html, 'html.parser')
            full_text = soup.get_text(separator='\n', strip=True)
            
            # Skapa kort sammanfattning
            lines = full_text.split('\n')
            short_summary = '\n'.join(lines[:10]) if len(lines) > 10 else full_text
            
            if len(short_summary) > 500:
                short_summary = short_summary[:497] + "..."
            
            return short_summary, full_text
            
        except Exception as e:
            return f"Fel vid hämtning: {str(e)}", f"Fel vid hämtning: {str(e)}"
    
    def fetch_page_content(self, course_id: int, page_slug: str, max_chars: int = 500) -> str:
        """Hämtar innehåll från en Canvas-sida"""
        try:
            page = self._make_request(f"courses/{course_id}/pages/{page_slug}")
            
            if not page or 'body' not in page:
                return "Kunde inte hämta innehåll"
            
            # Konvertera HTML till text
            soup = BeautifulSoup(page['body'], 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            
            # Begränsa längd
            if len(text) > max_chars:
                text = text[:max_chars-3] + "..."
            
            return text
            
        except Exception:
            return "Kunde inte hämta innehåll"
    
    def get_page_slug_from_url(self, page_url: str) -> Optional[str]:
        """Extraherar page slug från en Canvas page URL"""
        # Format: .../courses/{course_id}/pages/{page_slug}
        if '/pages/' in page_url:
            return page_url.split('/pages/')[-1]
        return None
    
    def download_file_content(self, file_url: str) -> Optional[str]:
        """Laddar ner och returnerar filinnehåll som text"""
        try:
            response = requests.get(file_url, headers=self.headers)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None
    
    def build_folder_tree(self, folders_df: pd.DataFrame, files_df: pd.DataFrame) -> Dict:
        """Bygger en trädstruktur av mappar och filer"""
        # Skapa mappstruktur
        folder_info = {}
        children = {}
        files_in_folder = {}
        
        # Bygg upp mappinfo
        for _, folder in folders_df.iterrows():
            folder_id = folder['id']
            folder_info[folder_id] = (folder['name'], folder.get('parent_folder_id'))
            
            # Initiera barn-lista
            if folder_id not in children:
                children[folder_id] = []
            
            # Lägg till som barn till förälder
            parent_id = folder.get('parent_folder_id')
            if parent_id:
                if parent_id not in children:
                    children[parent_id] = []
                children[parent_id].append(folder_id)
        
        # Placera filer i mappar
        for _, file in files_df.iterrows():
            folder_id = file.get('folder_id')
            if folder_id:
                if folder_id not in files_in_folder:
                    files_in_folder[folder_id] = []
                files_in_folder[folder_id].append(file.to_dict())
        
        # Hitta root-mappar
        root_ids = [fid for fid, (name, parent) in folder_info.items() if not parent]
        
        return {
            'folder_info': folder_info,
            'children': children,
            'files_in_folder': files_in_folder,
            'root_ids': root_ids
        }
    
    @staticmethod
    def fmt_size(size_bytes: int) -> str:
        """Formaterar filstorlek till läsbart format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def get_course_assignments_by_module(self, course_id: int) -> Dict[str, List[Dict]]:
        """
        Hämtar uppgifter grupperade per modul för en kurs
        
        Returns:
            Dict med modulnamn som nycklar och lista av uppgifter som värden
        """
        modules = self.get_course_modules(course_id)
        assignments_by_module = {}
        
        for module in modules:
            module_name = module.get('name', 'Namnlös modul')
            module_assignments = []
            
            items = module.get('items', [])
            if not items:
                items = self.get_module_items(course_id, module['id'])
            
            for item in items:
                if item.get('type') == 'Assignment':
                    # Hämta fullständig uppgiftsinformation
                    try:
                        assignment_id = item.get('content_id')
                        if assignment_id:
                            assignment = self._make_request(f"courses/{course_id}/assignments/{assignment_id}")
                            module_assignments.append(assignment)
                    except Exception:
                        pass
            
            if module_assignments:
                assignments_by_module[module_name] = module_assignments
        
        return assignments_by_module
    
    def get_study_recommendations(self, course_id: int, upcoming_days: int = 14) -> List[Dict]:
        """
        Genererar studierekommendationer baserat på kommande deadlines
        
        Args:
            course_id: Canvas kurs-ID
            upcoming_days: Antal dagar framåt att kolla
            
        Returns:
            Lista med studierekommendationer
        """
        assignments = self.get_course_assignments(course_id)
        recommendations = []
        
        for assignment in assignments:
            if assignment.get('due_at'):
                due_date = datetime.fromisoformat(assignment['due_at'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                days_until = (due_date - now).days
                
                if 0 <= days_until <= upcoming_days:
                    priority = 'hög' if days_until <= 3 else 'medium' if days_until <= 7 else 'låg'
                    
                    recommendations.append({
                        'assignment': assignment['name'],
                        'due_date': due_date,
                        'days_until': days_until,
                        'priority': priority,
                        'points': assignment.get('points_possible', 0),
                        'module': self._find_assignment_module(course_id, assignment['id'])
                    })
        
        # Sortera efter prioritet och deadline
        recommendations.sort(key=lambda x: (x['days_until'], -x['points']))
        
        return recommendations
    
    def _find_assignment_module(self, course_id: int, assignment_id: int) -> Optional[str]:
        """Hittar vilken modul en uppgift tillhör"""
        modules = self.get_course_modules(course_id)
        
        for module in modules:
            items = module.get('items', [])
            if not items:
                items = self.get_module_items(course_id, module['id'])
            
            for item in items:
                if item.get('type') == 'Assignment' and item.get('content_id') == assignment_id:
                    return module.get('name', 'Okänd modul')
        
        return None