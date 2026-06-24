from database import sauvegarder_analyse
# =============================================================================
# ANALYSEUR MICROBIOLOGIQUE AVEC IA (QWEN via OLLAMA)
# =============================================================================
# Ce script analyse automatiquement les rapports PDF de laboratoire
# et génère des plans d'action en cas de non-conformité.
#
# Auteur : Toi !
# Date : 24 Juin 2026
# =============================================================================

# --- IMPORTS DES BIBLIOTHÈQUES ---
import pdfplumber        # Pour lire les PDFs
import requests          # Pour communiquer avec Ollama
import json              # Pour gérer les données JSON
import os                # Pour manipuler les fichiers et dossiers
import glob              # Pour trouver les PDFs dans un dossier
from datetime import datetime  # Pour dater les résultats

# =============================================================================
# CONFIGURATION
# =============================================================================

# Adresse de l'API Ollama (locale, sur ton PC)
OLLAMA_URL = "http://localhost:11434/api/chat"

# Nom du modèle à utiliser (doit être téléchargé avec : ollama pull qwen2.5)
MODEL_NAME = "qwen2.5"

# Dossier où se trouvent les PDFs (le dossier actuel)
DOSSIER_PDFS = "./"

# Fichier où sauvegarder les résultats
FICHIER_RESULTATS = "resultats_analyses.json"

# =============================================================================
# FONCTION 1 : Appeler l'IA Qwen
# =============================================================================

def appeler_qwen(system_prompt, user_prompt):
    """
    Envoie un message à Qwen et retourne sa réponse.
    
    system_prompt : Le rôle donné à l'IA (ex: "Tu es un expert en microbiologie")
    user_prompt : La question ou la tâche à réaliser
    """
    
    # On prépare les messages pour l'IA
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # On prépare la requête pour Ollama
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,  # On veut la réponse complète, pas en streaming
        "format": "json"  # On force Qwen à répondre en JSON
    }
    
    try:
        # On envoie la requête à Ollama
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()  # Lève une erreur si le serveur refuse
        
        # On extrait le contenu de la réponse
        content = response.json()['message']['content']
        
        # On nettoie la réponse pour extraire uniquement le JSON
        # (parfois Qwen ajoute du texte avant ou après)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # On convertit le texte JSON en objet Python
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        print(f"   ⚠️ Erreur de format JSON de Qwen : {e}")
        print(f"   Réponse brute reçue : {content[:200]}...")
        return None
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Impossible de se connecter à Ollama.")
        print(f"   💡 Vérifie qu'Ollama est lancé (icône lama dans la barre des tâches)")
        return None
    except Exception as e:
        print(f"   ❌ Erreur inattendue : {e}")
        return None

# =============================================================================
# FONCTION 2 : Extraire le texte d'un PDF
# =============================================================================

def extraire_texte_pdf(chemin_pdf):
    """
    Lit un fichier PDF et retourne tout son texte sous forme de chaîne.
    """
    texte = ""
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            for page in pdf.pages:
                texte_page = page.extract_text()
                if texte_page:
                    texte += texte_page + "\n"
        return texte
    except Exception as e:
        print(f"   ❌ Impossible de lire le PDF : {e}")
        return None

# =============================================================================
# FONCTION 3 : Analyser un rapport avec Qwen
# =============================================================================

def analyser_rapport(texte_rapport):
    """
    Demande à Qwen d'extraire les données structurées du rapport.
    Retourne un dictionnaire avec toutes les infos du rapport.
    """
    
    system_prompt = """Tu es un expert en microbiologie alimentaire et en extraction de données.
Ton but est d'extraire les informations du rapport d'analyse au format JSON strict.
Ne devine rien, extrais uniquement ce qui est écrit dans le document."""

    user_prompt = f"""
Analyse ce rapport d'analyse microbiologique et retourne UNIQUEMENT un JSON avec cette structure exacte :
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

    return appeler_qwen(system_prompt, user_prompt)

# =============================================================================
# FONCTION 4 : Générer un plan d'action (si Non-Conformité)
# =============================================================================

def generer_plan_action(donnees_rapport):
    """
    Demande à Qwen de générer un plan d'action correctif
    et un plan d'analyse adapté pour le mois suivant.
    """
    
    # On identifie les microbes en défaut
    microbes_nc = []
    for analyse in donnees_rapport.get('analyses', []):
        eval_lower = analyse.get('evaluation', '').upper()
        if 'NON CONFORME' in eval_lower or 'CRITIQUE' in eval_lower or 'DÉFAUT' in eval_lower:
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

Génère un JSON avec cette structure exacte :
{{
    "niveau_risque": "FAIBLE, MOYEN, ÉLEVÉ ou CRITIQUE",
    "actions_immediates": [
        {{
            "titre": "titre court de l'action",
            "description": "description détaillée de l'action"
        }}
    ],
    "plan_mois_suivant": [
        {{
            "titre": "titre court de l'analyse",
            "description": "description détaillée"
        }}
    ],
    "investigation_amont": "liste des points à vérifier en amont (fournisseurs, process, environnement)"
}}
"""

    return appeler_qwen(system_prompt, user_prompt)

