"""API key and secret encryption utilities."""
import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib


class SecretManager:
    """Manage encrypted API keys and secrets."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        if encryption_key:
            # Derive key from provided secret
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"nexus_salt_v1",
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
            self.cipher = Fernet(key)
        else:
            # Use environment key
            from nexus.config.settings import config
            if not config.api_keys_encryption_key:
                raise ValueError(
                    "No encryption key configured. Set API_KEYS_ENCRYPTION_KEY in .env"
                )
            key = config.api_keys_encryption_key.encode()
            if len(base64.urlsafe_b64decode(key)) != 32:
                raise ValueError("Invalid encryption key format")
            self.cipher = Fernet(key)
    
    def encrypt(self, secret: str) -> str:
        """Encrypt a secret."""
        if not secret:
            raise ValueError("Secret cannot be empty")
        
        encrypted = self.cipher.encrypt(secret.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_secret: str) -> str:
        """Decrypt a secret."""
        if not encrypted_secret:
            raise ValueError("Encrypted secret cannot be empty")
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_secret.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key."""
        return base64.b64encode(os.urandom(32)).decode()


def hash_secret(secret: str, salt: str = "") -> str:
    """Hash a secret for logging/comparison (one-way)."""
    combined = f"{secret}{salt}".encode()
    return hashlib.sha256(combined).hexdigest()


def mask_secret(secret: str, visible: int = 4) -> str:
    """Mask a secret for display."""
    if not secret or len(secret) <= visible:
        return "*" * 8
    
    return secret[:visible] + "*" * (len(secret) - visible)


class SecretsConfig:
    """Schema for encrypted secrets storage."""
    
    def __init__(self, config_path: Optional[str] = None):
        import json
        from pathlib import Path
        
        self.config_path = Path(config_path) if config_path else Path.home() / ".config" / "nexus" / "secrets.enc"
        self._secrets: dict = {}
        
        if self.config_path.exists():
            try:
                self._load()
            except Exception:
                pass
    
    def _load(self):
        """Load encrypted secrets."""
        import json
        from pathlib import Path
        
        if not self.config_path.exists():
            return
        
        # Decrypt the entire file
        with open(self.config_path, 'r') as f:
            encrypted_data = f.read()
        
        if not encrypted_data:
            return
        
        manager = SecretManager()
        try:
            decrypted = manager.decrypt(encrypted_data)
            self._secrets = json.loads(decrypted)
        except Exception:
            self._secrets = {}
    
    def _save(self):
        """Save encrypted secrets."""
        import json
        from pathlib import Path
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        manager = SecretManager()
        encrypted = manager.encrypt(json.dumps(self._secrets))
        
        with open(self.config_path, 'w') as f:
            f.write(encrypted)
    
    def get(self, key: str) -> Optional[str]:
        """Get a secret."""
        return self._secrets.get(key)
    
    def set(self, key: str, value: str):
        """Set a secret."""
        self._secrets[key] = value
        self._save()
    
    def delete(self, key: str):
        """Delete a secret."""
        if key in self._secrets:
            del self._secrets[key]
            self._save()