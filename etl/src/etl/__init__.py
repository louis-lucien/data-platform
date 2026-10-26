"""ETL : des sources opérationnelles vers le Data Warehouse (schéma en étoile).

Extract  : lire PostgreSQL OLTP (clients, compteurs, régions) + Cassandra (relevés).
Transform: NETTOYER (dédoublonner les clients, valider les emails), réconcilier,
           agréger les relevés horaires en consommation journalière.
Load     : écrire les dimensions et les faits dans la base `warehouse`.

C'est ici que les défauts VOLONTAIRES des sources (annoncés depuis l'étape 2)
sont enfin corrigés — le warehouse ne contient que des données propres.
"""

__version__ = "0.1.0"
