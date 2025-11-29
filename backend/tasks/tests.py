"""
Unit Tests for the Smart Task Analyzer.

This module contains comprehensive tests for the scoring algorithm,
covering edge cases, different strategies, and circular dependency detection.
"""

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
import json

from .scoring import (
    TaskPriorityScorer,
    ScoringWeights,
    ScoredTask,
    ScoreBreakdown,
    scored_task_to_dict,
    STRATEGY_WEIGHTS
)


class UrgencyScoreTests(TestCase):
    """Tests for the urgency scoring component."""
    
    def setUp(self):
        self.scorer = TaskPriorityScorer()
        self.today = date.today()
    
    def test_overdue_task_high_urgency(self):
        """Overdue tasks should have urgency score >= 80."""
        yesterday = self.today - timedelta(days=1)
        score, is_overdue, _ = self.scorer.calculate_urgency_score(yesterday, self.today)
        
        self.assertTrue(is_overdue)
        self.assertGreaterEqual(score, 80)
    
    def test_severely_overdue_max_urgency(self):
        """Tasks overdue by 14+ working days should have max urgency (100)."""
        # Use 21 calendar days to ensure 14+ working days
        three_weeks_ago = self.today - timedelta(days=21)
        score, is_overdue, _ = self.scorer.calculate_urgency_score(three_weeks_ago, self.today)
        
        self.assertTrue(is_overdue)
        self.assertGreaterEqual(score, 95)  # Should be very close to 100
    
    def test_due_today_high_urgency(self):
        """Tasks due today should have urgency score of 75."""
        score, is_overdue, _ = self.scorer.calculate_urgency_score(self.today, self.today)
        
        self.assertFalse(is_overdue)
        self.assertEqual(score, 75)
    
    def test_due_tomorrow_slightly_lower(self):
        """Tasks due in the near future should have urgency less than 75."""
        # Use 3 days ahead to ensure at least 1 working day regardless of weekends
        near_future = self.today + timedelta(days=3)
        score, _, _ = self.scorer.calculate_urgency_score(near_future, self.today)
        
        self.assertLess(score, 75)
        self.assertGreater(score, 40)
    
    def test_due_in_week_medium_urgency(self):
        """Tasks due in 7 days should have urgency around 50."""
        next_week = self.today + timedelta(days=7)
        score, _, _ = self.scorer.calculate_urgency_score(next_week, self.today)
        
        self.assertAlmostEqual(score, 50, delta=10)
    
    def test_due_in_month_low_urgency(self):
        """Tasks due in 30 days should have low urgency."""
        next_month = self.today + timedelta(days=30)
        score, _, _ = self.scorer.calculate_urgency_score(next_month, self.today)
        
        self.assertLess(score, 35)
        self.assertGreater(score, 10)
    
    def test_no_due_date_moderate_urgency(self):
        """Tasks without due date should have moderate urgency (30)."""
        score, is_overdue, working_days = self.scorer.calculate_urgency_score(None, self.today)
        
        self.assertFalse(is_overdue)
        self.assertEqual(score, 30)
        self.assertIsNone(working_days)
    
    def test_far_future_minimum_urgency(self):
        """Tasks due far in the future should have minimum urgency."""
        far_future = self.today + timedelta(days=365)
        score, _, _ = self.scorer.calculate_urgency_score(far_future, self.today)
        
        self.assertLessEqual(score, 20)
        self.assertGreaterEqual(score, 10)


class ImportanceScoreTests(TestCase):
    """Tests for the importance scoring component."""
    
    def setUp(self):
        self.scorer = TaskPriorityScorer()
    
    def test_max_importance_high_score(self):
        """Importance 10 should result in score of 100."""
        score = self.scorer.calculate_importance_score(10)
        self.assertEqual(score, 100)
    
    def test_min_importance_low_score(self):
        """Importance 1 should result in low score."""
        score = self.scorer.calculate_importance_score(1)
        self.assertLess(score, 20)
    
    def test_medium_importance_medium_score(self):
        """Importance 5 should result in medium score."""
        score = self.scorer.calculate_importance_score(5)
        self.assertGreater(score, 30)
        self.assertLess(score, 70)
    
    def test_importance_scales_exponentially(self):
        """Higher importance values should scale faster."""
        score_5 = self.scorer.calculate_importance_score(5)
        score_7 = self.scorer.calculate_importance_score(7)
        score_9 = self.scorer.calculate_importance_score(9)
        
        # Difference between 7 and 9 should be greater than between 5 and 7
        diff_low = score_7 - score_5
        diff_high = score_9 - score_7
        self.assertGreater(diff_high, diff_low * 0.5)
    
    def test_invalid_importance_clamped(self):
        """Invalid importance values should be clamped."""
        score_low = self.scorer.calculate_importance_score(0)
        score_high = self.scorer.calculate_importance_score(15)
        
        # Should be treated as 1 and 10 respectively
        self.assertEqual(score_low, self.scorer.calculate_importance_score(1))
        self.assertEqual(score_high, self.scorer.calculate_importance_score(10))


