'''
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
'''

import socket
import select
import json
import string
import time
import signal
import sys
import manager
import connection
import proxy as Proxy
import threading
import log as Log
import share_stats
import control
import argparse


def signal_handler(signal, frame):
    shutdown = True
    controller.shutdown = True
    log.info('exit')
    if pool:
        pool.shutdown(0)
        pool.close()
    for c in proxies.list():
        proxies.del_proxy(c)
    time.sleep(1)
    sys.exit(0)

def parse_args():
    parser = argparse.ArgumentParser(
        description='Stratum mining relay proxy')
    parser.add_argument(
        '-s',
        dest='pool',
        type=str,
        default="mine.magicpool.org",
        help='Hostname of stratum mining pool')
    parser.add_argument(
        '-t',
        dest='port',
        type=int,
        default=3333,
        help='Port of Stratum mining pool')
    parser.add_argument(
        '-l',
        dest='listen',
        type=str,
        default='0.0.0.0',
        help='IP to listen for incomming connections (miners)')
    parser.add_argument(
        '-p',
        dest='listen_port',
        type=int,
        default=3333,
        help='Port to listen on for incoming connections')
    parser.add_argument(
        '-c',
        dest='control',
        type=str,
        default='127.0.0.1',
        help='IP to listen for incomming control remote management')
    parser.add_argument(
        '-x',
        dest='control_port',
        type=int,
        default=2222,
        help='Control port to listen for orders')
    parser.add_argument(
        '-o',
        dest='log',
        type=str,
        default=None,
        help='File to store logs')
    parser.add_argument(
        '-q',
        dest='quiet',
        action="store_true",
        help='Enable quite mode, no stdout output')
    parser.add_argument(
        '-v',
        dest='verbose',
        type=int,
        default=3,
        help='Verbose level from 0 to 4')
    return parser.parse_args()

args = parse_args()
shutdown = False
signal.signal(signal.SIGINT, signal_handler)

# Set log stuff
Log.verbose = args.verbose
Log.filename = args.log
Log.stdout = not args.quiet
log = Log.Log('main')

# Share statistics module
shares = share_stats.Shares()

# Start proxy cleaner thread
proxies = Proxy.ProxyDB()
t = threading.Thread(target=proxies.cleaner, args=[])
t.daemon = True
t.start()

# Set and start control thread
controller = control.Control(proxydb=proxies, sharestats=shares)
controller.listen_ip = args.control
controller.listen_port = args.control_port
controller.poolmap['pool'] = args.pool
controller.poolmap['port'] = args.port
t = threading.Thread(target=controller.start, args=[])
t.daemon = True
t.start()

# Start listening for incoming connections
server_listen = connection.Server(args.listen, args.listen_port)


while not shutdown:
    # Wait for client connection
    miner = server_listen.listen()
    pool_connection = connection.Client(
        controller.poolmap['pool'], controller.poolmap['port'])
    pool = pool_connection.connect()
    proxy = Proxy.Proxy(pool, sharestats=shares)
    proxy.add_miner(miner)
    t = threading.Thread(target=proxy.start, args=[])
    t.daemon = True
    t.start()
    proxies.add_proxy(proxy, t)
