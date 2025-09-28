import requests
import time
from datetime import datetime
import threading
from flask import Flask

# ==== Flask dummy server ====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Both workers running in background"

# ==== Common User ID ====
USER_ID = 5531217637

# ==== Worker 1 Config (Scointasks - 10 requests/hour) ====
URL1 = "https://scointasks.top/scratch/api/watch-ad.php"
REQUESTS_PER_HOUR_1 = 10  # Changed to 10 as required
DELAY_BETWEEN_REQUESTS_1 = 360  # 6 minutes between requests for 10 per hour

headers1 = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/json',
    'Cookie': 'video_ad_watched=2025-09-28',
    'Origin': 'https://scointasks.top',
    'Referer': 'https://scointasks.top/scratch/index.html',
    'Sec-Ch-Ua': '"Microsoft Edge";v="140", "Chromium";v="140", "Microsoft Edge WebView2";v="140", "Not=A?Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0'
}

# ==== Worker 2 Config (Shibaadearner - 15 requests/hour) ====
URL2 = "https://shibaadearner.top/scratch/api/watch-ad.php"
REQUESTS_PER_HOUR_2 = 15
DELAY_BETWEEN_REQUESTS_2 = 240  # 4 minutes between requests for 15 per hour

headers2 = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/json',
    'Cookie': 'video_ad_watched=2025-09-28',
    'Origin': 'https://shibaadearner.top',
    'Referer': 'https://shibaadearner.top/scratch/',
    'Sec-Ch-Ua': '"Microsoft Edge";v="140", "Chromium";v="140", "Microsoft Edge WebView2";v="140", "Not=A?Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0'
}

# ==== Worker 1 Functions (Scointasks) ====
def send_request_worker1():
    try:
        response = requests.post(URL1, headers=headers1, json={"user_id": USER_ID})
        if response.status_code == 200:
            data = response.json()
            print(f"[Worker1-Scointasks] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Success!")
            print(f"  Status: {data.get('status')}")
            print(f"  Message: {data.get('message')}")
            print(f"  New Balance: {data.get('new_balance')}")
            print(f"  Watches This Hour: {data.get('watches_this_hour')}")
            print(f"  Earned: {data.get('earned')}")
            print("-" * 50)
        else:
            print(f"[Worker1-Scointasks] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error: Status Code {response.status_code}")
    except Exception as e:
        print(f"[Worker1-Scointasks] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Request failed: {e}")

def worker1_loop():
    print("[Worker1-Scointasks] Background worker started. Script will run continuously.")
    while True:
        start_time = time.time()
        print(f"\n[Worker1-Scointasks] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting new hour cycle...")

        for i in range(REQUESTS_PER_HOUR_1):
            print(f"\n[Worker1-Scointasks] Sending request {i+1}/{REQUESTS_PER_HOUR_1}")
            send_request_worker1()
            if i < REQUESTS_PER_HOUR_1 - 1:
                print(f"[Worker1-Scointasks] Waiting {DELAY_BETWEEN_REQUESTS_1} seconds before next request...")
                time.sleep(DELAY_BETWEEN_REQUESTS_1)

        time_spent = time.time() - start_time
        remaining_time = 3600 - time_spent
        if remaining_time > 0:
            print(f"\n[Worker1-Scointasks] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Completed {REQUESTS_PER_HOUR_1} requests.")
            print(f"[Worker1-Scointasks] Waiting {int(remaining_time)} seconds ({remaining_time/60:.1f} minutes) until next hour...")
            time.sleep(remaining_time)

# ==== Worker 2 Functions (Shibaadearner) ====
def send_request_worker2():
    try:
        response = requests.post(URL2, headers=headers2, json={"user_id": USER_ID})
        if response.status_code == 200:
            data = response.json()
            print(f"[Worker2-Shibaadearner] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Success!")
            print(f"  Status: {data.get('status')}")
            print(f"  Message: {data.get('message')}")
            print(f"  New Balance: {data.get('new_balance')}")
            print(f"  Watches This Hour: {data.get('watches_this_hour')}")
            print(f"  Earned: {data.get('earned')}")
            print("-" * 50)
        else:
            print(f"[Worker2-Shibaadearner] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error: Status Code {response.status_code}")
    except Exception as e:
        print(f"[Worker2-Shibaadearner] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Request failed: {e}")

def worker2_loop():
    print("[Worker2-Shibaadearner] Background worker started. Script will run continuously.")
    while True:
        start_time = time.time()
        print(f"\n[Worker2-Shibaadearner] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting new hour cycle...")

        for i in range(REQUESTS_PER_HOUR_2):
            print(f"\n[Worker2-Shibaadearner] Sending request {i+1}/{REQUESTS_PER_HOUR_2}")
            send_request_worker2()
            if i < REQUESTS_PER_HOUR_2 - 1:
                print(f"[Worker2-Shibaadearner] Waiting {DELAY_BETWEEN_REQUESTS_2} seconds before next request...")
                time.sleep(DELAY_BETWEEN_REQUESTS_2)

        time_spent = time.time() - start_time
        remaining_time = 3600 - time_spent
        if remaining_time > 0:
            print(f"\n[Worker2-Shibaadearner] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Completed {REQUESTS_PER_HOUR_2} requests.")
            print(f"[Worker2-Shibaadearner] Waiting {int(remaining_time)} seconds ({remaining_time/60:.1f} minutes) until next hour...")
            time.sleep(remaining_time)

# ==== Entry point ====
if __name__ == "__main__":
    # Start Worker 1 thread (Scointasks - 10 requests/hour)
    t1 = threading.Thread(target=worker1_loop)
    t1.daemon = True
    t1.start()
    
    # Start Worker 2 thread (Shibaadearner - 15 requests/hour)
    t2 = threading.Thread(target=worker2_loop)
    t2.daemon = True
    t2.start()
    
    print("Both workers started successfully!")
    print("Worker1 (Scointasks): 10 requests per hour")
    print("Worker2 (Shibaadearner): 15 requests per hour")
    
    # Flask server to keep Render happy
    app.run(host="0.0.0.0", port=10000)