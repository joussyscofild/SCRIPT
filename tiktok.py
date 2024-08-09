import http.client
import json
import time
import os
import requests
import urllib.parse
from datetime import datetime, timedelta

# Set up RapidAPI credentials
RAPIDAPI_KEY = "your_rapid-api-key"
RAPIDAPI_HOST = "tiktok-api15.p.rapidapi.com"
DOWNLOAD_DIR = "downloads"
TRACKED_FILE = "downloaded_videos.txt"
METADATA_FILE = "video_metadata.json"

# Facebook credentials
ACCESS_TOKEN = "your-acess-token"
PAGE_ID = "your-page-ID"

# Ensure the necessary directories and files exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
for file in [TRACKED_FILE, METADATA_FILE]:
    if not os.path.exists(file):
        open(file, 'a').close()

# Load already downloaded video IDs
def load_downloaded_videos():
    with open(TRACKED_FILE, 'r') as file:
        return set(file.read().splitlines())

# Save new downloaded video IDs
def save_downloaded_video(video_id):
    with open(TRACKED_FILE, 'a') as file:
        file.write(f"{video_id}\n")

# Save video metadata
def save_video_metadata(metadata):
    with open(METADATA_FILE, 'r+') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = []
        data.append(metadata)
        file.seek(0)
        json.dump(data, file, indent=4)

# Download content from a URL
def download_content(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Downloaded {filename}")
    else:
        print(f"Failed to download {filename} with status code {response.status_code}")

# Fetch video information
def fetch_videos_by_keyword(keyword, count=10, cursor=0, language='en'):
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"/index/Tiktok/searchVideoListByKeywords?keywords={encoded_keyword}&count={count}&cursor={cursor}&language={language}"
    conn.request("GET", url, headers=headers)
    res = conn.getresponse()
    data = res.read()
    return json.loads(data.decode("utf-8"))

# Initialize upload session for Facebook reel
def initialize_upload_session():
    url = f"https://graph.facebook.com/v20.0/{PAGE_ID}/video_reels"
    params = {
        "upload_phase": "start",
        "access_token": ACCESS_TOKEN
    }
    response = requests.post(url, params=params)
    return response.json()

# Upload video to Facebook
def upload_video_to_facebook(video_path, video_id, upload_url):
    with open(video_path, 'rb') as video_file:
        file_size = os.path.getsize(video_path)
        headers = {
            "Authorization": f"OAuth {ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size)
        }
        response = requests.post(upload_url, headers=headers, data=video_file)
    return response.json()

# Schedule reel on Facebook
def schedule_reel(video_id, title, description, author, scheduled_publish_time):
    full_description = f"{title}\n\n{description}\n\nCredits: @{author}"
    url = f"https://graph.facebook.com/v20.0/{PAGE_ID}/video_reels"
    params = {
        "access_token": ACCESS_TOKEN,
        "video_id": video_id,
        "upload_phase": "finish",
        "video_state": "SCHEDULED",
        "description": full_description,
        "title": title,
        "scheduled_publish_time": int(scheduled_publish_time.timestamp())
    }
    response = requests.post(url, params=params)
    return response.json()

# Process a single video
def process_video(video, downloaded_videos, scheduled_time):
    video_id = video.get("aweme_id")
    if video_id in downloaded_videos:
        return False  # Return False indicating the video was skipped

    play_url = video.get("play")
    title = video.get("title", "TikTok Video")
    description = video.get("description", "")
    author = video.get("author", {}).get("nickname", "Unknown")

    if play_url:
        video_dir = os.path.join(DOWNLOAD_DIR, video_id)
        os.makedirs(video_dir, exist_ok=True)

        play_path = os.path.join(video_dir, "video.mp4")
        download_content(play_url, play_path)

        upload_session = initialize_upload_session()
        if "video_id" in upload_session and "upload_url" in upload_session:
            upload_result = upload_video_to_facebook(play_path, upload_session["video_id"], upload_session["upload_url"])
            if upload_result.get("success"):
                publish_result = schedule_reel(upload_session["video_id"], title, description, author, scheduled_time)
                if publish_result.get("success"):
                    print(f"Successfully scheduled reel with video ID: {upload_session['video_id']} for {scheduled_time}")
                else:
                    print(f"Failed to schedule reel with video ID: {upload_session['video_id']} - {publish_result}")
            else:
                print(f"Failed to upload video with video ID: {upload_session['video_id']} - {upload_result}")
        else:
            print(f"Failed to initialize upload session for: {title}")

        metadata = {
            "video_id": video_id,
            "title": title,
            "author": author,
            "video_path": play_path,
            "scheduled_time": scheduled_time.isoformat()
        }

        save_video_metadata(metadata)
        save_downloaded_video(video_id)
        return True  # Return True indicating the video was processed

# Main function
def main():
    keyword = input("Enter the keyword to search for: ")
    num_videos = int(input("Enter the number of videos to scrape: "))
    language = input("Enter the language code (e.g., 'en' for English, 'es' for Spanish): ")
    cursor = 0
    has_more = True
    scraped_count = 0

    downloaded_videos = load_downloaded_videos()

    print(f"Starting to scrape videos for keyword: {keyword}")

    # Schedule starting from the next full hour
    now = datetime.now()
    if now.minute == 0:
        scheduled_time = now + timedelta(hours=1)
    else:
        scheduled_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    while has_more and scraped_count < num_videos:
        response = fetch_videos_by_keyword(keyword, count=min(num_videos-scraped_count, 20), cursor=cursor, language=language)

        if response.get("code") != 0:
            print(f"Error: {response.get('msg')}")
            break

        videos = response.get("data", {}).get("videos", [])
        cursor = response.get("data", {}).get("cursor", 0)
        has_more = response.get("data", {}).get("hasMore", False)

        for video in videos:
            if scraped_count >= num_videos:
                break
            if process_video(video, downloaded_videos, scheduled_time):
                scraped_count += 1
                scheduled_time += timedelta(hours=1)  # Increment the scheduled time by one hour for the next video

        if not has_more:
            break
        time.sleep(1)  # Reduced delay between batches

    print("Scraping and scheduling completed.")

if __name__ == "__main__":
    main()
