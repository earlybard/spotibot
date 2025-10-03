from enum import Enum
import json, logging, os, argparse

from telegram import Update, LinkPreviewOptions, Message
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import spotipy
from spotipy.oauth2 import SpotifyOAuth

parser = argparse.ArgumentParser()
parser.add_argument("-b", "--backlog", help="Parse file of chat history to process and add to the playlists", action="store_true")
parser.add_argument("-r", "--read", help="File to read containing telegram chat history")
parser.add_argument("-l", "--logging", help="Print to console when executing certain actions", action="store_true")

args = parser.parse_args()

scopes = ["user-library-read",
          "playlist-read-private",
          "playlist-read-collaborative",
          "playlist-modify-private",
          "playlist-modify-public"]

SPOTIFY_ID = os.getenv("SPOTIFY_ID")
SPOTIFY_SECRET = os.getenv("SPOTIFY_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SINGLES_PLAYLIST = os.getenv("SINGLES_PLAYLIST")
ALBUMS_PLAYLIST = os.getenv("ALBUMS_PLAYLIST")

class SaveStatus(Enum):
    NOT_TRACK = 0
    DUPLICATE_TRACK = 1
    DUPLICATE_ALBUM = 2
    ADDED_TRACK = 3
    ADDED_ALBUM = 4

SINGLES_PLAYLIST_TRACKS = []
ALBUMS_PLAYLIST_TRACKS = []


TRACK_URL = "https://open.spotify.com/track/"
ALBUM_URL = "https://open.spotify.com/album/"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET, redirect_uri=SPOTIFY_REDIRECT_URI, scope=scopes, show_dialog=False))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def add_track_to_playlist(trackLink: str):
    """
    Add a track or album to a playlist and return success/fail information
    """
    if args.logging: print("add_track_to_playlist", trackLink)
    
    global SINGLES_PLAYLIST_TRACKS
    global ALBUMS_PLAYLIST_TRACKS
    
    if trackLink.startswith(TRACK_URL):
        id = trackLink.split(TRACK_URL)[1].split("?")[0]
        if id not in SINGLES_PLAYLIST_TRACKS:
            sp.playlist_add_items(SINGLES_PLAYLIST, [trackLink])
            SINGLES_PLAYLIST_TRACKS.append(id)
            return SaveStatus.ADDED_TRACK
        else:
            return SaveStatus.DUPLICATE_TRACK
                   
    # full album, only add new entries
    if trackLink.startswith(ALBUM_URL):
        albumId = trackLink.split(ALBUM_URL)[1].split("?")[0]
        albumIds = sp.album_tracks(album_id=albumId, limit=50)["items"]
        anySaved = False
        for track in albumIds:
            if track["id"] not in ALBUMS_PLAYLIST_TRACKS:
                sp.playlist_add_items(ALBUMS_PLAYLIST, [track["id"]])
                ALBUMS_PLAYLIST_TRACKS.append(track["id"])
                anySaved = True
        if anySaved:
            return SaveStatus.ADDED_ALBUM
        else:
            return SaveStatus.DUPLICATE_ALBUM
                
    return SaveStatus.NOT_TRACK

async def print_track_details(uri, message: Message, duplicate: bool):
    track = sp.track(uri)
    await message.reply_markdown(
        f"*Track*: _{track['name']}_ by {track['artists'][0]['name']}\n\n---{' already' if duplicate else ''}" + 
        " added to [TECHIES](https://open.spotify.com/playlist/1T3VM24iUb9tRu63wo4oJX)---" + 
        f"\n\n*Album*: {track['album']['name']} - {track['album']['release_date']}",
        disable_notification=True, link_preview_options=LinkPreviewOptions(url=track['album']['images'][0]['url']))
    
async def print_album_details(uri, message: Message, duplicate: bool):
    album = sp.album(uri)
    await message.reply_markdown(
        f"*Album*: _{album['name']}_ by {album['artists'][0]['name']} - {album['release_date']}\n\n---{' already' if duplicate else ''}" +
        " added to [TECHIES_ALBUMS](https://open.spotify.com/playlist/0xOvlCuCSwZzpFKZdZrKLS)---",
        disable_notification=True, link_preview_options=LinkPreviewOptions(url=album['images'][0]['url']))

