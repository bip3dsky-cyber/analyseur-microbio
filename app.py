# =============================================================================
# APPLICATION WEB STREAMLIT - ANALYSEUR MICROBIOLOGIQUE (VERSION CLOUD GROQ)
# =============================================================================

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import requests
import pdfplumber
import tempfile
import base64
from io import BytesIO
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import des modules locaux
from database import (
    init_database, sauvegarder_analyse, get_historique_analyses,
    get_plan_surveillance_actuel, get_statistiques_generales
)

# Configuration de la page
st.set_page_config(
    page_title="Analyseur Microbiologique IA",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# FONCTION POUR GÉNÉRER UN PDF AVEC GRAPHIQUES
# =============================================================================

class PDFReport(FPDF):
    def header(self):
        # Logo si existe
        logo_path = 'assets/logo.png'
        if os.path.exists(logo_path):
            try:
                self.image(logo_path, 10, 8, 33)
            except:
                pass
        # Titre
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'Rapport Qualite Microbiologique', 0, 0, 'C')
        self.ln(20)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        self.ln(4)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        # Encoder pour éviter les erreurs avec les caractères spéciaux
        body_encoded = body.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 5, body_encoded)
        self.ln()

def generate_pdf_report(historique, stats):
    """Génère un PDF complet avec statistiques et graphiques"""
    pdf = PDFReport()
    pdf.add_page()
    
    # Résumé exécutif
    pdf.chapter_title('RESUME EXECUTIF')
    resume_text = (
        f"Date du rapport: {datetime.now().strftime('%d/%m/%Y')}\n"
        f"Total analyses: {stats['total_analyses']}\n"
        f"Non-conformites: {stats['total_nc']}\n"
        f"Taux de NC: {stats['taux_nc']:.1f}%\n\n"
        f"Ce rapport presente l'analyse des resultats microbiologiques "
        f"et les actions correctives mises en place."
    )
    pdf.chapter_body(resume_text)
    
    # Statistiques par rayon
    if stats['nc_par_rayon']:
        pdf.chapter_title('NC PAR RAYON')
        for rayon, nb in stats['nc_par_rayon'].items():
            pdf.chapter_body(f"- {rayon}: {nb} NC")
    
    # Microbes fréquents
    if stats['microbes_frequents']:
        pdf.chapter_title('MICROBES LES PLUS FREQUENTS')
        for microbe, nb in stats['microbes_frequents'].items():
            pdf.chapter_body(f"- {microbe}: {nb} detections")
    
    # Historique détaillé
    pdf.chapter_title('HISTORIQUE DES ANALYSES')
    for analyse in historique[:20]:  # Limite aux 20 dernières
        donnees = json.loads(analyse['donnees_completes'])
        statut = "NON CONFORME" if analyse['non_conforme'] else "CONFORME"
        produit = donnees.get('produit', 'N/A')
        rayon = donnees.get('rayon', 'N/A')
        date = analyse['date_analyse_systeme'][:10]
        
        pdf.chapter_body(
            f"Date: {date}\n"
            f"Produit: {produit}\n"
            f"Rayon: {rayon}\n"
            f"Statut: {statut}\n"
        )
        pdf.ln(2)
    
    # Sauvegarder le PDF
    pdf_path = "rapport_qualite.pdf"
    pdf.output(pdf_path)
    return pdf_path

# =============================================================================
# CONFIGURATION IA (GROQ CLOUD)
# =============================================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Récupération des secrets Streamlit
try:
    API_KEY = st.secrets["api"]["API_KEY"]
    MODEL_NAME = st.secrets["api"]["MODEL_NAME"]
except:
    API_KEY = ""
    MODEL_NAME = "llama-3.3-70b-versatile"

def appeler_ia(system_prompt, user_prompt):
    """Appelle l'API Groq (Llama 3)"""
    
    if not API_KEY:
        st.error("⚠️ Clé API manquante. Configurez les secrets dans Streamlit Cloud.")
        return None
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        st.error(f"Erreur IA : {e}")
        return None

