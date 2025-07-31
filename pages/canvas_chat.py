"""
Canvas Chat - AI-assistent för kursmaterial
"""
import streamlit as st
from utils.session import init_session_state
import base64
import PyPDF2
import io
from typing import Dict, List, Optional


def render():
    """Renderar Canvas chat-sidan"""
    init_session_state()
    
    st.markdown("### Canvas AI-assistent")
    st.markdown("Ställ frågor om ditt kursmaterial och få svar baserat på innehållet")
    
    # Information om hur systemet fungerar
    with st.expander("Hur fungerar Canvas AI-assistenten?", expanded=False):
        st.markdown("""
        **Teknisk implementation:**
        - Standard: Använder INTE RAG - hela filinnehållet skickas direkt som kontext
        - Vid "Ta med alla kursfiler": Använder enkel filnamnssökning för >20 filer
        - Sökning: Söker relevanta filer baserat på matchning mellan din fråga och filnamn
        - AI:n instrueras att endast svara baserat på det tillhandahållna materialet
        
        **Filbegränsningar:**
        - **PDF-filer:** Max 50 sidor läses in, max 50 000 tecken per fil
        - **Textfiler:** Max 10 000 tecken per fil visas i chatten
        - **Rekommenderad filstorlek:** Under 5 MB för bästa prestanda
        - **Total kontext:** Begränsas av AI-modellens tokenantal (vanligtvis ~100k tokens)
        
        **Filtyper som stöds:**
        - ✓ PDF-filer (textextraktion)
        - ✓ Textfiler (.txt, .csv, .json, .html, .md)
        - ✗ Bilder stöds EJ (PNG, JPG, etc. kan inte analyseras)
        - ✗ Binära filer (Word, Excel, etc. kan inte läsas)
        
        **Tips för bästa resultat:**
        - Använd filer med tydlig text (inte skannade dokument)
        - Dela upp stora dokument i mindre delar
        - Ställ specifika frågor om innehållet
        - Ta bort onödiga filer från kontexten för att spara utrymme
        """)
    
    # Initiera chat-historik om den inte finns
    if 'canvas_chat_history' not in st.session_state:
        st.session_state.canvas_chat_history = []
    
    # Initiera kontext-filer
    if 'canvas_chat_context' not in st.session_state:
        st.session_state.canvas_chat_context = {}
    
    # Visa aktiva filer i kontext
    if st.session_state.canvas_chat_context:
        with st.expander("Aktiva filer i kontext", expanded=True):
            for file_id, file_info in st.session_state.canvas_chat_context.items():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{file_info['name']}** ({file_info['type']})")
                    if file_info.get('size'):
                        st.caption(f"Storlek: {file_info['size']}")
                with col2:
                    if st.button("Ta bort", key=f"remove_{file_id}"):
                        del st.session_state.canvas_chat_context[file_id]
                        st.rerun()
    
    # Lägg till fil från Canvas
    if 'chat_file' in st.session_state and st.session_state.chat_file:
        file_info = st.session_state.chat_file
        file_id = f"canvas_{hash(file_info['name'])}"
        
        if file_id not in st.session_state.canvas_chat_context:
            # Hantera olika filtyper
            mime_type = file_info.get('mime', '')
            
            if mime_type == 'application/pdf' or file_info['name'].endswith('.pdf'):
                # För PDF, försök extrahera text
                with st.spinner(f"Läser PDF {file_info['name']}..."):
                    content = extract_pdf_content(file_info.get('url'))
                    if content:
                        file_info['content'] = content
                        file_info['type'] = 'PDF'
                        st.success(f"Läste {len(content)} tecken från PDF")
                    else:
                        file_info['content'] = f"[PDF-fil: {file_info['name']}] (Kunde inte extrahera text)"
                        file_info['type'] = 'PDF (ej läsbar)'
                        st.warning("Kunde inte extrahera text från PDF")
            elif 'content' not in file_info:
                # Om innehåll inte redan finns, markera som binär fil
                file_info['type'] = 'Binär fil'
                file_info['content'] = f"[Fil: {file_info['name']}] (Binär fil, kan inte läsas som text)"
            else:
                file_info['type'] = 'Text'
            
            st.session_state.canvas_chat_context[file_id] = file_info
            st.success(f"La till {file_info['name']} i chatten")
            
        # Rensa chat_file
        st.session_state.chat_file = None
        st.rerun()
    
    # Checkboxar för kontext
    col1, col2 = st.columns([1, 1])
    
    with col1:
        include_graph = st.checkbox(
            "Inkludera hela kunskapsgrafen",
            value=False,
            help="Lägger till alla kurser och koncept från din kunskapsgraf"
        )
    
    with col2:
        include_all_files = st.checkbox(
            "Ta med alla kursfiler",
            value=False,
            help="Försöker inkludera alla filer från vald kurs (söker relevanta filer för stora mängder)",
            key="include_all_files_checkbox"
        )
        
        if include_all_files and st.session_state.selected_canvas_course:
            if 'confirm_all_files' not in st.session_state:
                st.session_state.confirm_all_files = False
            
            if not st.session_state.confirm_all_files:
                st.warning("Detta kan ta flera minuter beroende på antal filer.")
                if st.button("Bekräfta - hämta alla filer", key="confirm_fetch_all"):
                    st.session_state.confirm_all_files = True
                    st.rerun()
            else:
                # Visa process-container
                process_container = st.container()
                with process_container:
                    st.info("Processingstatus visas här när du skickar en fråga...")
    
    # Chat-gränssnitt
    st.divider()
    
    # Visa vilken modell som används
    st.caption("Använder modell: Claude Sonnet 3.7")
    
    # Container för chat-meddelanden
    chat_container = st.container()
    
    # Chat-input längst ner
    if prompt := st.chat_input("Ställ en fråga om kursmaterialet..."):
        # Lägg till användarmeddelande
        st.session_state.canvas_chat_history.append({"role": "user", "content": prompt})
        
        # Generera svar
        with st.spinner("Tänker..."):
            response = generate_response(
                prompt,
                st.session_state.canvas_chat_context,
                include_graph,
                include_all_files,
                st.session_state.canvas_chat_history[:-1],  # Exkludera det senaste meddelandet för att undvika dubbel
                "anthropic/claude-sonnet-3.7"
            )
            
            # Lägg till assistentens svar i historiken
            st.session_state.canvas_chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    
    # Visa chat-historik i containern
    with chat_container:
        for message in st.session_state.canvas_chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Återställ bekräftelse när checkbox avmarkeras
        if not include_all_files and 'confirm_all_files' in st.session_state:
            st.session_state.confirm_all_files = False
    
    # Rensa chat-knapp
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("Rensa chat", type="secondary"):
            st.session_state.canvas_chat_history = []
            st.rerun()
    
    with col2:
        if st.button("Rensa kontext", type="secondary"):
            st.session_state.canvas_chat_context = {}
            st.rerun()


