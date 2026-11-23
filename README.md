# BHHaccess

Contrôle d'accès par badge QR, on-premises. FastAPI + SQLAlchemy 2 + PostgreSQL.

## Structure

- `backend/` : API FastAPI (ci-dessous)
- `frontend/` : application React/TypeScript en deux parties :
  - **/** (PWA des agents) : **aucune connexion**. Le téléphone est appairé une fois avec un code, puis l'agent choisit son poste (groupé par unité et zone) et scanne : caméra, verdict plein écran, saisie manuelle.
  - **/admin** : administration (connexion) : tableau de bord, employés + import Excel, badges et QR, unités et zones, agents, téléphones, journal + export, rapports, utilisateurs et droits. Le menu s'adapte aux droits de chacun.

## Modèle : unités, zones, postes, agents

```
Unité ──< Zone ──< Poste de contrôle (entrée ou sortie) ──< Affectation >── Agent (sans connexion)
```
- L'accès d'un employé se règle **par unité** dans sa fiche (zones cochées). Une unité sans zone cochée s'affiche « Refusé ». La décision au scan reste prise **par zone**.
- **Téléphones** : le super user crée un téléphone et obtient un code (8 caractères, 15 min, usage unique). Le téléphone le saisit une fois (ou ouvre `/pair/CODE`) et reçoit un jeton propre, stocké haché côté serveur. Téléphone perdu : « Bloquer » (effet immédiat). Chaque changement de poste sur un téléphone est inscrit dans l'audit (« Poste choisi sur le téléphone », avant → après) et la liste des téléphones montre le poste actuel ; le bouton « Historique » de l'écran de scan montre les scans du téléphone des 12 dernières heures (lecture seule, « QR non reconnu » sans identité). Essais de code limités (8 échecs / 10 min / IP).
- **Agents** (facultatif) : renseignés par le super user et placés à un poste ; l'historique des affectations est conservé. Chaque passage du journal enregistre l'unité, la zone, le poste, le téléphone et l'**agent au poste à ce moment** (nom figé, il survit à un renommage). Filtres et export CSV par unité et par agent.

```bash
cd frontend && npm install && npm test && npm run build   # 106 tests
npm run dev                                               # http://localhost:5173, proxy /api -> localhost:8001
```

La caméra exige HTTPS (ou localhost) : en production, Nginx interne avec certificat.

## Architecture backend (MVC en couches)

```
Requête HTTP
   │
   ▼
controllers/   C  Routes minces : valident le droit, appellent UN service, renvoient un DTO
   │  (deps.py = racine de composition : injection des dépendances)
   ▼
services/         Cas d'usage et règles applicatives (scan, badge, zone, journal, audit…)
   │      │
   │      └──► domain/   Règles métier pures, sans base ni HTTP (rules, permissions, QR token)
   ▼
repositories/     Seul endroit qui écrit du SQL
   ▼
models/        M  Tables SQLAlchemy        schemas/  V  Contrats JSON (Pydantic)
```

## SOLID, où le voir

| Principe | Application |
|---|---|
| **S** Responsabilité unique | Une règle de scan = une classe (`domain/rules.py`) ; un service = un cas d'usage |
| **O** Ouvert/fermé | Nouvelle règle d'accès = nouvelle classe ajoutée dans `build_default_engine()`, aucun autre fichier modifié |
| **L** Substitution | Toute `Rule` ou `TokenSigner` est interchangeable (Protocols) |
| **I** Ségrégation d'interfaces | Protocols minuscules : `Clock`, `TokenSigner`, `Rule` |
| **D** Inversion de dépendances | Les services reçoivent leurs dépendances (dépôts, horloge, signataire) ; tests = horloge factice, base SQLite mémoire |

## Règles de conception

- Une **sortie n'est jamais refusée** : les mêmes règles ne lèvent que des *drapeaux*.
- Le QR est un JWT Ed25519 **sans donnée personnelle** ; `version` du badge incrémentée à la réémission = ancien QR mort.
- Les droits sont évalués **côté serveur à chaque requête** : rôle + exceptions par personne.
- Journal **immuable** (purge seulement, tracée) ; audit **jamais supprimable**.

## Lancer

```bash
cd backend
pip install -e ".[dev]"
pytest                                          # 218 tests (SQLite en mémoire)
# même suite sur un vrai PostgreSQL (schéma via Alembic) :
BHH_TEST_DATABASE_URL=postgresql+psycopg2://user@host/db pytest   # + la course concurrente
alembic upgrade head                            # base existante : appliquer les migrations (0001 à 0016)
uvicorn app.main:create_app --factory --reload --port 8001  # http://localhost:8001/docs
# production : cp .env.example .env && docker compose up --build   (alembic upgrade head au démarrage)
```

Compte initial : variables `BHH_INITIAL_ADMIN_*`. Migrations : `alembic revision --autogenerate -m "..."`.

Documentation de l'API : `/docs` (Swagger) ou `/redoc`, en français, rangée comme le menu du back-office,
avec le droit requis de chaque route (lu dans le code). Elle est décrite dans `backend/app/api_docs.py` :
toute nouvelle route doit y être ajoutée, sinon `tests/test_api_docs.py` échoue.

