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
    """Appelle l'API Groq (Llama 3) au lieu d'Ollama local"""
    
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
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)
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

st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio(
    "Choisir une page :",
    ["📊 Tableau de bord", "📤 Analyser des PDFs", "📅 Plan de Surveillance", "📜 Historique"]
)

st.sidebar.markdown("---")

if API_KEY:
    st.sidebar.success("✅ IA connectée (Groq)")
else:
    st.sidebar.error("⚠️ Clé API manquante")

st.sidebar.info("""
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
        historique = get_historique_analyses(1)
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

# =============================================================================
# PAGE 2: ANALYSER DES PDFs (VERSION COMPLÈTE)
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
# PAGE 4: HISTORIQUE
# =============================================================================

elif page == "📜 Historique":
    st.header("📜 Historique complet des analyses")
    
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
        
        if filtre_rayon:
            df = df[df['rayon'].isin(filtre_rayon)]
        
        if filtre_statut == "Conformes":
            df = df[df['non_conforme'] == 0]
        elif filtre_statut == "Non-conformes":
            df = df[df['non_conforme'] == 1]
        
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
        
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Télécharger en CSV",
            data=csv,
            file_name=f"historique_analyses_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        st.markdown("---")
        st.subheader("🔍 Détails d'une analyse")
        
        liste_analyses = [f"{a['date_analyse_systeme'][:10]} - {a['produit']} ({a['statut_global']})" for a in historique]
        choix = st.selectbox("Sélectionner une analyse", liste_analyses)
        
        if choix:
            idx = liste_analyses.index(choix)
            analyse = historique[idx]
            
            donnees = json.loads(analyse['donnees_completes'])
            st.json(donnees)
            
            if analyse['plan_action']:
                plan = json.loads(analyse['plan_action'])
                st.markdown("### 📋 Plan d'action généré")
                st.json(plan)
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