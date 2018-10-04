import argparse
import configparser
import datetime
import logging
import re
import requests

config = configparser.ConfigParser({"client_id": ""})
config.read("info.ini")

if not config["DEFAULT"].get("client_id"):
    with open("info.ini", "w") as fp:
        config.write(fp)
    raise KeyError("client_id parameter missing in info.ini")
    
session = requests.Session()
session.headers["Client-ID"] = config["DEFAULT"]["client_id"]

accounts = dict(u.split(",") for u in config["DEFAULT"]["accounts"].split("\n"))
opts = {}

def update_users(account_names):
    """
    
    Updates the cache file of usernames and user ids
    
    Parameters:
     account_names: username or list of usernames
    
    Returns:
     None
    
    """
    
    if opts.get("nocache"):
        return
    
    if isinstance(account_names, str):
        account_names = (account_names,)
    
    new_accounts = {s.lower() for s in account_names} - accounts.keys()
    
    if new_accounts:
        logging.info(f"Saving new users: {' '.join(new_accounts)}")
        
        url = "https://api.twitch.tv/helix/users"
        response = session.get(url, params={"login": new_accounts}).json()
        
        accounts.update({item["display_name"].lower(): item["id"] for item in response["data"]})

        config["DEFAULT"]["accounts"] = "\n".join([f"{k},{v}" for k, v in accounts.items()])
        
        with open("info.ini", "w") as fp:
            config.write(fp)

def get_time(video_id):
    """
    
    Uses the api to get the time the video was created.
    
    Parameters:
     video_id: if of the VOD.
     
    Returns:
     datetime: when the VOD was created.
    
    """
    
    logging.info(f"Getting video time: {video_id}")
    
    url = "https://api.twitch.tv/helix/videos"
    
    response = session.get(url, params={"id": video_id}).json()
    created_at = response["data"][0]["created_at"]
    
    return datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    
def parse_offset(time):
    duration = re.search(r"((\d+)h)?((\d+)m)?((\d+)s)?", time)

    return datetime.timedelta(
        hours=int(duration[2] or 0),
        minutes=int(duration[6] or 0),
        seconds=int(duration[4] or 0)
    )

def search_videos(name, time, buffer):
    """
    
    Searches the user's past broadcasts for a video that was recorded 
    during a specific time.
    
    Parameters:
     name: case insensitive username of the user to search for videos.
     time: datetime to search for.
     buffer: amount of time in seconds to take away from the offset.
     
    Returns:
     string: url of VOD with offset or "Not found".
    
    """
    
    logging.info(f"Searching: name={name} time={time} buffer={buffer}")
    
    url = "https://api.twitch.tv/helix/videos"
    parameters = {
        "type": "archive",
        "user_id": accounts[name.lower()]
    }
    
    while True:
        response = session.get(url, params=parameters).json()

        if response.get("data") is None:
            return "Not found"

        for item in response["data"]:
            created = datetime.datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            duration = parse_offset(item["duration"])

            if created <= time < created + duration:
                seconds = (time - created).seconds - buffer
                if seconds <= 0:
                    return f"{item['url']}"
                else:
                    return f"{item['url']}?t={seconds}s"
            elif created + duration < time:
                return "Not found"

        parameters["after"] = response["pagination"]["cursor"]

def get_videos(clip_url, account_names, buffer=0):
    """
    
    Get a list of videos that were recorded at the time clip_url was created.
    
    Parameters:
     clip_url: full of clip or VOD url with offset
     account_names: username or list of usernames to search for videos.
     buffer: amount of time in seconds to take away from the offset.
     
    Returns:
     list of (username, url) tuples: If a video does not exist, url is "Not found".
    
    """
    
    if isinstance(account_names, str):
        account_names = (account_names,)
        
    update_users(account_names)
    
    if clip_url.startswith("https://clips.twitch.tv/"):
        """
        
        The old v2 API is used to get the time and offset that the clip 
        was created.
        
        The new API (https://api.twitch.tv/helix/clips) does not provide 
        the offset (yet 04/10/18).
        
        The VOD offset time cannot be inferred from the created_at field.
        
        """
        
        url = f"https://clips.twitch.tv/api/v2/clips/{clip_url[24:]}"
        
        response = requests.get(url).json()
        
        if "vod_url" in response:
            time = get_time(response["vod_id"])
            time += datetime.timedelta(0, response["vod_offset"])
            
            return [(name, search_videos(name, time, buffer)) for name in account_names]
    elif clip_url.startswith("https://www.twitch.tv/videos/"):
        time = get_time(re.search(r"\d+", clip_url).group())
        
        if "?t=" in clip_url:
            time += parse_offset(clip_url.split("=")[1])
        
        return [(name, search_videos(name, time, buffer)) for name in account_names]
        
    return [(name, "Not found") for name in account_names]
    
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("url",
        help="Clip or VOD url.")
    parser.add_argument("-u", "--users", nargs="+", required=True,
        help="A single username or multiple usernames separated by a space.")
    parser.add_argument("-b", "--buffer", type=int, default=0,
        help="Amount of time in seconds to set back the offset.")
    parser.add_argument("-n", "--nocache", action="store_true",
        help="If this flag is specified, usernames will not be cached.")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="Show debug info.")
    
    args = parser.parse_args()
    
    opts["nocache"] = args.nocache
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    
    return (args.url, args.users, args.buffer)

if __name__ == "__main__":
    values = get_videos(*parse_args())
    column_width = max(len(x[0]) for x in values)
    print("\n".join([f"{user:<{column_width}} {url}" for user, url in values]))