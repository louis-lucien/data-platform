# =============================================================================
#  Image Airflow dérivée : Airflow + provider Docker
# =============================================================================
#  On part de l'image officielle et on ajoute UNIQUEMENT le provider dont on a
#  besoin (DockerOperator). On fige la version du provider pour des builds
#  reproductibles. On n'installe PAS pandas ni les drivers de base : Airflow
#  n'exécute pas le code métier, il lance des conteneurs qui le contiennent.
#
#  Airflow 2.10.5 : dernière 2.x stable, architecture classique (webserver +
#  scheduler), massivement documentée — le bon choix pour apprendre.
# =============================================================================
FROM apache/airflow:2.10.5

# La contrainte officielle garantit des versions compatibles entre Airflow et
# ses dépendances (Airflow publie un "constraints file" par version/python).
RUN pip install --no-cache-dir \
    "apache-airflow-providers-docker==3.14.1"
