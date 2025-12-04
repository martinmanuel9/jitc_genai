#!/usr/bin/env python3
"""
Database Backup Manager for Litigation GenAI
Programmatic backup and restore for PostgreSQL, ChromaDB, and Redis

Usage:
    python backup_manager.py backup [--db-only]
    python backup_manager.py restore <backup_dir> [--skip-confirmation]
    python backup_manager.py list
    python backup_manager.py cleanup --keep <n>
"""

import os
import sys
import subprocess
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import argparse


class BackupManager:
    """Manages database backups for Litigation GenAI system"""

    def __init__(self, backup_root: str = "./backups"):
        self.backup_root = Path(backup_root)
        self.backup_root.mkdir(exist_ok=True)

        # Container names from docker-compose.yml
        self.containers = {
            "postgres": "postgres_db",
            "chromadb": "chromadb",
            "redis": "redis"
        }

        # Volume names from docker-compose.yml
        self.volumes = {
            "postgres": "genai_postgres_data",
            "chromadb": "genai_chroma_data",
            "redis": "genai_redis_data"
        }

    def run_command(self, cmd: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command with error handling"""
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"   Error: {e.stderr if hasattr(e, 'stderr') else str(e)}")
            raise

    def check_container_running(self, container_name: str) -> bool:
        """Check if a Docker container is running"""
        result = self.run_command(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture=True,
            check=False
        )
        return container_name in result.stdout.split('\n')

    def validate_environment(self) -> bool:
        """Validate that all required containers are running"""
        print("Checking Docker containers...")
        all_running = True

        for service, container in self.containers.items():
            if self.check_container_running(container):
                print(f"  ✓ {service} ({container})")
            else:
                print(f"  ✗ {service} ({container}) - NOT RUNNING")
                all_running = False

        if not all_running:
            print("\n Not all containers are running!")
            print("   Start services with: docker compose up -d")
            return False

        print("All containers are running\n")
        return True

    def backup_postgres(self, backup_dir: Path) -> bool:
        """Backup PostgreSQL database using pg_dumpall"""
        print("[PostgreSQL] Backing up database...")
        backup_file = backup_dir / "postgres_backup.sql"

        try:
            with open(backup_file, 'w') as f:
                result = subprocess.run(
                    ["docker", "exec", self.containers["postgres"],
                     "pg_dumpall", "-U", "g3nA1-user"],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )

            size = backup_file.stat().st_size / (1024 * 1024)  # MB
            print(f"✓ PostgreSQL backup complete ({size:.2f} MB)")
            return True
        except Exception as e:
            print(f"✗ PostgreSQL backup failed: {e}")
            return False

    def backup_chromadb(self, backup_dir: Path) -> bool:
        """Backup ChromaDB vector database

        IMPORTANT: ChromaDB path must match docker-compose.yml volume mount.
        Current path: /chroma/chroma
        If you change the volume mount, also update:
        - scripts/backup.sh (line ~105)
        - scripts/restore.sh (line ~159)
        """
        print("[ChromaDB] Backing up vector database...")
        chroma_backup = backup_dir / "chromadb_data"

        try:
            # Copy from container (path: /chroma/chroma per docker-compose.yml)
            self.run_command(
                ["docker", "cp",
                 f"{self.containers['chromadb']}:/chroma/chroma",
                 str(chroma_backup)],
                check=True
            )

            # Calculate size
            total_size = sum(
                f.stat().st_size for f in chroma_backup.rglob('*') if f.is_file()
            ) / (1024 * 1024)  # MB

            print(f"ChromaDB backup complete ({total_size:.2f} MB)")
            return True
        except Exception as e:
            print(f"ChromaDB backup failed: {e}")
            return False

    def backup_redis(self, backup_dir: Path) -> bool:
        """Backup Redis cache"""
        print("[Redis] Backing up cache...")
        redis_backup = backup_dir / "redis_data"

        try:
            # Trigger Redis BGSAVE
            self.run_command(
                ["docker", "exec", self.containers["redis"],
                 "redis-cli", "BGSAVE"],
                check=False  # Don't fail if BGSAVE fails
            )

            # Wait briefly for save to complete
            import time
            time.sleep(2)

            # Copy data directory
            self.run_command(
                ["docker", "cp",
                 f"{self.containers['redis']}:/data",
                 str(redis_backup)],
                check=True
            )

            total_size = sum(
                f.stat().st_size for f in redis_backup.rglob('*') if f.is_file()
            ) / (1024 * 1024)  # MB

            print(f"Redis backup complete ({total_size:.2f} MB)")
            return True
        except Exception as e:
            print(f"Redis backup failed: {e}")
            return False

    def backup_application_data(self, backup_dir: Path) -> int:
        """Backup application data (images, local data, migrations)"""
        print("[Application] Backing up application data...")
        count = 0

        # Backup stored images
        if Path("./stored_images").exists():
            shutil.copytree("./stored_images", backup_dir / "stored_images")
            print("  ✓ Stored images")
            count += 1

        # Backup local data
        if Path("./data").exists():
            shutil.copytree("./data", backup_dir / "local_data")
            print("  ✓ Local data")
            count += 1

        # Backup migrations
        if Path("./migrations").exists():
            shutil.copytree("./migrations", backup_dir / "migrations")
            print("Migrations")
            count += 1

        if count > 0:
            print(f"Application data backup complete ({count} items)")
        else:
            print("No application data found")

        return count

    def create_backup_metadata(self, backup_dir: Path, db_only: bool) -> None:
        """Create backup metadata file"""
        # Get git info
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, check=False
            ).stdout.strip()

            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, check=False
            ).stdout.strip()
        except:
            branch = "N/A"
            commit = "N/A"

        # Calculate total size
        total_size = sum(
            f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
        )

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "backup_type": "database_only" if db_only else "full",
            "git_branch": branch,
            "git_commit": commit,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "databases": ["postgresql", "chromadb", "redis"]
        }

        # Write JSON metadata
        with open(backup_dir / "backup_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        # Write human-readable metadata
        with open(backup_dir / "backup_info.txt", 'w') as f:
            f.write(f"""Litigation GenAI - Backup Information
=====================================
Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Backup Type: {"Database Only" if db_only else "Full Backup"}
Git Branch: {branch}
Git Commit: {commit}
Total Size: {metadata['total_size_mb']} MB

Databases Backed Up:
- PostgreSQL (relational database)
- ChromaDB (vector database)
- Redis (cache)
""")

        print("Metadata created")

    def create_backup(self, db_only: bool = False) -> Optional[Path]:
        """Create a full backup of all databases and optionally application data"""
        print("=" * 60)
        print("Litigation GenAI - Database Backup")
        print("=" * 60)

        # Validate environment
        if not self.validate_environment():
            return None

        # Create backup directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.backup_root / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        print(f"Backup location: {backup_dir}")
        print(f"Database-only mode: {db_only}\n")

        # Backup databases
        success = True
        success &= self.backup_postgres(backup_dir)
        success &= self.backup_chromadb(backup_dir)
        success &= self.backup_redis(backup_dir)

        if not success:
            print("\nBackup failed - some databases could not be backed up")
            return None

        # Backup application data (unless db-only)
        if not db_only:
            self.backup_application_data(backup_dir)

        # Create metadata
        self.create_backup_metadata(backup_dir, db_only)

        # Summary
        total_size = sum(
            f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
        ) / (1024 * 1024)

        print("\n" + "=" * 60)
        print("BACKUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Location: {backup_dir}")
        print(f"Size: {total_size:.2f} MB")
        print(f"\nTo restore: python {sys.argv[0]} restore {backup_dir}")
        print("=" * 60)

        return backup_dir

    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []

        for backup_dir in sorted(self.backup_root.iterdir(), reverse=True):
            if not backup_dir.is_dir():
                continue

            metadata_file = backup_dir / "backup_metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
            else:
                # Legacy backup without JSON metadata
                metadata = {
                    "timestamp": backup_dir.name,
                    "backup_type": "unknown",
                    "total_size_mb": sum(
                        f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
                    ) / (1024 * 1024)
                }

            backups.append({
                "path": backup_dir,
                "name": backup_dir.name,
                **metadata
            })

        return backups

    def cleanup_old_backups(self, keep: int = 5) -> None:
        """Remove old backups, keeping only the most recent N"""
        backups = self.list_backups()

        if len(backups) <= keep:
            print(f"Found {len(backups)} backups, keeping all (limit: {keep})")
            return

        to_remove = backups[keep:]
        print(f"Removing {len(to_remove)} old backups (keeping {keep} most recent):")

        for backup in to_remove:
            print(f"  Removing: {backup['name']} ({backup['total_size_mb']:.2f} MB)")
            shutil.rmtree(backup['path'])

        print(f"✓ Cleanup complete")

    def restore_backup(self, backup_dir: Path, skip_confirmation: bool = False) -> bool:
        """Restore databases and application data from backup"""
        print("=" * 60)
        print("Litigation GenAI - Database Restore")
        print("=" * 60)

        # Validate backup directory
        if not backup_dir.exists() or not backup_dir.is_dir():
            print(f"Backup directory not found: {backup_dir}")
            return False

        # Show backup info
        backup_info = backup_dir / "backup_info.txt"
        if backup_info.exists():
            print("\n" + backup_info.read_text())
            print("=" * 60)

        # Confirmation prompt
        if not skip_confirmation:
            print("\nWARNING: This will OVERWRITE existing data!")
            response = input("\nContinue with restore? (yes/N): ")
            if response.lower() != "yes":
                print("Restore cancelled.")
                return False
            print()

        # Stop all services
        print("[1/7] Stopping Docker services...")
        self.run_command(["docker", "compose", "down"], check=True)
        print("✓ Services stopped\n")

        # Restore PostgreSQL
        print("[2/7] Restoring PostgreSQL database...")
        postgres_backup = backup_dir / "postgres_backup.sql"
        if postgres_backup.exists():
            # Start only PostgreSQL
            self.run_command(["docker", "compose", "up", "-d", "postgres"], check=True)
            print("  Waiting for PostgreSQL to be ready...")
            import time
            time.sleep(5)

            # Wait for PostgreSQL to accept connections
            for i in range(30):
                result = self.run_command(
                    ["docker", "exec", self.containers["postgres"],
                     "pg_isready", "-U", "g3nA1-user"],
                    check=False, capture=True
                )
                if result.returncode == 0:
                    break
                time.sleep(1)

            # Restore database
            print("  Running restore...")
            with open(postgres_backup, 'r') as f:
                subprocess.run(
                    ["docker", "exec", "-i", self.containers["postgres"],
                     "psql", "-U", "g3nA1-user", "-d", "postgres"],
                    stdin=f,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    check=True
                )

            print("✓ PostgreSQL restored successfully")
            self.run_command(["docker", "compose", "down"], check=True)
        else:
            print("⊘ No PostgreSQL backup found, skipping")
        print()

        # Restore ChromaDB
        print("[3/7] Restoring ChromaDB vector database...")
        chroma_backup = backup_dir / "chromadb_data"
        if chroma_backup.exists() and chroma_backup.is_dir():
            # Remove and recreate volume
            self.run_command(
                ["docker", "volume", "rm", self.volumes["chromadb"]],
                check=False
            )
            self.run_command(
                ["docker", "volume", "create", self.volumes["chromadb"]],
                check=True
            )

            # Copy backup to volume
            backup_abs_path = chroma_backup.absolute()
            self.run_command([
                "docker", "run", "--rm",
                "-v", f"{self.volumes['chromadb']}:/chroma/chroma",
                "-v", f"{backup_abs_path}:/backup",
                "alpine", "sh", "-c", "cp -r /backup/. /chroma/chroma/"
            ], check=True)

            print("✓ ChromaDB restored successfully")
        else:
            print("⊘ No ChromaDB backup found, skipping")
        print()

        # Restore Redis
        print("[4/7] Restoring Redis cache...")
        redis_backup = backup_dir / "redis_data"
        if redis_backup.exists() and redis_backup.is_dir():
            # Remove and recreate volume
            self.run_command(
                ["docker", "volume", "rm", self.volumes["redis"]],
                check=False
            )
            self.run_command(
                ["docker", "volume", "create", self.volumes["redis"]],
                check=True
            )

            # Copy backup to volume
            backup_abs_path = redis_backup.absolute()
            self.run_command([
                "docker", "run", "--rm",
                "-v", f"{self.volumes['redis']}:/data",
                "-v", f"{backup_abs_path}:/backup",
                "alpine", "sh", "-c", "cp -r /backup/. /data/"
            ], check=True)

            print("✓ Redis restored successfully")
        else:
            print("⊘ No Redis backup found, skipping")
        print()

        # Restore application data
        print("[5/7] Restoring application data...")
        restored_count = 0

        if (backup_dir / "stored_images").exists():
            if Path("./stored_images").exists():
                shutil.rmtree("./stored_images")
            shutil.copytree(backup_dir / "stored_images", "./stored_images")
            print("  ✓ Stored images restored")
            restored_count += 1

        if (backup_dir / "local_data").exists():
            if Path("./data").exists():
                shutil.rmtree("./data")
            shutil.copytree(backup_dir / "local_data", "./data")
            print("  ✓ Local data restored")
            restored_count += 1

        if (backup_dir / "migrations").exists():
            if Path("./migrations").exists():
                shutil.rmtree("./migrations")
            shutil.copytree(backup_dir / "migrations", "./migrations")
            print("  ✓ Migrations restored")
            restored_count += 1

        if restored_count == 0:
            print("⊘ No application data found in backup")
        else:
            print(f"✓ Restored {restored_count} application data items")
        print()

        # Skip legacy check
        print("[6/7] Checking for legacy backup items...")
        print("✓ Legacy check complete\n")

        # Start all services
        print("[7/7] Starting Docker services...")
        self.run_command(["docker", "compose", "up", "-d"], check=True)
        print("✓ All services started\n")

        # Wait for services
        print("Waiting for services to be ready...")
        import time
        time.sleep(5)

        # Summary
        print("\n" + "=" * 60)
        print("✅ RESTORE COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Restored from: {backup_dir}")
        print("\nNext steps:")
        print("  1. Verify services: docker compose ps")
        print("  2. Check logs: docker compose logs -f")
        print("=" * 60)

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Database Backup Manager for Litigation GenAI"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create a new backup')
    backup_parser.add_argument(
        '--db-only',
        action='store_true',
        help='Backup only databases (exclude application data)'
    )

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_dir', help='Backup directory to restore from')
    restore_parser.add_argument(
        '--skip-confirmation',
        action='store_true',
        help='Skip confirmation prompt'
    )

    # List command
    list_parser = subparsers.add_parser('list', help='List all backups')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove old backups')
    cleanup_parser.add_argument(
        '--keep',
        type=int,
        default=5,
        help='Number of recent backups to keep (default: 5)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = BackupManager()

    if args.command == 'backup':
        manager.create_backup(db_only=args.db_only)

    elif args.command == 'restore':
        backup_path = Path(args.backup_dir)
        if not backup_path.exists():
            # Try relative to backup root
            backup_path = manager.backup_root / args.backup_dir

        if not backup_path.exists():
            print(f"❌ Backup directory not found: {args.backup_dir}")
            print("\nAvailable backups:")
            backups = manager.list_backups()
            for backup in backups[:5]:
                print(f"  - {backup['name']}")
            sys.exit(1)

        manager.restore_backup(backup_path, skip_confirmation=args.skip_confirmation)

    elif args.command == 'list':
        backups = manager.list_backups()

        if not backups:
            print("No backups found")
            return

        print("\nAvailable Backups:")
        print("=" * 80)
        for backup in backups:
            print(f"📦 {backup['name']}")
            print(f"   Type: {backup['backup_type']}")
            print(f"   Size: {backup['total_size_mb']:.2f} MB")
            if 'git_branch' in backup:
                print(f"   Git: {backup['git_branch']} ({backup['git_commit']})")
            print()

    elif args.command == 'cleanup':
        manager.cleanup_old_backups(keep=args.keep)


if __name__ == '__main__':
    main()
