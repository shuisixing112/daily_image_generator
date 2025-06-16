# 將 prompt 欄位擷取出來，並呼叫 BingImageCreator 指令至Bing生圖
# 將圖下載並命名分類

import os
from dotenv import load_dotenv
import re
import subprocess
import requests
from datetime import datetime
import base64
import pytz
from google.cloud import storage
from datetime import datetime
import firebase_admin
from firebase_admin import storage, credentials

# 載入 .env 檔案中的環境變數
load_dotenv()
BING_U = os.getenv("BING_U")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
FIREBASE_STORAGE_BUCKET= os.getenv("FIREBASE_STORAGE_BUCKET")

tz = pytz.timezone("Asia/Taipei")

try:
    firebase_admin.initialize_app()
    print("✅ Firebase Admin SDK 初始化成功！")
except ValueError:
    # 如果已經初始化過，會捕獲這個錯誤，表示可以安全跳過
    print("ℹ️ Firebase Admin SDK 已經初始化，跳過重複初始化。")
except Exception as e:
    print(f"❌ Firebase Admin SDK 初始化失敗：{e}")
    # 您可能希望在這裡添加更具體的錯誤處理，例如退出程式
    exit(1)

# def upload_to_imgbb(image_path, api_key):
#     """Uploads an image to imgBB and returns the URL of the uploaded image.

#     Parameters:
#     image_path (str): The local path to the image file to upload.
#     api_key (str): The imgBB API key to use for the upload.

#     Returns:
#     str: The URL of the uploaded image if successful, or None if upload failed.
#     """
#     with open(image_path, "rb") as f:
#         encoded_image = base64.b64encode(f.read())
#     url = "https://api.imgbb.com/1/upload"
#     payload = {
#         "key": api_key,
#         "image": encoded_image,
#         "name": filename_without_ext,  # 🆕 新增圖片名稱
#     }
#     response = requests.post(url, data=payload)
#     if response.status_code == 200:
#         data = response.json()
#         image_url = data["data"]["url"]
#         print("✅ 圖片已上傳成功！imgBB 連結：", image_url)
#         return image_url
#     else:
#         print("❌ 上傳失敗：", response.status_code, response.text)
#         return None


# 不經過本地端上傳照片到ImgBB
def upload_to_imgbb_from_memory(image_bytes, image_name, api_key):
    """Uploads an image (in-memory bytes) to imgBB and returns the URL."""
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": encoded_image,
        "name": filename_without_ext,
    }
    response = requests.post(url, data=payload)

    if response.status_code == 200:
        data = response.json()
        image_url = data["data"]["url"]
        print(f"✅ 圖片已上傳成功！imgBB 連結: {image_url}")
        return image_url
    else:
        print(f"❌ 上傳失敗：", response.status_code, response.text)
        return None


# 從 Firebase Storage 中最新的年-月資料夾中，找出最新 .txt prompt
def get_latest_prompt_from_firebase(bucket_name= FIREBASE_STORAGE_BUCKET ):
    bucket =storage.bucket(bucket_name)

    # 👉 取得目前年月，格式為 '2025-06'
    current_year_month = datetime.now().strftime("%Y-%m")
    prefix = f"prompts/{current_year_month}/"

    # 🔍 找出此資料夾下的所有檔案
    blobs = list(bucket.list_blobs(prefix=prefix))

    if not blobs:
        raise FileNotFoundError(f"❗ 找不到任何檔案於 Firebase Storage: {prefix}")

    # 🕐 根據建立時間排序，取得最新一筆
    latest_blob = sorted(blobs, key=lambda b: b.time_created, reverse=True)[0]

    print(f"✅ 讀取最新 prompt 檔案：{latest_blob.name}")
    content = latest_blob.download_as_text()

    return content


# 設定文字檔與圖片輸出路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_DIR = os.path.join(BASE_DIR, "prompts")

# 依照月份建立圖片輸出資料夾
base_output_dir = os.path.join(BASE_DIR, "generated_images")
now = datetime.now()
year_month = now.strftime("%Y-%m")
OUTPUT_DIR = os.path.join(base_output_dir, year_month)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 建立圖片輸出資料夾（如果還沒建立）
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 取得最新的 .txt 檔案
txt_files = [f for f in os.listdir(TEXT_DIR) if f.endswith(".txt")]
latest_file = max(txt_files, key=lambda f: os.path.getctime(os.path.join(TEXT_DIR, f)))

