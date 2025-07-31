"""
Canvas Explorer-sida för StudyBuddy
"""
import streamlit as st
import pandas as pd
from utils.session import init_session_state, lazy_init_canvas_api


def render():
    """Renderar Canvas Explorer-sidan"""
    init_session_state()
    
    st.markdown("### Canvas Explorer")
    st.markdown("Utforska dina Canvas-kurser och material")
    
    # Kontrollera om Canvas API är konfigurerad
    from config import CANVAS_TOKEN, CANVAS_BASE_URL
    
    if not CANVAS_TOKEN or not CANVAS_BASE_URL:
        st.error("Canvas API är inte konfigurerad!")
        st.markdown("""
        ### Så här konfigurerar du Canvas:
        
        1. **Skapa en `.env` fil** i projektets rotmapp om den inte redan finns
        
        2. **Lägg till följande rader** i `.env` filen:
        ```
        CANVAS_TOKEN=din_canvas_api_token_här
        CANVAS_BASE_URL=https://chalmers.instructure.com
        ```
        
        3. **Hämta din Canvas API-token**:
           - Logga in på Canvas
           - Gå till Konto → Inställningar
           - Klicka på "+ Ny åtkomsttoken" under "Godkända integrationer"
           - Ge token ett namn och klicka "Generera token"
           - Kopiera token till `.env` filen
        
        4. **Starta om applikationen** efter att du lagt till informationen
        
        Se README.md för mer detaljerad information.
        """)
        return
    
    # Lazy-init Canvas API
    canvas_api = lazy_init_canvas_api()
    
    if not canvas_api:
        st.error("Kunde inte ansluta till Canvas API")
        st.info("Kontrollera att din token är giltig och att Canvas är tillgängligt")
        return
    
    # Hämta kurser om de inte redan är laddade
    if 'user_courses' not in st.session_state:
        st.session_state.user_courses = None
    
    if 'selected_canvas_course' not in st.session_state:
        st.session_state.selected_canvas_course = None
    
    if 'course_modules' not in st.session_state:
        st.session_state.course_modules = {}
    
    if st.session_state.user_courses is None:
        with st.spinner("Hämtar dina kurser från Canvas..."):
            try:
                courses = canvas_api.get_user_courses()
                st.session_state.user_courses = courses
            except Exception as e:
                st.error(f"Kunde inte hämta kurser: {str(e)}")
                st.info("Kontrollera att din Canvas-token är korrekt konfigurerad i .env-filen")
                return
    
    if not st.session_state.user_courses:
        st.warning("Inga kurser hittades på ditt Canvas-konto")
        return
    
    # Kursväljare med sökfunktion
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Skapa lista med kurser för dropdown
        course_options = []
        course_dict = {}
        
        # Lägg till favoriter först om de finns
        if 'favorite_courses' not in st.session_state:
            st.session_state.favorite_courses = set()
        
        favorites = []
        non_favorites = []
        
        for course in st.session_state.user_courses:
            course_id = course['id']
            course_label = f"{course.get('course_code', 'N/A')} - {course.get('name', 'Namnlös kurs')}"
            
            if course_id in st.session_state.favorite_courses:
                favorites.append((course_id, f"[FAVORIT] {course_label}", course))
            else:
                non_favorites.append((course_id, course_label, course))
        
        # Kombinera favoriter först, sedan övriga
        all_courses = favorites + non_favorites
        
        if all_courses:
            course_labels = [label for _, label, _ in all_courses]
            course_mapping = {label: course for _, label, course in all_courses}
            
            # Hitta index för vald kurs eller första favoriten
            default_index = 0
            if st.session_state.selected_canvas_course:
                # Försök hitta redan vald kurs
                for i, label in enumerate(course_labels):
                    if course_mapping[label]['id'] == st.session_state.selected_canvas_course['id']:
                        default_index = i
                        break
            elif favorites:
                # Om ingen kurs är vald men det finns favoriter, välj första favoriten
                default_index = 0
            
            # Dropdown med sökfunktion
            selected_label = st.selectbox(
                "Välj kurs",
                course_labels,
                index=default_index,
                placeholder="Sök eller välj kurs..."
            )
            
            if selected_label and selected_label in course_mapping:
                selected_course = course_mapping[selected_label]
                if st.session_state.selected_canvas_course != selected_course:
                    st.session_state.selected_canvas_course = selected_course
                    # Rensa moduler för att tvinga omladdning
                    if selected_course['id'] in st.session_state.course_modules:
                        del st.session_state.course_modules[selected_course['id']]
    
    with col2:
        if st.session_state.selected_canvas_course:
            course_id = st.session_state.selected_canvas_course['id']
            is_favorite = course_id in st.session_state.favorite_courses
            
            if st.button(
                "Favoritmarkerad" if is_favorite else "Markera som favorit",
                key="toggle_favorite",
                use_container_width=True
            ):
                if is_favorite:
                    st.session_state.favorite_courses.remove(course_id)
                else:
                    st.session_state.favorite_courses.add(course_id)
                st.rerun()
    
    # Visa vald kurs
    if st.session_state.selected_canvas_course:
        course = st.session_state.selected_canvas_course
        course_id = course['id']
        
        st.markdown(f"## {course.get('name', 'Namnlös kurs')}")
        st.markdown(f"**Kurskod:** {course.get('course_code', 'N/A')}")
        
        # Kursflikar
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Moduler", "Filer", "Uppgifter", "Kursplan", "Lägg till i graf"])
        
        with tab1:
            render_modules(course_id, canvas_api)
        
        with tab2:
            render_files(course_id, canvas_api)
        
        with tab3:
            render_assignments(course_id, canvas_api)
        
        with tab4:
            render_syllabus(course_id, canvas_api)
        
        with tab5:
            render_add_to_graph(course, canvas_api)
    else:
        st.info("Välj en kurs från dropdown-menyn ovan för att börja utforska")
    
    # AI Chat-sektion
    st.divider()
    
    # Kontrollera om LiteLLM är konfigurerat innan chat visas
    from config import LITELLM_API_KEY, LITELLM_BASE_URL
    if not LITELLM_API_KEY or not LITELLM_BASE_URL:
        st.warning("AI Chat är inte tillgänglig - LiteLLM API saknas")
        st.markdown("""
        För att aktivera AI Chat, lägg till följande i din `.env` fil:
        ```
        LITELLM_API_KEY=din_api_nyckel
        LITELLM_BASE_URL=din_base_url
        LITELLM_MODEL=anthropic/claude-sonnet-3.7
        ```
        """)
    else:
        from pages.canvas_chat import render as render_chat
        render_chat()


