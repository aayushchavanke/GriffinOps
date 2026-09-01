import sys
import numpy as np
import pandas as pd
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.GraphUtils import GraphUtils
import warnings

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Suppress warnings for cleaner terminal output during team testing
warnings.filterwarnings("ignore")

class AdvancedCausalEngine:
    """
    GriffinOps Phase 2 Causal Engine.
    Upgrades root cause analysis from Linear Granger to Non-Linear PC Algorithm (causal-learn).
    """
    
    def __init__(self, alpha=0.05):
        # Alpha is our statistical significance threshold (5%)
        self.alpha = alpha

    def discover_root_cause(self, telemetry_df: pd.DataFrame):
        """
        Takes a DataFrame where columns are Microservices and rows are Time/Pings.
        Returns the directional Root Cause Graph and detected causal relationships.
        """
        if telemetry_df.empty or len(telemetry_df.columns) < 2:
            return {"status": "INSUFFICIENT_DATA", "edges": [], "root_causes": []}
            
        # 1. Convert our Pandas DataFrame to a raw numpy array for causal-learn
        data_matrix = telemetry_df.to_numpy()
        node_names = telemetry_df.columns.tolist()

        # 2. Run the PC Algorithm with Fisher-Z conditional independence test
        cg = pc(data_matrix, self.alpha, indep_test='fisherz', show_progress=False)

        # 3. Extract the Adjacency Matrix
        # -1 means A causes B. 1 means B causes A. 0 means no direct link.
        adj_matrix = cg.G.graph
        
        return self._format_results(adj_matrix, node_names)

    def _format_results(self, adj_matrix, node_names):
        """Helper method to translate the math matrix into structured SRE findings."""
        edges = []
        root_causes = set()
        
        for i, cause_node in enumerate(node_names):
            for j, victim_node in enumerate(node_names):
                # In causal-learn, an edge from i to j is represented as -1 in adj_matrix[i, j]
                if adj_matrix[i, j] == -1:
                    edges.append({
                        "cause": cause_node,
                        "victim": victim_node,
                        "relationship": "NON_LINEAR_CAUSAL_DEPENDENCY"
                    })
                    root_causes.add(cause_node)
                    
        return {
            "status": "CAUSAL_CASCADE_DETECTED" if edges else "INDEPENDENT_STABLE",
            "edges": edges,
            "root_causes": list(root_causes),
            "adjacency_matrix": adj_matrix.tolist(),
            "nodes": node_names
        }

# ==========================================
# TEAM TESTING BLOCK
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("🤖 [GriffinOps Phase 2] Advanced Causal Discovery (PC Algorithm)")
    print("=" * 65)

    # 1. Simulate 100 pings of telemetry for 3 microservices
    np.random.seed(42)
    pings = 100
    
    # Database spikes first (Root Cause)
    database_latency = np.random.normal(50, 10, pings)
    database_latency[80:] += 500  # Massive spike at ping 80
    
    # Payment API spikes immediately BECAUSE of the Database
    payment_api_latency = database_latency * 1.5 + np.random.normal(10, 5, pings)
    
    # Frontend UI spikes BECAUSE of the Payment API
    frontend_latency = payment_api_latency * 1.2 + np.random.normal(5, 2, pings)

    # 2. Package into DataFrame
    df_telemetry = pd.DataFrame({
        "Database_Node": database_latency,
        "Payment_API": payment_api_latency,
        "Frontend_UI": frontend_latency
    })

    # 3. Run PC Causal Discovery
    engine = AdvancedCausalEngine(alpha=0.05)
    result = engine.discover_root_cause(df_telemetry)

    print("\n🚨 [GriffinOps Non-Linear Root Cause Report] 🚨")
    print("-" * 55)
    for edge in result["edges"]:
        print(f"💥 ROOT CAUSE DETECTED: [{edge['cause']}] is crashing [{edge['victim']}]")
    print(f"🎯 Primary Isolated Culprit: {result['root_causes']}")
    print("-" * 55)
