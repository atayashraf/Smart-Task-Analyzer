"""
Priority Scoring Algorithm for Smart Task Analyzer.

This module implements an intelligent task prioritization system that considers
multiple factors: urgency, importance, effort, and dependencies. The algorithm
is configurable through different strategies and customizable weights.

Algorithm Design Philosophy:
---------------------------
The scoring system uses a weighted multi-factor approach where each factor
contributes to a final priority score between 0-100. The algorithm is designed
to handle real-world scenarios including:
- Overdue tasks (past due dates)
- Missing data (no due date specified)
- Circular dependencies (detected and flagged)
- Competing priorities (urgent vs important)
- Weekend/holiday awareness for urgency calculation
- Eisenhower Matrix quadrant classification

Scoring Formula:
---------------
priority_score = (urgency_score * urgency_weight) + 
                 (importance_score * importance_weight) + 
                 (effort_score * effort_weight) + 
                 (dependency_score * dependency_weight)

Each component score is normalized to 0-100 before weighting.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import math


# ==================== Error Codes ====================

class ErrorCode(Enum):
    """Professional error codes for API responses."""
    SUCCESS = "SUCCESS"
    ERR_MISSING_FIELD = "ERR_MISSING_FIELD"
    ERR_INVALID_DATE = "ERR_INVALID_DATE"
    ERR_INVALID_HOURS = "ERR_INVALID_HOURS"
    ERR_INVALID_IMPORTANCE = "ERR_INVALID_IMPORTANCE"
    ERR_CIRCULAR_DEPENDENCY = "ERR_CIRCULAR_DEPENDENCY"
    ERR_SELF_DEPENDENCY = "ERR_SELF_DEPENDENCY"
    ERR_INVALID_DEPENDENCY = "ERR_INVALID_DEPENDENCY"
    ERR_INVALID_WEIGHTS = "ERR_INVALID_WEIGHTS"
    ERR_EMPTY_TASKS = "ERR_EMPTY_TASKS"
    ERR_INVALID_STRATEGY = "ERR_INVALID_STRATEGY"


@dataclass
class ValidationError:
    """Structured validation error with code and details."""
    code: ErrorCode
    message: str
    field: Optional[str] = None
    task_id: Optional[int] = None
    
    def to_dict(self) -> Dict:
        result = {
            'error_code': self.code.value,
            'message': self.message
        }
        if self.field:
            result['field'] = self.field
        if self.task_id is not None:
            result['task_id'] = self.task_id
        return result


# ==================== Eisenhower Quadrant ====================

class EisenhowerQuadrant(Enum):
    """Eisenhower Matrix quadrant classification."""
    DO_NOW = "do_now"           # Urgent + Important
    PLAN = "plan"               # Not Urgent + Important  
    DELEGATE = "delegate"       # Urgent + Not Important
    ELIMINATE = "eliminate"     # Not Urgent + Not Important


@dataclass
class ScoringWeights:
    """
    Configuration for scoring weights.
    
    Different strategies use different weight configurations:
    - Smart Balance: Balanced consideration of all factors
    - Fastest Wins: Prioritizes low-effort tasks
    - High Impact: Prioritizes importance
    - Deadline Driven: Prioritizes urgency
    """
    urgency: float = 0.30
    importance: float = 0.35
    effort: float = 0.15
    dependency: float = 0.20
    
    def __post_init__(self):
        """Normalize weights to sum to 1.0."""
        total = self.urgency + self.importance + self.effort + self.dependency
        if total > 0:
            self.urgency /= total
            self.importance /= total
            self.effort /= total
            self.dependency /= total
    
    def to_dict(self) -> Dict:
        """Return weights as dictionary."""
        return {
            'urgency': round(self.urgency, 3),
            'importance': round(self.importance, 3),
            'effort': round(self.effort, 3),
            'dependency': round(self.dependency, 3)
        }


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how a task's score was calculated."""
    urgency_score: float = 0.0
    importance_score: float = 0.0
    effort_score: float = 0.0
    dependency_score: float = 0.0
    urgency_contribution: float = 0.0
    importance_contribution: float = 0.0
    effort_contribution: float = 0.0
    dependency_contribution: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'urgency': {
                'raw_score': round(self.urgency_score, 2),
                'contribution': round(self.urgency_contribution, 2)
            },
            'importance': {
                'raw_score': round(self.importance_score, 2),
                'contribution': round(self.importance_contribution, 2)
            },
            'effort': {
                'raw_score': round(self.effort_score, 2),
                'contribution': round(self.effort_contribution, 2)
            },
            'dependency': {
                'raw_score': round(self.dependency_score, 2),
                'contribution': round(self.dependency_contribution, 2)
            }
        }


