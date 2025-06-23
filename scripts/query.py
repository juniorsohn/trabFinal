#!/usr/bin/env python3
import os
import time
import argparse
import requests
import csv
import json
from dotenv import load_dotenv
from pathlib import Path

# Carrega .env um nível acima do diretório do script
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

API_URL = "https://www.fflogs.com/api/v2/client"
TOKEN_URL = "https://www.fflogs.com/oauth/token"

def get_access_token():
    token = os.getenv("FFLOGS_ACCESS_TOKEN")
    if token:
        return token

    client_id = os.getenv("FFLOGS_CLIENT_ID")
    client_secret = os.getenv("FFLOGS_CLIENT_SECRET")
    if client_id and client_secret:
        resp = requests.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"}
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Client credentials retornou sem access_token.")
        return token

    raise RuntimeError("Não encontrou token nem credenciais no ambiente.")

def obter_fights(access_token, report_code):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    query = """
    query getFights($code: String!) {
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

def obter_name_map_via_table(access_token, report_code, fight_ids):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    query = """
    query getTable($code: String!, $fightIDs: [Int!]!) {
      reportData {
        report(code: $code) {
          table(fightIDs: $fightIDs)
        }
      }
    }
    """
    variables = {"code": report_code, "fightIDs": fight_ids}
    resp = requests.post(API_URL, headers=headers, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    table_json = data["data"]["reportData"]["report"]["table"]
    if isinstance(table_json, str):
        parsed = json.loads(table_json)
    else:
        parsed = table_json

    name_map = {}
    for actor in parsed.get("composition", []):
        if "id" in actor and "name" in actor:
            name_map[actor["id"]] = actor["name"]
    return name_map

def fetch_events_page(access_token, report_code, fight_id, start_time, end_time):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    query = """
    query getEvents($code: String!, $fightID: Int!, $startTime: Float!, $endTime: Float!) {
      reportData {
        report(code: $code) {
          events(
            dataType: DamageDone,
            fightIDs: [$fightID],
            startTime: $startTime,
            endTime: $endTime,
            limit: 1000
          ) {
            data
          }
        }
      }
    }
    """
    variables = {
        "code": report_code,
        "fightID": fight_id,
        "startTime": start_time,
        "endTime": end_time
    }
    resp = requests.post(API_URL, headers=headers, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"{data['errors']}")
    events = data["data"]["reportData"]["report"]["events"]["data"]
    return events

def salvar_csv_events_detalhados(fights, report_code, access_token, output_file, delay=1.0, name_map=None):
    from pathlib import Path

    campos = [
        "fightID", "timestamp", "sourceID", "sourceName",
        "targetID", "targetName", "abilityGUID", "abilityName", "amount"
    ]

    # Define caminho para /projeto/data/<output_file>
    output_path = Path(__file__).resolve().parent.parent / "data" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()
    write_header = not file_exists or output_path.stat().st_size == 0

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(campos)
        for fight in fights:
            fid = fight["id"]
            print(f"Processando fight {fid}...")
            start = fight["startTime"]
            end = fight["endTime"]
            current = start
            while current < end:
                try:
                    entries = fetch_events_page(access_token, report_code, fid, current, end)
                except Exception as e:
                    print(f"[Erro] Fight {fid}: {e}")
                    break
                if not entries:
                    break
                for ev in entries:
                    src_id = ev.get("sourceID")
                    tgt_id = ev.get("targetID")
                    src_name = name_map.get(src_id) or ev.get("sourceName", "")
                    tgt_name = name_map.get(tgt_id) or ev.get("targetName", "")
                    writer.writerow([
                        fid,
                        ev.get("timestamp"),
                        src_id,
                        src_name,
                        tgt_id,
                        tgt_name,
                        ev.get("ability", {}).get("guid"),
                        ev.get("ability", {}).get("name"),
                        ev.get("amount")
                    ])
                current = max(ev.get("timestamp", current) for ev in entries) + 1
                time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="Extrai todas as instâncias de dano de um ou mais FFLogs reports.")
    parser.add_argument("report_code", nargs="?", help="Código do report FFLogs (opcional se usar --input)")
    parser.add_argument("--input", help="Arquivo contendo múltiplos report codes (um por linha)")
<<<<<<< HEAD
    parser.add_argument("--output", default="instancias_dano.csv", help="Arquivo CSV de saída")
=======
    parser.add_argument("--output", default="eventos.csv", help="Arquivo CSV de saída")
>>>>>>> 5455d70157b0833ee19c5344b1c5b86e5965c95e
    parser.add_argument("--page-delay", type=float, default=1.0, help="Delay entre páginas")
    args = parser.parse_args()

    try:
        access_token = get_access_token()
    except Exception as e:
        print(f"[Erro] Nao conseguiu obter access token: {e}")
        return

    report_codes = []

    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                report_codes = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"[Erro] Falha ao ler arquivo de input: {e}")
            return
    elif args.report_code:
        report_codes = [args.report_code]
    else:
        print("[Erro] Nenhum report_code ou input fornecido.")
        return

    for report_code in report_codes:
<<<<<<< HEAD
        print(f"\n🔍 Processando report: {report_code}")
=======
        print(f"\nProcessando report: {report_code}")
>>>>>>> 5455d70157b0833ee19c5344b1c5b86e5965c95e
        try:
            fights = obter_fights(access_token, report_code)
        except Exception as e:
            print(f"[Erro] Falha ao obter fights do report {report_code}: {e}")
            continue

        try:
            fight_ids = [f["id"] for f in fights]
            name_map = obter_name_map_via_table(access_token, report_code, fight_ids[:3])
        except Exception as e:
            print(f"[Erro] Falha ao obter nomes via table para report {report_code}: {e}")
            name_map = {}

        if not fights:
            print("Nenhum fight encontrado.")
            continue

        print("Fights encontrados:")
        for f in fights:
            print(f"  ID {f['id']}: {f.get('name','')}")

        salvar_csv_events_detalhados(fights, report_code, access_token, args.output, args.page_delay, name_map)

    print("\nConcluido. CSV salvo em", args.output)


if __name__ == "__main__":
    main()
