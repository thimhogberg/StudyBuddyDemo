"""
Grafverktyg för StudyBuddy
Hanterar grafbyggande och analyslogik
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from services.neo4j_service import Neo4jService


class GraphUtils:
    """Verktyg för att bygga och analysera grafer"""
    
    def __init__(self, neo4j_service: Neo4jService):
        """
        Initialiserar GraphUtils
        
        Args:
            neo4j_service: Neo4j service-instans
        """
        self.db = neo4j_service
    
    def create_concept_graph(self, concept_name: str) -> Dict:
        """
        Skapar en graf för ett specifikt koncept med dess relationer
        
        Args:
            concept_name: Namnet på konceptet att visualisera
            
        Returns:
            Dict med noder och kanter för visualisering
        """
        nodes = []
        edges = []
        
        try:
            with self.db.driver.session() as session:
                # Hämta konceptet och dess direkta relationer
                query = """
                MATCH (c:Koncept {namn: $concept_name})
                OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(req:Koncept)
                OPTIONAL MATCH (dep:Koncept)-[:FÖRUTSÄTTER]->(c)
                OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
                RETURN c, collect(DISTINCT req) as requires, 
                       collect(DISTINCT dep) as required_by,
                       collect(DISTINCT k) as courses
                """
                result = session.run(query, concept_name=concept_name).single()
                
                if not result:
                    return {"nodes": [], "edges": []}
                
                # Lägg till huvudkonceptet
                main_concept = result['c']
                nodes.append({
                    "id": main_concept['namn'],
                    "label": main_concept['namn'],
                    "type": "concept",
                    "color": "#4CAF50",
                    "size": 30
                })
                
                # Lägg till koncept som detta förutsätter
                for req in result['requires']:
                    nodes.append({
                        "id": req['namn'],
                        "label": req['namn'],
                        "type": "prerequisite",
                        "color": "#FF9800",
                        "size": 20
                    })
                    edges.append({
                        "from": main_concept['namn'],
                        "to": req['namn'],
                        "label": "förutsätter",
                        "color": "#FF9800",
                        "arrows": "to"
                    })
                
                # Lägg till koncept som förutsätter detta
                for dep in result['required_by']:
                    nodes.append({
                        "id": dep['namn'],
                        "label": dep['namn'],
                        "type": "dependent",
                        "color": "#2196F3",
                        "size": 20
                    })
                    edges.append({
                        "from": dep['namn'],
                        "to": main_concept['namn'],
                        "label": "förutsätter",
                        "color": "#2196F3",
                        "arrows": "to"
                    })
                
                # Lägg till kurser
                for course in result['courses']:
                    nodes.append({
                        "id": course['kurskod'],
                        "label": f"{course['kurskod']} - {course['namn']}",
                        "type": "course",
                        "color": "#9C27B0",
                        "size": 25
                    })
                    edges.append({
                        "from": course['kurskod'],
                        "to": main_concept['namn'],
                        "label": "innehåller",
                        "color": "#9C27B0",
                        "arrows": "to"
                    })
                
                return {"nodes": nodes, "edges": edges}
                
        except Exception as e:
            print(f"Fel vid skapande av konceptgraf: {e}")
            return {"nodes": [], "edges": []}
    
    def create_course_similarity_graph(self, kurs1: str, kurs2: str) -> Dict:
        """
        Skapar en graf som visar likheter mellan två kurser
        
        Args:
            kurs1: Första kurskoden
            kurs2: Andra kurskoden
            
        Returns:
            Dict med noder och kanter för visualisering
        """
        nodes = []
        edges = []
        
        try:
            with self.db.driver.session() as session:
                # Hämta gemensamma och unika koncept
                query = """
                MATCH (k1:Kurs {kurskod: $kurs1})
                MATCH (k2:Kurs {kurskod: $kurs2})
                OPTIONAL MATCH (k1)-[:INNEHÅLLER]->(c1:Koncept)
                OPTIONAL MATCH (k2)-[:INNEHÅLLER]->(c2:Koncept)
                WITH k1, k2, collect(DISTINCT c1.namn) as koncept1, collect(DISTINCT c2.namn) as koncept2
                RETURN k1, k2, 
                       [k IN koncept1 WHERE k IN koncept2] as gemensamma,
                       [k IN koncept1 WHERE NOT k IN koncept2] as bara_i_kurs1,
                       [k IN koncept2 WHERE NOT k IN koncept1] as bara_i_kurs2
                """
                result = session.run(query, kurs1=kurs1, kurs2=kurs2).single()
                
                if not result:
                    return {"nodes": [], "edges": []}
                
                # Lägg till kursnoder
                k1 = result['k1']
                k2 = result['k2']
                
                nodes.append({
                    "id": k1['kurskod'],
                    "label": f"{k1['kurskod']}\n{k1['namn']}",
                    "type": "course",
                    "color": "#2196F3",
                    "size": 40,
                    "x": -200,
                    "y": 0
                })
                
                nodes.append({
                    "id": k2['kurskod'],
                    "label": f"{k2['kurskod']}\n{k2['namn']}",
                    "type": "course",
                    "color": "#4CAF50",
                    "size": 40,
                    "x": 200,
                    "y": 0
                })
                
                # Lägg till gemensamma koncept
                y_offset = -150
                for koncept in result['gemensamma']:
                    if koncept:  # Kontrollera att konceptet inte är None
                        nodes.append({
                            "id": koncept,
                            "label": koncept,
                            "type": "shared_concept",
                            "color": "#FF9800",
                            "size": 25,
                            "x": 0,
                            "y": y_offset
                        })
                        edges.append({
                            "from": k1['kurskod'],
                            "to": koncept,
                            "color": "#FF9800",
                            "width": 2
                        })
                        edges.append({
                            "from": k2['kurskod'],
                            "to": koncept,
                            "color": "#FF9800",
                            "width": 2
                        })
                        y_offset += 50
                
                # Lägg till unika koncept för kurs 1
                y_offset = -150
                for koncept in result['bara_i_kurs1']:
                    if koncept:
                        nodes.append({
                            "id": f"{koncept}_1",
                            "label": koncept,
                            "type": "unique_concept",
                            "color": "#2196F3",
                            "size": 20,
                            "x": -300,
                            "y": y_offset
                        })
                        edges.append({
                            "from": k1['kurskod'],
                            "to": f"{koncept}_1",
                            "color": "#2196F3",
                            "width": 1,
                            "dashes": True
                        })
                        y_offset += 40
                
                # Lägg till unika koncept för kurs 2
                y_offset = -150
                for koncept in result['bara_i_kurs2']:
                    if koncept:
                        nodes.append({
                            "id": f"{koncept}_2",
                            "label": koncept,
                            "type": "unique_concept",
                            "color": "#4CAF50",
                            "size": 20,
                            "x": 300,
                            "y": y_offset
                        })
                        edges.append({
                            "from": k2['kurskod'],
                            "to": f"{koncept}_2",
                            "color": "#4CAF50",
                            "width": 1,
                            "dashes": True
                        })
                        y_offset += 40
                
                return {"nodes": nodes, "edges": edges}
                
        except Exception as e:
            print(f"Fel vid skapande av likhetsgraf: {e}")
            return {"nodes": [], "edges": []}
    
    def get_graph_context(self, max_nodes: int = 50) -> str:
        """
        Hämtar kontext från kunskapsgrafen för AI-assistenten
        
        Args:
            max_nodes: Max antal noder att inkludera
            
        Returns:
            Formaterad sträng med grafinformation
        """
        try:
            # Hämta statistik
            stats = self.db.get_graph_statistics()
            
            # Hämta kurslista
            courses_df = self.db.get_courses_list()
            
            # Bygg kontextsträng
            context = f"""KUNSKAPSGRAF ÖVERSIKT:
