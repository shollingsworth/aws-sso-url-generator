#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Generate a list of AWS SSO urls you can open in your browser.

    Fzf Usage:
        ./aws_sso_url_generator.py | fzf | awk '{print $NF}' |  xargs google-chrome

"""
import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import quote

import requests

os.environ[
    "ORG_SSO_FILE"
] = "~/.aws/sso/cache/0f9973e9ffde7c6301d38bf157526d341438e70b.json"

try:
    from aiohttp_retry import ExponentialRetry, RetryClient
except ImportError:
    raise SystemExit("aiohttp-retry is required. (pip3 install aiohttp-retry)")

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "protocol": self.protocol,
            "relayState": self.relayState,
        }


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "AccountId": self.AccountId,
            "AccountName": self.AccountName,
            "AccountEmail": self.AccountEmail,
        }


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "applicationId": self.applicationId,
            "applicationName": self.applicationName,
            "icon": self.icon,
            "searchMetadata": self.searchMetadata.to_dict(),
        }


@dataclass
class OutValue:
    profile: Profile
    account: AppInstance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "account": self.account.to_dict(),
        }


@dataclass
class OutError:
    account: Profile
    response: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account.to_dict(),
            "response": self.response,
        }


@dataclass
class Output:
    result: List[OutValue]
    errors: List[OutError]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": [v.to_dict() for v in self.result],
            "errors": [e.to_dict() for e in self.errors],
        }


async def fetch(session, pl: Dict[str, Any]) -> Tuple[AppInstance, Dict[str, Any]]:
    url = pl["url"]
    async with session.get(url) as response:
        resp = await response.text()
        return pl["account"], json.loads(resp)


def iter_app_instances() -> Iterable[AppInstance]:
    url = f"{BASE_URL}/instance/appinstances"
    r = requests.get(url, headers=HEADERS)
    dat = r.json()
    try:
        for i in dat["result"]:
            yield AppInstance.from_dict(i)
    except KeyError:
        raise SystemExit(f"{url}\nreturned {r.status_code}\n{r.json()['message']}")


async def json_output() -> Output:
    values = []
    errors = []
    retry_options = ExponentialRetry(attempts=5)
    async with RetryClient(
        raise_for_status=False, retry_options=retry_options, headers=HEADERS
    ) as session:
        # async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        tasks = []
        for account in iter_app_instances():
            url = f"{BASE_URL}/instance/appinstance/{account.id}/profiles"
            pl = {"account": account, "url": url}
            tasks.append(asyncio.create_task(fetch(session, pl)))
            #  if limit > 0:
            #      if len(tasks) >= limit:
            #          break
        completed = await asyncio.gather(*tasks)
        for account, resp in completed:
            try:
                results = resp["result"]
            except KeyError:
                errors.append(
                    OutError(
                        **{
                            "account": account,
                            "response": resp,
                        }
                    )
                )
                continue
            for dat in results:
                profile = Profile(**dat)
                assertion = profile.url.split("/")[-1]
                profile.url = f"{URL_START}{quote(account.name)}/{quote(assertion)}"
                values.append(
                    OutValue(
                        **{
                            "profile": profile,
                            "account": account,
                        }
                    )
                )
    return Output(
        **{
            "result": values,
            "errors": errors,
        }
    )


async def main(args):
    """Run main function."""
    out = await json_output()
    if args.json:
        dct = out.to_dict()
        sys.stdout.write(json.dumps(dct, indent=4, separators=(",", " : ")) + "\n")
        return

    for e in out.errors:
        sys.stderr.buffer.write(f"{e.account}: {e.response}\n".encode("utf-8"))
    for v in out.result:
        sys.stdout.buffer.write(
            f"{v.account.name}: {v.profile.name} {v.profile.url}\n".encode()
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    parser.add_argument(
        "--json",
        help="Output in JSON format",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()
    asyncio.run(main(args))
