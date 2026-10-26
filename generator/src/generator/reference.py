"""Données de référence stables : régions du Sénégal, noms, modèles de compteurs.

Les populations ci-dessous sont des valeurs de secours approximatives, utilisées
uniquement si le scraping de Wikipédia échoue (pas de réseau, page modifiée...).
"""

REGIONS = [
    {"code": "SN-DK", "nom": "Dakar", "chef_lieu": "Dakar", "lat": 14.6928, "lon": -17.4467, "population": 3_630_000},
    {"code": "SN-TH", "nom": "Thiès", "chef_lieu": "Thiès", "lat": 14.7910, "lon": -16.9359, "population": 2_000_000},
    {"code": "SN-DL", "nom": "Diourbel", "chef_lieu": "Diourbel", "lat": 14.6550, "lon": -16.2314, "population": 1_800_000},
    {"code": "SN-FK", "nom": "Fatick", "chef_lieu": "Fatick", "lat": 14.3390, "lon": -16.4111, "population": 860_000},
    {"code": "SN-KL", "nom": "Kaolack", "chef_lieu": "Kaolack", "lat": 14.1652, "lon": -16.0726, "population": 1_100_000},
    {"code": "SN-KF", "nom": "Kaffrine", "chef_lieu": "Kaffrine", "lat": 14.1059, "lon": -15.5508, "population": 690_000},
    {"code": "SN-KD", "nom": "Kolda", "chef_lieu": "Kolda", "lat": 12.8939, "lon": -14.9411, "population": 800_000},
    {"code": "SN-KG", "nom": "Kédougou", "chef_lieu": "Kédougou", "lat": 12.5556, "lon": -12.1744, "population": 170_000},
    {"code": "SN-LG", "nom": "Louga", "chef_lieu": "Louga", "lat": 15.6142, "lon": -16.2246, "population": 1_000_000},
    {"code": "SN-MT", "nom": "Matam", "chef_lieu": "Matam", "lat": 15.6559, "lon": -13.2554, "population": 680_000},
    {"code": "SN-SL", "nom": "Saint-Louis", "chef_lieu": "Saint-Louis", "lat": 16.0326, "lon": -16.4818, "population": 1_000_000},
    {"code": "SN-SD", "nom": "Sédhiou", "chef_lieu": "Sédhiou", "lat": 12.7081, "lon": -15.5569, "population": 520_000},
    {"code": "SN-TC", "nom": "Tambacounda", "chef_lieu": "Tambacounda", "lat": 13.7707, "lon": -13.6673, "population": 830_000},
    {"code": "SN-ZG", "nom": "Ziguinchor", "chef_lieu": "Ziguinchor", "lat": 12.5681, "lon": -16.2719, "population": 640_000},
]

URBAN_REGIONS = {"SN-DK"}

PRENOMS = [
    "Mamadou", "Moussa", "Ibrahima", "Cheikh", "Abdoulaye", "Ousmane", "Modou", "Aliou",
    "Babacar", "Pape", "Serigne", "Lamine", "Souleymane", "Malick", "Omar", "Jean", "Pierre",
    "Fatou", "Aminata", "Awa", "Mariama", "Aïssatou", "Khady", "Ndeye", "Coumba", "Astou",
    "Bineta", "Rokhaya", "Seynabou", "Adama", "Marie", "Germaine", "Yacine", "Dieynaba",
]

NOMS = [
    "Diop", "Ndiaye", "Fall", "Sow", "Ba", "Diallo", "Mbaye", "Sarr", "Faye", "Gueye",
    "Cissé", "Seck", "Diouf", "Kane", "Thiam", "Sy", "Niang", "Camara", "Badji", "Sagna",
    "Diatta", "Coly", "Mendy", "Gomis", "Sène", "Ndour", "Touré", "Wade", "Dieng", "Sylla",
]

QUARTIERS = [
    "Médina", "Escale", "Plateau", "HLM", "Grand Standing", "Cité Keur Gorgui", "Liberté",
    "Sicap", "Diamaguène", "Keur Massar", "Santhiaba", "Darou Salam", "Tableau Ferraille",
    "Boucotte", "Nord", "Sud", "Gouye Sor", "Thierno Kandji",
]

MODELES_COMPTEURS = ["Hexing HXE110", "Hexing HXE310", "Itron ACE6000", "Landis+Gyr E450", "Inhemeter DDSY"]

PUISSANCES_KVA = {
    "residentiel": [3, 6, 9],
    "professionnel": [9, 12, 18, 36],
    "agricole": [12, 18, 36],
}

CAPACITES_TRANSFORMATEURS_KVA = [50, 100, 160, 250, 400]

CANAUX_RECHARGE = {"mobile_money": 0.55, "point_de_vente": 0.25, "agence": 0.12, "application": 0.08}

MONTANTS_RECHARGE_FCFA = [1000, 2000, 3000, 5000, 10000, 20000]
