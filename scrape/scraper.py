import os
from influxdb import InfluxDBClient
import requests
import sys
import datetime
import time

import logging
logging.basicConfig()

class Database():
    client = None
    database = None

    def __init__(self, hostname="localhost", port=8086, username="root", password="root", database=None):
        self.client = InfluxDBClient(hostname, port, username, password, database)
        self.database = database

    def setDatabase(self, database):
        self.database = database;

    def writeTo(self, points=[], database=None, tags=None):
        if not database:
            database = self.database
        self.client.create_database(database)
        self.client.write_points(points, database=database, tags=tags)
        # Need to handle errors here: influxdb.exceptions.InfluxDBClientError


def scrapeValue(database, token):
    outdata = []
    try:
        logger.info("reading starts")
        URL = "https://monitor.balena-cloud.com/prometheus/api/v1/query?query=vpn_online_devices"
        cookies = dict(_oauth2_proxy=token)
        response = requests.get(URL, cookies=cookies)
        incoming = response.json()
        data = incoming['data']['result']
        readingtime = datetime.datetime.utcnow().isoformat()
        for m in data:
            outdata.append({
                "measurement": m['metric']['__name__'],
                "tags": {
                    "instance": m['metric']['instance'],
                },
                "fields": {
                    "value": int(m['value'][1]),
                },
                "time": datetime.datetime.utcfromtimestamp(m['value'][0]).isoformat()
            })
    except e:
        print("fail", e)
        pass
    if len(outdata) > 0:
        try:
            logger.debug(outdata)
            database.writeTo(points=outdata)
        except:
            logger.error("Couldn't write to database: ", sys.exc_info()[0])
    else:
        logger.debug("No data to write to the database")

if __name__ == "__main__":
    logger = logging.getLogger('sensor')
    if os.getenv('DEBUG', default=None):
        logger.setLevel(logging.DEBUG)

    influxdb_host = os.getenv('INFLUXDB_HOST')
    if not influxdb_host:
        logger.error("Need 'INFLUXDB_HOST' to set database to connect to")
    try:
        influxdb_port = int(os.getenv('INFLUXDB_PORT', default="8086"))
    except TypeError:
        influxdb_port = 8086
    except ValueError:
        logger.error("Value of 'INFLUXDB_PORT' is incorrect, not a number?")

    token = os.getenv('OAUTH_TOKEN')
    if not token:
        logger.error("Need 'OAUTH_TOKEN' to get access to the original data")

    database_name = os.getenv('DATABASE_NAME', default="prometheus")


    database = Database(hostname=influxdb_host, port=influxdb_port, database=database_name)

    interval = int(os.getenv("INTERVAL", default="5"))
    logger.debug("Measurement interval: {}s".format(interval))

    triggertime = time.monotonic()
    while True:
        triggertime = triggertime + interval
        if database and token:
            scrapeValue(database=database, token=token)
        sleeptime = triggertime - time.monotonic()
        if sleeptime > 0:
            time.sleep(sleeptime)
        else:
            # set up the reference again
            triggertime = time.monotonic()
