"""
Neo4j databas-service för StudyBuddy
Hanterar alla databaskopplingar och frågor mot Neo4j
"""
import pandas as pd
import json
from neo4j import GraphDatabase
from typing import Dict, List, Tuple, Optional
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jService:
    """Service för att hantera Neo4j-databasoperationer"""
    
    def __init__(self):
        """Initialiserar Neo4j-drivrutinen"""
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    def close(self):
        """Stänger databasanslutningen"""
        if self.driver:
            self.driver.close()
    
    def get_graph_statistics(self) -> Dict[str, int]:
        """
        Hämtar statistik från grafen
        
        Returns:
            Dict med antal kurser, koncept, relationer och totala noder
        """
        try:
            with self.driver.session() as session:
                stats = {}
                stats['courses'] = session.run("MATCH (n:Kurs) RETURN count(n) as count").single()['count']
                stats['concepts'] = session.run("MATCH (n:Koncept) RETURN count(n) as count").single()['count']
                stats['relations'] = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                stats['total_nodes'] = stats['courses'] + stats['concepts']
                return stats
        except Exception:
            return {'courses': 0, 'concepts': 0, 'relations': 0, 'total_nodes': 0}

    def get_courses_list(self) -> pd.DataFrame:
        """
        Hämtar lista över kurser med deras koncept
        
        Returns:
            DataFrame med kurskod, kursnamn, antal_koncept och koncept
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (k:Kurs)
                OPTIONAL MATCH (k)-[:INNEHÅLLER]->(c:Koncept)
                RETURN k.kurskod as kurskod, 
                       k.namn as kursnamn,
                       count(c) as antal_koncept,
                       collect(c.namn) as koncept
                ORDER BY k.kurskod
                """
                result = session.run(query)
                df = pd.DataFrame([dict(record) for record in result])
                if not df.empty:
                    df['koncept'] = df['koncept'].apply(lambda x: ', '.join(x) if x else '')
                return df
        except Exception:
            return pd.DataFrame()

    def search_concepts(self, search_term: str) -> List[Dict[str, str]]:
        """
        Söker efter koncept baserat på sökterm
        
        Args:
            search_term: Sökterm att matcha mot konceptnamn
            
        Returns:
            Lista med dict innehållande concept och courses
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (c:Koncept)<-[:INNEHÅLLER]-(k:Kurs)
                WHERE toLower(c.namn) CONTAINS toLower($search_term)
                RETURN c.namn as concept, collect(k.kurskod) as courses
                """
                result = session.run(query, search_term=search_term)
                return [{'concept': r['concept'], 'courses': ', '.join(r['courses'])} for r in result]
        except Exception:
            return []

    def get_concept_dependencies(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Hämtar koncept med antal förutsättningar och beroenden
        
        Returns:
            Tuple med tre DataFrames:
            - prereq_df: Koncept som förutsätts av andra
            - depends_df: Koncept som förutsätter andra
            - all_df: Alla koncept med fullständig information
        """
        try:
            with self.driver.session() as session:
                # Koncept som förutsätts av andra (inkommande pilar)
                query_prereq = """
                MATCH (c:Koncept)<-[:FÖRUTSÄTTER]-(other:Koncept)
                RETURN c.namn as koncept, count(other) as antal_som_kräver_detta
                ORDER BY antal_som_kräver_detta DESC
                """
                prereq_result = session.run(query_prereq)
                prereq_df = pd.DataFrame([dict(r) for r in prereq_result])
                
                # Koncept som förutsätter andra (utgående pilar)
                query_depends = """
                MATCH (c:Koncept)-[:FÖRUTSÄTTER]->(other:Koncept)
                RETURN c.namn as koncept, count(other) as antal_förutsättningar
                ORDER BY antal_förutsättningar DESC
                """
                depends_result = session.run(query_depends)
                depends_df = pd.DataFrame([dict(r) for r in depends_result])
                
                # Alla koncept med deras kurser
                query_all = """
                MATCH (c:Koncept)
                OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
                OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(req_by:Koncept)
                OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(requires:Koncept)
                RETURN c.namn as koncept,
                       collect(DISTINCT k.kurskod) as kurser,
                       count(DISTINCT req_by) as krävs_av_antal,
                       count(DISTINCT requires) as kräver_antal,
                       collect(DISTINCT req_by.namn) as krävs_av,
                       collect(DISTINCT requires.namn) as kräver
                ORDER BY krävs_av_antal DESC, c.namn
                """
                all_result = session.run(query_all)
                all_df = pd.DataFrame([dict(r) for r in all_result])
                
                return prereq_df, depends_df, all_df
        except Exception:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def get_course_similarity(self) -> pd.DataFrame:
        """
        Beräknar likhet mellan kurser baserat på gemensamma koncept
        
        Returns:
            DataFrame med kurspar och deras gemensamma koncept
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (k1:Kurs)-[:INNEHÅLLER]->(c:Koncept)<-[:INNEHÅLLER]-(k2:Kurs)
                WHERE k1.kurskod < k2.kurskod
                RETURN k1.kurskod as kurs1, 
                       k1.namn as kursnamn1,
                       k2.kurskod as kurs2, 
                       k2.namn as kursnamn2,
                       count(c) as gemensamma_koncept,
                       collect(c.namn) as koncept_lista
                ORDER BY gemensamma_koncept DESC
                """
                result = session.run(query)
                return pd.DataFrame([dict(r) for r in result])
        except Exception:
            return pd.DataFrame()

    def get_course_dependencies(self, kurskod: str) -> pd.DataFrame:
        """
        Hämtar vilka kurser en given kurs bygger på
        
        Args:
            kurskod: Kurskod att analysera
            
        Returns:
            DataFrame med kurser som denna kurs bygger på
        """
        try:
            with self.driver.session() as session:
                # Hitta kurser som denna kurs bygger på
                query = """
                MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c1:Koncept)-[:FÖRUTSÄTTER]->(c2:Koncept)<-[:INNEHÅLLER]-(k2:Kurs)
                WHERE k.kurskod <> k2.kurskod
                WITH k2, count(DISTINCT c2) as antal_koncept
                RETURN k2.kurskod as kurskod, 
                       k2.namn as kursnamn,
                       antal_koncept
                ORDER BY antal_koncept DESC
                """
                result = session.run(query, kurskod=kurskod)
                return pd.DataFrame([dict(r) for r in result])
        except Exception:
            return pd.DataFrame()

    def get_existing_graph_as_json(self) -> str:
        """
        Hämtar hela grafen från Neo4j som JSON-sträng
        
        Returns:
            JSON-sträng med noder och relationer
        """
        try:
            with self.driver.session(database="neo4j") as session:
                # Hämta alla noder
                nodes_query = """
                MATCH (n)
                RETURN collect({
                    id: elementId(n),
                    labels: labels(n),
                    properties: properties(n)
                }) as nodes
                """
                nodes_result = session.run(nodes_query).single()
                
                # Hämta alla relationer - mer robust hantering
                rels_query = """
                MATCH (n1)-[r]->(n2)
                WITH n1, n2, r,
                     CASE 
                        WHEN 'Kurs' IN labels(n1) AND n1.kurskod IS NOT NULL THEN n1.kurskod
                        WHEN n1.namn IS NOT NULL THEN n1.namn
                        ELSE toString(elementId(n1))
                     END as from_id,
                     CASE 
                        WHEN 'Kurs' IN labels(n2) AND n2.kurskod IS NOT NULL THEN n2.kurskod
                        WHEN n2.namn IS NOT NULL THEN n2.namn
                        ELSE toString(elementId(n2))
                     END as to_id
                RETURN collect({
                    from: from_id,
                    to: to_id,
                    type: type(r),
                    from_label: labels(n1)[0],
                    to_label: labels(n2)[0]
                }) as relationships
                """
                rels_result = session.run(rels_query).single()
                
            # Konvertera datetime till sträng
            def convert_datetime(obj):
                """Konvertera Neo4j datetime till sträng"""
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                return obj
            
            graph_json = {
                "nodes": convert_datetime(nodes_result["nodes"] if nodes_result else []),
                "relationships": convert_datetime(rels_result["relationships"] if rels_result else [])
            }
            
            return json.dumps(graph_json, indent=2, ensure_ascii=False, default=str)
        
        except Exception as e:
            # Om något går fel, returnera en tom graf med felmeddelande
            import traceback
            error_graph = {
                "nodes": [],
                "relationships": [],
                "error": f"Fel vid hämtning av graf: {str(e)}",
                "traceback": traceback.format_exc()
            }
            return json.dumps(error_graph, indent=2, ensure_ascii=False)

    def run_cypher_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """
        Kör en godtycklig Cypher-fråga
        
        Args:
            query: Cypher-frågan att köra
            parameters: Eventuella parametrar till frågan
            
        Returns:
            Lista med resultat som dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception:
            return []

    def get_all_courses(self) -> List[Dict[str, str]]:
        """
        Hämtar alla kurser från databasen
        
        Returns:
            Lista med dict innehållande kurskod och namn
        """
        try:
            with self.driver.session() as session:
                query = "MATCH (k:Kurs) RETURN k.kurskod as kurskod, k.namn as namn ORDER BY k.kurskod"
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception:
            return []

    def get_all_concepts(self) -> List[str]:
        """
        Hämtar alla koncept från databasen
        
        Returns:
            Lista med konceptnamn
        """
        try:
            with self.driver.session() as session:
                query = "MATCH (c:Koncept) RETURN c.namn as namn ORDER BY c.namn"
                result = session.run(query)
                return [record['namn'] for record in result]
        except Exception:
            return []

    def get_course_details(self, kurskod: str) -> Optional[Dict]:
        """
        Hämtar detaljerad information om en kurs
        
        Args:
            kurskod: Kurskoden att hämta information om
            
        Returns:
            Dict med kursinformation eller None
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (k:Kurs {kurskod: $kurskod})
                OPTIONAL MATCH (k)-[:INNEHÅLLER]->(c:Koncept)
                RETURN k.kurskod as kurskod,
                       k.namn as namn,
                       k.beskrivning as beskrivning,
                       collect(c.namn) as koncept
                """
                result = session.run(query, kurskod=kurskod).single()
                if result:
                    return dict(result)
                return None
        except Exception:
            return None

    def get_concept_details(self, concept_name: str) -> Optional[Dict]:
        """
        Hämtar detaljerad information om ett koncept
        
        Args:
            concept_name: Namnet på konceptet
            
        Returns:
            Dict med konceptinformation eller None
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (c:Koncept {namn: $namn})
                OPTIONAL MATCH (c)<-[:INNEHÅLLER]-(k:Kurs)
                OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(req:Koncept)
                OPTIONAL MATCH (c)<-[:FÖRUTSÄTTER]-(dep:Koncept)
                RETURN c.namn as namn,
                       c.beskrivning as beskrivning,
                       collect(DISTINCT k.kurskod) as kurser,
                       collect(DISTINCT req.namn) as förutsätter,
                       collect(DISTINCT dep.namn) as förutsätts_av
                """
                result = session.run(query, namn=concept_name).single()
                if result:
                    return dict(result)
                return None
        except Exception:
            return None