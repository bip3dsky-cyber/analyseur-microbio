# =============================================================================
# APPLICATION WEB STREAMLIT - ANALYSEUR MICROBIOLOGIQUE (VERSION MODERNE)
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

# Import des modules locaux
from database import (
    init_database, sauvegarder_analyse, get_historique_analyses,
    get_plan_surveillance_actuel, get_statistiques_generales,
    get_analyses_par_fichier
)

# =============================================================================
# CSS MODERNE - GLASSMORPHISME + DARK/LIGHT MODE
# =============================================================================

def get_css_theme(is_dark=True):
    """Retourne le CSS selon le thème choisi"""
    if is_dark:
        return """
        <style>
        /* Fond animé avec gradient */
        .stApp {
            background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #1a1a2e);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Glassmorphisme pour les cartes */
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        
        /* Sidebar glassmorphisme */
        section[data-testid="stSidebar"] {
            background: rgba(15, 12, 41, 0.8);
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Titres */
        h1, h2, h3 {
            color: #ffffff !important;
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        
        /* Texte */
        p, label, div {
            color: #e0e0e0 !important;
        }
        
        /* Boutons */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        /* Metrics */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
        }
        
        [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-size: 2rem !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #a0a0a0 !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 10px !important;
            color: #ffffff !important;
        }
        
        /* Selectbox et inputs */
        .stSelectbox > div > div {
            background: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 10px !important;
            color: #ffffff !important;
        }
        
        /* Success/Error/Warning boxes */
        .stSuccess {
            background: rgba(40, 167, 69, 0.2) !important;
            border: 1px solid rgba(40, 167, 69, 0.5) !important;
            border-radius: 10px !important;
            color: #51cf66 !important;
        }
        
        .stError {
            background: rgba(220, 53, 69, 0.2) !important;
            border: 1px solid rgba(220, 53, 69, 0.5) !important;
            border-radius: 10px !important;
            color: #ff6b6b !important;
        }
        
        .stWarning {
            background: rgba(255, 193, 7, 0.2) !important;
            border: 1px solid rgba(255, 193, 7, 0.5) !important;
            border-radius: 10px !important;
            color: #ffd43b !important;
        }
        
        .stInfo {
            background: rgba(23, 162, 184, 0.2) !important;
            border: 1px solid rgba(23, 162, 184, 0.5) !important;
            border-radius: 10px !important;
            color: #4dabf7 !important;
        }
        
        /* Dataframe */
        .stDataFrame {
            background: rgba(255, 255, 255, 0.05) !important;
            border-radius: 10px !important;
        }
        
        /* Radio buttons */
        .stRadio > label {
            color: #ffffff !important;
        }
        
        /* File uploader */
        .stFileUploader {
            background: rgba(255, 255, 255, 0.05);
            border: 2px dashed rgba(255, 255, 255, 0.3);
            border-radius: 15px;
            padding: 20px;
        }
        
        /* Progress bar */
        .stProgress > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.1);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(102, 126, 234, 0.5);
            border-radius: 5px;
        }
        </style>
        """
    else:
        return """
        <style>
        /* Fond clair avec gradient doux */
        .stApp {
            background: linear-gradient(-45deg, #f5f7fa, #c3cfe2, #e0eafc, #cfdef3);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Glassmorphisme clair */
        .glass-card {
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(0, 0, 0, 0.1);
        }
        
        /* Titres */
        h1, h2, h3 {
            color: #2c3e50 !important;
        }
        
        /* Texte */
        p, label, div {
            color: #34495e !important;
        }
        
        /* Boutons */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
        }
        
        /* Metrics */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 10px;
            padding: 15px;
        }
        
        [data-testid="stMetricValue"] {
            color: #2c3e50 !important;
            font-size: 2rem !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #7f8c8d !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.7) !important;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 0, 0, 0.1) !important;
            border-radius: 10px !important;
            color: #2c3e50 !important;
        }
        
        /* Selectbox */
        .stSelectbox > div > div {
            background: rgba(255, 255, 255, 0.9) !important;
            border: 1px solid rgba(0, 0, 0, 0.2) !important;
            border-radius: 10px !important;
            color: #2c3e50 !important;
        }
        
        /* File uploader */
        .stFileUploader {
            background: rgba(255, 255, 255, 0.7);
            border: 2px dashed rgba(102, 126, 234, 0.5);
            border-radius: 15px;
            padding: 20px;
        }
        
        /* Progress bar */
        .stProgress > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.05);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(102, 126, 234, 0.5);
            border-radius: 5px;
        }
        </style>
        """

