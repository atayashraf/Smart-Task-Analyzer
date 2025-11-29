# 📊 Smart Task Analyzer

An intelligent task prioritization system that uses multi-factor AI algorithms to score and rank tasks. Features customizable weights, Eisenhower Matrix classification, dependency graph visualization, and weekend/holiday awareness.

## 🚀 Features

### Core Features
- **Multi-Factor Priority Scoring**: Advanced algorithm analyzing urgency, importance, effort, and dependencies
- **Customizable Algorithm Weights**: Fine-tune how each factor influences priority scores
- **4 Built-in Strategies**: Smart Balance, Fastest Wins, High Impact, Deadline Driven
- **Circular Dependency Detection**: Identifies and flags tasks caught in dependency cycles

### Advanced Features (v2.0)
- **🎯 Eisenhower Matrix Classification**: Automatic Do First/Schedule/Delegate/Eliminate categorization
- **📅 Weekend & Holiday Awareness**: Urgency calculations use working days, not calendar days
- **🔗 Dependency Graph Visualization**: Interactive Mermaid.js graph showing task relationships
- **💬 Human-Readable Explanations**: Detailed reasoning for each task's priority ranking
- **📊 Complexity Scoring**: Tasks rated by complexity based on title length and dependencies
- **⚠️ Error Codes**: Structured error responses (ERR_NO_TASKS, ERR_INVALID_WEIGHTS, etc.)

### Frontend Features
- **Dark Glassmorphism UI**: Modern, stylish interface with gradient effects
- **Real-time Weight Adjustment**: Slider controls with auto-normalization
- **Multiple Views**: Priority List, Eisenhower Matrix, Dependency Graph
- **Score Breakdown Bars**: Visual representation of each scoring factor
- **Responsive Design**: Works on desktop and mobile devices

---

## 📦 Setup Instructions

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Backend Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Start the Django development server:**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000/api/`

### Frontend Setup

1. **Open the frontend:**
   - Simply open `frontend/index.html` in a web browser
   - Or use a local server (e.g., VS Code Live Server extension)

2. **Ensure the Django backend is running** on `http://localhost:8000`

### Running Tests

```bash
cd backend
python manage.py test tasks
```

All 42 tests should pass ✅

---

## 🧠 Algorithm Explanation

### Overview

The priority scoring algorithm uses a **weighted multi-factor approach** where each factor contributes to a final priority score between 0-100. The algorithm includes:

- **Working Day Calculations**: Skips weekends and common holidays
- **Eisenhower Quadrant Classification**: Based on urgency and importance thresholds
- **Complexity Assessment**: Derived from title length and dependency count

### Scoring Formula

```
priority_score = (urgency_score × urgency_weight) + 
                 (importance_score × importance_weight) + 
                 (effort_score × effort_weight) + 
                 (dependency_score × dependency_weight)
```

### Factor Calculations

#### 1. Urgency Score (Working Days Based)
- **Overdue tasks**: 80-100 (more working days overdue = higher)
- **Due today**: 75
- **Due in 1-5 working days**: 50-75 (linear decrease)
- **Due in 6-22 working days**: 20-50 (linear decrease)
- **Due beyond 22 working days**: 10-20 (asymptotic)
- **No due date**: 30 (moderate urgency)

#### 2. Importance Score (1-5 user rating → 0-100 score)
Uses exponential scaling:
```
score = 10 + (importance / 5)^1.5 × 90
```

#### 3. Effort Score (Quick Wins Encouraged)
- **Under 2 hours**: 80-100 ("quick wins")
- **2-8 hours**: 50-80 (manageable)
- **8-40 hours**: 20-50 (significant effort)
- **Beyond 40 hours**: 10-20 (major projects)

#### 4. Dependency Score (Blocking Tasks Prioritized)
- **Blocks 3+ tasks**: 80-100
- **Blocks 1-2 tasks**: 50-80
- **No dependents**: 30 (baseline)

### Strategy Presets

| Strategy | Urgency | Importance | Effort | Dependency |
|----------|---------|------------|--------|------------|
| Smart Balance | 30% | 35% | 15% | 20% |
| Fastest Wins | 15% | 20% | 55% | 10% |
| High Impact | 15% | 60% | 10% | 15% |
| Deadline Driven | 55% | 20% | 10% | 15% |
| Custom | User-defined (must sum to 100%) |

### Eisenhower Matrix Classification

Tasks are automatically classified into quadrants:

| Quadrant | Urgency | Importance | Action |
|----------|---------|------------|--------|
| 🔥 DO FIRST | High (≥60) | High (≥60) | Complete immediately |
| 📅 SCHEDULE | Low (<60) | High (≥60) | Plan for later |
| 👥 DELEGATE | High (≥60) | Low (<60) | Assign to others |
| 🗑️ ELIMINATE | Low (<60) | Low (<60) | Consider removing |

---

## 📡 API Reference

### `GET /api/tasks/`
List all tasks in the database.

### `POST /api/tasks/`
Create a new task.

**Request Body:**
```json
{
    "title": "Fix authentication bug",
    "description": "Login fails on mobile",
    "deadline": "2025-12-01",
    "estimated_hours": 4,
    "importance": 4,
    "dependencies": []
}
```

