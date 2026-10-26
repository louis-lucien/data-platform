"""Détection de fraude/anomalie sur les compteurs (apprentissage supervisé).

Fil rouge du projet : le générateur injecte des anomalies dans les relevés
(fraude_bypass, fraude_intermittente, compteur_bloque) ; les inspections terrain
(MongoDB) en étiquettent une partie. On apprend à repérer un compteur anormal à
partir de son PROFIL DE CONSOMMATION, sans attendre l'inspection.

Problème : classification BINAIRE (anomalie / normal).
Features  : agrégats par compteur calculés depuis le Data Warehouse.
Étiquettes: issues des inspections (seuls les compteurs inspectés sont étiquetés).

ATTENTION à la fuite de données : les features décrivent la CONSOMMATION, jamais
le fait d'avoir été inspecté. Les inspections ne servent QUE d'étiquettes.
"""

__version__ = "0.1.0"
