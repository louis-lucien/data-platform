"""Producteur de flux temps réel (étape 5).

Prolonge l'historique batch : les mêmes compteurs continuent d'émettre des
relevés, heure après heure, en s'appuyant sur le MÊME modèle physique que le
batch (generator.consumption). Les relevés partent sur Kafka (topic
`meter-readings`), les situations anormales sur `meter-alerts`.
"""