def render_modules(course_id: int, canvas_api):
    """Renderar kursmoduler"""
    # Hämta moduler om de inte finns cachade
    if course_id not in st.session_state.course_modules:
        with st.spinner("Hämtar moduler..."):
            try:
                modules = canvas_api.get_course_modules(course_id)
                st.session_state.course_modules[course_id] = modules
            except Exception as e:
                st.error(f"Kunde inte hämta moduler: {str(e)}")
                return
    
    modules = st.session_state.course_modules[course_id]
    
    if not modules:
        st.info("Inga moduler hittades för denna kurs")
        return
    
    # Visa moduler
    for module in modules:
        with st.expander(f"{module.get('name', 'Namnlös modul')}", expanded=False):
            # Visa modulinnehåll
            items = module.get('items', [])
            
            if not items:
                # Hämta items separat om de inte inkluderades
                try:
                    items = canvas_api.get_module_items(course_id, module['id'])
                except Exception:
                    st.warning("Kunde inte hämta modulinnehåll")
                    continue
            
            for item in items:
                item_type = item.get('type', 'Unknown')
                item_title = item.get('title', 'Namnlös')
                
                # Ikoner baserat på typ
                # Visa item
                item_prefix = {
                    'Page': 'Sida:',
                    'File': 'Fil:',
                    'Assignment': 'Uppgift:',
                    'Quiz': 'Quiz:',
                    'Discussion': 'Diskussion:',
                    'ExternalUrl': 'Länk:',
                    'ExternalTool': 'Verktyg:',
                    'SubHeader': 'Rubrik:'
                }.get(item_type, '')
                
                st.markdown(f"**{item_prefix} {item_title}**")
                
                # Visa sidinnehåll för Pages
                if item_type == 'Page' and item.get('page_url'):
                    page_slug = canvas_api.get_page_slug_from_url(item['page_url'])
                    if page_slug:
                        with st.spinner("Hämtar sidinnehåll..."):
                            content = canvas_api.fetch_page_content(
                                course_id, 
                                page_slug,
                                max_chars=500
                            )
                            if content != "Kunde inte hämta innehåll":
                                st.markdown(f"*{content}*")
                
                # Länk för externa URLs
                elif item_type == 'ExternalUrl' and item.get('external_url'):
                    st.markdown(f"[Öppna länk]({item['external_url']})")


