"""Demo data in one command (development / demo only, never production).

    cd backend && python scripts/seed_demo.py            # uses BHH_DATABASE_URL (.env)
    cd backend && python scripts/seed_demo.py --force    # even if the base already has employees

Creates 2 units (Usine de Bonabéri: Atelier "Sortie obligatoire" + Magasin "Signalé";
Siège Akwa: Bureaux "Libre"), their posts, 6 fictitious employees with photos and badges
(QR images in backend/demo-badges/), 3 agents (one holding the entry and the exit of the
single Magasin door), a demo phone (pairing code printed), the accounts rh1 and superuser1
(password Demo-2026!, no forced change) and a morning of passages so the dashboard is alive.
"""
import argparse
import sys
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controllers import deps  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.domain.enums import AntiPassbackMode, Direction, ZoneSensitivity  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Employee, Role, User  # noqa: E402
from app.repositories import repositories as r  # noqa: E402
from app.services.audit_service import AuditService  # noqa: E402
from app.services.device_service import DeviceService  # noqa: E402
from app.services.import_service import ImportResult  # noqa: E402
from app.services.photo_service import PhotoService  # noqa: E402
from app.services.scan_service import ScanSource  # noqa: E402

DEMO_PASSWORD = "Demo-2026!"
EMPLOYEES = [  # matricule, last name, first name, job, entity, department, colour
    ("EMP-0042", "Ngono", "Paul", "Soudeur", "BHH Industrie", "Production", (122, 31, 52)),
    ("EMP-0007", "Bella", "Awa", "Magasinière", "BHH Industrie", "Logistique", (29, 122, 70)),
    ("EMP-0101", "Etoa", "Jean", "Chef d'atelier", "BHH Industrie", "Production", (56, 89, 107)),
    ("EMP-0230", "Mbarga", "Clarisse", "Comptable", "BHH Holding", "Finances", (163, 107, 0)),
    ("EMP-0311", "Fotso", "Hervé", "Juriste", "BHH Holding", "Juridique", (61, 17, 32)),
    ("EMP-0404", "Ndi", "Marie", "Assistante RH", "BHH Holding", "Ressources humaines", (90, 60, 150)),
]


