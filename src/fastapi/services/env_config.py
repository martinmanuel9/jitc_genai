# env_config.py - Environment-specific configuration
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class EnvironmentConfig:
    """Detect and configure for different environments"""
    
    def __init__(self):
        self.is_docker = self._detect_docker()
        self.is_ec2 = self._detect_ec2()
        self.environment_name = self._get_environment_name()
        
        logger.info(f"Environment detected: {self.environment_name}")
        logger.info(f"Docker: {self.is_docker}, EC2: {self.is_ec2}")
        
    def _detect_docker(self) -> bool:
        """Detect if running in Docker container"""
        return (
            os.path.exists('/.dockerenv') or 
            os.environ.get('CONTAINER', '').lower() == 'true' or
            os.environ.get('DOCKER', '').lower() == 'true'
        )
    
    def _detect_ec2(self) -> bool:
        """Detect if running on EC2 instance"""
        try:
            # Check for EC2 metadata service
            import requests
            resp = requests.get(
                'http://169.254.169.254/latest/meta-data/instance-id', 
                timeout=2
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def _get_environment_name(self) -> str:
        """Get human-readable environment name"""
        if self.is_docker:
            return "Docker"
        elif self.is_ec2:
            return "EC2"
        else:
            return "Local"
    
    def get_database_url(self) -> str:
        """Get appropriate database URL for environment"""
        # Check for explicit DATABASE_URL first
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            logger.info(f"Using DATABASE_URL from environment: {db_url}")
            return db_url
        
        # Auto-detect based on environment
        if self.is_docker:
            # Docker environment - use PostgreSQL
            default_url = 'postgresql://g3nA1-user:m0re-g3nA1-s3cr3t@postgres:5432/rag_memory'
            logger.info("Docker environment detected, using PostgreSQL")
            return default_url
        else:
            # Local direct or EC2 - use SQLite
            default_url = 'sqlite:///./data/app.db'
            logger.info("Local/EC2 environment detected, using SQLite")
            return default_url
    
    def get_chroma_url(self) -> str:
        """Get ChromaDB URL for environment"""
        chroma_url = os.environ.get('CHROMA_URL')
        if chroma_url:
            return chroma_url

        if self.is_docker:
            return 'http://chromadb:8000'
        else:
            return 'http://localhost:8001'  # External port mapping
    
    def get_redis_url(self) -> str:
        """Get Redis URL for environment"""
        redis_url = os.environ.get('REDIS_URL')
        if redis_url:
            return redis_url
            
        if self.is_docker:
            return 'redis://redis:6379/0'
        else:
            return 'redis://localhost:6379/0'
    
    def get_fastapi_url(self) -> str:
        """Get FastAPI URL for environment"""
        fastapi_url = os.environ.get('FASTAPI_URL')
        if fastapi_url:
            return fastapi_url
            
        if self.is_docker:
            return 'http://fastapi:9020'
        else:
            return 'http://localhost:9020'
    
    def get_data_directory(self) -> str:
        """Get data directory for environment"""
        if self.is_docker:
            return '/app/data'
        else:
            # Ensure data directory exists
            data_dir = './data'
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
    
    def get_chroma_persist_directory(self) -> str:
        """Get ChromaDB persistence directory"""
        chroma_dir = os.environ.get('CHROMADB_PERSIST_DIRECTORY')
        if chroma_dir:
            return chroma_dir
            
        if self.is_docker:
            return '/app/chroma_db_data'
        else:
            persist_dir = './data/chroma'
            os.makedirs(persist_dir, exist_ok=True)
            return persist_dir

# Global instance
env_config = EnvironmentConfig()

# Helper functions for easy access
def get_database_url() -> str:
    return env_config.get_database_url()

def get_chroma_url() -> str:
    return env_config.get_chroma_url()

def get_redis_url() -> str:
    return env_config.get_redis_url()

def is_docker_environment() -> bool:
    return env_config.is_docker

def is_ec2_environment() -> bool:
    return env_config.is_ec2