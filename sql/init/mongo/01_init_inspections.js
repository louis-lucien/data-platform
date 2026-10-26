// ============================================================================
//  MongoDB : inspections terrain + alertes brutes (documents à schéma variable)
// ============================================================================
//  POURQUOI MongoDB ici ?
//    Un rapport d'inspection n'a PAS toujours les mêmes champs :
//      - inspection conforme   -> { resultat, constat: { scelle_intact } }
//      - fraude confirmée       -> + type_anomalie, montant_regularisation, ...
//      - défaut technique       -> + piece_remplacee, constat: { afficheur } ...
//    En relationnel il faudrait des colonnes nullables partout ou des tables
//    annexes. En MongoDB chaque document porte exactement les champs qui le
//    concernent : le schéma est VARIABLE par nature. C'est son terrain de jeu.
//
//  Ce fichier .js est exécuté par mongosh au premier démarrage du conteneur
//  (monté dans /docker-entrypoint-initdb.d, où l'image Mongo joue les .js).
//  Il s'exécute dans la base d'authentification ; on bascule donc sur la nôtre.
// ============================================================================

//  Base applicative du projet (séparée de la base admin).
const db = db.getSiblingDB('terrain');

// ----------------------------------------------------------------------------
//  Collection `inspections`
// ----------------------------------------------------------------------------
//  On NE fige PAS tout le document : on impose seulement le SOCLE COMMUN
//  (les champs présents dans TOUS les rapports) et on laisse le reste libre.
//  validationLevel/Action en "moderate"/"warn" : on tolère, on n'empêche pas —
//  adapté à des données terrain réelles, parfois imparfaites.
db.createCollection('inspections', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['inspection_id', 'compteur_id', 'date_inspection', 'resultat'],
            properties: {
                inspection_id:   { bsonType: 'string' },
                compteur_id:     { bsonType: 'string' },
                date_inspection: { bsonType: 'date' },
                resultat: {
                    enum: ['conforme', 'fraude_confirmee', 'defaut_technique'],
                    description: 'issue de l inspection'
                },
                type_anomalie: {
                    // présent seulement si anomalie ; sert d'étiquette au modèle ML
                    enum: ['fraude_bypass', 'fraude_intermittente', 'compteur_bloque']
                }
                // Tous les autres champs (constat, actions, montant, technicien,
                // photos, commentaire...) restent LIBRES : pas déclarés ici.
            }
        }
    },
    validationLevel: 'moderate',
    validationAction: 'warn'
});

//  Index : on indexe ce qu'on interrogera.
//    - compteur_id : "toutes les inspections d'un compteur" + jointure logique ML.
//    - inspection_id unique : garde-fou anti-doublon à l'ingestion.
//    - type_anomalie partiel : ne couvre que les docs qui ont ce champ
//      (les inspections conformes ne l'ont pas), parfait pour construire le
//      jeu d'étiquettes du modèle de détection de fraude.
db.inspections.createIndex({ inspection_id: 1 }, { unique: true });
db.inspections.createIndex({ compteur_id: 1 });
db.inspections.createIndex(
    { type_anomalie: 1 },
    { partialFilterExpression: { type_anomalie: { $exists: true } } }
);

// ----------------------------------------------------------------------------
//  Collection `alertes` : alertes brutes produites par le streaming (étape 6)
// ----------------------------------------------------------------------------
//  Encore plus hétérogène (chaque type d'alerte a ses détails). On la crée
//  sans validateur strict, avec juste des index utiles au tri temporel.
db.createCollection('alertes');
db.alertes.createIndex({ compteur_id: 1, horodatage: -1 });
db.alertes.createIndex({ type_alerte: 1 });

print('MongoDB: base "terrain" initialisee (collections inspections, alertes).');
