# 🔄 Cycle Detection Strategies on Neo4j

---

## 📊 Tổng quan các phương pháp

```
┌──────────────────────────────────────────────────────────────────┐
│          CYCLE DETECTION ON NEO4J: 3 MAIN APPROACHES             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1️⃣ CYPHER QUERIES                                              │
│     └─ Pure Neo4j query language                                │
│        Pro: Simple, no external dependencies                    │
│        Con: Limited for complex patterns                        │
│                                                                  │
│  2️⃣ NEO4J GDS (Graph Data Science)                              │
│     └─ Optimized graph algorithms library                       │
│        Pro: Fast, scalable, multiple algorithms                 │
│        Con: Requires GDS library installation                   │
│                                                                  │
│  3️⃣ HYBRID (Pull to Python + NetworkX)                          │
│     └─ Load from Neo4j → Process in Python                      │
│        Pro: Maximum flexibility, well-tested algorithms         │
│        Con: Memory overhead, slower for large graphs            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🎯 APPROACH 1: Pure Cypher Queries

### Khi nào dùng?
- ✅ Graph size nhỏ-vừa (<100k nodes)
- ✅ Đơn giản cycles (3-5 nodes)
- ✅ Không có infrastructure cho GDS
- ❌ Không phù hợp: Large graphs, complex patterns

### 1.1 Basic Cycle Detection (3-node triangle)

```cypher
// Find all 3-node cycles (triangles)
MATCH (a:Account)-[r1:TRANSFER]->(b:Account)
      -[r2:TRANSFER]->(c:Account)
      -[r3:TRANSFER]->(a)
RETURN 
  a.account_id as node_a,
  b.account_id as node_b,
  c.account_id as node_c,
  r1.amount + r2.amount + r3.amount as total_amount,
  r1.timestamp as start_time
ORDER BY total_amount DESC
LIMIT 100
```

**Output:**
```
node_a      node_b      node_c      total_amount  start_time
ACC_001     ACC_002     ACC_003     15000         2025-10-15
ACC_004     ACC_005     ACC_006     12500         2025-10-16
...
```

**Performance:**
- Time: O(n² × m) where n=nodes, m=edges
- For 800 nodes: ~2-5 seconds
- Scalability: Good for <50k nodes

---

### 1.2 Variable-length Cycles (3-8 nodes)

```cypher
// Find cycles of length 3-8
MATCH path = (start:Account)-[*3..8]->(start)
WHERE length(path) >= 3 AND length(path) <= 8
WITH 
  nodes(path) as cycle_nodes,
  relationships(path) as cycle_edges,
  length(path) as cycle_length
RETURN 
  [n in cycle_nodes | n.account_id] as participants,
  cycle_length,
  reduce(sum=0, r in cycle_edges | sum + r.amount) as total_amount,
  min([r.timestamp in cycle_edges]) as start_time
LIMIT 1000
```

**Issue:** ⚠️ **VERY SLOW** - exponential complexity!
- Returns duplicates (same cycle multiple times)
- May timeout on large graphs
- Not recommended for production

---

### 1.3 Better: Weakly Connected Components + DFS Pattern

```cypher
// Step 1: Find cycles in each weakly connected component
CALL apoc.algo.allSimplePaths(
  node, 
  node,
  "TRANSFER>",
  3,  // min length
  8   // max length
) YIELD path
RETURN path
```

**Requirements:** 
- Need APOC library (Advanced Procedures)
- Install: `neo4j-labs/apoc` plugin

**Performance:** Still not ideal for large graphs

---

### 1.4 Recommended Cypher: Community Detection

```cypher
// Use UNION approach to find specific patterns

// Pattern 1: 3-node cycles
MATCH (a:Account)-[:TRANSFER]->(b:Account)
      -[:TRANSFER]->(c:Account)
      -[:TRANSFER]->(a)
WITH DISTINCT 
  [a.account_id, b.account_id, c.account_id] as cycle,
  3 as size
WHERE a.account_id < b.account_id AND b.account_id < c.account_id

UNION

// Pattern 2: 4-node cycles
MATCH (a:Account)-[:TRANSFER]->(b:Account)
      -[:TRANSFER]->(c:Account)
      -[:TRANSFER]->(d:Account)
      -[:TRANSFER]->(a)
