"""Readable audit: French labels for actions, fields and values, and a one-line summary.

Used by the API (``action_label`` / ``summary`` on each line) and by the Excel / PDF exports,
so that the screen and the files say exactly the same thing.
"""
from collections.abc import Iterable

CATEGORY_LABEL = {
    "employee": "Employés",
    "badge": "Badges",
    "authorization": "Accès aux zones",
    "zone": "Zones",
    "unit": "Unités",
    "checkpoint": "Postes",
    "agent": "Agents",
    "device": "Téléphones",
    "presence": "Présences",
    "user": "Utilisateurs",
    "role": "Rôles et droits",
    "export": "Exports",
    "alert": "Alertes",
    "entity": "Entités",
    "department": "Départements",
    "logs": "Purge du journal",
}

ACTION_LABEL = {
    "employee.create": "Employé créé",
    "employee.update": "Fiche employé modifiée",
    "employee.status": "Statut de l'employé changé",
    "employee.archive": "Employé archivé",
    "employee.restore": "Employé restauré",
    "employee.import": "Import d'employés",
    "employee.bulk": "Modification en lot",
    "employee.photo": "Photo ajoutée ou remplacée",
    "employee.photo.delete": "Photo retirée",
    "badge.issue": "Badge émis",
    "badge.revoke": "Badge révoqué",
    "badge.print": "Badge imprimé",
    "authorization.grant": "Accès à une zone accordé",
    "authorization.revoke": "Accès à une zone retiré",
    "authorization.set": "Accès aux zones modifiés",
    "authorization.restrict": "Dates ou horaires d'accès modifiés",
    "zone.create": "Zone créée",
    "zone.update": "Zone modifiée",
    "zone.delete": "Zone supprimée",
    "zone.move": "Zone déplacée",
    "zone.antipassback": "Contrôle des entrées changé",
    "unit.create": "Unité créée",
    "unit.rename": "Unité renommée",
    "unit.delete": "Unité supprimée",
    "checkpoint.create": "Poste créé",
    "checkpoint.update": "Poste modifié",
    "checkpoint.delete": "Poste supprimé",
    "agent.create": "Agent créé",
    "agent.update": "Agent modifié",
    "agent.delete": "Agent supprimé",
    "agent.active": "Agent activé ou désactivé",
    "agent.assign": "Agent placé à un poste",
    "agent.unassign": "Poste libéré",
    "device.create": "Téléphone ajouté",
    "device.recode": "Nouveau code d'appairage",
    "device.revoke": "Téléphone révoqué",
    "device.rename": "Téléphone renommé",
    "device.delete": "Téléphone supprimé",
    "device.pair": "Téléphone appairé",
    "device.scope": "Périmètre du téléphone modifié",
    "device.voice": "Voix du téléphone réglée",
    "presence.unblock": "Présence débloquée",
    "user.create": "Utilisateur créé",
    "user.activate": "Utilisateur réactivé",
    "user.deactivate": "Utilisateur désactivé",
    "user.role": "Rôle de l'utilisateur changé",
    "user.override": "Droit individuel modifié",
    "user.override.clear": "Droit individuel retiré",
    "user.password.change": "Mot de passe changé",
    "user.password.reset": "Mot de passe réinitialisé",
    "role.update": "Droits d'un rôle modifiés",
    "entity.create": "Entité créée",
    "entity.rename": "Entité renommée",
    "entity.delete": "Entité supprimée",
    "department.create": "Département créé",
    "department.rename": "Département renommé",
    "department.delete": "Département supprimé",
    "alert.ack": "Alerte prise en compte",
    "alert.travel_time": "Temps de trajet entre postes réglé",
    "alert.travel_time.delete": "Temps de trajet entre postes retiré",
    "export.xlsx": "Export Excel",
    "export.pdf": "Export PDF",
    "export.csv": "Export CSV",
    "logs.purge": "Purge du journal des passages",
}