# =============================================================================
# FONCTIONS IA
# =============================================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

try:
    API_KEY = st.secrets["api"]["API_KEY"]
    MODEL_NAME = st.secrets["api"]["MODEL_NAME"]
except:
    API_KEY = ""
    MODEL_NAME = "llama-3.3-70b-versatile"

def appeler_ia(system_prompt, user_prompt):
    if not API_KEY:
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
        return None

def extraire_texte_pdf(file):
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
    system_prompt = """Tu es un expert en microbiologie alimentaire. Extrais les informations au format JSON strict."""

    user_prompt = f"""
Analyse ce rapport et retourne UNIQUEMENT un JSON :
{{
    "dossier_id": "string",
    "date_prelevement": "string",
    "site": "string",
    "rayon": "string",
    "produit": "string",
    "statut_global": "CONFORME ou NON CONFORME",
    "commentaire_lab": "string",
    "analyses": [
        {{
            "parametre": "string",
            "resultat": "string",
            "limite": "string",
            "evaluation": "string"
        }}
    ]
}}

TEXTE :
{texte_rapport}
"""
    return appeler_ia(system_prompt, user_prompt)

def generer_plan_action(donnees_rapport):
    microbes_nc = []
    for analyse in donnees_rapport.get('analyses', []):
        eval_upper = analyse.get('evaluation', '').upper()
        if 'NON CONFORME' in eval_upper or 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
            microbes_nc.append(f"{analyse.get('parametre')} ({analyse.get('evaluation')})")
    
    microbes_texte = ", ".join(microbes_nc) if microbes_nc else "Non précisé"

    system_prompt = """Tu es Responsable Qualité. Réponds UNIQUEMENT en JSON."""

    user_prompt = f"""
Non-Conformité :
- Produit : {donnees_rapport.get('produit', 'Inconnu')}
- Rayon : {donnees_rapport.get('rayon', 'Inconnu')}
- Microbes : {microbes_texte}
- Commentaire : {donnees_rapport.get('commentaire_lab', 'Non précisé')}

JSON :
{{
    "niveau_risque": "FAIBLE, MOYEN, ÉLEVÉ ou CRITIQUE",
    "actions_immediates": [
        {{"titre": "titre", "description": "description"}}
    ],
    "plan_mois_suivant": [
        {{"titre": "titre", "description": "description"}}
    ],
    "investigation_amont": "texte"
}}
"""
    return appeler_ia(system_prompt, user_prompt)

# =============================================================================
# INITIALISATION
# =============================================================================

init_database()

# Session state pour le thème
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    # Logo
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        try:
            st.image(logo_path, use_column_width=True)
        except:
            st.title(" Analyseur Microbio")
    else:
        st.title("🔬 Analyseur Microbio")
    
    st.markdown("---")
    
    # Toggle Dark/Light Mode
    st.markdown("### 🎨 Apparence")
    dark_mode = st.toggle(" Mode Sombre", value=st.session_state.dark_mode)
    st.session_state.dark_mode = dark_mode
    
    # Appliquer le CSS
    css = get_css_theme(dark_mode)
    st.markdown(css, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        " Navigation",
        ["📊 Tableau de bord", "📤 Analyser des PDFs", "📁 Historique par Fichier", " Plan de Surveillance"]
    )
    
    st.markdown("---")
    
    if API_KEY:
        st.success("✅ IA connectée (Groq)")
    else:
        st.error("⚠️ Clé API manquante")
    
    st.info("""
    **Système IA avec Mémoire**
    - Analyse automatique PDFs
    - Détection NC
    - Plans d'action intelligents
    - Historique par fichier
    """)

# =============================================================================
# PAGE 1: TABLEAU DE BORD
# =============================================================================

