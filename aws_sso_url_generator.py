#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Generate a list of AWS SSO urls you can open in your browser.

    Fzf Usage:
        ./aws_sso_url_generator.py | fzf | awk '{print $NF}' |  xargs google-chrome

"""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
from urllib.parse import quote

import requests

try:
    import aiohttp
except ImportError:
    raise SystemExit("aiohttp is required. (pip3 install aiohttp)")

SSO_FILE = os.environ.get("ORG_SSO_FILE")
if not SSO_FILE:
    raise SystemExit(
        "Please set ORG_SSO_FILE environment variable. (e.g."
        " ORG_SSO_FILE=~/.aws/sso/cache/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.json"
    )

AWS_CONFIG = Path(SSO_FILE).expanduser()
if not AWS_CONFIG.exists():
    raise SystemExit(f"{AWS_CONFIG} does not exist.")

_CONFIG = json.loads(AWS_CONFIG.read_text())
_REGION = _CONFIG["region"]
_START_URL = _CONFIG["startUrl"]

BASE_URL = f"https://portal.sso.{_REGION}.amazonaws.com"
URL_START = f"{_START_URL}/saml/custom/"

HEADERS = {
    "x-amz-sso_bearer_token": _CONFIG["accessToken"],
    "x-amz-sso-bearer-token": _CONFIG["accessToken"],
}


@dataclass
class Profile:
    id: str
    name: str
    description: str
    url: str
    protocol: str
    relayState: str

    @staticmethod
    def from_dict(obj: Any) -> "Profile":
        _id = str(obj.get("id"))
        _name = str(obj.get("name"))
        _description = str(obj.get("description"))
        _url = str(obj.get("url"))
        _protocol = str(obj.get("protocol"))
        _relayState = str(obj.get("relayState"))
        return Profile(_id, _name, _description, _url, _protocol, _relayState)


@dataclass
class SearchMetadata:
    AccountId: str
    AccountName: str
    AccountEmail: str

    @staticmethod
    def from_dict(obj: Any) -> "SearchMetadata":
        _AccountId = str(obj.get("AccountId"))
        _AccountName = str(obj.get("AccountName"))
        _AccountEmail = str(obj.get("AccountEmail"))
        return SearchMetadata(_AccountId, _AccountName, _AccountEmail)


@dataclass
class AppInstance:
    id: str
    name: str
    description: str
    applicationId: str
    applicationName: str
    icon: str
    searchMetadata: SearchMetadata

    @staticmethod
    def from_dict(obj: Any) -> "AppInstance":
        _id = str(obj.get("id"))
        _name = str(obj.get("name"))
        _description = str(obj.get("description"))
        _applicationId = str(obj.get("applicationId"))
        _applicationName = str(obj.get("applicationName"))
        _icon = str(obj.get("icon"))
        _searchMetadata = SearchMetadata.from_dict(obj.get("searchMetadata"))
        return AppInstance(
            _id,
            _name,
            _description,
            _applicationId,
            _applicationName,
            _icon,
            _searchMetadata,
        )


async def fetch(session, pl: Dict[str, Any]) -> Tuple[AppInstance, Dict[str, Any]]:
    url = pl["url"]
    async with session.get(url) as response:
        resp = await response.text()
        return pl["account"], json.loads(resp)


def iter_app_instances() -> Iterable[AppInstance]:
    url = f"{BASE_URL}/instance/appinstances"
    r = requests.get(url, headers=HEADERS)
    for i in r.json()["result"]:
        yield AppInstance.from_dict(i)


async def main():
    """Run main function."""
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = []
        for account in iter_app_instances():
            url = f"{BASE_URL}/instance/appinstance/{account.id}/profiles"
            pl = {"account": account, "url": url}
            tasks.append(asyncio.create_task(fetch(session, pl)))
            #  if len(tasks) >= 2:
            #      break
        results = await asyncio.gather(*tasks)
        for account, resp in results:
            try:
                results = resp["result"]
            except KeyError:
                print(f"{account.id} - {account.name} {resp}")
                continue
            for dat in results:
                profile = Profile(**dat)
                assertion = profile.url.split("/")[-1]
                new_url = f"{URL_START}{quote(account.name)}/{quote(assertion)}"
                print(f"{account.name}: {profile.name} {new_url}")


if __name__ == "__main__":
    asyncio.run(main())