## Données de démo

```bash
cd backend && python scripts/seed_demo.py
```
Crée 2 unités (Usine de Bonabéri : Atelier « Sortie obligatoire » + Magasin « Signalé » ; Siège Akwa : Bureaux « Libre » + Salle serveurs), 7 postes, 6 employés fictifs avec photos et badges (QR dans `backend/demo-badges/`), 3 agents dont un qui tient l'entrée et la sortie du magasin, un téléphone de démo (code affiché dans la console), les comptes `rh1`, `superuser1` (mot de passe `Demo-2026!`) et une matinée de passages. Refuse de tourner sur une base qui a déjà des employés (`--force` pour une base de démo). Les agents n'ont pas de compte.

## Fonctionnalités

Auth + RBAC (23 droits, rôles, exceptions par personne, garde-fous) · mots de passe : changement, réinitialisation, mot de passe temporaire imposé, sessions fermées au changement ·
employés : création, modification, suspension, archivage (QR « non reconnu », badges révoqués) et restauration, photos normalisées servies par lien signé 60 s, import Excel en deux temps (vérification sans rien enregistrer, puis création ; modèle à télécharger ; lignes refusées en Excel à corriger et réimporter ; 5 Mo / 5 000 lignes max ; nom du fichier dans l'audit) · actions en lot sur une sélection d'employés (entité / département, suspendre, réactiver, archiver avec motif, ajouter ou retirer des zones ; chaque employé contrôlé et audité, les refus listés) et zones par département (tout l'effectif d'un département, avec le nombre de personnes concernées avant de valider) ·
entités et départements (deux listes indépendantes gérées dans la console, création rapide depuis la fiche employé) · badges (émission réservée aux employés actifs, révocation avec motif, réémission, un seul badge actif garanti en base), QR compact signé Ed25519 avec logo (ECC H) et badge PDF à taille réelle ·
unités, zones, postes : modification, désactivation, suppression protégée ·
« Contrôle des entrées » par zone (Libre / Signalé, avec avertissement de l'agent en option / Sortie obligatoire), heure de la dernière entrée sur « Déjà entré », déblocage tracé (drapeau « Débloqué » sur le scan suivant) ·
accès temporaires (dates) et plages horaires par zone, vérifiés à l'heure de Douala (plages de nuit acceptées, sortie jamais bloquée) · appairage de téléphones sans connexion, chacun limité à son périmètre (unités, zones ou postes cochés ; scan refusé ailleurs) · agents par poste, porte unique entrée + sortie, relève avec historique ·
scan caméra (décodeur natif ou ZXing WebAssembly) et saisie manuelle, verdict avec photo ; l'écran du poste reste masqué jusqu'au clic sur « Démarrer le contrôle », qui active aussi la voix si elle est réglée sur ce téléphone ·
tableau de bord de supervision (présents / sortis par unité et zone, postes, refus) · journal filtrable + purge filtrée (période, employé, département, entité, zone) avec aperçu et confirmation, photos supprimables en lot ·
alertes d'usage suspect (même badge à deux postes trop vite selon le temps de trajet minimum, badge révoqué ou d'un employé archivé présenté, hors horaires, rafales, refus répétés), écran Rapport ▸ Alertes avec prise en compte individuelle ou groupée et révocation du badge · réglage des temps de trajet dans Paramétrage ▸ Réglage de distance · annonce vocale au poste (« Entrée autorisée, Jean Mbarga », refus, alerte), activée ou coupée par téléphone, et des nouvelles alertes au back-office · application en français ou en anglais (sélecteur FR | EN sur le téléphone, à la connexion et dans Général ▸ Identifiant ; textes du back-office dans frontend/src/i18n/admin.ts, messages du serveur dans backend/app/core/i18n.py, des tests signalent tout texte sans traduction ; journal, audit et exports restent en français) · rapports (Rapport ▸ Rapports, droit `reports.view`) : mouvements par employé et par zone (entrées, sorties, refus, déblocages comptés à part, premier et dernier passage), présence par zone (à l'intérieur maintenant, personnes entrées), tendances des refus (par jour, par motif, par zone, personnes les plus refusées, comparaison avec la période précédente ; 30 jours par défaut, 366 max), filtrables par période, entité, département, unité, zone et employé, exports Excel et PDF · sélection de passages dans le Journal pour exporter uniquement les lignes cochées en Excel ou PDF · exports Excel et PDF (journal, audit, employés) audités · écran d'audit (auteur, adresse IP, avant → après, filtres) jamais modifiable.

Derrière Nginx, mettre `BHH_TRUST_PROXY_HEADERS=true` pour que l'audit enregistre l'adresse réelle du poste (en-tête `X-Forwarded-For`) ; laisser `false` si l'API est exposée directement.

## Concurrence

Deux scans simultanés de la même personne sont sérialisés par un verrou sur la ligne employé
(`EmployeeRepository.get_locked`) : un seul passe en zone stricte.

## Pas encore fait

Voir `suivi de taches.xlsx` (tâches 35 et suivantes) · mode hors ligne (phase 3) · durcissement (verrouillage des connexions, HTTPS Nginx).
