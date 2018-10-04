# Twitch-Clips

Can be called from command line or imported into another script.

    usage: clips.py [-h] -u USERS [USERS ...] [-b BUFFER] [-n] [-v] url

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
