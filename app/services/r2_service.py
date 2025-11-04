import os
import boto3
from botocore.client import Config
from urllib.parse import urlparse
from botocore.exceptions import ClientError
from app.config import settings


class R2Client:
    def __init__(self):
        # Use boto3 with endpoint override for Cloudflare R2
        access_key = settings.CLOUDFLARE_R2_ACCESS_KEY_ID
        secret_key = settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY
        endpoint = settings.CLOUDFLARE_R2_ENDPOINT
        region = 'auto'

        if not access_key or not secret_key or not endpoint or not settings.CLOUDFLARE_R2_BUCKET:
            raise RuntimeError('R2 not configured. Please set CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_ENDPOINT and CLOUDFLARE_R2_BUCKET in .env')

        self.bucket = settings.CLOUDFLARE_R2_BUCKET
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            config=Config(signature_version='s3v4'),
            region_name=region,
        )

    def upload_file(self, file_path: str, key: str, public: bool = False) -> str:
        """Uploads a local file to R2 and returns the object URL (public if public=True).
        Key should be the object key in the bucket (e.g., `posts/<uuid>.png`).
        """
        extra_args = {}
        if public:
            extra_args['ACL'] = 'public-read'

        with open(file_path, 'rb') as f:
            self.s3.upload_fileobj(f, self.bucket, key, ExtraArgs=extra_args)

        # Construct URL
        if settings.CLOUDFLARE_R2_ENDPOINT.endswith('/'):
            endpoint = settings.CLOUDFLARE_R2_ENDPOINT[:-1]
        else:
            endpoint = settings.CLOUDFLARE_R2_ENDPOINT

        # Use the public URL if public=True, otherwise use the endpoint URL
        if public:
            if settings.CLOUDFLARE_R2_PUBLIC_URL:
                object_url = f"{settings.CLOUDFLARE_R2_PUBLIC_URL}/{key}"
            else:
                # Fallback to default R2 public URL
                object_url = f"https://{self.bucket}.r2.cloudflarestorage.com/{key}"
        else:
            object_url = f"{endpoint}/{self.bucket}/{key}"
        return object_url

    def upload_fileobj(self, fileobj, key: str, public: bool = False) -> str:
        """Uploads a file-like object to R2 and returns the object URL (public if public=True).
        Key should be the object key in the bucket (e.g., `posts/<uuid>.png`).
        """
        extra_args = {}
        if public:
            extra_args['ACL'] = 'public-read'

        self.s3.upload_fileobj(fileobj, self.bucket, key, ExtraArgs=extra_args)

        # Construct URL
        if settings.CLOUDFLARE_R2_ENDPOINT.endswith('/'):
            endpoint = settings.CLOUDFLARE_R2_ENDPOINT[:-1]
        else:
            endpoint = settings.CLOUDFLARE_R2_ENDPOINT

        # Use the public URL if public=True, otherwise use the endpoint URL
        if public:
            if settings.CLOUDFLARE_R2_PUBLIC_URL:
                object_url = f"{settings.CLOUDFLARE_R2_PUBLIC_URL}/{key}"
            else:
                # Fallback to default R2 public URL
                object_url = f"https://{self.bucket}.r2.cloudflarestorage.com/{key}"
        else:
            object_url = f"{endpoint}/{self.bucket}/{key}"
        return object_url


# Convenience function
def upload_file_to_r2(file_path: str, key_prefix: str = 'posts', public: bool = False) -> dict:
    client = R2Client()
    filename = os.path.basename(file_path)
    key = f"{key_prefix}/{filename}"
    url = client.upload_file(file_path, key, public=public)
    return {"key": key, "url": url}


def upload_fileobj_to_r2(fileobj, filename: str, key_prefix: str = 'posts', public: bool = False) -> dict:
    client = R2Client()
    key = f"{key_prefix}/{filename}"
    url = client.upload_fileobj(fileobj, key, public=public)
    return {"key": key, "url": url}


def download_bytes_from_r2_url(url: str) -> bytes:
    """Download object bytes from an R2 URL previously produced by upload_file_to_r2.

    Handles both internal endpoint URLs (<endpoint>/<bucket>/<key>) and public CDN URLs (<bucket>.r2.cloudflarestorage.com/<key>).
    """
    client = R2Client()

    parsed = urlparse(url)
    path = parsed.path.lstrip('/')

    # Check if it's a public R2 URL (bucket.r2.cloudflarestorage.com)
    if parsed.netloc.endswith('.r2.cloudflarestorage.com'):
        bucket_in_url = parsed.netloc.split('.')[0]
        key = path
    else:
        # Assume internal endpoint URL format: <endpoint>/<bucket>/<key>
        path_parts = path.split('/', 1)
        if len(path_parts) < 2:
            raise ValueError(f"Could not parse R2 URL to extract key: {url}")
        bucket_in_url, key = path_parts[0], path_parts[1]

    # Validate bucket matches configured
    if bucket_in_url != client.bucket:
        # It's possible the URL uses a CDN or different host but includes bucket; warn but attempt
        pass

    try:
        obj = client.s3.get_object(Bucket=client.bucket, Key=key)
        return obj['Body'].read()
    except ClientError as e:
        raise RuntimeError(f"Failed to download object from R2: {e}")
