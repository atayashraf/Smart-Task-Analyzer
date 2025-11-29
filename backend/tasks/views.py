"""
API Views for the Smart Task Analyzer.

This module provides the REST API endpoints for task analysis
and priority suggestions with professional error handling,
rate limiting, and advanced features.
"""

from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from datetime import datetime
import re

from .serializers import (
    TaskBulkInputSerializer,
    TaskInputSerializer
)
from .scoring import (
    TaskPriorityScorer,
    ScoringWeights,
    scored_task_to_dict,
    validate_tasks,
    validate_weights,
    ErrorCode,
    EisenhowerQuadrant,
    STRATEGY_WEIGHTS
)


# ============================================
# RATE LIMITING CLASSES
# ============================================

class AnalyzeRateThrottle(AnonRateThrottle):
    """Rate limit for analyze endpoint - 30 requests per minute."""
    rate = '30/min'


class SuggestRateThrottle(AnonRateThrottle):
    """Rate limit for suggest endpoint - 30 requests per minute."""
    rate = '30/min'


class ExportRateThrottle(AnonRateThrottle):
    """Rate limit for export endpoints - 10 requests per minute."""
    rate = '10/min'


# ============================================
# TASK PATTERN DETECTION
# ============================================

# Keywords that suggest high importance
HIGH_IMPORTANCE_KEYWORDS = [
    'critical', 'urgent', 'emergency', 'asap', 'important', 'priority',
    'blocker', 'blocking', 'deadline', 'must', 'required', 'essential',
    'production', 'outage', 'down', 'broken', 'fix', 'bug', 'security',
    'customer', 'client', 'ceo', 'vp', 'executive', 'stakeholder'
]

# Keywords that suggest low importance
LOW_IMPORTANCE_KEYWORDS = [
    'nice to have', 'maybe', 'someday', 'future', 'backlog', 'low priority',
    'refactor', 'cleanup', 'documentation', 'readme', 'comment', 'style',
    'formatting', 'optimization', 'enhancement', 'improvement', 'wish'
]

# Keywords that suggest high effort
HIGH_EFFORT_KEYWORDS = [
    'rewrite', 'redesign', 'architecture', 'migration', 'infrastructure',
    'database', 'integration', 'api', 'system', 'framework', 'platform',
    'major', 'complete', 'full', 'entire', 'overhaul', 'rebuild'
]

# Keywords that suggest low effort
LOW_EFFORT_KEYWORDS = [
    'quick', 'simple', 'easy', 'minor', 'small', 'tiny', 'typo', 'tweak',
    'update', 'change', 'add', 'remove', 'fix typo', 'rename', 'move'
]


