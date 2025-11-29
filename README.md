Smart Task Analyzer
An intelligent task prioritization system that helps you organize and prioritize your tasks using AI algorithms.

Features
Smart Priority Scoring: Ranks tasks based on urgency, importance, effort, and dependencies

Multiple Strategies: Choose from Smart Balance, Fastest Wins, High Impact, or Deadline Driven

Eisenhower Matrix: Automatically categorizes tasks into Do First, Schedule, Delegate, or Eliminate

Dependency Tracking: Visualize task relationships and detect circular dependencies

Customizable Weights: Adjust how each factor affects your priorities

Quick Setup
Backend (Django API)
bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
Frontend
Open frontend/index.html in your web browser.

How to Use
Add Tasks: Create tasks with titles, deadlines, importance ratings, and dependencies

Choose Strategy: Select a prioritization strategy that matches your goals

Get Recommendations: See AI-ranked tasks with detailed explanations

Visualize: View tasks in list, matrix, or dependency graph formats

API Endpoints
GET /api/tasks/ - List all tasks

POST /api/tasks/ - Create new task

POST /api/suggest/ - Get prioritized task suggestions

GET /api/strategies/ - Get available strategies

Example Task
json
{
  "title": "Fix login bug",
  "deadline": "2025-12-01",
  "importance": 4,
  "estimated_hours": 2,
  "dependencies": [2, 3]
}
Technologies Used
Backend: Django REST Framework

Frontend: HTML, CSS, JavaScript

Visualization: Mermaid.js

Testing: Django Test Framework

Running Tests
bash
cd backend
python manage.py test tasks