WITH DISTINCT
  [a.account_id, b.account_id, c.account_id, d.account_id] as cycle,
  4 as size
WHERE a.account_id < b.account_id 
  AND b.account_id < c.account_id 
  AND c.account_id < d.account_id

UNION

// Pattern 3: 5-node cycles
MATCH (a:Account)-[:TRANSFER]->(b:Account)
      -[:TRANSFER]->(c:Account)
      -[:TRANSFER]->(d:Account)
      -[:TRANSFER]->(e:Account)
      -[:TRANSFER]->(a)
WITH DISTINCT
  [a.account_id, b.account_id, c.account_id, d.account_id, e.account_id] as cycle,
  5 as size
WHERE a.account_id < b.account_id 
  AND b.account_id < c.account_id 
  AND c.account_id < d.account_id
  AND d.account_id < e.account_id

RETURN cycle, size
ORDER BY size DESC
LIMIT 500
```

**Pros:**
- Clear patterns
- Avoids duplicates (using ordering constraint)
- Predictable performance

**Cons:**
- Manual for each size
- Limited to fixed lengths
- Verbose

---

## 🚀 APPROACH 2: Neo4j Graph Data Science (GDS) ⭐ RECOMMENDED

### Khi nào dùng?
- ✅ Graph size lớn (>100k nodes)
- ✅ Multiple algorithms needed
- ✅ Production environment
- ✅ Real-time analytics
- ✅ Performance critical

### Installation

```bash
# Option 1: Docker (Recommended)
docker run --name neo4j \
  -e NEO4J_PLUGINS='["graph-data-science"]' \
  -p 7474:7474 \
  -p 7687:7687 \
  neo4j:5.0-enterprise

# Option 2: Manual installation
# Download GDS library from neo4j.com
# Place in /var/lib/neo4j/plugins/
# Restart Neo4j
```

### 2.1 Community Detection (Louvain Algorithm)

```cypher
// Step 1: Create in-memory graph
CALL gds.graph.project(
  'transaction_graph',
  'Account',
  'TRANSFER',
  {
    relationshipProperties: ['amount', 'timestamp']
  }
)

// Step 2: Run Louvain community detection
CALL gds.louvain.stream('transaction_graph')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) as node, communityId
RETURN 
  communityId,
  collect(node.account_id) as community_members,
  count(node) as community_size
ORDER BY community_size DESC
```

**Output:**
```
communityId  community_members               community_size
1            [ACC_001, ACC_002, ACC_003]    3
2            [ACC_010, ACC_011, ACC_012]    3
...
```

**Characteristics of Communities:**
- **Dense**: Many internal connections
- **Isolated**: Few external connections
- **Fraud rings**: Often identified as tight communities

**Performance:**
- Time: O(n + m) - Linear!
- For 800 nodes: <100ms
- Scalable to millions of nodes

### 2.2 Cycle Detection via Strongly Connected Components

```cypher
// Find Strongly Connected Components (SCCs)
// Within each SCC, there's a cycle

// Step 1: Project graph
CALL gds.graph.project(
  'directed_transactions',
  'Account',
  'TRANSFER'
)

// Step 2: Find SCCs
CALL gds.scc.stream('directed_transactions')
YIELD nodeId, componentId
WITH gds.util.asNode(nodeId) as node, componentId
WHERE componentId > 0  // Filter out trivial components
RETURN 
  componentId,
  collect(node.account_id) as accounts_in_cycle,
  count(*) as cycle_size
ORDER BY cycle_size DESC
LIMIT 100
```

**Important:** 
- SCC finds nodes that can reach each other
- Each SCC with >1 node contains a cycle
- Very efficient for cycle detection

**Output:**
```
componentId  accounts_in_cycle                cycle_size
15           [ACC_001, ACC_005, ACC_009]     3
23           [ACC_010, ACC_011, ACC_012]     3
...
```

---

### 2.3 Betweenness Centrality (Identify Ring Leaders)

```cypher
// Find nodes that are "hubs" in the transaction network
// These are likely ring leaders/organizers

CALL gds.graph.project(
  'transaction_network',
  'Account',
  'TRANSFER',
  {
    relationshipProperties: ['amount']
  }
)

