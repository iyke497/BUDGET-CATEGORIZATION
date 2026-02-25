// fmoh2024/static/js/compliance/agency.js

document.addEventListener('DOMContentLoaded', () => {
    // Filter projects
    const filterInput = document.getElementById('filterProjects');
    if (filterInput) {
        filterInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#projectTableBody tr');
            
            rows.forEach(row => {
                const projectName = row.dataset.projectName || '';
                const projectCode = row.dataset.projectCode || '';
                
                if (projectName.includes(searchTerm) || projectCode.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Update count
            const visibleCount = document.querySelectorAll('#projectTableBody tr:not([style*="display: none"])').length;
            document.getElementById('visibleCount')?.textContent = visibleCount;
        });
    }
    
    // Toggle project details
    document.querySelectorAll('.project-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.closest('a, button')) {
                item.classList.toggle('expanded');
            }
        });
    });
    
    // Export project list
    const exportBtn = document.getElementById('exportProjects');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            const projects = [];
            document.querySelectorAll('#projectTableBody tr').forEach(row => {
                if (row.style.display !== 'none') {
                    projects.push({
                        code: row.querySelector('.project-code')?.textContent,
                        name: row.cells[1]?.textContent,
                        appropriation: row.cells[2]?.textContent,
                        status: row.cells[3]?.textContent,
                        categorized: row.classList.contains('categorized')
                    });
                }
            });
            
            // Generate CSV
            const csv = ['Code,Project Name,Appropriation,Status,Categorized',
                ...projects.map(p => `${p.code},"${p.name}",${p.appropriation},${p.status},${p.categorized}`)
            ].join('\n');
            
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `projects-{{ details.agency.agency_code }}-${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
        });
    }
});