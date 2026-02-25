// fmoh2024/static/js/main/home.js - Updated to use correct fields

// Home page charts
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardCharts();
});

// Load all dashboard charts from consolidated endpoint
async function loadDashboardCharts() {
    try {
        const response = await fetch('/compliance/api/dashboard-stats');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Load all charts with the data
        renderComplianceChart(data.compliance_distribution);
        renderIntermediateOutcomeChart(data.intermediate_outcome_distribution);
        renderCategoryChart(data.category_distribution);
        renderHealthcareServiceChart(data.healthcare_service_distribution);
        
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        
        // Show errors for all charts
        showChartError('complianceChart', 'Unable to load compliance data');
        showChartError('intermediateOutcomeChart', 'Unable to load outcome data');
        showChartError('categoryChart', 'Unable to load category data');
        showChartError('healthcareServiceChart', 'Unable to load service data');
    }
}

// Render compliance distribution chart
function renderComplianceChart(data) {
    const ctx = document.getElementById('complianceChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: data.colors || [
                    '#4baa73', '#f39c12', '#e67e22', '#b91c1c'
                ],
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'IBM Plex Sans', size: 12 },
                        padding: 10,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} agencies (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Render intermediate outcome distribution chart
function renderIntermediateOutcomeChart(data) {
    const ctx = document.getElementById('intermediateOutcomeChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: generateColors(data.labels.length),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                title: {
                    display: false,
                    text: data.title || 'Intermediate Outcomes',
                    font: { family: 'IBM Plex Sans', size: 14, weight: '600' },
                    padding: { bottom: 20 }
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'IBM Plex Sans', size: 11 },
                        padding: 8,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} projects (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Render category distribution chart
function renderCategoryChart(data) {
    const ctx = document.getElementById('categoryChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: generateColors(data.labels.length),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                title: {
                    display: false,
                    text: data.title || 'Budget Categories',
                    font: { family: 'IBM Plex Sans', size: 14, weight: '600' },
                    padding: { bottom: 20 }
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'IBM Plex Sans', size: 11 },
                        padding: 8,
                        usePointStyle: true,
                        maxWidth: 150
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} projects (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Render healthcare service distribution chart
function renderHealthcareServiceChart(data) {
    const ctx = document.getElementById('healthcareServiceChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: generateColors(data.labels.length),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                title: {
                    display: true,
                    text: data.title || 'Healthcare Services',
                    font: { family: 'IBM Plex Sans', size: 14, weight: '600' },
                    padding: { bottom: 20 }
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'IBM Plex Sans', size: 11 },
                        padding: 8,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} projects (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Helper function to show chart error
function showChartError(chartId, message) {
    const canvas = document.getElementById(chartId);
    if (!canvas) return;
    
    const container = canvas.parentElement;
    container.innerHTML = `<div class="chart-error">⚠️ ${message}</div>`;
}

// Helper function to generate colors for charts
function generateColors(count) {
    const baseColors = [
        '#4baa73', '#3498db', '#9b59b6', '#e67e22', '#e74c3c',
        '#f1c40f', '#1abc9c', '#34495e', '#7f8c8d', '#2c3e50',
        '#27ae60', '#2980b9', '#8e44ad', '#d35400', '#c0392b'
    ];
    
    return baseColors.slice(0, count);
}