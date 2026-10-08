document.addEventListener('DOMContentLoaded', () => {
    const addExpenseForm = document.getElementById('addExpenseForm');
    const btnPredict = document.getElementById('btnPredict');
    const btnSendChat = document.getElementById('btnSendChat');
    const chatInput = document.getElementById('chatInput');

    // Toast Alert Trigger Function
    function showToast(message, type = 'warning') {
        const toastContainer = document.getElementById('toastContainer');
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'critical' ? 'bg-danger' : 'bg-warning text-dark';
        
        const toastHTML = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0 show mb-2" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body fw-bold">
                        <i class="fa-solid fa-triangle-exclamation me-2"></i> ${message}
                    </div>
                    <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        setTimeout(() => {
            const el = document.getElementById(toastId);
            if (el) el.remove();
        }, 5000);
    }

    // 1. Add Expense Handler
    if (addExpenseForm) {
        addExpenseForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const payload = {
                merchant_name: document.getElementById('merchantName').value,
                amount: parseFloat(document.getElementById('expenseAmount').value),
                payment_method: document.getElementById('paymentMethod').value
            };

            try {
                const res = await fetch('/add-expense', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.success) {
                    addExpenseForm.reset();
                    
                    // Display Alert if threshold triggered
                    if (data.alert) {
                        showToast(data.alert.message, data.alert.type);
                    }

                    // Prepend new row to transaction table
                    const tbody = document.getElementById('transactionTableBody');
                    const noTxnRow = document.getElementById('noTxnRow');
                    if (noTxnRow) noTxnRow.remove();

                    const newRow = `
                        <tr>
                            <td class="fw-bold">${data.transaction.merchant}</td>
                            <td class="text-danger">₹${data.transaction.amount.toFixed(2)}</td>
                            <td><span class="badge bg-secondary">${data.transaction.method}</span></td>
                            <td><span class="badge bg-info text-dark">${data.transaction.category}</span></td>
                            <td class="small text-muted">${data.transaction.date}</td>
                        </tr>
                    `;
                    tbody.insertAdjacentHTML('afterbegin', newRow);

                    // Reload page to automatically refresh progress bar percentages
                    setTimeout(() => window.location.reload(), 1500);
                }
            } catch (err) {
                console.error('Error recording expense:', err);
            }
        });
    }

    // 2. Predictive Budgeting Handler
    if (btnPredict) {
        btnPredict.addEventListener('click', async () => {
            const resultsDiv = document.getElementById('predictionResults');
            resultsDiv.innerHTML = '<div class="spinner-border spinner-border-sm text-warning" role="status"></div> Calculating trends...';

            try {
                const res = await fetch('/predict-budget');
                const data = await res.json();

                if (data.success) {
                    let html = '<ul class="list-group list-group-flush bg-transparent small">';
                    data.predictions.forEach(p => {
                        html += `
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between">
                                <span>${p.category}</span>
                                <div>
                                    <span class="text-muted me-2">Spent: ₹${p.spent_30d.toFixed(2)}</span>
                                    <strong class="text-warning">Proj: ₹${p.projected_next_month.toFixed(2)}</strong>
                                </div>
                            </li>
                        `;
                    });
                    html += '</ul>';
                    resultsDiv.innerHTML = html;
                }
            } catch (err) {
                resultsDiv.innerHTML = '<span class="text-danger">Failed to load projections.</span>';
            }
        });
    }

    // 3. Conversational AI Chatbot Handler
    if (btnSendChat && chatInput) {
        const sendMessage = async () => {
            const msg = chatInput.value.trim();
            if (!msg) return;

            const chatHistory = document.getElementById('chatHistory');
            
            // Append User Message
            chatHistory.insertAdjacentHTML('beforeend', `
                <div class="chat-msg-user p-3 mb-2 small text-end ms-auto" style="max-width: 80%;">
                    ${msg}
                </div>
            `);
            chatInput.value = '';
            chatHistory.scrollTop = chatHistory.scrollHeight;

            // Loading Indicator
            const loaderId = 'loader-' + Date.now();
            chatHistory.insertAdjacentHTML('beforeend', `
                <div id="${loaderId}" class="chat-msg-ai p-3 mb-2 small" style="max-width: 80%;">
                    <i class="fa-solid fa-spinner fa-spin me-2"></i> Analyzing financial context...
                </div>
            `);
            chatHistory.scrollTop = chatHistory.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });
                const data = await res.json();
                
                document.getElementById(loaderId).remove();
                
                chatHistory.insertAdjacentHTML('beforeend', `
                    <div class="chat-msg-ai p-3 mb-2 small" style="max-width: 85%;">
                        ${data.reply.replace(/\n/g, '<br>')}
                    </div>
                `);
                chatHistory.scrollTop = chatHistory.scrollHeight;
            } catch (err) {
                document.getElementById(loaderId).remove();
                chatHistory.insertAdjacentHTML('beforeend', `
                    <div class="chat-msg-ai p-3 mb-2 small text-danger">
                        Failed to receive AI response. Check network/API keys.
                    </div>
                `);
            }
        };

        btnSendChat.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});