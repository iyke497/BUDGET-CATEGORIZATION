// fmoh2024/static/js/compliance/dashboard.js (updated - removed chart code)

// Compliance Dashboard specific JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DataTable with pagination
    const table = $('#agencyTable').DataTable({
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        order: [[5, 'desc']], // Sort by compliance percentage descending
        columnDefs: [
            { orderable: false, targets: [7] }, // Disable sorting on Actions column
            { width: '25%', targets: 0 }, // Agency column wider
            { width: '15%', targets: 1 }, // Ministry column
            { className: 'text-center', targets: [3, 4, 5, 6, 7] } // Center align numeric columns
        ],
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search agencies or ministries...",
            lengthMenu: "Show _MENU_ agencies",
            info: "Showing _START_ to _END_ of _TOTAL_ agencies",
            infoEmpty: "Showing 0 agencies",
            infoFiltered: "(filtered from _MAX_ total)",
            paginate: {
                first: "First",
                last: "Last",
                next: "Next",
                previous: "Previous"
            }
        },
        dom: '<"datatable-top"lf>rt<"datatable-bottom"ip>',
        drawCallback: function() {
            updateBadgeCount();
        }
    });

    // Update badge count based on filtered results
    function updateBadgeCount() {
        const info = table.page.info();
        const badge = document.querySelector('.badge');
        if (badge) {
            badge.textContent = `${info.recordsDisplay} agencies`;
        }
    }

    // Initialize filters
    const fiscalYearSelect = document.getElementById('fiscalYear');
    const statusFilter = document.getElementById('statusFilter');
    const exportBtn = document.getElementById('exportData');
    
    // Handle fiscal year change - reload page with new parameter
    if (fiscalYearSelect) {
        fiscalYearSelect.addEventListener('change', (e) => {
            const url = new URL(window.location.href);
            url.searchParams.set('fiscal_year', e.target.value);
            window.location.href = url.toString();
        });
    }
    
    // Status filter - use DataTables column search
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            const status = e.target.value;
            if (status) {
                // Search in the Status column (index 6)
                table.column(6).search(status).draw();
            } else {
                table.column(6).search('').draw();
            }
        });
    }
    
    // Export to CSV - export only filtered/visible data
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            const fiscalYear = fiscalYearSelect?.value || '2024';
            exportTableToCSV(`compliance-data-${fiscalYear}.csv`);
        });
    }

    function exportTableToCSV(filename) {
        const csv = [];
        const rows = table.rows({ search: 'applied' }).nodes();
        
        // Headers
        const headers = [];
        $('#agencyTable thead th').each(function() {
            if ($(this).text() !== 'Actions') {
                headers.push($(this).text());
            }
        });
        csv.push(headers.join(','));
        
        // Data rows
        $(rows).each(function() {
            const row = [];
            $(this).find('td').each(function(index) {
                if (index < 7) { // Exclude Actions column
                    let text = $(this).text().trim();
                    // Clean up multi-line text and whitespace
                    text = text.replace(/\n/g, ' ').replace(/\s+/g, ' ');
                    // Escape commas and quotes for CSV
                    if (text.includes(',') || text.includes('"')) {
                        text = `"${text.replace(/"/g, '""')}"`;
                    }
                    row.push(text);
                }
            });
            csv.push(row.join(','));
        });
        
        // Create and download CSV file
        const csvContent = csv.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
    
    // Make table rows clickable for quick navigation
    $('#agencyTable tbody').on('click', 'tr', function(e) {
        // Don't navigate if clicking on the Details button
        if ($(e.target).closest('a').length) return;
        
        const detailsLink = $(this).find('a.btn-primary').attr('href');
        if (detailsLink) {
            window.location.href = detailsLink;
        }
    });

    // Add cursor pointer to indicate rows are clickable
    $('#agencyTable tbody tr').css('cursor', 'pointer');
});