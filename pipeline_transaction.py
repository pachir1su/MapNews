"""Crash-recoverable publication of MapNews analysis and map outputs.

The two compatibility JSON paths cannot be replaced in one filesystem atomic
operation. A durable journal, backup files and a last-written manifest make a
failed or interrupted publication detectable and recoverable at next startup.

Consumers that require cross-file consistency must validate the manifest.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def _manifest_path(map_path):
    path = Path(map_path)
    return path.with_name(path.name + ".manifest.json")


def _journal_path(map_path):
    path = Path(map_path)
    return path.with_name("." + path.name + ".pending-transaction.json")


@contextmanager
def output_lock(map_path):
    """Cross-process lock. OS releases it even if the process crashes."""
    lock_path = Path(map_path).with_name("." + Path(map_path).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.seek(0)
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("다른 MapNews 실행이 지도 결과를 갱신하고 있습니다.") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("다른 MapNews 실행이 지도 결과를 갱신하고 있습니다.") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write_temp(parent, content):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".mapnews-tx-", suffix=".tmp", dir=parent)
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _backup(path):
    path = Path(path)
    if not path.exists():
        return None
    destination = _write_temp(path.parent, b"")
    try:
        shutil.copyfile(path, destination)
        with destination.open("r+b") as stream:
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def _bytes(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2,
                      allow_nan=False).encode("utf-8")


def _journal_record(analysis_path, map_path, stages, backups, run_id, hashes):
    return {
        "version": 1, "run_id": run_id, "hashes": hashes,
        "analysis": str(analysis_path.resolve()),
        "map": str(map_path.resolve()),
        "stages": [str(s) for s in stages],
        "backups": [str(x) if x else None for x in backups],
    }


def _safe_temp(value, parent):
    if value is None:
        return None
    path = Path(value)
    if (path.parent.resolve() != Path(parent).resolve()
            or not path.name.startswith(".mapnews-tx-")
            or not path.name.endswith(".tmp")):
        raise ValueError("거래 복구 기록의 임시 파일 경로가 유효하지 않습니다.")
    return path


def _cleanup(record, journal):
    for raw in (record["stages"] + record["backups"]):
        if raw:
            path = Path(raw)
            path.unlink(missing_ok=True)
    Path(journal).unlink(missing_ok=True)


def _matching_snapshot(record, map_path):
    manifest = _manifest_path(map_path)
    if not manifest.exists():
        return False
    try:
        info = json.loads(manifest.read_text(encoding="utf-8"))
        if info.get("run_id") != record["run_id"]:
            return False
        for label in ("analysis", "map"):
            path = Path(record[label])
            if sha256(path.read_bytes()).hexdigest() != record["hashes"][label]:
                return False
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return True


def recover_pair(analysis_path, map_path):
    """Restore the last complete generation after an interrupted publication.

    Invoke while holding output_lock(), before loading previous output files.
    """
    analysis_path, map_path = Path(analysis_path), Path(map_path)
    journal = _journal_path(map_path)
    if not journal.exists():
        return False
    record = json.loads(journal.read_text(encoding="utf-8"))
    if (record.get("version") != 1
            or record.get("analysis") != str(analysis_path.resolve())
            or record.get("map") != str(map_path.resolve())
            or len(record.get("stages", [])) != 2
            or len(record.get("backups", [])) != 2):
        raise ValueError("거래 기록의 대상 파일이 일치하지 않아 복구를 중단합니다.")
    for key, target in (("analysis", analysis_path), ("map", map_path)):
        index = 0 if key == "analysis" else 1
        _safe_temp(record["stages"][index], target.parent)
        _safe_temp(record["backups"][index], target.parent)
    if _matching_snapshot(record, map_path):
        _cleanup(record, journal)  # Fully committed before interruption.
        return False
    # Roll back both output paths, rather than letting a half-written pair
    # masquerade as a successful single run.
    for index, target in enumerate((analysis_path, map_path)):
        backup = record["backups"][index]
        if backup:
            original = Path(backup)
            if not original.is_file():
                raise RuntimeError("이전 정상 결과의 백업이 없어 자동 복구할 수 없습니다.")
            os.replace(original, target)
        else:
            target.unlink(missing_ok=True)
    _cleanup(record, journal)
    return True


def publish_pair(analysis_path, analysis, map_path, mapped):
    """Publish the two output files and commit a shared checksummed manifest.

    If a normal write fails, restore both previous files. If the process dies
    during the transaction, recover_pair() completes or reverses it next run.
    """
    analysis_path, map_path = Path(analysis_path), Path(map_path)
    if analysis_path.resolve() == map_path.resolve():
        raise ValueError("분석·지도 출력 경로가 같습니다.")
    if not analysis or not mapped:
        raise ValueError("비어 있는 뉴스 결과는 게시하지 않습니다.")
    if (len(analysis) != len(mapped)
            or [row.get("id") for row in analysis] != [row.get("id") for row in mapped]):
        raise ValueError("분석·지도 파일의 기사 ID와 순서가 일치하지 않습니다.")
    if _journal_path(map_path).exists():
        raise RuntimeError("미완료 파일 거래가 있습니다. 먼저 recover_pair()를 실행해야 합니다.")

    data = (_bytes(analysis), _bytes(mapped))
    run_id = uuid.uuid4().hex
    hashes = {
        "analysis": sha256(data[0]).hexdigest(),
        "map": sha256(data[1]).hexdigest(),
    }
    manifest_payload = {
        "version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "analysis_path": str(analysis_path.resolve()),
        "map_path": str(map_path.resolve()),
        "article_count": len(mapped),
        "sha256": hashes,
    }
    stages = []
    backups = []
    journal = _journal_path(map_path)
    manifest_tmp = None
    published_journal = False
    committed = False
    try:
        stages = [
            _write_temp(analysis_path.parent, data[0]),
            _write_temp(map_path.parent, data[1]),
        ]
        backups = [_backup(analysis_path), _backup(map_path)]
        record = _journal_record(analysis_path, map_path, stages, backups,
                                 run_id, hashes)
        manifest_tmp = _write_temp(map_path.parent, _bytes(manifest_payload))
        journal_tmp = _write_temp(map_path.parent, _bytes(record))
        try:
            os.replace(journal_tmp, journal)
            published_journal = True
        finally:
            journal_tmp.unlink(missing_ok=True)
        # Keep the order stable; the manifest is the final commit marker.
        os.replace(stages[1], map_path)
        os.replace(stages[0], analysis_path)
        os.replace(manifest_tmp, _manifest_path(map_path))
        committed = True
    except BaseException:
        if published_journal:
            recover_pair(analysis_path, map_path)
        raise
    finally:
        if not published_journal:
            for path in stages + backups:
                if path:
                    path.unlink(missing_ok=True)
        if manifest_tmp:
            manifest_tmp.unlink(missing_ok=True)
    if committed:
        _cleanup(record, journal)
    return manifest_payload


def verify_pair(analysis_path, map_path):
    """Check shared commit marker; do not silently trust mismatched file ages."""
    manifest = _manifest_path(map_path)
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if (data.get("analysis_path") != str(Path(analysis_path).resolve())
                or data.get("map_path") != str(Path(map_path).resolve())):
            return False
        expected = data["sha256"]
        return (sha256(Path(analysis_path).read_bytes()).hexdigest() ==
                expected["analysis"]
                and sha256(Path(map_path).read_bytes()).hexdigest() ==
                expected["map"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
