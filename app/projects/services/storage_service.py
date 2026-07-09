import os
import logging
from app.config import settings

logger = logging.getLogger("storage_service")

class StorageService:
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER.lower()
        self.bucket = settings.STORAGE_BUCKET
        self.region = settings.STORAGE_REGION
        self.upload_dir = settings.UPLOAD_DIRECTORY
        
        # Ensure upload dir exists locally
        os.makedirs(self.upload_dir, exist_ok=True)
        
        self.s3_client = None
        if self.provider in ("s3", "r2"):
            try:
                import boto3
                endpoint_url = os.getenv("STORAGE_ENDPOINT_URL")
                self.s3_client = boto3.client(
                    "s3",
                    region_name=self.region,
                    endpoint_url=endpoint_url
                )
                logger.info(f"Initialized S3 storage provider on bucket '{self.bucket}' in region '{self.region}'.")
            except ImportError:
                logger.error("boto3 library is not installed. StorageService falling back to 'local' provider.")
                self.provider = "local"
            except Exception as e:
                logger.error(f"Failed to initialize S3 storage client: {e}. Falling back to 'local' provider.")
                self.provider = "local"

    def save_file(self, relative_path: str, content: bytes) -> str:
        """Saves a file and returns its access path/identifier."""
        # Clean relative path to prevent traversal
        relative_path = os.path.normpath(relative_path).lstrip(os.sep)
        
        if self.provider in ("s3", "r2") and self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=relative_path,
                    Body=content
                )
                logger.info(f"Saved file to S3 bucket: {relative_path}")
                return f"s3://{self.bucket}/{relative_path}"
            except Exception as e:
                logger.error(f"S3 save_file failed: {e}. Attempting local fallback.")
                
        # Fallback to local storage
        local_path = os.path.join(self.upload_dir, relative_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved file to local storage: {local_path}")
        return local_path

    def get_file(self, relative_path: str) -> bytes:
        """Retrieves file contents as bytes."""
        relative_path = os.path.normpath(relative_path).lstrip(os.sep)
        
        if self.provider in ("s3", "r2") and self.s3_client:
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket,
                    Key=relative_path
                )
                return response["Body"].read()
            except Exception as e:
                logger.error(f"S3 get_file failed: {e}. Attempting local fallback.")
                
        local_path = os.path.join(self.upload_dir, relative_path)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"File not found in storage: {relative_path}")

    def delete_file(self, relative_path: str) -> bool:
        """Deletes a file from the storage provider."""
        relative_path = os.path.normpath(relative_path).lstrip(os.sep)
        success = False
        
        if self.provider in ("s3", "r2") and self.s3_client:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket,
                    Key=relative_path
                )
                logger.info(f"Deleted file from S3 bucket: {relative_path}")
                success = True
            except Exception as e:
                logger.error(f"S3 delete_file failed: {e}")
                
        local_path = os.path.join(self.upload_dir, relative_path)
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Deleted file from local storage: {local_path}")
            success = True
            
        return success

storage_service = StorageService()
