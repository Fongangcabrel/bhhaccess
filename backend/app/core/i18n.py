"""Messages sent to the screens, in the language the app asks for (header ``Accept-Language``).

The code keeps writing its messages in French (the reference language, and the one of the journal
and the audit). Here they are translated on the way out when the app asks for English; a message
without a translation is sent in French rather than failing.
"""

import re

from fastapi import Request

EN: dict[str, str] = {
    # --- phones: pairing, perimeter, scan ------------------------------------------
    "Code invalide ou expiré": "Invalid or expired code",
    "Appareil non reconnu : appairez à nouveau ce téléphone": "Device not recognised: pair this phone again",
    "Trop de tentatives, réessayez dans quelques minutes": "Too many attempts, try again in a few minutes",
    "Ce poste n'est pas dans le périmètre de ce téléphone": "This post is not in this phone's perimeter",
    "Point de contrôle introuvable": "Checkpoint not found",
    "Ce poste est désactivé : choisissez un autre poste": "This post is deactivated: choose another post",
    "Aucun badge actif pour ce matricule": "No active badge for this employee number",
    "Authentification requise": "Authentication required",
    # --- back-office --------------------------------------------------------------------
    "Agent introuvable": "Agent not found",
    "Ce rôle est attribué à des comptes : donnez-leur d'abord un autre rôle":
        "This role is held by accounts: give them another role first",
    "Les quatre rôles modèles ne peuvent être ni renommés ni supprimés":
        "The four template roles can be neither renamed nor deleted",
    "Nom du rôle obligatoire": "Role name required",
    "Un rôle porte déjà ce nom": "A role already has this name",
    "La date de début doit précéder la date de fin": "The start date must come before the end date",
    "Période trop longue : 366 jours maximum pour les tendances": "Period too long: 366 days at most for trends",
    "Alerte déjà prise en compte": "Alert already handled",
    "Alerte introuvable": "Alert not found",
    "Appareil introuvable": "Device not found",
    "Aucun badge lié à cette alerte": "No badge linked to this alert",
    "Autorisation introuvable": "Authorisation not found",
    "Badge introuvable": "Badge not found",
    "Badge révoqué : émettez un nouveau badge pour l'imprimer": "Badge revoked: issue a new badge to print it",
    "Ce badge est déjà révoqué": "This badge is already revoked",
    "Ce poste a un historique de passages : désactivez-le plutôt":
        "This post has a passage history: deactivate it instead",
    "Ce poste est désactivé": "This post is deactivated",
    "Ce rôle contient des droits que vous n'avez pas": "This role contains rights you do not have",
    "Ce téléphone a déjà scanné : bloquez-le plutôt, le journal le cite":
        "This phone has already scanned: block it instead, the log refers to it",
    "Cet agent a déjà été posté : désactivez-le plutôt pour garder l'historique":
        "This agent has already been posted: deactivate them instead to keep the history",
    "Cet agent est désactivé": "This agent is deactivated",
    "Cet employé n'a pas de photo": "This employee has no photo",
    "Cet employé n'est pas archivé": "This employee is not archived",
    "Cette unité contient des zones : déplacez-les ou supprimez-les d'abord":
        "This unit contains zones: move or delete them first",
    "Cette zone a un historique de passages : désactivez-la plutôt":
        "This zone has a passage history: deactivate it instead",
    "Changez votre mot de passe temporaire avant de continuer": "Change your temporary password before going on",
    "Choisissez deux postes différents": "Choose two different posts",
    "Choisissez un mot de passe différent de l'actuel": "Choose a password different from the current one",
    "Cochez et enregistrez d'abord cette zone pour l'employé": "Tick and save this zone for the employee first",
    "Code de zone déjà utilisé": "Zone code already used",
    "Colonnes obligatoires absentes": "Required columns missing",
    "Compte inactif ou introuvable": "Account inactive or not found",
    "Des agents ont déjà tenu ce poste : désactivez-le plutôt":
        "Agents have already held this post: deactivate it instead",
    "Des agents ont déjà été postés dans cette zone : désactivez-la plutôt":
        "Agents have already been posted in this zone: deactivate it instead",
    "Des employés appartiennent à cette entité : changez-les d'entité ou renommez-la":
        "Employees belong to this entity: move them to another entity or rename it",
    "Des employés sont dans ce département : changez-les de département ou renommez-le":
        "Employees are in this department: move them to another department or rename it",
    "Droit requis": "Right required",
    "Durée entre 0 et 1440 minutes": "Duration between 0 and 1440 minutes",
    "Département déjà existant": "Department already exists",
    "Département introuvable": "Department not found",
    "Employé archivé : restaurez-le avant d'émettre un badge": "Archived employee: restore them before issuing a badge",
    "Employé archivé : restaurez-le avant de changer sa photo":
        "Archived employee: restore them before changing their photo",
    "Employé archivé : restaurez-le avant de le modifier": "Archived employee: restore them before editing",
    "Employé archivé : utilisez « Restaurer »": "Archived employee: use “Restore”",
    "Employé déjà archivé": "Employee already archived",
    "Employé introuvable": "Employee not found",
    "Employé ou zone introuvable": "Employee or zone not found",
    "Employé suspendu : réactivez-le avant d'émettre un badge":
        "Suspended employee: reactivate them before issuing a badge",
    "Entité déjà existante": "Entity already exists",
    "Entité introuvable": "Entity not found",
    "Fichier Excel illisible (.xlsx attendu)": "Unreadable Excel file (.xlsx expected)",
    "Fichier vide": "Empty file",
    "Format refusé : JPEG ou PNG uniquement": "Format refused: JPEG or PNG only",
    "Identifiant déjà utilisé": "Username already used",
    "Identifiants invalides": "Invalid username or password",
    "Image illisible : envoyez une photo JPEG ou PNG": "Unreadable image: send a JPEG or PNG photo",
    "Image trop grande": "Image too large",
    "Impossible : c'est le dernier super admin actif": "Not possible: this is the last active super admin",
    "Jours invalides : 1 = lundi … 7 = dimanche": "Invalid days: 1 = Monday … 7 = Sunday",
    "La date d'expiration doit être dans le futur": "The expiry date must be in the future",
    "La date de fin doit être après la date de début": "The end date must be after the start date",
    "La zone n'a aucun point de contrôle pour ce sens": "The zone has no checkpoint for this direction",
    "Le mot de passe doit contenir au moins une lettre et un chiffre":
        "The password must contain at least one letter and one digit",
    "Le mot de passe ne doit pas être l'identifiant": "The password must not be the username",
    "Le nom est obligatoire": "The name is required",
    "Le rôle super admin ne peut pas être modifié": "The super admin role cannot be changed",
    "Matricule déjà utilisé": "Employee number already used",
    "Matricule, nom et prénom sont obligatoires": "Employee number, last name and first name are required",
    "Mot de passe actuel incorrect": "Current password incorrect",
    "Mot de passe modifié : reconnectez-vous": "Password changed: sign in again",
    "Mot de passe trop court : 8 caractères minimum": "Password too short: 8 characters minimum",
    "Mot de passe trop long : 128 caractères maximum": "Password too long: 128 characters maximum",
    "Nom d'unité obligatoire": "Unit name required",
    "Nom de l'agent obligatoire": "Agent name required",
    "Nom de l'appareil obligatoire": "Device name required",
    "Nom de zone obligatoire": "Zone name required",
    "Nom du poste obligatoire": "Post name required",
    "Photo introuvable": "Photo not found",
    "Photo introuvable ou lien expiré": "Photo not found or link expired",
    "Photo trop lourde": "Photo too large",
    "Poste introuvable": "Post not found",
    "Précisez le motif lorsque vous choisissez « Autre »": "Give details when you choose “Other”",
    "QR invalide": "Invalid QR code",
    "Rôle introuvable": "Role not found",
    "Session invalide ou expirée": "Session invalid or expired",
    "Temps de trajet introuvable": "Travel time not found",
    "Un badge vient d'être émis pour cet employé : rechargez la fiche":
        "A badge has just been issued for this employee: reload the file",
    "Un motif est obligatoire": "A reason is required",
    "Unité déjà existante": "Unit already exists",
    "Unité introuvable": "Unit not found",
    "Unité, zone ou poste introuvable": "Unit, zone or post not found",
    "Utilisateur introuvable": "User not found",
    "Utilisez l'action « Archiver », qui demande un motif": "Use the “Archive” action, which asks for a reason",
    "Utilisez « Changer mon mot de passe » pour votre propre compte": "Use “Change my password” for your own account",
    "Vous ne pouvez pas accorder un droit que vous n'avez pas": "You cannot grant a right you do not have",
    "Vous ne pouvez pas modifier vos propres droits": "You cannot change your own rights",
    "Zone déjà existante": "Zone already exists",
    "Zone introuvable": "Zone not found",
    "« Remplacement » est posé automatiquement à la réémission : choisissez un autre motif":
        "“Replacement” is set automatically on reissue: choose another reason",
    "Fichier trop lourd": "File too large",
    "Trop d'employés": "Too many employees",
    "Choisissez des employés, un département ou une entité": "Choose employees, a department or an entity",
    "Choisissez l'entité ou le département à appliquer": "Choose the entity or the department to apply",
    "Choisissez au moins une zone": "Choose at least one zone",
    "Choisissez au moins un filtre (période, employé, département, entité ou zone)":
        "Choose at least one filter (period, employee, department, entity or zone)",
    "Choisissez au moins un filtre (sélection, département, entité ou archivés)":
        "Choose at least one filter (selection, department, entity or archived)",
    "Trop de lignes": "Too many rows",
    # --- import: reasons for a refused row ------------------------------------------------
    "matricule manquant": "employee number missing",
    "nom manquant": "last name missing",
    "prénom manquant": "first name missing",
    "matricule déjà utilisé": "employee number already used",
    "matricule en double dans le fichier": "employee number appears twice in the file",
    "entité inconnue": "unknown entity",
    "département inconnu": "unknown department",
    "matricule trop long": "employee number too long",
    "nom trop long": "last name too long",
    "prénom trop long": "first name too long",
    "fonction trop longue": "job title too long",
    "nom d'entité trop long": "entity name too long",
    "nom de département trop long": "department name too long",
    # --- refusal detail shown with the verdict -------------------------------------
    "Accès pas encore valable": "Access not valid yet",
    "Accès à cette zone expiré": "Access to this zone has expired",
    "Hors des horaires autorisés": "Outside the allowed hours",
}


def request_lang(request: Request) -> str:
    """« en » when the app asks for English first, otherwise « fr »."""
    header = request.headers.get("accept-language", "")
    return "en" if header.strip().lower().startswith("en") else "fr"


_DAYS = {"lun": "Mon", "mar": "Tue", "mer": "Wed", "jeu": "Thu", "ven": "Fri", "sam": "Sat", "dim": "Sun",
         "toute la journée": "all day", "tous les jours": "every day"}
_DAYS_RE = re.compile(r"\b(" + "|".join(sorted(_DAYS, key=len, reverse=True)) + r")\b")


def tr(message: str | None, lang: str) -> str | None:
    """Exact message, or « known message : details » (the time slots of a refusal, for instance)."""
    if message is None or lang != "en":
        return message
    if message in EN:
        return EN[message]
    head, sep, tail = message.partition(" : ")
    if sep and head in EN:
        tail = _DAYS_RE.sub(lambda m: _DAYS[m.group(1)], tail)
        tail = tail.replace(" Mo maximum", " MB maximum").replace(" caractères maximum", " characters maximum")
        return f"{EN[head]}: {tail}"
    return message
