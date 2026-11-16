"""Documentation of the API shown at /docs (Swagger) and /redoc, in French for the operators.

Everything is here rather than spread over the controllers: the overview, the ordered sections
(same order as the back-office menu) and, for each route, its section, summary and description.
The right needed (« Droit requis ») is not written by hand: it is read from the ``require(...)``
guards, so it cannot drift from the code. ``tests/test_api_docs.py`` fails when a route has no
entry here (or an entry no longer matches a route): /docs stays in step with the work.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute

TITLE = "BHHaccess – API"

DESCRIPTION = """
API du contrôle d'accès par badge QR de BHH : back-office (administration, RH, sécurité),
téléphones des agents aux postes, et rapports.

### S'authentifier
* **Back-office et agents connectés** : `POST /api/auth/login` renvoie un jeton ; l'envoyer ensuite
  dans l'en-tête `Authorization: Bearer <jeton>` (bouton **Authorize** ci-dessus). La session dure
  8 h. Un mot de passe temporaire doit être changé (`POST /api/auth/password`) avant tout autre appel.
* **Téléphones appairés** (sans compte) : `POST /api/device/pair` avec le code à usage unique
  affiché dans le back-office, puis l'en-tête `X-Device-Token: <jeton>` sur les routes `/api/device/...`.
  Un téléphone ne voit et ne scanne que les postes de **son périmètre**.

### Droits
Chaque route indique le **droit requis** (ex. `employees.edit`). Rôles par défaut : *Super admin*
(tout), *Super user* (tout sauf utilisateurs, rôles et configuration), *RH*, *Agent* ; un droit
peut aussi être accordé ou retiré à une personne précise.

### Décisions de scan (`verdict`)
`AUTORISE`, `SORTIE_ENREGISTREE`, `REFUSE_ZONE`, `REFUSE_REVOQUE`, `REFUSE_EXPIRE`,
`REFUSE_EMPLOYE_INACTIF`, `REFUSE_INVALIDE`, `REFUSE_ANTIPASSBACK`.
Le refus d'un accès temporaire ou d'une plage horaire est un `REFUSE_ZONE` dont la raison précise
`acces_pas_encore_valable`, `acces_expire` ou `hors_horaire`.
Indicateurs possibles sur une ligne du journal : `DOUBLE_ENTREE`, `SORTIE_SANS_ENTREE`,
`SORTIE_BADGE_REVOQUE`, `SORTIE_BADGE_EXPIRE`, `SORTIE_EMPLOYE_SUSPENDU`, `DEBLOQUE`.
Méthode d'une ligne : `QR`, `MANUEL` (matricule saisi), `CONSOLE` (déblocage depuis le back-office).

### Alertes
Calculées à chaque scan, elles ne changent jamais la décision : `SIMULTANEE` (deux postes plus vite
que le temps de trajet), `BADGE_REVOQUE`, `EMPLOYE_ARCHIVE`, `HORS_HORAIRE`, `RAFALE`, `REFUS_REPETES`.

### Erreurs
Réponse `{"detail": "message en français"}` : `400` règle métier, `401` non connecté,
`403` droit manquant ou hors périmètre, `404` introuvable, `409` conflit (ex. déjà traité),
`422` données invalides, `429` trop d'essais.
Avec l'en-tête `Accept-Language: en`, les messages destinés aux écrans (erreurs, motif d'un refus) sont
renvoyés en anglais quand une traduction existe ; sinon, et par défaut, en français.