@dataclass
class ScoredTask:
    """A task with its calculated priority score and metadata."""
    id: Optional[int]
    title: str
    due_date: Optional[date]
    estimated_hours: float
    importance: int
    dependencies: List[int]
    priority_score: float = 0.0
    priority_level: str = "Medium"
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    explanation: str = ""
    has_circular_dependency: bool = False
    is_overdue: bool = False
    is_blocking_others: bool = False
    eisenhower_quadrant: EisenhowerQuadrant = EisenhowerQuadrant.PLAN
    working_days_until_due: Optional[int] = None
    complexity_score: float = 0.0


# Strategy presets
STRATEGY_WEIGHTS = {
    'smart_balance': ScoringWeights(
        urgency=0.30,
        importance=0.35,
        effort=0.15,
        dependency=0.20
    ),
    'fastest_wins': ScoringWeights(
        urgency=0.15,
        importance=0.20,
        effort=0.55,
        dependency=0.10
    ),
    'high_impact': ScoringWeights(
        urgency=0.15,
        importance=0.60,
        effort=0.10,
        dependency=0.15
    ),
    'deadline_driven': ScoringWeights(
        urgency=0.55,
        importance=0.20,
        effort=0.10,
        dependency=0.15
    )
}

# Default holidays (US federal holidays - can be customized)
DEFAULT_HOLIDAYS = [
    # 2025 US Federal Holidays
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents Day
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 10, 13),  # Columbus Day
    date(2025, 11, 11),  # Veterans Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
]