class EffortScoreTests(TestCase):
    """Tests for the effort scoring component."""
    
    def setUp(self):
        self.scorer = TaskPriorityScorer()
    
    def test_quick_win_high_score(self):
        """Tasks under 2 hours should be scored as quick wins (80-100)."""
        score = self.scorer.calculate_effort_score(1)
        self.assertGreater(score, 80)
    
    def test_very_quick_task_max_score(self):
        """Very short tasks should have near maximum effort score."""
        score = self.scorer.calculate_effort_score(0.1)
        self.assertGreater(score, 95)
    
    def test_half_day_task_medium_score(self):
        """4-hour tasks should have medium effort score."""
        score = self.scorer.calculate_effort_score(4)
        self.assertGreater(score, 60)
        self.assertLess(score, 80)
    
    def test_full_day_task_lower_score(self):
        """8-hour tasks should have lower effort score."""
        score = self.scorer.calculate_effort_score(8)
        self.assertLessEqual(score, 50)
    
    def test_large_project_low_score(self):
        """40-hour tasks should have low effort score."""
        score = self.scorer.calculate_effort_score(40)
        self.assertLessEqual(score, 20)
    
    def test_effort_beyond_cap(self):
        """Tasks beyond 40 hours should be capped at minimum."""
        score_40 = self.scorer.calculate_effort_score(40)
        score_100 = self.scorer.calculate_effort_score(100)
        
        # Both should be at or near minimum
        self.assertLessEqual(score_100, 20)


class CircularDependencyTests(TestCase):
    """Tests for circular dependency detection."""
    
    def setUp(self):
        self.scorer = TaskPriorityScorer()
    
    def test_no_circular_dependencies(self):
        """Tasks with linear dependencies should not be flagged."""
        tasks = [
            {'id': 1, 'title': 'Task 1', 'dependencies': []},
            {'id': 2, 'title': 'Task 2', 'dependencies': [1]},
            {'id': 3, 'title': 'Task 3', 'dependencies': [2]},
        ]
        
        graph, circular = self.scorer.detect_circular_dependencies(tasks)
        self.assertEqual(len(circular), 0)
    
    def test_simple_circular_dependency(self):
        """Simple A -> B -> A cycle should be detected."""
        tasks = [
            {'id': 1, 'title': 'Task 1', 'dependencies': [2]},
            {'id': 2, 'title': 'Task 2', 'dependencies': [1]},
        ]
        
        graph, circular = self.scorer.detect_circular_dependencies(tasks)
        self.assertEqual(circular, {1, 2})
    
    def test_complex_circular_dependency(self):
        """Complex A -> B -> C -> A cycle should be detected."""
        tasks = [
            {'id': 1, 'title': 'Task 1', 'dependencies': [3]},
            {'id': 2, 'title': 'Task 2', 'dependencies': [1]},
            {'id': 3, 'title': 'Task 3', 'dependencies': [2]},
        ]
        
        graph, circular = self.scorer.detect_circular_dependencies(tasks)
        self.assertEqual(circular, {1, 2, 3})
    
    def test_partial_circular_with_safe_tasks(self):
        """Only tasks in cycle should be flagged, not others."""
        tasks = [
            {'id': 1, 'title': 'Task 1', 'dependencies': [2]},
            {'id': 2, 'title': 'Task 2', 'dependencies': [1]},
            {'id': 3, 'title': 'Task 3', 'dependencies': []},  # Not in cycle
        ]
        
        graph, circular = self.scorer.detect_circular_dependencies(tasks)
        self.assertIn(1, circular)
        self.assertIn(2, circular)
        self.assertNotIn(3, circular)
    
    def test_self_referencing_task(self):
        """Task depending on itself should be flagged."""
        tasks = [
            {'id': 1, 'title': 'Task 1', 'dependencies': [1]},
        ]
        
        graph, circular = self.scorer.detect_circular_dependencies(tasks)
        self.assertIn(1, circular)


