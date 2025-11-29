"""
Task Model for the Smart Task Analyzer.

This module defines the Task model with all required properties for
intelligent task prioritization and scoring.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Task(models.Model):
    """
    Represents a task with properties for priority scoring.
    
    Attributes:
        title: The task's descriptive title
        due_date: When the task is due (optional for open-ended tasks)
        estimated_hours: Expected time to complete the task
        importance: User-provided rating from 1-10
        dependencies: JSON list of task IDs this task depends on
        created_at: Timestamp of task creation
    """
    
    title = models.CharField(max_length=255, help_text="Task title/description")
    due_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Task due date (optional)"
    )
    estimated_hours = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0.1)],
        help_text="Estimated hours to complete (minimum 0.1)"
    )
    importance = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Importance rating from 1 (low) to 10 (high)"
    )
    dependencies = models.JSONField(
        default=list,
        blank=True,
        help_text="List of task IDs that this task depends on"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} (Importance: {self.importance})"
    
    def clean(self):
        """Validate the task data."""
        from django.core.exceptions import ValidationError
        
        # Ensure dependencies is a list
        if self.dependencies is None:
            self.dependencies = []
        
        if not isinstance(self.dependencies, list):
            raise ValidationError({'dependencies': 'Dependencies must be a list of task IDs'})