# =============================================================================
# FONCTION 5 : Afficher les résultats proprement
# =============================================================================

def afficher_resultat(nom_fichier, donnees, plan_action=None):
    """
    Affiche les résultats de l'analyse de manière lisible dans le terminal.
    """
    
    print("\n" + "="*70)
    print(f" RAPPORT : {nom_fichier}")
    print("="*70)
    
    # Infos générales
    print(f"📦 Produit  : {donnees.get('produit', 'N/A')}")
    print(f"🏪 Rayon    : {donnees.get('rayon', 'N/A')}")
    print(f" Date     : {donnees.get('date_prelevement', 'N/A')}")
    print(f"🆔 Dossier  : {donnees.get('dossier_id', 'N/A')}")
    
    # Statut global avec icône
    statut = donnees.get('statut_global', 'INCONNU')
    is_nc = 'NON CONFORME' in statut.upper()
    
    if is_nc:
        print(f"\n🚨 STATUT : {statut}")
    else:
        print(f"\n✅ STATUT : {statut}")
    
    # Commentaire du labo
    commentaire = donnees.get('commentaire_lab', '')
    if commentaire:
        print(f"\n💬 Commentaire du laboratoire :")
        print(f"   {commentaire}")
    
    # Détail des analyses
    print(f"\n🔬 RÉSULTATS DES ANALYSES :")
    print("-"*70)
    for analyse in donnees.get('analyses', []):
        parametre = analyse.get('parametre', 'N/A')
        resultat = analyse.get('resultat', 'N/A')
        limite = analyse.get('limite', 'N/A')
        evaluation = analyse.get('evaluation', 'N/A')
        
        # Icône selon l'évaluation
        eval_upper = evaluation.upper()
        if 'CRITIQUE' in eval_upper or 'DÉFAUT' in eval_upper:
            icone = "🔴"
        elif 'NON CONFORME' in eval_upper:
            icone = "🟠"
        else:
            icone = ""
        
        print(f"   {icone} {parametre}")
        print(f"      Résultat : {resultat} | Limite : {limite} | Évaluation : {evaluation}")
    
    # Si Non-Conformité, afficher le plan d'action
    if is_nc and plan_action:
        print(f"\n{'='*70}")
        print(f"🧠 PLAN D'ACTION GÉNÉRÉ PAR L'IA")
        print(f"{'='*70}")
        
        # Niveau de risque
        niveau = plan_action.get('niveau_risque', 'N/A')
        if niveau.upper() == 'CRITIQUE':
            print(f"⚠️  NIVEAU DE RISQUE : 🔴 {niveau}")
        elif niveau.upper() == 'ÉLEVÉ':
            print(f"⚠️  NIVEAU DE RISQUE : 🟠 {niveau}")
        elif niveau.upper() == 'MOYEN':
            print(f"⚠️  NIVEAU DE RISQUE : 🟡 {niveau}")
        else:
            print(f"⚠️  NIVEAU DE RISQUE : 🟢 {niveau}")
        
        # Actions immédiates
        print(f"\n🛑 ACTIONS IMMÉDIATES (Ce mois) :")
        for i, action in enumerate(plan_action.get('actions_immediates', []), 1):
            if isinstance(action, dict):
                titre = action.get('titre', action.get('action', 'Action'))
                desc = action.get('description', '')
                print(f"   {i}. {titre}")
                print(f"      → {desc}")
            else:
                print(f"   {i}. {action}")
        
        # Plan du mois suivant
        print(f"\n📅 PLAN D'ANALYSE MIS À JOUR (Mois prochain) :")
        for i, action in enumerate(plan_action.get('plan_mois_suivant', []), 1):
            if isinstance(action, dict):
                titre = action.get('titre', action.get('analyse', 'Analyse'))
                desc = action.get('description', '')
                print(f"   ➕ {i}. {titre}")
                print(f"      → {desc}")
            else:
                print(f"   ➕ {i}. {action}")
        
        # Investigation en amont
        investigation = plan_action.get('investigation_amont', '')
        if investigation:
            print(f"\n🔍 INVESTIGATION AMONT RECOMMANDÉE :")
            print(f"   {investigation}")

# =============================================================================
# FONCTION 6 : Sauvegarder les résultats en JSON
# =============================================================================

