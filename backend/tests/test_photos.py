"""Employee photos: normalisation, signed short-lived URLs, display at the gate (tâches 5 et 6)."""
from io import BytesIO

from PIL import Image


def image_bytes(fmt="JPEG", size=(1200, 900), exif=False, color=(180, 40, 60)) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", size, color)
    kwargs = {}
    if exif:
        data = Image.Exif()
        data[0x0110] = "Pixel 8"  # camera model
        data[0x0112] = 6  # orientation: rotate 90°
        kwargs["exif"] = data
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def upload(client, headers, employee_id, content, name="photo.jpg", mime="image/jpeg"):
    return client.post(f"/api/employees/{employee_id}/photo", headers=headers,
                       files={"file": (name, content, mime)})


def test_upload_normalises_to_a_clean_portrait(client, admin, world, app):
    employee_id = world["employee"]["id"]
    response = upload(client, admin, employee_id, image_bytes(exif=True))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_photo"] is True and body["photo_url"].startswith(f"/api/photos/{employee_id}?")

    photo = client.get(body["photo_url"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(photo.content)) as stored:
        assert stored.size == (600, 800)  # 3:4 portrait
        assert dict(stored.getexif()) == {}  # no metadata kept (model, orientation, location...)
    assert any(a["action"] == "employee.photo" for a in client.get("/api/audit", headers=admin).json())


def test_png_with_transparency_is_accepted(client, admin, world):
    buffer = BytesIO()
    Image.new("RGBA", (500, 500), (0, 0, 0, 0)).save(buffer, format="PNG")
    assert upload(client, admin, world["employee"]["id"], buffer.getvalue(), "p.png", "image/png").status_code == 200


def test_upload_rejects_wrong_files(client, admin, world):
    employee_id = world["employee"]["id"]
    assert upload(client, admin, employee_id, b"not an image").status_code == 400
    assert upload(client, admin, employee_id, image_bytes(fmt="GIF"), "p.gif", "image/gif").status_code == 400
    too_big = b"\xff\xd8" + b"0" * (2 * 1024 * 1024 + 10)
    response = upload(client, admin, employee_id, too_big)
    assert response.status_code == 400 and "2 Mo" in response.json()["detail"]


def test_upload_needs_the_edit_right(client, agent, world):
    assert upload(client, agent, world["employee"]["id"], image_bytes()).status_code == 403


def test_signed_url_expires_and_cannot_be_forged(client, admin, world, clock):
    url = upload(client, admin, world["employee"]["id"], image_bytes()).json()["photo_url"]
    assert client.get(url.replace("sig=", "sig=0")).status_code == 404
    assert client.get(url.split("&sig=")[0]).status_code == 422  # signature missing
    clock.advance(seconds=61)
    assert client.get(url).status_code == 404  # 60 s only


def test_replacing_the_photo_kills_old_urls_and_file(client, admin, world, app, tmp_path):
    employee_id = world["employee"]["id"]
    first = upload(client, admin, employee_id, image_bytes(color=(10, 10, 10))).json()["photo_url"]
    second = upload(client, admin, employee_id, image_bytes(color=(250, 250, 250))).json()["photo_url"]
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200
    assert len(list((tmp_path / "photos").iterdir())) == 1


def test_remove_photo(client, admin, world, tmp_path):
    employee_id = world["employee"]["id"]
    url = upload(client, admin, employee_id, image_bytes()).json()["photo_url"]
    removed = client.delete(f"/api/employees/{employee_id}/photo", headers=admin)
    assert removed.status_code == 200 and removed.json()["has_photo"] is False
    assert client.get(url).status_code == 404
    assert list((tmp_path / "photos").iterdir()) == []
    assert client.delete(f"/api/employees/{employee_id}/photo", headers=admin).status_code == 404


def test_scan_shows_photo_department_or_photo_absent(client, agent, admin, world):
    body = {"checkpoint_id": world["entry"]["id"], "token": world["token"]}
    without = client.post("/api/scan", headers=agent, json=body).json()
    assert without["employee"]["has_photo"] is False and without["employee"]["photo_url"] is None

    upload(client, admin, world["employee"]["id"], image_bytes())
    client.post("/api/scan", headers=agent, json={"checkpoint_id": world["exit"]["id"], "token": world["token"]})
    with_photo = client.post("/api/scan", headers=agent, json=body).json()
    assert with_photo["verdict"] == "AUTORISE"
    assert client.get(with_photo["employee"]["photo_url"]).status_code == 200
    assert "department_name" in with_photo["employee"]


def test_paired_phone_gets_the_photo(client, admin, world):
    code = client.post("/api/devices", headers=admin, json={"name": "Tel 1"}).json()["code"]
    device = {"X-Device-Token": client.post("/api/device/pair", json={"code": code}).json()["device_token"]}
    upload(client, admin, world["employee"]["id"], image_bytes())
    result = client.post("/api/device/scan", headers=device,
                         json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}).json()
    assert client.get(result["employee"]["photo_url"]).status_code == 200


def test_no_photo_for_unrecognised_qr_and_archived(client, agent, admin, world):
    upload(client, admin, world["employee"]["id"], image_bytes())
    client.post(f"/api/employees/{world['employee']['id']}/archive", headers=admin, json={"reason": "Départ"})
    result = client.post("/api/scan", headers=agent,
                         json={"checkpoint_id": world["entry"]["id"], "token": world["token"]}).json()
    assert result["verdict"] == "REFUSE_INVALIDE" and result["employee"] is None
    assert upload(client, admin, world["employee"]["id"], image_bytes()).status_code == 400
