#!/usr/bin/env python3
"""
Database Viewer for Cognitive Agent
Allows you to inspect the contents of the knowledge database
"""

import sqlite3
import json
import os
from datetime import datetime

# Database path
DB_PATH = os.getenv("COG_AI_DB", "cogai.db")

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def format_timestamp(ts):
    """Format timestamp for display"""
    if ts:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    return "Unknown"

def view_episodic_memory():
    """View episodic memory (conversations)"""
    print("\n" + "="*60)
    print("EPISODIC MEMORY (Conversations)")
    print("="*60)
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT role, text, ts 
            FROM episodic 
            ORDER BY ts DESC 
            LIMIT 20
        """)
        
        rows = cursor.fetchall()
        if not rows:
            print("No episodic memory found.")
            return
        
        for role, text, ts in rows:
            timestamp = format_timestamp(ts)
            print(f"\n[{timestamp}] {role.upper()}:")
            print(f"  {text[:100]}{'...' if len(text) > 100 else ''}")

def view_semantic_memory():
    """View semantic memory (facts)"""
    print("\n" + "="*60)
    print("SEMANTIC MEMORY (Facts)")
    print("="*60)
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT key, value, source, ts 
            FROM semantic 
            ORDER BY ts DESC
        """)
        
        rows = cursor.fetchall()
        if not rows:
            print("No semantic memory found.")
            return
        
        for key, value, source, ts in rows:
            timestamp = format_timestamp(ts)
            print(f"\n[{timestamp}] {key} = {value}")
            print(f"  Source: {source}")

def view_skills_memory():
    """View skills memory"""
    print("\n" + "="*60)
    print("SKILLS MEMORY")
    print("="*60)
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT note, meta, ts 
            FROM skills 
            ORDER BY ts DESC
        """)
        
        rows = cursor.fetchall()
        if not rows:
            print("No skills memory found.")
            return
        
        for note, meta, ts in rows:
            timestamp = format_timestamp(ts)
            print(f"\n[{timestamp}] {note}")
            if meta:
                try:
                    meta_data = json.loads(meta)
                    print(f"  Meta: {meta_data}")
                except:
                    print(f"  Meta: {meta}")

def view_knowledge_graph():
    """View knowledge graph entities and relations"""
    print("\n" + "="*60)
    print("KNOWLEDGE GRAPH")
    print("="*60)
    
    with get_db_connection() as conn:
        # Entities
        print("\nENTITIES:")
        cursor = conn.execute("""
            SELECT name, type, attributes, ts 
            FROM kg_entities 
            ORDER BY name
        """)
        
        entities = cursor.fetchall()
        if entities:
            for name, etype, attrs, ts in entities:
                timestamp = format_timestamp(ts)
                print(f"  {name} ({etype}) - {timestamp}")
                if attrs:
                    try:
                        attrs_data = json.loads(attrs)
                        if attrs_data:
                            print(f"    Attributes: {attrs_data}")
                    except:
                        pass
        else:
            print("  No entities found.")
        
        # Relations
        print("\nRELATIONS:")
        cursor = conn.execute("""
            SELECT subject, predicate, object, weight, ts 
            FROM kg_relations 
            ORDER BY subject, predicate
        """)
        
        relations = cursor.fetchall()
        if relations:
            for subject, predicate, object, weight, ts in relations:
                timestamp = format_timestamp(ts)
                print(f"  {subject} --[{predicate}]--> {object} (weight: {weight}) - {timestamp}")
        else:
            print("  No relations found.")

def view_vectors():
    """View vector embeddings info"""
    print("\n" + "="*60)
    print("VECTOR EMBEDDINGS")
    print("="*60)
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT kind, ref_id, LENGTH(embedding) as embedding_size
            FROM vectors 
            ORDER BY kind, ref_id
        """)
        
        rows = cursor.fetchall()
        if not rows:
            print("No vector embeddings found.")
            return
        
        # Group by kind
        by_kind = {}
        for kind, ref_id, size in rows:
            if kind not in by_kind:
                by_kind[kind] = []
            by_kind[kind].append((ref_id, size))
        
        for kind, items in by_kind.items():
            print(f"\n{kind.upper()} VECTORS ({len(items)} items):")
            for ref_id, size in items[:10]:  # Show first 10
                print(f"  ID {ref_id}: {size} bytes")
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")

def view_metadata():
    """View metadata"""
    print("\n" + "="*60)
    print("METADATA")
    print("="*60)
    
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT key, value FROM meta ORDER BY key")
        rows = cursor.fetchall()
        
        if not rows:
            print("No metadata found.")
            return
        
        for key, value in rows:
            print(f"  {key}: {value}")

def get_database_stats():
    """Get database statistics"""
    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)
    
    with get_db_connection() as conn:
        tables = ['episodic', 'semantic', 'skills', 'kg_entities', 'kg_relations', 'vectors', 'meta']
        
        for table in tables:
            try:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"  {table}: table not found")

