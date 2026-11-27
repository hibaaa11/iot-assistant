import os
import re
from datetime import datetime

import ollama
import psycopg2

MODEL = "llama3.2:3b"


# ---------- Configuration from .env (no extra library needed) ----------
def load_env(path=".env"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "iot"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


# ---------- Prompt ----------
def build_system_prompt():
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""You are a PostgreSQL expert. You write ONE SQL query that answers the user's question.

Database schema:
  Table mesures(
    temps   TIMESTAMPTZ,        -- time of the reading (UTC)
    machine TEXT,               -- 'machine_1', 'machine_2' or 'machine_3'
    capteur TEXT,               -- 'temperature', 'vibration' or 'courant' (current)
    valeur  DOUBLE PRECISION    -- the measured value; its meaning depends on capteur
  )

Facts about the data:
  - One reading every 5 minutes for each machine and each sensor.
  - Data range: from 2026-11-02 to 2026-11-23 (all times are UTC). Today's date is {today}.
  - Normal values: temperature about 65 (degrees C), vibration about 2 (mm/s), courant about 12 (amperes).

Rules:
  1. Return ONLY the SQL query, inside a ```sql code block. No explanation.
  2. Only SELECT queries. Never modify data.
  3. Always filter on capteur when a sensor is mentioned, because valeur mixes all sensors.
  4. When the question asks for ONE value (highest, peak, maximum, lowest, minimum, average, how many), the query MUST use an aggregate function (MAX, MIN, AVG, COUNT) and return a single row. Never return raw readings for such a question. "highest", "peak" and "maximum" mean MAX(valeur); "lowest" means MIN(valeur); "average" means AVG(valeur).
  5. For a given day, use ONE condition: DATE(temps) = 'YYYY-MM-DD' (for example DATE(temps) = '2026-11-05'). For several days, use DATE(temps) BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'. Never use hours.
  6. Use only the table mesures and the columns above.

Examples:

Question: What was the average courant of machine_1 on 2026-11-05?
```sql
SELECT AVG(valeur) AS avg_courant
FROM mesures
WHERE machine = 'machine_1' AND capteur = 'courant'
  AND DATE(temps) = '2026-11-05';
```

Question: Which machine had the highest vibration over the whole period?
```sql
SELECT machine, MAX(valeur) AS max_vibration
FROM mesures
WHERE capteur = 'vibration'
GROUP BY machine
ORDER BY max_vibration DESC
LIMIT 1;
```

Question: Give the daily maximum temperature of machine_2 between 2026-11-10 and 2026-11-12.
```sql
SELECT date_trunc('day', temps) AS jour, MAX(valeur) AS max_temp
FROM mesures
WHERE machine = 'machine_2' AND capteur = 'temperature'
    AND DATE(temps) BETWEEN '2026-11-10' AND '2026-11-12'
GROUP BY jour
ORDER BY jour;
```

Question: What was the peak temperature of machine_1 on 2026-11-07?
```sql
SELECT MAX(valeur) AS max_temp
FROM mesures
WHERE machine = 'machine_1' AND capteur = 'temperature'
  AND DATE(temps) = '2026-11-07';
```
"""


# ---------- LLM calls ----------
def ask_llm(messages):
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"temperature": 0},
    )
    return response["message"]["content"]


def extract_sql(text):
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    sql = match.group(1) if match else text
    return sql.strip()


# ---------- Guardrails ----------
FORBIDDEN = [
    "insert", "update", "delete", "drop", "alter", "create", "grant",
    "revoke", "truncate", "copy", "pg_sleep", "execute", "call",
]


def validate_sql(sql):
    """Return (clean_sql, error). error is None if the query is accepted."""
    clean = sql.strip().rstrip(";").strip()
    lowered = clean.lower()

    if not (lowered.startswith("select") or lowered.startswith("with")):
        return None, "Only SELECT queries are allowed."
    if ";" in clean:
        return None, "Only one statement is allowed."
    if "--" in clean or "/*" in clean:
        return None, "SQL comments are not allowed."
    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", lowered):
            return None, f"Forbidden keyword: {word}."
    if "mesures" not in lowered:
        return None, "The query must use the table mesures."
    if not re.search(r"\blimit\b", lowered):
        clean += " LIMIT 100"
    return clean, None


# ---------- Execution ----------
def run_sql(sql):
    conn = get_connection()
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return columns, rows
    finally:
        conn.close()


def format_value(v):
    if isinstance(v, float):
        return str(round(v, 2))
    return str(v)


def format_result(columns, rows, max_rows=20):
    lines = [" | ".join(columns)]
    for row in rows[:max_rows]:
        lines.append(" | ".join(format_value(v) for v in row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows)} rows in total)")
    return "\n".join(lines)


# ---------- Full pipeline ----------
def ask(question):
    result = {"question": question, "sql": None, "answer": None, "error": None}

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": question},
    ]

    columns, rows, sql = None, None, None
    last_error = None

    for attempt in range(2):  # one retry if the SQL fails
        raw = ask_llm(messages)
        candidate = extract_sql(raw)
        sql, error = validate_sql(candidate)

        if error is None:
            try:
                columns, rows = run_sql(sql)
                result["sql"] = sql
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc).strip()
                result["sql"] = sql
        else:
            last_error = error
            result["sql"] = candidate

        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": f"That query failed: {last_error}\nWrite a corrected SQL query. Return ONLY the SQL in a ```sql block.",
        })

    if last_error is not None:
        result["error"] = last_error
        result["answer"] = "I could not produce a valid query for this question."
        return result

    if not rows:
        result["answer"] = "The query returned no data."
        return result

    explain_prompt = (
        "You are given the final result of a database query that already answers the question. "
        "The query was already filtered and sorted, so the rows shown are the answer: "
        "do not comment on how many rows there are and do not say that data is missing.\n"
        "Write one or two short sentences that state the answer directly, "
        "quoting the machine names, the values and the dates exactly as they appear in the data. "
        "Do not invent anything. Answer in the same language as the question.\n\n"
        f"Question: {question}\n\n"
        f"SQL used:\n{sql}\n\n"
        f"Result:\n{format_result(columns, rows)}"
    )
    result["answer"] = ask_llm([{"role": "user", "content": explain_prompt}]).strip()
    return result


if __name__ == "__main__":
    print("Assistant ready. Type a question (or 'quit').")
    while True:
        q = input("\nQuestion > ").strip()
        if q.lower() in ("quit", "exit", ""):
            break
        r = ask(q)
        print(f"\nSQL: {r['sql']}")
        if r["error"]:
            print(f"Error: {r['error']}")
        print(f"Answer: {r['answer']}")