- Totalt antal kurser: {stats['courses']}
- Totalt antal koncept: {stats['concepts']}
- Totalt antal relationer: {stats['relations']}

KURSER I GRAFEN:
"""
            
            # Lägg till kursinformation
            if not courses_df.empty:
                for _, course in courses_df.head(max_nodes).iterrows():
                    context += f"\n{course['kurskod']} - {course['kursnamn']}"
                    if course['koncept']:
                        context += f"\n  Koncept: {course['koncept']}"
            
            return context
            
        except Exception as e:
            return f"Kunde inte hämta grafkontext: {str(e)}"
    
    def analyze_concept_importance(self) -> pd.DataFrame:
        """
        Analyserar konceptens viktighet baserat på antal relationer
        
        Returns:
            DataFrame med koncept sorterade efter viktighet
        """
        try:
            _, _, all_df = self.db.get_concept_dependencies()
            
            if not all_df.empty:
                # Beräkna viktighet som summan av inkommande och utgående relationer
                all_df['viktighet'] = all_df['krävs_av_antal'] + all_df['kräver_antal']
                all_df = all_df.sort_values('viktighet', ascending=False)
                
                return all_df[['koncept', 'kurser', 'krävs_av_antal', 'kräver_antal', 'viktighet']]
            
            return pd.DataFrame()
            
        except Exception:
            return pd.DataFrame()
    
    def find_learning_path(self, target_course: str) -> List[str]:
        """
        Hittar en rekommenderad inlärningsväg för en målkurs
        
        Args:
            target_course: Kurskod för målkursen
            
        Returns:
            Lista med kurskoder i rekommenderad ordning
        """
        try:
            # Hämta kurser som målkursen bygger på
            dependencies = self.db.get_course_dependencies(target_course)
            
            if dependencies.empty:
                return [target_course]
            
            # Sortera efter antal beroenden och returnera kurskoder
            path = dependencies.sort_values('antal_koncept', ascending=False)['kurskod'].tolist()
            path.append(target_course)
            
            return path
            
        except Exception:
            return [target_course]