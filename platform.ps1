# =============================================================================
#  Pilotage de la plateforme sous Windows (équivalent du Makefile)
# =============================================================================
#  Usage :  .\platform.ps1 <cible>
#  Cibles : build | up | down | reset | generate | load | stream | ml | airflow | ps | smoke | help
# =============================================================================
param([Parameter(Position = 0)][string]$Target = "help")

$ALL = "--profile", "load", "--profile", "stream", "--profile", "ml", "--profile", "airflow"

switch ($Target) {
    "build"    { docker compose @ALL build }
    "up"       { docker compose up -d }
    "down"     { docker compose @ALL down }
    "reset"    { docker compose @ALL down -v }
    "generate" { python -m generator.batch --out data/raw }
    "load" {
        docker compose --profile load up loader
        docker compose --profile load up etl
        docker compose --profile load up bi-init
    }
    "stream"   { docker compose --profile stream up -d }
    "ml" {
        docker compose --profile ml up ml-train
        docker compose --profile ml up ml-score
    }
    "airflow" {
        docker compose --profile airflow up airflow-init
        docker compose --profile airflow up -d airflow-webserver airflow-scheduler
    }
    "ps"       { docker compose @ALL ps }
    "smoke"    { bash scripts/smoke_test.sh }
    default {
        Write-Host "Cibles disponibles :" -ForegroundColor Cyan
        Write-Host "  build     Construit les images applicatives"
        Write-Host "  up        Démarre le socle (bases + Kafka + ELK)"
        Write-Host "  down      Arrête tout (garde les données)"
        Write-Host "  reset     Arrête tout et SUPPRIME les données"
        Write-Host "  generate  Génère le data lake (venv local)"
        Write-Host "  load      Charge les bases + ETL + vues BI"
        Write-Host "  stream    Démarre le temps réel (producteur + consumers)"
        Write-Host "  ml        Entraîne + score le détecteur d'anomalies"
        Write-Host "  airflow   Démarre Airflow (UI sur :8080)"
        Write-Host "  ps        État des conteneurs"
        Write-Host "  smoke     Vérifie que chaque base répond"
    }
}
