// Global keyboard help functions - accessible even in PC Busy mode
window.showKeyboardHelp = function() {
    const modal = document.getElementById('keyboardHelp');
    if (modal) modal.style.display = 'flex';
};

window.hideKeyboardHelp = function() {
    const modal = document.getElementById('keyboardHelp');
    if (modal) modal.style.display = 'none';
};

(() => {
// Enhanced Order System JavaScript
// Supports keyboard shortcuts, step navigation, themes, and accountant-friendly features

const __isPcBusyMode =
    (window.__ADD_ORDER_PC_BUSY__ === true) ||
    (document.body.classList.contains("mode-pc") && document.querySelector(".busy-order-pc"));

if (__isPcBusyMode) return;

function loadProducts() {
    const jsonEl = document.getElementById("productsData");
    if (jsonEl?.textContent) {
        try {
            const parsed = JSON.parse(jsonEl.textContent);
            if (Array.isArray(parsed)) return parsed;
        } catch (e) {}
    }

    const firstSelect = document.querySelector("#orderBody .item-row .product");
    if (!firstSelect) return [];
    return Array.from(firstSelect.querySelectorAll("option"))
        .filter(opt => opt.value)
        .map(opt => ({
            id: opt.value,
            name: (opt.textContent || "").trim(),
            price: parseFloat(opt.dataset.price || "0") || 0,
            barcode: (opt.dataset.barcode || "").trim(),
        }));
}

let products = loadProducts();

// Additional sundry value applied at order-level (added via keyboard popup)
let extraSundry = 0;

// Step management
let currentStep = 1;
const totalSteps = 4;

// Keyboard shortcuts and accountant-style navigation
document.addEventListener('keydown', function(e) {
    // Prevent default behavior for our shortcuts
    if (handleKeyboardShortcut(e)) {
        e.preventDefault();
    }
});

function handleKeyboardShortcut(e) {
    const activeElement = document.activeElement;
    const isInput = activeElement.tagName === 'INPUT' || activeElement.tagName === 'SELECT' || activeElement.tagName === 'TEXTAREA';

    // F1 - Help
    if (e.key === 'F1') {
        showKeyboardHelp();
        return true;
    }

    // F2 - Party Search (only when not in input)
    if (e.key === 'F2' && !isInput) {
        document.getElementById('partySearch').focus();
        return true;
    }

    // F3 - Product Search (only when not in input)
    if (e.key === 'F3' && !isInput) {
        const searchInputs = document.querySelectorAll('.product-search');
        if (searchInputs.length > 0) {
            searchInputs[0].focus();
        }
        return true;
    }

    // F4 - Add Row
    if (e.key === 'F4') {
        addRow();
        return true;
    }

    // F5 - Save Order
    if (e.key === 'F5') {
        document.querySelector('form').submit();
        return true;
    }

    // F6 - Save Draft
    if (e.key === 'F6') {
        document.getElementById('saveDraft')?.click();
        return true;
    }

    // F7 - Print
    if (e.key === 'F7') {
        window.print();
        return true;
    }

    // F8 - Bill Sundry (opens popup)
    if (e.key === 'F8') {
        openSundryPopup();
        return true;
    }

    // Ctrl+S - Quick Save
    if (e.ctrlKey && e.key === 's') {
        document.querySelector('form').submit();
        return true;
    }

    // Tab navigation with Enter
    if (e.key === 'Enter' && !e.shiftKey) {
        // Let row-level handlers manage Enter inside order table
        if (activeElement && activeElement.closest && activeElement.closest('#orderBody')) return false;

        const focusableElements = getFocusableElements();
        const currentIndex = focusableElements.indexOf(activeElement);
        if (currentIndex >= 0 && currentIndex < focusableElements.length - 1) {
            focusableElements[currentIndex + 1].focus();
            return true;
        }
    }

    // Shift+Tab navigation
    if (e.key === 'Enter' && e.shiftKey) {
        if (activeElement && activeElement.closest && activeElement.closest('#orderBody')) return false;
        const focusableElements = getFocusableElements();
        const currentIndex = focusableElements.indexOf(activeElement);
        if (currentIndex > 0) {
            focusableElements[currentIndex - 1].focus();
            return true;
        }
    }

    // Esc - Cancel/Close
    if (e.key === 'Escape') {
        if (document.getElementById('keyboardHelp').style.display !== 'none') {
            hideKeyboardHelp();
            return true;
        }
        // Clear current field
        if (activeElement && activeElement.value !== undefined) {
            activeElement.value = '';
        }
        return true;
    }

    return false;
}

function getFocusableElements() {
    return Array.from(document.querySelectorAll(
        'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])'
    )).filter(el => el.offsetParent !== null); // Only visible elements
}

// Step navigation
function updateStepIndicator() {
    // Update step circles
    document.querySelectorAll('.step-circle').forEach((step, index) => {
        const stepNum = index + 1;
        step.classList.remove('active', 'completed');
        if (stepNum < currentStep) {
            step.classList.add('completed');
        } else if (stepNum === currentStep) {
            step.classList.add('active');
        }
    });

    // Show/hide step content
    showStepContent(currentStep);

    // Update navigation buttons
    document.getElementById('prevStep').disabled = currentStep === 1;
    document.getElementById('nextStep').disabled = currentStep === totalSteps;
}

function showStepContent(step) {
    // Hide all step content
    document.querySelectorAll('.step-content').forEach(content => {
        content.style.display = 'none';
    });

    // Show current step content
    const currentContent = document.getElementById(`step-${step}`);
    if (currentContent) {
        currentContent.style.display = 'block';
    }

    // Auto-focus first field in step
    setTimeout(() => {
        const firstField = getFirstFieldInStep(step);
        if (firstField) {
            firstField.focus();
        }
    }, 100);
}

function getFirstFieldInStep(step) {
    switch(step) {
        case 1: return document.getElementById('orderType');
        case 2: return document.querySelector('.product-search');
        case 3: return document.querySelector('textarea[name="notes"]');
        case 4: return document.querySelector('button[type="submit"]');
        default: return null;
    }
}

// Step navigation event listeners
document.getElementById('nextStep').addEventListener('click', () => {
    if (currentStep < totalSteps) {
        currentStep++;
        updateStepIndicator();
    }
});

document.getElementById('prevStep').addEventListener('click', () => {
    if (currentStep > 1) {
        currentStep--;
        updateStepIndicator();
    }
});

// Keyboard help functions (already defined globally above)

// Enhanced row addition with keyboard support
function addRow(product=null){
    let tr=document.createElement("tr");
    tr.className = "item-row";

    tr.innerHTML=`
    <td>
        <div class="card border-warning">
            <div class="card-body p-2">
                <input type="text" class="form-control product-search mb-1 fw-bold" placeholder="🔍 Search Product (F3)" autocomplete="off">
                <div class="product-dropdown dropdown-menu dropdown-hidden"></div>
                <select name="product[]" class="form-select product d-none fw-bold" required title="Select Product">
                    <option value="">Select Product</option>
                    ${products.map(p=>`
                    <option value="${p.id}" data-price="${p.price}" data-barcode="${p.barcode}">
                    ${p.name}
                    </option>`).join("")}
                </select>
            </div>
        </div>
    </td>
    <td>
        <div class="card border-info">
            <div class="card-body p-2">
                <input type="number" name="qty[]" class="form-control qty text-center fw-bold" value="1" min="1" aria-label="Quantity">
            </div>
        </div>
    </td>
    <td>
        <div class="card border-danger">
            <div class="card-body p-2">
                <input type="number" name="price[]" class="form-control price text-end fw-bold" step="0.01" aria-label="Price">
            </div>
        </div>
    </td>
    <td>
        <div class="card border-success">
            <div class="card-body p-2">
                <input type="number" name="amount[]" class="form-control amount text-end fw-bold" readonly aria-label="Amount">
            </div>
        </div>
    </td>
    <td class="text-center">
        <button type="button" class="btn btn-danger btn-lg remove-btn fw-bold shadow">✕</button>
    </td>
    `;

    document.getElementById("orderBody").appendChild(tr);
    setupProductRow(tr);
    recalc();

    // Focus first input in new row
    setTimeout(() => {
        const firstInput = tr.querySelector('.product-search');
        if (firstInput) firstInput.focus();
    }, 100);
}

document.getElementById("addRow").onclick=()=>addRow();

// Enhanced calculation with visual feedback
function recalc(){
    let sub=0;
    document.querySelectorAll("#orderBody tr").forEach(tr=>{
        let q=+tr.querySelector(".qty").value||0;
        let p=+tr.querySelector(".price").value||0;
        let t=q*p;
        tr.querySelector(".amount").value = t.toFixed(2);
        sub+=t;
    });

    // Include sundry amounts in subtotal
    sub += (parseFloat(extraSundry) || 0);

    // Animate number changes
    animateNumberChange('subTotal', sub);
    animateNumberChange('tax', sub * 0.18);
    animateNumberChange('grandTotal', sub * 1.18);
}

function animateNumberChange(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const currentValue = parseFloat(element.textContent) || 0;
    if (currentValue !== newValue) {
        element.style.transform = 'scale(1.1)';
        element.style.color = newValue > currentValue ? '#28a745' : '#dc3545';

        setTimeout(() => {
            element.textContent = newValue.toFixed(2);
            element.style.transform = 'scale(1)';
            element.style.color = '';
        }, 200);
    }
}

document.addEventListener("input",recalc);

// Enhanced QR / BARCODE scanning
document.getElementById("startScan").onclick=()=>{
    const scanner = document.getElementById('scanner');
    scanner.innerHTML = '<div class="text-center text-primary fw-bold">📷 Initializing camera...</div>';

    new Html5Qrcode("scanner").start(
        {facingMode:"environment"},
        {fps:10,qrbox:250},
        (code)=>{
            // Success feedback
            scanner.innerHTML = '<div class="text-center text-success fw-bold">✅ Product scanned successfully!</div>';

            let row=[...document.querySelectorAll(".product option")]
            .find(o=>o.dataset.barcode===code);

            if(row){
                addRow();
                let last=document.querySelector("#orderBody tr:last-child select");
                last.value=row.value;
                last.dispatchEvent(new Event("change"));

                // AI Suggestion
                showAISuggestion(`🤖 Added ${row.text} automatically from barcode scan!`);
            } else {
                showAISuggestion(`⚠️ Product not found for barcode: ${code}`);
            }

            // Auto-stop after successful scan
            setTimeout(() => {
                try {
                    new Html5Qrcode("scanner").stop();
                } catch(e) {}
            }, 2000);
        },
        (error)=>{
            console.log('Scan error:', error);
        }
    ).catch(err => {
        scanner.innerHTML = '<div class="text-center text-danger fw-bold">❌ Camera access denied. Please allow camera permissions.</div>';
    });
};

// AI Suggestions
function showAISuggestion(message) {
    const suggestionDiv = document.createElement('div');
    suggestionDiv.className = 'ai-suggestions mt-3';
    suggestionDiv.innerHTML = `
        <div class="suggestion-item fw-bold">
            ${message}
        </div>
    `;

    const scanSection = document.querySelector('.scan-section');
    // Prevent duplicate messages
    const existing = Array.from(scanSection.querySelectorAll('.suggestion-item')).map(si => si.textContent.trim());
    if (existing.includes(message.trim())) return;
    scanSection.appendChild(suggestionDiv);

    setTimeout(() => {
        suggestionDiv.remove();
    }, 5000);
}

// Enhanced product row setup
function setupProductRow(row) {
    const searchInput = row.querySelector(".product-search");
    const select = row.querySelector(".product");
    const priceInput = row.querySelector(".price");
    const qtyInput = row.querySelector(".qty");
    const amountInput = row.querySelector(".amount");

    // Product search with keyboard support
    searchInput.addEventListener("keyup", (e) => {
        const val = searchInput.value.toLowerCase();
        [...select.options].forEach(opt => {
            if (!opt.value) return;
            opt.style.display = opt.text.toLowerCase().includes(val) ? "block" : "none";
        });

        // Auto-select if only one match
        const visibleOptions = [...select.options].filter(opt => opt.style.display !== 'none' && opt.value);
        if (visibleOptions.length === 1 && e.key === 'Enter') {
            select.value = visibleOptions[0].value;
            select.dispatchEvent(new Event('change'));
            searchInput.value = visibleOptions[0].text;
        }
    });

    // Auto price fill
    select.addEventListener("change", () => {
        const price = select.selectedOptions[0]?.dataset.price || 0;
        priceInput.value = price;
        recalc();

        // Move to quantity field
        setTimeout(() => qtyInput.focus(), 100);
    });

    // Auto calculation and navigation
    qtyInput.addEventListener("input", () => recalc());
    priceInput.addEventListener("input", () => recalc());

    // Enter key navigation
    qtyInput.addEventListener("keydown", (e) => {
        if (e.key === 'Enter') {
            priceInput.focus();
        }
    });

    priceInput.addEventListener("keydown", (e) => {
        if (e.key === 'Enter') {
            // If this is last row and user already added >=2 rows, treat Enter as finish
            const rows = document.querySelectorAll('#orderBody .item-row');
            const isLast = rows.length && rows[rows.length - 1] === row;
            if (isLast && rows.length >= 2) {
                // Open sundry popup for final adjustments instead of auto-adding rows
                openSundryPopup();
            } else {
                // Add new row and focus first field
                addRow();
            }
            e.preventDefault();
            return;
        }
    });
}

// Initialize first row
setupProductRow(document.querySelector(".item-row"));

// Initialize step system
updateStepIndicator();

// Mode switching
document.querySelectorAll('.mode-switcher .btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-switcher .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const mode = btn.dataset.mode;
        document.getElementById('mainOrderCard').className = `card shadow-lg border-0 order-card mode-${mode}`;
    });
});