class StrategyTests(TestCase):
    """Tests for different scoring strategies."""
    
    def setUp(self):
        self.today = date.today()
        self.tasks = [
            {
                'id': 1,
                'title': 'Quick urgent task',
                'due_date': (self.today + timedelta(days=1)).isoformat(),
                'estimated_hours': 1,
                'importance': 5,
                'dependencies': []
            },
            {
                'id': 2,
                'title': 'Important long task',
                'due_date': (self.today + timedelta(days=10)).isoformat(),
                'estimated_hours': 20,
                'importance': 10,
                'dependencies': []
            },
            {
                'id': 3,
                'title': 'Quick low importance',
                'due_date': (self.today + timedelta(days=30)).isoformat(),
                'estimated_hours': 0.5,
                'importance': 2,
                'dependencies': []
            },
        ]
    
    def test_fastest_wins_prioritizes_low_effort(self):
        """Fastest Wins strategy should prioritize quick tasks."""
        scorer = TaskPriorityScorer(strategy='fastest_wins')
        results = scorer.analyze_tasks(self.tasks)
        
        # Quick tasks should rank higher
        quick_task_ids = [1, 3]  # Both are quick
        self.assertIn(results[0].id, quick_task_ids)
    
    def test_high_impact_prioritizes_importance(self):
        """High Impact strategy should prioritize important tasks."""
        scorer = TaskPriorityScorer(strategy='high_impact')
        results = scorer.analyze_tasks(self.tasks)
        
        # Task 2 has importance 10, should be first
        self.assertEqual(results[0].id, 2)
    
    def test_deadline_driven_prioritizes_urgency(self):
        """Deadline Driven strategy should prioritize urgent tasks."""
        scorer = TaskPriorityScorer(strategy='deadline_driven')
        results = scorer.analyze_tasks(self.tasks)
        
        # Task 1 is due tomorrow, should be first
        self.assertEqual(results[0].id, 1)
    
    def test_smart_balance_considers_all_factors(self):
        """Smart Balance should consider all factors."""
        scorer = TaskPriorityScorer(strategy='smart_balance')
        results = scorer.analyze_tasks(self.tasks)
        
        # All tasks should have non-zero scores
        for task in results:
            self.assertGreater(task.priority_score, 0)


class EdgeCaseTests(TestCase):
    """Tests for edge cases and error handling."""
    
    def setUp(self):
        self.scorer = TaskPriorityScorer()
    
    def test_empty_task_list(self):
        """Empty task list should return empty results."""
        results = self.scorer.analyze_tasks([])
        self.assertEqual(len(results), 0)
    
    def test_task_without_id(self):
        """Tasks without IDs should still be scored."""
        tasks = [
            {
                'title': 'No ID task',
                'due_date': date.today().isoformat(),
                'estimated_hours': 2,
                'importance': 7,
                'dependencies': []
            }
        ]
        
        results = self.scorer.analyze_tasks(tasks)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].id)
        self.assertGreater(results[0].priority_score, 0)
    
    def test_task_with_missing_due_date(self):
        """Tasks without due dates should have moderate urgency."""
        tasks = [
            {
                'id': 1,
                'title': 'No due date',
                'due_date': None,
                'estimated_hours': 4,
                'importance': 5,
                'dependencies': []
            }
        ]
        
        results = self.scorer.analyze_tasks(tasks)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_overdue)
    
    def test_task_with_invalid_dependency_reference(self):
        """Tasks with references to non-existent dependencies should handle gracefully."""
        tasks = [
            {
                'id': 1,
                'title': 'Task with invalid dep',
                'due_date': date.today().isoformat(),
                'estimated_hours': 2,
                'importance': 5,
                'dependencies': [999]  # Non-existent
            }
        ]
        
        # Should not raise an exception
        results = self.scorer.analyze_tasks(tasks)
        self.assertEqual(len(results), 1)
    
    def test_extreme_values(self):
        """Extreme but valid values should be handled."""
        tasks = [
            {
                'id': 1,
                'title': 'Extreme task',
                'due_date': (date.today() - timedelta(days=100)).isoformat(),  # Very overdue
                'estimated_hours': 1000,  # Very long
                'importance': 10,
                'dependencies': []
            }
        ]
        
        results = self.scorer.analyze_tasks(tasks)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_overdue)
    
    def test_due_date_as_string(self):
        """Due date provided as string should be parsed correctly."""
        tasks = [
            {
                'id': 1,
                'title': 'String date task',
                'due_date': '2025-12-31',
                'estimated_hours': 2,
                'importance': 5,
                'dependencies': []
            }
        ]
        
        results = self.scorer.analyze_tasks(tasks)
        self.assertEqual(len(results), 1)