Dates et heures : ISO 8601 avec fuseau (affichage local : Africa/Douala).
"""

# Same order as the back-office menu.
TAGS: list[dict[str, str]] = [
    {"name": "Connexion", "description": "Ouvrir une session, voir son compte, changer son mot de passe."},
    {"name": "Tableau de bord", "description": "Supervision en direct : qui est dedans, compteurs du jour."},
    {"name": "Employés", "description": "Fiches, import Excel, statut (suspendre, archiver, restaurer), photo."},
    {"name": "Badges", "description": "Émission, révocation avec motif, QR et badge à imprimer."},
    {"name": "Entités et départements",
     "description": "Deux listes indépendantes, utilisées dans les fiches employés."},
    {"name": "Unités et zones",
     "description": "Unités (sites), zones, postes de contrôle, anti-passback, accès des employés "
                    "(zones cochées, accès temporaires et plages horaires)."},
    {"name": "Agents", "description": "Agents de sécurité et leur affectation aux postes."},
    {"name": "Téléphones",
     "description": "Côté téléphone (appairage, postes, scan, sans compte) et gestion dans le back-office "
                    "(codes, périmètre, révocation)."},
    {"name": "Utilisateurs", "description": "Comptes du back-office, rôles et droits individuels."},
    {"name": "Scan", "description": "Scan par un agent connecté et déblocage depuis la console."},
    {"name": "Journal", "description": "Passages enregistrés (consultation, purge)."},
    {"name": "Alertes",
     "description": "Usages suspects de badge et temps de trajet minimum entre postes."},
    {"name": "Audit", "description": "Qui a fait quoi, quand, depuis quelle adresse. Jamais modifiable."},
    {"name": "Exports", "description": "Excel et PDF du journal, de l'audit et des employés."},
    {"name": "Exploitation", "description": "Surveillance du service."},
]

# "METHOD /path": (section, summary, description). Description may be "".
ROUTES: dict[str, tuple[str, str, str]] = {
    # --- Connexion
    "POST /api/auth/login": ("Connexion", "Se connecter",
        "Identifiant + mot de passe ; renvoie le jeton de session (8 h). Trop d'échecs : `429`."),
    "GET /api/auth/me": ("Connexion", "Mon compte", "Nom, rôle et droits effectifs de la personne connectée."),
    "POST /api/auth/password": ("Connexion", "Changer mon mot de passe",
        "Renvoie une nouvelle session ; les autres sessions de la personne s'arrêtent. "
        "Seule route ouverte (avec *Mon compte*) tant qu'un mot de passe temporaire n'est pas changé."),
    # --- Tableau de bord
    "GET /api/monitoring": ("Tableau de bord", "Supervision en direct",
        "Présents / sortis par unité et par zone, compteurs du jour, état des postes, derniers refus. "
        "Filtre facultatif `unit_id`."),
    "GET /api/stats/today": ("Tableau de bord", "Chiffres du jour", "Entrées, sorties, refus et présents."),
    "GET /api/presence": ("Tableau de bord", "Qui est à l'intérieur", "Filtre facultatif `zone_id`."),
    "GET /api/assignments": ("Tableau de bord", "Historique des affectations d'agents",
        "Quel agent tenait quel poste, et quand."),
    # --- Employés
    "GET /api/employees": ("Employés", "Lister les employés",
        "Sans `status` : effectif actuel (actifs et suspendus). `status=ARCHIVE` : les archives. "
        "Recherche par nom ou matricule, pagination `limit`/`offset`."),
    "POST /api/employees": ("Employés", "Créer un employé",
        "Matricule unique ; entité et département choisis dans les listes (indépendantes)."),
    "POST /api/employees/bulk": ("Employés", "Modifier des employés en lot",
        "Pour une sélection (`employee_ids`) ou tout l'effectif d'un département / d'une entité "
        "(`in_department_id`, `in_entity_id`) : `org` (entité et/ou département ; seuls les champs envoyés "
        "changent), `suspend`, `reactivate`, `archive` (motif obligatoire), `add_zones` / `remove_zones` "
        "(`zone_ids`). Chaque employé passe les contrôles habituels et a sa ligne d'audit ; un refus "
        "n'empêche pas les autres. `dry_run` : compte seulement les employés concernés. 1 000 au maximum. "
        "Droit selon l'action : `employees.edit`, `employees.archive` ou `authorizations.manage`."),
    "GET /api/employees/import/template.xlsx": ("Employés", "Modèle d'import (Excel)",
        "Colonnes attendues, une ligne d'exemple et un mode d'emploi."),
    "POST /api/employees/import/check": ("Employés", "Import, étape 1 : vérifier le fichier",
        "Lit et contrôle chaque ligne **sans rien enregistrer** : nombre de lignes conformes, lignes refusées "
        "avec leur motif, entités et départements qui seraient créés, aperçu. 5 Mo et 5 000 lignes maximum."),
    "POST /api/employees/import/rejected.xlsx": ("Employés", "Import : télécharger les lignes refusées",
        "Les lignes refusées avec leurs colonnes d'origine et une colonne « Erreurs » : à corriger puis importer."),
    "POST /api/employees/import": ("Employés", "Import, étape 2 : créer les employés",
        "Mêmes contrôles, puis crée les lignes conformes ; renvoie les lignes rejetées. "
        "Le nom du fichier est inscrit dans l'audit."),
    "GET /api/employees/{employee_id}": ("Employés", "Fiche d'un employé",
        "Avec une adresse de photo signée valable 60 s (les listes indiquent seulement `has_photo`)."),
    "PATCH /api/employees/{employee_id}": ("Employés", "Modifier un employé", "Seuls les champs envoyés changent."),
    "PATCH /api/employees/{employee_id}/status": ("Employés", "Suspendre ou réactiver",
        "Un employé suspendu ne peut plus entrer ; sa sortie reste enregistrée (indicateur "
        "`SORTIE_EMPLOYE_SUSPENDU`). L'archivage est une action séparée."),
    "POST /api/employees/{employee_id}/archive": ("Employés", "Archiver (départ)",
        "Motif obligatoire. Le badge actif est révoqué ; son QR présenté ensuite affiche « QR non reconnu » "
        "à l'agent et crée une alerte `EMPLOYE_ARCHIVE`."),
    "POST /api/employees/{employee_id}/restore": ("Employés", "Restaurer un employé archivé",
        "Il redevient actif ; son ancien badge reste révoqué, un nouveau badge est à émettre."),
    "POST /api/employees/{employee_id}/photo": ("Employés", "Ajouter ou remplacer la photo",
        "JPEG ou PNG, taille limitée. Montrée à l'agent au scan pour comparer avec le visage."),
    "DELETE /api/employees/{employee_id}/photo": ("Employés", "Retirer la photo", ""),
    "GET /api/employees/{employee_id}/badges": ("Employés", "Badges d'un employé",
        "Historique complet, avec motif et auteur des révocations."),
    "GET /api/employees/{employee_id}/authorizations": ("Employés", "Autorisations d'un employé (liste brute)",
        "Préférer *Accès d'un employé* (regroupé par unité, avec restrictions)."),
    # --- Badges
    "POST /api/badges": ("Badges", "Émettre un badge",
        "Seulement pour un employé actif. Un badge actif existant est remplacé (motif `REMPLACE`) : "
        "un seul badge actif par employé."),
    "POST /api/badges/{badge_id}/revoke": ("Badges", "Révoquer un badge",
        "Motif : `PERTE`, `VOL`, `DEPART` ou `AUTRE` (précision obligatoire). Effet immédiat ; "
        "chaque présentation ensuite crée une alerte `BADGE_REVOQUE`."),
    "GET /api/badges/{badge_id}/qr-token": ("Badges", "Contenu du QR", "Jeton signé (Ed25519) encodé dans le QR."),
    "GET /api/badges/{badge_id}/qr.png": ("Badges", "Image du QR",
        "PNG, correction d'erreur H, logo BHH au centre, matricule dessous."),
    "GET /api/badges/{badge_id}/print.pdf": ("Badges", "Badge à imprimer (PDF)",
        "QR + matricule, à taille réelle avec traits de coupe."),
    # --- Entités et départements
    "GET /api/org": ("Entités et départements", "Les deux listes",
        "Entités et départements, chacun avec le nombre d'employés qui l'utilisent."),
    "GET /api/org/entities": ("Entités et départements", "Lister les entités", ""),
    "POST /api/org/entities": ("Entités et départements", "Créer une entité", "Nom unique."),
    "PATCH /api/org/entities/{entity_id}": ("Entités et départements", "Renommer une entité", ""),
    "DELETE /api/org/entities/{entity_id}": ("Entités et départements", "Supprimer une entité",
        "Refusé (`409`) tant que des employés l'utilisent."),
    "GET /api/org/departments": ("Entités et départements", "Lister les départements", ""),
    "POST /api/org/departments": ("Entités et départements", "Créer un département",
        "Nom unique ; un département ne dépend d'aucune entité."),
    "PATCH /api/org/departments/{department_id}": ("Entités et départements", "Renommer un département", ""),
    "DELETE /api/org/departments/{department_id}": ("Entités et départements", "Supprimer un département",
        "Refusé (`409`) tant que des employés l'utilisent."),
    # --- Unités et zones
    "GET /api/units": ("Unités et zones", "Lister les unités", ""),
    "POST /api/units": ("Unités et zones", "Créer une unité", ""),
    "PATCH /api/units/{unit_id}": ("Unités et zones", "Renommer une unité", ""),
    "DELETE /api/units/{unit_id}": ("Unités et zones", "Supprimer une unité",
        "Refusé (`409`) tant qu'elle contient des zones."),
    "GET /api/zones": ("Unités et zones", "Lister les zones", "Avec leurs postes et leur réglage anti-passback."),
    "POST /api/zones": ("Unités et zones", "Créer une zone", "Dans une unité ; code, description et sensibilité."),
    "PATCH /api/zones/{zone_id}": ("Unités et zones", "Modifier une zone",
        "Seuls les champs envoyés changent ; `null` efface le code ou la description."),
    "DELETE /api/zones/{zone_id}": ("Unités et zones", "Supprimer une zone",
        "Refusé (`409`) si la zone a un historique de passages ou d'agents : la désactiver plutôt."),
    "PATCH /api/zones/{zone_id}/unit": ("Unités et zones", "Déplacer une zone vers une autre unité", ""),
    "PATCH /api/zones/{zone_id}/antipassback": ("Unités et zones", "Contrôle des entrées (anti-passback)",
        "Mode de la zone : `DESACTIVE`, `SOUPLE` (double entrée ou sortie sans entrée seulement signalée) "
        "ou `STRICT` (refus `REFUSE_ANTIPASSBACK`), et avertissement affiché à l'agent."),
    "POST /api/zones/{zone_id}/checkpoints": ("Unités et zones", "Ajouter un poste",
        "Sens : `ENTREE` ou `SORTIE`."),
    "GET /api/checkpoints": ("Unités et zones", "Lister les postes", "Tous les postes, avec zone et unité."),
    "PATCH /api/checkpoints/{checkpoint_id}": ("Unités et zones", "Modifier un poste",
        "Nom, sens, activation."),
    "DELETE /api/checkpoints/{checkpoint_id}": ("Unités et zones", "Supprimer un poste", ""),
    "GET /api/employees/{employee_id}/access": ("Unités et zones", "Accès d'un employé",
        "Zones cochées, regroupées par unité, avec accès temporaire, plages horaires et lisible "
        "(« jusqu'au 30/11 · sam 06:00–10:00 »)."),
    "PUT /api/employees/{employee_id}/access": ("Unités et zones", "Définir les zones d'un employé",
        "Liste complète des zones autorisées (`zone_ids`) ; les zones gardées conservent leurs restrictions."),
    "PUT /api/employees/{employee_id}/access/{zone_id}/restrictions": ("Unités et zones",
        "Restrictions d'une zone (dates, horaires)",
        "Accès temporaire (`valid_from` / `valid_until`) et plages hebdomadaires (jours 1 = lundi … 7 = dimanche, "
        "plages de nuit possibles, début = fin pour toute la journée). Vide = accès permanent."),
    "PUT /api/authorizations": ("Unités et zones", "Autoriser une zone (unitaire)",
        "Préférer *Définir les zones d'un employé*."),
    "DELETE /api/authorizations/{employee_id}/{zone_id}": ("Unités et zones", "Retirer une zone (unitaire)", ""),
    # --- Agents
    "GET /api/agents": ("Agents", "Lister les agents", ""),
    "POST /api/agents": ("Agents", "Créer un agent", ""),
    "PATCH /api/agents/{agent_id}": ("Agents", "Modifier un agent", ""),
    "DELETE /api/agents/{agent_id}": ("Agents", "Supprimer un agent", ""),
    "PATCH /api/agents/{agent_id}/active": ("Agents", "Activer ou désactiver un agent", ""),
    "PUT /api/checkpoints/{checkpoint_id}/agent": ("Agents", "Affecter un agent à un poste",
        "Les scans du poste lui sont attribués dans le journal ; `null` libère le poste."),
    # --- Téléphones
    "POST /api/device/pair": ("Téléphones", "Appairer un téléphone",
        "Côté téléphone, sans compte : échange le code à usage unique contre le jeton `X-Device-Token`. "
        "Trop d'échecs : `429`."),
    "GET /api/device/settings": ("Téléphones", "Réglages du téléphone",
        "Son nom et si la voix est activée. En-tête `X-Device-Token`."),
    "GET /api/device/checkpoints": ("Téléphones", "Postes du téléphone",
        "Seulement les postes actifs de son périmètre. En-tête `X-Device-Token`."),
    "POST /api/device/scan": ("Téléphones", "Scanner un QR (téléphone)",
        "En-tête `X-Device-Token`. Poste hors périmètre : `403`. Renvoie la décision, la photo, "
        "l'avertissement éventuel, la dernière entrée et l'alerte déclenchée (`alert`), à annoncer."),
    "POST /api/device/scan/manual": ("Téléphones", "Saisir un matricule (téléphone)",
        "Quand le QR est abîmé. Même réponse que le scan ; méthode `MANUEL` au journal."),
    "GET /api/devices": ("Téléphones", "Lister les téléphones", "Avec le résumé du périmètre."),
    "POST /api/devices": ("Téléphones", "Déclarer un téléphone", "Renvoie le code d'appairage à usage unique."),
    "POST /api/devices/{device_id}/code": ("Téléphones", "Nouveau code d'appairage",
        "Pour réinstaller le téléphone ; l'ancien jeton cesse de fonctionner."),
    "PATCH /api/devices/{device_id}": ("Téléphones", "Renommer un téléphone", ""),
    "DELETE /api/devices/{device_id}": ("Téléphones", "Supprimer un téléphone", ""),
    "PUT /api/devices/{device_id}/scope": ("Téléphones", "Périmètre du téléphone",
        "Unités, zones et postes couverts (une unité couvre toutes ses zones, une zone tous ses postes). "
        "Vide = tout le site."),
    "PUT /api/devices/{device_id}/voice": ("Téléphones", "Activer ou couper la voix",
        "Le téléphone annonce le résultat à voix haute (« Entrée autorisée, Jean Mbarga », « Alerte : "
        "badge révoqué présenté »). Le bip et la vibration restent toujours."),
    "POST /api/devices/{device_id}/revoke": ("Téléphones", "Révoquer un téléphone",
        "Perdu ou volé : il ne peut plus rien faire."),
    # --- Utilisateurs
    "GET /api/users": ("Utilisateurs", "Lister les utilisateurs", ""),
    "POST /api/users": ("Utilisateurs", "Créer un utilisateur",
        "Avec un mot de passe temporaire à changer à la première connexion."),
    "PATCH /api/users/{user_id}/active": ("Utilisateurs", "Activer ou désactiver un compte", ""),
    "POST /api/users/{user_id}/password": ("Utilisateurs", "Réinitialiser le mot de passe",
        "Mot de passe temporaire ; ses sessions ouvertes s'arrêtent."),
    "PUT /api/users/{user_id}/role": ("Utilisateurs", "Changer le rôle", ""),
    "PUT /api/users/{user_id}/overrides": ("Utilisateurs", "Accorder ou retirer un droit à une personne",
        "Prioritaire sur son rôle."),
    "DELETE /api/users/{user_id}/overrides/{permission}": ("Utilisateurs", "Revenir au droit du rôle", ""),
    "GET /api/roles": ("Utilisateurs", "Lister les rôles", "Avec leurs droits."),
    "PUT /api/roles/{role_id}": ("Utilisateurs", "Modifier les droits d'un rôle", ""),
    # --- Scan (agent connecté)
    "POST /api/scan": ("Scan", "Scanner un QR (agent connecté)",
        "Renvoie la décision (`verdict`), la photo (sauf `REFUSE_INVALIDE`), l'avertissement éventuel "
        "et la dernière entrée. Les alertes sont calculées au passage, sans changer la décision."),
    "POST /api/scan/manual": ("Scan", "Saisir un matricule (agent connecté)",
        "Quand le QR est abîmé ; méthode `MANUEL` au journal."),
    "POST /api/presence/unblock": ("Scan", "Débloquer une personne (console)",
        "Remet la présence à zéro pour une zone bloquée par l'anti-passback. Ligne `CONSOLE` au journal ; "
        "le passage suivant porte l'indicateur `DEBLOQUE`."),
    # --- Journal
    "GET /api/logs": ("Journal", "Consulter le journal",
        "Plus récent d'abord. Filtres : période, employé, zone, poste, décision, indicateur, méthode."),
    "POST /api/logs/purge": ("Journal", "Purger le journal",
        "Supprime les lignes antérieures à une date ; l'opération est tracée dans l'audit."),
    "GET /api/logs/export.csv": ("Journal", "Exporter le journal en CSV",
        "Ancien format ; préférer *Exports*."),
    # --- Alertes
    "GET /api/alerts": ("Alertes", "Lister les alertes",
        "Plus récente d'abord. Filtres `status` (`NOUVELLE`, `PRISE_EN_COMPTE`) et `type`."),
    "GET /api/alerts/count": ("Alertes", "Nombre d'alertes nouvelles", "Compteur du menu."),
    "POST /api/alerts/{alert_id}/ack": ("Alertes", "Prendre en compte une alerte",
        "Note facultative. Déjà prise en compte : `409`."),
    "POST /api/alerts/{alert_id}/revoke-badge": ("Alertes", "Révoquer le badge depuis l'alerte",
        "Révoque le badge concerné (motif comme pour une révocation) puis marque l'alerte prise en compte."),
    "GET /api/travel-times": ("Alertes", "Temps de trajet réglés",
        "Par défaut : 10 min entre deux unités différentes, aucun contrôle dans une même unité."),
    "PUT /api/travel-times": ("Alertes", "Régler le temps de trajet entre deux postes",
        "Valable dans les deux sens, en minutes ; `0` = jamais contrôler cette paire."),
    "DELETE /api/travel-times/{travel_id}": ("Alertes", "Revenir au temps par défaut", ""),
    # --- Audit
    "GET /api/audit": ("Audit", "Consulter l'audit",
        "Plus récent d'abord, avec auteur, adresse IP, libellés et changements avant / après. "
        "Filtres : période, auteur, action (préfixe), objet, actions des téléphones."),
    "GET /api/audit/actors": ("Audit", "Auteurs présents dans l'audit", "Pour le filtre."),
    # --- Exports
    "GET /api/exports/journal.{fmt}": ("Exports", "Exporter le journal",
        "`fmt` : `xlsx` ou `pdf`. Mêmes filtres que l'écran Journal ; l'export est tracé dans l'audit."),
    "GET /api/exports/audit.{fmt}": ("Exports", "Exporter l'audit",
        "`fmt` : `xlsx` ou `pdf`. Mêmes filtres que l'écran Audit."),
    "GET /api/exports/employees.{fmt}": ("Exports", "Exporter les employés", "`fmt` : `xlsx` ou `pdf`."),
    # --- Exploitation
    "GET /health": ("Exploitation", "État du service", "Répond `ok` quand l'API tourne."),
}


def route_keys(path: str, route: APIRoute) -> list[str]:
    return [f"{method} {path}" for method in sorted(route.methods - {"HEAD", "OPTIONS"})]


def required_rights(route: APIRoute) -> tuple[list[str], bool]:
    """Rights taken from the ``require(...)`` guards; True when the phone token is the credential."""
    rights: list[str] = []
    device = False
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop(0)  # declaration order
        for permission in getattr(dep.call, "permissions", ()):
            if str(permission) not in rights:
                rights.append(str(permission))
        if getattr(dep.call, "__name__", "") == "current_device":
            device = True
        stack.extend(dep.dependencies)
    return rights, device


def documented_routes(app: FastAPI) -> list[tuple[str, APIRoute]]:
    """(public path, route) of every route shown in /docs.

    Recent FastAPI keeps each included router as one entry (``original_router`` + include prefix)
    instead of copying its routes into the app: walk both shapes, and document the routers' own
    route objects, which are the ones the OpenAPI schema is built from.
    """

    def walk(routes, prefix: str):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                context = getattr(route, "include_context", None)
                yield from walk(inner.routes, prefix + getattr(context, "prefix", ""))
            elif isinstance(route, APIRoute) and route.include_in_schema:
                yield prefix + route.path, route

    return list(walk(app.routes, ""))


def apply(app: FastAPI) -> None:
    """Section, summary, description and right of every route (missing entries are left as they are)."""
    app.title = TITLE
    app.description = DESCRIPTION
    app.openapi_tags = TAGS
    for path, route in documented_routes(app):
        entry = next((ROUTES[k] for k in route_keys(path, route) if k in ROUTES), None)
        if entry is None:
            continue
        tag, summary, description = entry
        rights, device = required_rights(route)
        if rights:
            access = "**Droit requis** : " + " + ".join(f"`{r}`" for r in rights)
        elif device:
            access = "**Accès** : téléphone appairé (en-tête `X-Device-Token`)"
        elif path in ("/api/auth/login", "/api/device/pair", "/health"):
            access = "**Accès** : public"
        else:
            access = "**Accès** : toute personne connectée"
        route.tags = [tag]
        route.summary = summary
        route.description = f"{description}\n\n{access}" if description else access
    app.openapi_schema = None
