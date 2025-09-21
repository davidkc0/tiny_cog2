#!/usr/bin/env python3
"""
Quick Database Viewer - Simple overview of database contents
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("COG_AI_DB", "cogai.db")

def quick_view():
    """Quick overview of database contents"""
    if not os.path.exists(DB_PATH):
        print(f"Database '{DB_PATH}' not found!")
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        print("🧠 Cognitive Agent Database Overview")
        print("=" * 50)
        
        # Get counts
        tables = {
            'episodic': 'Conversations',
            'semantic': 'Facts', 
            'skills': 'Skills',
            'kg_entities': 'Knowledge Entities',
            'kg_relations': 'Knowledge Relations',
            'vectors': 'Embeddings'
        }
        
        for table, description in tables.items():
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"📊 {description}: {count}")
            except:
                print(f"📊 {description}: table not found")
        
        print("\n🔍 Recent Knowledge Graph Entities:")
        entities = conn.execute("""
            SELECT name, type, ts FROM kg_entities 
            ORDER BY ts DESC LIMIT 10
        """).fetchall()
        
        for name, etype, ts in entities:
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            print(f"  • {name} ({etype}) - {timestamp}")
        
        print("\n🔗 Recent Relations:")
        relations = conn.execute("""
            SELECT subject, predicate, object, ts 
            FROM kg_relations 
            ORDER BY ts DESC LIMIT 10
        """).fetchall()
        
        for subject, predicate, object, ts in relations:
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            print(f"  • {subject} --[{predicate}]--> {object} - {timestamp}")
        
        print("\n💬 Recent Conversations:")
        conversations = conn.execute("""
            SELECT role, text, ts FROM episodic 
            ORDER BY ts DESC LIMIT 5
        """).fetchall()
        
        for role, text, ts in conversations:
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            preview = text[:50] + "..." if len(text) > 50 else text
            print(f"  [{timestamp}] {role}: {preview}")

if __name__ == "__main__":
    quick_view()
