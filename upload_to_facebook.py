import os
import time
import requests
from datetime import datetime, timedelta
import json

# Facebook credentials
ACCESS_TOKEN = "EAAOwGHUinK8BO4mBv197so8P2ZC2oYq8HIMkZCwXeoKSL3CZAgswMf2TWl9uaAQJZBFT6yro9XrNQOgAM0RMkmMviOZA614oQEWVX2ZC9pvSctZARV4ynmzg5SI8BYrilyrQOtaCa0wjG6txHsqPZA9HZAsL5QDFxwX7V774YTH0zXLqdIDKSAE4DRGh9MZBPHr6YZD"
PAGE_ID = "104599939083967"
DOWNLOAD_DIR = "downloads"
NEW_VIDEOS_FILE = "new_videos.txt"
METADATA_FILE = "video_metadata.json"

# Upload video to Facebook
def schedule_video_to_facebook(video_path, title, description, scheduled_time):
    url = f"https://graph.facebook.com/v12.0/{PAGE_ID}/videos"
    params = {
        'access_token': ACCESS_TOKEN,
        'title': title,
        'description': description,
        'published': 'false',  # Set to false to schedule the post
        'scheduled_publish_time': scheduled_time
    }
    files = {
        'source': open(video_path, 'rb')
    }
    response = requests.post(url, params=params, files=files)
    return response.json()

# Load metadata for specific video
def load_metadata(video_id):
    with open(METADATA_FILE, 'r') as file:
        data = json.load(file)
        for video in data:
            if video['video_id'] == video_id:
                return video
    return None

# Main function
def main():
    current_time = datetime.now()
    one_hour = timedelta(hours=1)

    with open(NEW_VIDEOS_FILE, 'r') as file:
        new_videos = [line.strip() for line in file.readlines()]

    for video_id in new_videos:
        metadata = load_metadata(video_id)
        if metadata:
            video_path = metadata['video_path']
            title = metadata['title']
            author = metadata['author']
            description = f"{title}\n\nCredits: @{author}"

            scheduled_time = int((current_time + one_hour).timestamp())

            fb_response = schedule_video_to_facebook(video_path, title, description, scheduled_time)

            if 'id' in fb_response:
                fb_video_id = fb_response['id']
                print(f"Scheduled video with ID: {fb_video_id} at {datetime.fromtimestamp(scheduled_time)}")
            else:
                print(f"Failed to schedule video: {video_path}")
                print(f"Response: {fb_response}")

            current_time += one_hour
            time.sleep(2)  # Adding a small delay to avoid any rate limits

    # Clear new_videos.txt after scheduling
    open(NEW_VIDEOS_FILE, 'w').close()

if __name__ == "__main__":
    main()