def render_files(course_id: int, canvas_api):
    """Renderar kursfiler"""
    # Lazy loading - visa knapp först
    if f'show_files_{course_id}' not in st.session_state:
        st.session_state[f'show_files_{course_id}'] = False
    
    if not st.session_state[f'show_files_{course_id}']:
        if st.button("Hämta filer", key=f"fetch_files_{course_id}", type="primary"):
            st.session_state[f'show_files_{course_id}'] = True
            st.rerun()
        else:
            st.info("Klicka på knappen för att hämta kursfiler")
            return
    
    with st.spinner("Hämtar filer och mappar..."):
        try:
            # Hämta mappar och filer
            folders_df = canvas_api.get_course_folders(course_id)
            files_df = canvas_api.get_course_files(course_id)
            
            if files_df.empty:
                st.info("Inga filer hittades för denna kurs")
                return
            
            # Visa filstatistik
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Antal filer", len(files_df))
            with col2:
                total_size = files_df['size_b'].sum()
                st.metric("Total storlek", canvas_api.fmt_size(total_size))
            with col3:
                st.metric("Antal mappar", len(folders_df))
            
            # Sökfunktion
            search = st.text_input("Sök filer", placeholder="Sök på filnamn...")
            
            if search:
                mask = files_df['name'].str.contains(search, case=False, na=False)
                files_df = files_df[mask]
            
            # Visa mappträd
            if not folders_df.empty:
                st.markdown("#### Mappstruktur")
                
                # Bygg och visa mappträd
                tree_data = canvas_api.build_folder_tree(folders_df, files_df)
                
                # Rendera trädet - börja med root-mappar
                for root_id in tree_data['root_ids']:
                    render_folder_tree(tree_data, course_id, canvas_api, root_id, 0)
            else:
                # Visa bara filer om inga mappar finns
                st.markdown("#### Alla filer")
                for _, file in files_df.iterrows():
                    render_file_item(file, course_id)
                    
        except Exception as e:
            st.error(f"Kunde inte hämta filer: {str(e)}")


def render_folder_tree(tree_data: dict, course_id: int, canvas_api, folder_id=None, indent=0):
    """Renderar mappträd rekursivt"""
    children = tree_data['children']
    folder_info = tree_data['folder_info']
    files_in_folder = tree_data['files_in_folder']
    
    # Hämta barn till denna mapp
    child_folders = children.get(folder_id, [])
    files = files_in_folder.get(folder_id, [])
    
    # Visa mappar
    for child_id in sorted(child_folders, key=lambda x: folder_info[x][0].lower()):
        name, _ = folder_info[child_id]
        n_files = len(files_in_folder.get(child_id, []))
        
        with st.expander(f"{'　' * indent}{name} ({n_files} filer)", expanded=False):
            # Visa filer i denna mapp
            for file in sorted(files_in_folder.get(child_id, []), key=lambda x: x['name'].lower()):
                render_file_item(file, course_id, indent + 1)
            
            # Rekursivt visa undermappar
            render_folder_tree(tree_data, course_id, canvas_api, child_id, indent + 1)


