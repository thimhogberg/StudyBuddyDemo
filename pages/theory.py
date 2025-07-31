"""
Theory-sida för StudyBuddy Studio - Pedagogisk bakgrund och forskning
"""
import streamlit as st
from utils.session import init_session_state


def render():
    """Renderar theory-sidan med pedagogisk bakgrund"""
    init_session_state()
    
    st.markdown("### Pedagogisk Bakgrund")
    st.markdown("Den vetenskapliga grunden för StudyBuddy Studio")
    
    # Pitch
    st.markdown("""
    ## StudyBuddy: Revolutionerande personaliserat lärande
    
    StudyBuddy implementerar beprövade pedagogiska principer och den senaste forskningen inom 
    utbildningsteknologi för att skapa en förbättrad lärmiljö. Genom att kombinera AI-driven personalisering 
    med etablerade lärandeteorier strävar vi efter att approximera det som Benjamin Bloom kallade "2 sigma-problemet" - 
    där individuellt handledda studenter presterar två standardavvikelser bättre än traditionell undervisning.
    """)
    
    st.divider()
    
    # Huvudprinciper
    st.markdown("## Vetenskapliga grunder")
    
    # 2 Sigma Problem
    with st.expander("Blooms 2 Sigma-problem", expanded=True):
        st.markdown("""
        ### Forskningen
        Benjamin Bloom (1984) visade att studenter som får individuell handledning presterar två standardavvikelser bättre i genomsnitt (≈ 98:e percentilen) 
        jämfört med studenter i traditionella klassrum. Detta kallas "2 sigma-problemet" eftersom förbättringen motsvarar 
        två standardavvikelser.
        
        ### Målbild för StudyBuddy
        StudyBuddy strävar efter att approximera de effekter Bloom (1984) visade för 1:1-handledning. 
        Empiriskt bevis för att AI-system konsekvent når 2σ saknas dock och måste valideras lokalt genom kontrollerade studier.
        
        - **Individuell AI-handledning**: Varje student får personaliserad vägledning baserad på sin kunskapsprofil
        - **Adaptiv svårighetsgrad**: Systemet anpassar automatiskt innehållet efter studentens nivå
        - **Feedback optimerad för uppgiftstypen**: Snabb när det gynnar uppgiftstypen, fördröjd när det gynnar djupinlärning
        
        ### Referenser
        - Bloom, B. S. (1984). "The 2 Sigma Problem: The Search for Methods of Group Instruction as 
          Effective as One-to-One Tutoring". Educational Researcher, 13(6), 4-16.
        """)
    
    # Mastery Learning
    with st.expander("Mastery Learning"):
        st.markdown("""
        ### Forskningen
        Mastery Learning innebär att studenter måste behärska ett koncept innan de går vidare till nästa. 
        Forskning visar att detta leder till djupare förståelse och bättre långsiktig retention.
        
        ### Hur StudyBuddy implementerar detta
        - **Mastery Score**: Varje koncept har en mastery-poäng (0.0-1.0) som spårar förståelsenivån
        - **Förutsättningshantering**: Systemet säkerställer att grundläggande koncept behärskas först
        - **Exponentiell viktning**: Nya bedömningar vägs mot historisk prestanda för att ge en rättvis bild
        
        ### Fördelar
        - I flera studier rapporteras att upp till 80-90% når lärandemålen med mastery learning, jämfört med avsevärt lägre andelar i traditionell undervisning. Effekten varierar med kursdesign, bedömningspraxis och implementation.
        - Minskar kunskapsluckor som annars ackumuleras över tid
        - Ökar självförtroendet genom tydliga framsteg
        
        ### Metod för kunskapsspårning
        StudyBuddy använder exponentiellt viktad genomsnittsberäkning (EWMA) för att uppdatera mastery scores, vilket balanserar ny prestation mot historisk data. EWMA valdes för transparens och beräkningsenkelhet.
        
        ### Referenser
        - Guskey, T. R. (2010). "Lessons of Mastery Learning". Educational Leadership, 68(2), 52-57.
        - Anderson, L. W. (1976). "An Empirical Investigation of Individual Differences in Time to Learn".
        """)
    
    # Knowledge Graphs
    with st.expander("Kunskapsgrafer och konceptuella nätverk"):
        st.markdown("""
        ### Forskningen
        Kunskap är inte linjär utan formar komplexa nätverk av sammankopplade koncept. Visualisering 
        av dessa nätverk förbättrar förståelse och retention.
        
        ### Hur StudyBuddy implementerar detta
        - **Neo4j kunskapsgraf**: Alla koncept och deras relationer lagras i en grafbaserad databas
        - **Visuell navigering**: Studenter kan se hur koncept hänger ihop
        - **Strukturerade lärvägar**: AI analyserar grafen för att föreslå lämpliga vägar
        
        ### Fördelar
        - Förbättrad konceptuell förståelse
        - Lättare att se "the big picture"
        - Naturlig progression från enkla till komplexa koncept
        
        ### Referenser
        - Novak, J. D., & Cañas, A. J. (2008). "The Theory Underlying Concept Maps and How to Construct Them".
        - Schwendimann, B. A. (2011). "Mapping biological ideas: Concept maps as knowledge integration tools".
        """)
    
    # Socratic Method
    with st.expander("Sokratisk metod och aktivt lärande"):
        st.markdown("""
        ### Forskningen
        Den sokratiska metoden använder riktade frågor för att leda studenter till insikt snarare än 
        att bara presentera information. Detta främjar kritiskt tänkande och djup förståelse.
        
        ### Hur StudyBuddy implementerar detta
        - **Sokratisk dialog**: AI ställer frågor som bygger på studentens svar
        - **Progressiv fördjupning**: Börjar med grundläggande frågor och ökar komplexiteten
        - **Reflektion**: Studenten uppmuntras att förklara och motivera sina svar
        
        ### Fördelar
        - Utvecklar kritiskt tänkande
        - Förbättrar problemlösningsförmåga
        - Skapar djupare konceptuell förståelse
        
        ### Referenser
        - Paul, R., & Elder, L. (2019). "The Thinker's Guide to the Art of Socratic Questioning".
        - Chi, M. T. (2009). "Active-constructive-interactive: A conceptual framework for differentiating learning activities".
        """)
    
    # Immediate Feedback
    with st.expander("Feedback och formativ bedömning"):
        st.markdown("""
        ### Forskningen
        Specifik feedback är en av de mest effektiva faktorerna för lärande. 
        Hattie & Timperley (2007) rapporterar en hög genomsnittlig effektstorlek för feedback (≈0.73), men effekten varierar kraftigt beroende på feedbacknivå (uppgift, process, självreglering vs. person) och uppgiftstyp. StudyBuddy prioriterar uppgifts-, process- och självregleringsnivåerna.
        Tidpunkt och typ av feedback bör optimeras efter uppgift: omedelbar och specifik vid färdighetsinlärning; 
        fördröjd feedback kan gynna djupare bearbetning vid komplex problemlösning. StudyBuddy använder för närvarande 
        omedelbar feedback för alla uppgiftstyper.
        
        ### Hur StudyBuddy implementerar detta
        - **Realtidsutvärdering**: AI analyserar svar direkt och ger feedback
        - **Specifik vägledning**: Pekar ut styrkor och förbättringsområden
        - **Konstruktiv återkoppling**: Fokuserar på hur studenten kan förbättra sig
        
        ### Fördelar
        - Förhindrar att missförstånd befästs
        - Ökar motivation genom tydliga framsteg
        - Möjliggör snabb korrigering av förståelse
        
        ### Referenser
        - Hattie, J., & Timperley, H. (2007). "The Power of Feedback". Review of Educational Research, 77(1), 81-112.
        - Shute, V. J. (2008). "Focus on Formative Feedback". Review of Educational Research, 78(1), 153-189.
        """)
    
    # Adaptive Learning
    with st.expander("Individualisering och adaptivt lärande"):
        st.markdown("""
        ### Forskningen
        Varje student har unika förutsättningar och takt. Adaptiva system som anpassar 
        sig efter individen visar signifikant bättre resultat. Pashler et al. (2008) visar dock att evidensen 
        för att undervisa utifrån deklarerade "lärstilar" är svag.
        
        ### Hur StudyBuddy implementerar detta
        - **Tre instruktionella lägen**: Sokratisk dialog, Guidat lärande, Direkt bedömning
        - **Dynamisk svårighetsanpassning**: Innehållet anpassas efter studentens nivå
        - **Personaliserade lärvägar**: AI väljer väg baserat på faktisk prestandadata 
          och kunskapsprofil - inte självrapporterad stil
        
        ### Fördelar
        - Varje student kan lära sig i sin egen takt
        - Minskar frustration och ökar engagement
        - Maximerar lärandepotential för alla nivåer
        
        ### Referenser
        - Pashler, H., et al. (2008). "Learning Styles: Concepts and Evidence". Psychological Science, 9(3), 105-119.
        - Walkington, C. A. (2013). "Using adaptive learning technologies to personalize instruction to student interests".
        """)
    
    # Spaced Repetition
    with st.expander("Spaced repetition och långsiktig retention"):
        st.markdown("""
        ### Forskningen
        Ebbinghaus visade att minnet avtar snabbt utan repetition; exakt takt beror på material, individ och tidshorisont. 
        Spaced repetition motverkar detta genom strategiskt placerade repetitioner.
        
        ### Hur StudyBuddy implementerar detta
        - **SM-2 algoritm**: Anpassar repetitionsintervall baserat på prestation
        - **Retention tracking**: Spårar minnesbehållning för varje koncept
        - **Automatisk schemaläggning**: Nästa repetition beräknas baserat på svårighetsgrad
        - **Kursfiltrering**: Repetera koncept från specifika kurser eller alla
        
        ### Fördelar
        - Stora och konsistenta effekter på långtidsretention har visats; den exakta storleken varierar med uppgift, intervall och mätmetod
        - Effektivare användning av studietid
        - Bygger starkare neurala kopplingar
        
        ### Implementation
        StudyBuddy använder SM-2 algoritmen med personliga anpassningar för ease factor (1.3-3.0) och intervallmultiplikator.
        
        ### Referenser
        - Cepeda, N. J., et al. (2006). "Distributed practice in verbal recall tasks: A review and quantitative synthesis".
        - Karpicke, J. D., & Roediger, H. L. (2008). "The Critical Importance of Retrieval for Learning".
        """)
    
    # Smart träning
    with st.expander("Smart träning och AI-optimerade uppgifter"):
        st.markdown("""
        ### Forskningen
        Deliberate practice kräver fokuserade övningar på svaga områden med omedelbar feedback. 
        Ericsson et al. (1993) visade att expertis utvecklas genom systematisk träning på 
        utmanande uppgifter precis bortom nuvarande förmåga.
        
        ### Hur StudyBuddy implementerar detta
        - **Optimeringsalgoritm**: Väljer koncept med högst score enligt formeln:
          Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time
        - **Varierade uppgiftstyper**: MCQ, öppna frågor, problemlösning, kodning
        - **Anpassad svårighet**: Lätt/medium/svår baserat på studentens val
        - **Omedelbar AI-feedback**: Specifik återkoppling på varje svar
        
        ### Pedagogisk grund
        - **ΔP(recall)**: Prioriterar koncept som håller på att glömmas
        - **Discrimination bonus**: Extra poäng för koncept som ofta förväxlas
        - **Failure risk**: Undviker för svåra koncept med låg success rate
        - **Tidsoptimering**: Maximerar lärande per tidsenhet
        
        ### Referenser
        - Ericsson, K. A., et al. (1993). "The Role of Deliberate Practice in the Acquisition of Expert Performance".
        - Roediger, H. L., & Butler, A. C. (2011). "The critical role of retrieval practice in long-term retention".
        """)
    
    # Två studielägen
    with st.expander("Två studielägen: Smart träning vs Studera"):
        st.markdown("""
        ### Två olika angreppssätt för lärande
        
        StudyBuddy erbjuder två kompletterande studielägen som proof-of-concept för olika pedagogiska strategier:
        
        **1. Smart träning (Flik 7)**
        - **Automatiskt konceptval**: Optimeringsalgoritm väljer nästa koncept
        - **Formel**: Score = (ΔP(recall) + discrimination_bonus - failure_risk) / time
        - **Fokus**: Maximera lärande per tidsenhet genom att prioritera koncept som:
          - Håller på att glömmas (högt ΔP(recall))
          - Ofta förväxlas med andra (discrimination bonus)
          - Har rimlig svårighetsgrad (låg failure risk)
        - **Uppgiftstyper**: AI genererar varierade uppgifter (MCQ, öppna frågor, problemlösning)
        - **Användningsfall**: När du vill träna effektivt på dina svaga områden
        
        **2. Studera (Flik 8)**
        - **Strukturerad progression**: AI guidar dig genom koncept baserat på vald studieväg
        - **Tre studievägar**:
          - Från grunden (följer förutsättningskedjan)
          - Kursbaserat (fokus på specifik kurs)
          - Specifikt koncept (direkt val)
        - **Tre instruktionslägen**:
          - Sokratisk dialog (frågebaserat lärande)
          - Guidat lärande (strukturerad undervisning)
          - Direkt bedömning (snabb kunskapskontroll)
        - **Användningsfall**: När du vill följa en strukturerad lärväg med pedagogisk variation
        
        ### Varför två lägen?
        Som proof-of-concept demonstrerar dessa två lägen olika pedagogiska strategier:
        - **Smart träning**: Algoritmstyrd optimering för effektivitet
        - **Studera**: Strukturerad progression med val av instruktionsmetod
        
        I en produktionsversion skulle dessa troligen integreras till ett enhetligt system som 
        kombinerar fördelarna från båda ansatserna.
        """)
    
    st.divider()
    
    # Implementation i StudyBuddy
    st.markdown("## Hur StudyBuddy implementerar dessa principer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### Studievägar (implementerat)
        **Från grunden**: Mastery learning med förutsättningshantering
        - AI analyserar kunskapsgrafen och väljer koncept med uppfyllda förutsättningar
        - Använder faktiska mastery scores för att avgöra progression
        - Implementerat i "Studera"-fliken
        
        **Kursbaserat**: Fokuserat lärande inom kurser
        - Filtrerar koncept från valda kurser
        - Respekterar förutsättningar mellan koncept
        - Implementerat i "Studera"-fliken
        
        **Specifikt koncept**: Direkt konceptfokus
        - Välj vilket koncept som helst att studera
        - AI identifierar och föreslår att fylla kunskapsluckor om förutsättningar saknas
        - Implementerat i "Studera"-fliken
        """)
    
    with col2:
        st.markdown("""
        ### Instruktionella lägen (implementerat)
        **Sokratisk dialog**: Frågebaserat lärande
        - AI ställer 5 progressiva frågor
        - Anpassar frågor baserat på kunskapsgraf och mastery scores
        - Avslutar med bedömning och uppdaterar mastery score
        
        **Guidat lärande**: Strukturerad undervisning
        - AI förklarar koncept anpassat efter studentens nivå
        - Testar förståelse med 3 frågor
        - Personaliserad feedback baserat på kunskapsprofil
        
        **Direkt bedömning**: Snabb kunskapskontroll
        - 3 frågor av ökande svårighet
        - Frågor anpassade efter studentens mastery score
        - Beräknar och uppdaterar mastery score
        
        *Notera: Dessa lägen finns i "Studera"-fliken för manuellt val*
        """)
    
    st.divider()
    
    # Implementerade funktioner
    st.success("""
    ### Färdiga funktioner
    ✓ **Kunskapsgraf med Neo4j** - Fullt funktionell
    ✓ **AI-extraktion av koncept** - Via LLM från kursplaner
    ✓ **Tre studievägar** - Implementerade och testade (Studera-fliken)
    ✓ **Tre instruktionslägen** - Fullt funktionella med AI-anpassning (Studera-fliken)
    ✓ **Mastery tracking** - EWMA-baserad uppdatering
    ✓ **Canvas-integration** - Hämta kurser, filer och chatta med material
    ✓ **Spaced repetition** - Fullt implementerad SM-2 algoritm
    ✓ **Smart träning** - Optimeringsalgoritm med nyttofunktion för effektiv träning
    ✓ **Studera** - Strukturerad progression med tre studievägar och instruktionslägen
    ✓ **Alumn & Karriär** - Jobbannonsmatchning och kompetensanalys
    """)
    
    
    
    # Teknisk implementation
    st.markdown("## Teknisk arkitektur")
    
    st.info("""
    ### Implementerade teknologier
    - **Neo4j**: Grafbaserad databas för kunskapsstruktur
    - **LiteLLM**: API för AI-interaktion (Claude/GPT) med personaliserade prompts
    - **Streamlit**: Webbgränssnitt med Python
    - **PyVis**: Interaktiv grafvisualisering
    - **Canvas API**: Integration med Chalmers LMS
    - **EWMA**: Exponentiellt viktad genomsnittsberäkning för mastery scores
    - **SM-2**: Spaced repetition algoritm för långsiktig retention
    
    ### Dataflöde
    1. Kursinformation hämtas från JSON-fil eller Canvas API
    2. LLM extraherar koncept och relationer från kursplaner
    3. Neo4j lagrar kunskapsgrafen persistent
    4. AI bedömer studentens svar med personaliserade prompts
    5. Algoritmer väljer nästa koncept baserat på grafen och scores
    6. Smart träning använder optimeringsalgoritm för konceptval
    7. Spaced repetition schemalägger framtida repetitioner
    """)
    
    
    
    # Slutsats
    st.markdown("## Sammanfattning")
    
    st.success("""
    StudyBuddy är ett fungerande proof-of-concept som visar hur pedagogisk forskning 
    kan kombineras med modern AI-teknologi. Systemet implementerar grundläggande versioner 
    av beprövade lärandeprinciper, men kräver validering för att bevisa effektivitet.
    
    **Styrkor:**
    - Solid pedagogisk grund från etablerad forskning
    - Fungerande implementation av kärnfunktioner
    - Flexibel arkitektur som tillåter vidareutveckling
    
    **Viktigt att notera:**
    - Effekter är ej validerade genom kontrollerade studier
    - Systemet är ett proof-of-concept
    - Designat för en användare
    """)
    
    st.divider()
    
    # Referenser
    with st.expander("Fullständig referenslista"):
        st.markdown("""
        1. Anderson, L. W. (1976). An Empirical Investigation of Individual Differences in Time to Learn. Journal of Educational Psychology, 68(2), 226-233.
        
        2. Bloom, B. S. (1984). The 2 Sigma Problem: The Search for Methods of Group Instruction as Effective as One-to-One Tutoring. Educational Researcher, 13(6), 4-16.
        
        3. Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. Psychological Bulletin, 132(3), 354-380.
        
        4. Chi, M. T. (2009). Active-constructive-interactive: A conceptual framework for differentiating learning activities. Topics in Cognitive Science, 1(1), 73-105.
        
        5. Guskey, T. R. (2010). Lessons of Mastery Learning. Educational Leadership, 68(2), 52-57.
        
        6. Hattie, J., & Timperley, H. (2007). The Power of Feedback. Review of Educational Research, 77(1), 81-112.
        
        7. Karpicke, J. D., & Roediger, H. L. (2008). The Critical Importance of Retrieval for Learning. Science, 319(5865), 966-968.
        
        8. Novak, J. D., & Cañas, A. J. (2008). The Theory Underlying Concept Maps and How to Construct and Use Them. Technical Report IHMC CmapTools.
        
        9. Pashler, H., McDaniel, M., Rohrer, D., & Bjork, R. (2008). Learning Styles: Concepts and Evidence. Psychological Science in the Public Interest, 9(3), 105-119.
        
        10. Paul, R., & Elder, L. (2019). The Thinker's Guide to the Art of Socratic Questioning. Foundation for Critical Thinking.
        
        11. Schwendimann, B. A. (2011). Mapping biological ideas: Concept maps as knowledge integration tools for evolution education. Doctoral dissertation, University of California, Berkeley.
        
        12. Shute, V. J. (2008). Focus on Formative Feedback. Review of Educational Research, 78(1), 153-189.
        
        13. Walkington, C. A. (2013). Using adaptive learning technologies to personalize instruction to student interests: The impact of relevant contexts on performance and learning outcomes. Journal of Educational Psychology, 105(4), 932-945.
        """)


if __name__ == "__main__":
    render()