if page == "📊 Tableau de bord":
    st.markdown("## 📊 Vue d'ensemble de la qualité")
    
    stats = get_statistiques_generales()
    historique = get_historique_analyses(limit=100)
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Total Analyses", stats['total_analyses'])
    with col2:
        st.metric(
            "🚨 Non-Conformités",
            stats['total_nc'],
            delta=f"{stats['taux_nc']:.1f}% du total",
            delta_color="inverse" if stats['taux_nc'] > 10 else "normal"
        )
    with col3:
        plan = get_plan_surveillance_actuel()
        nb_renforce = sum(1 for p in plan if p['statut_surveillance'] != 'NORMAL')
        st.metric("⚠️ Surveillance Renforcée", nb_renforce)
    with col4:
        if historique:
            dernier = historique[0]
            st.metric(
                "📅 Dernière Analyse",
                datetime.fromisoformat(dernier['date_analyse_systeme']).strftime("%d/%m")
            )
        else:
            st.metric("📅 Dernière Analyse", "Aucune")
    
    st.markdown("---")
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🚨 NC par Rayon")
        if stats['nc_par_rayon']:
            fig_rayon = px.bar(
                x=list(stats['nc_par_rayon'].keys()),
                y=list(stats['nc_par_rayon'].values()),
                labels={'x': 'Rayon', 'y': 'Nombre de NC'},
                color=list(stats['nc_par_rayon'].values()),
                color_continuous_scale='Reds'
            )
            fig_rayon.update_layout(
                showlegend=False, 
                height=300,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white' if dark_mode else 'black')
            )
            st.plotly_chart(fig_rayon, use_container_width=True)
        else:
            st.info("Aucune NC enregistrée")
    
    with col2:
        st.markdown("### 🦠 Microbes les plus fréquents")
        if stats['microbes_frequents']:
            fig_microbe = px.pie(
                values=list(stats['microbes_frequents'].values()),
                names=list(stats['microbes_frequents'].keys()),
                hole=0.4
            )
            fig_microbe.update_layout(
                height=300,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white' if dark_mode else 'black')
            )
            st.plotly_chart(fig_microbe, use_container_width=True)
        else:
            st.info("Aucun microbe détecté")
    
    st.markdown("---")
    st.markdown("### ⚠️ Alertes Actives")
    
    plan_actif = get_plan_surveillance_actuel()
    if plan_actif:
        for item in plan_actif:
            if item['statut_surveillance'] != 'NORMAL':
                couleur = {
                    'CRISE': '🔴',
                    'TRES RENFORCE': '',
                    'RENFORCE': '🟡'
                }.get(item['statut_surveillance'], '')
                
                with st.expander(f"{couleur} {item['rayon']} - {item['produit'] or 'Tous produits'}"):
                    st.write(f"**Statut :** {item['statut_surveillance']}")
                    st.write(f"**Fréquence :** {item['frequence_mois']} analyses/mois")
                    st.write(f"**Incidents (3 mois) :** {item['nb_incidents_3mois']}")
    else:
        st.success("✅ Aucune alerte active")

# =============================================================================
# PAGE 2: ANALYSER DES PDFs
# =============================================================================