def render_file_item(file: pd.Series, course_id: int, indent: int = 0):
    """Renderar en fil"""
    # Import canvas_api from parent scope or get from session state
    from utils.session import lazy_init_canvas_api
    canvas_api = lazy_init_canvas_api()
    
    size = canvas_api.fmt_size(file['size_b'])
    file_type = "[PDF]" if file.get('mime', '').startswith("application/pdf") else ""
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.markdown(f"{'　' * indent}{file_type} {file['name']} ({size})")
    
    with col2:
        if st.button("Använd i chatt", key=f"chat_file_{file['id']}", help="Använd denna fil i AI-chatten"):
            # Förbered fil för chat
            file_info = {
                "name": file['name'],
                "url": file.get('url'),
                "mime": file.get('mime', ''),
                "size": canvas_api.fmt_size(file.get('size_b', 0))
            }
            
            # För textfiler, ladda innehåll direkt
            if file.get('mime') in ["text/plain", "text/csv", "application/json", "text/html", "text/markdown"]:
                content = canvas_api.download_file_content(file['url'])
                if content:
                    file_info['content'] = content
                    st.session_state.chat_file = file_info
                    st.success(f"Fil '{file['name']}' redo för chatt!")
                    st.info("Scrolla ner till chatten för att ställa frågor om filen")
                else:
                    st.error("Kunde inte ladda filen")
            else:
                # För PDF och andra filer, låt chat-komponenten hantera det
                st.session_state.chat_file = file_info
                st.success(f"Fil '{file['name']}' redo för chatt!")
                st.info("Scrolla ner till chatten för att ställa frågor om filen")
    
    with col3:
        st.markdown(f"[Ladda ner]({file['url']})")


def render_syllabus(course_id: int, canvas_api):
    """Renderar kursplan"""
    with st.spinner("Hämtar kursplan..."):
        short_syllabus, full_syllabus = canvas_api.fetch_syllabus(course_id)
        
        if full_syllabus and full_syllabus != "Ingen kursplan tillgänglig":
            # Visa kort version först
            st.markdown("#### Sammanfattning")
            st.info(short_syllabus)
            
            # Expanderbar full version
            with st.expander("Visa fullständig kursplan"):
                st.markdown(full_syllabus)
        else:
            st.info("Ingen kursplan tillgänglig för denna kurs")


def render_add_to_graph(course, canvas_api):
    """Renderar gränssnitt för att lägga till kurs i kunskapsgrafen"""
    st.markdown("#### Lägg till kurs i kunskapsgrafen")
    st.info("AI kommer att analysera kursplanen och extrahera relevanta koncept baserat på dina inställningar.")
    
    # Visa inställningar
    col1, col2 = st.columns(2)
    
    with col1:
        max_concepts = st.number_input(
            "Max antal koncept per kurs",
            min_value=1,
            max_value=30,
            value=st.session_state.get('max_concepts', 10),
            step=1,
            help="Maximalt antal koncept som ska extraheras från kursen"
        )
    
    with col2:
        language = st.selectbox(
            "Språk för analys",
            ["Svenska", "Engelska"],
            index=0 if st.session_state.get('language', 'Svenska') == 'Svenska' else 1,
            help="Vilket språk AI ska använda för att analysera kursen"
        )
    
    # Samla kursinformation
    course_code = course.get('course_code', 'N/A')
    course_name = course.get('name', 'Okänd kurs')
    
    st.markdown(f"**Kurs att lägga till:** {course_code} - {course_name}")
    
    if st.button("Lägg till kurs i kunskapsgrafen", type="primary"):
        with st.spinner(f"Bygger graf för {course_code}..."):
            try:
                # Visa vilken AI-modell som används
                from config import LITELLM_MODEL
                st.info(f"AI analyserar med modell: **{LITELLM_MODEL}**")
                
                # Visa vilka koncept som extraheras
                # Hämta kursplan
                _, full_syllabus = canvas_api.fetch_syllabus(course['id'])
                
                course_info = f"""
Kurskod: {course_code}
Kursnamn: {course_name}

"""
                if full_syllabus and full_syllabus != "Ingen kursplan tillgänglig":
                    course_info += f"Kursplan:\n{full_syllabus}"
                
                # Använd samma byggfunktion som i Bygg graf
                from src.graph_builder import GraphBuilder
                if 'graph_builder' not in st.session_state:
                    st.session_state.graph_builder = GraphBuilder()
                
                # Temporärt lägg till kursen i parser så den kan hittas
                # Detta är en workaround eftersom Canvas-kurser inte finns i course_summary_full.json
                if 'parser' not in st.session_state:
                    from src.course_parser import CourseParser
                    st.session_state.parser = CourseParser()
                
                # Skapa temporär kursdata som parser förväntar sig
                temp_course_data = {
                    'courseCode': course_code,
                    'name': course_name,
                    'nameAlt': course_name,
                    'purpose': full_syllabus if full_syllabus and full_syllabus != "Ingen kursplan tillgänglig" else "",
                    'AI_summary': f"Canvas-kurs: {course_name}"
                }
                
                # Lägg till kursen temporärt till parserns cache
                st.session_state.parser._temp_canvas_course = temp_course_data
                
                # Extrahera koncept med LLM och visa dem
                st.info("AI extraherar koncept...")
                concepts = st.session_state.graph_builder.llm.extract_concepts(
                    course_info, 
                    st.session_state.graph_builder._get_existing_concepts_summary(),
                    max_concepts=max_concepts,
                    language=language
                )
                
                if concepts:
                    st.success(f"AI hittade {len(concepts)} koncept:")
                    for concept in concepts:
                        st.write(f"- **{concept.get('namn', '')}**: {concept.get('beskrivning', '')[:100]}...")
                        if concept.get('förutsätter'):
                            st.write(f"  Förutsätter: {', '.join(concept['förutsätter'])}")
                
                # Bygg graf
                stats = st.session_state.graph_builder.build_graph_for_course(course_code)
                st.success(f"Graf byggd! Skapade {stats['koncept']} nya koncept och {stats['relationer']} relationer.")
                
                # Rensa eventuell cache
                if 'courses_df' in st.session_state:
                    del st.session_state.courses_df
                    
            except Exception as e:
                st.error(f"Fel vid byggande av graf: {str(e)}")


