import json
import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import spotipy
from spotipy.oauth2 import SpotifyOAuth

scopes = ["user-library-read",
          "playlist-read-private",
          "playlist-read-collaborative",
          "playlist-modify-private",
          "playlist-modify-public"]

SPOTIFY_ID = os.getenv("SPOTIFY_ID")
SPOTIFY_SECRET = os.getenv("SPOTIFY_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PLAYLIST = "1T3VM24iUb9tRu63wo4oJX"

spotipy = spotipy.Spotify(auth_manager=SpotifyOAuth(SPOTIFY_ID, SPOTIFY_SECRET, "http://localhost:9090", scope=scopes))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def parse(update: Update, context: ContextTypes.DEFAULT_TYPE):

    words = update.message.text.split()

    for word in words:
        if word.startswith("https://open.spotify.com/track"):

            track = spotipy.track(word)

            spotipy.playlist_remove_all_occurrences_of_items(PLAYLIST, [word])

            spotipy.playlist_add_items(PLAYLIST, [word])

            await update.message.reply_markdown(
                f"{track['name']} - {track['artists'][0]['name']}" +
                " added to [TECHIES](https://open.spotify.com/playlist/1T3VM24iUb9tRu63wo4oJX)",
                quote=False)


if __name__ == '__main__':
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

                        spotipy.playlist_remove_all_occurrences_of_items(PLAYLIST, [word])

                        spotipy.playlist_add_items(PLAYLIST, [word])
