"""
Performance profiling and optimization service for AP Intake & Validation system.
"""

import asyncio
import cProfile
import io
import json
import logging
import memory_profiler
import pstats
import psutil
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from functools import wraps
from contextlib import asynccontextmanager

from prometheus_client import Histogram, Gauge

from app.services.prometheus_service import prometheus_service
from app.services.database_performance_service import database_performance_service

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Results from a performance profiling session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0

    # CPU profiling results
    cpu_profile_stats: Optional[Dict[str, Any]] = None
    top_cpu_functions: List[Dict[str, Any]] = field(default_factory=list)

    # Memory profiling results
    memory_profile_stats: Optional[Dict[str, Any]] = None
    peak_memory_mb: float = 0.0
    memory_timeline: List[Dict[str, Any]] = field(default_factory=list)

    # Function call statistics
    function_calls: int = 0
    primitive_calls: int = 0
    total_time: float = 0.0

    # Context information
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""
    category: str  # memory, cpu, database, algorithm
    priority: str  # high, medium, low
    title: str
    description: str
    estimated_improvement: str
    implementation_effort: str
    code_location: Optional[str] = None
    metrics_impact: Dict[str, float] = field(default_factory=dict)


class PerformanceProfilingService:
    """Service for profiling and optimizing application performance."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_profiles: Dict[str, ProfileResult] = {}
        self.profile_history: List[ProfileResult] = []
        self.max_history_size = 100

        # Prometheus metrics for profiling
        self.profiling_duration_histogram = Histogram(
            'ap_intake_profiling_duration_seconds',
            'Time spent profiling application components',
            ['component', 'profile_type'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
            registry=prometheus_service.registry
        )

        self.memory_usage_gauge = Gauge(
            'ap_intake_memory_usage_mb',
            'Memory usage in MB',
            ['component'],
            registry=prometheus_service.registry
        )

        self.optimization_recommendations_gauge = Gauge(
            'ap_intake_optimization_recommendations',
            'Number of optimization recommendations',
            ['category', 'priority'],
            registry=prometheus_service.registry
        )

    @asynccontextmanager
    async def profile_function(self, function_name: str, profile_cpu: bool = True, profile_memory: bool = True):
        """Context manager for profiling individual functions."""
        session_id = f"function_{function_name}_{int(time.time())}"
        profile_result = ProfileResult(
            session_id=session_id,
            start_time=datetime.utcnow(),
            context={"function_name": function_name, "type": "function"}
        )

        self.active_profiles[session_id] = profile_result

        try:
            # Start profiling
            cpu_profiler = cProfile.Profile() if profile_cpu else None
            memory_tracker = []

            if cpu_profiler:
                cpu_profiler.enable()

            # Monitor memory usage
            if profile_memory:
                process = psutil.Process()
                start_memory = process.memory_info().rss / 1024 / 1024  # MB

            yield

            # Stop profiling
            if cpu_profiler:
                cpu_profiler.disable()

            # Collect memory stats
            if profile_memory:
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                profile_result.peak_memory_mb = max(end_memory - start_memory, 0)

            # Process CPU profiling results
            if cpu_profiler:
                stats_stream = io.StringIO()
                ps = pstats.Stats(cpu_profiler, stream=stats_stream)
                ps.sort_stats('cumulative')
                ps.print_stats(20)  # Top 20 functions

                # Parse stats
                stats_text = stats_stream.getvalue()
                profile_result.cpu_profile_stats = self._parse_pstats_output(stats_text)
                profile_result.top_cpu_functions = self._extract_top_functions(stats_text, 10)

            # Finalize profile
            profile_result.end_time = datetime.utcnow()
            profile_result.duration_seconds = (
                profile_result.end_time - profile_result.start_time
            ).total_seconds()

            # Store results
            self.profile_history.append(profile_result)
            if len(self.profile_history) > self.max_history_size:
                self.profile_history = self.profile_history[-self.max_history_size:]

            # Log results
            self.logger.info(f"Function profiling completed: {function_name} in {profile_result.duration_seconds:.3f}s")

        except Exception as e:
            self.logger.error(f"Function profiling failed for {function_name}: {e}")
            raise

        finally:
            self.active_profiles.pop(session_id, None)

    @asynccontextmanager
    async def profile_endpoint(self, endpoint_name: str, request_data: Optional[Dict] = None):
        """Context manager for profiling API endpoints."""
        session_id = f"endpoint_{endpoint_name}_{int(time.time())}"
        profile_result = ProfileResult(
            session_id=session_id,
            start_time=datetime.utcnow(),
            context={
                "endpoint_name": endpoint_name,
                "type": "endpoint",
                "request_data": request_data
            }
        )

        self.active_profiles[session_id] = profile_result

        try:
            # Start system monitoring
            start_time = time.time()
            process = psutil.Process()

            # Initial metrics
            start_cpu = process.cpu_percent()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_fds = process.num_fds() if hasattr(process, 'num_fds') else 0

            # Memory timeline tracking
            memory_timeline = []

            async def monitor_resources():
                """Background task to monitor resource usage."""
                while session_id in self.active_profiles:
                    try:
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        memory_timeline.append({
                            "timestamp": time.time() - start_time,
                            "memory_mb": memory_mb,
                            "cpu_percent": process.cpu_percent()
                        })
                        await asyncio.sleep(0.1)  # Sample every 100ms
                    except Exception:
                        break

            # Start monitoring task
            monitor_task = asyncio.create_task(monitor_resources())

            yield

            # Stop monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Collect final metrics
            end_time = time.time()
            end_cpu = process.cpu_percent()
            end_memory = process.memory_info().rss / 1024 / 1024
            end_fds = process.num_fds() if hasattr(process, 'num_fds') else 0

            # Calculate resource usage
            duration = end_time - start_time
            avg_cpu = (start_cpu + end_cpu) / 2
            memory_delta = end_memory - start_memory
            fd_delta = end_fds - start_fds

            # Store profile results
            profile_result.end_time = datetime.utcnow()
            profile_result.duration_seconds = duration
            profile_result.peak_memory_mb = max(memory_timeline, key=lambda x: x["memory_mb"])["memory_mb"] if memory_timeline else end_memory
            profile_result.memory_timeline = memory_timeline

            profile_result.metadata = {
                "avg_cpu_percent": avg_cpu,
                "memory_delta_mb": memory_delta,
                "fd_delta": fd_delta,
                "duration_seconds": duration
            }

            # Store in history
            self.profile_history.append(profile_result)
            if len(self.profile_history) > self.max_history_size:
                self.profile_history = self.profile_history[-self.max_history_size:]

            # Update Prometheus metrics
            self.profiling_duration_histogram.labels(
                component=endpoint_name,
                profile_type="endpoint"
            ).observe(duration)

            self.memory_usage_gauge.labels(component=endpoint_name).set(end_memory)

            # Log performance summary
            self.logger.info(
                f"Endpoint profiling: {endpoint_name} - "
                f"Duration: {duration:.3f}s, "
                f"Avg CPU: {avg_cpu:.1f}%, "
                f"Memory Delta: {memory_delta:.1f}MB"
            )

        except Exception as e:
            self.logger.error(f"Endpoint profiling failed for {endpoint_name}: {e}")
            raise

        finally:
            self.active_profiles.pop(session_id, None)

    async def profile_workflow(self, workflow_name: str, workflow_func: Callable, *args, **kwargs):
        """Profile a complete workflow execution."""
        session_id = f"workflow_{workflow_name}_{int(time.time())}"
        profile_result = ProfileResult(
            session_id=session_id,
            start_time=datetime.utcnow(),
            context={
                "workflow_name": workflow_name,
                "type": "workflow",
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            }
        )

        self.active_profiles[session_id] = profile_result

        try:
            # Start comprehensive profiling
            cpu_profiler = cProfile.Profile()
            memory_profiler_enabled = True

            # Start CPU profiling
            cpu_profiler.enable()

            # Start memory profiling
            memory_timeline = []
            process = psutil.Process()
            start_time = time.time()

            async def monitor_workflow():
                """Monitor workflow execution."""
                while session_id in self.active_profiles:
                    try:
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        cpu_percent = process.cpu_percent()

                        memory_timeline.append({
                            "timestamp": time.time() - start_time,
                            "memory_mb": memory_mb,
                            "cpu_percent": cpu_percent
                        })

                        await asyncio.sleep(0.5)  # Sample every 500ms
                    except Exception:
                        break

            # Start monitoring
            monitor_task = asyncio.create_task(monitor_workflow())

            # Execute the workflow
            workflow_result = await workflow_func(*args, **kwargs)

            # Stop monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Stop CPU profiling
            cpu_profiler.disable()

            # Process profiling results
            stats_stream = io.StringIO()
            ps = pstats.Stats(cpu_profiler, stream=stats_stream)
            ps.sort_stats('cumulative')
            ps.print_stats(50)  # Top 50 functions

            stats_text = stats_stream.getvalue()
            profile_result.cpu_profile_stats = self._parse_pstats_output(stats_text)
            profile_result.top_cpu_functions = self._extract_top_functions(stats_text, 20)

            # Process memory profiling
            profile_result.memory_timeline = memory_timeline
            if memory_timeline:
                profile_result.peak_memory_mb = max(m["memory_mb"] for m in memory_timeline)

            # Calculate function call statistics
            profile_result.function_calls = len(ps.stats) if hasattr(ps, 'stats') else 0

            # Finalize profile
            profile_result.end_time = datetime.utcnow()
            profile_result.duration_seconds = (
                profile_result.end_time - profile_result.start_time
            ).total_seconds()

            # Store results
            self.profile_history.append(profile_result)
            if len(self.profile_history) > self.max_history_size:
                self.profile_history = self.profile_history[-self.max_history_size:]

            self.logger.info(
                f"Workflow profiling completed: {workflow_name} in {profile_result.duration_seconds:.3f}s"
            )

            return workflow_result

        except Exception as e:
            self.logger.error(f"Workflow profiling failed for {workflow_name}: {e}")
            profile_result.metadata["error"] = str(e)
            profile_result.metadata["traceback"] = traceback.format_exc()
            raise

        finally:
            self.active_profiles.pop(session_id, None)

    def _parse_pstats_output(self, stats_text: str) -> Dict[str, Any]:
        """Parse pstats output into structured data."""
        try:
            lines = stats_text.split('\n')
            data = {"functions": [], "summary": {}}

            # Find the header line
            header_line = None
            for i, line in enumerate(lines):
                if 'ncalls' in line and 'tottime' in line and 'cumtime' in line:
                    header_line = i
                    break

            if header_line:
                # Parse function statistics
                for line in lines[header_line + 2:]:
                    if line.strip() and not line.startswith(' '):
                        # This looks like a function line
                        parts = line.split()
                        if len(parts) >= 6:
                            try:
                                ncalls = parts[0]
                                tottime = float(parts[1])
                                percall = float(parts[2]) if len(parts) > 2 else 0
                                cumtime = float(parts[3]) if len(parts) > 3 else 0
                                percall_cum = float(parts[4]) if len(parts) > 4 else 0
                                filename_line = ':'.join(parts[5:]).strip()

                                data["functions"].append({
                                    "ncalls": ncalls,
                                    "total_time": tottime,
                                    "per_call_time": percall,
                                    "cumulative_time": cumtime,
                                    "per_call_cumulative": percall_cum,
                                    "filename": filename_line
                                })
                            except (ValueError, IndexError):
                                continue

            # Calculate summary
            if data["functions"]:
                total_calls = sum(f["ncalls"] for f in data["functions"] if isinstance(f["ncalls"], int))
                total_time = sum(f["total_time"] for f in data["functions"])
                data["summary"] = {
                    "total_function_calls": total_calls,
                    "total_profiled_time": total_time,
                    "unique_functions": len(data["functions"])
                }

            return data

        except Exception as e:
            self.logger.warning(f"Failed to parse pstats output: {e}")
            return {"functions": [], "summary": {}}

    def _extract_top_functions(self, stats_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Extract top CPU-consuming functions from stats."""
        try:
            parsed = self._parse_pstats_output(stats_text)
            functions = parsed.get("functions", [])

            # Sort by cumulative time
            functions.sort(key=lambda x: x.get("cumulative_time", 0), reverse=True)

            return functions[:limit]

        except Exception as e:
            self.logger.warning(f"Failed to extract top functions: {e}")
            return []

    async def analyze_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze performance trends from profiling history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_profiles = [
            p for p in self.profile_history
            if p.start_time >= cutoff_time
        ]

        if not recent_profiles:
            return {"message": "No profiling data available for the specified time period"}

        # Group by profile type
        profiles_by_type = {
            "function": [],
            "endpoint": [],
            "workflow": []
        }

        for profile in recent_profiles:
            profile_type = profile.context.get("type", "unknown")
            if profile_type in profiles_by_type:
                profiles_by_type[profile_type].append(profile)

        # Analyze trends
        analysis = {
            "period_hours": hours,
            "total_profiles": len(recent_profiles),
            "profiles_by_type": {k: len(v) for k, v in profiles_by_type.items()},
            "performance_trends": {},
            "bottlenecks": [],
            "recommendations": []
        }

        # Analyze endpoint performance
        if profiles_by_type["endpoint"]:
            endpoint_stats = self._analyze_endpoint_performance(profiles_by_type["endpoint"])
            analysis["performance_trends"]["endpoints"] = endpoint_stats

            # Identify slow endpoints
            slow_endpoints = [
                (profile.context["endpoint_name"], profile.duration_seconds)
                for profile in profiles_by_type["endpoint"]
                if profile.duration_seconds > 1.0  # Slower than 1 second
            ]

            if slow_endpoints:
                analysis["bottlenecks"].extend([
                    {
                        "type": "slow_endpoint",
                        "component": endpoint,
                        "value": duration,
                        "threshold": 1.0,
                        "unit": "seconds"
                    }
                    for endpoint, duration in slow_endpoints
                ])

        # Analyze memory usage patterns
        memory_analysis = self._analyze_memory_patterns(recent_profiles)
        analysis["performance_trends"]["memory"] = memory_analysis

        # Identify memory bottlenecks
        high_memory_profiles = [
            profile for profile in recent_profiles
            if profile.peak_memory_mb > 100  # More than 100MB
        ]

        if high_memory_profiles:
            analysis["bottlenecks"].extend([
                {
                    "type": "high_memory_usage",
                    "component": profile.context.get("endpoint_name") or profile.context.get("function_name", "unknown"),
                    "value": profile.peak_memory_mb,
                    "threshold": 100,
                    "unit": "MB"
                }
                for profile in high_memory_profiles
            ])

        # Generate recommendations
        analysis["recommendations"] = await self._generate_optimization_recommendations(recent_profiles)

        return analysis

    def _analyze_endpoint_performance(self, endpoint_profiles: List[ProfileResult]) -> Dict[str, Any]:
        """Analyze endpoint performance trends."""
        endpoint_stats = {}

        for profile in endpoint_profiles:
            endpoint_name = profile.context.get("endpoint_name", "unknown")
            if endpoint_name not in endpoint_stats:
                endpoint_stats[endpoint_name] = {
                    "call_count": 0,
                    "total_duration": 0,
                    "min_duration": float('inf'),
                    "max_duration": 0,
                    "memory_samples": []
                }

            stats = endpoint_stats[endpoint_name]
            stats["call_count"] += 1
            stats["total_duration"] += profile.duration_seconds
            stats["min_duration"] = min(stats["min_duration"], profile.duration_seconds)
            stats["max_duration"] = max(stats["max_duration"], profile.duration_seconds)

            if profile.peak_memory_mb > 0:
                stats["memory_samples"].append(profile.peak_memory_mb)

        # Calculate statistics for each endpoint
        for endpoint_name, stats in endpoint_stats.items():
            if stats["call_count"] > 0:
                stats["avg_duration"] = stats["total_duration"] / stats["call_count"]

                if stats["memory_samples"]:
                    stats["avg_memory_mb"] = sum(stats["memory_samples"]) / len(stats["memory_samples"])
                    stats["max_memory_mb"] = max(stats["memory_samples"])

                # Remove infinite value if present
                if stats["min_duration"] == float('inf'):
                    stats["min_duration"] = stats["avg_duration"]

        return endpoint_stats

    def _analyze_memory_patterns(self, profiles: List[ProfileResult]) -> Dict[str, Any]:
        """Analyze memory usage patterns."""
        memory_data = []

        for profile in profiles:
            if profile.peak_memory_mb > 0:
                memory_data.append({
                    "timestamp": profile.start_time.isoformat(),
                    "memory_mb": profile.peak_memory_mb,
                    "component": profile.context.get("endpoint_name") or profile.context.get("function_name", "unknown"),
                    "type": profile.context.get("type", "unknown")
                })

        if not memory_data:
            return {"message": "No memory data available"}

        # Calculate statistics
        memory_values = [m["memory_mb"] for m in memory_data]
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)
        min_memory = min(memory_values)

        # Find memory hotspots
        hotspots = sorted(memory_data, key=lambda x: x["memory_mb"], reverse=True)[:10]

        return {
            "statistics": {
                "avg_memory_mb": round(avg_memory, 2),
                "max_memory_mb": round(max_memory, 2),
                "min_memory_mb": round(min_memory, 2),
                "sample_count": len(memory_data)
            },
            "memory_hotspots": hotspots,
            "trend": "increasing" if len(memory_data) > 1 and memory_values[-1] > memory_values[0] else "stable"
        }

    async def _generate_optimization_recommendations(self, profiles: List[ProfileResult]) -> List[Dict[str, Any]]:
        """Generate optimization recommendations based on profiling data."""
        recommendations = []

        # Analyze slow functions from CPU profiling
        slow_functions = []
        for profile in profiles:
            if profile.top_cpu_functions:
                for func in profile.top_cpu_functions[:5]:  # Top 5 per profile
                    if func["cumulative_time"] > 0.1:  # More than 100ms
                        slow_functions.append({
                            "function": func["filename"],
                            "cumulative_time": func["cumulative_time"],
                            "profile_context": profile.context
                        })

        # Group similar slow functions
        function_groups = {}
        for func in slow_functions:
            func_name = func["function"].split(":")[-1]  # Extract function name
            if func_name not in function_groups:
                function_groups[func_name] = {
                    "total_time": 0,
                    "count": 0,
                    "contexts": []
                }

            function_groups[func_name]["total_time"] += func["cumulative_time"]
            function_groups[func_name]["count"] += 1
            function_groups[func_name]["contexts"].append(func["profile_context"])

        # Generate recommendations for slow functions
        for func_name, stats in function_groups.items():
            if stats["total_time"] > 0.5:  # Total time > 500ms
                recommendations.append({
                    "category": "cpu",
                    "priority": "high" if stats["total_time"] > 1.0 else "medium",
                    "title": f"Optimize slow function: {func_name}",
                    "description": f"Function {func_name} is consuming significant CPU time ({stats['total_time']:.3f}s across {stats['count']} calls)",
                    "estimated_improvement": f"{(stats['total_time'] * 0.3):.3f}s faster",
                    "implementation_effort": "medium",
                    "metrics_impact": {"cpu_reduction_percent": 30}
                })

        # Analyze memory usage
        high_memory_profiles = [
            profile for profile in profiles
            if profile.peak_memory_mb > 50  # More than 50MB
        ]

        if high_memory_profiles:
            avg_memory = sum(p.peak_memory_mb for p in high_memory_profiles) / len(high_memory_profiles)
            recommendations.append({
                "category": "memory",
                "priority": "high" if avg_memory > 100 else "medium",
                "title": "Reduce memory usage in high-memory operations",
                "description": f"Several operations are using {avg_memory:.1f}MB on average",
                "estimated_improvement": f"{(avg_memory * 0.4):.1f}MB reduction",
                "implementation_effort": "low",
                "metrics_impact": {"memory_reduction_percent": 40}
            })

        # Database performance recommendations
        try:
            db_health = await database_performance_service.generate_database_health_report()
            if db_health.get("health_score", 100) < 80:
                recommendations.append({
                    "category": "database",
                    "priority": "high",
                    "title": "Optimize database queries and indexes",
                    "description": "Database health score indicates performance issues",
                    "estimated_improvement": "20-50% faster queries",
                    "implementation_effort": "medium",
                    "metrics_impact": {"query_speed_improvement_percent": 35}
                })
        except Exception as e:
            logger.warning(f"Failed to get database health for recommendations: {e}")

        return recommendations

    async def get_profile_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of profiling results."""
        if session_id:
            profile = self.active_profiles.get(session_id) or \
                     next((p for p in self.profile_history if p.session_id == session_id), None)
            if not profile:
                return {"error": f"Profile {session_id} not found"}
            return self._profile_to_dict(profile)

        # Return summary of recent profiles
        recent_profiles = self.profile_history[-10:]  # Last 10 profiles
        return {
            "total_profiles": len(self.profile_history),
            "active_profiles": len(self.active_profiles),
            "recent_profiles": [self._profile_to_dict(p) for p in recent_profiles],
            "summary": {
                "avg_duration": sum(p.duration_seconds for p in recent_profiles) / len(recent_profiles) if recent_profiles else 0,
                "avg_memory_mb": sum(p.peak_memory_mb for p in recent_profiles if p.peak_memory_mb > 0) / len([p for p in recent_profiles if p.peak_memory_mb > 0]) if any(p.peak_memory_mb > 0 for p in recent_profiles) else 0
            }
        }

    def _profile_to_dict(self, profile: ProfileResult) -> Dict[str, Any]:
        """Convert profile result to dictionary."""
        return {
            "session_id": profile.session_id,
            "start_time": profile.start_time.isoformat(),
            "end_time": profile.end_time.isoformat() if profile.end_time else None,
            "duration_seconds": profile.duration_seconds,
            "peak_memory_mb": profile.peak_memory_mb,
            "context": profile.context,
            "metadata": profile.metadata,
            "top_cpu_functions": profile.top_cpu_functions[:5] if profile.top_cpu_functions else []
        }

    def clear_profile_history(self, older_than_hours: int = 24):
        """Clear profiling history older than specified hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            self.profile_history = [
                p for p in self.profile_history
                if p.start_time >= cutoff_time
            ]
            self.logger.info(f"Cleared profiling history older than {older_than_hours} hours")
        except Exception as e:
            self.logger.error(f"Failed to clear profiling history: {e}")


# Decorator for automatic function profiling
def profile_function(name: Optional[str] = None, cpu: bool = True, memory: bool = True):
    """Decorator to automatically profile functions."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            async with performance_profiling_service.profile_function(func_name, cpu, memory):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            # For sync functions, we'll run profiling in async context
            async def run_profile():
                async with performance_profiling_service.profile_function(func_name, cpu, memory):
                    return func(*args, **kwargs)
            return asyncio.run(run_profile())

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Singleton instance
performance_profiling_service = PerformanceProfilingService()