#!/bin/bash

export VIRTUAL_ENV=/usr/local

curl 'https://zenodo.org/api/funders/?page=1&size=10000' | \
jq '[.hits.hits[] | .metadata]' > /code/zenodo/zenodo/modules/fixtures/data/funders.json

#echo "[" > /code/zenodo/zenodo/modules/fixtures/data/grants.json
#cat /code/zenodo/zenodo/modules/fixtures/data/funders.json | jq '.[] | .doi' | while read name; do
#  curl "https://zenodo.org/api/grants/?page=1&size=10000&funder=$name" | \
#  jq '.hits.hits[] | .metadata' >> /code/zenodo/zenodo/modules/fixtures/data/grants.json
#done
#echo "]" >> /code/zenodo/zenodo/modules/fixtures/data/grants.json

# This will only load a fraction of the ~5'000'000 grants. Only 10000 are allowed. There does not appear to be an API to load them all:
# ?page=1&size=1000 etc. will stop at 10 pages.

# To get e.g. the CS3MESH4EOSC grant: https://zenodo.org/api/grants/10.13039/501100000780::863353

#curl "https://zenodo.org/api/grants/?page=1&size=10000" | \
#  jq '.hits.hits[] | .metadata' > /code/zenodo/zenodo/modules/fixtures/data/grants.json

curl 'https://zenodo.org/api/licenses/?page=1&size=10000' | \
jq '[.hits.hits[] | .metadata | del(.suggest)]' > /code/zenodo/zenodo/modules/fixtures/data/licenses.json

cat /code/zenodo/zenodo/modules/fixtures/data/licenses.json | \
jq 'map(if .legacy_ids[0] == null then (.legacy_ids=[.id]) else . end) | map({(.legacy_ids[0] | ascii_downcase): .id}) | add' > \
/code/zenodo/zenodo/modules/fixtures/data/licenses_map.json


# from https://gitter.im/zenodo/zenodo?at=5cbeffbf4b4cb471d9433f1b

zenodo opendefinition loadlicenses -s opendefinition
zenodo opendefinition loadlicenses -s spdx

zenodo index reindex -t od_lic
zenodo index run

