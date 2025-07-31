"""
Kunskapsgraf-sida för Chalmers Knowledge Graph Builder
"""
import streamlit as st
import pandas as pd
import base64
import tempfile
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import networkx as nx
from io import BytesIO
from utils.session import init_session_state
from components.network_vis import NetworkVisualizer


def render():
    """Renderar kunskapsgrafsidan"""
    init_session_state()
    
    st.markdown("### Kunskapsgraf")
    st.markdown("Utforska hur kurser och koncept hänger ihop")
    
    # Kontrollera om Neo4j är konfigurerad
    from config import NEO4J_URI, NEO4J_PASSWORD
    
    if not NEO4J_URI or not NEO4J_PASSWORD:
        st.error("Neo4j databas är inte konfigurerad!")
        st.markdown("""
        ### Så här konfigurerar du Neo4j:
        
        1. **Skapa en `.env` fil** i projektets rotmapp om den inte redan finns
        
        2. **Lägg till följande rader** i `.env` filen:
        ```
        NEO4J_URI=neo4j+s://din-databas-uri.neo4j.io
        NEO4J_USER=neo4j
        NEO4J_PASSWORD=ditt-databas-lösenord
        ```
        
        3. **Skapa en gratis Neo4j databas**:
           - Gå till [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/)
           - Skapa ett gratis konto
           - Skapa en ny AuraDB Free databas
           - Kopiera connection URI och lösenord till `.env` filen
        
        4. **Starta om applikationen** efter att du lagt till informationen
        
        Se README.md för mer detaljerad information.
        """)
        return
    
    if not st.session_state.neo4j_service:
        st.error("Kunde inte ansluta till Neo4j databas")
        st.info("Kontrollera att dina uppgifter är korrekta och att databasen är aktiv")
        return
    
    # Hämta statistik
    stats = st.session_state.neo4j_service.get_graph_statistics()
    
    # Visa statistik
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Kurser", stats['courses'])
    with col2:
        st.metric("Koncept", stats['concepts'])
    with col3:
        st.metric("Relationer", stats['relations'])
    with col4:
        st.metric("Totalt antal noder", stats['total_nodes'])
    
    # Filteralternativ
    col1, col2 = st.columns(2)
    
    with col1:
        filter_option = st.selectbox(
            "Visa",
            ["Alla noder", "Bara kurser", "Bara koncept"],
            index=0
        )
    
    with col2:
        # Hämta kurslista för dropdown
        courses = st.session_state.neo4j_service.get_all_courses()
        course_options = ["Ingen"] + [f"{c['kurskod']} - {c['namn']}" for c in courses]
        
        selected = st.selectbox(
            "Markera kurs",
            course_options,
            index=0
        )
        
        if selected != "Ingen":
            st.session_state.highlight_course = selected.split(" - ")[0]
        else:
            st.session_state.highlight_course = None
    
    # Andra raden med filter
    col3, col4 = st.columns(2)
    
    with col3:
        # År-filter
        year_filter = st.selectbox(
            "Filtrera på år",
            ["Alla år", "År 1", "År 2", "År 3", "År 4", "År 5"],
            index=0,
            key="year_filter_graph"  # Unik nyckel
        )
    
    with col4:
        # Läsperiod-filter
        period_filter = st.selectbox(
            "Filtrera på läsperiod",
            ["Alla perioder", "LP1", "LP2", "LP3", "LP4"],
            index=0,
            key="period_filter_graph"  # Unik nyckel
        )
    
    # Kursfilter med dropdown
    selected_courses = []
    all_course_codes = []
    
    if courses:
        all_course_codes = [c['kurskod'] for c in courses]
        
        # Skapa en expander för kursfilter
        with st.expander("Filtrera på kurser", expanded=False):
            st.markdown("Välj vilka kurser som ska visas i grafen:")
            
            # Visa/dölj alla knappar
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Välj alla", key="select_all_courses"):
                    st.session_state.selected_courses_filter = all_course_codes
            with col2:
                if st.button("Avmarkera alla", key="deselect_all_courses"):
                    st.session_state.selected_courses_filter = []
            
            # Initiera session state om det inte finns
            if 'selected_courses_filter' not in st.session_state:
                st.session_state.selected_courses_filter = all_course_codes
            
            # Checkboxar för varje kurs
            selected_courses = []
            for course in courses:
                is_selected = st.checkbox(
                    f"{course['kurskod']} - {course['namn']}",
                    value=course['kurskod'] in st.session_state.selected_courses_filter,
                    key=f"filter_{course['kurskod']}"
                )
                if is_selected:
                    selected_courses.append(course['kurskod'])
            
            # Uppdatera session state
            st.session_state.selected_courses_filter = selected_courses
    
    fixed_nodes = st.checkbox("Fixera noder", value=True)
    
    # Mastery-baserad visualisering
    use_mastery_vis = st.checkbox(
        "Visa mastery-baserad visualisering", 
        value=False,
        help="Koncept med låg mastery blir mer transparenta, de med hög mastery får tydligare färger"
    )
    
    # Avancerade inställningar
    with st.expander("Avancerade visualiseringsinställningar"):
        col1, col2 = st.columns(2)
        
        with col1:
            cluster_similarity = st.checkbox(
                "Gruppera liknande kurser",
                value=False,
                help="Kurser med liknande innehåll placeras närmare varandra"
            )
            
            gravity = st.slider(
                "Gravitationskraft",
                min_value=-20000,
                max_value=-1000,
                value=-8000,
                step=1000,
                help="Hur starkt noder attraheras mot centrum"
            )
        
        with col2:
            spring_length = st.slider(
                "Fjäderlängd",
                min_value=50,
                max_value=300,
                value=120,
                step=10,
                help="Avstånd mellan sammankopplade noder"
            )
    
    # Visa graf
    try:
        visualizer = NetworkVisualizer()
        
        # Hämta grafdata baserat på filter
        nodes = []
        edges = []
        filtered_nodes = set()
        filtered_course_nodes = set()  # Håll reda på filtrerade kurser
        
        with st.session_state.neo4j_service.driver.session() as session:
            # När vi filtrerar på år/period och visar "Alla noder", 
            # visa kurser som matchar filtret plus ALLA koncept som är kopplade till dessa kurser
            if (year_filter != "Alla år" or period_filter != "Alla perioder") and filter_option == "Alla noder":
                # Först: hämta kurser som matchar år/period-filter
                course_conditions = ["n:Kurs"]
                if year_filter != "Alla år":
                    year_num = int(year_filter.split()[-1])
                    course_conditions.append(f"n.år = {year_num}")
                if period_filter != "Alla perioder":
                    period_num = int(period_filter[2])
                    course_conditions.append(f"n.läsperiod = {period_num}")
                
                course_query = "MATCH (n) WHERE " + " AND ".join(course_conditions) + " RETURN n"
                result = session.run(course_query)
                
                for record in result:
                    node = record['n']
                    filtered_course_nodes.add(node.get('kurskod'))
                
                # Sedan: hämta alla koncept som är kopplade till dessa kurser
                if filtered_course_nodes:
                    nodes_query = """
                    MATCH (n)
                    WHERE (n:Kurs AND n.kurskod IN $kurser) 
                       OR (n:Koncept AND EXISTS {
                           MATCH (k:Kurs)-[:INNEHÅLLER]->(n)
                           WHERE k.kurskod IN $kurser
                       })
                    RETURN n
                    """
                    result = session.run(nodes_query, kurser=list(filtered_course_nodes))
                else:
                    # Inga kurser matchar filtret
                    result = []
            else:
                # Standard filtrering
                base_query = "MATCH (n) WHERE "
                where_conditions = []
                
                # Nodtyp-filter
                if filter_option == "Bara kurser":
                    where_conditions.append("n:Kurs")
                elif filter_option == "Bara koncept":
                    where_conditions.append("n:Koncept")
                else:
                    where_conditions.append("(n:Kurs OR n:Koncept)")
                
                # År-filter (bara för kurser)
                if year_filter != "Alla år":
                    year_num = int(year_filter.split()[-1])
                    if filter_option == "Bara kurser":
                        where_conditions.append(f"n.år = {year_num}")
                
                # Period-filter (bara för kurser)
                if period_filter != "Alla perioder":
                    period_num = int(period_filter[2])
                    if filter_option == "Bara kurser":
                        where_conditions.append(f"n.läsperiod = {period_num}")
                
                # Kursfilter - begränsa till valda kurser
                if 'selected_courses' in locals() and selected_courses and len(selected_courses) < len(all_course_codes):
                    if filter_option == "Bara kurser":
                        where_conditions.append(f"n.kurskod IN {selected_courses}")
                    elif filter_option == "Alla noder":
                        # För "Alla noder", filtrera både kurser och deras koncept
                        where_conditions.append(f"(n:Kurs AND n.kurskod IN {selected_courses}) OR (n:Koncept AND EXISTS {{MATCH (k:Kurs)-[:INNEHÅLLER]->(n) WHERE k.kurskod IN {selected_courses}}})")
                
                nodes_query = base_query + " AND ".join(where_conditions) + " RETURN n"
                result = session.run(nodes_query)
            
            # Debug
            if st.checkbox("Visa debug-info", value=False):
                if isinstance(nodes_query, str):
                    st.code(nodes_query)
                else:
                    st.write("Filtrerade kurser:", list(filtered_course_nodes))
            
            # Hämta noder
            for record in result:
                node = record['n']
                node_id = node.get('kurskod') or node.get('namn')
                filtered_nodes.add(node_id)
                
                # Bestäm färg och storlek
                if 'Kurs' in node.labels:
                    color = '#808080' if node_id == st.session_state.highlight_course else '#A9A9A9'
                    size = 35 if node_id == st.session_state.highlight_course else 25
                    label = f"{node.get('kurskod')}\n{node.get('namn', '')}"
                    
                    # Lägg till år och period i tooltip
                    år = node.get('år', '')
                    period = node.get('läsperiod', '')
                    regel = node.get('regel', '')
                    tooltip = f"{node.get('namn_sv', node.get('namn', ''))}\n"
                    tooltip += f"Engelskt namn: {node.get('namn_en', '')}\n"
                    tooltip += f"År {år}, LP{period}\n"
                    tooltip += f"Regel: {regel}\n"
                    if node.get('syfte'):
                        tooltip += f"\nSyfte: {node.get('syfte', '')[:200]}..."
                else:
                    # För koncept, hämta mastery score
                    mastery_score = node.get('mastery_score', 0.0)
                    
                    # Basera färg och transparens på mastery score om visualisering är aktiverad
                    if use_mastery_vis:
                        # Skala transparens baserat på mastery (0.3 för låg mastery, 1.0 för hög)
                        opacity = 0.3 + (mastery_score * 0.7)
                        
                        # Färgskala från rött (låg mastery) till grönt (hög mastery)
                        if mastery_score < 0.3:
                            base_color = '#FF6B6B'  # Rött för låg mastery
                        elif mastery_score < 0.7:
                            base_color = '#FFE66D'  # Gult för medium mastery
                        else:
                            base_color = '#95E1D3'  # Grönt för hög mastery
                        
                        # Konvertera hex till rgba med opacity
                        hex_color = base_color.lstrip('#')
                        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                        color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
                        
                        # Storlek baserat på mastery
                        size = 15 + (mastery_score * 15)  # 15-30 baserat på mastery
                    else:
                        color = '#95E1D3'
                        size = 20
                    
                    label = node.get('namn')
                    tooltip = f"{node.get('beskrivning', label)}\nMastery: {mastery_score:.2f}"
                
                nodes.append({
                    'id': node_id,
                    'label': label,
                    'color': color,
                    'size': size,
                    'title': tooltip
                })
            
            # Hämta relationer - bara mellan filtrerade noder
            edges_query = """
            MATCH (n1)-[r]->(n2)
            WHERE (n1:Kurs OR n1:Koncept) AND (n2:Kurs OR n2:Koncept)
            RETURN n1, r, n2, elementId(n1) as id1, elementId(n2) as id2
            """
            
            result = session.run(edges_query)
            
            for record in result:
                n1 = record['n1']
                n2 = record['n2']
                rel = record['r']
                
                from_id = n1.get('kurskod') or n1.get('namn')
                to_id = n2.get('kurskod') or n2.get('namn')
                
                # Bara inkludera kant om båda noder är med i filtret
                if from_id in filtered_nodes and to_id in filtered_nodes:
                    edges.append({
                        'from': from_id,
                        'to': to_id,
                        'label': rel.type,
                        'color': '#FFE66D' if rel.type == 'FÖRUTSÄTTER' else '#A8E6CF',
                        'arrows': 'to'
                    })
        
        # Anpassad fysik
        custom_physics = None
        if cluster_similarity:
            custom_physics = {
                "solver": "barnesHut",
                "barnesHut": {
                    "gravitationalConstant": -15000,
                    "centralGravity": 0.3,
                    "springLength": 80
                }
            }
        else:
            custom_physics = {
                "solver": "barnesHut",
                "barnesHut": {
                    "gravitationalConstant": gravity,
                    "centralGravity": 0.3,
                    "springLength": spring_length
                }
            }
        
        # Visa grafen
        if nodes:
            # Nedladdningsknapp för graf
            col1, col2 = st.columns([3, 1])
            with col2:
                # Hämta programnamn för nedladdning
                program_name = ""
                if 'selected_program_code' in st.session_state and st.session_state.selected_program_code:
                    # Hämta programnamn från parser istället
                    programs = st.session_state.parser.get_programs()
                    for code, name in programs:
                        if code == st.session_state.selected_program_code:
                            # Ta bort programkoden från namnet
                            program_name = name.split(' - ')[0] if ' - ' in name else name
                            break
                
                if st.button("Ladda ner graf som bild", key="download_graph"):
                    with st.spinner("Genererar bild..."):
                        # Skapa NetworkX-graf
                        G = nx.DiGraph()
                        
                        # Lägg till noder
                        for node in nodes:
                            G.add_node(node['id'], 
                                     label=node['label'], 
                                     color=node['color'],
                                     size=node.get('size', 20))
                        
                        # Lägg till kanter
                        for edge in edges:
                            G.add_edge(edge['from'], edge['to'])
                        
                        # Skapa figur med enkel vit bakgrund
                        fig = plt.figure(figsize=(16, 12), facecolor='white')
                        ax = fig.add_subplot(111, facecolor='white')
                        
                        # Skapa layout - spring layout för bra organisation
                        pos = nx.spring_layout(G, k=2, iterations=50, scale=1.5)
                        
                        # Rita kanter med enkel stil
                        for edge in edges:
                            if edge['from'] in pos and edge['to'] in pos:
                                x = [pos[edge['from']][0], pos[edge['to']][0]]
                                y = [pos[edge['from']][1], pos[edge['to']][1]]
                                
                                # Färgade linjer
                                if edge.get('label') == 'FÖRUTSÄTTER':
                                    color = '#FFB347'  # Orange för förutsättningar
                                else:
                                    color = '#90EE90'  # Ljusgrön för innehåller
                                
                                # Alla linjer är heldragna
                                ax.plot(x, y, color=color, alpha=0.7, linewidth=1.5, 
                                       linestyle='-', zorder=1)
                        
                        # Rita noder med enkel stil
                        for node_id, (x, y) in pos.items():
                            node_data = next((n for n in nodes if n['id'] == node_id), None)
                            if node_data:
                                color_str = node_data.get('color', '#4ECDC4')
                                
                                # Hantera rgba-färger för mastery-visualisering
                                alpha = 0.9
                                if color_str.startswith('rgba'):
                                    import re
                                    rgba_match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
                                    if rgba_match:
                                        r, g, b, a = rgba_match.groups()
                                        color = (int(r)/255, int(g)/255, int(b)/255)
                                        alpha = float(a)
                                    else:
                                        color = color_str
                                else:
                                    color = color_str
                                
                                # Bestäm nodtyp baserat på originalfärg eller innehåll
                                # Kurser har grå (#808080/#A9A9A9) färg
                                # Koncept har grön (#95E1D3) eller rgba-varianter
                                if '#808080' in str(color_str) or '#A9A9A9' in str(color_str):
                                    # Detta är en kurs
                                    size = 800
                                    shape = 's'  # Fyrkant för kurser
                                    if use_mastery_vis and color_str.startswith('rgba'):
                                        # Använd mastery-färg om aktiverad
                                        node_color = color
                                        node_alpha = alpha
                                    else:
                                        node_color = '#808080'  # Grå för kurser
                                        node_alpha = 0.9
                                else:
                                    # Detta är ett koncept
                                    size = 600
                                    shape = 'o'  # Cirkel för koncept
                                    if use_mastery_vis and color_str.startswith('rgba'):
                                        # Använd mastery-färg om aktiverad
                                        node_color = color
                                        node_alpha = alpha
                                    else:
                                        node_color = '#4ECDC4'  # Turkos för koncept
                                        node_alpha = 0.9
                                
                                # Rita nod
                                ax.scatter(x, y, c=[node_color], s=size, marker=shape, 
                                          edgecolors='darkgray', linewidths=1.5, 
                                          zorder=3, alpha=node_alpha)
                                
                                # Lägg till text med Spotify Wrapped-stil
                                label = node_data.get('label', '').split('\n')[0]  # Bara första raden
                                if len(label) > 20:
                                    label = label[:20] + '...'
                                
                                # Modern stil med vit text på mörk bakgrund
                                ax.text(x, y, label.upper(), 
                                       fontsize=7, ha='center', va='center',
                                       fontweight='bold',
                                       color='white',
                                       bbox=dict(boxstyle='round,pad=0.3', 
                                                facecolor='#2D2D2D', 
                                                edgecolor='none',
                                                alpha=0.7),
                                       zorder=4)
                        
                        # Färgad titel
                        fig.text(0.5, 0.94, 'DIN KUNSKAPSGRAF', 
                                ha='center', va='top', fontsize=32, 
                                color='#1DB954', weight='bold',
                                fontfamily='sans-serif')
                        
                        # Lägg till statistik i hörnet
                        # Räkna baserat på nodtyp istället för färg (eftersom färger kan vara rgba nu)
                        course_count = 0
                        concept_count = 0
                        
                        # Kolla genom grafen för att räkna nodtyper
                        with st.session_state.neo4j_service.driver.session() as count_session:
                            for node in nodes:
                                node_id = node['id']
                                # Kolla om det är en kurs eller koncept
                                result = count_session.run("""
                                    MATCH (n) 
                                    WHERE (n:Kurs AND n.kurskod = $id) OR (n:Koncept AND n.namn = $id)
                                    RETURN labels(n) as labels
                                """, id=node_id)
                                
                                record = result.single()
                                if record:
                                    if 'Kurs' in record['labels']:
                                        course_count += 1
                                    elif 'Koncept' in record['labels']:
                                        concept_count += 1
                        
                        # Färgad statistik
                        stats_text = f"{course_count} KURSER • {concept_count} KONCEPT • {len(edges)} KOPPLINGAR"
                        
                        # Lägg till statistik längst ner
                        fig.text(0.5, 0.05, stats_text, 
                                ha='center', va='bottom', fontsize=12, 
                                color='#1DB954', weight='bold',
                                fontfamily='sans-serif', transform=fig.transFigure)
                        
                        # Lägg till undertitel
                        fig.text(0.5, 0.02, 'STUDYBUDDY STUDIO', 
                                ha='center', va='bottom', fontsize=8, 
                                color='#B3B3B3',
                                fontfamily='sans-serif', transform=fig.transFigure)
                        
                        # Ta bort axlar
                        ax.set_xlim(-2.5, 2.5)
                        ax.set_ylim(-2.5, 2.5)
                        ax.axis('off')
                        
                        # Lägg till färgad legend
                        from matplotlib.lines import Line2D
                        legend_elements = [
                            Line2D([0], [0], marker='s', color='w', label='KURSER',
                                  markerfacecolor='#808080', markersize=10, markeredgecolor='darkgray'),
                            Line2D([0], [0], marker='o', color='w', label='KONCEPT',
                                  markerfacecolor='#4ECDC4', markersize=10, markeredgecolor='darkgray'),
                            Line2D([0], [0], color='#90EE90', linewidth=2, label='INNEHÅLLER'),
                            Line2D([0], [0], color='#FFB347', linewidth=2, label='FÖRUTSÄTTER')
                        ]
                        ax.legend(handles=legend_elements, loc='upper right', frameon=True,
                                 fancybox=True, shadow=True)
                        
                        # Spara till bytes
                        buf = BytesIO()
                        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', 
                                   facecolor='white', edgecolor='none')
                        buf.seek(0)
                        
                        # Skapa nedladdningsknapp med dagens datum
                        from datetime import datetime
                        today = datetime.now().strftime("%Y-%m-%d")
                        st.download_button(
                            label="Klicka här för att ladda ner bilden",
                            data=buf,
                            file_name=f"kunskapsgraf_{today}.png",
                            mime="image/png"
                        )
                        
                        plt.close(fig)
            
            # Visa grafen
            with col1:
                visualizer.display_graph(
                    nodes=nodes,
                    edges=edges,
                    height="600px",
                    physics_enabled=not fixed_nodes,
                    custom_physics=custom_physics,
                    key="knowledge_graph"
                )
        else:
            st.info("Inga noder att visa med nuvarande filter")
        
    except Exception as e:
        st.error(f"Kunde inte visa grafen: {str(e)}")
    
    # Visa kurser i grafen med deras koncept
    with st.expander("Individuella kursgrafer - Klicka här för att se detaljerade grafer för varje kurs", expanded=True):
        if stats['courses'] > 0:
            with st.session_state.neo4j_service.driver.session() as session:
                # Hämta alla kurser med deras koncept
                query = """
                MATCH (k:Kurs)
                OPTIONAL MATCH (k)-[:INNEHÅLLER]->(c:Koncept)
                RETURN k.kurskod as kurskod, 
                       k.namn as namn,
                       k.år as år,
                       k.läsperiod as period,
                       k.regel as regel,
                       collect(c.namn) as koncept
                ORDER BY k.år, k.läsperiod, k.kurskod
                """
                result = session.run(query)
                
                kurser = list(result)
                if kurser:
                    current_year = None
                    for record in kurser:
                        year = record['år'] or 0
                        if year != current_year:
                            if year > 0:
                                st.markdown(f"#### År {year}")
                            else:
                                st.markdown("#### År ej angivet")
                            current_year = year
                        
                        regel_text = ""
                        if record['regel'] == 'O':
                            regel_text = " (Obligatorisk)"
                        elif record['regel'] == 'V':
                            regel_text = " (Valbar)"
                        elif record['regel'] == 'X':
                            regel_text = " (Examensarbete)"
                        elif record['regel'] == 'F':
                            regel_text = " (Fristående)"
                        
                        period_text = f"LP{record['period']}" if record['period'] else "Period ej angiven"
                        
                        # Använd expander för varje kurs
                        with st.expander(f"{record['kurskod']} - {record['namn']} ({period_text}){regel_text}"):
                            if record['koncept']:
                                koncept_list = [k for k in record['koncept'] if k]
                                if koncept_list:
                                    # Visa konceptlista
                                    st.markdown("**Koncept i kursen:**")
                                    for koncept in koncept_list:
                                        st.markdown(f"  - {koncept}")
                                    
                                    # Skapa individuell graf för kursen
                                    st.markdown("**Kursgraf:**")
                                    
                                    # Hämta noder och relationer för denna specifika kurs
                                    course_nodes = []
                                    course_edges = []
                                    
                                    # Lägg till kursnoden
                                    course_nodes.append({
                                        'id': record['kurskod'],
                                        'label': f"{record['kurskod']}\n{record['namn']}",
                                        'color': '#808080',
                                        'size': 30,
                                        'title': record['namn']
                                    })
                                    
                                    # Hämta koncept och relationer för kursen - skapa ny session
                                    with st.session_state.neo4j_service.driver.session() as concept_session:
                                        concept_query = """
                                        MATCH (k:Kurs {kurskod: $kurskod})-[:INNEHÅLLER]->(c:Koncept)
                                        OPTIONAL MATCH (c)-[:FÖRUTSÄTTER]->(p:Koncept)
                                        RETURN c.namn as koncept, c.beskrivning as beskrivning,
                                               collect(DISTINCT p.namn) as prerequisites
                                        """
                                        concept_result = concept_session.run(concept_query, kurskod=record['kurskod'])
                                        
                                        added_concepts = set()
                                        for concept_rec in concept_result:
                                            koncept_namn = concept_rec['koncept']
                                            if koncept_namn and koncept_namn not in added_concepts:
                                                # Lägg till konceptnod
                                                course_nodes.append({
                                                    'id': koncept_namn,
                                                    'label': koncept_namn,
                                                    'color': '#95E1D3',
                                                    'size': 20,
                                                    'title': concept_rec['beskrivning'] or koncept_namn
                                                })
                                                added_concepts.add(koncept_namn)
                                                
                                                # Lägg till kant från kurs till koncept
                                                course_edges.append({
                                                    'from': record['kurskod'],
                                                    'to': koncept_namn,
                                                    'label': 'INNEHÅLLER',
                                                    'color': '#A8E6CF',
                                                    'arrows': 'to'
                                                })
                                                
                                                # Lägg till förutsättningar
                                                for prereq in concept_rec['prerequisites']:
                                                    if prereq and prereq not in added_concepts:
                                                        course_nodes.append({
                                                            'id': prereq,
                                                            'label': prereq,
                                                            'color': '#FFE66D',
                                                            'size': 15,
                                                            'title': f"Förutsättning: {prereq}"
                                                        })
                                                        added_concepts.add(prereq)
                                                    
                                                    if prereq:
                                                        course_edges.append({
                                                            'from': koncept_namn,
                                                            'to': prereq,
                                                            'label': 'FÖRUTSÄTTER',
                                                            'color': '#FFE66D',
                                                            'arrows': 'to'
                                                        })
                                    
                                    # Visa grafen om det finns noder
                                    if len(course_nodes) > 1:
                                        # Anpassad fysik för bättre layout utan överlapp
                                        course_physics = {
                                            "solver": "barnesHut",
                                            "barnesHut": {
                                                "gravitationalConstant": -8000,
                                                "centralGravity": 0.3,
                                                "springLength": 150,
                                                "springConstant": 0.04,
                                                "damping": 0.09,
                                                "avoidOverlap": 0.5
                                            },
                                            "stabilization": {
                                                "enabled": True,
                                                "iterations": 1000,
                                                "updateInterval": 50
                                            }
                                        }
                                        
                                        course_visualizer = NetworkVisualizer()
                                        course_visualizer.display_graph(
                                            nodes=course_nodes,
                                            edges=course_edges,
                                            height="400px",
                                            physics_enabled=True,
                                            custom_physics=course_physics,
                                            key=f"course_graph_{record['kurskod']}"
                                        )
                                else:
                                    st.markdown("  *Inga koncept registrerade*")
                            else:
                                st.markdown("  *Inga koncept registrerade*")
                else:
                    st.info("Inga kurser hittades i grafen")
        else:
            st.info("Inga kurser i grafen ännu. Gå till fliken 'Kurser' för att bygga grafen.")
    
    # Tips
    with st.expander("Tips för att använda grafen"):
        st.markdown("""
        - **Klicka på noder** för att se mer information
        - **Dra noder** för att omorganisera layouten
        - **Scrolla** för att zooma in/ut
        - **Dubbelklicka** på bakgrunden för att återställa zoom
        - **Håll ner Shift** och klicka för att välja flera noder
        - Använd **filteralternativen** för att fokusera på specifika delar
        - **År-filter** visar bara kurser från specifikt år (koncept visas alltid)
        - **Period-filter** visar bara kurser från specifik läsperiod
        """)


if __name__ == "__main__":
    render()