def interactive_mode():
    """Interactive mode for exploring specific data"""
    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print("Commands:")
    print("  search <term> - Search for term in all text fields")
    print("  entity <name> - Show details for specific entity")
    print("  relations <entity> - Show all relations for entity")
    print("  recent <n> - Show n most recent conversations")
    print("  quit - Exit interactive mode")
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == "quit":
                break
            elif command.startswith("search "):
                term = command[7:]
                search_database(term)
            elif command.startswith("entity "):
                entity = command[7:]
                show_entity_details(entity)
            elif command.startswith("relations "):
                entity = command[10:]
                show_entity_relations(entity)
            elif command.startswith("recent "):
                try:
                    n = int(command[7:])
                    show_recent_conversations(n)
                except ValueError:
                    print("Please enter a valid number")
            else:
                print("Unknown command. Type 'quit' to exit.")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

def search_database(term):
    """Search for term in database"""
    print(f"\nSearching for '{term}'...")
    
    with get_db_connection() as conn:
        # Search in episodic memory
        cursor = conn.execute("""
            SELECT role, text, ts FROM episodic 
            WHERE text LIKE ? 
            ORDER BY ts DESC 
            LIMIT 5
        """, (f"%{term}%",))
        
        rows = cursor.fetchall()
        if rows:
            print(f"\nFound in conversations:")
            for role, text, ts in rows:
                timestamp = format_timestamp(ts)
                print(f"  [{timestamp}] {role}: {text[:100]}...")
        
        # Search in entities
        cursor = conn.execute("""
            SELECT name, type FROM kg_entities 
            WHERE name LIKE ? 
            ORDER BY name
        """, (f"%{term}%",))
        
        rows = cursor.fetchall()
        if rows:
            print(f"\nFound in entities:")
            for name, etype in rows:
                print(f"  {name} ({etype})")

def show_entity_details(entity):
    """Show details for specific entity"""
    with get_db_connection() as conn:
        # Get entity info
        cursor = conn.execute("""
            SELECT name, type, attributes, ts 
            FROM kg_entities 
            WHERE name LIKE ?
        """, (f"%{entity}%",))
        
        rows = cursor.fetchall()
        if not rows:
            print(f"Entity '{entity}' not found.")
            return
        
        for name, etype, attrs, ts in rows:
            timestamp = format_timestamp(ts)
            print(f"\nEntity: {name}")
            print(f"  Type: {etype}")
            print(f"  Created: {timestamp}")
            if attrs:
                try:
                    attrs_data = json.loads(attrs)
                    print(f"  Attributes: {attrs_data}")
                except:
                    print(f"  Attributes: {attrs}")

def show_entity_relations(entity):
    """Show all relations for entity"""
    with get_db_connection() as conn:
        # Outgoing relations
        cursor = conn.execute("""
            SELECT predicate, object, weight, ts 
            FROM kg_relations 
            WHERE subject LIKE ?
            ORDER BY predicate
        """, (f"%{entity}%",))
        
        outgoing = cursor.fetchall()
        if outgoing:
            print(f"\nOutgoing relations from '{entity}':")
            for pred, obj, weight, ts in outgoing:
                timestamp = format_timestamp(ts)
                print(f"  {entity} --[{pred}]--> {obj} (weight: {weight}) - {timestamp}")
        
        # Incoming relations
        cursor = conn.execute("""
            SELECT subject, predicate, weight, ts 
            FROM kg_relations 
            WHERE object LIKE ?
            ORDER BY subject
        """, (f"%{entity}%",))
        
        incoming = cursor.fetchall()
        if incoming:
            print(f"\nIncoming relations to '{entity}':")
            for subj, pred, weight, ts in incoming:
                timestamp = format_timestamp(ts)
                print(f"  {subj} --[{pred}]--> {entity} (weight: {weight}) - {timestamp}")

def show_recent_conversations(n):
    """Show n most recent conversations"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT role, text, ts 
            FROM episodic 
            ORDER BY ts DESC 
            LIMIT ?
        """, (n,))
        
        rows = cursor.fetchall()
        if not rows:
            print("No conversations found.")
            return
        
        print(f"\n{n} most recent conversations:")
        for role, text, ts in rows:
            timestamp = format_timestamp(ts)
            print(f"\n[{timestamp}] {role.upper()}:")
            print(f"  {text}")

def main():
    """Main function"""
    print("Cognitive Agent Database Viewer")
    print("=" * 40)
    
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found!")
        return
    
    # Show all data
    get_database_stats()
    view_episodic_memory()
    view_semantic_memory()
    view_skills_memory()
    view_knowledge_graph()
    view_vectors()
    view_metadata()
    
    # Interactive mode
    interactive_mode()
    
    print("\nGoodbye!")

if __name__ == "__main__":
    main()
