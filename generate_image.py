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

tz = pytz.timezone("Asia/Taipei")

def upload_to_imgbb(image_path, api_key):
    """Uploads an image to imgBB and returns the URL of the uploaded image.

    Parameters:
    image_path (str): The local path to the image file to upload.
    api_key (str): The imgBB API key to use for the upload.

    Returns:
    str: The URL of the uploaded image if successful, or None if upload failed.
    """
    with open(image_path, "rb") as f:
        encoded_image = base64.b64encode(f.read())
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": encoded_image,
        "name": filename_without_ext,  # 🆕 新增圖片名稱
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        data = response.json()
        image_url = data["data"]["url"]
        print("✅ 圖片已上傳成功！imgBB 連結：", image_url)
        return image_url
    else:
        print("❌ 上傳失敗：", response.status_code, response.text)
        return None


# 載入 .env 檔案中的環境變數
load_dotenv()
BING_U = os.getenv("BING_U")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

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

# 擷取 prompt 欄位
with open(os.path.join(TEXT_DIR, latest_file), "r", encoding="utf-8") as f:
    content = f.read()

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
    os.rename(
        os.path.join(OUTPUT_DIR, old_name),
        os.path.join(OUTPUT_DIR, new_name)
    )
    # 儲存圖片後
    image_path = os.path.join(OUTPUT_DIR, new_name)

    filename_without_ext = os.path.splitext(os.path.basename(image_path))[0]
    
    # 自動上傳到 imgBB
    imgbb_api_key = os.getenv("IMGBB_API_KEY")  # 建議從 .env 中讀取
    upload_to_imgbb(image_path, imgbb_api_key)

    print("✅ 圖片已上傳成功！imgBB!")


print("✅ 圖片已重新命名並儲存完成！")
