"""
Serializers for the Task model.

This module provides serialization/deserialization for Task objects
and handles validation of incoming task data.
"""

from rest_framework import serializers
from datetime import date


class TaskInputSerializer(serializers.Serializer):
    """
    Serializer for validating incoming task data.
    
    This handles tasks that may not be persisted to the database,
    such as those submitted for analysis via the API.
    """
    
    id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    estimated_hours = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        min_value=0.1,
        required=True
    )
    importance = serializers.IntegerField(min_value=1, max_value=10, required=True)
    dependencies = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    
    def validate_title(self, value):
        """Ensure title is not empty or just whitespace."""
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty")
        return value.strip()
    
    def validate_dependencies(self, value):
        """Ensure dependencies is a valid list."""
        if value is None:
            return []
        return value


class TaskOutputSerializer(serializers.Serializer):
    """
    Serializer for task output with priority score and explanation.
    """
    
    id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField()
    due_date = serializers.DateField(allow_null=True)
    estimated_hours = serializers.DecimalField(max_digits=5, decimal_places=2)
    importance = serializers.IntegerField()
    dependencies = serializers.ListField(child=serializers.IntegerField())
    priority_score = serializers.FloatField()
    priority_level = serializers.CharField()
    score_breakdown = serializers.DictField()
    explanation = serializers.CharField()


class TaskBulkInputSerializer(serializers.Serializer):
    """
    Serializer for bulk task analysis requests.
    """
    
    tasks = serializers.ListField(
        child=TaskInputSerializer(),
        min_length=1,
        error_messages={
            'min_length': 'At least one task is required for analysis'
        }
    )
    strategy = serializers.ChoiceField(
        choices=[
            ('smart_balance', 'Smart Balance'),
            ('fastest_wins', 'Fastest Wins'),
            ('high_impact', 'High Impact'),
            ('deadline_driven', 'Deadline Driven')
        ],
        default='smart_balance',
        required=False
    )
    
    # Optional weight customization
    urgency_weight = serializers.FloatField(
        min_value=0, 
        max_value=1, 
        default=0.3, 
        required=False
    )
    importance_weight = serializers.FloatField(
        min_value=0, 
        max_value=1, 
        default=0.35, 
        required=False
    )
    effort_weight = serializers.FloatField(
        min_value=0, 
        max_value=1, 
        default=0.15, 
        required=False
    )
    dependency_weight = serializers.FloatField(
        min_value=0, 
        max_value=1, 
        default=0.2, 
        required=False
    )


class SuggestionOutputSerializer(serializers.Serializer):
    """
    Serializer for task suggestion output.
    """
    
    suggested_tasks = TaskOutputSerializer(many=True)
    total_estimated_hours = serializers.FloatField()
    strategy_used = serializers.CharField()
    message = serializers.CharField()