def extract_pdf_content(pdf_url: str, max_pages: int = 50) -> Optional[str]:
    """Extraherar text från PDF-fil"""
    try:
        # Om vi har en URL, ladda ner PDF:en
        if pdf_url and pdf_url.startswith('http'):
            import requests
            # Hämta Canvas token för autentisering
            headers = {}
            if hasattr(st.session_state, 'canvas_api') and st.session_state.canvas_api:
                headers = st.session_state.canvas_api.headers
            
            response = requests.get(pdf_url, headers=headers)
            if response.status_code == 200:
                pdf_file = io.BytesIO(response.content)
            else:
                return None
        else:
            return None
        
        # Läs PDF
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Begränsa antal sidor
        num_pages = min(len(pdf_reader.pages), max_pages)
        
        # Extrahera text
        text = ""
        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        
        # Begränsa total längd (ca 50k tecken)
        if len(text) > 50000:
            text = text[:50000] + "\n\n[Text trunkerad pga storlek]"
        
        return text
        
    except Exception as e:
        st.warning(f"Kunde inte läsa PDF: {str(e)}")
        return None


def generate_response(prompt: str, context_files: Dict, include_graph: bool, include_all_files: bool, chat_history: List, model: str) -> str:
    """Genererar svar baserat på kontext och fråga"""
    
    # Bygg kontext från filer
    context = "KURSMATERIAL I KONTEXT:\n\n"
    included_files = []
    excluded_files = []
    total_tokens = 0
    max_context_tokens = 50000  # Säker gräns för de flesta modeller
    
    # Hantera "ta med alla filer"
    if include_all_files and hasattr(st.session_state, 'selected_canvas_course') and st.session_state.selected_canvas_course:
        try:
            # Skapa progress placeholder
            progress_placeholder = st.empty()
            progress_placeholder.info("Hämtar kursfiler...")
            
            # Hämta alla filer för kursen
            course_id = st.session_state.selected_canvas_course['id']
            all_files = st.session_state.canvas_api.get_course_files(course_id)
            
            if not all_files.empty:
                progress_placeholder.info(f"Hittade {len(all_files)} filer. Påbörjar bearbetning...")
                
                # För stora filsamlingar, använd enkel RAG-approach
                if len(all_files) > 20:
                    context += "**OBS: Använder filnamnssökning för stora filsamlingar**\n\n"
                    progress_placeholder.info("Söker efter relevanta filer baserat på din fråga...")
                    
                    # Enkel sökning baserat på filnamn
                    relevant_files = search_relevant_files(all_files, prompt)
                    
                    file_count = 0
                    for _, file in relevant_files.iterrows():
                        file_count += 1
                        progress_placeholder.info(f"Bearbetar fil {file_count}/{len(relevant_files)}: {file['name']}")
                        
                        if file.get('size_b', 0) < 5000000:  # Max 5MB per fil
                            content = fetch_file_content(file)
                            if content:
                                # Uppskatta tokens (ca 4 tecken per token)
                                file_tokens = len(content) // 4
                                if total_tokens + file_tokens < max_context_tokens:
                                    context += f"=== {file['name']} ===\n{content[:10000]}\n\n"
                                    included_files.append(file['name'])
                                    total_tokens += file_tokens
                                else:
                                    excluded_files.append(f"{file['name']} (för stor för kontext)")
                else:
                    # För mindre antal filer, inkludera alla som får plats
                    file_count = 0
                    for _, file in all_files.iterrows():
                        file_count += 1
                        progress_placeholder.info(f"Bearbetar fil {file_count}/{len(all_files)}: {file['name']}")
                        
                        if file.get('size_b', 0) < 5000000:
                            content = fetch_file_content(file)
                            if content:
                                file_tokens = len(content) // 4
                                if total_tokens + file_tokens < max_context_tokens:
                                    context += f"=== {file['name']} ===\n{content[:10000]}\n\n"
                                    included_files.append(file['name'])
                                    total_tokens += file_tokens
                                else:
                                    excluded_files.append(f"{file['name']} (context fullt)")
                
                progress_placeholder.success(f"Bearbetning klar! {len(included_files)} filer inkluderade.")
                
        except Exception as e:
            context += f"**Fel vid hämtning av kursfiler:** {str(e)}\n\n"
    
    # Lägg till manuellt valda filer
    for file_id, file_info in context_files.items():
        content = file_info.get('content', '')
        
        # Begränsa innehåll per fil
        if len(content) > 10000:
            content = content[:10000] + "\n[Innehåll trunkerat]"
        
        context += f"=== {file_info['name']} ===\n{content}\n\n"
        included_files.append(file_info['name'])
    
    # Lägg till kunskapsgraf om vald
    if include_graph:
        try:
            graph_json = st.session_state.neo4j_service.get_existing_graph_as_json()
            context += f"\n\nKUNSKAPSGRAF:\n{graph_json[:5000]}\n"
        except Exception:
            pass
    
    # Visa status om filer
    if included_files or excluded_files:
        status_msg = f"\n**Filstatus:**\n"
        if included_files:
            status_msg += f"- Inkluderade filer ({len(included_files)}): {', '.join(included_files[:10])}"
            if len(included_files) > 10:
                status_msg += f" och {len(included_files)-10} till"
        if excluded_files:
            status_msg += f"\n- Exkluderade filer ({len(excluded_files)}): {', '.join(excluded_files[:5])}"
            if len(excluded_files) > 5:
                status_msg += f" och {len(excluded_files)-5} till"
            status_msg += "\n- Tips: Byt till en modell med större context window för att inkludera fler filer"
        
        st.info(status_msg)
    
    # Bygg meddelanden för LLM
    messages = [
        {
            "role": "system",
            "content": st.session_state.get('canvas_chat_system_prompt', get_default_canvas_prompt())
        }
    ]
    
    # Lägg till kontext som första användarmeddelande
    if context_files:
        messages.append({
            "role": "user",
            "content": f"Här är kursmaterialet jag vill att du baserar dina svar på:\n\n{context}"
        })
        messages.append({
            "role": "assistant",
            "content": "Jag har läst igenom kursmaterialet och är redo att svara på dina frågor baserat på innehållet."
        })
    
    # Lägg till chat-historik (bara de senaste 10 för att spara tokens)
    for msg in chat_history[-10:]:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Lägg till nuvarande fråga
    messages.append({"role": "user", "content": prompt})
    
    # Anropa LLM
    try:
        from litellm import completion
        from config import LITELLM_API_KEY, LITELLM_BASE_URL
        
        response = completion(
            model=model,  # Använd vald modell
            messages=messages,
            temperature=0.7,
            api_key=LITELLM_API_KEY,
            base_url=LITELLM_BASE_URL
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Fel vid generering av svar: {str(e)}"


def search_relevant_files(files_df, query: str, max_files: int = 10):
    """Enkel relevansbaserad filsökning baserat på filnamn"""
    # Konvertera query till lowercase
    query_lower = query.lower()
    query_words = query_lower.split()
    
    # Poängsätt filer baserat på namn
    files_df['relevance'] = 0
    for idx, row in files_df.iterrows():
        filename = row['name'].lower()
        score = 0
        
        # Exakt matchning av ord
        for word in query_words:
            if word in filename:
                score += 2
        
        # Partiell matchning
        for word in query_words:
            if any(word in part for part in filename.split('_')):
                score += 1
        
        files_df.at[idx, 'relevance'] = score
    
    # Returnera topp-filer sorterade efter relevans
    return files_df.nlargest(max_files, 'relevance')


def fetch_file_content(file_row) -> Optional[str]:
    """Hämtar innehåll från en fil"""
    try:
        mime_type = file_row.get('mime', '')
        
        # PDF-filer
        if mime_type == 'application/pdf' or file_row['name'].endswith('.pdf'):
            return extract_pdf_content(file_row.get('url'))
        
        # Textfiler
        elif mime_type in ["text/plain", "text/csv", "application/json", "text/html", "text/markdown"]:
            if hasattr(st.session_state, 'canvas_api'):
                return st.session_state.canvas_api.download_file_content(file_row.get('url'))
        
        return None
    except Exception:
        return None


def get_default_canvas_prompt() -> str:
    """Returnerar standard systemprompt för Canvas-chatten"""
    return """Du är en hjälpsam AI-assistent som svarar på frågor om kursmaterial.

VIKTIGA REGLER:
1. Basera ALLTID dina svar på det tillhandahållna kursmaterialet
2. Om svaret inte finns i materialet, säg det tydligt
3. Citera relevanta delar från materialet när det är lämpligt
4. Var konkret och specifik i dina svar
5. Om frågan är oklar, be om förtydligande
6. Använd ALDRIG emojis i dina svar

När du svarar:
- Referera till vilket dokument informationen kommer från
- Ge exempel från materialet när det är relevant
- Förklara koncept med kursmaterialets egna ord
- Undvik att lägga till information som inte finns i materialet"""