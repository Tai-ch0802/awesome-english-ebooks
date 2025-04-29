# script/sync.py
import os
import sys
import boto3
from botocore.exceptions import ClientError
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_to_s3(file_path, bucket_name, s3_key):
    """
    將單一檔案上傳到 S3

    :param file_path: 要上傳的本地檔案路徑
    :param bucket_name: S3 Bucket 的名稱
    :param s3_key: 存放在 S3 上的檔案路徑/名稱
    :return: 如果成功上傳返回 True，否則 False
    """
    # 從環境變數讀取 AWS 憑證 (由 GitHub Actions 提供)
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION')
    endpoint_url = os.environ.get('S3_ENDPOINT')

    if not all([aws_access_key_id, aws_secret_access_key, aws_region, bucket_name]):
        logging.error("缺少必要的 AWS 配置 (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME)")
        return False

    # 建立 S3 client
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )

    try:
        logging.info(f"正在上傳 {file_path} 到 s3://{bucket_name}/{s3_key}...")
        s3_client.upload_file(file_path, bucket_name, s3_key)
        logging.info(f"成功上傳 {file_path} 到 s3://{bucket_name}/{s3_key}")
    except FileNotFoundError:
        logging.error(f"檔案未找到: {file_path}")
        return False
    except ClientError as e:
        logging.error(f"上傳 {file_path} 到 S3 時發生錯誤: {e}")
        return False
    return True

if __name__ == "__main__":
    # 從環境變數獲取 S3 Bucket 名稱
    s3_bucket = os.environ.get('S3_BUCKET_NAME')

    if not s3_bucket:
        logging.error("環境變數 S3_BUCKET_NAME 未設定")
        sys.exit(1)

    # 從命令列參數獲取需要上傳的檔案列表
    # GitHub Actions 會將變更的檔案路徑作為參數傳遞給這個腳本
    files_to_upload = sys.argv[1:]

    if not files_to_upload:
        logging.info("沒有需要上傳的 PDF 檔案。")
        sys.exit(0)

    logging.info(f"準備上傳以下檔案到 S3 Bucket '{s3_bucket}':")
    for f in files_to_upload:
        logging.info(f"- {f}")

    all_successful = True
    for file_path in files_to_upload:
        # 使用檔案在 repo 中的相對路徑作為 S3 的 key
        s3_object_key = file_path
        if not upload_to_s3(file_path, s3_bucket, s3_object_key):
            all_successful = False
            logging.error(f"上傳失敗: {file_path}")

    if all_successful:
        logging.info("所有指定的檔案均已成功上傳。")
        sys.exit(0)
    else:
        logging.error("部分或全部檔案上傳失敗。")
        sys.exit(1)