def render_assignments(course_id: int, canvas_api):
    """Renderar kursuppgifter"""
    with st.spinner("Hämtar uppgifter..."):
        try:
            assignments = canvas_api.get_course_assignments(course_id)
            
            if not assignments:
                st.info("Inga uppgifter hittades för denna kurs")
                return
            
            # Konvertera till DataFrame
            df = pd.DataFrame(assignments)
            
            # Sortera efter deadline
            df['due_at_parsed'] = pd.to_datetime(df['due_at'], errors='coerce')
            df = df.sort_values('due_at_parsed', na_position='last')
            
            # Visa uppgifter
            for _, assignment in df.iterrows():
                with st.expander(f"{assignment['name']}", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Beskrivning
                        if assignment.get('description'):
                            st.markdown("**Beskrivning:**")
                            # Begränsa längd på beskrivning
                            desc = assignment['description']
                            if len(desc) > 500:
                                desc = desc[:500] + "..."
                            st.markdown(desc)
                        
                        # Inlämningstyper
                        if assignment.get('submission_types'):
                            st.markdown(f"**Inlämningstyp:** {', '.join(assignment['submission_types'])}")
                    
                    with col2:
                        # Deadline
                        if assignment.get('due_at'):
                            due_date = pd.to_datetime(assignment['due_at'])
                            st.metric("Deadline", due_date.strftime("%Y-%m-%d %H:%M"))
                            
                            # Beräkna dagar kvar
                            now = datetime.now(timezone.utc)
                            days_left = (due_date - now).days
                            if days_left < 0:
                                st.error(f"Försenad med {abs(days_left)} dagar")
                            elif days_left == 0:
                                st.warning("Deadline idag!")
                            else:
                                st.info(f"{days_left} dagar kvar")
                        
                        # Poäng
                        if assignment.get('points_possible'):
                            st.metric("Poäng", assignment['points_possible'])
                        
                        # Länk till Canvas
                        if assignment.get('html_url'):
                            st.markdown(f"[Öppna i Canvas]({assignment['html_url']})")
                            
        except Exception as e:
            st.error(f"Kunde inte hämta uppgifter: {str(e)}")


