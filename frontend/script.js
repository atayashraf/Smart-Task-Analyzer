// Smart Task Analyzer - Enhanced Frontend JavaScript
// Features: Custom Weights, Eisenhower Matrix, Dependency Graph, Advanced UI
// New: Local Storage, Undo/Redo, Keyboard Shortcuts, Export, Heatmap

const API_BASE_URL = 'http://127.0.0.1:8000/api';

// ============================================
// GLOBAL STATE
// ============================================

let currentTasks = [];
let prioritizedTasks = [];
let timeContext = null;

// Undo/Redo stacks
const MAX_UNDO_STACK = 50;
let undoStack = [];
let redoStack = [];

// Local storage keys
const STORAGE_KEYS = {
    TASKS: 'smart_task_analyzer_tasks',
    WEIGHTS: 'smart_task_analyzer_weights',
    STRATEGY: 'smart_task_analyzer_strategy',
    SETTINGS: 'smart_task_analyzer_settings'
};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initializeMermaid();
    initializeWeightSliders();
    initializeEventListeners();
    initializeKeyboardShortcuts();
    loadFromLocalStorage();
    loadTimeContext();
    loadStrategies();
    loadTasks();
    renderShortcutHints();
});

function initializeMermaid() {
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({
            startOnLoad: false,
            theme: 'base',
            themeVariables: {
                primaryColor: '#fb923c',
                primaryTextColor: '#1c1917',
                primaryBorderColor: '#f97316',
                lineColor: '#f97316',
                secondaryColor: '#fff7ed',
                tertiaryColor: '#fef8f3',
                background: '#fef8f3',
                mainBkg: '#ffffff',
                nodeBkg: '#ffffff',
                clusterBkg: '#fff7ed',
                titleColor: '#1c1917',
                edgeLabelBackground: '#ffffff'
            },
            flowchart: {
                curve: 'basis',
                padding: 15
            }
        });
    }
}

function initializeWeightSliders() {
    const sliders = ['urgency', 'importance', 'effort', 'dependencies'];
    sliders.forEach(name => {
        const slider = document.getElementById(`${name}-weight`);
        const display = document.getElementById(`${name}-value`);
        if (slider && display) {
            slider.addEventListener('input', () => {
                display.textContent = slider.value;
                updateWeightTotal();
            });
        }
    });
}

function initializeEventListeners() {
    // Normalize weights button
    const normalizeBtn = document.getElementById('normalize-weights');
    if (normalizeBtn) {
        normalizeBtn.addEventListener('click', normalizeWeights);
    }

    // Task form submission
    const taskForm = document.getElementById('task-form');
    if (taskForm) {
        taskForm.addEventListener('submit', handleAddTask);
    }

    // Analyze button
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', handleAnalyzeTasks);
    }

    // Strategy change
    const strategySelect = document.getElementById('strategy-select');
    if (strategySelect) {
        strategySelect.addEventListener('change', () => {
            const isCustom = strategySelect.value === 'custom';
            const weightsSection = document.querySelector('.weight-controls');
            if (weightsSection) {
                weightsSection.style.display = isCustom ? 'block' : 'none';
            }
            saveToLocalStorage();
        });
    }

    // Importance slider display
    const importanceSlider = document.getElementById('task-importance');
    const importanceDisplay = document.getElementById('importance-display');
    if (importanceSlider && importanceDisplay) {
        importanceSlider.addEventListener('input', () => {
            importanceDisplay.textContent = importanceSlider.value;
        });
    }

    // View toggle buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            switchView(btn.dataset.view);
        });
    });
}

// ============================================
// WEIGHT MANAGEMENT
// ============================================

function getCustomWeights() {
    return {
        urgency: parseFloat(document.getElementById('urgency-weight')?.value) || 0.35,
        importance: parseFloat(document.getElementById('importance-weight')?.value) || 0.30,
        effort: parseFloat(document.getElementById('effort-weight')?.value) || 0.20,
        dependencies: parseFloat(document.getElementById('dependencies-weight')?.value) || 0.15
    };
}

function updateWeightTotal() {
    const weights = getCustomWeights();
    const total = Object.values(weights).reduce((sum, w) => sum + w, 0);
    const totalDisplay = document.getElementById('weight-total');
    if (totalDisplay) {
        totalDisplay.textContent = total.toFixed(2);
        totalDisplay.style.color = Math.abs(total - 1.0) < 0.01 ? '#10b981' : '#ef4444';
    }
}

