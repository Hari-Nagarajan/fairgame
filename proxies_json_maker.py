#!/usr/bin/python
import json
import re
import sys


https = False
socks5 = False

while True:
    answer = input("Are your proxies https or socks5?: ")
    if answer.lower() == "https":
        https = True
        break
    if answer.lower() == "socks5":
        socks5 = True
        break
    else:
        print("Type in the correct type of Ctrl-C to exit\n")

proxies_regex = re.compile(r"(.*:.*):(.*:.*)", re.I | re.S)

with open(sys.argv[1], "r") as f:
    proxies_list = f.readlines()

proxies = list()

for proxy in proxies_list:
    match_object = re.match(proxies_regex, proxy)
    proxies.append(f"{match_object.group(2).strip()}@{match_object.group(1)}")

proxies_dict = {"proxies": []}

if https:
    for proxy in proxies:
        proxies_dict["proxies"].append(f"https://{proxy}")
if socks5:
    for proxy in proxies:
        proxies_dict["proxies"].append(f"socks5://{proxy}")

with open("proxies.json", 'w') as f:
    f.write(json.dumps(proxies_dict, indent=4))
    print("Conversion to json completed.")
