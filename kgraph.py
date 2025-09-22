import networkx as nx
import time
import storage

class KnowledgeGraph:
    def __init__(self):
        self.G = nx.MultiDiGraph()
        self._load_from_storage()

    def _load_from_storage(self):
        for name, etype, attrs, ts in storage.load_kg_entities():
            self.G.add_node(name, type=etype, **attrs, ts=ts)
        for subj, pred, obj, weight, attrs, ts in storage.load_kg_relations():
            self.G.add_edge(subj, obj, key=pred, pred=pred, weight=weight, ts=ts, **attrs)

    def upsert_entity(self, name: str, etype: str = "entity", **attrs):
        # Avoid 'type' conflict with NetworkX by using 'entity_type'
        node_attrs = {**attrs, "entity_type": etype, "ts": time.time()}
        self.G.add_node(name, **node_attrs)
        storage.upsert_kg_entity(name, etype, attrs)

    def upsert_relation(self, subj: str, pred: str, obj: str, weight: float=1.0, **attrs):
        self.upsert_entity(subj)
        self.upsert_entity(obj)
        self.G.add_edge(subj, obj, key=pred, pred=pred, weight=weight, **attrs, ts=time.time())
        storage.upsert_kg_relation(subj, pred, obj, weight, attrs)

    # ---- Helpers the agent calls ----
    def search_entities(self, term: str, limit: int = 10):
        # First try direct name search
        rows = storage.search_kg_entities(term, limit=limit)
        if rows:
            return [name for (name, _, _, _) in rows]
        
        term_l = term.lower()
        results = []
        
        # Direct name match
        for n in self.G.nodes:
            if term_l in str(n).lower():
                results.append(n)
        
        # If no direct matches, try to find related entities
        if not results:
            # Look for entities that might be related to the search term
            for n in self.G.nodes:
                node_data = self.G.nodes[n]
                # Check if the search term relates to the entity type or attributes
                if 'type' in node_data:
                    entity_type = node_data['type'].lower()
                    if any(keyword in term_l for keyword in [entity_type, 'favorite', 'like', 'prefer']):
                        results.append(n)
        
        # If still no results, try semantic search through relations
        if not results:
            for n in self.G.nodes:
                # Check if any relations mention the search term
                for _, dst, _, data in self.G.out_edges(n, keys=True, data=True):
                    pred = data.get('pred', '').lower()
                    if any(keyword in pred for keyword in term_l.split()):
                        results.append(n)
                        break
        
        return results[:limit]

    def get_entity_info(self, name: str):
        if name not in self.G: return None
        data = self.G.nodes[name].copy()
        etype = data.pop("type", "entity")
        return {"type": etype, "attrs": data}

    def get_related_concepts(self, name: str, max_out: int = 10):
        if name not in self.G: return []
        rels = []
        # Outgoing edges: name -> target with relation
        for _, dst, _, d in self.G.out_edges(name, keys=True, data=True):
            rels.append((dst, d.get("pred", "related_to")))
            if len(rels) >= max_out: return rels
        # Incoming edges: source -> name with relation (reverse the relation)
        for src, _, _, d in self.G.in_edges(name, keys=True, data=True):
            pred = d.get("pred", "related_to")
            # For incoming edges, we need to reverse the relationship
            # e.g., if "blue likes user", then from user's perspective it's "liked_by blue"
            if pred == "likes":
                rels.append((src, "liked_by"))
            elif pred == "owns":
                rels.append((src, "owned_by"))
            elif pred == "works_as":
                rels.append((src, "employer_of"))
            else:
                rels.append((src, f"related_to_{pred}"))
            if len(rels) >= max_out: break
        return rels

    def remove_relations(self, subject: str, predicate: str):
        """Remove all relations with given subject and predicate"""
        edges_to_remove = []
        if subject in self.G:
            for _, obj, key, data in self.G.out_edges(subject, keys=True, data=True):
                if data.get('pred') == predicate:
                    edges_to_remove.append((subject, obj, key))
        
        for subj, obj, key in edges_to_remove:
            self.G.remove_edge(subj, obj, key)
        
        # Also remove from storage
        storage.remove_kg_relations(subject, predicate)

    def update_relation(self, subject: str, predicate: str, new_object: str, weight: float = 1.0, **attrs):
        """Update a relation by replacing the object"""
        # Remove existing relations with same subject/predicate
        self.remove_relations(subject, predicate)
        
        # Add the new relation
        self.upsert_relation(subject, predicate, new_object, weight, **attrs)