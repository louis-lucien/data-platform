"""Chargeur du data lake vers les bases de la plateforme énergie.

Lit `data/raw/<entité>/dt=.../` (produit par le package `generator`) et remplit
chaque base avec le bon pilote. Les données sont chargées BRUTES : les défauts
de qualité volontaires des clients ne sont PAS nettoyés ici — c'est le rôle de
l'ETL (étape 9), qui alimentera le Data Warehouse. Le chargeur, lui, copie
fidèlement la source dans sa base opérationnelle.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
