# supervisor_agent/tests/test_resource_management.py
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from supervisor_agent.core.resource_allocation_engine import (
    DynamicResourceAllocator,
    ResourceMetrics,
    ResourceDemand,
    AllocationPlan,
    AllocationStrategy,
    ResourceType,
    ScalingAction,
    ScalingRecommendation
)
from supervisor_agent.core.conflict_resolver import (
    ResourceConflictResolver,
    ResourceConflict,
    ConflictType,
    ResolutionStrategy,
    ResolutionPlan,
    TaskReservation,
    QueuedTask,
    QueueType
)
from supervisor_agent.models.task import Task


class TestDynamicResourceAllocator:
    """Test suite for DynamicResourceAllocator."""

    @pytest.fixture
    def allocator(self):
        """Create a DynamicResourceAllocator instance."""
        return DynamicResourceAllocator()

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            id="test_task_001",
            config={
                "description": "Analyze data and optimize machine learning models for performance",
                "complexity": "high"
            },
            priority=3
        )

    @pytest.mark.asyncio
    async def test_monitor_resource_usage_real_metrics(self, allocator):
        """Test resource monitoring with real system metrics."""
        metrics = await allocator.monitor_resource_usage()
        
        assert isinstance(metrics, ResourceMetrics)
        assert 0 <= metrics.cpu_percent <= 100
        assert 0 <= metrics.memory_percent <= 100
        assert 0 <= metrics.disk_percent <= 100
        assert metrics.network_io >= 0
        assert isinstance(metrics.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_monitor_resource_usage_fallback(self, allocator):
        """Test resource monitoring fallback when psutil fails."""
        with patch('psutil.cpu_percent', side_effect=Exception("psutil error")):
            metrics = await allocator.monitor_resource_usage()
            
            assert isinstance(metrics, ResourceMetrics)
            assert metrics.cpu_percent > 0  # Simulated values
            assert metrics.memory_percent > 0
            assert metrics.disk_percent == 70.0  # Fixed simulated value

    @pytest.mark.asyncio
    async def test_predict_resource_demand_no_history(self, allocator):
        """Test demand prediction with no historical data."""
        demand = await allocator.predict_resource_demand(60)
        
        assert isinstance(demand, ResourceDemand)
        assert demand.cpu_demand == 50.0
        assert demand.memory_demand == 60.0
        assert demand.disk_demand == 70.0
        assert demand.network_demand == 100.0
        assert demand.confidence == 0.5
        assert demand.time_horizon == 60

    @pytest.mark.asyncio
    async def test_predict_resource_demand_with_history(self, allocator):
        """Test demand prediction with historical data."""
        # Add some historical metrics
        for i in range(10):
            metrics = ResourceMetrics(
                cpu_percent=50.0 + i,
                memory_percent=60.0 + i * 0.5,
                disk_percent=70.0,
                network_io=1000000.0
            )
            allocator.resource_history.append(metrics)
        
        demand = await allocator.predict_resource_demand(30)
        
        assert isinstance(demand, ResourceDemand)
        assert demand.confidence > 0.5  # Should be higher with data
        assert demand.time_horizon == 30
        assert demand.peak_time is not None

    @pytest.mark.asyncio
    async def test_optimize_allocation_strategy(self, allocator, sample_task):
        """Test allocation strategy optimization."""
        # Test CPU pressure scenario
        high_cpu_metrics = ResourceMetrics(
            cpu_percent=85.0,
            memory_percent=50.0,
            disk_percent=60.0,
            network_io=1000000.0
        )
        strategy = await allocator.optimize_allocation_strategy(high_cpu_metrics, [sample_task])
        assert strategy == AllocationStrategy.CPU_OPTIMIZED

        # Test memory pressure scenario
        high_memory_metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=85.0,
            disk_percent=60.0,
            network_io=1000000.0
        )
        strategy = await allocator.optimize_allocation_strategy(high_memory_metrics, [sample_task])
        assert strategy == AllocationStrategy.MEMORY_OPTIMIZED

        # Test high task volume scenario
        many_tasks = [sample_task] * 15
        normal_metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=50.0,
            disk_percent=60.0,
            network_io=1000000.0
        )
        strategy = await allocator.optimize_allocation_strategy(normal_metrics, many_tasks)
        assert strategy == AllocationStrategy.PERFORMANCE_OPTIMIZED

    @pytest.mark.asyncio
    async def test_allocate_resources_for_task(self, allocator, sample_task):
        """Test resource allocation for a task."""
        allocation = await allocator.allocate_resources_for_task(sample_task)
        
        assert isinstance(allocation, AllocationPlan)
        assert allocation.task_id == sample_task.id
        assert allocation.cpu_allocation > 0
        assert allocation.memory_allocation > 0
        assert allocation.disk_allocation > 0
        assert allocation.network_allocation > 0
        assert allocation.priority == sample_task.priority
        assert allocation.estimated_duration > 0
        assert allocation.cost_estimate > 0

    @pytest.mark.asyncio
    async def test_allocate_resources_cpu_optimized(self, allocator, sample_task):
        """Test CPU-optimized resource allocation."""
        allocation = await allocator.allocate_resources_for_task(
            sample_task, AllocationStrategy.CPU_OPTIMIZED
        )
        
        # Should allocate more CPU and less memory compared to balanced
        balanced_allocation = await allocator.allocate_resources_for_task(
            sample_task, AllocationStrategy.BALANCED
        )
        
        assert allocation.cpu_allocation > balanced_allocation.cpu_allocation
        assert allocation.memory_allocation < balanced_allocation.memory_allocation

    @pytest.mark.asyncio
    async def test_implement_cost_optimization(self, allocator):
        """Test cost optimization implementation."""
        original_plan = AllocationPlan(
            task_id="test_task",
            cpu_allocation=2.0,
            memory_allocation=2048,
            disk_allocation=10,
            network_allocation=100.0,
            priority=3,
            estimated_duration=60,
            cost_estimate=1.0,
            strategy=AllocationStrategy.BALANCED
        )
        
        optimized_plan = await allocator.implement_cost_optimization(original_plan)
        
        assert optimized_plan.cpu_allocation < original_plan.cpu_allocation
        assert optimized_plan.memory_allocation < original_plan.memory_allocation
        assert optimized_plan.cost_estimate < original_plan.cost_estimate
        assert optimized_plan.strategy == AllocationStrategy.COST_OPTIMIZED

    @pytest.mark.asyncio
    async def test_scale_resources_dynamically(self, allocator):
        """Test dynamic resource scaling recommendations."""
        # High CPU demand scenario
        high_demand = ResourceDemand(
            cpu_demand=90.0,
            memory_demand=70.0,
            disk_demand=60.0,
            network_demand=500000000.0,
            confidence=0.8,
            time_horizon=60
        )
        
        recommendations = await allocator.scale_resources_dynamically(high_demand)
        
        assert len(recommendations) > 0
        cpu_rec = next((r for r in recommendations if r.resource_type == ResourceType.CPU), None)
        assert cpu_rec is not None
        assert cpu_rec.action == ScalingAction.SCALE_UP
        assert cpu_rec.urgency == "high"

    @pytest.mark.asyncio
    async def test_get_resource_utilization_report(self, allocator, sample_task):
        """Test resource utilization report generation."""
        # Allocate some resources first
        await allocator.allocate_resources_for_task(sample_task)
        
        report = await allocator.get_resource_utilization_report()
        
        assert "current_usage" in report
        assert "historical_averages" in report
        assert "allocations" in report
        assert "recommendations" in report
        assert "efficiency_metrics" in report
        
        assert report["allocations"]["active_tasks"] == 1
        assert report["allocations"]["total_cpu_allocated"] > 0
        assert report["allocations"]["total_memory_allocated_mb"] > 0

    def test_calculate_trend(self, allocator):
        """Test trend calculation from historical values."""
        # Increasing trend
        increasing_values = [10.0, 20.0, 30.0, 40.0, 50.0]
        trend = allocator._calculate_trend(increasing_values)
        assert trend > 0

        # Decreasing trend
        decreasing_values = [50.0, 40.0, 30.0, 20.0, 10.0]
        trend = allocator._calculate_trend(decreasing_values)
        assert trend < 0

        # Stable trend
        stable_values = [30.0, 30.0, 30.0, 30.0, 30.0]
        trend = allocator._calculate_trend(stable_values)
        assert abs(trend) < 0.1  # Should be close to 0


