#
# Copyright (c) 2025 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import httpx
import json
import sys

from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("mqmcpserver")

# Configure logging
import os
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("log", "mqmcpserver.log"))
    ]
)

# Change this to point to your mqweb server
URL_BASE = "https://localhost:9443/ibmmq/rest/v3/admin/"

# Change these to a suitable user in your mqweb server
USER_NAME = "mqreader"
PASSWORD = "mqreader"

@mcp.tool()
async def dspmq() -> str:
    """List available queue managers and whether they are running or not
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }    
    
    url = URL_BASE + "qmgr/"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False,auth=auth) as client:
        try:            
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmq(response.content)
        except Exception as err:
            print(err, file=sys.stderr)
            return "Something went wrong!"
                        
# Put the output of for each queue manager on its own line, separated by ---                        
def prettify_dspmq(payload: str) -> str:
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput="\n---\n"
    for x in jsonOutput['qmgr']:
      prettifiedOutput += "name = " + x['name'] + ", running = " + x['state'] + "\n---\n"
    
    return prettifiedOutput
    
@mcp.tool()
async def runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    """Run an MQSC command against a specific queue manager

    Args:
        qmgr_name: A queue manager name   
        mqsc_command: An MQSC command to run on the queue manager   
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }
    
    data = "{\"type\":\"runCommand\",\"parameters\":{\"command\":\"" + mqsc_command + "\"}}"
    
    url = URL_BASE + "action/qmgr/" + qmgr_name + "/mqsc"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False,auth=auth) as client:
        try:            
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_runmqsc(response.content)
        except Exception as err:
            print(err, file=sys.stderr)
            return "Something went wrong!"
            
# Put the output of each MQSC command on its own line, separated by ---
# For the moment this will not work against z/OS queue managers which use a slightly different format.
def prettify_runmqsc(payload: str) -> str:
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput="\n---\n"
    for x in jsonOutput['commandResponse']:
      prettifiedOutput += x['text'][0] + "\n---\n"
    
    return prettifiedOutput    

if __name__ == "__main__":
    print("Starting MQ MCP Server...", file=sys.stderr)
    # Initialize and run the server on 127.0.0.1:8000
    mcp.run(transport='stdio')