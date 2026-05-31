// static/script.js

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Receipt Logic: Auto Print
    // لو إحنا في صفحة الفاتورة، هيتم الطباعة أوتوماتيك
    if (document.querySelector('.receipt-container')) {
        setTimeout(function() {
            window.print();
        }, 500);
    }

    // 2. Cashier Mode Initialization
    const clientTypeInput = document.getElementById('client_type');
    if (clientTypeInput) {
        setMode('new'); 
    }

    // 3. Init Charts (فقط إذا كان عنصر الـ Chart موجود في الصفحة)
    initBarberChart();
});

// وظيفة تبديل حالة العميل (جديد أو قديم) في صفحة الكاشير
window.setMode = function(mode) {
    const typeInput = document.getElementById('client_type');
    if (!typeInput) return;

    typeInput.value = mode;
    const nameDiv = document.getElementById('name_div');
    const searchBtn = document.getElementById('search_btn');
    const nameInput = document.getElementById('name_input');
    const historyDiv = document.getElementById('client_history');
    const btnNew = document.getElementById('btn-new');
    const btnOld = document.getElementById('btn-old');
    
    if (mode === 'new') {
        // تنسيق زر الجديد
        btnNew.style.backgroundColor = '#d4af37';
        btnNew.style.color = '#000';
        btnNew.style.fontWeight = '700';
        // تنسيق زر القديم
        btnOld.style.backgroundColor = 'transparent';
        btnOld.style.color = 'white';
        btnOld.style.fontWeight = 'normal';
        
        nameDiv.classList.remove('d-none');
        searchBtn.classList.add('d-none');
        nameInput.required = true;
        historyDiv.classList.add('d-none');
        nameInput.value = '';
    } else {
        // تنسيق زر القديم
        btnOld.style.backgroundColor = '#d4af37';
        btnOld.style.color = '#000';
        btnOld.style.fontWeight = '700';
        btnNew.style.backgroundColor = 'transparent';
        btnNew.style.color = 'white';
        btnNew.style.fontWeight = 'normal';
        
        nameDiv.classList.add('d-none');
        searchBtn.classList.remove('d-none');
        nameInput.required = false;
    }
};

// وظيفة البحث عن العميل عبر الـ API (تتضمن نظام الولاء)
window.searchClient = function() {
    const phone = document.getElementById('phone_input').value;
    if(!phone) return;
    
    const historyDiv = document.getElementById('client_history');
    historyDiv.classList.remove('d-none');
    document.getElementById('history_content').innerHTML = '<span class="spinner-border spinner-border-sm text-gold"></span> <span class="text-white ms-2">Searching...</span>';
    
    fetch(`/api/client/${phone}`)
        .then(res => res.json())
        .then(data => {
            const content = document.getElementById('history_content');
            if(data.found) {
                // عرض بيانات العميل + النقاط
                let html = `
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="text-gold fw-bold">${data.name}</h5>
                        <span class="badge bg-gold text-dark fs-6">Points: ${data.points}</span>
                    </div>`;
                
                // إضافة خيار استخدام النقاط إذا كان الرصيد يسمح
                if (data.points >= 100) {
                    html += `
                    <div class="alert alert-warning py-2 mb-3">
                        <input type="checkbox" name="use_points" value="1" class="me-2">
                        <span class="fw-bold">Use 100 points for $5 Discount?</span>
                    </div>`;
                }

                // عرض التاريخ (History)
                if(data.history.length > 0) {
                    html += `<ul class="list-unstyled mb-0">`;
                    data.history.forEach(tx => {
                        html += `<li class="mb-2 pb-2 border-bottom border-secondary d-flex justify-content-between align-items-center">
                                    <span class="text-white-50 small">📅 ${tx.date}</span> 
                                    <span class="text-white fw-semibold">${tx.services}</span> 
                                    <span class="text-gold fw-bold">$${tx.total}</span>
                                 </li>`;
                    });
                    html += `</ul>`;
                } else {
                    html += `<span class="text-white small">No previous transactions found.</span>`;
                }
                content.innerHTML = html;
            } else {
                content.innerHTML = `<div class="alert alert-danger border-0 bg-danger text-white mb-0 py-2 fw-bold">Client not found! Register as New.</div>`;
            }
        });
};

// وظيفة رسم الـ Chart (بتقرأ البيانات من الـ HTML)
window.initBarberChart = function() {
    const canvas = document.getElementById('barberChart');
    if (!canvas) return; 

    const names = JSON.parse(canvas.dataset.names);
    const values = JSON.parse(canvas.dataset.values);

    new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: names,
            datasets: [{
                label: 'Total Earnings ($)',
                data: values,
                backgroundColor: '#d4af37'
            }]
        },
        options: { 
            responsive: true,
            plugins: {
                legend: { labels: { color: '#fff' } }
            },
            scales: {
                y: { ticks: { color: '#fff' } },
                x: { ticks: { color: '#fff' } }
            }
        }
    });
};