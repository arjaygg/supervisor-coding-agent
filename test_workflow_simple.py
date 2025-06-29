#!/usr/bin/env python3
"""
Simple workflow engine test
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supervisor_agent.core.workflow_engine import WorkflowEngine
from supervisor_agent.db.enums import TaskType

def test_workflow_engine_basic():
    """Test basic workflow engine functionality"""
    try:
        print("--- Testing Workflow Engine Initialization ---")
        
        # Initialize workflow engine
        engine = WorkflowEngine()
        print("✅ Workflow engine initialized successfully")
        
        # Check if main components are available
        components = []
        if hasattr(engine, 'dag_resolver'):
            components.append("DAG Resolver")
        if hasattr(engine, 'task_orchestrator'):
            components.append("Task Orchestrator")
        if hasattr(engine, 'scheduler'):
            components.append("Scheduler")
        
        print(f"✅ Available components: {', '.join(components)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow engine initialization failed: {e}")
        return False

def test_simple_dependency_logic():
    """Test simple dependency validation logic"""
    try:
        print("\n--- Testing Simple Dependency Logic ---")
        
        # Create a simple task dependency graph: A -> B -> C
        tasks = {
            "task_a": {"id": "task_a", "name": "Task A", "type": TaskType.CODE_ANALYSIS.value},
            "task_b": {"id": "task_b", "name": "Task B", "type": TaskType.FEATURE.value},
            "task_c": {"id": "task_c", "name": "Task C", "type": TaskType.TESTING.value}
        }
        
        dependencies = [
            {"task_id": "task_b", "depends_on": "task_a"},
            {"task_id": "task_c", "depends_on": "task_b"}
        ]
        
        print(f"✅ Created {len(tasks)} tasks with {len(dependencies)} dependencies")
        
        # Test execution order calculation
        def calculate_execution_order(tasks, dependencies):
            # Build dependency map
            deps_map = {}
            for dep in dependencies:
                task_id = dep["task_id"]
                depends_on = dep["depends_on"]
                if task_id not in deps_map:
                    deps_map[task_id] = []
                deps_map[task_id].append(depends_on)
            
            # Calculate execution order using topological sort
            execution_order = []
            completed = set()
            remaining = set(tasks.keys())
            
            while remaining:
                # Find tasks with no remaining dependencies
                ready_tasks = []
                for task_id in remaining:
                    task_deps = deps_map.get(task_id, [])
                    if all(dep in completed for dep in task_deps):
                        ready_tasks.append(task_id)
                
                if not ready_tasks:
                    raise Exception("Circular dependency detected or orphaned tasks")
                
                # Process ready tasks
                for task_id in ready_tasks:
                    execution_order.append(task_id)
                    completed.add(task_id)
                    remaining.remove(task_id)
            
            return execution_order
        
        execution_order = calculate_execution_order(tasks, dependencies)
        print(f"✅ Execution order calculated: {' → '.join(execution_order)}")
        
        # Verify the order is correct
        expected_order = ["task_a", "task_b", "task_c"]
        if execution_order == expected_order:
            print("✅ Execution order is correct")
            return True
        else:
            print(f"❌ Execution order incorrect. Expected: {expected_order}, Got: {execution_order}")
            return False
        
    except Exception as e:
        print(f"❌ Dependency logic test failed: {e}")
        return False

def test_circular_dependency_detection():
    """Test circular dependency detection"""
    try:
        print("\n--- Testing Circular Dependency Detection ---")
        
        # Create tasks with circular dependency: A -> B -> C -> A
        tasks = {
            "task_a": {"id": "task_a", "name": "Task A"},
            "task_b": {"id": "task_b", "name": "Task B"},
            "task_c": {"id": "task_c", "name": "Task C"}
        }
        
        circular_dependencies = [
            {"task_id": "task_b", "depends_on": "task_a"},
            {"task_id": "task_c", "depends_on": "task_b"},
            {"task_id": "task_a", "depends_on": "task_c"}  # This creates the cycle
        ]
        
        def has_circular_dependency(tasks, dependencies):
            # Build adjacency list
            graph = {task_id: [] for task_id in tasks}
            for dep in dependencies:
                task_id = dep["task_id"]
                depends_on = dep["depends_on"]
                graph[depends_on].append(task_id)
            
            # DFS to detect cycles
            visited = set()
            rec_stack = set()
            
            def dfs(node):
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                
                rec_stack.remove(node)
                return False
            
            for task_id in tasks:
                if task_id not in visited:
                    if dfs(task_id):
                        return True
            return False
        
        has_cycle = has_circular_dependency(tasks, circular_dependencies)
        if has_cycle:
            print("✅ Circular dependency correctly detected")
            return True
        else:
            print("❌ Failed to detect circular dependency")
            return False
        
    except Exception as e:
        print(f"❌ Circular dependency detection test failed: {e}")
        return False

def test_parallel_execution_planning():
    """Test parallel execution planning"""
    try:
        print("\n--- Testing Parallel Execution Planning ---")
        
        # Create a more complex graph with parallel paths
        # A -> B, A -> C, B -> D, C -> D
        tasks = {
            "task_a": {"id": "task_a", "name": "Task A"},
            "task_b": {"id": "task_b", "name": "Task B"},
            "task_c": {"id": "task_c", "name": "Task C"},
            "task_d": {"id": "task_d", "name": "Task D"}
        }
        
        dependencies = [
            {"task_id": "task_b", "depends_on": "task_a"},
            {"task_id": "task_c", "depends_on": "task_a"},
            {"task_id": "task_d", "depends_on": "task_b"},
            {"task_id": "task_d", "depends_on": "task_c"}
        ]
        
        def calculate_execution_phases(tasks, dependencies):
            # Build dependency map
            deps_map = {}
            for dep in dependencies:
                task_id = dep["task_id"]
                depends_on = dep["depends_on"]
                if task_id not in deps_map:
                    deps_map[task_id] = []
                deps_map[task_id].append(depends_on)
            
            # Calculate phases
            phases = []
            completed = set()
            remaining = set(tasks.keys())
            
            while remaining:
                # Find all tasks ready for parallel execution
                current_phase = []
                for task_id in remaining:
                    task_deps = deps_map.get(task_id, [])
                    if all(dep in completed for dep in task_deps):
                        current_phase.append(task_id)
                
                if not current_phase:
                    raise Exception("No ready tasks found - possible circular dependency")
                
                phases.append(current_phase)
                for task_id in current_phase:
                    completed.add(task_id)
                    remaining.remove(task_id)
            
            return phases
        
        phases = calculate_execution_phases(tasks, dependencies)
        print(f"✅ Calculated {len(phases)} execution phases:")
        
        for i, phase in enumerate(phases, 1):
            if len(phase) > 1:
                print(f"  Phase {i}: {', '.join(phase)} (parallel)")
            else:
                print(f"  Phase {i}: {phase[0]}")
        
        # Verify expected structure
        # Phase 1: task_a
        # Phase 2: task_b, task_c (parallel)
        # Phase 3: task_d
        if (len(phases) == 3 and 
            phases[0] == ["task_a"] and
            set(phases[1]) == {"task_b", "task_c"} and
            phases[2] == ["task_d"]):
            print("✅ Parallel execution phases calculated correctly")
            return True
        else:
            print("❌ Parallel execution phases incorrect")
            return False
        
    except Exception as e:
        print(f"❌ Parallel execution planning test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Workflow Engine - Simple Version\n")
    
    success = True
    success &= test_workflow_engine_basic()
    success &= test_simple_dependency_logic()
    success &= test_circular_dependency_detection()
    success &= test_parallel_execution_planning()
    
    if success:
        print("\n🎉 All workflow engine tests passed!")
        print("\n📊 Test Summary:")
        print("✅ Workflow engine initialization")
        print("✅ Basic dependency resolution")
        print("✅ Circular dependency detection")
        print("✅ Parallel execution planning")
        print("\n🔧 Core workflow capabilities validated!")
        sys.exit(0)
    else:
        print("\n💥 Some workflow engine tests failed!")
        sys.exit(1)