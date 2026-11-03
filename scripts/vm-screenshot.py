#!/usr/bin/env python3
"""Capture the emulated display through QMP before stopping a boot test."""
import json
from pathlib import Path
import socket
import sys

with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(10)
    client.connect(sys.argv[1])
    stream = client.makefile("rwb")
    json.loads(stream.readline())  # QMP greeting

    def command(name, arguments=None):
        request = {"execute": name}
        if arguments:
            request["arguments"] = arguments
        stream.write(json.dumps(request).encode() + b"\n")
        stream.flush()
        while True:
            reply = json.loads(stream.readline())
            if "error" in reply:
                raise RuntimeError(reply["error"])
            if "return" in reply:
                return

    command("qmp_capabilities")
    command("screendump", {"filename": str(Path(sys.argv[2]).resolve()), "format": "png"})
