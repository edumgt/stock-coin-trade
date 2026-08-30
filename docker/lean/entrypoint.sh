#!/usr/bin/env sh
set -eu

mkdir -p /results

# /Lean/Data는 이미지에 market-hours/symbol-properties 등 LEAN 엔진 필수
# 참조 데이터가 들어 있는 디렉터리라서 통째로 volume mount하면 안 된다.
# 대신 별도 경로(/custom-data)로 받은 시트 데이터를 그 안에 복사해 넣는다.
cp /custom-data/prices.csv /Lean/Data/prices.csv

cp /module/config.json /results/config.json
cd /results

exec dotnet /Lean/Launcher/bin/Debug/QuantConnect.Lean.Launcher.dll
