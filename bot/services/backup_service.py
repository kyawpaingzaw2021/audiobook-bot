"""Daily pg_dump -> gzip -> local disk + admin DM + 7-day retention."""
import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.config import config

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(
    os.getenv("BACKUP_DIR", "/opt/audiobook-bot/data/backups")
)
RETENTION_DAYS = 7
MIN_FREE_MB = 500
TIMEOUT_SEC = 300


async def run_backup(bot: Bot) -> tuple[bool, str]:
    """Dump DB -> gzip -> local disk -> admin DM. Async."""
    try:
        if not shutil.which("pg_dump"):
            return False, "pg_dump မရှိပါ"

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        try:
            _, _, free = shutil.disk_usage(BACKUP_DIR)
            free_mb = free / 1024 / 1024
            if free_mb < MIN_FREE_MB:
                return (
                    False,
                    f"Disk space နည်း ({free_mb:.0f} MB ကျန်)",
                )
        except Exception as e:
            logger.warning(f"Disk check failed: {e}")

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        db_file = BACKUP_DIR / f"audiobook_{ts}.sql.gz"
        tmp_file = BACKUP_DIR / f"audiobook_{ts}.sql.gz.tmp"

        env = os.environ.copy()
        env["PGPASSWORD"] = config.DB_PASSWORD

        cmd = [
            "pg_dump",
            "-h", config.DB_HOST,
            "-p", str(config.DB_PORT),
            "-U", config.DB_USER,
            "-d", config.DB_NAME,
            "--no-owner",
            "--no-acl",
        ]

        stdout, stderr, rc = await _run_pg_dump(cmd, env)

        if rc != 0:
            err = stderr.decode(errors="ignore")[:300]
            logger.error(f"pg_dump failed: {err}")
            return False, f"pg_dump error: {err}"

        if not stdout:
            return False, "pg_dump empty output"

        def _write_gz() -> None:
            with gzip.open(tmp_file, "wb") as f:
                f.write(stdout)

        await asyncio.to_thread(_write_gz)

        if not tmp_file.exists() or tmp_file.stat().st_size == 0:
            tmp_file.unlink(missing_ok=True)
            return False, "Backup empty"

        tmp_file.rename(db_file)
        size_kb = db_file.stat().st_size / 1024
        logger.info(
            f"Backup saved: {db_file.name} ({size_kb:.1f} KB)"
        )

        if config.ADMIN_ID != 0:
            try:
                await bot.send_document(
                    chat_id=config.ADMIN_ID,
                    document=FSInputFile(db_file),
                    caption=(
                        f"<b>Daily Backup</b>\n\n"
                        f"Time: "
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                        f"Size: {size_kb:.1f} KB\n"
                        f"File: <code>{db_file.name}</code>"
                    ),
                )
            except Exception as e:
                logger.warning(f"Admin DM failed: {e}")

        await _cleanup_old_backups(days=RETENTION_DAYS)

        return True, f"OK - {size_kb:.1f} KB"

    except Exception as e:
        logger.exception(f"Backup failed: {e}")
        return False, str(e)


async def _run_pg_dump(
    cmd: list[str], env: dict
) -> tuple[bytes, bytes, int]:
    """Run pg_dump async. Returns (stdout, stderr, returncode)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        logger.exception(f"pg_dump spawn error: {e}")
        return b"", str(e).encode(), 1

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        await proc.wait()
        return b"", f"timeout >{TIMEOUT_SEC}s".encode(), 1

    return stdout or b"", stderr or b"", proc.returncode or 0


async def _cleanup_old_backups(days: int = 7) -> None:
    """Delete backups older than N days."""
    try:
        cutoff = datetime.now().timestamp() - (days * 86400)
        count = 0
        for f in BACKUP_DIR.glob("audiobook_*.sql.gz"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to remove {f.name}: {e}"
                )
        if count:
            logger.info(f"Cleanup: removed {count} old backups")
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")


async def list_backups() -> list[dict]:
    """List all backups with metadata."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(
        BACKUP_DIR.glob("audiobook_*.sql.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            stat = f.stat()
            out.append({
                "name": f.name,
                "size_kb": stat.st_size / 1024,
                "mtime": datetime.fromtimestamp(stat.st_mtime),
            })
        except Exception:
            continue
    return out
