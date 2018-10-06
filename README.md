# Twitch-Clips

A script that retrieves the time in a Twitch broadcaster's VOD that matches the time a Twitch clip was created or the url+timestamp of another Twitch VOD.

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
      
CLI Example:

    D:\Twitch_clips>python clips.py https://clips.twitch.tv/ZanyVenomousWasabiWow -u singsing carn_ rime_
    singsing https://www.twitch.tv/videos/316172110?t=28686s
    carn_    https://www.twitch.tv/videos/316173396?t=28372s
    rime_    Not found

Python script:

    from clips import get_videos
    
    url = "https://www.twitch.tv/videos/<video_id>?t=1h2m3s"
    users = ["user1", "user2"]
    
    results = get_videos(url, users, buffer=0)
