# =============================================================================
# GESTION DE LA BASE DE DONNÉES
# =============================================================================

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os

DB_PATH = "historique_analyses.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fichier_pdf TEXT,
            dossier_id TEXT,
            date_prelevement TEXT,
            date_analyse_systeme TEXT,
            site TEXT,
            rayon TEXT,
            produit TEXT,
            statut_global TEXT,
            non_conforme BOOLEAN,
            niveau_risque TEXT,
            donnees_completes TEXT,
            plan_action TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS microbes_detectes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyse_id INTEGER,
            parametre TEXT,
            resultat TEXT,
            limite TEXT,
            evaluation TEXT,
            FOREIGN KEY (analyse_id) REFERENCES analyses (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plan_surveillance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rayon TEXT,
            produit TEXT,
            frequence_mois INTEGER DEFAULT 1,
            dernier_incident TEXT,
            nb_incidents_3mois INTEGER DEFAULT 0,
            statut_surveillance TEXT DEFAULT 'NORMAL',
            date_mise_a_jour TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def sauvegarder_analyse(donnees: Dict, plan_action: Optional[Dict] = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO analyses (
            fichier_pdf, dossier_id, date_prelevement, date_analyse_systeme,
            site, rayon, produit, statut_global, non_conforme,
            niveau_risque, donnees_completes, plan_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        donnees.get('fichier', ''),
        donnees.get('donnees_rapport', {}).get('dossier_id', ''),
        donnees.get('donnees_rapport', {}).get('date_prelevement', ''),
        datetime.now().isoformat(),
        donnees.get('donnees_rapport', {}).get('site', ''),
        donnees.get('donnees_rapport', {}).get('rayon', ''),
        donnees.get('donnees_rapport', {}).get('produit', ''),
        donnees.get('donnees_rapport', {}).get('statut_global', ''),
        1 if donnees.get('non_conforme', False) else 0,
        plan_action.get('niveau_risque', '') if plan_action else '',
        json.dumps(donnees, ensure_ascii=False),
        json.dumps(plan_action, ensure_ascii=False) if plan_action else ''
    ))
    
    analyse_id = cursor.lastrowid
    
    for microbe in donnees.get('donnees_rapport', {}).get('analyses', []):
        cursor.execute("""
            INSERT INTO microbes_detectes (
                analyse_id, parametre, resultat, limite, evaluation
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            analyse_id,
            microbe.get('parametre', ''),
            microbe.get('resultat', ''),
            microbe.get('limite', ''),
            microbe.get('evaluation', '')
        ))
    
    if donnees.get('non_conforme', False):
        _mettre_a_jour_plan_surveillance(
            cursor,
            donnees.get('donnees_rapport', {}).get('rayon', ''),
            donnees.get('donnees_rapport', {}).get('produit', ''),
            plan_action
        )
    
    conn.commit()
    conn.close()

def _mettre_a_jour_plan_surveillance(cursor, rayon: str, produit: str, plan_action: Dict):
    cursor.execute("""
        SELECT id FROM plan_surveillance
        WHERE rayon = ? AND (produit = ? OR produit = '')
    """, (rayon, produit))
    
    existing = cursor.fetchone()
    
    trois_mois_avant = (datetime.now() - timedelta(days=90)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM analyses
        WHERE rayon = ? 
        AND (produit = ? OR produit LIKE ?)
        AND non_conforme = 1
        AND date_analyse_systeme > ?
    """, (rayon, produit, f"%{produit}%", trois_mois_avant))
    
    nb_incidents = cursor.fetchone()[0]
    
    if nb_incidents == 0:
        frequence, statut = 1, 'NORMAL'
    elif nb_incidents == 1:
        frequence, statut = 2, 'RENFORCE'
    elif nb_incidents == 2:
        frequence, statut = 4, 'TRES RENFORCE'
    else:
        frequence, statut = 8, 'CRISE'
    
    if existing:
        cursor.execute("""
            UPDATE plan_surveillance
            SET frequence_mois = ?, dernier_incident = ?, 
                nb_incidents_3mois = ?, statut_surveillance = ?,
                date_mise_a_jour = ?
            WHERE id = ?
        """, (frequence, datetime.now().isoformat(), nb_incidents, 
              statut, datetime.now().isoformat(), existing[0]))
    else:
        cursor.execute("""
            INSERT INTO plan_surveillance (
                rayon, produit, frequence_mois, dernier_incident,
                nb_incidents_3mois, statut_surveillance, date_mise_a_jour
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (rayon, produit, frequence, datetime.now().isoformat(),
              nb_incidents, statut, datetime.now().isoformat()))

def get_historique_analyses(limit: int = 50) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM analyses
        ORDER BY date_analyse_systeme DESC
        LIMIT ?
    """, (limit,))
    
    resultats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultats

def get_analyses_par_fichier(fichier_pdf: str) -> List[Dict]:
    """Récupère toutes les analyses d'un fichier spécifique"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM analyses
        WHERE fichier_pdf = ?
        ORDER BY date_analyse_systeme DESC
    """, (fichier_pdf,))
    
    resultats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultats

def get_plan_surveillance_actuel() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM plan_surveillance
        ORDER BY 
            CASE statut_surveillance
                WHEN 'CRISE' THEN 1
                WHEN 'TRES RENFORCE' THEN 2
                WHEN 'RENFORCE' THEN 3
                ELSE 4
            END,
            rayon, produit
    """)
    
    resultats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultats

def get_statistiques_generales() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM analyses")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM analyses WHERE non_conforme = 1")
    total_nc = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT rayon, COUNT(*) as nb
        FROM analyses 
        WHERE non_conforme = 1
        GROUP BY rayon
        ORDER BY nb DESC
    """)
    nc_par_rayon = {row[0]: row[1] for row in cursor.fetchall()}
    
    cursor.execute("""
        SELECT m.parametre, COUNT(*) as nb
        FROM microbes_detectes m
        JOIN analyses a ON m.analyse_id = a.id
        WHERE a.non_conforme = 1 
        AND (m.evaluation LIKE '%NON CONFORME%' OR m.evaluation LIKE '%CRITIQUE%')
        GROUP BY m.parametre
        ORDER BY nb DESC
        LIMIT 5
    """)
    microbes_frequents = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'total_analyses': total,
        'total_nc': total_nc,
        'taux_nc': (total_nc / total * 100) if total > 0 else 0,
        'nc_par_rayon': nc_par_rayon,
        'microbes_frequents': microbes_frequents
    }

if not os.path.exists(DB_PATH):
    init_database()