function normalizeWeights() {
    const weights = getCustomWeights();
    const total = Object.values(weights).reduce((sum, w) => sum + w, 0);
    
    if (total === 0) return;
    
    const sliders = ['urgency', 'importance', 'effort', 'dependencies'];
    sliders.forEach(name => {
        const slider = document.getElementById(`${name}-weight`);
        const display = document.getElementById(`${name}-value`);
        if (slider && display) {
            const normalizedValue = (weights[name] / total).toFixed(2);
            slider.value = normalizedValue;
            display.textContent = normalizedValue;
        }
    });
    
    updateWeightTotal();
    showNotification('Weights normalized to sum to 1.0', 'success');
}

// ============================================
// API FUNCTIONS
// ============================================

async function loadStrategies() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/strategies/`);
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('strategy-select');
            if (select && data.strategies) {
                // Keep existing options, strategies loaded from API
                console.log('Available strategies:', data.strategies);
            }
        }
    } catch (error) {
        console.log('Using default strategies');
    }
}

function loadTasks() {
    // Tasks are stored locally - no API call needed
    // Already loaded from local storage in loadFromLocalStorage()
    renderTaskList(currentTasks);
    updateTaskCount();
    updateUndoRedoButtons();
}

function handleAddTask(event) {
    event.preventDefault();
    
    // Validate required fields
    const title = document.getElementById('task-title').value.trim();
    const deadline = document.getElementById('task-deadline').value;
    const hours = document.getElementById('task-hours').value;
    
    if (!title) {
        showNotification('Task title is required', 'warning');
        return;
    }
    if (!deadline) {
        showNotification('Deadline is required', 'warning');
        return;
    }
    if (!hours || parseFloat(hours) <= 0) {
        showNotification('Estimated hours must be greater than 0', 'warning');
        return;
    }
    
    // Save state before adding task (for undo)
    saveState('Add task');
    
    // Create new task with local ID
    const newTask = {
        id: Date.now(), // Use timestamp as unique ID
        title: title,
        description: document.getElementById('task-description')?.value || '',
        deadline: deadline,
        estimated_hours: parseFloat(hours),
        importance: parseInt(document.getElementById('task-importance').value) || 3,
        dependencies: parseDependencies(document.getElementById('task-dependencies')?.value || '')
    };
    
    // Add to local tasks array
    currentTasks.push(newTask);
    renderTaskList(currentTasks);
    updateTaskCount();
    
    // Reset form
    event.target.reset();
    // Reset importance slider display
    const importanceDisplay = document.getElementById('importance-display');
    if (importanceDisplay) importanceDisplay.textContent = '3';
    
    // Save to local storage
    saveToLocalStorage();
    
    showNotification('Task added successfully!', 'success');
}

async function handleAnalyzeTasks() {
    if (currentTasks.length === 0) {
        showNotification('No tasks to analyze. Add some tasks first!', 'warning');
        return;
    }
    
    const strategy = document.getElementById('strategy-select').value === 'custom' ? 'smart_balance' : document.getElementById('strategy-select').value;
    
    // Format tasks for API
    const tasksForApi = currentTasks.map(task => ({
        id: task.id,
        title: task.title,
        description: task.description || '',
        due_date: task.deadline,
        estimated_hours: task.estimated_hours,
        importance: task.importance,
        dependencies: task.dependencies || []
    }));
    
    let requestBody = {
        tasks: tasksForApi,
        strategy: strategy
    };
    
    // Add custom weights if using custom strategy
    if (document.getElementById('strategy-select').value === 'custom') {
        const weights = getCustomWeights();
        const total = Object.values(weights).reduce((sum, w) => sum + w, 0);
        
        if (Math.abs(total - 1.0) > 0.01) {
            showNotification('Weights must sum to 1.0. Click "Normalize" to fix.', 'warning');
            return;
        }
        
        requestBody.weights = {
            urgency: weights.urgency,
            importance: weights.importance,
            effort: weights.effort,
            dependency: weights.dependencies
        };
    }
    
    try {
        showLoading(true);
        const response = await fetch(`${API_BASE_URL}/tasks/analyze/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (response.ok) {
            const data = await response.json();
            prioritizedTasks = data.tasks || [];
            renderPrioritizedTasks(prioritizedTasks);
            renderEisenhowerMatrix(prioritizedTasks);
            generateDependencyGraph(prioritizedTasks);
            renderPriorityHeatmap(prioritizedTasks);
            
            // Save to local storage
            saveToLocalStorage();
            
            // Show results section
            document.getElementById('results-section').style.display = 'block';
            document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });
            
            showNotification(`Analysis complete! ${prioritizedTasks.length} tasks prioritized.`, 'success');
        } else {
            const error = await response.json();
            showNotification(`Error: ${error.error || error.detail}`, 'error');
        }
    } catch (error) {
        showNotification('Analysis failed', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    
    // Save state before deleting (for undo)
    saveState('Delete task');
    
    // Remove task from local array
    currentTasks = currentTasks.filter(t => t.id !== taskId);
    renderTaskList(currentTasks);
    updateTaskCount();
    saveToLocalStorage();
    
    // Hide results if no tasks left
    if (currentTasks.length === 0) {
        document.getElementById('results-section').style.display = 'none';
    }
    
    showNotification('Task deleted', 'success');
}

// ============================================
// RENDERING FUNCTIONS
// ============================================

function renderTaskList(tasks) {
    const container = document.getElementById('task-list');
    if (!container) return;
    
    if (tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📝</span>
                <p>No tasks yet. Add your first task above!</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="task-card" data-id="${task.id}">
            <div class="task-header">
                <h3 class="task-title">${escapeHtml(task.title)}</h3>
                <button class="delete-btn" onclick="deleteTask(${task.id})" title="Delete task">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    </svg>
                </button>
            </div>
            ${task.description ? `<p class="task-description">${escapeHtml(task.description)}</p>` : ''}
            <div class="task-meta">
                <span class="meta-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="16" y1="2" x2="16" y2="6"></line>
                        <line x1="8" y1="2" x2="8" y2="6"></line>
                        <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                    ${formatDate(task.deadline)}
                </span>
                <span class="meta-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    ${task.estimated_hours}h
                </span>
                <span class="meta-item importance-badge importance-${task.importance}">
                    ★ ${task.importance}
                </span>
                ${task.dependencies && task.dependencies.length > 0 ? `
                    <span class="meta-item dependencies-badge">
                        🔗 ${task.dependencies.length} dep${task.dependencies.length > 1 ? 's' : ''}
                    </span>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function renderPrioritizedTasks(tasks) {
    const container = document.getElementById('prioritized-list');
    if (!container) return;
    
    if (tasks.length === 0) {
        container.innerHTML = '<p class="empty-state">No tasks analyzed yet.</p>';
        return;
    }
    
    container.innerHTML = tasks.map((task, index) => {
        // Extract scores from score_breakdown (scores are already 0-100)
        const breakdown = task.score_breakdown || {};
        const urgencyScore = breakdown.urgency?.raw_score || 0;
        const importanceScore = breakdown.importance?.raw_score || 0;
        const effortScore = breakdown.effort?.raw_score || 0;
        const dependencyScore = breakdown.dependency?.raw_score || 0;
        
        return `
        <div class="priority-card rank-${index + 1}" data-quadrant="${task.eisenhower_quadrant || 'unknown'}">
            <div class="priority-rank">${index + 1}</div>
            <div class="priority-content">
                <div class="priority-header">
                    <h3 class="task-title">${escapeHtml(task.title)}</h3>
                    <div class="priority-badges">
                        <span class="priority-score">${(task.priority_score || 0).toFixed(1)}</span>
                        ${task.eisenhower_quadrant ? `
                            <span class="quadrant-badge quadrant-${getQuadrantClass(task.eisenhower_quadrant)}">
                                ${getQuadrantLabel(task.eisenhower_quadrant)}
                            </span>
                        ` : ''}
                        ${task.priority_level ? `
                            <span class="priority-level-badge priority-${task.priority_level.toLowerCase()}">
                                ${task.priority_level}
                            </span>
                        ` : ''}
                    </div>
                </div>
                
                <div class="score-breakdown">
                    <div class="score-bar">
                        <span class="score-label">Urgency</span>
                        <div class="bar-container">
                            <div class="bar urgency-bar" style="width: ${Math.min(urgencyScore, 100)}%"></div>
                        </div>
                        <span class="score-value">${urgencyScore.toFixed(0)}%</span>
                    </div>
                    <div class="score-bar">
                        <span class="score-label">Importance</span>
                        <div class="bar-container">
                            <div class="bar importance-bar" style="width: ${Math.min(importanceScore, 100)}%"></div>
                        </div>
                        <span class="score-value">${importanceScore.toFixed(0)}%</span>
                    </div>
                    <div class="score-bar">
                        <span class="score-label">Effort</span>
                        <div class="bar-container">
                            <div class="bar effort-bar" style="width: ${Math.min(effortScore, 100)}%"></div>
                        </div>
                        <span class="score-value">${effortScore.toFixed(0)}%</span>
                    </div>
                    <div class="score-bar">
                        <span class="score-label">Dependencies</span>
                        <div class="bar-container">
                            <div class="bar dependency-bar" style="width: ${Math.min(dependencyScore, 100)}%"></div>
                        </div>
                        <span class="score-value">${dependencyScore.toFixed(0)}%</span>
                    </div>
                </div>
                
                ${task.is_overdue ? '<div class="overdue-warning">⚠️ Overdue!</div>' : ''}
                
                ${task.explanation ? `
                    <div class="explanation-section">
                        <button class="explanation-toggle" onclick="toggleExplanation(this)">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 18l6-6-6-6"/>
                            </svg>
                            Show Reasoning
                        </button>
                        <div class="explanation-content" style="display: none;">
                            <p>${escapeHtml(task.explanation)}</p>
                        </div>
                    </div>
                ` : ''}
            </div>
        </div>
    `}).join('');
}

function renderEisenhowerMatrix(tasks) {
    // Map API quadrant values to HTML element IDs
    const quadrantMapping = {
        'do_now': 'quadrant-do-first',
        'plan': 'quadrant-schedule',
        'delegate': 'quadrant-delegate',
        'eliminate': 'quadrant-eliminate'
    };
    
    const quadrants = {
        'do_now': [],
        'plan': [],
        'delegate': [],
        'eliminate': []
    };
    
    tasks.forEach(task => {
        const quadrant = task.eisenhower_quadrant || 'plan';
        if (quadrants[quadrant]) {
            quadrants[quadrant].push(task);
        }
    });
    
    Object.entries(quadrants).forEach(([quadrant, quadrantTasks]) => {
        const containerId = quadrantMapping[quadrant];
        const container = document.getElementById(containerId);
        if (container) {
            const taskList = container.querySelector('.quadrant-tasks');
            if (taskList) {
                taskList.innerHTML = quadrantTasks.map(task => `
                    <div class="quadrant-task">
                        <span class="task-name">${escapeHtml(task.title)}</span>
                        <span class="task-score">${((task.priority_score || 0) * 100).toFixed(0)}</span>
                    </div>
                `).join('') || '<p class="empty-quadrant">No tasks</p>';
            }
        }
    });
}

function generateDependencyGraph(tasks) {
    const graphContainer = document.getElementById('dependency-graph');
    if (!graphContainer || typeof mermaid === 'undefined') return;
    
    // Check if any tasks have dependencies
    const hasDependencies = tasks.some(t => t.dependencies && t.dependencies.length > 0);
    
    if (!hasDependencies) {
        graphContainer.innerHTML = `
            <div class="no-dependencies">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M8 12h8M12 8v8"/>
                </svg>
                <p>No dependencies defined between tasks</p>
            </div>
        `;
        return;
    }
    
    // Build Mermaid graph syntax
    let graphDef = 'graph TD\n';
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    
    tasks.forEach(task => {
        const nodeId = `task_${task.id}`;
        const label = task.title.length > 20 ? task.title.substring(0, 20) + '...' : task.title;
        const score = (task.priority_score * 100).toFixed(0);
        graphDef += `    ${nodeId}["${escapeForMermaid(label)}<br/>Score: ${score}"]\n`;
        
        // Style based on Eisenhower quadrant
        const quadrant = task.eisenhower_quadrant || 'SCHEDULE';
        graphDef += `    style ${nodeId} fill:${getQuadrantColor(quadrant)},stroke:#667eea\n`;
    });
    
    // Add dependency edges
    tasks.forEach(task => {
        if (task.dependencies && task.dependencies.length > 0) {
            task.dependencies.forEach(depId => {
                if (taskMap.has(depId)) {
                    graphDef += `    task_${depId} --> task_${task.id}\n`;
                }
            });
        }
    });
    
    // Render graph
    graphContainer.innerHTML = `<div class="mermaid">${graphDef}</div>`;
    
    try {
        mermaid.init(undefined, graphContainer.querySelector('.mermaid'));
    } catch (error) {
        console.error('Mermaid rendering error:', error);
        graphContainer.innerHTML = `
            <div class="graph-error">
                <p>Unable to render dependency graph</p>
            </div>
        `;
    }
}

// ============================================
// VIEW SWITCHING
// ============================================

function switchView(viewName) {
    const views = ['list-view', 'matrix-view', 'graph-view'];
    views.forEach(view => {
        const element = document.getElementById(view);
        if (element) {
            element.style.display = view === `${viewName}-view` ? 'block' : 'none';
        }
    });
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function toggleExplanation(button) {
    const content = button.nextElementSibling;
    const isHidden = content.style.display === 'none';
    content.style.display = isHidden ? 'block' : 'none';
    button.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" 
             style="transform: rotate(${isHidden ? '90' : '0'}deg); transition: transform 0.2s;">
            <path d="M9 18l6-6-6-6"/>
        </svg>
        ${isHidden ? 'Hide' : 'Show'} Reasoning
    `;
}

function parseDependencies(input) {
    if (!input.trim()) return [];
    return input.split(',')
        .map(id => parseInt(id.trim()))
        .filter(id => !isNaN(id));
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.ceil((date - now) / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays <= 7) return `${diffDays} days`;
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeForMermaid(text) {
    return text.replace(/"/g, "'").replace(/[<>]/g, '');
}

function getQuadrantClass(quadrant) {
    const classes = {
        'do_now': 'urgent-important',
        'plan': 'not-urgent-important',
        'delegate': 'urgent-not-important',
        'eliminate': 'not-urgent-not-important'
    };
    return classes[quadrant] || 'unknown';
}

function getQuadrantLabel(quadrant) {
    const labels = {
        'do_now': '🔥 Do Now',
        'plan': '📅 Plan',
        'delegate': '👥 Delegate',
        'eliminate': '🗑️ Eliminate'
    };
    return labels[quadrant] || quadrant;
}

function getQuadrantColor(quadrant) {
    const colors = {
        'do_now': '#ef4444',
        'plan': '#3b82f6',
        'delegate': '#f59e0b',
        'eliminate': '#6b7280'
    };
    return colors[quadrant] || '#667eea';
}

function getComplexityClass(score) {
    if (score >= 0.7) return 'high';
    if (score >= 0.4) return 'medium';
    return 'low';
}

function getComplexityLabel(score) {
    if (score >= 0.7) return '🔴 Complex';
    if (score >= 0.4) return '🟡 Moderate';
    return '🟢 Simple';
}

function updateTaskCount() {
    const counter = document.getElementById('task-count');
    if (counter) {
        counter.textContent = currentTasks.length;
    }
}

function showLoading(show) {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
        loader.style.display = show ? 'flex' : 'none';
    }
}

function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${getNotificationIcon(type)}</span>
        <span class="notification-message">${escapeHtml(message)}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => notification.classList.add('show'), 10);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    return icons[type] || icons.info;
}

// Make deleteTask available globally
window.deleteTask = deleteTask;
window.toggleExplanation = toggleExplanation;

// ============================================
// LOCAL STORAGE SYNC
// ============================================

function saveToLocalStorage() {
    try {
        // Save tasks
        localStorage.setItem(STORAGE_KEYS.TASKS, JSON.stringify(currentTasks));
        
        // Save weights
        const weights = getCustomWeights();
        localStorage.setItem(STORAGE_KEYS.WEIGHTS, JSON.stringify(weights));
        
        // Save strategy
        const strategy = document.getElementById('strategy-select')?.value || 'smart_balance';
        localStorage.setItem(STORAGE_KEYS.STRATEGY, strategy);
        
        console.log('Saved to local storage');
    } catch (error) {
        console.error('Failed to save to local storage:', error);
    }
}

function loadFromLocalStorage() {
    try {
        // Load tasks (will be overwritten by API if available)
        const savedTasks = localStorage.getItem(STORAGE_KEYS.TASKS);
        if (savedTasks) {
            const parsed = JSON.parse(savedTasks);
            if (Array.isArray(parsed)) {
                currentTasks = parsed;
                renderTaskList(currentTasks);
                updateTaskCount();
            }
        }
        
        // Load weights
        const savedWeights = localStorage.getItem(STORAGE_KEYS.WEIGHTS);
        if (savedWeights) {
            const weights = JSON.parse(savedWeights);
            applyWeights(weights);
        }
        
        // Load strategy
        const savedStrategy = localStorage.getItem(STORAGE_KEYS.STRATEGY);
        if (savedStrategy) {
            const select = document.getElementById('strategy-select');
            if (select) {
                select.value = savedStrategy;
                // Trigger change event to show/hide weight controls
                select.dispatchEvent(new Event('change'));
            }
        }
        
        console.log('Loaded from local storage');
    } catch (error) {
        console.error('Failed to load from local storage:', error);
    }
}

function applyWeights(weights) {
    const sliders = ['urgency', 'importance', 'effort', 'dependencies'];
    sliders.forEach(name => {
        const slider = document.getElementById(`${name}-weight`);
        const display = document.getElementById(`${name}-value`);
        if (slider && display && weights[name] !== undefined) {
            slider.value = weights[name];
            display.textContent = weights[name].toFixed(2);
        }
    });
    updateWeightTotal();
}

function clearLocalStorage() {
    Object.values(STORAGE_KEYS).forEach(key => localStorage.removeItem(key));
    showNotification('Local storage cleared', 'info');
}

// ============================================
// UNDO/REDO SYSTEM
// ============================================

function saveState(action) {
    const state = {
        action,
        timestamp: Date.now(),
        tasks: JSON.parse(JSON.stringify(currentTasks)),
        weights: getCustomWeights(),
        strategy: document.getElementById('strategy-select')?.value || 'smart_balance'
    };
    
    undoStack.push(state);
    if (undoStack.length > MAX_UNDO_STACK) {
        undoStack.shift();
    }
    
    // Clear redo stack on new action
    redoStack = [];
    
    updateUndoRedoButtons();
}

function undo() {
    if (undoStack.length === 0) {
        showNotification('Nothing to undo', 'info');
        return;
    }
    
    // Save current state to redo stack
    const currentState = {
        action: 'undo',
        timestamp: Date.now(),
        tasks: JSON.parse(JSON.stringify(currentTasks)),
        weights: getCustomWeights(),
        strategy: document.getElementById('strategy-select')?.value || 'smart_balance'
    };
    redoStack.push(currentState);
    
    // Restore previous state
    const previousState = undoStack.pop();
    restoreState(previousState);
    
    showNotification(`Undone: ${previousState.action}`, 'info');
    updateUndoRedoButtons();
}

function redo() {
    if (redoStack.length === 0) {
        showNotification('Nothing to redo', 'info');
        return;
    }
    
    // Save current state to undo stack
    const currentState = {
        action: 'redo',
        timestamp: Date.now(),
        tasks: JSON.parse(JSON.stringify(currentTasks)),
        weights: getCustomWeights(),
        strategy: document.getElementById('strategy-select')?.value || 'smart_balance'
    };
    undoStack.push(currentState);
    
    // Restore redo state
    const nextState = redoStack.pop();
    restoreState(nextState);
    
    showNotification(`Redone: ${nextState.action}`, 'info');
    updateUndoRedoButtons();
}

function restoreState(state) {
    currentTasks = state.tasks;
    renderTaskList(currentTasks);
    updateTaskCount();
    applyWeights(state.weights);
    
    const select = document.getElementById('strategy-select');
    if (select) {
        select.value = state.strategy;
        select.dispatchEvent(new Event('change'));
    }
    
    saveToLocalStorage();
}

function updateUndoRedoButtons() {
    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');
    
    if (undoBtn) {
        undoBtn.disabled = undoStack.length === 0;
        undoBtn.title = undoStack.length > 0 
            ? `Undo: ${undoStack[undoStack.length - 1]?.action || 'last action'} (Ctrl+Z)` 
            : 'Nothing to undo (Ctrl+Z)';
    }
    
    if (redoBtn) {
        redoBtn.disabled = redoStack.length === 0;
        redoBtn.title = redoStack.length > 0 
            ? `Redo: ${redoStack[redoStack.length - 1]?.action || 'last action'} (Ctrl+Y)` 
            : 'Nothing to redo (Ctrl+Y)';
    }
}

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', handleKeyboardShortcut);
}

function handleKeyboardShortcut(event) {
    const target = event.target;
    const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT';
    
    // Ctrl/Cmd key combinations
    if (event.ctrlKey || event.metaKey) {
        switch (event.key.toLowerCase()) {
            case 'z':
                if (event.shiftKey) {
                    event.preventDefault();
                    redo();
                } else {
                    event.preventDefault();
                    undo();
                }
                break;
            case 'y':
                event.preventDefault();
                redo();
                break;
            case 'enter':
                event.preventDefault();
                handleAnalyzeTasks();
                break;
            case 'n':
                event.preventDefault();
                focusNewTask();
                break;
            case 's':
                event.preventDefault();
                saveToLocalStorage();
                showNotification('Saved to local storage', 'success');
                break;
            case 'e':
                event.preventDefault();
                showExportModal();
                break;
        }
    }
    
    // Non-Ctrl shortcuts (only when not in input)
    if (!isInput) {
        switch (event.key) {
            case 'Escape':
                closeAllModals();
                break;
            case '?':
                event.preventDefault();
                showShortcutsHelp();
                break;
            case '1':
                switchView('list');
                break;
            case '2':
                switchView('matrix');
                break;
            case '3':
                switchView('graph');
                break;
        }
    }
}

function focusNewTask() {
    const titleInput = document.getElementById('task-title');
    if (titleInput) {
        titleInput.focus();
        titleInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function renderShortcutHints() {
    const shortcutsContainer = document.getElementById('keyboard-shortcuts');
    if (shortcutsContainer) {
        shortcutsContainer.innerHTML = `
            <div class="shortcuts-toggle" onclick="toggleShortcutsPanel()">
                <span>⌨️ Shortcuts</span>
            </div>
            <div class="shortcuts-panel" id="shortcuts-panel" style="display: none;">
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> Analyze</div>
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>N</kbd> New task</div>
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>Z</kbd> Undo</div>
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>Y</kbd> Redo</div>
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>S</kbd> Save</div>
                <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>E</kbd> Export</div>
                <div class="shortcut-item"><kbd>1</kbd> List view</div>
                <div class="shortcut-item"><kbd>2</kbd> Matrix view</div>
                <div class="shortcut-item"><kbd>3</kbd> Graph view</div>
                <div class="shortcut-item"><kbd>?</kbd> Help</div>
            </div>
        `;
    }
}

function toggleShortcutsPanel() {
    const panel = document.getElementById('shortcuts-panel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

function showShortcutsHelp() {
    const panel = document.getElementById('shortcuts-panel');
    if (panel) {
        panel.style.display = 'block';
    }
}

// ============================================
// EXPORT FUNCTIONALITY
// ============================================

function showExportModal() {
    const modal = document.getElementById('export-modal') || createExportModal();
    modal.style.display = 'flex';
}

function createExportModal() {
    const modal = document.createElement('div');
    modal.id = 'export-modal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>📤 Export Tasks</h3>
                <button class="modal-close" onclick="closeExportModal()">×</button>
            </div>
            <div class="modal-body">
                <p>Choose export format:</p>
                <div class="export-options">
                    <button class="export-btn" onclick="exportAsJSON()">
                        <span class="export-icon">📄</span>
                        <span>JSON</span>
                    </button>
                    <button class="export-btn" onclick="exportAsCSV()">
                        <span class="export-icon">📊</span>
                        <span>CSV</span>
                    </button>
                    <button class="export-btn" onclick="copyToClipboard()">
                        <span class="export-icon">📋</span>
                        <span>Copy</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    return modal;
}

function closeExportModal() {
    const modal = document.getElementById('export-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
}

async function exportAsJSON() {
    if (currentTasks.length === 0) {
        showNotification('No tasks to export', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/export/json/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tasks: currentTasks,
                strategy: document.getElementById('strategy-select')?.value || 'smart_balance'
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            downloadFile(JSON.stringify(data, null, 2), 'task_analysis.json', 'application/json');
            showNotification('Exported as JSON', 'success');
            closeExportModal();
        } else {
            // Fallback to local export
            exportLocalJSON();
        }
    } catch (error) {
        // Fallback to local export
        exportLocalJSON();
    }
}

function exportLocalJSON() {
    const exportData = {
        exported_at: new Date().toISOString(),
        total_tasks: currentTasks.length,
        tasks: currentTasks,
        prioritized_tasks: prioritizedTasks
    };
    downloadFile(JSON.stringify(exportData, null, 2), 'task_analysis.json', 'application/json');
    showNotification('Exported as JSON (local)', 'success');
    closeExportModal();
}

async function exportAsCSV() {
    if (currentTasks.length === 0) {
        showNotification('No tasks to export', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/export/csv/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tasks: currentTasks,
                strategy: document.getElementById('strategy-select')?.value || 'smart_balance'
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'task_analysis.csv';
            a.click();
            URL.revokeObjectURL(url);
            showNotification('Exported as CSV', 'success');
            closeExportModal();
        } else {
            // Fallback to local export
            exportLocalCSV();
        }
    } catch (error) {
        // Fallback to local export
        exportLocalCSV();
    }
}

function exportLocalCSV() {
    const headers = ['Title', 'Description', 'Deadline', 'Estimated Hours', 'Importance', 'Dependencies'];
    const rows = currentTasks.map(task => [
        `"${(task.title || '').replace(/"/g, '""')}"`,
        `"${(task.description || '').replace(/"/g, '""')}"`,
        task.deadline || '',
        task.estimated_hours || '',
        task.importance || '',
        (task.dependencies || []).join(';')
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    downloadFile(csv, 'task_analysis.csv', 'text/csv');
    showNotification('Exported as CSV (local)', 'success');
    closeExportModal();
}

