from datetime import datetime, timedelta
from requests import Session
import argparse
import json
import logging
import re

logging.basicConfig(
    style="{",
    level=logging.INFO,
    format="[{levelname}] {asctime} {module} {message}",
    datefmt='%H:%M:%S'
)

info = {"client_id": "", "accounts": {}}
try:
    with open("info.json") as fp:
        info.update(json.load(fp))
except FileNotFoundError:
    with open("info.json", "w") as fp:
        json.dump(info, fp, indent=4, sort_keys=True)
        
if not info.get("client_id"):
    raise ValueError("client_id required in info.json file.")
    
session = Session()
# Temporary client_id until I can find what i need for permissions
session.headers["Client-ID"] = "kimne78kx3ncx6brgo4mv6wki5h1ko"
# session.headers["Client-ID"] = info["client_id"]

clip_re_1 = re.compile(r"https://clips.twitch.tv/(?P<clip_id>\w+).*")
clip_re_2 = re.compile(r"https://www.twitch.tv/\w+/clip/(?P<clip_id>\w+).*")
timestamp_re = re.compile(r"((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?")
vod_re = re.compile(r"https://www.twitch.tv/videos/(?P<vod_id>\d+)(\?t=)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?")
ctime_re = re.compile(r"(?P<years>\d{4})-(?P<months>\d\d)-(?P<days>\d\d) (?P<hours>\d\d):(?P<minutes>\d\d):(?P<seconds>\d\d) ?(?P<timezone>\w\w\w)?")

def update_accounts(account_names):
    new_accounts = set(account_names) - info["accounts"].keys()
    
    if new_accounts:
        url = "https://api.twitch.tv/helix/users"
        response = session.get(url, params={"login": new_accounts}).json()
        
        if response.get("error") == "Unauthorized":
            raise ValueError("Invalid client_id.")
            
        for item in response["data"]:
            info["accounts"][item["login"]] = item["id"]
            logging.info(f"New account: {item['login']}")
        
    with open("info.json", "w") as fp:
        json.dump(info, fp, indent=4, sort_keys=True)
        
    return set(account_names) - info["accounts"].keys()
    
def extract_timestamp(url):
    data = (vod_re.search(url) or clip_re_1.search(url) or clip_re_2.search(url) or ctime_re.search(url) or re.search(r".*")).groupdict()
    
    if data.get("vod_id"):
        url = "https://api.twitch.tv/helix/videos"
        response = session.get(url, params={"id": data["vod_id"]})
        created_at = response.json()["data"][0]["created_at"]
        
        return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ") + timedelta(
            hours=int(data["hours"] or 0),
            minutes=int(data["minutes"] or 0),
            seconds=int(data["seconds"] or 0)
        )
    
    if data.get("clip_id"):
        url = "https://gql.twitch.tv/gql"
        data = f'[{{"operationName":"ClipsFullVideoButton","variables":{{"slug":"{data["clip_id"]}"}},"extensions":{{"persistedQuery":{{"version":1,"sha256Hash":"d519a5a70419d97a3523be18fe6be81eeb93429e0a41c3baa9441fc3b1dffebf"}}}}}}]'
        
        response = session.post(url, data=data).json()[0]["data"]["clip"]
        
        offset = response["videoOffsetSeconds"]
        video_id = response["video"]["id"]
        
        return extract_timestamp(f"https://www.twitch.tv/videos/{video_id}") + timedelta(seconds=offset)
        
    if data.get("years"):
        return datetime(
            int(data["years"]),
            int(data["months"]),
            int(data["days"]),
            int(data["hours"]),
            int(data["minutes"]),
            int(data["seconds"])
        )
        
def search_video(time, name, buffer):
    url = "https://api.twitch.tv/helix/videos"
    parameters = {"type": "archive", "user_id": info["accounts"][name]}
    
    while True:
        response = session.get(url, params=parameters).json()
        
        for item in response["data"]:
            created = datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            extracted_duration = timestamp_re.search(item["duration"])
            duration = timedelta(
                hours=int(extracted_duration["hours"] or 0),
                minutes=int(extracted_duration["minutes"] or 0),
                seconds=int(extracted_duration["seconds"] or 0)
            )
            
            if created <= time < created + duration:
                result_url = [item["url"]]
                seconds = (time - created).seconds - buffer
                if seconds > 0:
                    result_url.append("?t=")
                    if seconds >= 3600:
                        hours, seconds = divmod(seconds, 3600)
                        result_url.extend((str(hours), "h"))
                    if seconds >= 60:
                        minutes, seconds = divmod(seconds, 60)
                        result_url.extend((str(minutes), "m"))
                    if seconds:
                        result_url.extend((str(seconds), "s"))
                return name, "".join(result_url)
            elif created + duration < time:
                return name, None
                
        if response["pagination"].get("cursor"):
            parameters["after"] = response["pagination"]["cursor"]
        else:
            return name, None
        
def main(url, names, buffer=10):
    # This accounts for the buffer Twitch already uses
    buffer -= 5
    
    video_timestamp = extract_timestamp(url)
    
    if video_timestamp:
        invalid_names = update_accounts(names)
        return [
            (name, "Invalid") if name in invalid_names else search_video(video_timestamp, name, buffer)
            for name in names
        ]
    else:
        logging.error("Invalid url.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument("url",
        help="clip or VOD url. Requires quotes ('')")
    parser.add_argument("users",
        help="username or multiple usernames separated by commas.")
    parser.add_argument("-buffer", type=int, default=10,
        help="Amount of time in seconds to offset the start.")
    
    args = parser.parse_args()
    
    for name, value in main(args.url, args.users.split(","), args.buffer):
        print(name, value)
