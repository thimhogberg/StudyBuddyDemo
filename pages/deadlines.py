"""
Deadline och Kalender-sida för StudyBuddy
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from utils.session import init_session_state, lazy_init_canvas_api


def render():
    """Renderar deadline och kalender-sidan"""
    init_session_state()
    
    st.markdown("### Deadlines & Kalender")
    st.markdown("Håll koll på alla dina uppgifter och viktiga datum")
    
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
    
    # Lazy loading för hela sidan
    if 'deadlines_loaded' not in st.session_state:
        st.session_state.deadlines_loaded = False
    if 'deadlines_data' not in st.session_state:
        st.session_state.deadlines_data = None
    
    # Visa knapp för att ladda all data
    if not st.session_state.deadlines_loaded:
        st.info("Klicka på knappen nedan för att hämta uppgifter och deadlines från Canvas")
        if st.button("Hämta deadlines och kalender", type="primary", key="load_all_deadlines"):
            with st.spinner("Hämtar data från Canvas..."):
                try:
                    # Hämta alla uppgifter
                    assignments = canvas_api.get_upcoming_assignments()
                    
                    # Hämta kalenderhändelser för nästa 30 dagar
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=30)
                    events = canvas_api.get_calendar_events(
                        start_date.isoformat(),
                        end_date.isoformat()
                    )
                    
                    # Spara data
                    st.session_state.deadlines_data = {
                        'assignments': assignments,
                        'events': events,
                        'fetch_time': datetime.now()
                    }
                    st.session_state.deadlines_loaded = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Kunde inte hämta data: {str(e)}")
        return
    
    # Visa återställningsknapp
    col1, col2 = st.columns([3, 1])
    with col1:
        fetch_time = st.session_state.deadlines_data.get('fetch_time', datetime.now())
        st.caption(f"Data hämtad: {fetch_time.strftime('%Y-%m-%d %H:%M')}")
    with col2:
        if st.button("Uppdatera", key="refresh_deadlines"):
            st.session_state.deadlines_loaded = False
            st.rerun()
    
    # Skapa flikar för olika vyer
    tab1, tab2, tab3 = st.tabs(["Kommande uppgifter", "Kalendervy", "Översikt"])
    
    with tab1:
        render_upcoming_assignments(st.session_state.deadlines_data['assignments'])
    
    with tab2:
        render_calendar_view(
            st.session_state.deadlines_data['assignments'],
            st.session_state.deadlines_data['events'],
            canvas_api
        )
    
    with tab3:
        render_overview(st.session_state.deadlines_data['assignments'])


def render_upcoming_assignments(assignments):
    """Visar kommande uppgifter"""
    if not assignments:
        st.info("Inga kommande uppgifter hittades")
        return
    
    # Konvertera till DataFrame för enklare hantering
    df = pd.DataFrame(assignments)
    
    # Konvertera deadline till datetime
    df['due_datetime'] = pd.to_datetime(df['due_at'], utc=True)
    now = datetime.now(timezone.utc)
    df['days_until'] = ((df['due_datetime'] - now).dt.total_seconds() / 86400).astype(int)
    
    # Filtrera och sortera
    col1, col2, col3 = st.columns(3)
    
    with col1:
        time_filter = st.selectbox(
            "Tidsperiod",
            ["Alla", "Denna vecka", "Nästa vecka", "Denna månad"],
            key="time_filter"
        )
    
    with col2:
        course_filter = st.selectbox(
            "Kurs",
            ["Alla kurser"] + sorted(df['course_name'].unique().tolist()),
            key="course_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sortera efter",
            ["Deadline", "Kurs", "Poäng"],
            key="sort_by"
        )
    
    # Applicera filter
    filtered_df = df.copy()
    
    if time_filter == "Denna vecka":
        filtered_df = filtered_df[filtered_df['days_until'] <= 7]
    elif time_filter == "Nästa vecka":
        filtered_df = filtered_df[(filtered_df['days_until'] > 7) & (filtered_df['days_until'] <= 14)]
    elif time_filter == "Denna månad":
        filtered_df = filtered_df[filtered_df['days_until'] <= 30]
    
    if course_filter != "Alla kurser":
        filtered_df = filtered_df[filtered_df['course_name'] == course_filter]
    
    # Sortera
    if sort_by == "Deadline":
        filtered_df = filtered_df.sort_values('due_datetime')
    elif sort_by == "Kurs":
        filtered_df = filtered_df.sort_values(['course_name', 'due_datetime'])
    elif sort_by == "Poäng":
        filtered_df = filtered_df.sort_values('points_possible', ascending=False)
    
    # Visa uppgifter
    st.markdown(f"### Visar {len(filtered_df)} uppgifter")
    
    for _, assignment in filtered_df.iterrows():
        render_assignment_card(assignment)


def render_assignment_card(assignment):
    """Renderar ett uppgiftskort"""
    days_until = assignment['days_until']
    
    # Bestäm färg baserat på tid kvar
    if days_until < 0:
        color = "red"
        time_text = f"Försenad med {abs(days_until)} dagar"
    elif days_until == 0:
        color = "orange"
        time_text = "Deadline idag!"
    elif days_until <= 3:
        color = "orange"
        time_text = f"{days_until} dagar kvar"
    elif days_until <= 7:
        color = "yellow"
        time_text = f"{days_until} dagar kvar"
    else:
        color = "green"
        time_text = f"{days_until} dagar kvar"
    
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### {assignment['name']}")
            st.markdown(f"**Kurs:** {assignment['course_code']} - {assignment['course_name']}")
            
            # Visa beskrivning om den finns
            if assignment.get('description'):
                with st.expander("Visa beskrivning"):
                    st.markdown(assignment['description'][:500] + "..." if len(assignment['description']) > 500 else assignment['description'])
        
        with col2:
            st.markdown(f"**Deadline:**")
            st.markdown(f":{color}[{time_text}]")
            deadline = assignment['due_datetime'].strftime("%Y-%m-%d %H:%M")
            st.caption(deadline)
        
        with col3:
            if assignment.get('points_possible'):
                st.metric("Poäng", f"{assignment['points_possible']}")
            
            # Länk till Canvas
            if assignment.get('html_url'):
                st.markdown(f"[Öppna i Canvas]({assignment['html_url']})")
        
        st.divider()


def render_calendar_view(assignments, events, canvas_api):
    """Visar kalendervy"""
    st.markdown("### Kalenderöversikt")
    
    # Datum väljare
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Från datum",
            value=datetime.now(),
            key="cal_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "Till datum",
            value=datetime.now() + timedelta(days=30),
            key="cal_end_date"
        )
    
    # Kombinera till en lista av händelser
    all_events = []
    
    # Lägg till uppgifter
    for assignment in assignments:
        if assignment.get('due_at'):
            due_date = pd.to_datetime(assignment['due_at'])
            if start_date <= due_date.date() <= end_date:
                all_events.append({
                    'date': due_date,
                    'type': 'Uppgift',
                    'title': assignment['name'],
                    'course': assignment.get('course_name', 'Okänd kurs'),
                    'color': 'red'
                })
    
    # Lägg till kalenderhändelser
    for event in events:
        if event.get('start_at'):
            event_date = pd.to_datetime(event['start_at'])
            if start_date <= event_date.date() <= end_date:
                all_events.append({
                    'date': event_date,
                    'type': 'Händelse',
                    'title': event.get('title', 'Namnlös händelse'),
                    'course': event.get('context_name', 'Allmän'),
                    'color': 'blue'
                })
    
    if not all_events:
        st.info("Inga händelser under vald period")
        return
    
    # Sortera efter datum
    all_events.sort(key=lambda x: x['date'])
    
    # Gruppera per dag
    current_date = None
    
    for event in all_events:
        event_date = event['date'].date()
        
        # Ny dag
        if event_date != current_date:
            current_date = event_date
            st.markdown(f"### {event_date.strftime('%A %d %B %Y')}")
        
        # Visa händelse
        col1, col2, col3 = st.columns([1, 3, 2])
        
        with col1:
            st.markdown(f"**{event['date'].strftime('%H:%M')}**")
        
        with col2:
            color = event['color']
            st.markdown(f":{color}[{event['type']}] **{event['title']}**")
        
        with col3:
            st.caption(event['course'])


def render_overview(assignments):
    """Visar översikt över deadlines"""
    st.markdown("### Deadline-översikt")
    
    if not assignments:
        st.info("Inga uppgifter att analysera")
        return
    
    df = pd.DataFrame(assignments)
    df['due_datetime'] = pd.to_datetime(df['due_at'], utc=True)
    now = datetime.now(timezone.utc)
    df['days_until'] = ((df['due_datetime'] - now).dt.total_seconds() / 86400).astype(int)
    
    # Statistik
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total = len(df)
        st.metric("Totalt antal uppgifter", total)
    
    with col2:
        overdue = len(df[df['days_until'] < 0])
        st.metric("Försenade", overdue, delta=-overdue if overdue > 0 else None)
    
    with col3:
        this_week = len(df[(df['days_until'] >= 0) & (df['days_until'] <= 7)])
        st.metric("Denna vecka", this_week)
    
    with col4:
        total_points = df['points_possible'].sum()
        st.metric("Totala poäng", f"{total_points:.0f}")
    
    st.divider()
    
    # Uppgifter per kurs
    st.markdown("#### Uppgifter per kurs")
    course_stats = df.groupby('course_name').agg({
        'name': 'count',
        'points_possible': 'sum',
        'days_until': lambda x: (x >= 0).sum()  # Antal ej försenade
    }).rename(columns={
        'name': 'Antal uppgifter',
        'points_possible': 'Totala poäng',
        'days_until': 'Ej inlämnade'
    })
    
    st.dataframe(course_stats, use_container_width=True)
    
    # Tidslinje
    st.markdown("#### Deadline-tidslinje")
    
    # Skapa bins för tidsperioder
    bins = [-float('inf'), 0, 7, 14, 30, float('inf')]
    labels = ['Försenade', 'Denna vecka', 'Nästa vecka', 'Denna månad', 'Senare']
    df['time_category'] = pd.cut(df['days_until'], bins=bins, labels=labels)
    
    time_stats = df['time_category'].value_counts()
    
    # Visa som bar chart
    chart_data = pd.DataFrame({
        'Tidsperiod': time_stats.index,
        'Antal uppgifter': time_stats.values
    })
    
    st.bar_chart(chart_data.set_index('Tidsperiod'))




if __name__ == "__main__":
    render()