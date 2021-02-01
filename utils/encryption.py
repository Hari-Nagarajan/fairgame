#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import getpass as getpass
import stdiomask
import json
import os
from base64 import b64encode, b64decode
from Crypto.Cipher import ChaCha20_Poly1305
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import scrypt

from utils.logger import log


def encrypt(pt, password):
    """Encryption function to securely store user credentials, uses ChaCha_Poly1305
    with a user defined SCrypt key."""
    salt = get_random_bytes(32)
    key = scrypt(password, salt, key_len=32, N=2 ** 20, r=8, p=1)
    nonce = get_random_bytes(12)
    cipher = ChaCha20_Poly1305.new(key=key, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(pt)
    json_k = ["nonce", "salt", "ct", "tag"]
    json_v = [b64encode(x).decode("utf-8") for x in (nonce, salt, ct, tag)]
    result = json.dumps(dict(zip(json_k, json_v)))

    return result


def decrypt(ct, password):
    """Decryption function to unwrap and return the decrypted creds back to the main thread."""
    try:
        b64Ct = json.loads(ct)
        json_k = ["nonce", "salt", "ct", "tag"]
        json_v = {k: b64decode(b64Ct[k]) for k in json_k}

        key = scrypt(password, json_v["salt"], key_len=32, N=2 ** 20, r=8, p=1)
        cipher = ChaCha20_Poly1305.new(key=key, nonce=json_v["nonce"])
        ptData = cipher.decrypt_and_verify(json_v["ct"], json_v["tag"])

        return ptData
    except (KeyError, ValueError):
        print("Incorrect Password.")
        exit(0)


def create_encrypted_config(data, file_path):
    """Creates an encrypted credential file if none exists.  Stores results in a
    file in the root directory."""
    if isinstance(data, dict):
        data = json.dumps(data)
    payload = bytes(data, "utf-8")
    log.info("Create a password for the credential file")
    cpass = stdiomask.getpass(prompt="Credential file password: ", mask="*")
    vpass = stdiomask.getpass(prompt="Verify credential file password: ", mask="*")
    if cpass == vpass:
        result = encrypt(payload, cpass)
        with open(file_path, "w") as f:
            f.write(result)
        log.info("Credentials safely stored.")
    else:
        print("Password and verify password do not match.")
        exit(0)


def load_encrypted_config(config_path, encrypted_pass=None):
    """Decrypts a previously encrypted credential file and returns the contents back
    to the calling thread."""
    log.info("Reading credentials from: " + config_path)
    with open(config_path, "r") as json_file:
        data = json_file.read()
    try:
        if "nonce" in data:
            if encrypted_pass is None:
                password = stdiomask.getpass(
                    prompt="Credential file password: ", mask="*"
                )
            else:
                password = encrypted_pass
            decrypted = decrypt(data, password)
            return json.loads(decrypted)
        else:
            log.info(
                "Your configuration file is unencrypted, it will now be encrypted."
            )
            create_encrypted_config(data, config_path)
            return json.loads(data)
    except Exception as e:
        log.error(e)
        log.error(
            f"Failed to decrypt the credential file. If you have forgotten the password, delete {config_path} and rerun the bot"
        )


# def main():
#
#    password = getpass.getpass(prompt="Password: ")
#
#    if not os.path.isfile("../amazon_config.enc"):
#        verify = getpass.getpass(prompt="Verify Password: ")
#
#        if verify == password:
#            ptFile = open("../amazon_config.json", "rb")
#            data = ptFile.read()
#            ct = encrypt(data, password)
#
#            ctFile = open("../amazon_config.enc", "w")
#            ctFile.write(ct)
#            ctFile.close()
#        else:
#            print("Passwords do no match")
#            exit(0)
#
#    ctFile = open("../amazon_config.enc", "r")
#    data = ctFile.read()
#    pt = decrypt(data, password)
#    print(pt)
#
#
# main()