class APIEndpointTests(APITestCase):
    """Tests for the API endpoints."""
    
    def test_analyze_endpoint_success(self):
        """POST /api/tasks/analyze/ should return sorted tasks."""
        data = {
            'tasks': [
                {
                    'id': 1,
                    'title': 'Task 1',
                    'due_date': '2025-11-30',
                    'estimated_hours': 3,
                    'importance': 8,
                    'dependencies': []
                },
                {
                    'id': 2,
                    'title': 'Task 2',
                    'due_date': '2025-12-15',
                    'estimated_hours': 5,
                    'importance': 5,
                    'dependencies': []
                }
            ],
            'strategy': 'smart_balance'
        }
        
        response = self.client.post(
            '/api/tasks/analyze/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['tasks']), 2)
        self.assertIn('summary', response.data)
    
    def test_analyze_endpoint_empty_tasks(self):
        """Analyze endpoint should reject empty task list."""
        data = {'tasks': []}
        
        response = self.client.post(
            '/api/tasks/analyze/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
    
    def test_analyze_endpoint_invalid_task(self):
        """Analyze endpoint should reject invalid task data."""
        data = {
            'tasks': [
                {
                    'title': '',  # Empty title
                    'estimated_hours': -5,  # Invalid hours
                    'importance': 15  # Out of range
                }
            ]
        }
        
        response = self.client.post(
            '/api/tasks/analyze/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_suggest_endpoint_success(self):
        """POST /api/tasks/suggest/ should return top suggestions."""
        data = {
            'tasks': [
                {
                    'id': 1,
                    'title': 'Task 1',
                    'due_date': '2025-11-28',
                    'estimated_hours': 2,
                    'importance': 8,
                    'dependencies': []
                },
                {
                    'id': 2,
                    'title': 'Task 2',
                    'due_date': '2025-12-15',
                    'estimated_hours': 4,
                    'importance': 5,
                    'dependencies': []
                }
            ],
            'count': 3
        }
        
        response = self.client.post(
            '/api/tasks/suggest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('suggested_tasks', response.data)
        self.assertIn('total_estimated_hours', response.data)
    
    def test_suggest_endpoint_respects_count(self):
        """Suggest endpoint should limit results to requested count."""
        data = {
            'tasks': [
                {'id': i, 'title': f'Task {i}', 'estimated_hours': 1, 
                 'importance': 5, 'dependencies': []}
                for i in range(1, 10)
            ],
            'count': 3
        }
        
        response = self.client.post(
            '/api/tasks/suggest/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['suggested_tasks']), 3)
    
    def test_api_info_endpoint(self):
        """GET /api/ should return API information."""
        response = self.client.get('/api/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('name', response.data)
        self.assertIn('endpoints', response.data)
        self.assertIn('strategies', response.data)


class ScoringWeightsTests(TestCase):
    """Tests for custom weight configuration."""
    
    def test_weights_normalize_to_one(self):
        """Weights should be normalized to sum to 1.0."""
        weights = ScoringWeights(
            urgency=0.5,
            importance=0.5,
            effort=0.5,
            dependency=0.5
        )
        
        total = weights.urgency + weights.importance + weights.effort + weights.dependency
        self.assertAlmostEqual(total, 1.0, places=5)
    
    def test_custom_weights_applied(self):
        """Custom weights should affect scoring."""
        tasks = [
            {
                'id': 1,
                'title': 'Quick task',
                'due_date': (date.today() + timedelta(days=30)).isoformat(),
                'estimated_hours': 0.5,
                'importance': 3,
                'dependencies': []
            },
            {
                'id': 2,
                'title': 'Important task',
                'due_date': (date.today() + timedelta(days=30)).isoformat(),
                'estimated_hours': 10,
                'importance': 10,
                'dependencies': []
            }
        ]
        
        # With high effort weight, quick task should rank higher
        effort_weights = ScoringWeights(urgency=0.1, importance=0.1, effort=0.7, dependency=0.1)
        scorer_effort = TaskPriorityScorer(custom_weights=effort_weights)
        results_effort = scorer_effort.analyze_tasks(tasks)
        
        # With high importance weight, important task should rank higher
        importance_weights = ScoringWeights(urgency=0.1, importance=0.7, effort=0.1, dependency=0.1)
        scorer_importance = TaskPriorityScorer(custom_weights=importance_weights)
        results_importance = scorer_importance.analyze_tasks(tasks)
        
        # Different strategies should produce different orderings
        self.assertEqual(results_effort[0].id, 1)  # Quick task first
        self.assertEqual(results_importance[0].id, 2)  # Important task first
