import os
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from app.config import settings

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def _ensure_bucket(bucket: str) -> None:
    client = _get_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_file(local_path: str, bucket: str, object_name: str) -> str:
    """
    上传文件到 MinIO。
    返回 object_name。
    """
    _ensure_bucket(bucket)
    client = _get_client()
    client.fput_object(bucket, object_name, local_path)
    return object_name


def download_file(bucket: str, object_name: str, local_path: str) -> None:
    """从 MinIO 下载文件到本地"""
    client = _get_client()
    client.fget_object(bucket, object_name, local_path)


def delete_file(bucket: str, object_name: str) -> None:
    """从 MinIO 删除文件"""
    client = _get_client()
    try:
        client.remove_object(bucket, object_name)
    except S3Error:
        pass


def delete_files(bucket: str, object_names: list[str]) -> None:
    """批量删除 MinIO 文件"""
    if not object_names:
        return
    client = _get_client()
    errors = client.remove_objects(bucket, object_names)
    for err in errors:
        pass  # 静默吞掉删除失败（文件可能已不存在）


def build_object_name(unit_id: str, filename: str, is_chunk: bool = False, chunk_index: int = 0) -> str:
    """
    构造 MinIO 对象路径。
    格式: {unit_id}/{filename}  或  {unit_id}/chunks/{chunk_index:04d}_{filename}
    """
    if is_chunk:
        return f"{unit_id}/chunks/{chunk_index:04d}_{filename}"
    return f"{unit_id}/{filename}"


def build_image_object_name(unit_id: str, image_name: str) -> str:
    """构造 MinIO 图片对象路径。格式: {unit_id}/images/{image_name}"""
    return f"{unit_id}/images/{image_name}"


def list_objects(bucket: str, prefix: str) -> list[str]:
    """列出 MinIO 中指定前缀下的所有对象名称"""
    client = _get_client()
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    return [obj.object_name for obj in objects]


def delete_prefix(bucket: str, prefix: str) -> int:
    """删除 MinIO 中指定前缀下的所有对象，返回删除数量"""
    names = list_objects(bucket, prefix)
    if names:
        delete_files(bucket, names)
    return len(names)


def get_presigned_url(bucket: str, object_name: str, expires_days: int = 7) -> str:
    """生成预签名 URL，用于外部访问 MinIO 对象"""
    client = _get_client()
    return client.presigned_get_object(bucket, object_name, expires=timedelta(days=expires_days))