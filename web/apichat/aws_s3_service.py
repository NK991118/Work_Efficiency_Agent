import boto3
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from datetime import datetime

import os
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.crypto import get_random_string


class S3Client:
    def __init__(self):
        pass
        # if settings.DEBUG:
        #     raise RuntimeError("DEBUG=True에서는 S3Client를 사용하지 않습니다. (로컬 저장 모드)")

        # if not settings.AWS_STORAGE_BUCKET_NAME:
        #     raise RuntimeError("AWS_STORAGE_BUCKET_NAME이 설정되지 않았습니다.")
        
        # self.s3 = boto3.client(
        #     "s3",
        #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        #     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        #     region_name=settings.AWS_S3_REGION_NAME,
        # )
        # self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def upload(self, file):
        save_dir = "chatimage"
        now = timezone.now()
        date_prefix = now.strftime("%Y%m%d_%H%M%S_")
        ext = os.path.splitext(file.name)[1]
        new_file_name = f"{date_prefix}{get_random_string(8)}{ext}"

        relative_path = f"{save_dir}/{new_file_name}"
        saved_path = default_storage.save(relative_path, file)

        return settings.MEDIA_URL + saved_path
    
        # new_file_name = f"{date_prefix}{file.name}"
        # extra_args = {"ContentType": file.content_type}
        # try:
        #     self.s3.upload_fileobj(
        #         file,
        #         self.bucket_name,
        #         f"{save_dir}{new_file_name}",
        #         ExtraArgs=extra_args,
        #     )
        #     return (
        #         f"https://{self.bucket_name}.s3.amazonaws.com/{save_dir}{new_file_name}"
        #     )
        # except NoCredentialsError:
        #     print("Credentials not available")