def sauvegarder_resultats(liste_resultats):
    """
    Sauvegarde tous les résultats dans un fichier JSON pour pouvoir les réutiliser.
    """
    try:
        with open(FICHIER_RESULTATS, 'w', encoding='utf-8') as f:
            json.dump(liste_resultats, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Résultats sauvegardés dans : {FICHIER_RESULTATS}")
    except Exception as e:
        print(f"\n❌ Erreur lors de la sauvegarde : {e}")

# =============================================================================
# FONCTION PRINCIPALE : Orchestre tout le processus
# =============================================================================

def main():
    """
    Fonction principale qui lance l'analyse de tous les PDFs du dossier.
    """
    
    print("🚀 " + "="*60)
    print("🚀 ANALYSEUR MICROBIOLOGIQUE AVEC IA (QWEN)")
    print("🚀 " + "="*60)
    print(f"📂 Dossier analysé : {os.path.abspath(DOSSIER_PDFS)}")
    print(f" Modèle IA utilisé : {MODEL_NAME}")
    print(f"⏰ Date de l'analyse : {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    print("="*60)
    
    # 1. Trouver tous les PDFs dans le dossier
    pdf_files = glob.glob(os.path.join(DOSSIER_PDFS, "*.pdf"))
    
    if not pdf_files:
        print("\n⚠️  Aucun fichier PDF trouvé dans le dossier !")
        print(f"   Place tes PDFs dans : {os.path.abspath(DOSSIER_PDFS)}")
        return
    
    print(f"\n📊 {len(pdf_files)} rapport(s) PDF trouvé(s)\n")
    
    # Liste pour stocker tous les résultats
    tous_les_resultats = []
    
    # Compteurs pour les statistiques
    total_nc = 0
    total_conforme = 0
    
    # 2. Traiter chaque PDF un par un
    for pdf_file in pdf_files:
        nom_fichier = os.path.basename(pdf_file)
        print(f"\n▶️  Traitement en cours : {nom_fichier}")
        print("-"*70)
        
        # Étape A : Extraire le texte du PDF
        print("   📖 Extraction du texte...")
        texte = extraire_texte_pdf(pdf_file)
        
        if not texte:
            print(f"   ❌ Impossible d'extraire le texte, on passe au suivant.")
            continue
        
        # Étape B : Analyser le rapport avec Qwen
        print("    Analyse par Qwen (extraction des données)...")
        donnees = analyser_rapport(texte)
        
        if not donnees:
            print(f"    Qwen n'a pas pu analyser ce rapport, on passe au suivant.")
            continue
        
        # Étape C : Vérifier s'il y a une Non-Conformité
        statut = donnees.get('statut_global', '')
        is_nc = 'NON CONFORME' in statut.upper()
        
        plan_action = None
        
        if is_nc:
            total_nc += 1
            print("   🚨 Non-Conformité détectée !")
            print("   🧠 Génération du plan d'action par Qwen...")
            plan_action = generer_plan_action(donnees)
            
            if not plan_action:
                print("   ⚠️  Le plan d'action n'a pas pu être généré.")
        else:
            total_conforme += 1
            print("   ✅ Rapport conforme.")
        
        # Étape D : Afficher les résultats
        afficher_resultat(nom_fichier, donnees, plan_action)
        
        # Étape E : Stocker les résultats pour la sauvegarde
        resultat_complet = {
            "fichier": nom_fichier,
            "date_analyse": datetime.now().isoformat(),
            "donnees_rapport": donnees,
            "plan_action": plan_action,
            "non_conforme": is_nc
        }
        tous_les_resultats.append(resultat_complet)
    
    # 3. Afficher le résumé final
    print("\n\n" + "="*70)
    print("📊 RÉSUMÉ DE L'ANALYSE")
    print("="*70)
    print(f"   📄 Total des rapports analysés : {len(pdf_files)}")
    print(f"   ✅ Rapports conformes         : {total_conforme}")
    print(f"   🚨 Rapports non conformes     : {total_nc}")
    print(f"   📈 Taux de non-conformité     : {(total_nc/len(pdf_files)*100):.1f}%")
    print("="*70)
    
    # 4. Sauvegarder les résultats en JSON
    sauvegarder_resultats(tous_les_resultats)
        # Sauvegarder dans la base de données
    print("\n💾 Sauvegarde dans la base de données...")
    for resultat in tous_les_resultats:
        sauvegarder_analyse(resultat, resultat.get('plan_action'))
    print("✅ Historique sauvegardé avec succès !")
    print("\n✨ Analyse terminée !")
    print("💡 Conseil : Ouvre le fichier 'resultats_analyses.json' pour voir")
    print("   toutes les données structurées (utile pour une base de données).")

# =============================================================================
# POINT D'ENTRÉE DU SCRIPT
# =============================================================================
# Cette ligne permet de lancer le script directement
if __name__ == "__main__":
    main()