"""
Script de migração: importa os dados do antigo dados.json
para o novo banco SQLite (dados.db) usado pelo app_rni_sqlite.py.

Como usar:
1. Coloque este arquivo na MESMA pasta onde está o seu dados.json atual.
2. Rode: python migrar_dados.py
3. Um arquivo dados.db será criado (ou atualizado) na mesma pasta.
4. Depois disso, rode o app normalmente: streamlit run app_rni_sqlite.py

O script é seguro para rodar mais de uma vez: ele avisa e pergunta antes
de duplicar dados se o dados.db já tiver pacientes cadastrados.
"""

import json
import os
import sqlite3
import sys

JSON_PATH = "dados.json"
DB_PATH = "dados.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            contact TEXT,
            indication TEXT,
            target TEXT,
            weeklyDose REAL,
            organizer TEXT,
            level TEXT,
            status TEXT,
            meds TEXT,
            evolution TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rni_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            value REAL,
            status TEXT,
            obs TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rni_patient ON rni_history(patient_id)")
    conn.commit()


def main():
    if not os.path.exists(JSON_PATH):
        print(f"Arquivo '{JSON_PATH}' não encontrado nesta pasta. Nada para migrar.")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        dados_antigos = json.load(f)

    pacientes_antigos = dados_antigos.get("patients", [])
    if not pacientes_antigos:
        print("O dados.json não contém pacientes. Nada para migrar.")
        sys.exit(0)

    conn = get_conn()
    init_db(conn)

    total_ja_existente = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    if total_ja_existente > 0:
        resposta = input(
            f"O dados.db já contém {total_ja_existente} paciente(s). "
            "Rodar a migração de novo vai DUPLICAR esses registros. "
            "Deseja continuar mesmo assim? (s/N): "
        ).strip().lower()
        if resposta != "s":
            print("Migração cancelada.")
            conn.close()
            sys.exit(0)

    total_pacientes = 0
    total_exames = 0

    for p in pacientes_antigos:
        cur = conn.execute(
            """INSERT INTO patients (name, age, contact, indication, target, weeklyDose,
               organizer, level, status, meds, evolution)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p.get("name", "Sem nome"),
                p.get("age"),
                p.get("contact", ""),
                p.get("indication", ""),
                p.get("target", "2.0-3.0"),
                p.get("weeklyDose", 0.0),
                p.get("organizer", "Não"),
                p.get("level", "Médio"),
                p.get("status", "Ativo"),
                p.get("meds", ""),
                p.get("evolution", ""),
            )
        )
        novo_patient_id = cur.lastrowid
        total_pacientes += 1

        for exame in p.get("rniHistory", []):
            conn.execute(
                "INSERT INTO rni_history (patient_id, date, value, status, obs) VALUES (?, ?, ?, ?, ?)",
                (
                    novo_patient_id,
                    exame.get("date"),
                    exame.get("value"),
                    exame.get("status"),
                    exame.get("obs"),
                )
            )
            total_exames += 1

    conn.commit()
    conn.close()

    print(f"Migração concluída: {total_pacientes} paciente(s) e {total_exames} registro(s) de RNI importados para {DB_PATH}.")
    print("Agora você pode rodar: streamlit run app_rni_sqlite.py")


if __name__ == "__main__":
    main()