def detect_task_patterns(title: str, description: str = '') -> dict:
    """
    Analyze task title and description to auto-detect importance and effort hints.
    
    Returns:
        dict with suggested_importance (1-10), suggested_effort_hours, and confidence
    """
    text = f"{title} {description}".lower()
    
    result = {
        'suggested_importance': None,
        'suggested_effort_hours': None,
        'importance_confidence': 0,
        'effort_confidence': 0,
        'detected_keywords': []
    }
    
    # Check for high importance keywords
    high_imp_matches = [kw for kw in HIGH_IMPORTANCE_KEYWORDS if kw in text]
    low_imp_matches = [kw for kw in LOW_IMPORTANCE_KEYWORDS if kw in text]
    
    if high_imp_matches:
        result['suggested_importance'] = min(8 + len(high_imp_matches), 10)
        result['importance_confidence'] = min(0.3 + 0.15 * len(high_imp_matches), 0.9)
        result['detected_keywords'].extend(high_imp_matches)
    elif low_imp_matches:
        result['suggested_importance'] = max(3 - len(low_imp_matches) // 2, 1)
        result['importance_confidence'] = min(0.3 + 0.1 * len(low_imp_matches), 0.7)
        result['detected_keywords'].extend(low_imp_matches)
    
    # Check for effort keywords
    high_effort_matches = [kw for kw in HIGH_EFFORT_KEYWORDS if kw in text]
    low_effort_matches = [kw for kw in LOW_EFFORT_KEYWORDS if kw in text]
    
    if high_effort_matches:
        result['suggested_effort_hours'] = 8 + len(high_effort_matches) * 4
        result['effort_confidence'] = min(0.3 + 0.1 * len(high_effort_matches), 0.7)
        result['detected_keywords'].extend(high_effort_matches)
    elif low_effort_matches:
        result['suggested_effort_hours'] = max(1 - len(low_effort_matches) * 0.25, 0.5)
        result['effort_confidence'] = min(0.3 + 0.1 * len(low_effort_matches), 0.7)
        result['detected_keywords'].extend(low_effort_matches)
    
    return result


# ============================================
# TIME-BASED SUGGESTIONS
# ============================================

def get_time_based_adjustments() -> dict:
    """
    Get suggested adjustments based on current time of day.
    
    Returns:
        dict with time_context, suggested_max_hours, effort_preference, and message
    """
    now = datetime.now()
    hour = now.hour
    
    # Define time periods
    if 5 <= hour < 9:
        return {
            'time_context': 'early_morning',
            'suggested_max_hours': 8,
            'effort_preference': 'high',  # Fresh mind, tackle complex tasks
            'focus_level': 'high',
            'message': 'Early morning - great time for complex, high-focus tasks!'
        }
    elif 9 <= hour < 12:
        return {
            'time_context': 'morning',
            'suggested_max_hours': 6,
            'effort_preference': 'high',
            'focus_level': 'high',
            'message': 'Peak productivity hours - tackle your most important work!'
        }
    elif 12 <= hour < 14:
        return {
            'time_context': 'midday',
            'suggested_max_hours': 4,
            'effort_preference': 'medium',
            'focus_level': 'medium',
            'message': 'Post-lunch period - good for moderate complexity tasks.'
        }
    elif 14 <= hour < 17:
        return {
            'time_context': 'afternoon',
            'suggested_max_hours': 4,
            'effort_preference': 'medium',
            'focus_level': 'medium',
            'message': 'Afternoon focus - balance important and quick-win tasks.'
        }
    elif 17 <= hour < 20:
        return {
            'time_context': 'evening',
            'suggested_max_hours': 2,
            'effort_preference': 'low',
            'focus_level': 'low',
            'message': 'Evening hours - focus on lighter tasks or wrap-up work.'
        }
    elif 20 <= hour < 23:
        return {
            'time_context': 'late_evening',
            'suggested_max_hours': 1,
            'effort_preference': 'low',
            'focus_level': 'low',
            'message': 'Late evening - only tackle quick, low-effort tasks.'
        }
    else:  # 23-5
        return {
            'time_context': 'night',
            'suggested_max_hours': 0.5,
            'effort_preference': 'minimal',
            'focus_level': 'minimal',
            'message': 'Late night - consider resting! Only urgent items if needed.'
        }


# ============================================
# TASK FATIGUE MODEL
# ============================================

def calculate_fatigue_adjustment(
    completed_tasks: list,
    current_task_effort: float,
    current_task_category: str = None
) -> dict:
    """
    Calculate fatigue-based score adjustment based on previously completed work.
    
    Args:
        completed_tasks: List of dicts with 'effort_hours' and 'category' keys
        current_task_effort: Hours for the task being evaluated
        current_task_category: Optional category of current task
    
    Returns:
        dict with fatigue_level, score_multiplier, and recommendation
    """
    if not completed_tasks:
        return {
            'fatigue_level': 0,
            'score_multiplier': 1.0,
            'total_hours_worked': 0,
            'consecutive_heavy_tasks': 0,
            'recommendation': 'Fresh start - ready for any task!'
        }
    
    total_hours = sum(t.get('effort_hours', 0) for t in completed_tasks)
    
    # Count consecutive heavy tasks (> 2 hours)
    consecutive_heavy = 0
    for task in reversed(completed_tasks):
        if task.get('effort_hours', 0) > 2:
            consecutive_heavy += 1
        else:
            break
    
    # Count same-category tasks in a row
    same_category_streak = 0
    if current_task_category:
        for task in reversed(completed_tasks):
            if task.get('category') == current_task_category:
                same_category_streak += 1
            else:
                break
    
    # Calculate fatigue level (0-100)
    fatigue_level = min(100, (
        (total_hours / 8) * 40 +  # Hours worked contribution
        consecutive_heavy * 15 +   # Consecutive heavy tasks
        same_category_streak * 10  # Same category fatigue
    ))
    
    # Calculate score multiplier (tasks should be deprioritized when fatigued)
    if fatigue_level < 20:
        multiplier = 1.0
        recommendation = 'Energy levels good - proceed with planned tasks.'
    elif fatigue_level < 40:
        multiplier = 0.95
        recommendation = 'Slight fatigue - consider mixing in a quick win.'
    elif fatigue_level < 60:
        multiplier = 0.85
        recommendation = 'Moderate fatigue - prioritize shorter, easier tasks.'
    elif fatigue_level < 80:
        multiplier = 0.70
        recommendation = 'High fatigue - strongly recommend switching to quick tasks or taking a break.'
    else:
        multiplier = 0.50
        recommendation = 'Very high fatigue - consider stopping or only doing minimal tasks.'
    
    # Extra penalty if current task is also heavy
    if current_task_effort > 4 and fatigue_level > 50:
        multiplier *= 0.8
        recommendation += ' Avoid starting new heavy tasks.'
    
    return {
        'fatigue_level': round(fatigue_level, 1),
        'score_multiplier': round(multiplier, 2),
        'total_hours_worked': round(total_hours, 1),
        'consecutive_heavy_tasks': consecutive_heavy,
        'same_category_streak': same_category_streak,
        'recommendation': recommendation
    }


# ============================================
# API ENDPOINTS
# ============================================

@extend_schema(
    summary="Analyze and prioritize tasks",
    description="""
    Analyze a list of tasks and return them sorted by priority score.
    
    Supports customizable weights and multiple sorting strategies.
    Returns Eisenhower Matrix classification and detailed explanations.
    """,
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'tasks': {'type': 'array', 'items': {'type': 'object'}},
                'strategy': {'type': 'string', 'enum': ['smart_balance', 'fastest_wins', 'high_impact', 'deadline_driven']},
                'weights': {'type': 'object'},
            },
            'required': ['tasks']
        }
    },
    responses={200: OpenApiTypes.OBJECT},
    tags=['Analysis']
)
@api_view(['POST'])
@throttle_classes([AnalyzeRateThrottle])
def analyze_tasks(request: Request) -> Response:
    """
    Analyze a list of tasks and return them sorted by priority score.
    
    POST /api/tasks/analyze/
    
    Request Body:
    {
        "tasks": [...],
        "strategy": "smart_balance",           // Optional
        "weights": {                           // Optional custom weights
            "urgency": 0.3,
            "importance": 0.35,
            "effort": 0.15,
            "dependency": 0.2
        },
        "skip_weekends": true,                 // Optional (default: true)
        "auto_detect_patterns": true,          // Optional: auto-adjust based on keywords
        "time_aware": true                     // Optional: adjust based on time of day
    }
    """
    serializer = TaskBulkInputSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {
                'success': False,
                'error_code': ErrorCode.ERR_MISSING_FIELD.value,
                'errors': serializer.errors,
                'message': 'Invalid input data. Please check your tasks format.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    tasks = validated_data['tasks']
    strategy = validated_data.get('strategy', 'smart_balance')
    
    # Validate strategy
    if strategy not in STRATEGY_WEIGHTS:
        return Response(
            {
                'success': False,
                'error_code': ErrorCode.ERR_INVALID_STRATEGY.value,
                'message': f"Invalid strategy: {strategy}. Valid options: {list(STRATEGY_WEIGHTS.keys())}"
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for custom weights
    custom_weights = None
    weights_dict = request.data.get('weights', {})
    
    if weights_dict or any(
        validated_data.get(w) is not None 
        for w in ['urgency_weight', 'importance_weight', 'effort_weight', 'dependency_weight']
    ):
        custom_weights = ScoringWeights(
            urgency=weights_dict.get('urgency', validated_data.get('urgency_weight', 0.3)),
            importance=weights_dict.get('importance', validated_data.get('importance_weight', 0.35)),
            effort=weights_dict.get('effort', validated_data.get('effort_weight', 0.15)),
            dependency=weights_dict.get('dependency', validated_data.get('dependency_weight', 0.2))
        )
    
    # Get options
    skip_weekends = request.data.get('skip_weekends', True)
    auto_detect = request.data.get('auto_detect_patterns', False)
    time_aware = request.data.get('time_aware', False)
    
    # Auto-detect patterns if enabled
    pattern_hints = {}
    if auto_detect:
        for task in tasks:
            task_id = task.get('id', task.get('title', ''))
            pattern_hints[task_id] = detect_task_patterns(
                task.get('title', ''),
                task.get('description', '')
            )
    
    # Get time-based adjustments if enabled
    time_adjustments = get_time_based_adjustments() if time_aware else None
    
    # Create scorer and analyze
    scorer = TaskPriorityScorer(
        strategy=strategy, 
        custom_weights=custom_weights,
        skip_weekends=skip_weekends
    )
    scored_tasks = scorer.analyze_tasks(tasks)
    
    # Build response
    result_tasks = [scored_task_to_dict(t) for t in scored_tasks]
    
    # Add pattern hints if detected
    if auto_detect:
        for task in result_tasks:
            task_id = task.get('id', task.get('title', ''))
            if task_id in pattern_hints:
                task['pattern_detection'] = pattern_hints[task_id]
    
    # Calculate summary statistics
    high_count = sum(1 for t in scored_tasks if t.priority_level == "High")
    medium_count = sum(1 for t in scored_tasks if t.priority_level == "Medium")
    low_count = sum(1 for t in scored_tasks if t.priority_level == "Low")
    overdue_count = sum(1 for t in scored_tasks if t.is_overdue)
    circular_detected = any(t.has_circular_dependency for t in scored_tasks)
    
    # Eisenhower quadrant distribution
    quadrant_counts = {
        'do_now': sum(1 for t in scored_tasks if t.eisenhower_quadrant == EisenhowerQuadrant.DO_NOW),
        'plan': sum(1 for t in scored_tasks if t.eisenhower_quadrant == EisenhowerQuadrant.PLAN),
        'delegate': sum(1 for t in scored_tasks if t.eisenhower_quadrant == EisenhowerQuadrant.DELEGATE),
        'eliminate': sum(1 for t in scored_tasks if t.eisenhower_quadrant == EisenhowerQuadrant.ELIMINATE)
    }
    
    response_data = {
        'success': True,
        'error_code': ErrorCode.SUCCESS.value,
        'count': len(result_tasks),
        'strategy': strategy,
        'weights_used': scorer.weights.to_dict(),
        'skip_weekends': skip_weekends,
        'tasks': result_tasks,
        'summary': {
            'total_tasks': len(result_tasks),
            'high_priority_count': high_count,
            'medium_priority_count': medium_count,
            'low_priority_count': low_count,
            'overdue_count': overdue_count,
            'circular_dependencies_detected': circular_detected
        },
        'eisenhower_matrix': {
            'quadrants': quadrant_counts,
            'labels': {
                'do_now': '🔴 Do Now (Urgent + Important)',
                'plan': '📅 Plan (Important, Not Urgent)',
                'delegate': '👥 Delegate (Urgent, Less Important)',
                'eliminate': '⚪ Eliminate (Neither)'
            }
        }
    }
    
    # Add time-based context if enabled
    if time_adjustments:
        response_data['time_context'] = time_adjustments
    
    return Response(response_data)


@extend_schema(
    summary="Get task suggestions for today",
    description="""
    Return the top tasks the user should work on based on priority analysis.
    Supports time-aware suggestions and fatigue modeling.
    """,
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'tasks': {'type': 'array', 'items': {'type': 'object'}},
                'strategy': {'type': 'string'},
                'count': {'type': 'integer', 'default': 3},
                'max_hours': {'type': 'number', 'default': 8.0},
                'completed_tasks': {'type': 'array', 'description': 'Previously completed tasks for fatigue calculation'},
            },
            'required': ['tasks']
        }
    },
    responses={200: OpenApiTypes.OBJECT},
    tags=['Suggestions']
)
@api_view(['POST'])
@throttle_classes([SuggestRateThrottle])
def suggest_tasks(request: Request) -> Response:
    """
    Return the top tasks the user should work on today with explanations.
    
    POST /api/tasks/suggest/
    
    Request Body:
    {
        "tasks": [...],
        "strategy": "smart_balance",
        "count": 3,                   // Optional, default 3
        "max_hours": 8.0,             // Optional, max hours for the day
        "weights": {...},             // Optional custom weights
        "time_aware": true,           // Optional: adjust based on time
        "completed_tasks": [...]      // Optional: for fatigue calculation
    }
    """
    # Extract tasks from request
    tasks_data = request.data.get('tasks', [])
    
    if not tasks_data:
        return Response(
            {
                'success': False,
                'error_code': ErrorCode.ERR_EMPTY_TASKS.value,
                'message': 'No tasks provided. Please submit at least one task.',
                'suggested_tasks': [],
                'total_estimated_hours': 0
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate tasks
    validated_tasks = []
    for task in tasks_data:
        task_serializer = TaskInputSerializer(data=task)
        if task_serializer.is_valid():
            validated_tasks.append(task_serializer.validated_data)
        else:
            continue
    
    if not validated_tasks:
        return Response(
            {
                'success': False,
                'error_code': ErrorCode.ERR_MISSING_FIELD.value,
                'message': 'All provided tasks were invalid. Please check the format.',
                'errors': 'Invalid task format',
                'suggested_tasks': [],
                'total_estimated_hours': 0
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    strategy = request.data.get('strategy', 'smart_balance')
    count = int(request.data.get('count', 3))
    max_hours = float(request.data.get('max_hours', 8.0))
    time_aware = request.data.get('time_aware', False)
    completed_tasks = request.data.get('completed_tasks', [])
    
    # Get time adjustments
    time_adjustments = None
    if time_aware:
        time_adjustments = get_time_based_adjustments()
        # Adjust max_hours based on time of day
        max_hours = min(max_hours, time_adjustments['suggested_max_hours'])
    
    # Calculate fatigue
    fatigue_info = None
    if completed_tasks:
        avg_effort = sum(t.get('estimated_hours', 2) for t in validated_tasks) / len(validated_tasks)
        fatigue_info = calculate_fatigue_adjustment(completed_tasks, avg_effort)
    
    # Handle custom weights
    custom_weights = None
    weights_dict = request.data.get('weights', {})
    if weights_dict:
        custom_weights = ScoringWeights(
            urgency=weights_dict.get('urgency', 0.3),
            importance=weights_dict.get('importance', 0.35),
            effort=weights_dict.get('effort', 0.15),
            dependency=weights_dict.get('dependency', 0.2)
        )
    
    # Create scorer and get suggestions
    scorer = TaskPriorityScorer(strategy=strategy, custom_weights=custom_weights)
    suggested, message = scorer.suggest_top_tasks(
        validated_tasks, 
        count=count, 
        max_hours=max_hours
    )
    
    # Calculate total hours
    total_hours = sum(t.estimated_hours for t in suggested)
    
    # Build response
    result_tasks = [scored_task_to_dict(t) for t in suggested]
    
    # Group by Eisenhower quadrant
    quadrant_groups = {}
    for task in suggested:
        quadrant = task.eisenhower_quadrant.value
        if quadrant not in quadrant_groups:
            quadrant_groups[quadrant] = []
        quadrant_groups[quadrant].append(task.title)
    
    response_data = {
        'success': True,
        'error_code': ErrorCode.SUCCESS.value,
        'suggested_tasks': result_tasks,
        'total_estimated_hours': round(total_hours, 2),
        'strategy_used': strategy,
        'weights_used': scorer.weights.to_dict(),
        'message': message,
        'quadrant_breakdown': quadrant_groups
    }
    
    if time_adjustments:
        response_data['time_context'] = time_adjustments
    
    if fatigue_info:
        response_data['fatigue_analysis'] = fatigue_info
    
    return Response(response_data)


@extend_schema(
    summary="Detect task patterns",
    description="Analyze task title and description to auto-detect importance and effort hints.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'description': {'type': 'string'},
            },
            'required': ['title']
        }
    },
    responses={200: OpenApiTypes.OBJECT},
    tags=['Utilities']
)
@api_view(['POST'])
def detect_patterns(request: Request) -> Response:
    """
    Analyze a task's title and description to detect patterns.
    
    POST /api/tasks/detect-patterns/
    """
    title = request.data.get('title', '')
    description = request.data.get('description', '')
    
    if not title:
        return Response(
            {'error': 'Title is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    patterns = detect_task_patterns(title, description)
    
    return Response({
        'success': True,
        'title': title,
        'patterns': patterns
    })


@extend_schema(
    summary="Get time-based context",
    description="Get suggested work patterns based on current time of day.",
    responses={200: OpenApiTypes.OBJECT},
    tags=['Utilities']
)
@api_view(['GET'])
def get_time_context(request: Request) -> Response:
    """
    Get time-based work suggestions.
    
    GET /api/tasks/time-context/
    """
    return Response({
        'success': True,
        'current_time': datetime.now().isoformat(),
        **get_time_based_adjustments()
    })


@extend_schema(
    summary="Calculate fatigue level",
    description="Calculate work fatigue based on completed tasks.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'completed_tasks': {'type': 'array'},
                'next_task_effort': {'type': 'number'},
            },
            'required': ['completed_tasks']
        }
    },
    responses={200: OpenApiTypes.OBJECT},
    tags=['Utilities']
)
@api_view(['POST'])
def calculate_fatigue(request: Request) -> Response:
    """
    Calculate fatigue level based on completed work.
    
    POST /api/tasks/fatigue/
    """
    completed_tasks = request.data.get('completed_tasks', [])
    next_task_effort = float(request.data.get('next_task_effort', 2))
    next_task_category = request.data.get('next_task_category')
    
    fatigue_info = calculate_fatigue_adjustment(
        completed_tasks,
        next_task_effort,
        next_task_category
    )
    
    return Response({
        'success': True,
        **fatigue_info
    })


