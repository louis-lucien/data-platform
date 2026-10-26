"""Consumers Kafka de la plateforme énergie.

Chaque consumer lit un topic et en fait quelque chose d'utile :
  - redis_consumer : meter-readings -> Redis (dernier relevé, conso live/région) ;
  - mongo_consumer : meter-alerts   -> MongoDB (historique des alertes).

Le squelette Kafka (connexion, boucle, commit) est factorisé dans `base.py` ;
chaque consumer n'écrit que SA logique de traitement d'un message.
"""

__version__ = "0.1.0"
