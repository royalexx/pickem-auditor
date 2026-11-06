#!/usr/bin/env python3
"""Fetch pinned research-only GitHub releases for Deepnote without GitHub CLI.

Downloads never alter the original releases or production ranking. The trusted
NHL release digest and NFL parameter/manifest checks are enforced again by
their individual inference adapters before scoring.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

REPO="royalexx/pickem-auditor"
RELEASES={
 "saves":("research-nhl-saves-20261029-run40993538888",
   {"posterior.nc":"d64c87f8c48b735545aee291525b6f041e5320b1da931d724c4ecbbd7283adc9",
    "manifest.json":"434f63a56ddecc1de316da62d58cc677cf74ed3412870ee96934e7989464db9b",
    "model_receipt.json":"0b0c9998a4c521439721302d0da49f269f07ac0f2201f67149c9690c27442a75"}),
 "targets":("research-nfl-targets-20261031-v3",
   {"model.json":None,"parameters.npz":None}),
}
def checksum(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as stream:
  for block in iter(lambda:stream.read(1024*1024),b""):h.update(block)
 return h.hexdigest()

def request(url,token,accept="application/vnd.github+json"):
 return urllib.request.Request(url,headers={
  "Authorization":"Bearer "+token,"Accept":accept,
  "X-GitHub-Api-Version":"2022-11-28",
  "User-Agent":"pickem-auditor-research-shadow"})

def fetch(model,out,*,token,opener=urllib.request.urlopen):
 if model not in RELEASES:raise ValueError("unknown_verified_model")
 if not token:raise ValueError("GITHUB_TOKEN_required")
 tag,pins=RELEASES[model];out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with opener(request(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}",token),
             timeout=60) as stream:
  listing=json.load(stream)
 if listing.get("tag_name")!=tag:raise ValueError("unexpected_release_identity")
 assets={a["name"]:a for a in listing.get("assets",[]) if a.get("name") in pins}
 if set(assets)!=set(pins):raise ValueError("incomplete_pinned_research_release")
 result={}
 for name,sha in pins.items():
  target=out/name
  if target.is_file() and target.stat().st_size and (sha is None or checksum(target)==sha):
   result[name]={"status":"existing","bytes":target.stat().st_size,"sha256":checksum(target)}
   continue
  asset=assets[name]
  # Browser-style release URLs return 404 for private repositories even
  # with a valid token. Use authenticated REST release-asset endpoint.
  url=asset.get("url")
  asset_id=asset.get("id")
  if (not isinstance(asset_id,int) or
      url!=f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}"):
   raise ValueError("untrusted_private_release_asset_api")
  temp=target.with_suffix(target.suffix+".download")
  try:
   with opener(request(url,token,accept="application/octet-stream"),timeout=180) as stream, temp.open("wb") as dst:
    while True:
     block=stream.read(1024*1024)
     if not block:break
     dst.write(block)
   if temp.stat().st_size!=asset.get("size"):
    raise ValueError("release_asset_size_mismatch:"+name)
   digest=checksum(temp)
   if sha and digest!=sha:raise ValueError("release_sha256_mismatch:"+name)
   temp.replace(target)
   result[name]={"status":"downloaded","bytes":target.stat().st_size,"sha256":digest}
  finally:temp.unlink(missing_ok=True)
 return {"schema":"precision_nuts_shadow_release_fetch_v1",
         "model":model,"tag":tag,"assets":result,"ranking_allowed":False}
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--model",choices=RELEASES,required=True)
 parser.add_argument("--out",type=Path,required=True)
 parser.add_argument("--receipt",type=Path,required=True)
 a=parser.parse_args()
 try:r=fetch(a.model,a.out,token=os.environ.get("GITHUB_TOKEN"))
 except Exception as exc:
  r={"schema":"precision_nuts_shadow_release_fetch_v1","model":a.model,
     "status":"unavailable","error":type(exc).__name__+":"+str(exc)[:180],
     "ranking_allowed":False}
 a.receipt.parent.mkdir(parents=True,exist_ok=True)
 a.receipt.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print("RESEARCH_POSTERIOR_RELEASE "+json.dumps(r,sort_keys=True),flush=True)
 return 2 if r.get("status")=="unavailable" else 0
if __name__=="__main__":raise SystemExit(main())
