# script/sync.py
import os
import sys
import boto3
from botocore.exceptions import ClientError
import logging
import pathlib

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def transform_path_to_s3_key(repo_path_str):
    """
    根據指定規則轉換 repo 內的檔案路徑為 S3 的 object key。
    規則：移除開頭的 '數字_' 和第二層的日期目錄。
    例如：'01_economist/te_2025.04.26/TheEconomist.2025.04.26.pdf'
          轉換為 'economist/TheEconomist.2025.04.26.pdf'

    :param repo_path_str: Repo 內的相對路徑字串
    :return: 轉換後的 S3 key 字串，如果格式不符則返回 None
    """
    try:
        repo_path = pathlib.Path(repo_path_str)
        parts = repo_path.parts # 將路徑分割成各部分 ('01_economist', 'te_2025.04.26', 'TheEconomist...')

        # 檢查路徑結構是否至少有三層 (folder/date/file)
        if len(parts) >= 3:
            first_dir = parts[0] # 例如 '01_economist'
            filename = parts[-1] # 取得最後的檔名

            # 找到第一個底線的位置
            underscore_index = first_dir.find('_')

            # 檢查是否有底線，且底線不是第一個字元 (避免像 '_folder' 這種)
            if underscore_index > 0:
                # 取得底線之後的部分作為 category
                category = first_dir[underscore_index + 1:]

                # 組合新的 S3 key: category/filename
                s3_key = f"others/{category}/{filename}"
                logging.info(f"路徑轉換: '{repo_path_str}' -> S3 Key: '{s3_key}'")
                return s3_key
            else:
                logging.warning(f"路徑 '{repo_path_str}' 的第一層目錄 '{first_dir}' 不符合 '數字_分類' 格式，無法轉換。")
                return None
        else:
            # 如果路徑結構不符預期，可以決定是跳過、用原路徑或其他處理方式
            # 目前設定為無法轉換則返回 None
            logging.warning(f"路徑 '{repo_path_str}' 的結構不符合預期的 '分類/日期/檔案' 格式，無法轉換。")
            return None
    except Exception as e:
        logging.error(f"轉換路徑 '{repo_path_str}' 時發生錯誤: {e}")
        return None

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
    successful_uploads = 0
    skipped_files = 0
    
    for file_path in files_to_upload:
        # 在這裡進行路徑轉換
        s3_object_key = transform_path_to_s3_key(file_path)
        
        if s3_object_key:
            # 如果轉換成功，則執行上傳
            if not upload_to_s3(file_path, s3_bucket, s3_object_key):
                all_successful = False
                logging.error(f"上傳失敗: {file_path} (目標 S3 Key: {s3_object_key})")
        else:
            # 如果轉換失敗 (路徑格式不符)，則記錄警告並跳過此檔案
            logging.warning(f"因路徑格式不符或轉換失敗，已跳過上傳: {file_path}")
            skipped_files += 1
            # 根據需求，你可以決定跳過是否算作整體失敗
            # all_successful = False # 如果希望任何跳過都算失敗，取消此行註解
    
    logging.info(f"處理完成。成功上傳 {successful_uploads} 個檔案，跳過 {skipped_files} 個檔案。")

    if all_successful:
        logging.info("所有指定的檔案均已成功上傳。")
        sys.exit(0)
    else:
        logging.error("部分或全部檔案上傳失敗。")
        sys.exit(1)