elif page == "📤 Analyser des PDFs":
    st.markdown("## 📤 Analyse de rapports microbiologiques")
    
    uploaded_files = st.file_uploader(
        "Choisissez des fichiers PDF",
        type=['pdf'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.write(f" {len(uploaded_files)} fichier(s) sélectionné(s)")
        
        if st.button(" Lancer l'analyse", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            resultats = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Traitement : {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
                
                texte = extraire_texte_pdf(uploaded_file)
                
                if not texte:
                    st.warning(f"❌ Impossible de lire {uploaded_file.name}")
                    continue
                
                donnees = analyser_rapport(texte)
                
                if not donnees:
                    st.warning(f"️ IA n'a pas pu analyser {uploaded_file.name}")
                    continue
                
                statut = donnees.get('statut_global', '')
                is_nc = 'NON CONFORME' in statut.upper()
                
                plan_action = None
                if is_nc:
                    plan_action = generer_plan_action(donnees)
                
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
            st.success(f"{len(resultats)} rapport(s) analysé(s) !")
            
            # Afficher les résultats
            st.markdown("---")
            st.markdown("###  Résultats")
            
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
                
                if is_nc and res['plan_action']:
                    plan = res['plan_action']
                    st.markdown(f"**⚠️ Niveau de risque :** {plan.get('niveau_risque', 'N/A')}")
                    
                    st.markdown("**🛑 Actions immédiates :**")
                    for action in plan.get('actions_immediates', []):
                        if isinstance(action, dict):
                            st.write(f"- **{action.get('titre')}** : {action.get('description')}")
                    
                    st.markdown("**📅 Plan mois suivant :**")
                    for action in plan.get('plan_mois_suivant', []):
                        if isinstance(action, dict):
                            st.write(f"-  **{action.get('titre')}** : {action.get('description')}")
                
                st.markdown("---")

# =============================================================================
# PAGE 3: HISTORIQUE PAR FICHIER (NOUVEAU)
# =============================================================================

elif page == "📁 Historique par Fichier":
    st.markdown("## 📁 Historique détaillé par fichier PDF")
    
    historique = get_historique_analyses(limit=100)
    
    if not historique:
        st.info(" Aucune analyse enregistrée. Analysez d'abord des PDFs.")
    else:
        # Grouper par nom de fichier
        fichiers_uniques = list(set([h['fichier_pdf'] for h in historique]))
        
        st.markdown(f"### 📋 {len(fichiers_uniques)} fichier(s) analysé(s)")
        
        # Sélecteur de fichier
        fichier_selectionne = st.selectbox(
            "🔍 Sélectionnez un fichier pour voir les détails",
            fichiers_uniques
        )
        
        if fichier_selectionne:
            # Récupérer toutes les analyses de ce fichier
            analyses_fichier = [h for h in historique if h['fichier_pdf'] == fichier_selectionne]
            
            st.markdown("---")
            
            # En-tête du fichier
            is_nc_global = any(a['non_conforme'] for a in analyses_fichier)
            
            if is_nc_global:
                st.error(f"🚨 **Fichier :** {fichier_selectionne}")
            else:
                st.success(f"✅ **Fichier :** {fichier_selectionne}")
            
            # Stats du fichier
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total analyses", len(analyses_fichier))
            with col2:
                nb_nc = sum(1 for a in analyses_fichier if a['non_conforme'])
                st.metric("🚨 Non-conformités", nb_nc)
            with col3:
                taux = (nb_nc / len(analyses_fichier) * 100) if len(analyses_fichier) > 0 else 0
                st.metric("📈 Taux de NC", f"{taux:.1f}%")
            
            st.markdown("---")
            
            # Graphique camembert du fichier
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📊 Répartition Conformité")
                nb_conforme = len(analyses_fichier) - nb_nc
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Conformes', 'Non-conformes'],
                    values=[nb_conforme, nb_nc],
                    hole=0.3,
                    marker_colors=['#44CC44', '#FF4444']
                )])
                fig_pie.update_layout(
                    height=300,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white' if dark_mode else 'black')
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.markdown("###  Répartition par Rayon")
                rayons = {}
                for a in analyses_fichier:
                    donnees = json.loads(a['donnees_completes'])
                    rayon = donnees.get('rayon', 'Inconnu')
                    rayons[rayon] = rayons.get(rayon, 0) + 1
                
                if rayons:
                    fig_bar = px.bar(
                        x=list(rayons.keys()),
                        y=list(rayons.values()),
                        labels={'x': 'Rayon', 'y': 'Nombre'},
                        color=list(rayons.values()),
                        color_continuous_scale='Blues'
                    )
                    fig_bar.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white' if dark_mode else 'black'),
                        showlegend=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            st.markdown("---")
            
            # Détails de chaque analyse du fichier
            st.markdown("### 🔬 Détails des analyses")
            
            for i, analyse in enumerate(analyses_fichier, 1):
                donnees = json.loads(analyse['donnees_completes'])
                is_nc = analyse['non_conforme']
                
                # Carte glassmorphisme pour chaque analyse
                st.markdown(f"""
                <div class="glass-card">
                <h3>{'' if is_nc else '✅'} Analyse {i} - {donnees.get('produit', 'N/A')}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                # Infos principales
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(" Rayon", donnees.get('rayon', 'N/A'))
                with col2:
                    st.metric("📅 Date", donnees.get('date_prelevement', 'N/A'))
                with col3:
                    st.metric("🆔 Dossier", donnees.get('dossier_id', 'N/A'))
                with col4:
                    statut_text = "🔴 NON CONFORME" if is_nc else "🟢 CONFORME"
                    st.metric("📊 Statut", statut_text)
                
                # Graphique des résultats
                analyses = donnees.get('analyses', [])
                if analyses:
                    st.markdown("#### 📈 Résultats des analyses")
                    
                    # Préparer données pour graphique
                    parametres = [a.get('parametre', 'N/A') for a in analyses]
                    evaluations = [a.get('evaluation', 'N/A') for a in analyses]
                    
                    # Couleurs selon évaluation
                    colors = []
                    for eval_val in evaluations:
                        eval_upper = eval_val.upper()
                        if 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
                            colors.append('#FF4444')
                        elif 'NON CONFORME' in eval_upper:
                            colors.append('#FF8800')
                        else:
                            colors.append('#44CC44')
                    
                    fig = go.Figure(data=[go.Bar(
                        x=parametres,
                        y=[1] * len(parametres),
                        marker_color=colors,
                        text=evaluations,
                        textposition='auto',
                        hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>'
                    )])
                    
                    fig.update_layout(
                        title="Résultats par paramètre",
                        xaxis_title="Paramètres",
                        yaxis_title="Conformité",
                        showlegend=False,
                        height=300,
                        yaxis=dict(showticklabels=False),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white' if dark_mode else 'black')
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tableau détaillé
                    st.markdown("#### 📋 Tableau détaillé")
                    df_analyses = pd.DataFrame(analyses)
                    df_display = df_analyses.rename(columns={
                        'parametre': 'Paramètre',
                        'resultat': 'Résultat',
                        'limite': 'Limite',
                        'evaluation': 'Évaluation'
                    })
                    st.dataframe(df_display, use_container_width=True)
                
                # Commentaire labo
                if donnees.get('commentaire_lab'):
                    st.markdown("#### 💬 Commentaire du laboratoire")
                    if is_nc:
                        st.error(donnees.get('commentaire_lab'))
                    else:
                        st.info(donnees.get('commentaire_lab'))
                
                # Plan d'action
                if is_nc and analyse.get('plan_action'):
                    st.markdown("#### 📋 Plan d'action")
                    plan = json.loads(analyse['plan_action'])
                    
                    niveau = plan.get('niveau_risque', 'N/A')
                    if niveau.upper() == 'CRITIQUE':
                        st.error(f"⚠️ Niveau de risque: **{niveau}**")
                    elif niveau.upper() == 'ÉLEVÉ':
                        st.warning(f"⚠️ Niveau de risque: **{niveau}**")
                    else:
                        st.info(f"ℹ️ Niveau de risque: **{niveau}**")
                    
                    st.markdown("**🛑 Actions immédiates :**")
                    for action in plan.get('actions_immediates', []):
                        if isinstance(action, dict):
                            st.write(f"- **{action.get('titre')}** : {action.get('description')}")
                    
                    st.markdown("**📅 Plan mois suivant :**")
                    for action in plan.get('plan_mois_suivant', []):
                        if isinstance(action, dict):
                            st.write(f"- ➕ **{action.get('titre')}** : {action.get('description')}")
                
                st.markdown("---")

# =============================================================================
# PAGE 4: PLAN DE SURVEILLANCE
# =============================================================================

elif page == "📅 Plan de Surveillance":
    st.markdown("##  Plan de Surveillance Adaptatif")
    
    st.markdown("""
    Ce plan est **automatiquement ajusté** selon l'historique des NC.
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
                st.markdown(f"### {statut_colors[statut]} {statut}")
                
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
        st.info("📭 Aucun plan enregistré")
    
    st.markdown("---")
    st.markdown("### 💡 Recommandations")
    
    total_renforce = sum(1 for p in plan if p['statut_surveillance'] != 'NORMAL') if plan else 0
    
    if total_renforce > 0:
        st.warning(f"""
        **Action requise :** {total_renforce} produit(s) en surveillance renforcée
        
        **Recommandations :**
        - Augmenter la fréquence des prélèvements
        - Vérifier les fournisseurs
        - Renforcer les formations hygiène
        - Contrôler les températures
        """)
    else:
        st.success("""
        **Situation normale**
        
        Tous les produits en surveillance standard (1 analyse/mois).
        """)

# =============================================================================
# PIED DE PAGE
# =============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; opacity: 0.7;'>
    <p>🔬 Analyseur Microbiologique Intelligent | Powered by Groq (Llama 3) + Streamlit</p>
    <p>Design Glassmorphisme - Mode Sombre/Clair</p>
</div>
""", unsafe_allow_html=True)