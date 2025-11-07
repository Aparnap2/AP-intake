#!/usr/bin/env python3
"""
Storage management utility for the AP Intake system.

This script provides tools for managing and monitoring the local storage,
including cleanup, statistics, and maintenance operations.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.db.session import AsyncSessionLocal, SessionLocal
from app.models.storage_audit import FileDeduplication, StorageAudit
from app.services.local_storage_service import LocalStorageService


class StorageManager:
    """Storage management utility class."""

    def __init__(self):
        """Initialize the storage manager."""
        self.storage_service = LocalStorageService()
        self.storage_path = Path(settings.STORAGE_PATH)

    async def get_storage_stats(self) -> Dict:
        """Get comprehensive storage statistics."""
        stats = {
            "storage_path": str(self.storage_path),
            "total_files": 0,
            "total_size": 0,
            "compressed_files": 0,
            "compressed_size_saved": 0,
            "deduplicated_files": 0,
            "unique_files": 0,
            "by_type": {},
            "by_organization": {},
            "archive_size": 0,
            "temp_size": 0,
        }

        try:
            # Get database statistics
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, func

                # Count unique files (deduplication records)
                result = await session.execute(
                    select(func.count(FileDeduplication.id))
                )
                stats["unique_files"] = result.scalar() or 0

                # Get total reference count
                result = await session.execute(
                    select(func.sum(FileDeduplication.reference_count))
                )
                total_references = result.scalar() or 0
                stats["deduplicated_files"] = total_references - stats["unique_files"]

                # Get compression statistics
                result = await session.execute(
                    select(
                        func.count(FileDeduplication.id),
                        func.sum(FileDeduplication.original_size),
                        func.sum(FileDeduplication.compressed_size)
                    ).where(FileDeduplication.is_compressed == True)
                )
                compressed_count, original_total, compressed_total = result.first() or (0, 0, 0)
                stats["compressed_files"] = compressed_count or 0
                if original_total and compressed_total:
                    stats["compressed_size_saved"] = original_total - compressed_total

            # Walk through storage directories
            for file_path in self.storage_path.rglob("*"):
                if file_path.is_file():
                    stats["total_files"] += 1
                    size = file_path.stat().st_size
                    stats["total_size"] += size

                    # Categorize by directory
                    relative_path = file_path.relative_to(self.storage_path)
                    parts = str(relative_path).split("/")

                    if len(parts) >= 2:
                        category = parts[0]
                        if category == "by_type":
                            file_type = parts[1] if len(parts) > 1 else "unknown"
                            stats["by_type"][file_type] = stats["by_type"].get(file_type, 0) + size
                        elif category == "by_vendor":
                            vendor = parts[1] if len(parts) > 1 else "unknown"
                            stats["by_organization"][vendor] = stats["by_organization"].get(vendor, 0) + size
                        elif category == "by_date":
                            date_key = f"{parts[1]}/{parts[2]}" if len(parts) > 2 else "unknown"
                            stats["by_organization"][f"date:{date_key}"] = (
                                stats["by_organization"].get(f"date:{date_key}", 0) + size
                            )
                        elif category == "archive":
                            stats["archive_size"] += size
                        elif category == "temp":
                            stats["temp_size"] += size

            # Convert sizes to human readable format
            stats["total_size_mb"] = round(stats["total_size"] / (1024 * 1024), 2)
            stats["compressed_size_saved_mb"] = round(stats["compressed_size_saved"] / (1024 * 1024), 2)
            stats["archive_size_mb"] = round(stats["archive_size"] / (1024 * 1024), 2)
            stats["temp_size_mb"] = round(stats["temp_size"] / (1024 * 1024), 2)

            # Convert by_type and by_organization to MB
            for key in stats["by_type"]:
                stats["by_type"][key] = round(stats["by_type"][key] / (1024 * 1024), 2)
            for key in stats["by_organization"]:
                stats["by_organization"][key] = round(stats["by_organization"][key] / (1024 * 1024), 2)

        except Exception as e:
            print(f"Error getting storage stats: {e}")

        return stats

    async def cleanup_temp_files(self, max_age_hours: int = 24) -> Dict:
        """Clean up temporary files older than max_age_hours."""
        cleanup_stats = {
            "files_deleted": 0,
            "space_freed": 0,
            "errors": []
        }

        try:
            temp_dir = self.storage_path / "temp"
            if not temp_dir.exists():
                return cleanup_stats

            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            for temp_file in temp_dir.rglob("*"):
                if temp_file.is_file():
                    try:
                        file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            size = temp_file.stat().st_size
                            temp_file.unlink()
                            cleanup_stats["files_deleted"] += 1
                            cleanup_stats["space_freed"] += size
                    except Exception as e:
                        cleanup_stats["errors"].append(f"Error deleting {temp_file}: {e}")

            cleanup_stats["space_freed_mb"] = round(cleanup_stats["space_freed"] / (1024 * 1024), 2)

        except Exception as e:
            cleanup_stats["errors"].append(f"Error during cleanup: {e}")

        return cleanup_stats

    async def cleanup_audit_logs(self, max_age_days: int = 90) -> Dict:
        """Clean up old audit logs."""
        cleanup_stats = {
            "records_deleted": 0,
            "errors": []
        }

        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import delete

                cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

                # Delete old audit records
                stmt = delete(StorageAudit).where(StorageAudit.created_at < cutoff_date)
                result = await session.execute(stmt)
                cleanup_stats["records_deleted"] = result.rowcount
                await session.commit()

        except Exception as e:
            cleanup_stats["errors"].append(f"Error cleaning audit logs: {e}")

        return cleanup_stats

    async def find_orphaned_files(self) -> List[Dict]:
        """Find files that exist on disk but not in database."""
        orphaned_files = []

        try:
            # Get all files in storage
            all_files = set()
            for file_path in self.storage_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(self.storage_path))
                    all_files.add(relative_path)

            # Get all files from database
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(select(FileDeduplication.stored_path))
                db_files = {row[0] for row in result.fetchall()}

                # Find orphaned files (in filesystem but not in database)
                orphaned_paths = all_files - db_files

                for orphaned_path in orphaned_paths:
                    full_path = self.storage_path / orphaned_path
                    if full_path.exists():
                        orphaned_files.append({
                            "path": orphaned_path,
                            "size": full_path.stat().st_size,
                            "modified": datetime.fromtimestamp(full_path.stat().st_mtime)
                        })

        except Exception as e:
            print(f"Error finding orphaned files: {e}")

        return orphaned_files

    async def get_access_report(self, days: int = 30) -> Dict:
        """Generate access report for the last N days."""
        report = {
            "period_days": days,
            "total_operations": 0,
            "operations_by_type": {},
            "operations_by_status": {},
            "top_users": {},
            "top_files": {},
            "errors": []
        }

        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, func

                cutoff_date = datetime.utcnow() - timedelta(days=days)

                # Total operations
                result = await session.execute(
                    select(func.count(StorageAudit.id))
                    .where(StorageAudit.created_at >= cutoff_date)
                )
                report["total_operations"] = result.scalar() or 0

                # Operations by type
                result = await session.execute(
                    select(StorageAudit.operation, func.count(StorageAudit.id))
                    .where(StorageAudit.created_at >= cutoff_date)
                    .group_by(StorageAudit.operation)
                )
                report["operations_by_type"] = dict(result.fetchall())

                # Operations by status
                result = await session.execute(
                    select(StorageAudit.operation_status, func.count(StorageAudit.id))
                    .where(StorageAudit.created_at >= cutoff_date)
                    .group_by(StorageAudit.operation_status)
                )
                report["operations_by_status"] = dict(result.fetchall())

                # Top users
                result = await session.execute(
                    select(StorageAudit.user_id, func.count(StorageAudit.id))
                    .where(StorageAudit.created_at >= cutoff_date)
                    .where(StorageAudit.user_id.isnot(None))
                    .group_by(StorageAudit.user_id)
                    .order_by(func.count(StorageAudit.id).desc())
                    .limit(10)
                )
                report["top_users"] = dict(result.fetchall())

                # Top accessed files
                result = await session.execute(
                    select(StorageAudit.file_path, func.count(StorageAudit.id))
                    .where(StorageAudit.created_at >= cutoff_date)
                    .group_by(StorageAudit.file_path)
                    .order_by(func.count(StorageAudit.id).desc())
                    .limit(10)
                )
                report["top_files"] = dict(result.fetchall())

                # Recent errors
                result = await session.execute(
                    select(StorageAudit.operation, StorageAudit.error_message, StorageAudit.created_at)
                    .where(StorageAudit.created_at >= cutoff_date)
                    .where(StorageAudit.operation_status == "failure")
                    .where(StorageAudit.error_message.isnot(None))
                    .order_by(StorageAudit.created_at.desc())
                    .limit(20)
                )
                report["errors"] = [
                    {
                        "operation": row[0],
                        "error": row[1],
                        "timestamp": row[2].isoformat()
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            print(f"Error generating access report: {e}")

        return report

    async def optimize_storage(self) -> Dict:
        """Run storage optimization operations."""
        optimization_results = {
            "temp_cleanup": {},
            "audit_cleanup": {},
            "orphaned_files_found": 0,
            "errors": []
        }

        try:
            # Clean up temporary files
            optimization_results["temp_cleanup"] = await self.cleanup_temp_files()

            # Clean up old audit logs
            optimization_results["audit_cleanup"] = await self.cleanup_audit_logs()

            # Find orphaned files
            orphaned_files = await self.find_orphaned_files()
            optimization_results["orphaned_files_found"] = len(orphaned_files)

            if orphaned_files:
                print(f"Found {len(orphaned_files)} orphaned files:")
                for orphaned in orphaned_files[:10]:  # Show first 10
                    print(f"  - {orphaned['path']} ({orphaned['size']} bytes)")

        except Exception as e:
            optimization_results["errors"].append(str(e))

        return optimization_results


async def main():
    """Main function for the storage manager CLI."""
    parser = argparse.ArgumentParser(description="Storage Management Utility")
    parser.add_argument("command", choices=[
        "stats", "cleanup-temp", "cleanup-audit", "find-orphans", "access-report", "optimize"
    ], help="Command to execute")
    parser.add_argument("--max-age-hours", type=int, default=24,
                       help="Maximum age in hours for temp file cleanup")
    parser.add_argument("--max-age-days", type=int, default=90,
                       help="Maximum age in days for audit log cleanup")
    parser.add_argument("--report-days", type=int, default=30,
                       help="Number of days for access report")
    parser.add_argument("--format", choices=["json", "table"], default="table",
                       help="Output format")

    args = parser.parse_args()

    manager = StorageManager()

    if args.command == "stats":
        stats = await manager.get_storage_stats()
        if args.format == "json":
            print(json.dumps(stats, indent=2))
        else:
            print("Storage Statistics")
            print("=" * 50)
            print(f"Storage Path: {stats['storage_path']}")
            print(f"Total Files: {stats['total_files']}")
            print(f"Total Size: {stats['total_size_mb']} MB")
            print(f"Unique Files: {stats['unique_files']}")
            print(f"Deduplicated Files: {stats['deduplicated_files']}")
            print(f"Compressed Files: {stats['compressed_files']}")
            print(f"Space Saved by Compression: {stats['compressed_size_saved_mb']} MB")
            print(f"Archive Size: {stats['archive_size_mb']} MB")
            print(f"Temp Size: {stats['temp_size_mb']} MB")

            if stats["by_type"]:
                print("\nBy File Type:")
                for file_type, size_mb in stats["by_type"].items():
                    print(f"  {file_type}: {size_mb} MB")

            if stats["by_organization"]:
                print("\nBy Organization:")
                for org, size_mb in stats["by_organization"].items():
                    print(f"  {org}: {size_mb} MB")

    elif args.command == "cleanup-temp":
        result = await manager.cleanup_temp_files(args.max_age_hours)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print("Temporary File Cleanup")
            print("=" * 30)
            print(f"Files Deleted: {result['files_deleted']}")
            print(f"Space Freed: {result['space_freed_mb']} MB")
            if result["errors"]:
                print("Errors:")
                for error in result["errors"]:
                    print(f"  - {error}")

    elif args.command == "cleanup-audit":
        result = await manager.cleanup_audit_logs(args.max_age_days)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print("Audit Log Cleanup")
            print("=" * 25)
            print(f"Records Deleted: {result['records_deleted']}")
            if result["errors"]:
                print("Errors:")
                for error in result["errors"]:
                    print(f"  - {error}")

    elif args.command == "find-orphans":
        orphaned = await manager.find_orphaned_files()
        if args.format == "json":
            print(json.dumps(orphaned, indent=2))
        else:
            print("Orphaned Files")
            print("=" * 20)
            if orphaned:
                print(f"Found {len(orphaned)} orphaned files:")
                for orphaned_file in orphaned:
                    print(f"  - {orphaned_file['path']} ({orphaned_file['size']} bytes, {orphaned_file['modified']})")
            else:
                print("No orphaned files found.")

    elif args.command == "access-report":
        report = await manager.get_access_report(args.report_days)
        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"Access Report (Last {report['period_days']} days)")
            print("=" * 50)
            print(f"Total Operations: {report['total_operations']}")

            print("\nOperations by Type:")
            for op_type, count in report["operations_by_type"].items():
                print(f"  {op_type}: {count}")

            print("\nOperations by Status:")
            for status, count in report["operations_by_status"].items():
                print(f"  {status}: {count}")

            if report["top_users"]:
                print("\nTop Users:")
                for user, count in report["top_users"].items():
                    print(f"  {user}: {count}")

            if report["top_files"]:
                print("\nTop Accessed Files:")
                for file_path, count in report["top_files"].items():
                    print(f"  {file_path}: {count}")

            if report["errors"]:
                print("\nRecent Errors:")
                for error in report["errors"][:10]:
                    print(f"  {error['timestamp']}: {error['operation']} - {error['error']}")

    elif args.command == "optimize":
        results = await manager.optimize_storage()
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print("Storage Optimization Results")
            print("=" * 35)
            print("Temporary File Cleanup:")
            print(f"  Files Deleted: {results['temp_cleanup'].get('files_deleted', 0)}")
            print(f"  Space Freed: {results['temp_cleanup'].get('space_freed_mb', 0)} MB")

            print("\nAudit Log Cleanup:")
            print(f"  Records Deleted: {results['audit_cleanup'].get('records_deleted', 0)}")

            print(f"\nOrphaned Files Found: {results['orphaned_files_found']}")

            if results["errors"]:
                print("\nErrors:")
                for error in results["errors"]:
                    print(f"  - {error}")


if __name__ == "__main__":
    asyncio.run(main())