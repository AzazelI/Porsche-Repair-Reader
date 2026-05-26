// ==========================================
// PORSCHE REPAIR READER INTERACTIVE ENGINE
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
    // API Configuration
    const DEFAULT_API_URL = "http://localhost:8000";
    
    // Core UI Nodes
    const uploadSection = document.getElementById("upload-section");
    const loadingSection = document.getElementById("loading-section");
    const dashboardSection = document.getElementById("dashboard-section");
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const btnReset = document.getElementById("btn-reset");
    
    // Settings Nodes
    const settingsToggle = document.getElementById("settings-toggle");
    const settingsModal = document.getElementById("settings-modal");
    const settingsClose = document.getElementById("settings-close");
    const apiKeyInput = document.getElementById("api-key-input");
    const apiUrlInput = document.getElementById("api-url-input");
    const settingsSave = document.getElementById("settings-save");
    
    // Loading/Speedometer Elements
    const speedoProgress = document.getElementById("speedo-progress");
    const speedoValue = document.getElementById("speedo-value");
    const loadingStatusText = document.getElementById("loading-status-text");
    
    // Result Target Nodes
    const resLaborTime = document.getElementById("res-labor-time");
    const resTotalParts = document.getElementById("res-total-parts");
    const resTotalTools = document.getElementById("res-total-tools");
    const resTitleKa = document.getElementById("res-title-ka");
    const resTitleEn = document.getElementById("res-title-en");
    
    const stepsContainer = document.getElementById("steps-container");
    const partsContainer = document.getElementById("parts-container");
    const detailsContainer = document.getElementById("details-container");
    const toolsContainer = document.getElementById("tools-container");

    // ==========================================
    // CONFIGURATION MANAGEMENT
    // ==========================================
    
    // Load existing settings from LocalStorage
    let savedApiKey = localStorage.getItem("gemini_api_key") || "";
    if (savedApiKey) {
        apiKeyInput.value = savedApiKey;
    }
    
    let savedApiUrl = localStorage.getItem("backend_api_url") || DEFAULT_API_URL;
    apiUrlInput.value = savedApiUrl;

    // Toggle Settings Modal
    settingsToggle.addEventListener("click", () => {
        settingsModal.classList.remove("hidden");
    });

    settingsClose.addEventListener("click", () => {
        settingsModal.classList.add("hidden");
    });

    // Close on outside click
    window.addEventListener("click", (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.add("hidden");
        }
    });

    // Save Settings
    settingsSave.addEventListener("click", () => {
        const key = apiKeyInput.value.trim();
        const url = apiUrlInput.value.trim() || DEFAULT_API_URL;
        
        if (key) {
            localStorage.setItem("gemini_api_key", key);
            savedApiKey = key;
        } else {
            localStorage.removeItem("gemini_api_key");
            savedApiKey = "";
        }
        
        localStorage.setItem("backend_api_url", url);
        savedApiUrl = url;
        
        alert("პარამეტრები წარმატებით შეინახა!");
        settingsModal.classList.add("hidden");
    });

    // ==========================================
    // DRAG AND DROP FILE HANDLERS
    // ==========================================

    // Click to select file
    dropZone.addEventListener("click", () => {
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Drag-over styling
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // ==========================================
    // BACKEND FILE UPLOAD & SPEEDOMETER ENGINE
    // ==========================================

    function setSpeedometer(percent) {
        // SVG circumference is ~502. 
        // 0% -> dashoffset = 502
        // 100% -> dashoffset = 0 (full meter)
        const circumference = 502;
        const offset = circumference - (percent / 100) * circumference;
        speedoProgress.style.strokeDashoffset = offset;
        
        // Update reading value (e.g. speed scale 0 to 300)
        const speedValue = Math.round((percent / 100) * 300);
        speedoValue.textContent = speedValue;
    }

    function handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("გთხოვთ ატვირთოთ მხოლოდ PDF ფაილი.");
            return;
        }

        // Show loading screen, hide upload
        uploadSection.classList.add("hidden");
        loadingSection.classList.remove("hidden");
        
        // Start speedometer simulation
        setSpeedometer(0);
        loadingStatusText.textContent = "ტექსტის პარსინგი PDF-დან...";
        
        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 45) {
                progress += Math.floor(Math.random() * 5) + 1;
                setSpeedometer(progress);
            }
        }, 300);

        // Prepare multipart form data
        const formData = new FormData();
        formData.append("file", file);

        // Construct headers conditionally: send key if overridden locally, otherwise let server use env var
        const headers = {};
        if (savedApiKey) {
            headers["X-Gemini-API-Key"] = savedApiKey;
        }

        // Call FastAPI Backend
        fetch(`${savedApiUrl}/analyze-instruction`, {
            method: "POST",
            headers: headers,
            body: formData
        })
        .then(response => {
            // Speed up loader to 75% on upload receive
            progress = 75;
            setSpeedometer(75);
            loadingStatusText.textContent = "ხელოვნური ინტელექტი აანალიზებს და თარგმნის...";
            
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || "API Error"); });
            }
            return response.json();
        })
        .then(data => {
            // Success: fill dial to 100%
            setSpeedometer(100);
            loadingStatusText.textContent = "ანალიზი წარმატებით დასრულდა!";
            
            setTimeout(() => {
                clearInterval(progressInterval);
                renderDashboard(data);
            }, 800);
        })
        .catch(error => {
            clearInterval(progressInterval);
            loggerError(error.message);
        });
    }

    function loggerError(msg) {
        alert(`შეცდომა დამუშავებისას: ${msg}`);
        uploadSection.classList.remove("hidden");
        loadingSection.classList.add("hidden");
    }

    // ==========================================
    // RENDERING DATA TO PREMIUM COCKPIT DASHBOARD
    // ==========================================

    function renderDashboard(data) {
        // Hide loading, show dashboard
        loadingSection.classList.add("hidden");
        dashboardSection.classList.remove("hidden");

        // Set Top Summary Stats
        resLaborTime.textContent = data.labor_time || "N/A";
        resTotalParts.textContent = data.parts ? data.parts.length : 0;
        resTotalTools.textContent = data.special_tools ? data.special_tools.length : 0;
        
        // Set Titles
        resTitleKa.textContent = data.title_ka || "სარემონტო ინსტრუქცია";
        resTitleEn.textContent = `Original: ${data.title_en || "N/A"}`;

        // 1. Render Step-by-Step Timeline
        stepsContainer.innerHTML = "";
        if (data.steps && data.steps.length > 0) {
            data.steps.forEach(step => {
                const stepCard = document.createElement("div");
                stepCard.className = "step-card";
                
                // Construct HTML with translation and collapse toggle for original english
                let warningHtml = "";
                if (step.warning_ka) {
                    warningHtml = `
                        <div class="step-warning">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <div>
                                <div class="warning-text-ka">${step.warning_ka}</div>
                                ${step.warning_en ? `<div class="warning-text-en">${step.warning_en}</div>` : ""}
                            </div>
                        </div>
                    `;
                }

                stepCard.innerHTML = `
                    <div class="step-node"></div>
                    <div class="step-header">
                        <span class="step-number">ნაბიჯი ${step.step_number}</span>
                        <button class="btn-toggle-en" onclick="toggleStepOriginal(this)">
                            <i class="fa-solid fa-eye"></i> ორიგინალი (EN)
                        </button>
                    </div>
                    <p class="step-desc-ka">${step.description_ka}</p>
                    <p class="step-desc-en hidden">${step.description_en}</p>
                    ${warningHtml}
                `;
                stepsContainer.appendChild(stepCard);
            });
        } else {
            stepsContainer.innerHTML = "<p class='no-data'>ინსტრუქციის საფეხურები ვერ მოიძებნა.</p>";
        }

        // 2. Render Parts Table
        partsContainer.innerHTML = "";
        if (data.parts && data.parts.length > 0) {
            data.parts.forEach(part => {
                const row = document.createElement("tr");
                
                // Badge styles
                const isRenew = part.status.toLowerCase() === "renew";
                const badgeClass = isRenew ? "badge-renew" : "badge-if-necessary";
                const badgeText = isRenew ? "Renew (შეცვლა)" : "If Necessary";

                row.innerHTML = `
                    <td><span class="part-no">${part.part_number}</span></td>
                    <td>
                        <div class="part-title">
                            <span class="part-title-ka">${part.description_ka}</span>
                            <span class="part-title-en">${part.description_en}</span>
                        </div>
                    </td>
                    <td><span class="badge ${badgeClass}">${badgeText}</span></td>
                `;
                partsContainer.appendChild(row);
            });
        } else {
            partsContainer.innerHTML = `<tr><td colspan="3" class="no-data-table">შესაცვლელი ნაწილები არ მოიძებნა.</td></tr>`;
        }

        // 3. Render Technical specs/details
        detailsContainer.innerHTML = "";
        if (data.key_details_ka && data.key_details_ka.length > 0) {
            data.key_details_ka.forEach((detail, index) => {
                const li = document.createElement("li");
                const originalEn = data.key_details_en && data.key_details_en[index] ? data.key_details_en[index] : "";
                
                li.innerHTML = `
                    <strong>${detail}</strong>
                    ${originalEn ? `<span class="detail-en">${originalEn}</span>` : ""}
                `;
                detailsContainer.appendChild(li);
            });
        } else {
            detailsContainer.innerHTML = "<li>დამატებითი ტექნიკური მახასიათებლები არ არის მითითებული.</li>";
        }

        // 4. Render Special Tools
        toolsContainer.innerHTML = "";
        if (data.special_tools && data.special_tools.length > 0) {
            data.special_tools.forEach(tool => {
                const toolCard = document.createElement("div");
                toolCard.className = "tool-card";
                toolCard.innerHTML = `
                    <span class="tool-no">${tool.tool_number}</span>
                    <span class="tool-name-ka">${tool.name_ka}</span>
                    <span class="tool-name-en">${tool.name_en}</span>
                `;
                toolsContainer.appendChild(toolCard);
            });
        } else {
            toolsContainer.innerHTML = "<p class='no-data-card'>სპეციალური ხელსაწყოები არ არის საჭირო.</p>";
        }
    }

    // Reset view
    btnReset.addEventListener("click", () => {
        dashboardSection.classList.add("hidden");
        uploadSection.classList.remove("hidden");
        fileInput.value = "";
    });
});

// Global function to toggle English version of steps (needed for inline onclick)
window.toggleStepOriginal = function(button) {
    const stepCard = button.closest(".step-card");
    const enText = stepCard.querySelector(".step-desc-en");
    
    if (enText.classList.contains("hidden")) {
        enText.classList.remove("hidden");
        button.innerHTML = `<i class="fa-solid fa-eye-slash"></i> დამალვა`;
    } else {
        enText.classList.add("hidden");
        button.innerHTML = `<i class="fa-solid fa-eye"></i> ორიგინალი (EN)`;
    }
};