@extend_schema(
    summary="Export tasks as JSON",
    description="Export analyzed tasks in JSON format.",
    responses={200: OpenApiTypes.OBJECT},
    tags=['Export']
)
@api_view(['POST'])
@throttle_classes([ExportRateThrottle])
def export_json(request: Request) -> Response:
    """
    Export tasks and analysis as JSON.
    
    POST /api/tasks/export/json/
    """
    tasks_data = request.data.get('tasks', [])
    strategy = request.data.get('strategy', 'smart_balance')
    
    if not tasks_data:
        return Response({'error': 'No tasks to export'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Analyze tasks first
    validated_tasks = []
    for task in tasks_data:
        task_serializer = TaskInputSerializer(data=task)
        if task_serializer.is_valid():
            validated_tasks.append(task_serializer.validated_data)
    
    scorer = TaskPriorityScorer(strategy=strategy)
    scored_tasks = scorer.analyze_tasks(validated_tasks)
    result_tasks = [scored_task_to_dict(t) for t in scored_tasks]
    
    export_data = {
        'exported_at': datetime.now().isoformat(),
        'strategy': strategy,
        'total_tasks': len(result_tasks),
        'tasks': result_tasks,
        'summary': {
            'high_priority': sum(1 for t in scored_tasks if t.priority_level == "High"),
            'medium_priority': sum(1 for t in scored_tasks if t.priority_level == "Medium"),
            'low_priority': sum(1 for t in scored_tasks if t.priority_level == "Low"),
        }
    }
    
    return Response(export_data)


@extend_schema(
    summary="Export tasks as CSV",
    description="Export analyzed tasks in CSV format.",
    responses={200: OpenApiTypes.STR},
    tags=['Export']
)
@api_view(['POST'])
@throttle_classes([ExportRateThrottle])
def export_csv(request: Request) -> Response:
    """
    Export tasks and analysis as CSV.
    
    POST /api/tasks/export/csv/
    """
    import csv
    from io import StringIO
    from django.http import HttpResponse
    
    tasks_data = request.data.get('tasks', [])
    strategy = request.data.get('strategy', 'smart_balance')
    
    if not tasks_data:
        return Response({'error': 'No tasks to export'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Analyze tasks
    validated_tasks = []
    for task in tasks_data:
        task_serializer = TaskInputSerializer(data=task)
        if task_serializer.is_valid():
            validated_tasks.append(task_serializer.validated_data)
    
    scorer = TaskPriorityScorer(strategy=strategy)
    scored_tasks = scorer.analyze_tasks(validated_tasks)
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Rank', 'Title', 'Priority Score', 'Priority Level', 'Urgency Score',
        'Importance Score', 'Effort Score', 'Dependency Score', 'Eisenhower Quadrant',
        'Due Date', 'Estimated Hours', 'Is Overdue', 'Explanation'
    ])
    
    # Data rows
    for i, task in enumerate(scored_tasks, 1):
        writer.writerow([
            i,
            task.title,
            round(task.priority_score, 3),
            task.priority_level,
            round(task.scores.urgency, 3),
            round(task.scores.importance, 3),
            round(task.scores.effort, 3),
            round(task.scores.dependency, 3),
            task.eisenhower_quadrant.value,
            task.due_date,
            task.estimated_hours,
            task.is_overdue,
            task.explanation
        ])
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="task_analysis.csv"'
    return response


@extend_schema(
    summary="API information",
    description="Get API information and available endpoints.",
    responses={200: OpenApiTypes.OBJECT},
    tags=['Info']
)
@api_view(['GET'])
def api_info(request: Request) -> Response:
    """
    Return API information and available endpoints.
    
    GET /api/
    """
    return Response({
        'name': 'Smart Task Analyzer API',
        'version': '2.0.0',
        'documentation': '/api/docs/',
        'features': [
            'Multi-factor priority scoring',
            'Customizable algorithm weights',
            'Eisenhower Matrix classification',
            'Weekend & holiday awareness',
            'Circular dependency detection',
            'Human-readable explanations',
            'Rate limiting (30 req/min)',
            'OpenAPI/Swagger documentation',
            'Auto-detect task patterns',
            'Time-based suggestions',
            'Task fatigue modeling',
            'Export (JSON/CSV)'
        ],
        'endpoints': {
            'POST /api/tasks/analyze/': 'Analyze and sort tasks by priority',
            'POST /api/tasks/suggest/': 'Get top task suggestions for today',
            'GET /api/tasks/strategies/': 'Get available sorting strategies',
            'POST /api/tasks/detect-patterns/': 'Auto-detect task importance/effort',
            'GET /api/tasks/time-context/': 'Get time-based work suggestions',
            'POST /api/tasks/fatigue/': 'Calculate work fatigue level',
            'POST /api/tasks/export/json/': 'Export analysis as JSON',
            'POST /api/tasks/export/csv/': 'Export analysis as CSV',
            'GET /api/docs/': 'Interactive API documentation',
            'GET /api/schema/': 'OpenAPI schema',
            'GET /api/': 'This info endpoint'
        },
        'strategies': {
            'smart_balance': 'Balanced consideration of all factors (default)',
            'fastest_wins': 'Prioritize low-effort quick wins',
            'high_impact': 'Prioritize importance over everything',
            'deadline_driven': 'Prioritize based on due date urgency'
        },
        'error_codes': {
            code.value: code.name for code in ErrorCode
        }
    })


@extend_schema(
    summary="Get available strategies",
    description="Return available sorting strategies and their configurations.",
    responses={200: OpenApiTypes.OBJECT},
    tags=['Info']
)
@api_view(['GET'])
def get_strategies(request: Request) -> Response:
    """
    Return available sorting strategies and their weight configurations.
    
    GET /api/tasks/strategies/
    """
    strategies = {}
    for name, weights in STRATEGY_WEIGHTS.items():
        strategies[name] = {
            'name': name.replace('_', ' ').title(),
            'description': {
                'smart_balance': 'Balanced consideration of urgency, importance, effort, and dependencies',
                'fastest_wins': 'Prioritizes quick tasks to build momentum and clear your backlog',
                'high_impact': 'Focuses on the most important tasks regardless of deadline',
                'deadline_driven': 'Prioritizes tasks by their due dates and urgency'
            }.get(name, ''),
            'weights': weights.to_dict(),
            'best_for': {
                'smart_balance': 'General productivity, mixed task lists',
                'fastest_wins': 'Overwhelming backlogs, building momentum',
                'high_impact': 'Strategic work, long-term projects',
                'deadline_driven': 'Deadline-heavy environments, time-sensitive work'
            }.get(name, '')
        }
    
    return Response({
        'success': True,
        'strategies': strategies,
        'default': 'smart_balance'
    })
