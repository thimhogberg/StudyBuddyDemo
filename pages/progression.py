"""
Progression-sida för att visa och hantera mastery scores
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from utils.session import init_session_state


def render():
    """Renderar progressionssidan"""
    init_session_state()
    
    st.markdown("### Progression")
    st.markdown("Följ din kunskapsutveckling genom att uppdatera dina mastery scores")
    
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
    
    # Info-ruta om mastery scores
    with st.expander("Vad är Mastery Scores?"):
        st.info("""
        **Mastery Score** är ett mått på hur väl du behärskar ett koncept (0.0 - 1.0).
        
        - **0.0**: Ingen kunskap - Du har inte börjat studera detta koncept än
        - **0.1-0.3**: Grundläggande förståelse - Du känner till konceptet men har begränsad praktisk erfarenhet
        - **0.4-0.6**: God förståelse - Du kan tillämpa konceptet i vanliga situationer
        - **0.7-0.9**: Avancerad kunskap - Du behärskar konceptet väl och kan hantera komplexa problem
        - **1.0**: Expert - Du har fullständig förståelse och kan lära ut konceptet till andra
        
        Alla koncept startar på 0.0 när grafen skapas. Uppdatera dina scores allt eftersom du lär dig!
        """)
    
    # Hämta alla koncept med mastery scores
    with st.session_state.neo4j_service.driver.session() as session:
        result = session.run("""
            MATCH (c:Koncept)
            OPTIONAL MATCH (k:Kurs)-[:INNEHÅLLER]->(c)
            RETURN c.namn as namn, 
                   c.beskrivning as beskrivning,
                   COALESCE(c.mastery_score, 0.0) as mastery_score,
                   collect(DISTINCT k.kurskod) as kurser
            ORDER BY c.namn
        """)
        
        concepts = []
        for record in result:
            concepts.append({
                'namn': record['namn'],
                'beskrivning': record['beskrivning'],
                'mastery_score': record['mastery_score'],
                'kurser': ', '.join(record['kurser']) if record['kurser'] else 'Inga kurser'
            })
    
    if concepts:
        # Kursprogression i kronologisk ordning FÖRST
        st.markdown("#### Kursprogression i kronologisk ordning")
        with st.expander("Vad visar detta?"):
            st.markdown("""
            **Radarchart som visar alla kurser i kronologisk ordning**
            
            - Kurserna är ordnade runt cirkeln i den ordning de läses (År 1 LP1 → År 3 LP4)
            - Ju längre från centrum, desto högre genomsnittlig mastery för kursen
            - Det blåa området visar din progression genom programmet
            - Idealiskt bör tidigare kurser (början av cirkeln) ha högre mastery
            - Baserat på din kunskapsgraf
            """)
        
        # Hämta alla kurser i kronologisk ordning
        with st.session_state.neo4j_service.driver.session() as session:
            result = session.run("""
                MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
                WHERE k.år IS NOT NULL AND k.läsperiod IS NOT NULL
                WITH k.kurskod as kurs, k.namn as kursnamn, 
                     k.år as år, k.läsperiod as läsperiod,
                     AVG(COALESCE(c.mastery_score, 0.0)) as avg_mastery,
                     COUNT(c) as antal_koncept
                ORDER BY k.år, k.läsperiod
                RETURN kurs, kursnamn, år, läsperiod, avg_mastery, antal_koncept
            """)
            
            kronologisk_data = list(result)
            
            if kronologisk_data and len(kronologisk_data) >= 3:  # Behöver minst 3 kurser för radarchart
                # Visa alla kurser, men varna om det är många
                if len(kronologisk_data) > 20:
                    st.info(f"Visar alla {len(kronologisk_data)} kurser. Grafen kan bli lite trång.")
                
                fig = plt.figure(figsize=(5, 5))
                ax = fig.add_subplot(111, projection='polar')
                
                # Förbered data
                kurser_labels = []
                for i, d in enumerate(kronologisk_data):
                    # Visa kurskod med år och läsperiod
                    label = f"{d['kurs']} (År{d['år']} LP{d['läsperiod']})"
                    kurser_labels.append(label)
                
                mastery_values = [d['avg_mastery'] for d in kronologisk_data]
                
                # Antal variabler
                num_vars = len(kurser_labels)
                
                # Beräkna vinklar - jämnt fördelade runt cirkeln
                angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)
                
                # Stäng polygonen
                mastery_values_plot = mastery_values + [mastery_values[0]]
                angles_plot = angles.tolist() + [angles[0]]
                
                # Sätt rutnät och axlar INNAN vi ritar data
                ax.set_theta_offset(np.pi / 2)
                ax.set_theta_direction(-1)
                ax.set_rlabel_position(0)
                
                # Sätt labels
                ax.set_xticks(angles)
                ax.set_xticklabels(kurser_labels, size=3)
                ax.set_ylim(0, 1)
                
                # Flytta labels utanför cirkeln
                ax.tick_params(axis='x', which='major', pad=10)
                
                # Sätt r-grid (cirkulära linjer)
                ax.set_rticks([0.2, 0.4, 0.6, 0.8])
                ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8'], size=4)
                
                # Aktivera rutnät
                ax.grid(True, linestyle='-', linewidth=0.5, alpha=0.3)
                
                # Rita data
                ax.plot(angles_plot, mastery_values_plot, 'o-', linewidth=2, color='#4ECDC4', markersize=3)
                ax.fill(angles_plot, mastery_values_plot, alpha=0.25, color='#4ECDC4')
                
                # Använd kolumner för att begränsa bredden
                col1, col2, col3 = st.columns([0.5, 3, 0.5])
                with col2:
                    st.pyplot(fig)
                
                # Visa också som tabell för tydlighet
                with st.expander("Visa som tabell"):
                    if kronologisk_data:
                        # Skapa DataFrame manuellt för att undvika KeyError
                        table_data = []
                        for d in kronologisk_data:
                            table_data.append({
                                'Kurskod': d['kurs'],
                                'Kursnamn': d['kursnamn'],
                                'År': d['år'],
                                'Läsperiod': d['läsperiod'],
                                'Genomsnittlig Mastery': round(d['avg_mastery'], 2),
                                'Antal Koncept': d['antal_koncept']
                            })
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True)
            else:
                st.info("Behöver minst 3 kurser med år och läsperiod för att visa kronologisk progression")
        
        
        # Visa statistik
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        
        total_concepts = len(concepts)
        avg_mastery = sum(c['mastery_score'] for c in concepts) / total_concepts if total_concepts > 0 else 0
        mastered = sum(1 for c in concepts if c['mastery_score'] >= 0.7)
        started = sum(1 for c in concepts if c['mastery_score'] > 0)
        
        with col1:
            st.metric("Totalt antal koncept", total_concepts)
        with col2:
            st.metric("Genomsnittlig mastery", f"{avg_mastery:.2f}")
        with col3:
            st.metric("Behärskade koncept (≥0.7)", mastered)
        with col4:
            st.metric("Påbörjade koncept", started)
        
        # Visualiseringar
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Fördelning av mastery scores
            st.markdown("#### Fördelning av mastery scores")
            with st.expander("Vad visar detta?"):
                st.markdown("""
                **Histogram över alla koncepts mastery scores**
                
                - Visar hur många koncept som har varje mastery-nivå (0.0-1.0)
                - Röda staplar = koncept med 0 mastery (ej påbörjade)
                - Turkosa staplar = koncept under arbete (0.1-0.6)
                - Gröna staplar = välbehärskade koncept (0.7-1.0)
                - Varje stapel representerar ett intervall om 0.1
                - Baserat på din kunskapsgraf
                """)
            
            # Skapa histogram med bins för att gruppera närliggande värden
            mastery_scores = pd.DataFrame(concepts)['mastery_score']
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # Skapa bins för histogrammet (0.0, 0.1, 0.2, ..., 1.0)
            bins = np.arange(0, 1.1, 0.1)
            
            # Skapa histogram
            n, bins_edges, patches = ax.hist(mastery_scores, bins=bins, edgecolor='white', linewidth=1.2)
            
            # Färglägg staplarna
            for i, patch in enumerate(patches):
                bin_center = (bins_edges[i] + bins_edges[i+1]) / 2
                if bin_center < 0.05:  # 0.0 bin
                    patch.set_facecolor('#FF6B6B')
                elif bin_center >= 0.7:  # 0.7+ bins
                    patch.set_facecolor('#95E1D3')
                else:
                    patch.set_facecolor('#4ECDC4')
            
            # Lägg till värden på staplarna om de inte är 0
            for i in range(len(n)):
                if n[i] > 0:
                    # Beräkna mitten av varje bin
                    bin_center = (bins_edges[i] + bins_edges[i+1]) / 2
                    # Placera text med mer marginal
                    ax.text(bin_center, n[i] + max(n)*0.02, 
                           f'{int(n[i])}',
                           ha='center', va='bottom', fontsize=9, weight='bold')
            
            ax.set_xlabel("Mastery Score", fontsize=12)
            ax.set_ylabel("Antal koncept", fontsize=12)
            ax.set_xlim(-0.05, 1.05)
            ax.set_xticks(bins)
            ax.set_xticklabels([f'{x:.1f}' for x in bins], fontsize=10)
            
            # Justera y-axeln för att ge plats åt texten
            if len(n) > 0:
                ax.set_ylim(0, max(n) * 1.15)
            
            st.pyplot(fig)
        
        with col2:
            # Top 10 koncept med högst mastery
            st.markdown("#### Top 10 koncept")
            with st.expander("Vad visar detta?"):
                st.markdown("""
                **Horisontellt stapeldiagram över dina stärkaste koncept**
                
                - Rangordnar de 10 koncept där du har högst mastery
                - Längre stapel = högre mastery score
                - Hjälper dig se vilka områden du behärskar bäst
                - Användbart för att identifiera dina styrkor
                - Baserat på din kunskapsgraf
                """)
            
            top_concepts = sorted(concepts, key=lambda x: x['mastery_score'], reverse=True)[:10]
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            y_pos = np.arange(len(top_concepts))
            scores = [c['mastery_score'] for c in top_concepts]
            names = [c['namn'] for c in top_concepts]
            
            bars = ax.barh(y_pos, scores, color='#4ECDC4')
            
            # Lägg till värden på staplarna
            for i, (bar, score) in enumerate(zip(bars, scores)):
                ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2.,
                       f'{score:.2f}',
                       ha='left', va='center')
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names)
            ax.set_xlabel("Mastery Score")
            ax.set_xlim(0, 1)
            ax.invert_yaxis()
            
            st.pyplot(fig)
        
        # Top 5 kurser med högst mastery - fullbredd
        st.divider()
        st.markdown("#### Kurser med högst behärskning")
        with st.expander("Vad visar detta?"):
            st.markdown("""
            **Stapeldiagram över de 5 kurser du behärskar bäst**
            
            - Visar kurser rankade efter genomsnittlig mastery score
            - Högre stapel = bättre behärskning av kursens koncept
            - Visar även antal koncept per kurs
            - Användbart för CV och jobbansökningar
            - Baserat på din kunskapsgraf
            """)
        
        # Hämta top 5 kurser
        with st.session_state.neo4j_service.driver.session() as session:
                result = session.run("""
                    MATCH (k:Kurs)-[:INNEHÅLLER]->(c:Koncept)
                    WHERE c.mastery_score > 0
                    WITH k.kurskod as kurs, k.namn as kursnamn, 
                         AVG(c.mastery_score) as avg_mastery,
                         COUNT(c) as antal_koncept
                    ORDER BY avg_mastery DESC
                    LIMIT 5
                    RETURN kurs, kursnamn, avg_mastery, antal_koncept
                """)
                
                kurs_data = list(result)
                
                if kurs_data:
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    # Förbered data
                    kurser = [f"{d['kurs']}\n{d['kursnamn'][:30]}..." if len(d['kursnamn']) > 30 else f"{d['kurs']}\n{d['kursnamn']}" for d in kurs_data]
                    mastery_scores = [d['avg_mastery'] for d in kurs_data]
                    
                    # Skapa staplar
                    y_pos = np.arange(len(kurser))
                    bars = ax.barh(y_pos, mastery_scores, color='#4ECDC4')
                    
                    # Lägg till värden på staplarna
                    for i, (bar, d) in enumerate(zip(bars, kurs_data)):
                        # Mastery score
                        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2.,
                               f'{d["avg_mastery"]:.2f}',
                               ha='left', va='center', fontweight='bold')
                        # Antal koncept
                        ax.text(bar.get_width()/2, bar.get_y() + bar.get_height()/2.,
                               f'{d["antal_koncept"]} koncept',
                               ha='center', va='center', color='white', fontsize=9)
                    
                    # Anpassa graf
                    ax.set_yticks(y_pos)
                    ax.set_yticklabels(kurser, fontsize=9)
                    ax.set_xlabel('Genomsnittlig Mastery Score', fontsize=12)
                    ax.set_xlim(0, 1.05)
                    ax.invert_yaxis()
                    
                    # Lägg till rutnät
                    ax.grid(axis='x', alpha=0.3)
                    
                    # Färga bakgrund baserat på nivå
                    ax.axvspan(0, 0.3, alpha=0.1, color='red')
                    ax.axvspan(0.3, 0.7, alpha=0.1, color='yellow')
                    ax.axvspan(0.7, 1.0, alpha=0.1, color='green')
                    
                    plt.tight_layout(pad=1.5)
                    st.pyplot(fig)
                else:
                    st.info("Ingen kursdata tillgänglig ännu")
        
        # Progression över tid (om data finns)
        st.divider()
        st.markdown("#### Lärandekurva")
        with st.expander("Vad visar detta?"):
            st.markdown("""
            **Linjediagram som visar din progression över tid**
            
            - Visar hur din genomsnittliga mastery utvecklats de senaste 30 dagarna
            - Blå linje: Din genomsnittliga mastery över alla koncept
            - Blå skuggning: Visualiserar framstegen
            - Röda punkter: Milstolpar når du passerat 25%, 50%, 75%
            - Streckade linjer: Markerar milstolpsnivåerna
            
            **OBS**: Detta är MOCK-DATA! I en fullständig implementation 
            skulle detta visa verklig historisk data från din studiehistorik.
            Grafen genereras slumpmässigt baserat på din nuvarande genomsnittliga mastery.
            """)
        
        # Simulera progressionsdata (i verkligheten skulle detta komma från historisk data)
        fig, ax = plt.subplots(figsize=(12, 4))
        
        # Generera exempeldata
        days = pd.date_range(end=pd.Timestamp.now(), periods=30)
        overall_progress = np.cumsum(np.random.normal(0.02, 0.01, 30))
        overall_progress = np.clip(overall_progress + avg_mastery - 0.3, 0, 1)
        
        ax.plot(days, overall_progress, 'b-', linewidth=2, label='Genomsnittlig Mastery')
        ax.fill_between(days, overall_progress, alpha=0.3)
        
        # Markera milstolpar
        milestones = [0.25, 0.5, 0.75]
        for milestone in milestones:
            if max(overall_progress) >= milestone:
                milestone_day = days[np.argmax(overall_progress >= milestone)]
                ax.axhline(y=milestone, color='gray', linestyle='--', alpha=0.5)
                ax.plot(milestone_day, milestone, 'ro', markersize=8)
                ax.text(milestone_day, milestone + 0.02, f'{int(milestone*100)}%', 
                       ha='center', fontsize=9)
        
        ax.set_xlabel('Datum', fontsize=12)
        ax.set_ylabel('Genomsnittlig Mastery', fontsize=12)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Formatera x-axeln
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)
        
        st.pyplot(fig)
        
        # Redigerbar tabell för att uppdatera mastery scores
        st.divider()
        st.markdown("#### Uppdatera mastery scores")
        
        st.warning("""**OBS: Utvecklarläge**
        
        Denna sida tillåter manuell justering av mastery scores för test- och utvecklingsändamål. 
        I den slutliga studentversionen kommer mastery scores endast att uppdateras genom AI-bedömningar 
        baserat på faktisk prestation i studiesessionerna.""")
        
        # Sökfunktion
        search_term = st.text_input("Sök koncept", placeholder="Skriv konceptnamn...")
        
        # Filtrera koncept baserat på sökning
        filtered_concepts = concepts
        if search_term:
            filtered_concepts = [c for c in concepts if search_term.lower() in c['namn'].lower()]
        
        # Visa koncept i batches för bättre prestanda
        batch_size = 20
        total_pages = (len(filtered_concepts) - 1) // batch_size + 1
        
        if total_pages > 1:
            page = st.selectbox("Sida", range(1, total_pages + 1))
        else:
            page = 1
        
        start_idx = (page - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(filtered_concepts))
        
        # Visa koncept för aktuell sida
        st.write(f"Visar {start_idx + 1}-{end_idx} av {len(filtered_concepts)} koncept")
        
        for idx in range(start_idx, end_idx):
            concept = filtered_concepts[idx]
            
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**{concept['namn']}**")
                    if concept['beskrivning']:
                        st.caption(concept['beskrivning'][:100] + "..." if len(concept['beskrivning']) > 100 else concept['beskrivning'])
                    st.caption(f"Kurser: {concept['kurser']}")
                
                with col2:
                    current_score = concept['mastery_score']
                    color = '#FF6B6B' if current_score < 0.3 else '#95E1D3' if current_score >= 0.7 else '#4ECDC4'
                    st.markdown(f"<h3 style='color: {color}; text-align: center;'>{current_score:.2f}</h3>", unsafe_allow_html=True)
                
                with col3:
                    new_score = st.number_input(
                        "Ny score",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(current_score),
                        step=0.1,
                        key=f"score_{concept['namn']}",
                        label_visibility="collapsed"
                    )
                    
                    if new_score != current_score:
                        if st.button("Uppdatera", key=f"update_{concept['namn']}"):
                            # Uppdatera mastery score i databasen
                            with st.session_state.neo4j_service.driver.session() as update_session:
                                update_session.run("""
                                    MATCH (c:Koncept {namn: $namn})
                                    SET c.mastery_score = $score
                                """, namn=concept['namn'], score=new_score)
                            
                            st.success(f"Uppdaterade {concept['namn']} till {new_score:.2f}")
                            st.rerun()
                
                st.divider()
        
        # Exportera progression
        st.divider()
        st.markdown("#### Exportera din progression")
        
        if st.button("Ladda ner progression som CSV"):
            df = pd.DataFrame(concepts)
            csv = df.to_csv(index=False)
            st.download_button(
                label="Klicka för att ladda ner",
                data=csv,
                file_name="progression_mastery_scores.csv",
                mime="text/csv"
            )
    
    else:
        st.warning("Inga koncept hittades i grafen. Bygg först en kunskapsgraf!")


if __name__ == "__main__":
    render()