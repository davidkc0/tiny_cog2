#!/usr/bin/env python3
"""
Test script for the Enhanced Memory System
Tests all aspects of the new memory storage and retrieval
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refactored_cognitive_agent import CognitiveAgent
import storage
import time

def clear_database():
    """Clear all data from the database for clean testing"""
    print("🧹 Clearing database for clean test...")
    
    # Ensure schema exists first
    storage.ensure_schema()
    
    with storage.get_db() as conn:
        # Clear all tables (check if they exist first)
        tables = ["episodic", "semantic", "skills", "vectors", "kg_entities", "kg_relations", "meta"]
        
        for table in tables:
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception as e:
                print(f"   Note: Could not clear {table} table: {e}")
        
        # Reset any auto-increment counters
        try:
            conn.execute("DELETE FROM sqlite_sequence")
        except:
            pass  # Table may not exist
        
        conn.commit()
    
    print("✅ Database cleared successfully")

def test_enhanced_memory_system():
    """Comprehensive test of the complete enhanced memory system"""
    print("🧠 Testing Complete Enhanced Memory System")
    print("=" * 60)
    
    # Start with clean database
    clear_database()
    print()
    
    # Create agent with default configuration (includes complete enhanced memory)
    agent = CognitiveAgent({})
    
    print(f"📊 Initial Agent Status:")
    status = agent.get_status()
    print(f"   Tools: {[tool['name'] for tool in status['tools']]}")
    print(f"   Memory Strategy: {status['memory_strategy']}")
    print(f"   Pipeline Steps: {' → '.join(status['pipeline_steps'])}")
    print(f"   Knowledge: {status['kg_entities']} entities, {status['kg_relations']} relations")
    
    # Check if complete enhanced memory is active
    has_complete_memory = 'complete_enhanced_memory_storage' in status['pipeline_steps']
    print(f"   Complete Enhanced Memory: {'✅ ACTIVE' if has_complete_memory else '❌ INACTIVE'}")
    print()
    
    # Test 1: Store personal facts
    print("🧪 Test 1: Storing Personal Facts")
    print("-" * 30)
    
    test_inputs = [
        "My favorite color is purple",
        "I live in New York City", 
        "I work as a software engineer",
        "My hobby is playing piano"
    ]
    
    for user_input in test_inputs:
        print(f"User: {user_input}")
        response = agent.act(user_input)
        print(f"Agent: {response}")
        print()
        time.sleep(0.5)  # Brief pause between interactions
    
    # Test 2: Calculator tool result storage
    print("🧪 Test 2: Calculator Tool Results")
    print("-" * 30)
    
    calc_inputs = [
        "What is 15 * 8?",
        "Calculate 100 / 4"
    ]
    
    for user_input in calc_inputs:
        print(f"User: {user_input}")
        response = agent.act(user_input)
        print(f"Agent: {response}")
        print()
        time.sleep(0.5)
    
    # Test 3: Memory retrieval and effectiveness
    print("🧪 Test 3: Memory Retrieval & Effectiveness")
    print("-" * 40)
    
    retrieval_inputs = [
        "What is my favorite color?",
        "Where do I live?", 
        "What do you know about me?",
        "What calculations have we done?",
        "What have I searched for?"
    ]
    
    for user_input in retrieval_inputs:
        print(f"User: {user_input}")
        response = agent.act(user_input)
        print(f"Agent: {response}")
        print()
        time.sleep(0.5)
    
    # Test 3b: Test implicit relationship learning
    print("🧪 Test 3b: Implicit Relationship Learning")
    print("-" * 40)
    
    implicit_inputs = [
        "Thank you for helping me with the calculations",
        "Can you tell me about machine learning?",
        "Yes, that's correct about my location"
    ]
    
    for user_input in implicit_inputs:
        print(f"User: {user_input}")
        response = agent.act(user_input)
        print(f"Agent: {response}")
        print()
        time.sleep(0.5)
    
    # Test 4: Check database contents
    print("🧪 Test 4: Database Analysis")
    print("-" * 30)
    
    with storage.get_db() as conn:
        # Check episodic memories
        episodic_count = conn.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
        print(f"📝 Episodic memories: {episodic_count}")
        
        # Check semantic facts
        semantic_count = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
        print(f"🧠 Semantic facts: {semantic_count}")
        
        # Check skills
        skills_count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        print(f"🎯 Skills/patterns: {skills_count}")
        
        # Check KG entities and relations
        kg_entities_count = conn.execute("SELECT COUNT(*) FROM kg_entities").fetchone()[0]
        kg_relations_count = conn.execute("SELECT COUNT(*) FROM kg_relations").fetchone()[0]
        print(f"🕸️  KG entities: {kg_entities_count}")
        print(f"🔗 KG relations: {kg_relations_count}")
        
        # Show recent semantic facts
        print(f"\n📋 Recent semantic facts:")
        semantic_facts = conn.execute(
            "SELECT key, value, source FROM semantic ORDER BY ts DESC LIMIT 5"
        ).fetchall()
        for i, (key, value, source) in enumerate(semantic_facts, 1):
            print(f"   {i}. {key} = {value} (from {source})")
        
        # Show recent KG relations
        print(f"\n🔗 Recent KG relations:")
        kg_relations = conn.execute(
            "SELECT subject, predicate, object FROM kg_relations ORDER BY ts DESC LIMIT 5"
        ).fetchall()
        for i, (subject, predicate, obj) in enumerate(kg_relations, 1):
            print(f"   {i}. {subject} {predicate} {obj}")
    
    # Test 5: Enhanced memory step statistics
    print(f"\n📊 Memory System Statistics:")
    final_status = agent.get_status()
    print(f"   Final KG size: {final_status['kg_entities']} entities, {final_status['kg_relations']} relations")
    
    # Check if the pipeline contains complete enhanced memory storage
    pipeline_steps = final_status['pipeline_steps']
    has_complete_memory = 'complete_enhanced_memory_storage' in pipeline_steps
    print(f"   Complete enhanced memory active: {'✅ YES' if has_complete_memory else '❌ NO'}")
    
    # Show memory effectiveness if available
    if has_complete_memory:
        print(f"   Memory system effectiveness: Tracked in pipeline metadata")
    
    print("\n" + "=" * 60)
    print("🎉 Complete Enhanced Memory System Test Complete!")
    
    return {
        'episodic_count': episodic_count,
        'semantic_count': semantic_count,
        'skills_count': skills_count,
        'kg_entities_count': kg_entities_count,
        'kg_relations_count': kg_relations_count,
        'complete_memory_active': has_complete_memory
    }

def test_memory_consolidation():
    """Test memory consolidation features"""
    print("\n🧪 Testing Memory Consolidation")
    print("-" * 30)
    
    agent = CognitiveAgent({})
    
    # Simulate 12 interactions to trigger consolidation (every 10 turns)
    for i in range(12):
        user_input = f"This is interaction number {i+1}"
        agent.act(user_input)
    
    # Check if reflection was created
    with storage.get_db() as conn:
        reflections = conn.execute(
            "SELECT note FROM skills WHERE meta LIKE '%reflection%' ORDER BY ts DESC LIMIT 1"
        ).fetchall()
        
        if reflections:
            print(f"✅ Reflection created: {reflections[0][0]}")
        else:
            print("❌ No reflection found")

def test_fact_updating():
    """Test fact updating functionality"""
    print("\n🧪 Testing Fact Updates")
    print("-" * 30)
    
    agent = CognitiveAgent({})
    
    # Store initial fact
    print("Storing initial fact...")
    agent.act("My favorite food is pizza")
    
    # Update the fact
    print("Updating fact...")
    agent.act("Actually, my favorite food is now sushi")
    
    # Check if both versions exist
    with storage.get_db() as conn:
        food_facts = conn.execute(
            "SELECT key, value, source FROM semantic WHERE key LIKE '%food%' ORDER BY ts"
        ).fetchall()
        
        print(f"Food facts found: {len(food_facts)}")
        for key, value, source in food_facts:
            superseded = "_superseded" in source
            status = "SUPERSEDED" if superseded else "CURRENT"
            print(f"   {key} = {value} ({status})")

if __name__ == "__main__":
    try:
        # Run main test
        results = test_enhanced_memory_system()
        
        # Run additional tests
        test_memory_consolidation()
        test_fact_updating()
        
        print(f"\n🏆 Test Summary:")
        print(f"   Episodic memories: {results['episodic_count']}")
        print(f"   Semantic facts: {results['semantic_count']}")
        print(f"   Skills/patterns: {results['skills_count']}")
        print(f"   KG entities: {results['kg_entities_count']}")
        print(f"   KG relations: {results['kg_relations_count']}")
        print(f"   Complete enhanced memory: {'✅ Active' if results['complete_memory_active'] else '❌ Inactive'}")
        
        if results['complete_memory_active'] and results['semantic_count'] > 0:
            print(f"\n🎉 Complete Enhanced Memory System is working correctly!")
        else:
            print(f"\n⚠️  Complete Enhanced Memory System may have issues")
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Always clear database after testing
        print(f"\n🧹 Cleaning up...")
        clear_database()
        print(f"✅ Test cleanup complete - database ready for normal use")
