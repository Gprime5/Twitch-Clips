# Twitch-Clips

Can be called from command line or imported into another script.

Provide client_id in info.ini before use.

Command line:
    
    usage: clips.py [-h] url -u USERS [USERS ...] [-b BUFFER] [-n] [-v]

    positional arguments:
      url                   Clip or VOD url.

    optional arguments:
      -h, --help            show this help message and exit
      -u USERS [USERS ...], --users USERS [USERS ...]
                            A single username or multiple usernames separated by a
                            space.
      -b BUFFER, --buffer BUFFER
                            Amount of time in seconds to set back the offset.
      -n, --nocache         If this flag is specified, usernames will not be
                            cached.
      -v, --verbose         Show debug info.

Python script:

    from clips import get_videos
    
    url = "https://www.twitch.tv/videos/<video_id>?t=1h2m3s"
    users = ["user1", "user2"]
    
    results = get_videos(url, users, buffer=0)
