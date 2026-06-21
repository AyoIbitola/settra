import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    @staticmethod
    def get_client():
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    @staticmethod
    def upload_file(file_content: bytes, object_name: str, content_type: str = "application/pdf") -> str:
        """
        Uploads an in-memory file to S3 and returns the public URL.
        """
        s3 = S3Service.get_client()
        bucket = settings.AWS_S3_BUCKET_NAME

        try:
            s3.put_object(
                Bucket=bucket,
                Key=object_name,
                Body=file_content,
                ContentType=content_type,
                # Depending on bucket ACLs, you might need to upload with public-read or
                # use presigned URLs. For now, assuming the bucket allows reading or we return standard URLs.
            )
            # Return the standard representation of the URL
            return f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{object_name}"
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    @staticmethod
    def generate_presigned_url(object_url: str, expiration: int = 3600) -> str:
        """
        Generates a presigned URL for downloading a private S3 object.
        Retrieves the bucket and key from the standard object URL.
        """
        s3 = S3Service.get_client()
        bucket = settings.AWS_S3_BUCKET_NAME
        try:
            # Parse the object key from the URL
            key = object_url.split(".amazonaws.com/")[-1]
            response = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return response
        except (BotoCoreError, ClientError, IndexError) as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