FIELD_LABEL = {
    "name": "Nom", "full_name": "Nom", "first_name": "Prénom", "last_name": "Nom",
    "matricule": "Matricule", "job_title": "Fonction", "entity_id": "Entité", "entity": "Entité",
    "department_id": "Département", "department": "Département", "status": "Statut",
    "mode": "Contrôle des entrées", "antipassback_mode": "Contrôle des entrées", "unit": "Unité",
    "code": "Code", "description": "Description", "sensitivity": "Sensibilité", "is_active": "Active",
    "active": "Actif", "direction": "Sens", "role": "Rôle", "effect": "Effet", "permission": "Droit",
    "permissions": "Droits", "zones": "Zones", "zone": "Zone", "reason": "Motif", "note": "Précision",
    "version": "Version", "replaced_versions": "Versions remplacées", "rows": "Lignes",
    "filters": "Filtres", "checkpoint": "Poste", "checkpoints": "Postes", "created": "Créés",
    "rejected": "Rejetés",
    "operation": "Opération",
    "total": "Employés concernés", "done": "Modifiés", "unchanged": "Déjà à jour", "failed": "En échec",
    "file": "Fichier", "created_entities": "Entités créées",
    "created_departments": "Départements créés", "deleted": "Supprimées", "badges_revoked": "Badges révoqués",
    "presences_cleared": "Présences effacées", "added": "Ajoutés", "removed": "Retirés",
    "username": "Identifiant", "phone": "Téléphone", "replaced": "Remplace",
    "valid_until": "Valable jusqu'au", "badge_id": "Badge n°", "state": "État",
    "warn_agent": "Avertir l'agent", "also_keeps": "Garde aussi", "left": "A quitté",
    "previous_photo": "Remplace une photo existante", "restrictions": "Restrictions", "scope": "Périmètre",
    "voice": "Voix",
    "minutes": "Minutes", "alert_id": "Alerte n°",
}

# Technical keys kept in the stored detail but not worth reading on screen.
HIDDEN = {"badge_id", "zone_id"}
# When before / after already say it, these are redundant.
REDUNDANT_WITH_CHANGES = {"added", "removed"}

VALUE_LABEL = {
    "ACTIF": "actif", "SUSPENDU": "suspendu", "ARCHIVE": "archivé", "REVOQUE": "révoqué",
    "org": "entité / département", "suspend": "suspendre", "reactivate": "réactiver", "archive": "archiver",
    "add_zones": "ajouter des zones", "remove_zones": "retirer des zones",
    "DESACTIVE": "Libre", "SOUPLE": "Signalé", "STRICT": "Sortie obligatoire",
    "ENTREE": "Entrée", "SORTIE": "Sortie",
    "PERTE": "Perte", "VOL": "Vol", "DEPART": "Départ", "REMPLACEMENT": "Remplacement", "AUTRE": "Autre",
    "STANDARD": "Standard", "RESTREINTE": "Restreinte", "CRITIQUE": "Critique",
    "SIMULTANEE": "Utilisation simultanée", "BADGE_REVOQUE": "Badge révoqué présenté",
    "EMPLOYE_ARCHIVE": "QR d'employé archivé", "HORS_HORAIRE": "Hors horaires", "RAFALE": "Rafale de scans",
    "REFUS_REPETES": "Refus répétés",
    "allow": "accordé", "deny": "refusé", "in": "à l'intérieur", "out": "sorti",
}


def audit_label(action: str) -> str:
    return ACTION_LABEL.get(action, action)


def audit_category_label(prefix: str) -> str:
    return CATEGORY_LABEL.get(prefix.split(".")[0], prefix)


def field_label(key: str) -> str:
    return FIELD_LABEL.get(key, key.replace("_", " "))


def value_label(value: object) -> str:
    if value is None or value == "" or value == []:
        return "–"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, dict):
        return ", ".join(f"{field_label(k)} {value_label(v)}" for k, v in value.items())
    if isinstance(value, Iterable) and not isinstance(value, str):
        return ", ".join(value_label(v) for v in value)
    return VALUE_LABEL.get(str(value), str(value))


def changes(detail: dict) -> list[dict]:
    """``before`` / ``after`` as a list of {field, label, before, after} (only what changed)."""
    before, after = detail.get("before"), detail.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    keys = list(dict.fromkeys([*before.keys(), *after.keys()]))
    return [{"field": k, "label": field_label(k), "before": before.get(k), "after": after.get(k),
             "before_text": value_label(before.get(k)), "after_text": value_label(after.get(k))}
            for k in keys if before.get(k) != after.get(k)]


def describe_other(detail: dict | None) -> str:
    """Everything but before / after: motif, filters, number of rows..."""
    detail = detail or {}
    skip = {"before", "after", *HIDDEN} | (REDUNDANT_WITH_CHANGES if changes(detail) else set())
    return " ; ".join(f"{field_label(k)} : {value_label(v)}" for k, v in detail.items()
                      if k not in skip and v not in (None, "", [], {}))  # empty values say nothing


def describe_detail(detail: dict | None) -> str:
    """One line: « Nom : Usine → Usine A ; Motif : Perte »."""
    detail = detail or {}
    parts = [f"{c['label']} : {c['before_text']} → {c['after_text']}" for c in changes(detail)]
    other = describe_other(detail)
    return " ; ".join([*parts, other] if other else parts)
