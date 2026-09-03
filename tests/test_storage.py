from datetime import datetime, timezone

from radar import storage
from radar.schemas import CompanyProfile, CrawlSnapshot


def _make_snapshot(domain: str, suffix: str) -> CrawlSnapshot:
    profile = CompanyProfile(domain=domain, extracted_at=datetime.now(timezone.utc))
    return CrawlSnapshot(id=f"{domain}__{suffix}", profile=profile, raw_pages={f"https://{domain}": "hello"})


def test_save_and_get_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "radar.db")
    monkeypatch.setattr(storage, "SNAPSHOTS_DIR", tmp_path / "snapshots")

    snapshot = _make_snapshot("example.com", "001")
    storage.save_snapshot(snapshot)

    latest = storage.get_latest_snapshot("example.com")
    assert latest is not None
    assert latest.id == snapshot.id
    assert latest.raw_pages == snapshot.raw_pages


def test_latest_snapshot_updates_across_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "radar.db")
    monkeypatch.setattr(storage, "SNAPSHOTS_DIR", tmp_path / "snapshots")

    older = _make_snapshot("example.com", "001")
    storage.save_snapshot(older)

    newer = _make_snapshot("example.com", "002")
    storage.save_snapshot(newer)

    assert storage.get_latest_snapshot("example.com").id == newer.id


def test_watchlist_add_list_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "radar.db")
    monkeypatch.setattr(storage, "SNAPSHOTS_DIR", tmp_path / "snapshots")

    storage.add_to_watchlist("owncompany.com", is_own_company=True)
    storage.add_to_watchlist("competitor.com", is_own_company=False)

    rows = {row["domain"]: row for row in storage.list_watchlist()}
    assert rows["owncompany.com"]["is_own_company"] == 1
    assert rows["competitor.com"]["is_own_company"] == 0

    storage.remove_from_watchlist("competitor.com")
    rows = {row["domain"]: row for row in storage.list_watchlist()}
    assert "competitor.com" not in rows
    assert "owncompany.com" in rows