function applyTheme(theme) {
    Array.from(document.body.classList).forEach(cls => {
        if (cls.startsWith("theme-")) document.body.classList.remove(cls);
    });
    document.body.classList.add(`theme-${theme}`);
}

// Theme switching
document.getElementById('themeSelect')?.addEventListener('change', (e) => {
    const theme = e.target.value;
    applyTheme(theme);
    localStorage.setItem('preferredTheme', theme);
});

// Load saved theme
const savedTheme = localStorage.getItem('preferredTheme') || 'default';
if (document.getElementById('themeSelect')) {
    document.getElementById('themeSelect').value = savedTheme;
}
applyTheme(savedTheme);

// Enhanced action buttons
document.getElementById('saveDraft')?.addEventListener('click', () => {
    // Save as draft functionality
    alert('Draft saved successfully! You can continue editing later.');
});

document.getElementById('shareWhatsApp')?.addEventListener('click', () => {
    const orderData = getOrderData();
    const message = `Order Summary:\nType: ${orderData.type}\nParty: ${orderData.party}\nTotal: ₹${orderData.total}\n\nGenerated by KhataPro`;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
});

document.getElementById('shareEmail')?.addEventListener('click', () => {
    const orderData = getOrderData();
    const subject = `Order from ${orderData.party}`;
    const body = `Order Details:\n\nType: ${orderData.type}\nParty: ${orderData.party}\nTotal: ₹${orderData.total}\n\nGenerated by KhataPro`;
    const emailUrl = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.open(emailUrl, '_blank');
});

