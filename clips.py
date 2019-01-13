from tkinter import Entry, Frame, Menu, StringVar, TclError, Tk, ttk
import argparse
import datetime
import json
import logging
import queue
import re
import threading
import webbrowser

import requests

def load_settings():
    settings = {"client_id": "", "accounts": {}}
    try:
        with open("info.json") as fp:
            settings.update(json.load(fp))
    except FileNotFoundError:
        with open("info.json", "w") as fp:
            json.dump(settings, fp, indent=4, sort_keys=True)
    return settings
    
def update_users(account_names):
    new_accounts = set(account_names) - settings["accounts"].keys()
    
    if new_accounts:
        logging.info("Downloading new account data.")
        url = "https://api.twitch.tv/helix/users"
        response = session.get(url, params={"login": new_accounts}, timeout=2).json()
        
        if response.get("error") == "Unauthorized":
            raise ValueError("Invalid client_id.")
        
        for item in response["data"]:
            settings["accounts"][item["login"]] = item["id"]
        invalid = set(account_names) - settings["accounts"].keys()
            
        if not args.nocache:
            logging.info(f"Saving new users: {' '.join(new_accounts - invalid)}")
            with open("info.json", "w") as fp:
                json.dump(settings, fp, indent=4, sort_keys=True)
                
        return invalid
    return ()
    
def get_time(video_id):
    """Uses the api to get the time the video was created.
    
    Parameters:
     video_id: ID of the VOD.
     
    Returns:
     datetime: when the VOD was created.
    """
    
    logging.info(f"Getting video time start: {video_id}")
    
    url = "https://api.twitch.tv/helix/videos"
    parameters = {"id": video_id}
    response = session.get(url, params={"id": video_id}, timeout=2).json()
    created_at = response["data"][0]["created_at"]
    
    return datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    
def offset_to_timedelta(time):
    duration = re.search(r"((\d+)h)?((\d+)m)?((\d+)s)?", time)

    return datetime.timedelta(
        hours=int(duration[2] or 0),
        minutes=int(duration[4] or 0),
        seconds=int(duration[6] or 0)
    )
    
def get_videos(clip_url, account_names, buffer=0):
    logging.info("Getting clip data.")
    
    if clip_url.startswith("https://www.twitch.tv/videos/"):
            time = get_time(re.search(r"\d+", clip_url).group())
            url, *parameters = clip_url.split("?")
            
            if parameters:
                for parameter in parameters[0].split("&"):
                    if parameter.startswith("t="):
                        time += parse_offset(parameter.split("=")[1])
            
            return [(name, search_videos(name, time, buffer)) for name in account_names]
    else:
        if clip_url.startswith("https://clips.twitch.tv/"):
            url = f"https://api.twitch.tv/kraken/clips/{clip_url[24:]}"
        elif clip_url.startswith("https://www.twitch.tv/cryaotic/clip/"):
            url = f"https://api.twitch.tv/kraken/clips/{clip_url[36:]}"
        else:
            url = f"https://api.twitch.tv/kraken/clips/{clip_url}"
            
        """ The old v5 Kraken API is used to get the time and offset that 
        the clip was created.
        
        The new API (https://api.twitch.tv/helix/clips) does not provide 
        the offset (yet 11/01/19).
        
        The VOD offset time cannot be inferred from the created_at field.
        """
        
        response = session.get(url, timeout=2).json()
        
        if not response.get("vod"):
            return (None, None)
            
        if "vod" in response:
            time = get_time(response["vod"]["id"])
            time += datetime.timedelta(0, response["vod"]["offset"])
            
            return [(name, search_videos(name, time, buffer)) for name in account_names]
        
    return [(name, "Not found") for name in account_names]
    
