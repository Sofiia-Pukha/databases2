import psycopg2
import redis
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "university",
    "user": "postgres",
    "password": "",
}

MONGO_URI = "mongodb://localhost:27017"


def get_connection(autocommit=False):
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **DB_CONFIG)
    conn.autocommit = autocommit
    with conn.cursor() as cur:
        cur.execute("SET search_path TO lab2")
    if not autocommit:
        conn.commit()
    return conn


def get_mongo_db():
    return MongoClient(MONGO_URI)["university"]


def get_redis():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)