# 從本地擷取 prompt 欄位
# with open(os.path.join(TEXT_DIR, latest_file), "r", encoding="utf-8") as f:
#     content = f.read()

# 從Firebase的prompt擷取欄位
content = get_latest_prompt_from_firebase(FIREBASE_STORAGE_BUCKET)
print("💡 從Firebase Storage讀取最新prompt...")

try:
    content = get_latest_prompt_from_firebase(FIREBASE_STORAGE_BUCKET)
    print(f"✅ 成功從Firebase Storage讀取到prompt！")
except FileNotFoundError as e:
    print(f"❌ 錯誤：{e}. 請確認Firebase Storage中有prompt文件。")
    exit(1) # 如果沒有找到prompt，則終止程式
except Exception as e:
    print(f"❌ 從Firebase Storage讀取prompt時發生未知錯誤：{e}")
    exit(1)

prompt = content    # 將從 Firebase 讀取的內容賦值給 prompt 變數，以便後續使用

match = re.search(r'"prompt"\s*:\s*"([^"]+)"', content, re.DOTALL)
if not match:
    print("❌ 找不到 prompt 欄位")
    exit()

prompt = match.group(1)
print(f"🎨 擷取到 prompt：{prompt}")

# 擷取 animal 和 action 和 location 欄位
match_animal = re.search(r'"animal"\s*:\s*"([^"]+)"', content, re.DOTALL)
match_action = re.search(r'"action"\s*:\s*"([^"]+)"', content, re.DOTALL)
match_location = re.search(r'"location_description"\s*:\s*"([^"]+)"', content, re.DOTALL)

animal = match_animal.group(1).replace(" ", "_") if match_animal else "unknown"
action = match_action.group(1).replace(" ", "_") if match_action else "unknown"
location = match_location.group(1).replace(" ", "_") if match_location else "unknown"

# 呼叫 BingImageCreator 指令
command = [
    "python", "-m", "BingImageCreator",    
    "-U", BING_U,  # 若你用的是 auth cookie 改用這裡
    "--prompt", prompt,
    "--output-dir", OUTPUT_DIR,
    "--download-count", "4"
]

# print(f"DEBUG: BING_U_VALUE: {BING_U}") # 注意這裡使用的是變數 BING_U
# print(f"DEBUG: Prompt: {prompt}")
# print(f"DEBUG: OUTPUT_DIR: {OUTPUT_DIR}")
# print(f"DEBUG: Final command list: {command}")
# print(f"DEBUG: Type of command list: {type(command)}")
# print(f"DEBUG: Check for None in command list: {'None' in command}")

subprocess.run(command, check=True)

print("✅ 圖片已生成！")

# 將下載圖片重新命名
files = sorted(
    [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpeg")],
    key=lambda x: os.path.getctime(os.path.join(OUTPUT_DIR, x)),
    reverse=True
)[:4]  # 最新的4張圖

now = datetime.now(tz).strftime("%Y-%m-%d_%H%M")

for i, old_name in enumerate(reversed(files), start=1):
    new_name = f"{now}_{animal}_{action}_{location}_{i}.jpeg"
    # os.rename(
    #     os.path.join(OUTPUT_DIR, old_name),
    #     os.path.join(OUTPUT_DIR, new_name)
    # )
    file_path = os.path.join(OUTPUT_DIR, old_name)

    # 儲存在本地後改名
    # image_path = os.path.join(OUTPUT_DIR, new_name)
    # filename_without_ext = os.path.splitext(os.path.basename(image_path))[0]

    # 🔄 讀取圖片 bytes（不儲存中繼檔）
    with open(file_path, "rb") as f:
        image_bytes = f.read()

    filename_without_ext = os.path.splitext(new_name)[0]
    
    # 從本地自動上傳到 imgBB
    # imgbb_api_key = os.getenv("IMGBB_API_KEY")  # 建議從 .env 中讀取
    # upload_to_imgbb(image_path, imgbb_api_key)

    # ✅ 上傳記憶體圖片到 imgBB
    upload_to_imgbb_from_memory(image_bytes, filename_without_ext, IMGBB_API_KEY)

    print("✅ 圖片已上傳成功！imgBB!")


# print("✅ 圖片已重新命名並儲存完成！")
