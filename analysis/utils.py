#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging

from pymongo import MongoClient

MONGODB_ENDPOINT = os.getenv("MONGODB_ENDPOINT")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")

log = logging.getLogger(__name__)

def connect_to_mongodb():
    log.info("Connecting to MongoDB")
    return MongoClient(
        MONGODB_ENDPOINT, username=MONGODB_USERNAME, password=MONGODB_PASSWORD
    )
