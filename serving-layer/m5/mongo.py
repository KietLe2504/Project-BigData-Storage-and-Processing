from pymongo import MongoClient

from m5.config import Settings


def connect():
    settings = Settings.from_env()
    client = MongoClient(settings.uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    client.admin.command("ping")
    return client, client[settings.database]