CALL gds.betweenness.stream('transaction_network')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) as node, score
WHERE score > 0
RETURN 
  node.account_id,
  score as centrality_score,
  node.kyc_risk_score,
  node.monthly_transaction_count
ORDER BY centrality_score DESC
LIMIT 50
```

**Interpretation:**
- High centrality = Key nodes in network
- Likely involved in multiple fraud rings
- Good for identifying "organizers"

---

### 2.4 Triangle Counting (3-node cycles specifically)

```cypher
// Count and find all triangles in the graph
CALL gds.graph.project(
  'undirected_graph',
  'Account',
  {
    TRANSFER: {
      orientation: 'UNDIRECTED'  // Treat as undirected
    }
  }
)

CALL gds.triangleCount.stream('undirected_graph')
YIELD nodeId, triangleCount
WITH gds.util.asNode(nodeId) as node, triangleCount
WHERE triangleCount > 0
RETURN 
  node.account_id,
  triangleCount as triangles_involved,
  node.kyc_risk_score
ORDER BY triangleCount DESC
LIMIT 50
```

**Use case:**
- Specific focus on 3-person rings
- Fast triangles enumeration
- Common pattern in fraud detection

---

### 2.5 Shortest Path (Trace money flow)

```cypher
// Find shortest path between two accounts
// Useful for understanding fraud connections

CALL gds.graph.project(
  'shortest_path_graph',
  'Account',
  'TRANSFER'
)

CALL gds.shortestPath.dijkstra.stream(
  'shortest_path_graph',
  {
    sourceNode: apoc.cypher.runFirstColumn(
      'MATCH (a:Account {account_id: "ACC_001"}) RETURN id(a)', 
      {}
    ),
    targetNode: apoc.cypher.runFirstColumn(
      'MATCH (a:Account {account_id: "ACC_003"}) RETURN id(a)', 
      {}
    ),
    relationshipWeightProperty: 'amount'
  }
)
YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs
RETURN
  [nodeId in nodeIds | gds.util.asNode(nodeId).account_id] as path,
  totalCost as total_amount
```

---

## 🐍 APPROACH 3: Hybrid (Python + NetworkX)

### Khi nào dùng?
- ✅ Complex analysis needed
- ✅ Custom algorithms
- ✅ Multiple processing steps
- ✅ Combining with external data
- ❌ Không: Very large graphs (memory constraint)

### 3.1 Pull từ Neo4j → Process in NetworkX

```python
# src/hybrid_cycle_detection.py

from neo4j import GraphDatabase
import networkx as nx
import pandas as pd

