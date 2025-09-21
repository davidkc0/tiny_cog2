# storage.py
import sqlite3, time, json, os, pickle

DB_PATH = os.getenv("COG_AI_DB", "cogai.db")

def get_db():
    return sqlite3.connect(DB_PATH)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodic (
    id INTEGER PRIMARY KEY,
    role TEXT,
    text TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS semantic (
    id INTEGER PRIMARY KEY,
    key TEXT,
    value TEXT,
    source TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY,
    note TEXT,
    meta TEXT, -- JSON
    ts REAL
);
CREATE TABLE IF NOT EXISTS vectors (
    id INTEGER PRIMARY KEY,
    kind TEXT, -- "episodic", "semantic", "skills"
    ref_id INTEGER,
    embedding BLOB
);
CREATE TABLE IF NOT EXISTS kg_entities (
    name TEXT PRIMARY KEY,
    type TEXT,
    attributes TEXT, -- JSON
    ts REAL
);
CREATE TABLE IF NOT EXISTS kg_relations (
    id INTEGER PRIMARY KEY,
    subject TEXT,
    predicate TEXT,
    object TEXT,
    weight REAL,
    attributes TEXT, -- JSON
    ts REAL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

def ensure_schema():
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)

def get_meta(key, default=None):
    with get_db() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else default

def set_meta(key, value):
    with get_db() as c:
        c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))

def clear_vectors():
    """Clear all vectors (use when embedding dimension changes)."""
    with get_db() as conn:
        conn.execute("DELETE FROM vectors")

def clear_vectors_by_kind(kind):
    """Clear vectors of a specific kind."""
    with get_db() as conn:
        conn.execute("DELETE FROM vectors WHERE kind=?", (kind,))

def check_vector_dimensions():
    """Check if all stored vectors have consistent dimensions."""
    import numpy as np, pickle
    dimensions = {}
    with get_db() as conn:
        rows = conn.execute("SELECT kind, embedding FROM vectors").fetchall()
    
    for kind, blob in rows:
        try:
            v = np.array(pickle.loads(blob))
            dim = len(v)
            if kind not in dimensions:
                dimensions[kind] = dim
            elif dimensions[kind] != dim:
                return False, f"Dimension mismatch in {kind}: {dimensions[kind]} vs {dim}"
        except Exception as e:
            return False, f"Error loading vector: {e}"
    
    return True, dimensions

def insert_episodic(role, text):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO episodic(role,text,ts) VALUES(?,?,?)",
            (role, text, time.time())
        )
        return cur.lastrowid

def insert_semantic(key, value, source="agent"):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO semantic(key,value,source,ts) VALUES(?,?,?,?)",
            (key, value, source, time.time())
        )
        return cur.lastrowid

def insert_skill(note, meta=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO skills(note,meta,ts) VALUES(?,?,?)",
            (note, json.dumps(meta or {}), time.time())
        )
        return cur.lastrowid

def upsert_vector(kind, ref_id, emb):
    blob = pickle.dumps(emb)
    with get_db() as conn:
        conn.execute("DELETE FROM vectors WHERE kind=? AND ref_id=?", (kind, ref_id))
        conn.execute(
            "INSERT INTO vectors(kind,ref_id,embedding) VALUES(?,?,?)",
            (kind, ref_id, blob)
        )

def nearest(kind, query_emb, k=5):
    import numpy as np, pickle
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ref_id, embedding FROM vectors WHERE kind=?",
            (kind,)
        ).fetchall()
    if not rows: return []
    q = np.array(query_emb)
    sims = []
    for rid, blob in rows:
        try:
            v = np.array(pickle.loads(blob))
            # Handle dimension mismatch by padding or truncating
            if len(q) != len(v):
                min_len = min(len(q), len(v))
                q_trunc = q[:min_len]
                v_trunc = v[:min_len]
            else:
                q_trunc = q
                v_trunc = v
            
            denom = (np.linalg.norm(q_trunc) + 1e-9) * (np.linalg.norm(v_trunc) + 1e-9)
            similarity = float(q_trunc @ v_trunc) / denom
            sims.append((similarity, rid))
        except Exception as e:
            print(f"Error computing similarity for vector {rid}: {e}")
            continue
    sims.sort(reverse=True)
    return [rid for _, rid in sims[:k]]

def get_episodic_by_ids(ids):
    if not ids: return []
    with get_db() as conn:
        placeholders = ','.join('?' * len(ids))
        rows = conn.execute(
            f"SELECT role, text, ts FROM episodic WHERE id IN ({placeholders})",
            ids
        ).fetchall()
    return [(role, text, ts) for role, text, ts in rows]

def get_semantic_by_ids(ids):
    if not ids: return []
    with get_db() as conn:
        placeholders = ','.join('?' * len(ids))
        rows = conn.execute(
            f"SELECT key, value, source, ts FROM semantic WHERE id IN ({placeholders})",
            ids
        ).fetchall()
    return [(key, value, source, ts) for key, value, source, ts in rows]

def get_skills_by_ids(ids):
    if not ids: return []
    with get_db() as conn:
        placeholders = ','.join('?' * len(ids))
        rows = conn.execute(
            f"SELECT note, meta, ts FROM skills WHERE id IN ({placeholders})",
            ids
        ).fetchall()
    return [(note, json.loads(meta), ts) for note, meta, ts in rows]

# ---- Knowledge Graph persistence ----
def upsert_kg_entity(name, etype="entity", attributes=None):
    with get_db() as conn:
        attrs_json = json.dumps(attributes or {})
        conn.execute(
            "INSERT OR REPLACE INTO kg_entities(name, type, attributes, ts) VALUES(?,?,?,?)",
            (name, etype, attrs_json, time.time())
        )

def upsert_kg_relation(subject, predicate, object, weight=1.0, attributes=None):
    with get_db() as conn:
        attrs_json = json.dumps(attributes or {})
        conn.execute(
            "INSERT OR REPLACE INTO kg_relations(subject, predicate, object, weight, attributes, ts) VALUES(?,?,?,?,?,?)",
            (subject, predicate, object, weight, attrs_json, time.time())
        )

def load_kg_entities():
    with get_db() as conn:
        rows = conn.execute("SELECT name, type, attributes, ts FROM kg_entities").fetchall()
    return [(name, etype, json.loads(attrs), ts) for name, etype, attrs, ts in rows]

def load_kg_relations():
    with get_db() as conn:
        rows = conn.execute("SELECT subject, predicate, object, weight, attributes, ts FROM kg_relations").fetchall()
    return [(subj, pred, obj, weight, json.loads(attrs), ts) for subj, pred, obj, weight, attrs, ts in rows]

def search_kg_entities(query, limit=10):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, type, attributes, ts FROM kg_entities WHERE name LIKE ? LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
    return [(name, etype, json.loads(attrs), ts) for name, etype, attrs, ts in rows]

def remove_kg_relations(subject, predicate):
    """Remove existing relations with same subject and predicate"""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM kg_relations WHERE subject = ? AND predicate = ?",
            (subject, predicate)
        )

def update_kg_relation(subject, predicate, new_object, weight=1.0, attributes=None):
    """Replace existing relation with new object"""
    with get_db() as conn:
        # Remove old relations with same subject/predicate
        conn.execute(
            "DELETE FROM kg_relations WHERE subject = ? AND predicate = ?",
            (subject, predicate)
        )
        # Add new relation
        attrs_json = json.dumps(attributes or {})
        conn.execute(
            "INSERT INTO kg_relations(subject, predicate, object, weight, attributes, ts) VALUES(?,?,?,?,?,?)",
            (subject, predicate, new_object, weight, attrs_json, time.time())
        )