def extraire_texte_pdf(file):
    """Extrait le texte d'un fichier PDF uploadé"""
    texte = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                texte_page = page.extract_text()
                if texte_page:
                    texte += texte_page + "\n"
        return texte
    except Exception as e:
        return None

def analyser_rapport(texte_rapport):
    """Analyse un rapport avec l'IA"""
    
    system_prompt = """Tu es un expert en microbiologie alimentaire et en extraction de données.
Ton but est d'extraire les informations du rapport d'analyse au format JSON strict.
Ne devine rien, extrais uniquement ce qui est écrit dans le document."""

    user_prompt = f"""
Analyse ce rapport d'analyse microbiologique et retourne UNIQUEMENT un JSON avec cette structure :
{{
    "dossier_id": "le numéro du dossier analytique",
    "date_prelevement": "la date du prélèvement",
    "site": "le nom du site client",
    "rayon": "le rayon ou secteur",
    "produit": "le nom du produit analysé",
    "statut_global": "CONFORME ou NON CONFORME",
    "commentaire_lab": "le texte explicatif sous STATUT GLOBAL",
    "analyses": [
        {{
            "parametre": "nom du microorganisme",
            "resultat": "la valeur observée",
            "limite": "la limite réglementaire",
            "evaluation": "Satisfaisant, Non conforme, ou CRITIQUE"
        }}
    ]
}}

TEXTE DU RAPPORT :
{texte_rapport}
"""

    return appeler_ia(system_prompt, user_prompt)

def generer_plan_action(donnees_rapport):
    """Génère un plan d'action si Non-Conformité"""
    
    microbes_nc = []
    for analyse in donnees_rapport.get('analyses', []):
        eval_upper = analyse.get('evaluation', '').upper()
        if 'NON CONFORME' in eval_upper or 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
            microbes_nc.append(f"{analyse.get('parametre')} ({analyse.get('evaluation')})")
    
    microbes_texte = ", ".join(microbes_nc) if microbes_nc else "Non précisé"

    system_prompt = """Tu es le Responsable Qualité d'une grande surface alimentaire.
Tu dois proposer un plan d'actions correctives immédiates et mettre à jour 
le plan de surveillance pour le mois prochain suite à une non-conformité.
Réponds UNIQUEMENT au format JSON."""

    user_prompt = f"""
Voici une Non-Conformité (NC) détectée sur un de nos produits :
- Produit : {donnees_rapport.get('produit', 'Inconnu')}
- Rayon : {donnees_rapport.get('rayon', 'Inconnu')}
- Microbes en défaut : {microbes_texte}
- Commentaire du labo : {donnees_rapport.get('commentaire_lab', 'Non précisé')}

Génère un JSON avec cette structure :
{{
    "niveau_risque": "FAIBLE, MOYEN, ÉLEVÉ ou CRITIQUE",
    "actions_immediates": [
        {{"titre": "titre court de l'action", "description": "description détaillée"}}
    ],
    "plan_mois_suivant": [
        {{"titre": "titre court de l'analyse", "description": "description détaillée"}}
    ],
    "investigation_amont": "liste des points à vérifier en amont (fournisseurs, process, environnement)"
}}
"""

    return appeler_ia(system_prompt, user_prompt)

# Initialiser la base de données
init_database()

# =============================================================================
# BARRE LATÉRALE
# =============================================================================

with st.sidebar:
    # Logo
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        try:
            st.image(logo_path, use_column_width=True)
        except:
            st.title("🔬 Analyseur Microbiologique")
    else:
        st.title("🔬 Analyseur Microbiologique")
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Choisir une page :",
        ["📊 Tableau de bord", "📤 Analyser des PDFs", "📅 Plan de Surveillance", "📜 Historique"]
    )
    
    st.markdown("---")
    
    # Status API
    if API_KEY:
        st.success("✅ IA connectée (Groq)")
    else:
        st.error("⚠️ Clé API manquante")
    
    st.info("""
    **Système IA avec Mémoire**
    - Analyse automatique des PDFs
    - Détection des non-conformités
    - Plans d'action intelligents
    - Adaptation mensuelle automatique
    """)

# =============================================================================
# PAGE 1: TABLEAU DE BORD
# =============================================================================