class TaskPriorityScorer:
    """
    Main class for calculating task priority scores.
    
    This scorer implements a flexible, multi-factor prioritization algorithm
    that can be configured with different strategies or custom weights.
    
    Features:
    - Multi-factor weighted scoring
    - Customizable weights
    - Weekend and holiday awareness
    - Eisenhower Matrix classification
    - Circular dependency detection
    - Human-readable explanations
    """
    
    # Constants for urgency calculation
    OVERDUE_MAX_PENALTY_DAYS = 14  # Maximum days overdue for highest urgency
    FUTURE_COMFORT_DAYS = 30  # Days in future considered "low urgency"
    
    # Constants for effort scoring
    QUICK_WIN_HOURS = 2  # Tasks under this are "quick wins"
    MAX_EFFORT_HOURS = 40  # Cap for effort calculation
    
    # Thresholds for Eisenhower Matrix
    URGENCY_THRESHOLD = 60  # Above this = urgent
    IMPORTANCE_THRESHOLD = 6  # Above this (1-10 scale) = important
    
    def __init__(
        self, 
        strategy: str = 'smart_balance',
        custom_weights: Optional[ScoringWeights] = None,
        skip_weekends: bool = True,
        holidays: Optional[List[date]] = None
    ):
        """
        Initialize the scorer with a strategy or custom weights.
        
        Args:
            strategy: One of 'smart_balance', 'fastest_wins', 
                     'high_impact', 'deadline_driven'
            custom_weights: Optional custom weights (overrides strategy)
            skip_weekends: Whether to skip weekends in urgency calculation
            holidays: List of holiday dates to skip (uses defaults if None)
        """
        if custom_weights:
            self.weights = custom_weights
        elif strategy in STRATEGY_WEIGHTS:
            self.weights = STRATEGY_WEIGHTS[strategy]
        else:
            self.weights = STRATEGY_WEIGHTS['smart_balance']
        
        self.strategy = strategy
        self.skip_weekends = skip_weekends
        self.holidays = set(holidays) if holidays else set(DEFAULT_HOLIDAYS)
    
    def count_working_days(
        self, 
        start_date: date, 
        end_date: date
    ) -> int:
        """
        Count working days between two dates (excluding weekends and holidays).
        
        Args:
            start_date: Start date (exclusive)
            end_date: End date (inclusive)
        
        Returns:
            Number of working days. Negative if end_date is before start_date.
        """
        if start_date >= end_date:
            # Count backwards for overdue
            return -self._count_working_days_forward(end_date, start_date)
        return self._count_working_days_forward(start_date, end_date)
    
    def _count_working_days_forward(self, start: date, end: date) -> int:
        """Count working days from start to end (both exclusive of start)."""
        if not self.skip_weekends:
            return (end - start).days
        
        count = 0
        current = start + timedelta(days=1)
        while current <= end:
            # Check if it's a weekday (0=Monday, 6=Sunday)
            if current.weekday() < 5 and current not in self.holidays:
                count += 1
            current += timedelta(days=1)
        return count
    
    def calculate_urgency_score(
        self, 
        due_date: Optional[date], 
        reference_date: Optional[date] = None
    ) -> Tuple[float, bool, Optional[int]]:
        """
        Calculate urgency score based on due date with weekend/holiday awareness.
        
        Scoring Logic:
        - Overdue tasks: Score 80-100 (more overdue = higher score)
        - Due today: Score 75
        - Due in 1-7 working days: Score 50-75 (linear decrease)
        - Due in 8-30 working days: Score 20-50 (linear decrease)
        - Due beyond 30 working days: Score 10-20
        - No due date: Score 30 (treated as moderate urgency)
        
        Returns:
            Tuple of (urgency_score, is_overdue, working_days_until_due)
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Handle missing due date
        if due_date is None:
            return (30.0, False, None)
        
        # Calculate working days
        working_days = self.count_working_days(reference_date, due_date)
        
        # Overdue tasks
        if working_days < 0:
            days_overdue = abs(working_days)
            overdue_score = 80 + min(days_overdue / self.OVERDUE_MAX_PENALTY_DAYS, 1) * 20
            return (min(overdue_score, 100), True, working_days)
        
        # Due today
        if working_days == 0:
            return (75.0, False, 0)
        
        # Due within a week (5 working days)
        if working_days <= 5:
            score = 75 - (working_days / 5) * 25
            return (score, False, working_days)
        
        # Due within a month (~22 working days)
        if working_days <= 22:
            score = 50 - ((working_days - 5) / 17) * 30
            return (score, False, working_days)
        
        # Due beyond a month
        score = 10 + 10 * math.exp(-(working_days - 22) / 22)
        return (max(score, 10), False, working_days)
    
    def calculate_importance_score(self, importance: int) -> float:
        """
        Convert importance rating (1-10) to score (0-100).
        
        Uses a slightly exponential curve to emphasize higher importance values.
        A task rated 10 is significantly more important than one rated 5.
        
        Formula: score = 10 + (importance / 10)^1.5 * 90
        """
        # Validate and clamp importance
        importance = max(1, min(10, importance))
        
        # Exponential scaling to emphasize high-importance tasks
        normalized = importance / 10
        score = 10 + (normalized ** 1.5) * 90
        return min(score, 100)
    
    def calculate_effort_score(self, estimated_hours: float) -> float:
        """
        Calculate effort score (lower effort = higher score for "quick wins").
        
        Scoring Logic:
        - Tasks under 2 hours: Score 80-100 ("quick wins")
        - Tasks 2-8 hours: Score 50-80 (manageable)
        - Tasks 8-40 hours: Score 20-50 (significant effort)
        - Tasks beyond 40 hours: Score 10-20 (major projects)
        
        This scoring encourages completing quick tasks to build momentum.
        """
        hours = float(estimated_hours)
        hours = max(0.1, min(hours, self.MAX_EFFORT_HOURS))
        
        # Quick wins (under 2 hours)
        if hours <= self.QUICK_WIN_HOURS:
            # Scale from 100 (0.1h) to 80 (2h)
            score = 100 - (hours / self.QUICK_WIN_HOURS) * 20
            return score
        
        # Manageable tasks (2-8 hours)
        if hours <= 8:
            # Scale from 80 to 50
            score = 80 - ((hours - 2) / 6) * 30
            return score
        
        # Significant effort (8-40 hours)
        if hours <= 40:
            # Scale from 50 to 20
            score = 50 - ((hours - 8) / 32) * 30
            return score
        
        # Major projects (beyond cap)
        return 10
    
    def calculate_complexity_score(self, task: Dict) -> float:
        """
        Calculate a complexity factor based on task characteristics.
        
        Factors considered:
        - Title length (longer titles often indicate more complex tasks)
        - Number of dependencies
        - Estimated hours
        
        Returns a score from 0-100 where higher = more complex.
        """
        title = task.get('title', '')
        dependencies = task.get('dependencies', [])
        hours = float(task.get('estimated_hours', 1))
        
        # Title complexity (normalized to 0-30)
        title_score = min(len(title) / 100, 1) * 30
        
        # Dependency complexity (normalized to 0-40)
        dep_score = min(len(dependencies) / 5, 1) * 40
        
        # Effort complexity (normalized to 0-30)
        effort_score = min(hours / 20, 1) * 30
        
        return title_score + dep_score + effort_score
    
    def classify_eisenhower(
        self, 
        urgency_score: float, 
        importance: int
    ) -> EisenhowerQuadrant:
        """
        Classify task into Eisenhower Matrix quadrant.
        
        Quadrants:
        - DO_NOW: Urgent + Important (crisis, deadlines)
        - PLAN: Not Urgent + Important (strategic work)
        - DELEGATE: Urgent + Not Important (interruptions)
        - ELIMINATE: Not Urgent + Not Important (time wasters)
        """
        is_urgent = urgency_score >= self.URGENCY_THRESHOLD
        is_important = importance >= self.IMPORTANCE_THRESHOLD
        
        if is_urgent and is_important:
            return EisenhowerQuadrant.DO_NOW
        elif not is_urgent and is_important:
            return EisenhowerQuadrant.PLAN
        elif is_urgent and not is_important:
            return EisenhowerQuadrant.DELEGATE
        else:
            return EisenhowerQuadrant.ELIMINATE
    
    def calculate_dependency_score(
        self, 
        task_id: Optional[int],
        task_dependencies: List[int],
        all_tasks: List[Dict],
        dependency_graph: Dict[int, Set[int]]
    ) -> Tuple[float, bool]:
        """
        Calculate dependency score based on how many tasks this one blocks.
        
        Scoring Logic:
        - Tasks that block 3+ other tasks: Score 80-100
        - Tasks that block 1-2 tasks: Score 50-80
        - Tasks with no dependents: Score 30 (baseline)
        - Tasks with unmet dependencies: Score penalty applied
        
        Also detects circular dependencies.
        
        Returns:
            Tuple of (dependency_score, is_blocking_others)
        """
        if task_id is None:
            # For tasks without IDs, we can only check their dependencies
            has_unmet_deps = len(task_dependencies) > 0
            return (30.0 if not has_unmet_deps else 20.0, False)
        
        # Count how many tasks depend on this one
        dependents_count = sum(
            1 for deps in dependency_graph.values() 
            if task_id in deps
        )
        
        is_blocking = dependents_count > 0
        
        # Base score on number of dependents
        if dependents_count >= 3:
            score = 80 + min(dependents_count - 3, 4) * 5  # Cap at 100
        elif dependents_count >= 1:
            score = 50 + dependents_count * 15
        else:
            score = 30
        
        # Penalty if this task has unmet dependencies
        if task_dependencies:
            # Check if any dependencies are unresolved
            all_task_ids = {t.get('id') for t in all_tasks if t.get('id') is not None}
            unmet_deps = [d for d in task_dependencies if d not in all_task_ids]
            if unmet_deps:
                score *= 0.8  # 20% penalty for having unmet dependencies
        
        return (min(score, 100), is_blocking)
    
    def detect_circular_dependencies(
        self, 
        tasks: List[Dict]
    ) -> Tuple[Dict[int, Set[int]], Set[int]]:
        """
        Build dependency graph and detect circular dependencies.
        
        Uses DFS-based cycle detection to identify tasks involved in
        circular dependency chains.
        
        Returns:
            Tuple of (dependency_graph, set of task IDs in cycles)
        """
        # Build adjacency list
        graph: Dict[int, Set[int]] = {}
        task_ids = set()
        
        for task in tasks:
            task_id = task.get('id')
            if task_id is not None:
                task_ids.add(task_id)
                deps = task.get('dependencies', [])
                graph[task_id] = set(deps) if deps else set()
        
        # DFS-based cycle detection
        circular_tasks: Set[int] = set()
        visited: Set[int] = set()
        rec_stack: Set[int] = set()
        
        def dfs(node: int, path: List[int]) -> bool:
            """DFS to detect cycles, returns True if cycle found."""
            if node in rec_stack:
                # Found cycle - mark all nodes in the cycle
                cycle_start = path.index(node)
                circular_tasks.update(path[cycle_start:])
                return True
            
            if node in visited:
                return False
            
            if node not in graph:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                if neighbor in task_ids:  # Only check valid task IDs
                    if dfs(neighbor, path):
                        return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        # Check all nodes
        for task_id in task_ids:
            if task_id not in visited:
                dfs(task_id, [])
        
        return graph, circular_tasks
    
    def calculate_priority_score(
        self,
        task: Dict,
        all_tasks: List[Dict],
        dependency_graph: Dict[int, Set[int]],
        circular_tasks: Set[int],
        reference_date: Optional[date] = None
    ) -> ScoredTask:
        """
        Calculate the complete priority score for a task.
        
        Combines all factor scores using configured weights.
        Also calculates Eisenhower quadrant and complexity score.
        """
        task_id = task.get('id')
        title = task.get('title', 'Untitled Task')
        due_date = task.get('due_date')
        estimated_hours = float(task.get('estimated_hours', 1))
        importance = int(task.get('importance', 5))
        dependencies = task.get('dependencies', [])
        
        # Parse due_date if string
        if isinstance(due_date, str):
            try:
                due_date = date.fromisoformat(due_date)
            except ValueError:
                due_date = None
        
        # Calculate individual scores (with working days)
        urgency_score, is_overdue, working_days = self.calculate_urgency_score(
            due_date, reference_date
        )
        importance_score = self.calculate_importance_score(importance)
        effort_score = self.calculate_effort_score(estimated_hours)
        dependency_score, is_blocking = self.calculate_dependency_score(
            task_id, dependencies, all_tasks, dependency_graph
        )
        
        # Calculate complexity
        complexity = self.calculate_complexity_score(task)
        
        # Classify Eisenhower quadrant
        quadrant = self.classify_eisenhower(urgency_score, importance)
        
        # Check for circular dependencies
        has_circular = task_id in circular_tasks if task_id else False
        if has_circular:
            # Penalty for circular dependencies
            dependency_score *= 0.5
        
        # Calculate weighted contributions
        urgency_contribution = urgency_score * self.weights.urgency
        importance_contribution = importance_score * self.weights.importance
        effort_contribution = effort_score * self.weights.effort
        dependency_contribution = dependency_score * self.weights.dependency
        
        # Final score
        priority_score = (
            urgency_contribution +
            importance_contribution +
            effort_contribution +
            dependency_contribution
        )
        
        # Determine priority level
        if priority_score >= 75:
            priority_level = "High"
        elif priority_score >= 50:
            priority_level = "Medium"
        else:
            priority_level = "Low"
        
        # Build score breakdown
        breakdown = ScoreBreakdown(
            urgency_score=urgency_score,
            importance_score=importance_score,
            effort_score=effort_score,
            dependency_score=dependency_score,
            urgency_contribution=urgency_contribution,
            importance_contribution=importance_contribution,
            effort_contribution=effort_contribution,
            dependency_contribution=dependency_contribution
        )
        
        # Generate detailed explanation
        explanation = self._generate_detailed_explanation(
            title=title,
            priority_level=priority_level,
            priority_score=priority_score,
            urgency_score=urgency_score,
            importance=importance,
            estimated_hours=estimated_hours,
            is_overdue=is_overdue,
            is_blocking=is_blocking,
            has_circular=has_circular,
            due_date=due_date,
            working_days=working_days,
            quadrant=quadrant,
            breakdown=breakdown
        )
        
        return ScoredTask(
            id=task_id,
            title=title,
            due_date=due_date,
            estimated_hours=estimated_hours,
            importance=importance,
            dependencies=dependencies,
            priority_score=round(priority_score, 2),
            priority_level=priority_level,
            score_breakdown=breakdown,
            explanation=explanation,
            has_circular_dependency=has_circular,
            is_overdue=is_overdue,
            is_blocking_others=is_blocking,
            eisenhower_quadrant=quadrant,
            working_days_until_due=working_days,
            complexity_score=round(complexity, 2)
        )
    
    def _generate_detailed_explanation(
        self,
        title: str,
        priority_level: str,
        priority_score: float,
        urgency_score: float,
        importance: int,
        estimated_hours: float,
        is_overdue: bool,
        is_blocking: bool,
        has_circular: bool,
        due_date: Optional[date],
        working_days: Optional[int],
        quadrant: EisenhowerQuadrant,
        breakdown: ScoreBreakdown
    ) -> str:
        """
        Generate a detailed, human-readable explanation for the priority score.
        
        This explanation helps users understand WHY a task has its priority,
        making the algorithm transparent and actionable.
        """
        parts = []
        
        # Primary classification
        quadrant_labels = {
            EisenhowerQuadrant.DO_NOW: "🔴 DO NOW - Urgent & Important",
            EisenhowerQuadrant.PLAN: "📅 PLAN - Important but not urgent",
            EisenhowerQuadrant.DELEGATE: "👥 DELEGATE - Urgent but less important",
            EisenhowerQuadrant.ELIMINATE: "⚪ CONSIDER - Neither urgent nor important"
        }
        parts.append(quadrant_labels.get(quadrant, ""))
        
        # Urgency explanation
        if is_overdue:
            parts.append(f"⚠️ OVERDUE by {abs(working_days)} working day(s) - needs immediate attention!")
        elif working_days is not None:
            if working_days == 0:
                parts.append("⏰ Due TODAY - critical deadline")
            elif working_days <= 2:
                parts.append(f"⏰ Due in {working_days} working day(s) - very urgent")
            elif working_days <= 5:
                parts.append(f"📅 Due in {working_days} working days - approaching deadline")
            elif working_days <= 10:
                parts.append(f"📅 Due in {working_days} working days - plan this week")
            else:
                parts.append(f"📅 Due in {working_days} working days - schedule for later")
        else:
            parts.append("📅 No due date set - moderate urgency assumed")
        
        # Importance explanation
        if importance >= 9:
            parts.append(f"⭐ Critical importance ({importance}/10) - business-critical task")
        elif importance >= 7:
            parts.append(f"⭐ High importance ({importance}/10) - significant impact")
        elif importance >= 5:
            parts.append(f"⭐ Moderate importance ({importance}/10)")
        else:
            parts.append(f"⭐ Lower importance ({importance}/10) - consider if necessary")
        
        # Effort explanation
        if estimated_hours <= 1:
            parts.append(f"⚡ Quick win ({estimated_hours}h) - easy to complete")
        elif estimated_hours <= 2:
            parts.append(f"⚡ Short task ({estimated_hours}h) - good for focused session")
        elif estimated_hours <= 4:
            parts.append(f"💪 Half-day task ({estimated_hours}h)")
        elif estimated_hours <= 8:
            parts.append(f"💪 Full-day task ({estimated_hours}h) - block dedicated time")
        else:
            parts.append(f"📦 Large project ({estimated_hours}h) - consider breaking down")
        
        # Dependency flags
        if is_blocking:
            parts.append("🔒 BLOCKING: Other tasks depend on this - prioritize!")
        
        if has_circular:
            parts.append("⚠️ CIRCULAR DEPENDENCY: Part of a dependency cycle - review task structure")
        
        # Score summary
        top_factor = self._identify_top_factor(breakdown)
        parts.append(f"📊 Score: {priority_score:.1f}/100 (Primary factor: {top_factor})")
        
        return " | ".join(parts)
    
    def _identify_top_factor(self, breakdown: ScoreBreakdown) -> str:
        """Identify which factor contributed most to the score."""
        contributions = {
            'Urgency': breakdown.urgency_contribution,
            'Importance': breakdown.importance_contribution,
            'Effort': breakdown.effort_contribution,
            'Dependencies': breakdown.dependency_contribution
        }
        return max(contributions, key=contributions.get)
    
    def analyze_tasks(
        self, 
        tasks: List[Dict],
        reference_date: Optional[date] = None
    ) -> List[ScoredTask]:
        """
        Analyze and score a list of tasks.
        
        Args:
            tasks: List of task dictionaries
            reference_date: Date to use for urgency calculations (defaults to today)
        
        Returns:
            List of ScoredTask objects, sorted by priority (highest first)
        """
        if not tasks:
            return []
        
        # Detect circular dependencies
        dependency_graph, circular_tasks = self.detect_circular_dependencies(tasks)
        
        # Score each task
        scored_tasks = [
            self.calculate_priority_score(
                task, tasks, dependency_graph, circular_tasks, reference_date
            )
            for task in tasks
        ]
        
        # Sort by priority score (descending)
        scored_tasks.sort(key=lambda t: t.priority_score, reverse=True)
        
        return scored_tasks
    
    def suggest_top_tasks(
        self,
        tasks: List[Dict],
        count: int = 3,
        max_hours: float = 8.0,
        reference_date: Optional[date] = None
    ) -> Tuple[List[ScoredTask], str]:
        """
        Suggest the top tasks to work on today.
        
        Uses the scoring algorithm plus additional heuristics:
        - Prioritizes overdue tasks
        - Considers total hours for the day
        - Ensures variety (not all high-effort tasks)
        
        Args:
            tasks: List of task dictionaries
            count: Maximum number of tasks to suggest
            max_hours: Maximum total hours for suggestions
            reference_date: Date for calculations
        
        Returns:
            Tuple of (suggested tasks, strategy message)
        """
        scored = self.analyze_tasks(tasks, reference_date)
        
        if not scored:
            return [], "No tasks provided for analysis."
        
        suggested = []
        total_hours = 0.0
        
        # First pass: Get overdue tasks
        for task in scored:
            if task.is_overdue and len(suggested) < count:
                suggested.append(task)
                total_hours += task.estimated_hours
        
        # Second pass: Fill with highest priority tasks
        for task in scored:
            if task in suggested:
                continue
            
            if len(suggested) >= count:
                break
            
            # Check if adding this task exceeds our hour budget
            if total_hours + task.estimated_hours <= max_hours or len(suggested) == 0:
                suggested.append(task)
                total_hours += task.estimated_hours
        
        strategy_msg = self._generate_strategy_message(suggested, total_hours)
        
        return suggested, strategy_msg
    
    def _generate_strategy_message(
        self, 
        tasks: List[ScoredTask], 
        total_hours: float
    ) -> str:
        """Generate a summary message for the suggested tasks."""
        if not tasks:
            return "No tasks to suggest. Add some tasks to get started!"
        
        overdue_count = sum(1 for t in tasks if t.is_overdue)
        high_priority = sum(1 for t in tasks if t.priority_level == "High")
        
        parts = []
        parts.append(f"Recommended {len(tasks)} task(s) for today")
        parts.append(f"Total estimated time: {total_hours:.1f} hours")
        
        if overdue_count:
            parts.append(f"⚠️ {overdue_count} overdue task(s) need immediate attention")
        
        if high_priority:
            parts.append(f"🔴 {high_priority} high-priority task(s)")
        
        strategy_name = {
            'smart_balance': 'Smart Balance',
            'fastest_wins': 'Fastest Wins',
            'high_impact': 'High Impact',
            'deadline_driven': 'Deadline Driven'
        }.get(self.strategy, 'Custom')
        
        parts.append(f"Strategy: {strategy_name}")
        
        return " | ".join(parts)


def scored_task_to_dict(task: ScoredTask) -> Dict:
    """Convert a ScoredTask to a dictionary for JSON serialization."""
    return {
        'id': task.id,
        'title': task.title,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'estimated_hours': task.estimated_hours,
        'importance': task.importance,
        'dependencies': task.dependencies,
        'priority_score': task.priority_score,
        'priority_level': task.priority_level,
        'score_breakdown': task.score_breakdown.to_dict(),
        'explanation': task.explanation,
        'is_overdue': task.is_overdue,
        'is_blocking_others': task.is_blocking_others,
        'has_circular_dependency': task.has_circular_dependency,
        'eisenhower_quadrant': task.eisenhower_quadrant.value,
        'working_days_until_due': task.working_days_until_due,
        'complexity_score': task.complexity_score
    }


def validate_tasks(tasks: List[Dict]) -> List[ValidationError]:
    """
    Validate a list of tasks and return any errors found.
    
    This provides detailed error codes for professional API responses.
    """
    errors = []
    
    if not tasks:
        errors.append(ValidationError(
            code=ErrorCode.ERR_EMPTY_TASKS,
            message="At least one task is required for analysis"
        ))
        return errors
    
    seen_ids = set()
    
    for i, task in enumerate(tasks):
        task_id = task.get('id', i + 1)
        
        # Check required fields
        if not task.get('title') or not str(task.get('title', '')).strip():
            errors.append(ValidationError(
                code=ErrorCode.ERR_MISSING_FIELD,
                message="Task title is required and cannot be empty",
                field='title',
                task_id=task_id
            ))
        
        # Check estimated hours
        hours = task.get('estimated_hours')
        if hours is None:
            errors.append(ValidationError(
                code=ErrorCode.ERR_MISSING_FIELD,
                message="Estimated hours is required",
                field='estimated_hours',
                task_id=task_id
            ))
        elif not isinstance(hours, (int, float)) or hours < 0.1:
            errors.append(ValidationError(
                code=ErrorCode.ERR_INVALID_HOURS,
                message="Estimated hours must be a positive number (minimum 0.1)",
                field='estimated_hours',
                task_id=task_id
            ))
        
        # Check importance
        importance = task.get('importance')
        if importance is None:
            errors.append(ValidationError(
                code=ErrorCode.ERR_MISSING_FIELD,
                message="Importance rating is required",
                field='importance',
                task_id=task_id
            ))
        elif not isinstance(importance, int) or importance < 1 or importance > 10:
            errors.append(ValidationError(
                code=ErrorCode.ERR_INVALID_IMPORTANCE,
                message="Importance must be an integer between 1 and 10",
                field='importance',
                task_id=task_id
            ))
        
        # Check due date format
        due_date = task.get('due_date')
        if due_date and isinstance(due_date, str):
            try:
                date.fromisoformat(due_date)
            except ValueError:
                errors.append(ValidationError(
                    code=ErrorCode.ERR_INVALID_DATE,
                    message="Due date must be in ISO format (YYYY-MM-DD)",
                    field='due_date',
                    task_id=task_id
                ))
        
        # Check for self-dependency
        dependencies = task.get('dependencies', [])
        if task.get('id') and task.get('id') in dependencies:
            errors.append(ValidationError(
                code=ErrorCode.ERR_SELF_DEPENDENCY,
                message="A task cannot depend on itself",
                field='dependencies',
                task_id=task_id
            ))
        
        # Track duplicate IDs
        if task.get('id'):
            if task['id'] in seen_ids:
                errors.append(ValidationError(
                    code=ErrorCode.ERR_INVALID_DEPENDENCY,
                    message=f"Duplicate task ID: {task['id']}",
                    field='id',
                    task_id=task_id
                ))
            seen_ids.add(task['id'])
    
    return errors


def validate_weights(weights: Dict) -> List[ValidationError]:
    """Validate custom weights configuration."""
    errors = []
    
    for key in ['urgency', 'importance', 'effort', 'dependency']:
        weight_key = f'{key}_weight'
        if weight_key in weights:
            value = weights[weight_key]
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                errors.append(ValidationError(
                    code=ErrorCode.ERR_INVALID_WEIGHTS,
                    message=f"{key.capitalize()} weight must be between 0 and 1",
                    field=weight_key
                ))
    
    return errors