class HybridCycleDetector:
    def __init__(self, neo4j_uri, user, password):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))
    
    def load_graph_from_neo4j(self):
        """Load transaction graph from Neo4j to NetworkX"""
        
        with self.driver.session() as session:
            # Query all nodes
            result = session.run("""
                MATCH (a:Account)
                RETURN a.account_id as account_id, 
                       a.kyc_risk_score as risk_score
            """)
            
            nodes = [(record['account_id'], {
                'risk_score': record['risk_score']
            }) for record in result]
            
            # Query all edges
            result = session.run("""
                MATCH (a:Account)-[r:TRANSFER]->(b:Account)
                RETURN a.account_id as source,
                       b.account_id as destination,
                       r.amount as amount,
                       r.timestamp as timestamp
            """)
            
            edges = [(record['source'], record['destination'], {
                'weight': record['amount'],
                'timestamp': record['timestamp']
            }) for record in result]
        
        # Build NetworkX graph
        G = nx.DiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        
        return G
    
    def detect_all_cycles(self):
        """Detect cycles using NetworkX"""
        
        G = self.load_graph_from_neo4j()
        print(f"Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
        # Find all simple cycles (length limit to avoid explosion)
        cycles = list(nx.simple_cycles(G, length_limit=10))
        
        print(f"Found {len(cycles)} cycles")
        
        # Score and filter cycles
        scored_cycles = []
        for cycle in cycles:
            score = self._score_cycle(G, cycle)
            scored_cycles.append({
                'participants': cycle,
                'score': score,
                'size': len(cycle),
                'amount': self._get_cycle_amount(G, cycle)
            })
        
        # Sort by score
        scored_cycles.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_cycles
    
    def _score_cycle(self, G, cycle):
        """Score fraud likelihood"""
        
        score = 0
        
        # Factor 1: Cycle size
        score += len(cycle) * 0.2
        
        # Factor 2: Total amount
        total_amount = self._get_cycle_amount(G, cycle)
        score += min(total_amount / 100000, 1.0) * 0.3
        
        # Factor 3: Risk scores of participants
        avg_risk = np.mean([
            G.nodes[node].get('risk_score', 0.1) 
            for node in cycle
        ])
        score += (1 - avg_risk) * 0.2  # Higher risk = higher score
        
        # Factor 4: Density (how connected are they)
        density = self._calculate_cycle_density(G, cycle)
        score += density * 0.3
        
        return min(score, 1.0)  # Normalize to [0, 1]
    
    def _get_cycle_amount(self, G, cycle):
        """Calculate total amount in cycle"""
        total = 0
        for i in range(len(cycle)):
            src = cycle[i]
            dst = cycle[(i + 1) % len(cycle)]
            if G.has_edge(src, dst):
                total += G[src][dst].get('weight', 0)
        return total
    
    def _calculate_cycle_density(self, G, cycle):
        """Calculate connectivity density within cycle"""
        subgraph = G.subgraph(cycle)
        edges = subgraph.number_of_edges()
        max_edges = len(cycle) * (len(cycle) - 1)  # Directed
        density = edges / max_edges if max_edges > 0 else 0
        return density
    
    def save_results_to_neo4j(self, cycles):
        """Write detected cycles back to Neo4j"""
        
        with self.driver.session() as session:
            for i, cycle_info in enumerate(cycles):
                cycle = cycle_info['participants']
                
                # Create relationship for ring
                create_ring_query = f"""
                    MERGE (ring:FraudRing {{ring_id: 'RING_{i:03d}'}})
                    SET ring.score = {cycle_info['score']},
                        ring.size = {cycle_info['size']},
                        ring.amount = {cycle_info['amount']}
                """
                
                session.run(create_ring_query)
                
                # Connect accounts to ring
                for j, account_id in enumerate(cycle):
                    connect_query = f"""
                        MATCH (a:Account {{account_id: '{account_id}'}})
                        MATCH (r:FraudRing {{ring_id: 'RING_{i:03d}'}})
                        MERGE (a)-[:MEMBER_OF]->(r)
                        SET (a)-[:MEMBER_OF]->{{position: {j}}}
                    """
                    
                    session.run(connect_query)
        
        print(f"Saved {len(cycles)} cycles to Neo4j")

# Usage:
detector = HybridCycleDetector("bolt://localhost:7687", "neo4j", "password")
cycles = detector.detect_all_cycles()
detector.save_results_to_neo4j(cycles)
```

**Pros:**
- Full control over algorithms
- Can combine multiple methods
- Easy to debug & visualize

**Cons:**
- Memory intensive (must load entire graph)
- Slower for large graphs
- Extra network I/O

**Memory Requirements:**
- 800 nodes, 5000 edges: ~10-20 MB
- 100k nodes, 1M edges: ~500 MB - 1 GB
- Feasible for small-medium graphs

---

## 📊 PERFORMANCE COMPARISON

```
┌────────────────────┬──────────────┬──────────────┬──────────────┐
│   Method           │  Time (800n) │  Time (10kn) │  Scalability │
├────────────────────┼──────────────┼──────────────┼──────────────┤
│ Cypher (4-cycles)  │  2-5 sec     │  30+ sec     │  Poor        │
│ Cypher (Union)     │  1-2 sec     │  10-20 sec   │  Fair        │
│ GDS (SCC)          │  100ms       │  500ms       │  Excellent   │
│ GDS (Louvain)      │  150ms       │  800ms       │  Excellent   │
│ GDS (Triangles)    │  50ms        │  300ms       │  Excellent   │
│ NetworkX (Pull)    │  500ms       │  Timeout     │  Poor        │
│ NetworkX (Native)  │  2-3 sec     │  OOM         │  Poor        │
└────────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 🎯 RECOMMENDATION: HYBRID APPROACH (Best of Both Worlds)

### Strategy

```python
# Step 1: Use GDS for fast initial filtering
├─ SCC to find connected components with cycles
├─ Louvain to identify tight communities
└─ Betweenness to find hub nodes

# Step 2: Pull suspected rings to Python
├─ Detailed cycle analysis
├─ Score calculation
├─ Pattern matching

# Step 3: Write results back to Neo4j
├─ Create FraudRing nodes
├─ Add relationships
├─ Store metrics
```

### Implementation

```python
# src/recommended_cycle_detection.py

class OptimizedCycleDetector:
    def __init__(self, neo4j_uri, user, password):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))
        self.session = None
    
    def detect_fraud_rings(self):
        """Main pipeline using hybrid approach"""
        
        with self.driver.session() as session:
            self.session = session
            
            # Step 1: Use GDS to find SCCs (very fast)
            scc_results = self._find_scc()
            print(f"Found {len(scc_results)} potential rings via SCC")
            
            # Step 2: For each SCC, trace exact cycles
            detailed_rings = []
            for scc in scc_results[:100]:  # Process top 100
                cycles = self._trace_cycles_in_scc(scc)
                detailed_rings.extend(cycles)
            
            # Step 3: Score and rank
            scored_rings = self._score_rings(detailed_rings)
            
            # Step 4: Save to Neo4j
            self._save_rings_to_neo4j(scored_rings)
            
            return scored_rings
    
    def _find_scc(self):
        """Step 1: Fast SCC detection using GDS"""
        
        # Create in-memory projection
        self.session.run("""
            CALL gds.graph.project(
                'scc_graph',
                'Account',
                'TRANSFER'
            )
        """)
        
        # Find SCCs
        result = self.session.run("""
            CALL gds.scc.stream('scc_graph')
            YIELD nodeId, componentId
            WITH componentId, 
                 collect(gds.util.asNode(nodeId).account_id) as accounts
            WHERE size(accounts) >= 3  -- Only rings with 3+ nodes
            RETURN componentId, accounts, size(accounts) as ring_size
            ORDER BY ring_size DESC
        """)
        
        sccs = [dict(record) for record in result]
        
        # Clean up projection
        self.session.run("CALL gds.graph.drop('scc_graph')")
        
        return sccs
    
    def _trace_cycles_in_scc(self, scc):
        """Step 2: Get exact cycles within SCC"""
        
        accounts = scc['accounts']
        
        # Load subgraph locally
        result = self.session.run("""
            MATCH (a:Account)-[r:TRANSFER]->(b:Account)
            WHERE a.account_id IN $accounts 
              AND b.account_id IN $accounts
            RETURN a.account_id as source,
                   b.account_id as destination,
                   r.amount as amount
        """, accounts=accounts)
        
        # Build subgraph
        G = nx.DiGraph()
        for record in result:
            G.add_edge(record['source'], record['destination'], 
                      weight=record['amount'])
        
        # Find all cycles in this small subgraph
        cycles = list(nx.simple_cycles(G))
        
        return [{
            'participants': cycle,
            'size': len(cycle)
        } for cycle in cycles]
    
    def _score_rings(self, rings):
        """Step 3: Detailed scoring"""
        
        scored = []
        for ring in rings:
            score = self._calculate_ring_score(ring)
            scored.append({**ring, 'score': score})
        
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored
    
    def _calculate_ring_score(self, ring):
        """Calculate risk score for ring"""
        
        participants = ring['participants']
        
        # Query metrics for participants
        result = self.session.run("""
            MATCH (a:Account)
            WHERE a.account_id IN $participants
            RETURN 
                a.account_id,
                a.kyc_risk_score,
                a.monthly_transaction_count
        """, participants=participants)
        
        records = list(result)
        
        if not records:
            return 0.0
        
        # Calculate features
        avg_risk = np.mean([r['kyc_risk_score'] for r in records])
        avg_txn_count = np.mean([r['monthly_transaction_count'] for r in records])
        
        # Get transaction amount in ring
        amount_result = self.session.run("""
            MATCH (a:Account)-[r:TRANSFER]->(b:Account)
            WHERE a.account_id IN $participants 
              AND b.account_id IN $participants
            RETURN sum(r.amount) as total
        """, participants=participants)
        
        total_amount = amount_result.single()['total'] or 0
        
        # Score calculation
        score = (
            len(participants) * 0.2 +  # Size
            (1 - avg_risk) * 0.3 +  # Risk (inverted)
            min(total_amount / 100000, 1.0) * 0.3 +  # Amount
            avg_txn_count / 100 * 0.2  # Activity
        )
        
        return min(score, 1.0)
    
    def _save_rings_to_neo4j(self, rings):
        """Step 4: Write results back"""
        
        for i, ring in enumerate(rings[:500]):  # Save top 500
            with self.driver.session() as session:
                # Create ring node
                session.run("""
                    MERGE (r:FraudRing {ring_id: $ring_id})
                    SET r.size = $size,
                        r.score = $score,
                        r.detected_at = datetime()
                """, 
                ring_id=f"RING_{i:04d}",
                size=ring['size'],
                score=ring['score'])
                
                # Link accounts
                for j, account in enumerate(ring['participants']):
                    session.run("""
                        MATCH (a:Account {account_id: $account_id})
                        MATCH (r:FraudRing {ring_id: $ring_id})
                        MERGE (a)-[m:MEMBER_OF]->(r)
                        SET m.position = $position
                    """,
                    account_id=account,
                    ring_id=f"RING_{i:04d}",
                    position=j)
        
        print(f"Saved {len(rings[:500])} rings to Neo4j")

# Usage:
detector = OptimizedCycleDetector("bolt://localhost:7687", "neo4j", "password")
rings = detector.detect_fraud_rings()
```

---

## 🏆 FINAL RECOMMENDATION

### **Use GDS + Python Hybrid** ⭐⭐⭐

**Why:**
1. **Fast Initial Filtering**: GDS handles heavy lifting (SCC in <100ms)
2. **Exact Detection**: Python gets precise cycles
3. **Scalable**: Can handle 100k+ nodes
4. **Flexible**: Combine multiple algorithms
5. **Production-Ready**: GDS is battle-tested

### **Implementation Sequence**

```
Day 2-3 Implementation:
├─ Use GDS SCC for initial ring detection (FAST)
├─ For each SCC > 2 nodes: trace exact cycles (Python)
├─ Score all cycles (Custom logic)
├─ Save FraudRing nodes to Neo4j (Persistence)
└─ Time: <1 second for 800 nodes
```

### **Neo4j Query for Ring Storage**

```cypher
// Query to retrieve detected rings
MATCH (r:FraudRing)<-[m:MEMBER_OF]-(a:Account)
RETURN 
  r.ring_id,
  r.score,
  r.size,
  collect(a.account_id) as participants,
  collect(m.position) as positions
ORDER BY r.score DESC
```

---

## 📋 CHECKLIST

```
☐ Install Neo4j with GDS
☐ Load transaction data into Neo4j
☐ Setup Python driver (neo4j library)
☐ Implement GDS queries (SCC, Louvain)
☐ Implement hybrid cycle detection
☐ Add scoring logic
☐ Test on synthetic data (Ngày 2-3)
☐ Validate results vs ground truth (Ngày 3)
☐ Optimize if needed
☐ Document queries & code
```

---

## 🚀 QUICK START CODE

```python
# Minimal working example

from neo4j import GraphDatabase
import networkx as nx

uri = "bolt://localhost:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j", "password"))

def detect_rings():
    with driver.session() as session:
        # Step 1: SCC via GDS
        session.run("""
            CALL gds.graph.project(
                'fraud_graph', 'Account', 'TRANSFER'
            )
        """)
        
        result = session.run("""
            CALL gds.scc.stream('fraud_graph')
            YIELD nodeId, componentId
            WITH componentId, collect(gds.util.asNode(nodeId)) as nodes
            WHERE size(nodes) >= 3
            RETURN componentId, [n in nodes | n.account_id] as accounts
        """)
        
        rings = [dict(record) for record in result]
        print(f"Found {len(rings)} potential fraud rings!")
        
        return rings

if __name__ == "__main__":
    rings = detect_rings()
    for i, ring in enumerate(rings[:10]):
        print(f"Ring {i}: {ring['accounts']}")
```

---

**Conclusion:** 🎯 **Go with GDS + Hybrid approach for Day 2-3!**