if page == "📊 Tableau de bord":
    st.header("📊 Vue d'ensemble de la qualité")
    
    stats = get_statistiques_generales()
    historique = get_historique_analyses(limit=100)
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Total Analyses", value=stats['total_analyses'])
    
    with col2:
        st.metric(
            label="Non-Conformités",
            value=stats['total_nc'],
            delta=f"{stats['taux_nc']:.1f}% du total",
            delta_color="inverse" if stats['taux_nc'] > 10 else "normal"
        )
    
    with col3:
        plan = get_plan_surveillance_actuel()
        nb_renforce = sum(1 for p in plan if p['statut_surveillance'] != 'NORMAL')
        st.metric(label="Surveillance Renforcée", value=nb_renforce, delta="Produits à risque")
    
    with col4:
        if historique:
            dernier = historique[0]
            st.metric(
                label="Dernière Analyse",
                value=datetime.fromisoformat(dernier['date_analyse_systeme']).strftime("%d/%m"),
                delta="Date"
            )
        else:
            st.metric("Dernière Analyse", "Aucune")
    
    st.markdown("---")
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚨 NC par Rayon")
        if stats['nc_par_rayon']:
            fig_rayon = px.bar(
                x=list(stats['nc_par_rayon'].keys()),
                y=list(stats['nc_par_rayon'].values()),
                labels={'x': 'Rayon', 'y': 'Nombre de NC'},
                color=list(stats['nc_par_rayon'].values()),
                color_continuous_scale='Reds'
            )
            fig_rayon.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig_rayon, use_container_width=True)
        else:
            st.info("Aucune NC enregistrée")
    
    with col2:
        st.subheader("🦠 Microbes les plus fréquents")
        if stats['microbes_frequents']:
            fig_microbe = px.pie(
                values=list(stats['microbes_frequents'].values()),
                names=list(stats['microbes_frequents'].keys()),
                hole=0.4
            )
            fig_microbe.update_layout(height=300)
            st.plotly_chart(fig_microbe, use_container_width=True)
        else:
            st.info("Aucun microbe détecté")
    
    # Alertes actives
    st.markdown("---")
    st.subheader("⚠️ Alertes Actives (Surveillance Renforcée)")
    
    plan_actif = get_plan_surveillance_actuel()
    if plan_actif:
        for item in plan_actif:
            if item['statut_surveillance'] != 'NORMAL':
                couleur = {
                    'CRISE': '🔴',
                    'TRES RENFORCE': '🟠',
                    'RENFORCE': '🟡'
                }.get(item['statut_surveillance'], '')
                
                with st.expander(f"{couleur} {item['rayon']} - {item['produit'] or 'Tous produits'}"):
                    st.write(f"**Statut :** {item['statut_surveillance']}")
                    st.write(f"**Fréquence recommandée :** {item['frequence_mois']} analyses/mois")
                    st.write(f"**Incidents (3 mois) :** {item['nb_incidents_3mois']}")
    else:
        st.success("✅ Aucune alerte active - Tous les produits en surveillance normale")
    
    # Bouton export PDF
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if historique:
            if st.button("📄 Générer un rapport PDF", type="primary"):
                with st.spinner("Génération du PDF en cours..."):
                    pdf_path = generate_pdf_report(historique, stats)
                    
                    with open(pdf_path, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                    
                    st.download_button(
                        label="📥 Télécharger le PDF",
                        data=pdf_bytes,
                        file_name=f"rapport_qualite_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
                    st.success("✅ PDF généré avec succès !")
        else:
            st.info("📭 Aucune donnée à exporter. Analysez d'abord des PDFs.")

# =============================================================================
# PAGE 2: ANALYSER DES PDFs
# =============================================================================

elif page == "📤 Analyser des PDFs":
    st.header("📤 Analyse de rapports microbiologiques")
    
    uploaded_files = st.file_uploader(
        "Choisissez des fichiers PDF",
        type=['pdf'],
        accept_multiple_files=True,
        help="Sélectionnez un ou plusieurs rapports PDF d'analyse microbiologique"
    )
    
    if uploaded_files:
        st.write(f"📎 {len(uploaded_files)} fichier(s) sélectionné(s)")
        
        if st.button("🚀 Lancer l'analyse", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()
            
            resultats = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Traitement : {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
                
                # Extraire le texte
                texte = extraire_texte_pdf(uploaded_file)
                
                if not texte:
                    st.warning(f"❌ Impossible de lire {uploaded_file.name}")
                    continue
                
                # Analyser avec l'IA
                donnees = analyser_rapport(texte)
                
                if not donnees:
                    st.warning(f"⚠️ IA n'a pas pu analyser {uploaded_file.name}")
                    continue
                
                # Vérifier NC
                statut = donnees.get('statut_global', '')
                is_nc = 'NON CONFORME' in statut.upper()
                
                plan_action = None
                
                if is_nc:
                    plan_action = generer_plan_action(donnees)
                
                # Sauvegarder
                resultat_complet = {
                    "fichier": uploaded_file.name,
                    "date_analyse": datetime.now().isoformat(),
                    "donnees_rapport": donnees,
                    "plan_action": plan_action,
                    "non_conforme": is_nc
                }
                resultats.append(resultat_complet)
                sauvegarder_analyse(resultat_complet, plan_action)
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Analyse terminée !")
            st.success(f"{len(resultats)} rapport(s) analysé(s) avec succès !")
            
            # Afficher les résultats
            with results_container:
                st.markdown("---")
                st.subheader("📊 Résultats")
                
                for res in resultats:
                    donnees = res['donnees_rapport']
                    is_nc = res['non_conforme']
                    
                    icon = "🚨" if is_nc else "✅"
                    st.markdown(f"### {icon} {donnees.get('produit', 'N/A')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Rayon :** {donnees.get('rayon', 'N/A')}")
                        st.write(f"**Statut :** {donnees.get('statut_global', 'N/A')}")
                    with col2:
                        st.write(f"**Date :** {donnees.get('date_prelevement', 'N/A')}")
                        st.write(f"**Dossier :** {donnees.get('dossier_id', 'N/A')}")
                    
                    # Afficher les analyses
                    st.markdown("**🔬 Analyses :**")
                    for analyse in donnees.get('analyses', []):
                        eval_upper = analyse.get('evaluation', '').upper()
                        if 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
                            icone = "🔴"
                        elif 'NON CONFORME' in eval_upper:
                            icone = "🟠"
                        else:
                            icone = "🟢"
                        
                        st.write(f"- {icone} **{analyse.get('parametre')}** : {analyse.get('resultat')} (Limite: {analyse.get('limite')}) - *{analyse.get('evaluation')}*")
                    
                    # Afficher le plan d'action si NC
                    if is_nc and res['plan_action']:
                        plan = res['plan_action']
                        st.markdown(f"**⚠️ Niveau de risque :** {plan.get('niveau_risque', 'N/A')}")
                        
                        st.markdown("**🛑 Actions immédiates :**")
                        for action in plan.get('actions_immediates', []):
                            if isinstance(action, dict):
                                st.write(f"- **{action.get('titre')}** : {action.get('description')}")
                            else:
                                st.write(f"- {action}")
                        
                        st.markdown("**📅 Plan mois suivant :**")
                        for action in plan.get('plan_mois_suivant', []):
                            if isinstance(action, dict):
                                st.write(f"- ➕ **{action.get('titre')}** : {action.get('description')}")
                            else:
                                st.write(f"- ➕ {action}")
                        
                        investigation = plan.get('investigation_amont', '')
                        if investigation:
                            st.markdown(f"**🔍 Investigation amont :** {investigation}")
                    
                    st.markdown("---")

# =============================================================================
# PAGE 3: PLAN DE SURVEILLANCE
# =============================================================================

elif page == "📅 Plan de Surveillance":
    st.header("📅 Plan de Surveillance Adaptatif")
    
    st.markdown("""
    Ce plan est **automatiquement ajusté** en fonction de l'historique des non-conformités.
    Plus un produit a d'incidents, plus sa fréquence d'analyse augmente.
    """)
    
    plan = get_plan_surveillance_actuel()
    
    if plan:
        df_plan = pd.DataFrame(plan)
        
        statut_colors = {
            'NORMAL': '🟢',
            'RENFORCE': '🟡',
            'TRES RENFORCE': '🟠',
            'CRISE': '🔴'
        }
        
        for statut in ['CRISE', 'TRES RENFORCE', 'RENFORCE', 'NORMAL']:
            df_filtre = df_plan[df_plan['statut_surveillance'] == statut]
            if not df_filtre.empty:
                st.subheader(f"{statut_colors[statut]} {statut}")
                
                for _, row in df_filtre.iterrows():
                    with st.expander(f"🏪 **{row['rayon']}** - {row['produit'] or 'Tous produits'}"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Fréquence", f"{row['frequence_mois']}x/mois")
                        with col2:
                            st.metric("Incidents 3 mois", row['nb_incidents_3mois'])
                        with col3:
                            dernier = datetime.fromisoformat(row['dernier_incident']).strftime('%d/%m/%Y') if row['dernier_incident'] else 'Jamais'
                            st.metric("Dernier incident", dernier)
    else:
        st.info("📭 Aucun plan de surveillance enregistré. Analysez vos premiers PDFs pour commencer.")
    
    st.markdown("---")
    st.subheader("💡 Recommandations du mois")
    
    total_renforce = sum(1 for p in plan if p['statut_surveillance'] != 'NORMAL') if plan else 0
    
    if total_renforce > 0:
        st.warning(f"""
        **Action requise :** {total_renforce} produit(s) en surveillance renforcée
        
        **Recommandations :**
        - Augmenter la fréquence des prélèvements selon le tableau ci-dessus
        - Vérifier les fournisseurs des produits concernés
        - Renforcer les formations hygiène du personnel
        - Contrôler les températures de conservation
        """)
    else:
        st.success("""
        **Situation normale**
        
        Tous les produits sont en surveillance standard (1 analyse/mois).
        Continuez le suivi régulier.
        """)

# =============================================================================
# PAGE 4: HISTORIQUE (VERSION AMÉLIORÉE AVEC GRAPHIQUES)
# =============================================================================

elif page == "📜 Historique":
    st.header("📜 Historique complet des analyses")
    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        filtre_rayon = st.multiselect(
            "Filtrer par rayon",
            options=["Boucherie", "Marée", "Pâtisserie", "Traiteur", "Fruits & Légumes"]
        )
    with col2:
        filtre_statut = st.selectbox(
            "Filtrer par statut",
            options=["Toutes", "Conformes", "Non-conformes"]
        )
    
    historique = get_historique_analyses(limit=100)
    
    if historique:
        df = pd.DataFrame(historique)
        
        # Appliquer les filtres
        if filtre_rayon:
            df = df[df['rayon'].isin(filtre_rayon)]
        
        if filtre_statut == "Conformes":
            df = df[df['non_conforme'] == 0]
        elif filtre_statut == "Non-conformes":
            df = df[df['non_conforme'] == 1]
        
        # Afficher le tableau récapitulatif
        st.subheader("📋 Liste des analyses")
        st.dataframe(
            df[['date_analyse_systeme', 'rayon', 'produit', 'statut_global', 'niveau_risque']],
            use_container_width=True,
            column_config={
                "date_analyse_systeme": "Date",
                "rayon": "Rayon",
                "produit": "Produit",
                "statut_global": "Statut",
                "niveau_risque": "Niveau de risque"
            }
        )
        
        # Export CSV
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Télécharger en CSV",
            data=csv,
            file_name=f"historique_analyses_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # Détails d'une analyse
        st.markdown("---")
        st.subheader("🔍 Détails d'une analyse")
        
        liste_analyses = [f"{a['date_analyse_systeme'][:10]} - {a['produit']} ({a['statut_global']})" for a in historique]
        choix = st.selectbox("Sélectionner une analyse", liste_analyses)
        
        if choix:
            idx = liste_analyses.index(choix)
            analyse = historique[idx]
            donnees = json.loads(analyse['donnees_completes'])
            
            # Affichage visuel des détails
            is_nc = analyse['non_conforme']
            
            # En-tête avec couleur selon statut
            if is_nc:
                st.error(f"🚨 {donnees.get('produit', 'N/A')}")
            else:
                st.success(f"✅ {donnees.get('produit', 'N/A')}")
            
            # Informations principales en colonnes
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🏪 Rayon", donnees.get('rayon', 'N/A'))
            with col2:
                st.metric("📅 Date", donnees.get('date_prelevement', 'N/A'))
            with col3:
                st.metric("🆔 Dossier", donnees.get('dossier_id', 'N/A'))
            with col4:
                statut_color = "🔴 NON CONFORME" if is_nc else "🟢 CONFORME"
                st.metric("📊 Statut", statut_color)
            
            # Site client
            if donnees.get('site'):
                st.text(f"📍 Site: {donnees.get('site')}")
            
            st.markdown("---")
            
            # Graphique des résultats d'analyses
            st.subheader("🔬 Résultats des analyses microbiologiques")
            
            analyses = donnees.get('analyses', [])
            if analyses:
                # Préparer les données pour le graphique
                df_analyses = pd.DataFrame(analyses)
                
                # Créer un graphique bar
                fig = go.Figure()
                
                # Ajouter les barres avec couleurs selon l'évaluation
                colors = []
                for eval_val in df_analyses['evaluation']:
                    eval_upper = eval_val.upper() if eval_val else ''
                    if 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
                        colors.append('#FF4444')  # Rouge
                    elif 'NON CONFORME' in eval_upper:
                        colors.append('#FF8800')  # Orange
                    else:
                        colors.append('#44CC44')  # Vert
                
                fig.add_trace(go.Bar(
                    x=df_analyses['parametre'],
                    y=[1] * len(df_analyses),  # Valeur factice pour l'affichage
                    marker_color=colors,
                    text=df_analyses['evaluation'],
                    textposition='auto',
                    hovertemplate='<b>%{x}</b><br>Résultat: %{customdata[0]}<br>Limite: %{customdata[1]}<br>Évaluation: %{customdata[2]}<extra></extra>',
                    customdata=df_analyses[['resultat', 'limite', 'evaluation']].values
                ))
                
                fig.update_layout(
                    title="Résultats des analyses par paramètre",
                    xaxis_title="Paramètres analysés",
                    yaxis_title="Conformité",
                    showlegend=False,
                    height=400,
                    yaxis=dict(showticklabels=False)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tableau détaillé des résultats
                st.subheader("📊 Tableau détaillé des résultats")
                
                # Créer un DataFrame affichable
                df_display = df_analyses.copy()
                df_display = df_display.rename(columns={
                    'parametre': 'Paramètre',
                    'resultat': 'Résultat observé',
                    'limite': 'Limite réglementaire',
                    'evaluation': 'Évaluation'
                })
                
                # Appliquer un style conditionnel
                def colorer_evaluation(val):
                    if isinstance(val, str):
                        val_upper = val.upper()
                        if 'CRITIQUE' in val_upper or 'DÉFAUT' in val_upper:
                            return 'background-color: #FF4444; color: white; font-weight: bold'
                        elif 'NON CONFORME' in val_upper:
                            return 'background-color: #FF8800; color: white; font-weight: bold'
                        else:
                            return 'background-color: #44CC44; color: white; font-weight: bold'
                    return ''
                
                df_styled = df_display.style.applymap(colorer_evaluation, subset=['Évaluation'])
                st.dataframe(df_styled, use_container_width=True)
                
                # Détails texte pour chaque analyse
                st.subheader("📝 Détails par paramètre")
                for analyse_item in analyses:
                    parametre = analyse_item.get('parametre', 'N/A')
                    resultat = analyse_item.get('resultat', 'N/A')
                    limite = analyse_item.get('limite', 'N/A')
                    evaluation = analyse_item.get('evaluation', 'N/A')
                    
                    # Icône selon évaluation
                    eval_upper = evaluation.upper() if evaluation else ''
                    if 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
                        icone = "🔴"
                        couleur = "error"
                    elif 'NON CONFORME' in eval_upper:
                        icone = "🟠"
                        couleur = "warning"
                    else:
                        icone = "🟢"
                        couleur = "success"
                    
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{parametre}**")
                            st.text(f"Résultat: {resultat}")
                            st.text(f"Limite: {limite}")
                        with col2:
                            if couleur == "error":
                                st.error(f"{icone} {evaluation}")
                            elif couleur == "warning":
                                st.warning(f"{icone} {evaluation}")
                            else:
                                st.success(f"{icone} {evaluation}")
                        st.markdown("---")
            
            # Commentaire du laboratoire
            if donnees.get('commentaire_lab'):
                st.subheader("💬 Commentaire du laboratoire")
                if is_nc:
                    st.error(donnees.get('commentaire_lab'))
                else:
                    st.info(donnees.get('commentaire_lab'))
            
            # Plan d'action si NC
            if is_nc and analyse.get('plan_action'):
                st.markdown("---")
                st.subheader("📋 Plan d'action généré par l'IA")
                
                plan = json.loads(analyse['plan_action'])
                
                # Niveau de risque
                niveau_risque = plan.get('niveau_risque', 'N/A')
                if niveau_risque.upper() == 'CRITIQUE':
                    st.error(f"⚠️ Niveau de risque: **{niveau_risque}**")
                elif niveau_risque.upper() == 'ÉLEVÉ':
                    st.warning(f"⚠️ Niveau de risque: **{niveau_risque}**")
                else:
                    st.info(f"ℹ️ Niveau de risque: **{niveau_risque}**")
                
                # Actions immédiates
                st.markdown("### 🛑 Actions immédiates recommandées")
                for i, action in enumerate(plan.get('actions_immediates', []), 1):
                    if isinstance(action, dict):
                        titre = action.get('titre', 'Action')
                        description = action.get('description', '')
                        with st.expander(f"{i}. {titre}", expanded=False):
                            st.write(description)
                    else:
                        st.write(f"{i}. {action}")
                
                # Plan du mois suivant
                st.markdown("### 📅 Plan d'analyse pour le mois suivant")
                for i, action in enumerate(plan.get('plan_mois_suivant', []), 1):
                    if isinstance(action, dict):
                        titre = action.get('titre', 'Analyse')
                        description = action.get('description', '')
                        with st.expander(f"➕ {i}. {titre}", expanded=False):
                            st.write(description)
                    else:
                        st.write(f"➕ {i}. {action}")
                
                # Investigation amont
                if plan.get('investigation_amont'):
                    st.markdown("### 🔍 Investigation en amont recommandée")
                    st.info(plan.get('investigation_amont'))
            
            # Graphique comparatif si plusieurs analyses du même produit
            st.markdown("---")
            st.subheader("📈 Historique du produit")
            
            # Rechercher les analyses précédentes du même produit
            produit = donnees.get('produit', '')
            rayon = donnees.get('rayon', '')
            
            analyses_produit = [a for a in historique if json.loads(a['donnees_completes']).get('produit') == produit]
            
            if len(analyses_produit) > 1:
                st.info(f"Ce produit a été analysé {len(analyses_produit)} fois")
                
                # Compter les conformités/non-conformités
                nc_count = sum(1 for a in analyses_produit if a['non_conforme'])
                conforme_count = len(analyses_produit) - nc_count
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Analyses conformes", conforme_count)
                with col2:
                    st.metric("Non-conformités", nc_count)
                
                # Graphique camembert
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Conformes', 'Non-conformes'],
                    values=[conforme_count, nc_count],
                    hole=0.3
                )])
                fig_pie.update_layout(title=f"Taux de conformité - {produit[:50]}...")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Première analyse de ce produit")
    
    else:
        st.info("📭 Aucune analyse enregistrée. Commencez par analyser des PDFs.")

# =============================================================================
# PIED DE PAGE
# =============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>🔬 Analyseur Microbiologique Intelligent avec IA | Powered by Groq (Llama 3) + Streamlit</p>
    <p>Système adaptatif avec mémoire - Mise à jour automatique des plans de surveillance</p>
</div>
""", unsafe_allow_html=True)