#!/usr/bin/env python3
import os
import time
import argparse
import requests
import csv
import json

# Carrega .env um nível acima de scripts/
try:
    from dotenv import load_dotenv
    from pathlib import Path
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# Lê endpoint da API do ambiente ou usa /api/v2/user por padrão
API_URL = os.getenv("FFLOGS_API_URL", "https://www.fflogs.com/api/v2/user")
TOKEN_URL = "https://www.fflogs.com/oauth/token"

def get_access_token():
    token = os.getenv("FFLOGS_ACCESS_TOKEN")
    if token:
        return token

    client_id = os.getenv("FFLOGS_CLIENT_ID")
    client_secret = os.getenv("FFLOGS_CLIENT_SECRET")
    redirect_uri = os.getenv("FFLOGS_REDIRECT_URI")
    auth_code = os.getenv("FFLOGS_AUTH_CODE")

    if client_id and client_secret and redirect_uri and auth_code:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret
            }
        )
        resp.raise_for_status()
        data = resp.json()
        tok = data.get("access_token")
        if not tok:
            raise RuntimeError("Authorization code não retornou access_token.")
        return tok

    raise RuntimeError(
        "Não encontrou FFLOGS_ACCESS_TOKEN nem (FFLOGS_CLIENT_ID + FFLOGS_CLIENT_SECRET + FFLOGS_REDIRECT_URI + FFLOGS_AUTH_CODE) no ambiente."
    )

def obter_fights(access_token, report_code):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    query = """
    query getFightsWithTimes($code: String!) {
      reportData {
        report(code: $code) {
          fights {
            id
            name
            startTime
            endTime
          }
        }
      }
    }
    """
    variables = {"code": report_code}
    resp = requests.post(API_URL, headers=headers, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Erro ao obter fights: {data['errors']}")
    return data["data"]["reportData"]["report"]["fights"]

def fetch_events_page(access_token, report_code, fight_id, start_time, end_time, page_ts):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    query = """
    query getEventsForFight($code: String!, $fightID: Int!, $startTime: Float!, $endTime: Float!, $limit: Int!, $pageTimestamp: Float) {
      reportData {
        report(code: $code) {
          fights(ids: [$fightID]) {
            events(
              dataType: DAMAGE,
              startTime: $startTime,
              endTime: $endTime,
              limit: 1000,
              pageTimestamp: $pageTimestamp
            ) {
              entries {
                timestamp
                sourceID
                sourceName
                sourceIsFriendly
                targetID
                targetName
                targetIsFriendly
                abilityGUID
                abilityName
                amount
              }
              nextPageTimestamp
            }
          }
        }
      }
    }
    """
    variables = {
        "code": report_code,
        "fightID": fight_id,
        "startTime": start_time,
        "endTime": end_time,
        "pageTimestamp": page_ts
    }
    resp = requests.post(API_URL, headers=headers, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"{data['errors']}")
    fights_list = data["data"]["reportData"]["report"]["fights"]
    if not fights_list:
        return [], None
    events_block = fights_list[0].get("events")
    if not events_block:
        return [], None
    return events_block.get("entries", []), events_block.get("nextPageTimestamp")

def salvar_csv_events_simple(fights, report_code, access_token, output_file, page_delay):
    header = ["fightID", "fightName", "timestamp",
              "sourceID", "sourceName", "sourceIsFriendly",
              "targetID", "targetName", "targetIsFriendly",
              "abilityGUID", "abilityName", "amount"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for fight in fights:
            fid = fight["id"]
            fname = fight.get("name", "")
            start = fight.get("startTime")
            end = fight.get("endTime")
            if start is None or end is None:
                print(f"Pule fight {fid} sem start/end.")
                continue
            print(f"Processando fight {fid} ({fname})...")
            page_ts = None
            while True:
                try:
                    entries, next_ts = fetch_events_page(access_token, report_code, fid, start, end, page_ts)
                except Exception as e:
                    print(f"  Erro ao buscar página de eventos (fight {fid}): {e}")
                    break
                if not entries:
                    break
                for ev in entries:
                    writer.writerow([
                        fid,
                        fname,
                        ev.get("timestamp"),
                        ev.get("sourceID"),
                        ev.get("sourceName"),
                        ev.get("sourceIsFriendly"),
                        ev.get("targetID"),
                        ev.get("targetName"),
                        ev.get("targetIsFriendly"),
                        ev.get("abilityGUID"),
                        ev.get("abilityName"),
                        ev.get("amount")
                    ])
                if not next_ts:
                    break
                page_ts = next_ts
                time.sleep(page_delay)
            print(f"  Concluído fight {fid}.")
            time.sleep(page_delay)

def main():
    parser = argparse.ArgumentParser(
        description="Extrai instâncias de dano de um FFLogs report para CSV com autenticação de usuário."
    )
    parser.add_argument("report_code", help="Código do report FFLogs")
    parser.add_argument("-o", "--output", default="all_damage_events.csv",
                        help="Arquivo CSV de saída")
    parser.add_argument("--page-delay", type=float, default=1.0,
                        help="Delay (s) entre páginas de events e entre fights")
    args = parser.parse_args()

    try:
        access_token = get_access_token()
    except Exception as e:
        print(f"[Erro] não conseguiu obter access token: {e}")
        return

    try:
        fights = obter_fights(access_token, args.report_code)
    except Exception as e:
        print(f"[Erro] falha ao obter fights: {e}")
        return

    if not fights:
        print("Nenhum fight encontrado no report.")
        return

    print("Fights encontrados:")
    for f in fights:
        print(f"  ID {f['id']}: {f.get('name','')}")
    print(f"Usando API_URL = {API_URL}")
    salvar_csv_events_simple(fights, args.report_code, access_token, args.output, args.page_delay)
    print("Concluído. CSV salvo em", args.output)

if __name__ == "__main__":
    main()