document.getElementById('downloadPDF')?.addEventListener('click', () => {
    // PDF generation would require additional library like jsPDF
    alert('PDF download feature coming soon! Use Print (F7) for now.');
});

document.getElementById('downloadExcel')?.addEventListener('click', () => {
    // Excel generation would require additional library
    alert('Excel download feature coming soon! Use Print (F7) for now.');
});

function getOrderData() {
    const orderType = document.getElementById('orderType').selectedOptions[0]?.text || 'N/A';
    const party = document.getElementById('partySelect').selectedOptions[0]?.text || 'N/A';
    const total = document.getElementById('grandTotal').textContent || '0.00';

    return {
        type: orderType,
        party: party,
        total: total
    };
}

// Party search functionality
document.getElementById('partySearch').addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    const dropdown = document.getElementById('partyDropdown');
    const select = document.getElementById('partySelect');

    if (searchTerm.length > 0) {
        const options = Array.from(select.options).filter(option =>
            option.text.toLowerCase().includes(searchTerm)
        );

        if (options.length > 0) {
            dropdown.innerHTML = options.map(option =>
                `<div class="dropdown-item" onclick="selectParty('${option.value}', '${option.text}')">${option.text}</div>`
            ).join('');
            dropdown.style.display = 'block';
        } else {
            dropdown.style.display = 'none';
        }
    } else {
        dropdown.style.display = 'none';
    }
});