async def parse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if args.logging: print("parsing message")
    words = update.message.text.split()

    for word in words:
        status = add_track_to_playlist(word)
        if status is SaveStatus.ADDED_TRACK:
            await print_track_details(word, update.message)
            await update.message.set_reaction("❤")
            
        elif status is SaveStatus.DUPLICATE_TRACK:
            await print_track_details(word, update.message, True)
            await update.message.set_reaction("🙈")
            
        elif status is SaveStatus.ADDED_ALBUM:
            await print_album_details(word, update.message)
            await update.message.set_reaction("❤")
            
        elif status is SaveStatus.DUPLICATE_ALBUM:
            await print_album_details(word, update.message, True)
            await update.message.set_reaction("🙈")

def get_all_playlist_track_ids(playlist_id: str):
    
    """
    Gets a full list of tracks from the specified playlist
    """
    
    if args.logging: print("get_all_playlist_track_ids", playlist_id)
    
    # loop to get all tracks in the playlist (hard API limit of 100 per search)
    totalTracks = sp.playlist(playlist_id, fields="tracks.total")["tracks"]["total"]
    limit = 100
    
    # get remainder after last hundred
    totalSearches = 0 if totalTracks % limit == 0 else 1
    totalSearches += int(totalTracks / limit)
    searches = totalSearches
    
    fullTrackIds = []
    while searches != 0:
        if args.logging: print("remaining pages: ", searches)
        items = sp.playlist_items(playlist_id, limit=limit, offset=(totalSearches-searches)*limit, fields="items(track.id)")["items"]
        trackIds = list(map(lambda track: track["track"]["id"], items))

        fullTrackIds.extend(trackIds)
        searches -=1
        
    return fullTrackIds

def load_from_history_undestructively():
    """
    Run to check all links in a chat history dump and add to playlist in order of chat history if not present, without disrupting the existing playlist order
    """
    
    if args.logging: print("load_from_history_undestructively")
    filePath = "result.json"
    
    if args.read:
        filePath = args.read
    
    with open(filePath) as json_file:
        global SINGLES_PLAYLIST_TRACKS
        global ALBUMS_PLAYLIST_TRACKS
        
        data = json.load(json_file)["messages"]

        SINGLES_PLAYLIST_TRACKS = get_all_playlist_track_ids(SINGLES_PLAYLIST)
        ALBUMS_PLAYLIST_TRACKS = get_all_playlist_track_ids(ALBUMS_PLAYLIST)
        
            
        for message in data:
            for text in message["text"]:
                if not isinstance(text, str):
                    words = text["text"].split()
                else:
                    words = text.split()

                for word in words:
                    # single track, add to singles playlist
                    if word.startswith(TRACK_URL):
                        id = word.split(TRACK_URL)[1].split("?")[0]
                        if id not in SINGLES_PLAYLIST_TRACKS:
                            sp.playlist_add_items(SINGLES_PLAYLIST, [word])
                            SINGLES_PLAYLIST_TRACKS.append(id)
                    
                    # full album, only add new entries
                    if word.startswith(ALBUM_URL):
                        albumId = word.split(ALBUM_URL)[1].split("?")[0]
                        albumIds = sp.album_tracks(album_id=albumId, limit=50)["items"]
                        for track in albumIds:
                            if track["id"] not in ALBUMS_PLAYLIST_TRACKS:
                                sp.playlist_add_items(ALBUMS_PLAYLIST, [track["id"]])
                                ALBUMS_PLAYLIST_TRACKS.append(id)

if __name__ == '__main__':
    if args.backlog:
        load_from_history_undestructively()
    else:
        SINGLES_PLAYLIST_TRACKS = get_all_playlist_track_ids(SINGLES_PLAYLIST)
        ALBUMS_PLAYLIST_TRACKS = get_all_playlist_track_ids(ALBUMS_PLAYLIST)
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parse))
    application.run_polling()


def load_from_history():
    """
    Unused. Was run once to get all history.
    """
    with open("/Users/dylan/Downloads/result.json") as json_file:
        data = json.load(json_file)

        for message in data["messages"]:
            for text in message["text"]:

                if "text" in text:
                    words = text["text"].split()
                else:
                    words = text.split()

                for word in words:
                    if word.startswith("https://open.spotify.com/track"):
                        track = spotipy.track(word)

                        spotipy.playlist_remove_all_occurrences_of_items(SINGLES_PLAYLIST, [word])

                        spotipy.playlist_add_items(SINGLES_PLAYLIST, [word])