function copyToClipboard() {
    if (currentTasks.length === 0) {
        showNotification('No tasks to copy', 'warning');
        return;
    }
    
    const text = currentTasks.map((task, i) => 
        `${i + 1}. ${task.title}${task.deadline ? ` (Due: ${task.deadline})` : ''} - ${task.estimated_hours}h`
    ).join('\n');
    
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
        closeExportModal();
    }).catch(() => {
        showNotification('Failed to copy', 'error');
    });
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// ============================================
// TIME CONTEXT & FATIGUE
// ============================================

async function loadTimeContext() {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/time-context/`);
        if (response.ok) {
            timeContext = await response.json();
            renderTimeContext(timeContext);
        }
    } catch (error) {
        console.log('Time context not available');
    }
}

function renderTimeContext(context) {
    const container = document.getElementById('time-context');
    if (!container || !context) return;
    
    container.innerHTML = `
        <div class="time-context-card">
            <div class="time-header">
                <span class="time-icon">🕐</span>
                <span class="time-period">${context.time_context.replace('_', ' ').toUpperCase()}</span>
            </div>
            <p class="time-message">${context.message}</p>
            <div class="time-stats">
                <span class="stat">
                    <strong>Suggested max:</strong> ${context.suggested_max_hours}h
                </span>
                <span class="stat">
                    <strong>Focus level:</strong> ${context.focus_level}
                </span>
            </div>
        </div>
    `;
    container.style.display = 'block';
}

// ============================================
// PRIORITY HEATMAP
// ============================================

function renderPriorityHeatmap(tasks) {
    const container = document.getElementById('priority-heatmap');
    if (!container || tasks.length === 0) return;
    
    // Group tasks by urgency and importance for heatmap
    const grid = [];
    const maxScore = Math.max(...tasks.map(t => t.priority_score || 0));
    
    container.innerHTML = `
        <div class="heatmap-title">Priority Heatmap</div>
        <div class="heatmap-grid">
            ${tasks.slice(0, 20).map(task => {
                const intensity = (task.priority_score || 0) / Math.max(maxScore, 1);
                const hue = 120 - (intensity * 120); // Green to red
                return `
                    <div class="heatmap-cell" 
                         style="background-color: hsla(${hue}, 70%, 50%, ${0.3 + intensity * 0.7})"
                         title="${escapeHtml(task.title)}: ${((task.priority_score || 0) * 100).toFixed(0)}%">
                        <span class="heatmap-label">${task.title.substring(0, 10)}${task.title.length > 10 ? '...' : ''}</span>
                    </div>
                `;
            }).join('')}
        </div>
        <div class="heatmap-legend">
            <span class="legend-low">Low Priority</span>
            <div class="legend-gradient"></div>
            <span class="legend-high">High Priority</span>
        </div>
    `;
    container.style.display = 'block';
}

// ============================================
// AUTO-DETECT PATTERNS
// ============================================

async function detectTaskPatterns(title, description = '') {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/detect-patterns/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description })
        });
        
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.log('Pattern detection not available');
    }
    return null;
}

// Add pattern detection to task form
function initializePatternDetection() {
    const titleInput = document.getElementById('task-title');
    const descInput = document.getElementById('task-description');
    const importanceSlider = document.getElementById('task-importance');
    const hoursInput = document.getElementById('task-hours');
    
    if (!titleInput) return;
    
    let debounceTimer;
    
    const detectPatterns = async () => {
        const title = titleInput.value;
        const description = descInput?.value || '';
        
        if (title.length < 3) return;
        
        const result = await detectTaskPatterns(title, description);
        if (result && result.patterns) {
            const patterns = result.patterns;
            
            // Show suggestions
            if (patterns.suggested_importance && patterns.importance_confidence > 0.3) {
                showPatternSuggestion(
                    'importance',
                    `Suggested importance: ${patterns.suggested_importance} (${(patterns.importance_confidence * 100).toFixed(0)}% confident)`,
                    () => {
                        if (importanceSlider) importanceSlider.value = patterns.suggested_importance;
                    }
                );
            }
            
            if (patterns.suggested_effort_hours && patterns.effort_confidence > 0.3) {
                showPatternSuggestion(
                    'effort',
                    `Suggested hours: ${patterns.suggested_effort_hours}h (${(patterns.effort_confidence * 100).toFixed(0)}% confident)`,
                    () => {
                        if (hoursInput) hoursInput.value = patterns.suggested_effort_hours;
                    }
                );
            }
        }
    };
    
    titleInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(detectPatterns, 500);
    });
    
    if (descInput) {
        descInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(detectPatterns, 500);
        });
    }
}

function showPatternSuggestion(type, message, applyFn) {
    const existingSuggestion = document.querySelector(`.pattern-suggestion.${type}`);
    if (existingSuggestion) existingSuggestion.remove();
    
    const suggestion = document.createElement('div');
    suggestion.className = `pattern-suggestion ${type}`;
    suggestion.innerHTML = `
        <span class="suggestion-icon">💡</span>
        <span class="suggestion-text">${message}</span>
        <button class="suggestion-apply" onclick="this.parentElement.applyFn(); this.parentElement.remove();">Apply</button>
        <button class="suggestion-dismiss" onclick="this.parentElement.remove();">×</button>
    `;
    suggestion.applyFn = applyFn;
    
    const form = document.getElementById('task-form');
    if (form) {
        form.appendChild(suggestion);
        setTimeout(() => suggestion.remove(), 10000);
    }
}

// Make functions available globally
window.undo = undo;
window.redo = redo;
window.exportAsJSON = exportAsJSON;
window.exportAsCSV = exportAsCSV;
window.copyToClipboard = copyToClipboard;
window.closeExportModal = closeExportModal;
window.toggleShortcutsPanel = toggleShortcutsPanel;
window.showExportModal = showExportModal;