# Twitch-Clips

Have you ever watched a clip of 2 streamers playing and wanted to see the perspective of the other streamer, but don't want to go through the trouble of searching through their VODs?  
This script retrieves the time in a Twitch broadcaster's VOD that matches the time a Twitch clip was recorded or the url+timestamp of another Twitch VOD.

Provide client_id in info.json before use.

Command line:
    
    usage: clips.py [-h] [-url URL] [-u USERS] [-b BUFFER] [-n] [-v]

    optional arguments:
      -h, --help            show this help message and exit
      -url URL              clip or VOD url. Requires quotes ('') if url contains
                            an ampersand (&).
      -u USERS, --users USERS
                            a single username or multiple usernames separated by
                            commas.
      -b BUFFER, --buffer BUFFER
                            amount of time in seconds to set back the offest.
      -n, --nocache         if this flag is specified, usernames will not be
                            cached.
      -v, --verbose         show extra info.
      
CLI Example:

    D:\Twitch_clips>python -url clips.py https://clips.twitch.tv/ZanyVenomousWasabiWow -u singsing,carn_,rime_
    singsing https://www.twitch.tv/videos/316172110?t=7h58m6s
    carn_    https://www.twitch.tv/videos/316173396?t=7h52m52s
    rime_    Not found

If URL and USERS and BUFFER is not provided. this will open the Tkinter GUI.
