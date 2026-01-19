"""
Advanced Analytics & Insights Service for Daena

Provides:
- Predictive analytics for memory usage
- Cost optimization recommendations
- Performance trend analysis
- Enhanced anomaly detection
"""

from __future__ import annotations

import logging
import statistics
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryUsagePrediction:
    """Prediction for memory usage."""
    predicted_usage_gb: float
    predicted_growth_rate: float
    confidence: float
    timeframe_days: int
    recommendations: List[str]


@dataclass
class CostOptimizationRecommendation:
    """Cost optimization recommendation."""
    category: str
    current_cost_usd: float
    potential_savings_usd: float
    savings_percent: float
    action: str
    priority: str  # "high", "medium", "low"
    impact: str  # "high", "medium", "low"


@dataclass
class PerformanceTrend:
    """Performance trend analysis."""
    metric_name: str
    current_value: float
    trend: str  # "improving", "stable", "degrading"
    change_percent: float
    timeframe_days: int
    data_points: List[Tuple[float, float]]  # (timestamp, value)


class AdvancedAnalyticsService:
    """
    Advanced analytics service with predictive capabilities.
    """
    
    def __init__(self, history_days: int = 30):
        """
        Initialize advanced analytics service.
        
        Args:
            history_days: Number of days of history to maintain
        """
        self.history_days = history_days
        self.memory_history: deque = deque(maxlen=history_days * 24)  # Hourly data points
        self.cost_history: deque = deque(maxlen=history_days * 24)
        self.performance_history: Dict[str, deque] = {}
    
    def record_memory_usage(self, usage_gb: float, timestamp: Optional[float] = None):
        """Record memory usage data point."""
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        self.memory_history.append((timestamp, usage_gb))
    
    def record_cost(self, cost_usd: float, timestamp: Optional[float] = None):
        """Record cost data point."""
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        self.cost_history.append((timestamp, cost_usd))
    
    def record_performance_metric(self, metric_name: str, value: float, timestamp: Optional[float] = None):
        """Record performance metric data point."""
        if timestamp is None:
            timestamp = datetime.now().timestamp()
        if metric_name not in self.performance_history:
            self.performance_history[metric_name] = deque(maxlen=self.history_days * 24)
        self.performance_history[metric_name].append((timestamp, value))
    
    def predict_memory_usage(self, days_ahead: int = 7) -> MemoryUsagePrediction:
        """
        Predict memory usage for the next N days.
        
        Args:
            days_ahead: Number of days to predict ahead
            
        Returns:
            MemoryUsagePrediction with predictions and recommendations
        """
        if len(self.memory_history) < 24:  # Need at least 24 hours of data
            return MemoryUsagePrediction(
                predicted_usage_gb=0.0,
                predicted_growth_rate=0.0,
                confidence=0.0,
                timeframe_days=days_ahead,
                recommendations=["Insufficient data for prediction. Collect at least 24 hours of data."]
            )
        
        # Extract values
        values = [v for _, v in self.memory_history]
        timestamps = [t for t, _ in self.memory_history]
        
        # Simple linear regression for trend
        n = len(values)
        if n < 2:
            growth_rate = 0.0
        else:
            # Calculate growth rate (GB per day)
            time_span_days = (timestamps[-1] - timestamps[0]) / (24 * 3600)
            if time_span_days > 0:
                growth_rate = (values[-1] - values[0]) / time_span_days
            else:
                growth_rate = 0.0
        
        # Predict future usage
        current_usage = values[-1] if values else 0.0
        predicted_usage = current_usage + (growth_rate * days_ahead)
        
        # Calculate confidence based on data consistency
        if len(values) >= 7:
            std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
            mean_value = statistics.mean(values)
            cv = std_dev / mean_value if mean_value > 0 else 1.0  # Coefficient of variation
            confidence = max(0.0, min(1.0, 1.0 - cv))  # Lower CV = higher confidence
        else:
            confidence = 0.5
        
        # Generate recommendations
        recommendations = []
        if growth_rate > 0.1:  # Growing more than 0.1 GB/day
            recommendations.append(f"Memory usage is growing at {growth_rate:.2f} GB/day. Consider enabling aging policies.")
        if predicted_usage > 100:  # Predicted to exceed 100 GB
            recommendations.append(f"Predicted usage ({predicted_usage:.1f} GB) exceeds 100 GB. Review data retention policies.")
        if current_usage > 50:
            recommendations.append("Current usage is high. Consider archiving old data to L3 cold storage.")
        if not recommendations:
            recommendations.append("Memory usage is within normal parameters.")
        
        return MemoryUsagePrediction(
            predicted_usage_gb=predicted_usage,
            predicted_growth_rate=growth_rate,
            confidence=confidence,
            timeframe_days=days_ahead,
            recommendations=recommendations
        )
    
    def get_cost_optimization_recommendations(self) -> List[CostOptimizationRecommendation]:
        """
        Generate cost optimization recommendations.
        
        Returns:
            List of cost optimization recommendations
        """
        recommendations = []
        
        try:
            from memory_service.metrics import snapshot
            metrics = snapshot()
            
            # Get current costs
            total_cost = metrics.get("total_cost_usd", 0.0)
            savings = metrics.get("estimated_cost_savings_usd", 0.0)
            cas_hit_rate = metrics.get("llm_cas_hit_rate", 0.0)
            nbmf_reads = metrics.get("nbmf_reads", 0)
            nbmf_writes = metrics.get("nbmf_writes", 0)
            
            # Recommendation 1: CAS Hit Rate
            if cas_hit_rate < 0.6:
                potential_savings = total_cost * (0.6 - cas_hit_rate) * 0.5  # Estimate 50% of gap
                recommendations.append(CostOptimizationRecommendation(
                    category="CAS Efficiency",
                    current_cost_usd=total_cost,
                    potential_savings_usd=potential_savings,
                    savings_percent=(potential_savings / total_cost * 100) if total_cost > 0 else 0,
                    action="Increase CAS hit rate by adjusting simhash_threshold or improving deduplication",
                    priority="high" if cas_hit_rate < 0.4 else "medium",
                    impact="high"
                ))
            
            # Recommendation 2: NBMF Compression
            compression_ratio = metrics.get("compression_ratio", 1.0)
            if compression_ratio < 10.0:
                # Estimate savings from better compression
                current_storage_cost = total_cost * 0.1  # Assume 10% is storage
                potential_savings = current_storage_cost * (1 - 10.0 / compression_ratio) if compression_ratio > 0 else 0
                recommendations.append(CostOptimizationRecommendation(
                    category="Storage Compression",
                    current_cost_usd=current_storage_cost,
                    potential_savings_usd=potential_savings,
                    savings_percent=(potential_savings / current_storage_cost * 100) if current_storage_cost > 0 else 0,
                    action="Optimize NBMF compression settings (increase zstd_level, enable quantization)",
                    priority="medium",
                    impact="medium"
                ))
            
            # Recommendation 3: Read/Write Ratio
            if nbmf_reads > 0 and nbmf_writes > 0:
                read_write_ratio = nbmf_reads / nbmf_writes
                if read_write_ratio < 2.0:  # More writes than reads
                    recommendations.append(CostOptimizationRecommendation(
                        category="Access Pattern",
                        current_cost_usd=total_cost * 0.05,  # Estimate
                        potential_savings_usd=total_cost * 0.02,  # Estimate
                        savings_percent=2.0,
                        action="Optimize access patterns - consider caching frequently read data in L1",
                        priority="low",
                        impact="medium"
                    ))
            
            # Recommendation 4: Device Selection
            try:
                from Core.device_manager import DeviceManager
                device_mgr = DeviceManager()
                device = device_mgr.get_device()
                if device.device_type.value == "cpu":
                    # Estimate GPU/TPU savings
                    recommendations.append(CostOptimizationRecommendation(
                        category="Compute Device",
                        current_cost_usd=total_cost * 0.3,  # Estimate compute cost
                        potential_savings_usd=total_cost * 0.1,  # Estimate 10% savings with GPU
                        savings_percent=10.0,
                        action="Consider using GPU/TPU for batch operations to reduce latency and costs",
                        priority="medium",
                        impact="medium"
                    ))
            except ImportError:
                pass
            
            # Recommendation 5: Aging Policies
            if len(self.memory_history) > 0:
                current_usage = self.memory_history[-1][1] if self.memory_history else 0.0
                if current_usage > 20.0:  # More than 20 GB
                    recommendations.append(CostOptimizationRecommendation(
                        category="Data Lifecycle",
                        current_cost_usd=current_usage * 0.01,  # Estimate storage cost
                        potential_savings_usd=current_usage * 0.005,  # Estimate 50% reduction
                        savings_percent=50.0,
                        action="Enable aging policies to automatically compress/archive old data",
                        priority="medium",
                        impact="high"
                    ))
        
        except Exception as e:
            logger.error(f"Error generating cost recommendations: {e}")
        
        # Sort by priority and impact
        priority_order = {"high": 3, "medium": 2, "low": 1}
        impact_order = {"high": 3, "medium": 2, "low": 1}
        recommendations.sort(
            key=lambda x: (priority_order.get(x.priority, 0), impact_order.get(x.impact, 0), x.savings_percent),
            reverse=True
        )
        
        return recommendations
    
    def analyze_performance_trends(self, metric_name: str, days: int = 7) -> Optional[PerformanceTrend]:
        """
        Analyze performance trends for a metric.
        
        Args:
            metric_name: Name of the metric
            days: Number of days to analyze
            
        Returns:
            PerformanceTrend or None if insufficient data
        """
        if metric_name not in self.performance_history:
            return None
        
        history = self.performance_history[metric_name]
        if len(history) < 2:
            return None
        
        # Filter to last N days
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        recent_data = [(t, v) for t, v in history if t >= cutoff_time]
        
        if len(recent_data) < 2:
            return None
        
        values = [v for _, v in recent_data]
        current_value = values[-1]
        
        # Calculate trend
        if len(values) >= 7:
            # Compare first half vs second half
            mid = len(values) // 2
            first_half_avg = statistics.mean(values[:mid])
            second_half_avg = statistics.mean(values[mid:])
            
            if second_half_avg > first_half_avg * 1.05:
                trend = "improving"
            elif second_half_avg < first_half_avg * 0.95:
                trend = "degrading"
            else:
                trend = "stable"
            
            change_percent = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        else:
            # Simple comparison
            first_value = values[0]
            change_percent = ((current_value - first_value) / first_value * 100) if first_value > 0 else 0
            if change_percent > 5:
                trend = "improving"
            elif change_percent < -5:
                trend = "degrading"
            else:
                trend = "stable"
        
        return PerformanceTrend(
            metric_name=metric_name,
            current_value=current_value,
            trend=trend,
            change_percent=change_percent,
            timeframe_days=days,
            data_points=recent_data
        )
    
    def get_all_performance_trends(self, days: int = 7) -> Dict[str, PerformanceTrend]:
        """Get performance trends for all tracked metrics."""
        trends = {}
        for metric_name in self.performance_history.keys():
            trend = self.analyze_performance_trends(metric_name, days)
            if trend:
                trends[metric_name] = trend
        return trends
    
    def get_insights_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive insights summary.
        
        Returns:
            Dictionary with predictions, recommendations, and trends
        """
        # Memory prediction
        memory_prediction = self.predict_memory_usage(days_ahead=7)
        
        # Cost recommendations
        cost_recommendations = self.get_cost_optimization_recommendations()
        
        # Performance trends
        performance_trends = self.get_all_performance_trends(days=7)
        
        # Calculate total potential savings
        total_potential_savings = sum(rec.potential_savings_usd for rec in cost_recommendations)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "memory_prediction": {
                "predicted_usage_gb": memory_prediction.predicted_usage_gb,
                "predicted_growth_rate_gb_per_day": memory_prediction.predicted_growth_rate,
                "confidence": memory_prediction.confidence,
                "timeframe_days": memory_prediction.timeframe_days,
                "recommendations": memory_prediction.recommendations
            },
            "cost_optimization": {
                "total_recommendations": len(cost_recommendations),
                "total_potential_savings_usd": total_potential_savings,
                "recommendations": [
                    {
                        "category": rec.category,
                        "current_cost_usd": rec.current_cost_usd,
                        "potential_savings_usd": rec.potential_savings_usd,
                        "savings_percent": rec.savings_percent,
                        "action": rec.action,
                        "priority": rec.priority,
                        "impact": rec.impact
                    }
                    for rec in cost_recommendations
                ]
            },
            "performance_trends": {
                metric_name: {
                    "current_value": trend.current_value,
                    "trend": trend.trend,
                    "change_percent": trend.change_percent,
                    "timeframe_days": trend.timeframe_days,
                    "data_points_count": len(trend.data_points)
                }
                for metric_name, trend in performance_trends.items()
            },
            "summary": {
                "high_priority_recommendations": len([r for r in cost_recommendations if r.priority == "high"]),
                "total_potential_savings_usd": total_potential_savings,
                "metrics_tracked": len(performance_trends),
                "improving_metrics": len([t for t in performance_trends.values() if t.trend == "improving"]),
                "degrading_metrics": len([t for t in performance_trends.values() if t.trend == "degrading"])
            }
        }


# Global instance
advanced_analytics_service = AdvancedAnalyticsService()