### `GET /api/strategies/`
Get available sorting strategies.

**Response:**
```json
{
    "strategies": ["smart_balance", "fastest_wins", "high_impact", "deadline_driven", "custom"]
}
```

### `POST /api/suggest/`
Get prioritized task suggestions.

**Request Body:**
```json
{
    "task_ids": [1, 2, 3],
    "strategy": "smart_balance",
    "weights": {
        "urgency": 0.30,
        "importance": 0.35,
        "effort": 0.20,
        "dependencies": 0.15
    }
}
```

**Response:**
```json
{
    "prioritized_tasks": [
        {
            "id": 1,
            "title": "Fix authentication bug",
            "priority_score": 0.82,
            "urgency_score": 0.75,
            "importance_score": 0.80,
            "effort_score": 0.65,
            "dependency_score": 0.40,
            "eisenhower_quadrant": "DO_FIRST",
            "complexity_score": 0.45,
            "explanation": "High priority due to approaching deadline...",
            "is_overdue": false,
            "is_circular": false
        }
    ],
    "total_tasks": 3,
    "strategy": "smart_balance"
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| ERR_NO_TASKS | No tasks provided for analysis |
| ERR_INVALID_TASKS | Task IDs reference non-existent tasks |
| ERR_INVALID_WEIGHTS | Custom weights don't sum to 1.0 |
| ERR_INVALID_STRATEGY | Unknown strategy name |

---

## 🎯 Design Decisions

### 1. Working Days Instead of Calendar Days
**Decision**: Urgency uses working days (Mon-Fri, excluding holidays).

**Rationale**: A task due Monday shouldn't feel more urgent on Friday evening than Thursday. Weekend awareness makes urgency more accurate for professional contexts.

### 2. Customizable Algorithm Weights
**Decision**: Allow users to adjust scoring weights via API and UI.

**Rationale**: Different projects and teams have different priorities. A startup might value "fastest wins," while compliance work is "deadline driven."

### 3. Eisenhower Matrix Integration
**Decision**: Auto-classify tasks using urgency/importance thresholds.

**Rationale**: This well-known framework (used by Dwight Eisenhower) helps users quickly identify what to do, delegate, schedule, or eliminate.

### 4. Human-Readable Explanations
**Decision**: Generate natural language explanations for rankings.

**Rationale**: "Black box" algorithms frustrate users. Explaining *why* a task ranks #1 builds trust and helps users understand the system.

### 5. Mermaid.js for Dependency Visualization
**Decision**: Use Mermaid.js for dependency graphs.

**Rationale**: It's declarative, well-maintained, renders nicely, and doesn't require a complex D3.js setup. Perfect for showing task relationships.

---

## 🧪 Test Coverage

The test suite includes 42 comprehensive tests:

- **Urgency Score Tests**: Working days, overdue, holidays
- **Importance Score Tests**: Range validation, exponential scaling
- **Effort Score Tests**: Quick wins, large projects
- **Circular Dependency Tests**: Simple cycles, complex cycles
- **Strategy Tests**: All five strategies with various configurations
- **API Tests**: Endpoint validation, error handling, edge cases

Run with verbose output:
```bash
cd backend
python manage.py test tasks -v 2
```

---

## 📁 Project Structure

```
task-analyzer/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── task_analyzer/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── tasks/
│       ├── models.py           # Task model with database storage
│       ├── serializers.py      # DRF serializers with validation
│       ├── scoring.py          # Core algorithm (1000+ lines)
│       ├── views.py            # API endpoints
│       ├── urls.py             # URL routing
│       └── tests.py            # 42 unit tests
├── frontend/
│   ├── index.html              # Main UI with views
│   ├── styles.css              # Dark glassmorphism theme
│   └── script.js               # API integration, Mermaid.js
└── README.md
```

---

## ⏱️ Time Breakdown

| Section | Time |
|---------|------|
| Project Setup & Configuration | ~15 min |
| Core Algorithm Design | ~45 min |
| Algorithm Enhancements (v2.0) | ~60 min |
| API Endpoints | ~30 min |
| Frontend Development | ~90 min |
| Unit Tests | ~40 min |
| Documentation | ~30 min |
| **Total** | **~5 hours** |

---

## 🌟 Features Implemented

### Original Requirements ✅
- Multi-factor priority scoring
- Four sorting strategies
- Circular dependency detection
- RESTful API
- Comprehensive tests
- Documentation

### Bonus Enhancements ✅
1. **Customizable Algorithm Weights** - UI sliders + API support
2. **Human-Readable Explanations** - Why each task ranks where it does
3. **Eisenhower Matrix Classification** - Automatic quadrant assignment
4. **Weekend/Holiday Awareness** - Working days calculation
5. **Dependency Graph Visualization** - Mermaid.js integration
6. **Error Codes** - Structured API error handling
7. **Complexity Scoring** - Additional factor for task analysis
8. **Modern UI** - Dark glassmorphism with smooth animations

---

## 📝 License

This project was created as a technical assessment assignment.

---

## 👤 Author

Created for Software Development Intern Position Technical Assessment
#   S m a r t - T a s k - A n a l y z e r  
 