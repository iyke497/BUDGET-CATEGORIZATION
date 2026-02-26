// fmoh2024/static/js/projects/index.js

/**
 * Projects page initialization and DataTable setup
 */
(function() {
    'use strict';

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        initializeProjectsTable();
    });

    function initializeProjectsTable() {
        // Check if jQuery and DataTables are available
        if (typeof jQuery === 'undefined' || typeof jQuery.fn.DataTable === 'undefined') {
            console.error('jQuery or DataTables not loaded');
            return;
        }

        const $ = jQuery;

        // Get fiscal year from data attribute or URL
        const fiscalYear = document.querySelector('.fiscal-year-badge')?.textContent.replace('FY ', '') || '2024';

        // Initialize DataTable
        const table = $('#projects-table').DataTable({
            processing: true,
            serverSide: true,
            ajax: {
                url: '/projects/api',  // Using absolute path to avoid template issues
                data: function(d) {
                    d.fiscal_year = fiscalYear;
                    
                    // Add filter values from our custom filter bar
                    d.columns[0].search.value = $('#codeFilter').val();      // code
                    d.columns[1].search.value = $('#projectFilter').val();   // project_name
                    d.columns[2].search.value = $('#agencyFilter').val();    // agency
                    d.columns[3].search.value = $('#serviceFilter').val();   // health_care_service
                    d.columns[4].search.value = $('#outcomeFilter').val();   // intermediate_outcome
                    d.columns[5].search.value = $('#categoryFilter').val();  // category
                    // Column 6 (service_detail) is handled by the server
                },
                error: function(xhr, error, code) {
                    console.error('DataTables Ajax error:', error, code);
                    console.error('Response:', xhr.responseText);
                }
            },
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
            order: [[1, 'asc']], // Sort by project name by default
            columns: [
                { 
                    data: 'code',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            let html = '<div class="code-cell">' + (data || '—') + '</div>';
                            if (row && row.appropriation) {
                                const amount = parseFloat(row.appropriation).toLocaleString('en-NG', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
                                html += '<div class="appropriation-amount">₦' + amount + '</div>';
                            }
                            return html;
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'project_name',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            return data || '—';
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'agency',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            return data || '—';
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'health_care_service',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            if (!data) return '—';
                            let className = 'service-badge';
                            const dataLower = data.toLowerCase();
                            if (dataLower.includes('primary')) className += ' primary';
                            else if (dataLower.includes('secondary')) className += ' secondary';
                            else if (dataLower.includes('tertiary')) className += ' tertiary';
                            return '<span class="' + className + '">' + data.replace(/_/g, ' ') + '</span>';
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'intermediate_outcome',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            if (!data) return '—';
                            const className = 'outcome-badge ' + data.toLowerCase();
                            const displayText = data.replace(/_/g, ' ');
                            return '<span class="' + className + '">' + displayText + '</span>';
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'category',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            if (!data) return '—';
                            const className = 'category-badge ' + data.toLowerCase();
                            const displayText = data.replace(/_/g, ' ');
                            return '<span class="' + className + '">' + displayText + '</span>';
                        }
                        return data || '';
                    }
                },
                { 
                    data: 'service_detail',
                    render: function(data, type, row) {
                        if (type === 'display') {
                            if (!data) return '—';
                            let className = 'service-badge';
                            if (row && row.health_care_service) {
                                const service = row.health_care_service.toLowerCase();
                                if (service.includes('primary')) className += ' primary';
                                else if (service.includes('secondary')) className += ' secondary';
                                else if (service.includes('tertiary')) className += ' tertiary';
                            }
                            const displayText = data.replace(/_/g, ' ');
                            return '<span class="' + className + '">' + displayText + '</span>';
                        }
                        return data || '';
                    }
                }
            ],
            language: {
                processing: '<div class="loading"></div> Loading projects...',
                emptyTable: 'No projects found',
                zeroRecords: 'No matching projects found',
                info: 'Showing _START_ to _END_ of _TOTAL_ projects',
                infoEmpty: 'Showing 0 to 0 of 0 projects',
                infoFiltered: '(filtered from _MAX_ total projects)',
                lengthMenu: 'Show _MENU_ projects',
                search: 'Search all columns:',
                paginate: {
                    first: '«',
                    last: '»',
                    next: '›',
                    previous: '‹'
                }
            },
            drawCallback: function(settings) {
                // Update project count
                const info = this.api().page.info();
                $('#project-count').text(info.recordsTotal + ' projects');
            }
        });

        // Apply filters when filter bar inputs change
        $('#serviceFilter, #outcomeFilter, #categoryFilter').on('change', function() {
            table.ajax.reload();
        });

        // Debounced input handlers for text filters
        let timeout = null;
        $('#codeFilter, #projectFilter, #agencyFilter').on('keyup', function() {
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                table.ajax.reload();
            }, 400);
        });

        // Clear all filters
        $('#clearFilters').on('click', function() {
            $('#serviceFilter').val('');
            $('#outcomeFilter').val('');
            $('#categoryFilter').val('');
            $('#codeFilter').val('');
            $('#projectFilter').val('');
            $('#agencyFilter').val('');
            table.ajax.reload();
        });

        // Handle global search
        $('.dataTables_filter input').on('keyup', function() {
            table.search(this.value).draw();
        });
    }
})();