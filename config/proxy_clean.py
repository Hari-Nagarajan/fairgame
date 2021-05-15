#!/usr/bin/python
import json
import re

### This is from here: https://discordapp.com/channels/756730877509369906/839256456501919744/839506452279722004


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

proxies_regex = re.compile(r"(.*:.*)@(.*:.*)", re.I | re.S)

for i in range(4):
    j = i + 1

    with open("proxies." + str(j) + ".txt", "r") as f:
        proxies_list = f.readlines()

    proxies = list()

    print(proxies_list)
    for proxy in proxies_list:
        match_object = re.match(proxies_regex, proxy)
        if https:
            proxies.append(f"{match_object.group(1).strip()}@{match_object.group(2)}")
        if socks5:
            proxies.append(f"socks5://{match_object.group(2).strip()}@{match_object.group(1)}")

    proxies_dict = dict()

    if https:
        proxies_dict.update({"proxies": [ {"http": f"http://{proxy.rstrip()}",
                "https": f"https://{proxy.rstrip()}"} for proxy in proxies]})
    if socks5:
        proxies_dict.update({"proxies": [{"http": proxy.rstrip(), "https": proxy.rstrip()} for proxy in proxies]})

    with open("proxies." + str(j) + ".json", 'w') as f:
        f.write(json.dumps(proxies_dict, indent=4, sort_keys=True))
        print("Conversion to json completed.")
