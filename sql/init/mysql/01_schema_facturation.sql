-- =============================================================================
--  Base MySQL : système de facturation (recharges + factures)
-- =============================================================================
--  Pourquoi une base SÉPARÉE de PostgreSQL ? Parce que c'est la réalité du
--  métier : chez un distributeur, la facturation est souvent un logiciel tiers
--  (éditeur spécialisé) avec sa propre base, distincte du système de gestion
--  clientèle. Les relier est justement le travail de l'ETL. Ce projet reproduit
--  cette séparation pour que l'intégration multi-sources ait un vrai sens.
--
--  Deux modes de facturation, deux tables :
--    - prépayé  -> `recharges` : le client achète du crédit kWh à l'avance.
--    - postpayé -> `factures`  : on consomme, puis on facture le mois clos.
--
--  Ce script est joué au premier démarrage du conteneur `mysql`
--  (/docker-entrypoint-initdb.d), dans la base MYSQL_DATABASE.
--
--  Note encodage : utf8mb4 obligatoire pour les accents (Thiès, émise...).
-- =============================================================================

-- La base est déjà créée par l'image via MYSQL_DATABASE ; on s'y positionne.
-- Le nom réel vient du .env ; on ne le code pas en dur ici.
SET NAMES utf8mb4;

-- -----------------------------------------------------------------------------
--  Recharges des compteurs prépayés
-- -----------------------------------------------------------------------------
--  Remarque sur les clés étrangères inter-bases : MySQL ne PEUT PAS référencer
--  la table `compteurs` qui vit dans PostgreSQL. L'intégrité « ce compteur
--  existe-t-il ? » ne peut donc pas être garantie par une FK ici : c'est l'ETL
--  qui la vérifiera au moment de rapprocher les sources. On indexe quand même
--  compteur_id car toutes les requêtes filtrent dessus.

CREATE TABLE recharges (
    recharge_id    VARCHAR(16)   NOT NULL,           -- ex. RCH-0000001
    compteur_id    VARCHAR(16)   NOT NULL,           -- référence logique vers PostgreSQL
    horodatage     DATETIME      NOT NULL,           -- date/heure de l'achat
    montant_fcfa   INT           NOT NULL,           -- payé par le client (FCFA, sans décimale)
    kwh_achetes    DECIMAL(10,2) NOT NULL,           -- crédit kWh obtenu
    canal          VARCHAR(20)   NOT NULL,           -- mobile_money, agence, distributeur...
    code_recharge  CHAR(24)      NOT NULL,           -- jeton STS à 20 chiffres (format XXXX-XXXX-...)
    PRIMARY KEY (recharge_id),
    INDEX idx_recharges_compteur (compteur_id),
    INDEX idx_recharges_date     (horodatage),
    INDEX idx_recharges_canal    (canal)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- -----------------------------------------------------------------------------
--  Factures des compteurs postpayés
-- -----------------------------------------------------------------------------
--  Une facture par compteur et par mois CLOS (le mois en cours n'est pas encore
--  facturé). Montants décomposés HT / TVA / TTC comme sur une vraie facture.

CREATE TABLE factures (
    facture_id        VARCHAR(24)   NOT NULL,        -- ex. FAC-202608-00000123
    compteur_id       VARCHAR(16)   NOT NULL,        -- référence logique vers PostgreSQL
    periode_debut     DATE          NOT NULL,        -- 1er jour facturé
    periode_fin       DATE          NOT NULL,        -- dernier jour facturé
    kwh_factures      DECIMAL(10,2) NOT NULL,
    montant_ht_fcfa   DECIMAL(12,2) NOT NULL,
    tva_fcfa          DECIMAL(12,2) NOT NULL,
    montant_ttc_fcfa  DECIMAL(12,2) NOT NULL,
    date_emission     DATE          NOT NULL,
    date_echeance     DATE          NOT NULL,
    -- Cycle de vie de la facture. ENUM MySQL : la valeur est contrôlée à l'écriture.
    statut            ENUM('emise', 'payee', 'impayee') NOT NULL,
    date_paiement     DATE          NULL,            -- NULL tant que non payée
    PRIMARY KEY (facture_id),
    INDEX idx_factures_compteur (compteur_id),
    INDEX idx_factures_statut   (statut),
    INDEX idx_factures_echeance (date_echeance)      -- pour retrouver les impayés en retard
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