def search_videos(name, time, buffer):
    """Searches the user's past broadcasts for a video that was recorded 
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
        "user_id": settings["accounts"][name]
    }
    
    while True:
        response = session.get(url, params=parameters, timeout=2).json()

        if response.get("data") is None:
            return "Not found"

        for item in response["data"]:
            created = datetime.datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            duration = offset_to_timedelta(item["duration"])

            if created <= time < created + duration:
                logging.info(f"Found: {name} {item['url']}")
                
                seconds = (time - created).seconds - buffer
                if seconds > 0:
                    item['url'] += "?t="
                    if seconds >= 3600:
                        hours, seconds = divmod(seconds, 3600)
                        item['url'] += f"{hours}h"
                    if seconds >= 60:
                        minutes, seconds = divmod(seconds, 60)
                        item['url'] += f"{minutes}m"
                    if seconds:
                        item['url'] += f"{seconds}s"
                        
                return item['url']
            elif created + duration < time:
                return "Not found"
                
        if response["pagination"].get("cursor"):
            parameters["after"] = response["pagination"]["cursor"]
        else:
            return "Not found"

def main(args):
    if args.url is None:
        logging.error("Url parameter missing.")
        return
    if args.users is None:
        logging.error("Users parameter missing.")
        return
        
    account_names = set(args.users.split(","))
    
    try:
        invalid = update_users(account_names)
            
        values = get_videos(args.url[0], account_names - invalid, args.buffer)
        if values == (None, None):
            raise ValueError("Invalid clip ID.")
        print()
        
        column_width = max(len(name) for name, result in values)
        for user, result in values:
            print(f"{user:<{column_width}} {result}")
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        logging.error("Connection error.")
    except ValueError as e:
        logging.error(e.args[0])
        
# Streamline Threads and Queues
class thread_manager(threading.Thread):
    def __init__(self, function):
        super().__init__()
        
        self.queue = queue.Queue()
        self.function = function
        
    def run(self):
        while True:
            if self.function(self.queue.get()):
                break
    
    def put(self, item):
        self.queue.put(item)
        
    def start(self):
        super().start()
        return self

def tree(parent, gridx, gridy, cs, ws, **frame_args):
    """
    
    parent: parent frame
    gridx: x position in parent frame
    gridy: y position in parent frame
    cs: list of column names
    ws: list of column widths
    **frame_args: extra arguments for container frame

    """
    
    parent.columnconfigure(gridx, weight=1)
    parent.rowconfigure(gridy, weight=1)

    tree_frame = Frame(parent)
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)
    tree_frame.grid(sticky="nwse", column=gridx, row=gridy, **frame_args)

    def scroll(sbar, first, last):
        """Hide and show scrollbar as needed."""
        first, last = float(first), float(last)
        if first <= 0 and last >= 1:
            sbar.grid_remove()
        else:
            sbar.grid()
        sbar.set(first, last)

    x = lambda f, l: scroll(xs, f, l)
    y = lambda f, l: scroll(ys, f, l)
    tv = ttk.Treeview(tree_frame, xscroll=x, yscroll=y)
    tv.grid(sticky="nwes")

    xs = ttk.Scrollbar(tree_frame, orient='horizontal', command=tv.xview)
    xs.grid(column=0, row=1, sticky="ew")

    ys = ttk.Scrollbar(tree_frame, orient='vertical', command=tv.yview)
    ys.grid(column=1, row=0, sticky="ns")

    style = ttk.Style()
    style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
    style.configure("Treeview", font=('Consolas', 10))

    tv.heading("#0", text=cs[0], anchor='w')
    tv.column("#0", stretch=0, anchor="w", minwidth=ws[0], width=ws[0])

    tv["columns"] = cs[1:]
    for i, w in zip(cs[1:-1], ws[1:-1]):
        tv.heading(i, text=i, anchor='w')
        tv.column(i, stretch=0, anchor='w', minwidth=w, width=w)

    if len(tv["columns"]) > 0:
        tv.heading(cs[-1], text=cs[-1], anchor='w')
        tv.column(cs[-1], stretch=1, anchor='w', minwidth=ws[-1], width=ws[-1])
    
    def select(args):
        item = tv.identify_row(args.y)
        if item:
            if tv.item(item, "tags"):
                tv.item(item, tags="")
            else:
                tv.item(item, tags="on")
        else:
            tv.selection_remove(tv.selection())
            
    def parse_values(values, n):
        if isinstance(values, str):
            values = (values,)
            
        if len(values) > n:
            return len(values[n])
            
        return 0
        
    def double(args):
        #if tv.identify("region", args.x, args.y) == "separator":
        column = tv.identify("column", args.x, args.y)
        if column == "#0":
            widths = [tv.column("#0")["minwidth"], *(len(tv.item(i, "text"))*7+24 for i in tv.get_children())]
        else:
            try:
                col = tv.column(column)
            except TclError:
                return
            else:
                widths = [col["minwidth"], *(parse_values(tv.item(i, "values"), int(column[1:])-1)*7+7 for i in tv.get_children())]
            
        tv.column(column, width=max(widths))
            
    tv.bind("<ButtonRelease-1>", select)
    tv.bind("<Double-Button-1>", double)

    return tv

class GUI(Tk):
    pad = {"padx": 5, "pady": 5}
    
    def __init__(self):
        super().__init__()
        
        self.title("Twitch Clips")
        self.geometry("500x250+550+300")
        self.attributes("-topmost", True)
        self.minsize(550, 350)
        
        self.current_url = ""
        
        self.top_var = StringVar()
        lbl = ttk.Label(self, width=70, justify="center", textvariable=self.top_var)
        lbl.grid(columnspan=2, **self.pad)
        
        top_frame = Frame(self)
        top_frame.grid(columnspan=2, sticky="nwes")
        top_frame.columnconfigure(1, weight=1)
        
        lbl = ttk.Label(top_frame, text="Enter names:")
        lbl.grid(sticky="w", **self.pad)
        
        self.user_var = StringVar()
        entry = Entry(top_frame, textvariable=self.user_var)
        entry.grid(column=1, row=0, sticky="we", **self.pad)
        entry.bind("<Return>", self.add)
        entry.focus()
        
        self.tv = tree(self, 0, 2, ("Name", "ID", "URL"), (100, 100, 200), columnspan=2, **self.pad)
        self.tv.bind("<Button-3>", self.popup)
        self.tv.tag_configure("on", background="aquamarine")
        
        self.search_btn = ttk.Button(self, text="Search", width=10, command=self.search)
        self.search_btn.grid(column=1, row=3, **self.pad)
        
        def delete():
            user = self.tv.selection()[0]
            del settings["accounts"][user]
            self.tv.delete(user)
        
        self.menu = Menu(self, tearoff=0)
        self.menu.add_command(label="  Open Url", command=self.web_open)
        self.menu.add_command(label="  Copy Url", command=self.copy)
        self.menu.add_command(label="Remove User", command=delete)
        
        self.log_var = StringVar()
        lbl = ttk.Label(self, textvariable=self.log_var)
        lbl.grid(column=0, row=3, sticky="we", **self.pad)
        
        self.event_thread = thread_manager(self.run).start()
        
        for name, user_id in settings["accounts"].items():
            self.tv.insert("", "end", name, text=name, values=(user_id,))
        
        self.after(100, self.loop)
        self.protocol("WM_DELETE_WINDOW", self.end)
        
    def popup(self, args):
        item = self.tv.identify_row(args.y)
        if item:
            if item not in self.tv.selection():
                self.tv.selection_set(item)
            self.menu.post(args.x_root, args.y_root)
            
    def copy(self):
        item = self.tv.item(self.tv.selection()[0], "values")
        if len(item) == 2:
            if item[1] != "Not found":
                self.clipboard_clear()
                self.clipboard_append(item[1])
        
    def add(self, args):
        user = self.user_var.get()
        if user:
            self.tv.insert("", "end", user, text=user, tags="on")
            self.user_var.set("")
            self.log_var.set(f"Added new user: {user}.")
        
    def search(self):
        self.event_thread.put("search")
        
    def run(self, command):
        if command == "search":
            self.search_btn["state"] = "disabled"
            try:
                for invalid_user in update_users(self.tv.get_children()):
                    self.tv.delete(invalid_user)
                for name, user_id in settings["accounts"].items():
                    self.tv.item(name, values=(user_id,))
                    
                selected = self.tv.tag_has("on")
                if not selected:
                    self.log_var.set("No users selected.")
                    return
                
                self.log_var.set("Searching...")
                for name, result in get_videos(self.current_url, selected):
                    if result is None:
                        raise ValueError("Invalid clip ID.")
                    values = self.tv.item(name, "values")
                    self.tv.item(name, values=(*values, result))
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
                self.log_var.set("Connection error.")
            except ValueError as e:
                self.log_var.set(e.args[0])
            finally:
                self.search_btn["state"] = "enabled"
        elif command is None:
            return True
        
    def loop(self):
        try:
            clipboard = self.clipboard_get()
        except TclError:
            pass
        else:
            if "\n" not in clipboard and self.current_url != clipboard:
                self.current_url = clipboard
                self.top_var.set(clipboard)
        self.after(100, self.loop)
        
    def web_open(self):
        for item in self.tv.selection():
            item_info = self.tv.item(item)
            if item_info["values"][1:] and item_info["values"][1] != "Not found":
                webbrowser.open(item_info["values"][1])
        
    def end(self):
        self.event_thread.put(None)
        self.event_thread.join()
        
        with open("info.json", "w") as fp:
            json.dump(settings, fp, indent=4, sort_keys=True)
        
        self.destroy()

def parse_args():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-url", nargs=1,
        help="clip or VOD url. Requires quotes ('') if url contains an ampersand (&).")
    parser.add_argument("-u", "--users",
        help="a single username or multiple usernames separated by commas.")
    parser.add_argument("-b", "--buffer", type=int, default=0,
        help="amount of time in seconds to set back the offest.")
    parser.add_argument("-n", "--nocache", action="store_true",
        help="if this flag is specified, usernames will not be cached.")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="show extra info.")
    
    args = parser.parse_args()
        
    logging.basicConfig(
        style="{",
        level=logging.INFO if args.verbose else logging.WARNING,
        format="[{levelname}] {asctime} {module} {message}",
        datefmt='%H:%M:%S'
    )
    
    return args

if __name__ == "__main__":
    settings = load_settings()
    if settings["client_id"]:
        args = parse_args()
        session = requests.Session()
        session.headers["Client-ID"] = settings["client_id"]
        session.headers["Accept"] = "application/vnd.twitchtv.v5+json"
        if any((args.buffer, args.url, args.users)):
            main(args)
        else:
            GUI().mainloop()
    else:
        logging.warning("Missing client_id.")