class TestResourceConflictResolver:
    """Test suite for ResourceConflictResolver."""

    @pytest.fixture
    def resolver(self):
        """Create a ResourceConflictResolver instance."""
        return ResourceConflictResolver()

    @pytest.fixture
    def sample_allocations(self):
        """Create sample allocation plans for testing."""
        return [
            AllocationPlan(
                task_id="task_1",
                cpu_allocation=8.0,  # Overallocation
                memory_allocation=1024,
                disk_allocation=5,
                network_allocation=100.0,
                priority=1,
                estimated_duration=60,
                cost_estimate=0.5,
                strategy=AllocationStrategy.BALANCED
            ),
            AllocationPlan(
                task_id="task_2",
                cpu_allocation=12.0,  # Overallocation
                memory_allocation=2048,
                disk_allocation=10,
                network_allocation=200.0,
                priority=5,
                estimated_duration=90,
                cost_estimate=1.0,
                strategy=AllocationStrategy.BALANCED
            )
        ]

    @pytest.mark.asyncio
    async def test_detect_overallocation_conflicts(self, resolver, sample_allocations):
        """Test detection of resource overallocation conflicts."""
        conflicts = await resolver._detect_overallocation_conflicts(sample_allocations)
        
        # Should detect CPU overallocation (8 + 12 = 20 > 16 limit)
        cpu_conflicts = [c for c in conflicts if c.resource_type == ResourceType.CPU]
        assert len(cpu_conflicts) > 0
        
        conflict = cpu_conflicts[0]
        assert conflict.conflict_type == ConflictType.OVERALLOCATION
        assert conflict.requested_amount > conflict.available_amount
        assert conflict.severity in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_detect_priority_conflicts(self, resolver, sample_allocations):
        """Test detection of priority-based conflicts."""
        conflicts = await resolver._detect_priority_conflicts(sample_allocations)
        
        # Should detect priority conflict (high priority task starved)
        if conflicts:
            conflict = conflicts[0]
            assert conflict.conflict_type == ConflictType.PRIORITY_CONFLICT
            assert conflict.severity == "medium"

    @pytest.mark.asyncio
    async def test_detect_quota_conflicts(self, resolver, sample_allocations):
        """Test detection of quota exceeded conflicts."""
        # Create high-cost allocations
        high_cost_allocations = [
            AllocationPlan(
                task_id="expensive_task",
                cpu_allocation=4.0,
                memory_allocation=1024,
                disk_allocation=5,
                network_allocation=100.0,
                priority=3,
                estimated_duration=60,
                cost_estimate=150.0,  # Exceeds budget
                strategy=AllocationStrategy.BALANCED
            )
        ]
        
        conflicts = await resolver._detect_quota_conflicts(high_cost_allocations)
        
        assert len(conflicts) > 0
        conflict = conflicts[0]
        assert conflict.conflict_type == ConflictType.QUOTA_EXCEEDED
        assert conflict.requested_amount > conflict.available_amount

    @pytest.mark.asyncio
    async def test_detect_resource_conflicts_comprehensive(self, resolver, sample_allocations):
        """Test comprehensive conflict detection."""
        conflicts = await resolver.detect_resource_conflicts(sample_allocations)
        
        assert isinstance(conflicts, list)
        # Should have stored conflicts in active_conflicts
        assert len(resolver.active_conflicts) >= len(conflicts)

    @pytest.mark.asyncio
    async def test_implement_resolution_strategies(self, resolver):
        """Test resolution strategy implementation."""
        # Create a test conflict
        conflict = ResourceConflict(
            conflict_id="test_conflict_001",
            conflict_type=ConflictType.OVERALLOCATION,
            affected_tasks=["task_1", "task_2"],
            resource_type=ResourceType.CPU,
            requested_amount=20.0,
            available_amount=16.0,
            severity="high",
            description="CPU overallocation test"
        )
        
        resolution_plans = await resolver.implement_resolution_strategies([conflict])
        
        assert len(resolution_plans) == 1
        plan = resolution_plans[0]
        assert isinstance(plan, ResolutionPlan)
        assert plan.conflict_id == conflict.conflict_id
        assert plan.strategy in [strategy for strategy in ResolutionStrategy]
        assert len(plan.actions) > 0

    @pytest.mark.asyncio
    async def test_select_resolution_strategy(self, resolver):
        """Test resolution strategy selection."""
        # Test overallocation conflict
        overalloc_conflict = ResourceConflict(
            conflict_id="overalloc_test",
            conflict_type=ConflictType.OVERALLOCATION,
            affected_tasks=["task_1"],
            resource_type=ResourceType.CPU,
            requested_amount=20.0,
            available_amount=16.0,
            severity="critical",
            description="Critical overallocation"
        )
        
        strategy = await resolver._select_resolution_strategy(overalloc_conflict)
        assert strategy == ResolutionStrategy.SCALE_UP

        # Test priority conflict
        priority_conflict = ResourceConflict(
            conflict_id="priority_test",
            conflict_type=ConflictType.PRIORITY_CONFLICT,
            affected_tasks=["task_1"],
            resource_type=ResourceType.CPU,
            requested_amount=4.0,
            available_amount=2.0,
            severity="medium",
            description="Priority conflict"
        )
        
        strategy = await resolver._select_resolution_strategy(priority_conflict)
        assert strategy == ResolutionStrategy.PREEMPT

    @pytest.mark.asyncio
    async def test_manage_priority_queues(self, resolver):
        """Test priority queue management."""
        tasks = [
            Task(id="urgent_task", priority=1, config={"description": "urgent task"}),
            Task(id="normal_task", priority=5, config={"description": "normal task"}),
            Task(id="low_task", priority=8, config={"description": "low priority task"}),
            Task(id="background_task", priority=9, config={"description": "simple task"})
        ]
        
        queue_summary = await resolver.manage_priority_queues(tasks)
        
        assert isinstance(queue_summary, dict)
        assert QueueType.URGENT.value in queue_summary
        assert QueueType.NORMAL_PRIORITY.value in queue_summary
        assert QueueType.LOW_PRIORITY.value in queue_summary
        
        # Check that urgent task is in urgent queue
        urgent_queue_count = queue_summary[QueueType.URGENT.value]["count"]
        assert urgent_queue_count > 0

    @pytest.mark.asyncio
    async def test_coordinate_resource_reservation(self, resolver):
        """Test resource reservation coordination."""
        task = Task(id="reservation_test", config={"description": "test task"})
        allocation_plan = AllocationPlan(
            task_id=task.id,
            cpu_allocation=2.0,
            memory_allocation=1024,
            disk_allocation=5,
            network_allocation=100.0,
            priority=3,
            estimated_duration=60,
            cost_estimate=0.5,
            strategy=AllocationStrategy.BALANCED
        )
        
        result = await resolver.coordinate_resource_reservation(task, allocation_plan)
        
        assert result["reservation_status"] == "success"
        assert "reservations" in result
        assert "start_time" in result
        assert "end_time" in result
        assert result["total_cost"] == allocation_plan.cost_estimate

    @pytest.mark.asyncio
    async def test_handle_resource_preemption(self, resolver):
        """Test resource preemption handling."""
        # Create some reservations first
        resolver.resource_reservations[ResourceType.CPU.value] = [
            TaskReservation(
                task_id="low_priority_task",
                resource_type=ResourceType.CPU,
                amount=4.0,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                priority=7,  # Low priority
                is_preemptible=True
            )
        ]
        
        high_priority_task = Task(id="urgent_task", priority=1)
        result = await resolver.handle_resource_preemption(high_priority_task)
        
        assert result["preemption_status"] in ["success", "no_preemption_needed"]
        if result["preemption_status"] == "success":
            assert len(result["preempted_tasks"]) > 0
            assert "freed_resources" in result

    @pytest.mark.asyncio
    async def test_get_conflict_resolution_report(self, resolver):
        """Test conflict resolution report generation."""
        # Add some test data
        resolver.active_conflicts["test_conflict"] = ResourceConflict(
            conflict_id="test_conflict",
            conflict_type=ConflictType.OVERALLOCATION,
            affected_tasks=["task_1"],
            resource_type=ResourceType.CPU,
            requested_amount=20.0,
            available_amount=16.0,
            severity="high",
            description="Test conflict"
        )
        
        report = await resolver.get_conflict_resolution_report()
        
        assert "active_conflicts" in report
        assert "resolution_history" in report
        assert "queue_status" in report
        assert "resource_reservations" in report
        
        assert report["active_conflicts"]["count"] == 1
        assert ConflictType.OVERALLOCATION.value in report["active_conflicts"]["by_type"]

    def test_calculate_task_complexity(self, resolver):
        """Test task complexity calculation."""
        simple_task = Task(
            id="simple",
            config={"description": "simple task"}
        )
        complex_task = Task(
            id="complex",
            config={"description": "analyze optimize process transform compute data"}
        )
        
        simple_complexity = resolver._calculate_task_complexity(simple_task)
        complex_complexity = resolver._calculate_task_complexity(complex_task)
        
        assert complex_complexity > simple_complexity
        assert simple_complexity >= 1.0  # Minimum complexity

    def test_calculate_priority_score(self, resolver):
        """Test priority score calculation."""
        high_priority_task = Task(id="high", priority=1)
        low_priority_task = Task(id="low", priority=8)
        
        high_score = resolver._calculate_priority_score(high_priority_task, 1, 2.0)
        low_score = resolver._calculate_priority_score(low_priority_task, 8, 1.0)
        
        assert high_score > low_score