class MovableClock:
    """Lets the demo write passages at different hours of the morning."""

    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def portrait(initials: str, colour: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (600, 800), colour)
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 140, 450, 440), fill=(255, 255, 255, 60), outline=(255, 255, 255), width=6)
    draw.rounded_rectangle((90, 500, 510, 800), radius=120, fill=(255, 255, 255))
    try:
        font = ImageFont.load_default(size=150)
    except TypeError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), initials, font=font)
    draw.text((300 - (box[2] - box[0]) / 2, 290 - (box[3] - box[1]) / 2 - box[1]), initials, fill=colour, font=font)
    out = BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="seed even if employees already exist")
    args = parser.parse_args()

    settings = get_settings()
    app = create_app(settings)
    factory = app.state.session_factory
    with factory() as session:
        if session.query(Employee).count() and not args.force:
            sys.exit("La base contient déjà des employés : rien n'a été fait (utilisez --force pour une base de démo).")

        real_clock = app.state.clock
        now = real_clock.now()
        clock = MovableClock(now)
        audit = AuditService(r.AuditRepository(session), clock, "seed-demo", r.UserRepository(session))
        admin = session.query(User).filter_by(username=settings.initial_admin_username).one()

        # --- accounts --------------------------------------------------------------
        for username, role_name, full_name in (("rh1", "rh", "Responsable RH (démo)"),
                                               ("superuser1", "super_user", "Super user (démo)")):
            if session.query(User).filter_by(username=username).first() is None:
                role = session.query(Role).filter_by(name=role_name).one()
                session.add(User(username=username, full_name=full_name, role_id=role.id,
                                 password_hash=hash_password(DEMO_PASSWORD), must_change_password=False))

        # --- units, zones, posts ---------------------------------------------------
        zones = deps.get_zone_service(session, audit, clock)
        usine = zones.create_unit(admin.id, "Usine de Bonabéri")
        siege = zones.create_unit(admin.id, "Siège Akwa")
        atelier = zones.create_zone(admin.id, "Atelier", AntiPassbackMode.STRICT, usine.id, code="AT-01",
                                    sensitivity=ZoneSensitivity.RESTRICTED, description="Ateliers de production")
        magasin = zones.create_zone(admin.id, "Magasin", AntiPassbackMode.SOFT, usine.id, code="MG-01")
        bureaux = zones.create_zone(admin.id, "Bureaux", AntiPassbackMode.DISABLED, siege.id, code="BU-01")
        serveurs = zones.create_zone(admin.id, "Salle serveurs", AntiPassbackMode.STRICT, siege.id, code="DC-01",
                                     sensitivity=ZoneSensitivity.CRITICAL)
        posts = {
            "atelier_in": zones.add_checkpoint(admin.id, atelier.id, "Portail atelier", Direction.ENTRY),
            "atelier_out": zones.add_checkpoint(admin.id, atelier.id, "Sortie atelier", Direction.EXIT),
            "magasin_in": zones.add_checkpoint(admin.id, magasin.id, "Porte magasin", Direction.ENTRY),
            "magasin_out": zones.add_checkpoint(admin.id, magasin.id, "Porte magasin (sortie)", Direction.EXIT),
            "bureaux_in": zones.add_checkpoint(admin.id, bureaux.id, "Accueil", Direction.ENTRY),
            "bureaux_out": zones.add_checkpoint(admin.id, bureaux.id, "Sortie accueil", Direction.EXIT),
            "dc_in": zones.add_checkpoint(admin.id, serveurs.id, "Porte salle serveurs", Direction.ENTRY),
        }

        # --- employees, photos, badges, access ----------------------------------------
        employees_service = deps.get_employee_service(session, audit, clock)
        imports = deps.get_import_service(session, audit)
        photos = PhotoService(r.EmployeeRepository(session), audit, settings.photos_dir, settings.photo_max_bytes)
        badges = deps.get_badge_service(session, app.state.signer, audit, clock)
        badge_dir = Path("demo-badges")
        badge_dir.mkdir(exist_ok=True)
        people, tokens = {}, {}
        for matricule, last, first, job, entity, department, colour in EMPLOYEES:
            # Same rules as the Excel import: entities and departments are created on the fly.
            entity_id, department_id = imports._resolve_org({"entity": entity, "department": department},
                                                            ImportResult())
            employee = employees_service.create(admin.id, matricule=matricule, last_name=last, first_name=first,
                                                job_title=job, entity_id=entity_id, department_id=department_id,
                                                extra={})
            if matricule != "EMP-0404":  # one person without photo: shows "Photo absente"
                photos.upload(admin.id, employee.id, portrait(first[0] + last[0], colour))
            badge = badges.issue(admin.id, employee.id, None)
            tokens[matricule] = badges.qr_token(badge.id)
            (badge_dir / f"{matricule}.png").write_bytes(app.state.qr_renderer.render(tokens[matricule], matricule))
            people[matricule] = employee
        access = {
            "EMP-0042": [atelier, magasin], "EMP-0007": [magasin], "EMP-0101": [atelier, magasin, bureaux],
            "EMP-0230": [bureaux], "EMP-0311": [bureaux, serveurs], "EMP-0404": [bureaux],
        }
        for matricule, granted in access.items():
            zones.set_employee_access(admin.id, people[matricule].id, [z.id for z in granted])

        # --- agents at their posts --------------------------------------------------
        agents = deps.get_agent_service(session, audit, clock)
        roger = agents.create(admin.id, "Roger Tchoua", "AG-01")
        sylvie = agents.create(admin.id, "Sylvie Owona", "AG-02")
        agents.create(admin.id, "Bertrand Kamga", "AG-03")
        agents.assign(admin.id, posts["atelier_in"].id, roger.id)
        agents.assign(admin.id, posts["magasin_in"].id, sylvie.id)
        agents.assign(admin.id, posts["magasin_out"].id, sylvie.id, keep_other_posts=True)  # single door

        # --- demo phone -------------------------------------------------------------
        devices = DeviceService(r.DeviceRepository(session), audit, clock, app.state.pairing_limiter,
                                r.AccessLogRepository(session))
        _, code = devices.create(admin.id, "Téléphone de démo")

        # --- a morning of passages --------------------------------------------------
        scans = deps.get_scan_service(session, app.state.signer, app.state.engine, clock, SimpleNamespace(app=app))
        source = ScanSource(operator_id=admin.id)
        start = now - timedelta(hours=3)
        timeline = [
            (0, "atelier_in", "EMP-0042"), (4, "atelier_in", "EMP-0101"), (9, "magasin_in", "EMP-0007"),
            (15, "bureaux_in", "EMP-0230"), (21, "bureaux_in", "EMP-0311"), (26, "bureaux_in", "EMP-0404"),
            (40, "magasin_in", "EMP-0042"), (55, "magasin_out", "EMP-0042"), (70, "atelier_in", "EMP-0042"),
            (85, "dc_in", "EMP-0230"), (95, "dc_in", "EMP-0311"), (110, "bureaux_out", "EMP-0404"),
            (125, "magasin_in", "EMP-0007"), (140, "atelier_out", "EMP-0101"), (150, "bureaux_in", "EMP-0101"),
        ]
        for minutes, post, matricule in timeline:
            clock.current = start + timedelta(minutes=minutes)
            scans.scan_qr(source, posts[post].id, tokens[matricule])
        clock.current = start + timedelta(minutes=160)
        scans.scan_qr(source, posts["atelier_in"].id, "un-qr-qui-ne-vient-pas-de-chez-nous")
        session.commit()

    print("Démo prête.")
    print(f"  Comptes : rh1 / superuser1, mot de passe {DEMO_PASSWORD}")
    print(f"  Badges  : {badge_dir.resolve()}")
    print(f"  Code d'appairage du téléphone de démo (15 min) : {code}")


if __name__ == "__main__":
    main()
