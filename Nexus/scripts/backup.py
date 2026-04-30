"""Backup and restore utilities for Nexus."""
import os
import shutil
import tarfile
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import argparse


logger = logging.getLogger(__name__)


class BackupManager:
    """Manage backups of Nexus workspace and configuration."""
    
    def __init__(
        self,
        backup_dir: Path = None,
        workspace: Path = None,
        keep_backups: int = 7
    ):
        self.backup_dir = backup_dir or (Path.home() / ".nexus" / "backups")
        self.workspace = workspace or (Path.cwd() / "workspace")
        self.keep_backups = keep_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, name: str = None) -> Path:
        """Create a new backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"nexus_backup_{timestamp}"
        
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        logger.info(f"Creating backup: {backup_path}")
        
        with tarfile.open(backup_path, "w:gz") as tar:
            # Backup workspace
            if self.workspace.exists():
                logger.info(f"Backing up workspace: {self.workspace}")
                tar.add(self.workspace, arcname="workspace")
            
            # Backup config
            config_dir = Path.home() / ".config" / "nexus"
            if config_dir.exists():
                logger.info(f"Backing up config: {config_dir}")
                tar.add(config_dir, arcname="config")
            
            # Backup memory/logs
            nexus_data = Path.home() / ".nexus"
            if nexus_data.exists():
                logger.info(f"Backing up data: {nexus_data}")
                tar.add(nexus_data, arcname="data")
        
        # Write metadata
        metadata = {
            "name": backup_name,
            "created_at": datetime.now().isoformat(),
            "workspace": str(self.workspace),
            "files": self._get_backup_files(backup_path)
        }
        
        metadata_path = self.backup_dir / f"{backup_name}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Clean old backups
        self._clean_old_backups()
        
        logger.info(f"Backup created: {backup_path}")
        return backup_path
    
    def _get_backup_files(self, backup_path: Path) -> List[str]:
        """Get list of files in backup."""
        with tarfile.open(backup_path, "r:gz") as tar:
            return tar.getnames()
    
    def _clean_old_backups(self):
        """Remove old backups beyond keep limit."""
        backups = sorted(
            self.backup_dir.glob("nexus_backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for backup in backups[self.keep_backups:]:
            logger.info(f"Removing old backup: {backup}")
            backup.unlink()
            
            # Also remove metadata
            metadata = backup.with_suffix(".json")
            if metadata.exists():
                metadata.unlink()
    
    def list_backups(self) -> List[dict]:
        """List available backups."""
        backups = []
        
        for metadata_file in sorted(
            self.backup_dir.glob("nexus_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            try:
                with open(metadata_file) as f:
                    backup_info = json.load(f)
                    backup_info["path"] = str(
                        metadata_file.with_suffix(".tar.gz")
                    )
                    backups.append(backup_info)
            except Exception as e:
                logger.warning(f"Could not read backup metadata: {e}")
        
        return backups
    
    def restore_backup(self, backup_name: str):
        """Restore from a backup."""
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        
        logger.info(f"Restoring from backup: {backup_path}")
        
        # Extract to temp location first
        temp_dir = self.backup_dir / ".temp_restore"
        
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(temp_dir)
        
        # Restore workspace
        workspace_backup = temp_dir / "workspace"
        if workspace_backup.exists():
            if self.workspace.exists():
                shutil.rmtree(self.workspace)
            shutil.copytree(workspace_backup, self.workspace)
        
        # Restore config
        config_backup = temp_dir / "config"
        config_target = Path.home() / ".config" / "nexus"
        if config_backup.exists():
            config_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(config_backup, config_target, dirs_exist_ok=True)
        
        # Restore data
        data_backup = temp_dir / "data"
        data_target = Path.home() / ".nexus"
        if data_backup.exists():
            data_target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(data_backup, data_target, dirs_exist_ok=True)
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        logger.info("Backup restored successfully!")
    
    def delete_backup(self, backup_name: str):
        """Delete a specific backup."""
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        metadata_path = self.backup_dir / f"{backup_name}.json"
        
        if backup_path.exists():
            backup_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
        
        logger.info(f"Deleted backup: {backup_name}")


def main():
    """CLI for backup management."""
    parser = argparse.ArgumentParser(description="Nexus Backup Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create backup
    create_parser = subparsers.add_parser("create", help="Create a backup")
    create_parser.add_argument("--name", help="Backup name")
    
    # List backups
    subparsers.add_parser("list", help="List backups")
    
    # Restore backup
    restore_parser = subparsers.add_parser("restore", help="Restore a backup")
    restore_parser.add_argument("name", help="Backup name to restore")
    
    # Delete backup
    delete_parser = subparsers.add_parser("delete", help="Delete a backup")
    delete_parser.add_argument("name", help="Backup name to delete")
    
    args = parser.parse_args()
    
    manager = BackupManager()
    
    if args.command == "create":
        backup = manager.create_backup(args.name)
        print(f"Backup created: {backup}")
    
    elif args.command == "list":
        backups = manager.list_backups()
        if not backups:
            print("No backups found")
        else:
            for b in backups:
                print(f"{b['name']} - {b['created_at']}")
    
    elif args.command == "restore":
        manager.restore_backup(args.name)
        print("Restore complete!")
    
    elif args.command == "delete":
        manager.delete_backup(args.name)
        print("Backup deleted!")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()