# =============================================================================
# Name: minimized_VMs.py
# 
# Author: Hassan Fares
# Github: https://github.com/hassanfarescodes
#
# Description: Minimal reverse proxy that simulates core idea/act of SpotProxy
# using Docker containers as simulated spot VMs with dynamic backend rotation.
# =============================================================================

import os
import secrets
import logging
import aiohttp
import docker
import asyncio
from aiohttp import web
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true', help='Enable debug mode')                # -d argument for debug
args = parser.parse_args()

debug_mode = args.d

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[38;5;244m",                                                # Grey
        logging.INFO: "\033[38;5;231m",                                                 # White
        logging.WARNING: "\033[38;5;220m",                                              # Yellow
        logging.ERROR: "\033[38;5;196m",                                                # Bright red
        logging.CRITICAL: "\033[1;38;5;196m",                                           # Bright bold red
    }
    RESET = "\033[0m"

    def format(self, record):                                                           # Output format and colors
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

# Set up logger
handler = logging.StreamHandler()                                                       # Log formatting
formatter = ColorFormatter("%(asctime)s %(levelname)s %(message)s", 
                           "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.handlers = []                                                                    # Clear existing handlers
logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
logger.addHandler(handler)


DOCKER_IMAGE = "nginx"                                                                  # Service that will be running in the VMs
NUM_CONTAINERS = 6                                                                      # Number of VMs
PROXY_PORT = int(os.getenv("MINIMIZED_PORT", "8080"))                                   # Get MINIMIZED_PORT env variable, if not found then set to 8080
BASE_PORT = 8000

class ProxyStatus:
    def __init__(self, base_port):
        self.target_port = base_port                                                    # Base port + Number of containers = range of the ports
        self.active_container = None                                                    # Currently active container (port responsible for simulating different VMs) 


PROXY_STATE = ProxyStatus(base_port=8000)                                               # Object used to keep track of updating variables responsible for container statuses


docker_client = docker.from_env()                                                       # Allow docker to read/manage env variables

def configure_containers():                                                             # Deletes older containers and creates new ones
    for container in range(NUM_CONTAINERS):

        port = BASE_PORT + container                                                    # Port assigned to each container
        uname = f"Container-{container}"
        
        try:
            docker_client.containers.get(uname).stop()                                  # Delete containers
            docker_client.containers.get(uname).remove()
        
        except docker.errors.NotFound:                                                  # Skip "not found" errors
            pass

        docker_client.containers.run ( 
                                       DOCKER_IMAGE,                                    # Generate docker containers with configured settings
                                       name = uname,
                                       ports = {"80/tcp" : port},
                                       detach = True
                                     )

def change_container():                                                                 # Changes containers
    index = secrets.randbelow(NUM_CONTAINERS)                                           # Secure Index responsible for shuffling VMs
    PROXY_STATE.target_port = BASE_PORT + index
    PROXY_STATE.active_container = f"http://localhost:\033[38;5;46m{PROXY_STATE.target_port}"

    logging.info (f"[+] Switching active VM to {PROXY_STATE.active_container}")


async def shuffle_loop():                                                               # Shuffles between containers
    while True:
        await asyncio.sleep(15)                                                         # Every 15 seconds, the container changes
        change_container()

async def request_manager(request):                                                     # Handles requests and forwards data
    PROXY_STATE.target_url = PROXY_STATE.active_container + request.path_qs             # Forwards path to actual target url
    logging.info (f"{request.method} {request.path_qs} to {PROXY_STATE.target_url}")
    uheaders = dict(request.headers)
    uheaders.pop("Host", None)                                                          # Remove Host header if it exists

    async with aiohttp.ClientSession() as session:                                      # Define a session
        async with session.request (
                                     method = request.method,                           # Configure session with these settings
                                     url = PROXY_STATE.target_url,
                                     headers = uheaders,                                # Carry headers
                                     data = await request.read(),                       # Preserve other headers
                                     allow_redirects = False,
        ) as resp:
              body = await resp.read()                                                  # Parse entire body of header
              resp_headers = dict(resp.headers)
              resp_headers["Proxied-By"] = "minimized_VMs"                              # Add this header to indicate forwarding
              return web.Response(body = body,
                            status = resp.status, headers = resp_headers)


async def health(request):                                                              # Used to check if server is online
    return web.Response(text="OK")

async def start_bg_tasks(app):                                                          # Start up background functions
    configure_containers()
    change_container()
    app['shuffle'] = asyncio.create_task(shuffle_loop())



async def cleanup_bg_tasks(app):                                                        # Clean up and delete background functions
    app['shuffle'].cancel()
    for container in range(NUM_CONTAINERS):
        uname = f"Container-{container}"
        try:
            docker_client.containers.get(uname).stop()
            docker_client.containers.get(uname).remove()
        except docker.errors.NotFound:
            continue

app = web.Application()                                                                 # Initiate app object
app.router.add_get("/healthz", health)                                                  # /healthz --> health
app.router.add_route("*", "/{tail:.*}", request_manager)                                # /any --> request_manager
app.on_startup.append(start_bg_tasks)                                                   # start background tasks
app.on_cleanup.append(cleanup_bg_tasks)                                                 # cleanup background tasks

if __name__ == "__main__":
    logging.info(f"[!] Proxy running on port \033[38;5;46m{PROXY_PORT}")                # Start server
    web.run_app(app, host="0.0.0.0", port=PROXY_PORT)