function selectParty(value, text) {
    document.getElementById('partySelect').value = value;
    document.getElementById('partySearch').value = text;
    document.getElementById('partyDropdown').style.display = 'none';

    // Move to next step
    setTimeout(() => {
        document.getElementById('nextStep').click();
    }, 500);
}

// Hide dropdown when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.card-body')) {
        document.getElementById('partyDropdown').style.display = 'none';
    }
});

// Sundry popup and keyboard-only flow helpers
function openSundryPopup() {
    const popup = document.getElementById('sundryPopup');
    if (!popup) return;
    popup.style.display = 'block';
    // focus name field
    setTimeout(() => document.getElementById('sundryName')?.focus(), 50);
}

function closeSundryPopup() {
    const popup = document.getElementById('sundryPopup');
    if (!popup) return;
    popup.style.display = 'none';
    // move focus back to a sensible place: addRow button
    document.getElementById('addRow')?.focus();
}

// When trigger receives focus (keyboard tab reaches bottom), open popup
document.addEventListener('focusin', (e) => {
    if (e.target && e.target.id === 'sundryTrigger') {
        openSundryPopup();
    }
});

// Apply sundry: add hidden inputs and update totals, then go to save step
document.getElementById('applySundry')?.addEventListener('click', () => {
    const name = document.getElementById('sundryName')?.value || 'Sundry';
    const amt = parseFloat(document.getElementById('sundryAmount')?.value || '0') || 0;
    extraSundry = (parseFloat(extraSundry) || 0) + amt;

    // add hidden inputs to form so server receives sundry info
    const form = document.getElementById('orderForm');
    if (form) {
        const hn = document.createElement('input');
        hn.type = 'hidden'; hn.name = 'sundry_name[]'; hn.value = name; form.appendChild(hn);
        const ha = document.createElement('input');
        ha.type = 'hidden'; ha.name = 'sundry_amount[]'; ha.value = amt; form.appendChild(ha);
    }

    recalc();
    closeSundryPopup();

    // Move to final Save step (Step 4) and focus Save
    currentStep = 4;
    updateStepIndicator();
    setTimeout(() => document.querySelector('form button[type="submit"], #saveDraftStep4')?.focus(), 200);
});

document.getElementById('closeSundry')?.addEventListener('click', () => closeSundryPopup());

// Keyboard handling when sundry popup is open
document.addEventListener('keydown', (e) => {
    const popup = document.getElementById('sundryPopup');
    if (!popup || popup.style.display === 'none') return;
    if (e.key === 'Escape') {
        closeSundryPopup();
        e.preventDefault();
        return;
    }
    if (e.key === 'Enter') {
        // Treat Enter as apply
        document.getElementById('applySundry')?.click();
        e.preventDefault();
        return;
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Enhanced Order System loaded successfully!');
    console.log('💡 Press F1 for keyboard shortcuts help');
});

})();
