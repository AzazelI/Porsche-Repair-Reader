// ==========================================
// PORSCHE REPAIR READER INTERACTIVE ENGINE
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
    // API Configuration - Set fallback directly to production so it works out-of-the-box for everyone
    const DEFAULT_API_URL = "https://azazei-porsche-repair-reader.hf.space";
    
    // Core UI Nodes
    const uploadSection = document.getElementById("upload-section");
    const landingContainer = document.getElementById("landing-container") || uploadSection;
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
    const logoPorsche = document.getElementById("logo-porsche");
    
    // Loading/Speedometer Elements
    const speedoProgress = document.getElementById("speedo-progress");
    const speedoValue = document.getElementById("speedo-value");
    const speedoNeedle = document.getElementById("speedo-needle");
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
    // Auto-migrate suspended Render URLs to the new stable Hugging Face backend
    if (savedApiUrl.includes("onrender.com") || savedApiUrl.includes("render.com")) {
        savedApiUrl = DEFAULT_API_URL;
        localStorage.setItem("backend_api_url", DEFAULT_API_URL);
    }
    apiUrlInput.value = savedApiUrl;

    // Driving Mode Selector (Normal / Sport / Track Themes)
    const modeButtons = document.querySelectorAll(".btn-mode");
    modeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            modeButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const mode = btn.getAttribute("data-mode");
            document.body.classList.remove("theme-sport", "theme-track");
            
            if (mode === "sport") {
                document.body.classList.add("theme-sport");
            } else if (mode === "track") {
                document.body.classList.add("theme-track");
            }
        });
    });

    // Secret Admin Mode Handler (Triple Click on Porsche crest with Password protection)
    let clickCount = 0;
    let clickTimer = null;
    
    if (logoPorsche) {
        logoPorsche.addEventListener("click", () => {
            clickCount++;
            if (clickCount === 1) {
                clickTimer = setTimeout(() => {
                    clickCount = 0;
                }, 1500);
            } else if (clickCount === 3) {
                clearTimeout(clickTimer);
                clickCount = 0;
                
                // Prompt for admin password
                const passwordInput = prompt("გთხოვთ შეიყვანოთ საინჟინრო რეჟიმის პაროლი:");
                
                if (passwordInput === "Suffering1@") {
                    settingsToggle.classList.toggle("hidden");
                    
                    // Subtle visual feedback on logo click
                    logoPorsche.style.transform = "scale(1.2)";
                    logoPorsche.style.transition = "transform 0.2s ease";
                    setTimeout(() => {
                        logoPorsche.style.transform = "scale(1)";
                    }, 200);
                    
                    if (!settingsToggle.classList.contains("hidden")) {
                        alert("საინჟინრო რეჟიმი წარმატებით გააქტიურდა! ⚙️ ხატულა გამოჩნდა ნავიგაციის პანელში.");
                    } else {
                        alert("საინჟინრო რეჟიმი დეაქტივირებულია და ხატულა დაიმალა.");
                    }
                } else if (passwordInput !== null) {
                    alert("წვდომა უარყოფილია: არასწორი პაროლი!");
                }
            }
        });
    }

    // Also support ?admin=true URL parameter to show it automatically with password check
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("admin") === "true") {
        const passwordInput = prompt("საინჟინრო რეჟიმის გასააქტიურებლად შეიყვანეთ პაროლი:");
        if (passwordInput === "Suffering1@") {
            settingsToggle.classList.remove("hidden");
        } else if (passwordInput !== null) {
            alert("წვდომა უარყოფილია: არასწორი პაროლი!");
        }
    }

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
        
        // Rotate needle (0% -> 0deg, 100% -> 360deg)
        if (speedoNeedle) {
            const degrees = (percent / 100) * 360;
            speedoNeedle.style.transform = `rotate(${degrees}deg)`;
        }
        
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
        landingContainer.classList.add("hidden");
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

        // Start Sport Chrono Millisecond Timer
        const chronoTimeElement = document.getElementById("chrono-time");
        if (chronoTimeElement) {
            chronoTimeElement.textContent = "00:00.00";
        }
        let startTime = Date.now();
        const chronoInterval = setInterval(() => {
            const elapsedTime = Date.now() - startTime;
            const minutes = Math.floor(elapsedTime / 60000);
            const seconds = Math.floor((elapsedTime % 60000) / 1000);
            const ms = Math.floor((elapsedTime % 1000) / 10);
            
            const minutesStr = String(minutes).padStart(2, "0");
            const secondsStr = String(seconds).padStart(2, "0");
            const msStr = String(ms).padStart(2, "0");
            
            if (chronoTimeElement) {
                chronoTimeElement.textContent = `${minutesStr}:${secondsStr}.${msStr}`;
            }
        }, 33); // 30 fps refresh rate

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
                clearInterval(chronoInterval);
                renderDashboard(data);
            }, 800);
        })
        .catch(error => {
            clearInterval(progressInterval);
            clearInterval(chronoInterval);
            loggerError(error.message);
        });
    }

    function loggerError(msg) {
        // Reset fileInput value so they can upload the exact same file again immediately
        if (fileInput) {
            fileInput.value = "";
        }
        
        let displayMsg = msg;
        if (msg.includes("429") || msg.toLowerCase().includes("quota") || msg.toLowerCase().includes("limit")) {
            displayMsg = "Gemini სერვერი დროებით გადატვირთულია (კვოტა ამოიწურა).\n\n" +
                         "გთხოვთ, სცადოთ 60 წამში ხელახლა, ან საიდუმლო საინჟინრო მენიუდან (⚙️) " +
                         "შეიყვანოთ თქვენი პირადი Gemini API გასაღები, რათა გვერდი აუაროთ ამ შეზღუდვას.";
        }
        
        alert(`შეცდომა დამუშავებისას: ${displayMsg}`);
        landingContainer.classList.remove("hidden");
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
                    <div class="step-card-content-wrapper">
                        <button class="step-check-btn" onclick="toggleStepComplete(this)" title="ნაბიჯის მონიშვნა">
                            <i class="fa-solid fa-check"></i>
                        </button>
                        <div class="step-card-body">
                            <div class="step-header">
                                <span class="step-number">ნაბიჯი ${step.step_number}</span>
                                <button class="btn-toggle-en" onclick="toggleStepOriginal(this)">
                                    <i class="fa-solid fa-eye"></i> ორიგინალი (EN)
                                </button>
                            </div>
                            <p class="step-desc-ka">${step.description_ka}</p>
                            <p class="step-desc-en hidden">${step.description_en}</p>
                            ${warningHtml}
                        </div>
                    </div>
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
                const badgeText = isRenew ? "Renew (შეცვლა)" : "If Necessary (საჭიროებისამებრ)";

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
                
                // Dynamic Torque Gauge check
                const torqueRegex = /\b(\d+)\s*Nm\b/i;
                const torqueMatch = (detail + " " + originalEn).match(torqueRegex);
                let torqueGaugeHtml = "";
                
                if (torqueMatch) {
                    const torqueVal = parseInt(torqueMatch[1], 10);
                    const percent = Math.min(100, Math.round((torqueVal / 150) * 100));
                    torqueGaugeHtml = `
                        <div class="torque-widget">
                            <svg class="torque-gauge-svg" viewBox="0 0 36 36">
                                <path class="torque-gauge-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                                <path class="torque-gauge-fill" stroke-dasharray="${percent}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                            </svg>
                            <div>
                                <div class="torque-value-text">${torqueVal} Nm</div>
                                <div class="torque-label">დაჭერის მომენტი (Torque)</div>
                            </div>
                        </div>
                    `;
                }
                
                li.innerHTML = `
                    <div>
                        <strong>${detail}</strong>
                        ${originalEn ? `<span class="detail-en">${originalEn}</span>` : ""}
                        ${torqueGaugeHtml}
                    </div>
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
        landingContainer.classList.remove("hidden");
        fileInput.value = "";
    });
    
    // Printable job card trigger
    const btnPrint = document.getElementById("btn-print");
    if (btnPrint) {
        btnPrint.addEventListener("click", () => {
            window.print();
        });
    }

    // ==========================================
    // PORTCH SPORT CHRONO LIVE CLOCK ENGINE
    // ==========================================
    const liveHms = document.getElementById("chrono-live-hms");
    const liveMs = document.getElementById("chrono-live-ms");
    const handSecond = document.getElementById("chrono-hand-second");
    const handMinute = document.getElementById("chrono-hand-minute");

    function updateLiveChrono() {
        const now = new Date();
        const hrs = now.getHours();
        const mins = now.getMinutes();
        const secs = now.getSeconds();
        const ms = now.getMilliseconds();

        // Digital display
        if (liveHms) {
            const hrsStr = String(hrs).padStart(2, "0");
            const minsStr = String(mins).padStart(2, "0");
            const secsStr = String(secs).padStart(2, "0");
            liveHms.textContent = `${hrsStr}:${minsStr}:${secsStr}`;
        }
        if (liveMs) {
            const msStr = String(Math.floor(ms / 10)).padStart(2, "0");
            liveMs.textContent = `.${msStr}`;
        }

        // Clock hands analog sweep movement
        if (handSecond) {
            const secDeg = ((secs + ms / 1000) / 60) * 360;
            handSecond.style.transform = `rotate(${secDeg}deg)`;
        }

        // Minute hand moves 360 deg in 60 minutes
        if (handMinute) {
            const minDeg = ((mins + secs / 60) / 60) * 360;
            handMinute.style.transform = `rotate(${minDeg}deg)`;
        }

        requestAnimationFrame(updateLiveChrono);
    }
    
    // Initialize the ticking clock
    if (liveHms) {
        updateLiveChrono();
    }

    // Fetch live telemetry data on load to dynamically reflect active API keys count
    fetch(`${savedApiUrl}/health`)
    .then(res => res.json())
    .then(data => {
        const keyStatusElement = document.querySelector(".telemetry-item:nth-child(2) .telemetry-value");
        if (keyStatusElement && data.total_keys_count !== undefined) {
            const geminiCount = data.gemini_keys_count || 0;
            const groqCount = data.groq_keys_count || 0;
            const totalCount = data.total_keys_count || 0;
            keyStatusElement.innerHTML = `<span class="pulse-dot amber"></span> ${totalCount} KEYS OPERATIONAL`;
            keyStatusElement.setAttribute("title", `Gemini: ${geminiCount} გასაღები, Groq: ${groqCount} გასაღები`);
            keyStatusElement.style.cursor = "help";
        }
    })
    .catch(err => {
        console.warn("Failed to fetch live health telemetry:", err);
    });

    // ==========================================
    // INTERACTIVE DEMO MODE DATA & CONTROLLER
    // ==========================================
    const demoCards = document.querySelectorAll(".demo-card");
    
    const DEMO_DATA = {
        gt3: {
            title_ka: "Porsche 911 GT3 (992) - გამონაბოლქვის სპორტული მაყუჩის აწყობა",
            title_en: "Porsche 911 GT3 (992) - Sports Exhaust Muffler & Valve Assembly",
            labor_time: "2.5 Hours (სთ)",
            steps: [
                {
                    step_number: 1,
                    description_ka: "მოათავსეთ ავტომობილი ორსვეტიან ამწეზე და აწიეთ უსაფრთხო სამუშაო სიმაღლეზე.",
                    description_en: "Position the vehicle on a two-post lift and raise to safe working height."
                },
                {
                    step_number: 2,
                    description_ka: "მოხსენით უკანა ბამპერის საფარი და თბოდამცავი ფარები გამონაბოლქვის კოლექტორზე წვდომის მისაღებად.",
                    description_en: "Remove rear bumper cover and heat shield plates to gain access to the exhaust manifold."
                },
                {
                    step_number: 3,
                    description_ka: "გათიშეთ ელექტრონული გამონაბოლქვის სარქველების (Actuator Valves) კონექტორები მაქსიმალური სიფრთხილით.",
                    description_en: "Carefully disconnect the electrical exhaust valve actuator connectors."
                },
                {
                    step_number: 4,
                    description_ka: "მოუშვით სამაგრი საყელურები (Clamps) და მოხსენით ძველი მაყუჩის ბლოკი რეზინის საკიდებიდან.",
                    description_en: "Loosen the fastening clamps and remove the old muffler assembly from rubber hangers."
                },
                {
                    step_number: 5,
                    description_ka: "დაამონტაჟეთ ახალი სპორტული მაყუჩის ბლოკი. დაუჭირეთ სამაგრები 25 Nm ძალით. ყოველთვის გამოიყენეთ ახალი ჭანჭიკები!",
                    description_en: "Install the new sports muffler assembly. Torque clamps to 25 Nm. Always use new self-locking bolts!",
                    warning_ka: "გამოიყენეთ მხოლოდ ახალი კოროზიამედეგი ხრახნები, რათა თავიდან აიცილოთ გამონაბოლქვი აირის გაჟონვა.",
                    warning_en: "Use new anti-corrosion screws only to prevent exhaust gas leakage."
                },
                {
                    step_number: 6,
                    description_ka: "შეაერთეთ გამონაბოლქვი სარქველების აქტუატორები და შეამოწმეთ მათი სრული ფუნქციონალი PIWIS III კომპიუტერით.",
                    description_en: "Reconnect the exhaust valves and test operation using PIWIS III diagnostics tester."
                }
            ],
            parts: [
                {
                    part_number: "992.251.051.A",
                    description_ka: "სპორტული მაყუჩის ბლოკი (Sports Muffler)",
                    description_en: "Sports Muffler Assembly",
                    status: "renew"
                },
                {
                    part_number: "992.251.263",
                    description_ka: "მაყუჩის სამაგრი ხრახნი (Clamping Bolt)",
                    description_en: "Exhaust Clamping Bolt",
                    status: "renew"
                },
                {
                    part_number: "95B.253.115",
                    description_ka: "ლითონის საყელური (Exhaust Gasket)",
                    description_en: "Metal Exhaust Gasket",
                    status: "renew"
                }
            ],
            key_details_ka: [
                "მაყუჩის სამაგრი ხრახნების დაჭერის მომენტი: 25 Nm",
                "გამონაბოლქვის კოლექტორის ხრახნების დაჭერა: 30 Nm",
                "აქტუატორის კალიბრაცია საჭიროებს PIWIS III კომპიუტერს"
            ],
            key_details_en: [
                "Muffler clamp fastening torque: 25 Nm",
                "Exhaust manifold flange torque: 30 Nm",
                "Actuator calibration requires PIWIS III diagnostics tool"
            ],
            special_tools: [
                {
                    tool_number: "WE-1482",
                    name_ka: "საკიდის მოსახსნელი მაშები",
                    name_en: "Exhaust Hanger Removal Pliers"
                },
                {
                    tool_number: "VAS-6558",
                    name_ka: "დინამომეტრული გასაღები 5-50 Nm",
                    name_en: "Torque Wrench 5-50 Nm"
                }
            ]
        },
        cayenne: {
            title_ka: "Porsche Cayenne S (9YA) - კარბონის შემშვები სისტემა და ფილტრი",
            title_en: "Porsche Cayenne S (9YA) - Carbon Air Intake Filter & Snorkel Assembly",
            labor_time: "1.8 Hours (სთ)",
            steps: [
                {
                    step_number: 1,
                    description_ka: "გახსენით კაპოტი და მოხსენით ძრავის ზედა პლასტმასის დეკორატიული საფარი (Engine Cover).",
                    description_en: "Open hood and remove upper decorative plastic engine cover."
                },
                {
                    step_number: 2,
                    description_ka: "გათიშეთ ჰაერის მასის საზომი სენსორის (MAF) ელექტრო კონექტორი.",
                    description_en: "Disconnect Mass Air Flow (MAF) sensor electrical connector."
                },
                {
                    step_number: 3,
                    description_ka: "მოუშვით სამაგრი ჭანჭიკები და ამოიღეთ ქარხნული შემშვები ყუთი ჰაერის ფილტრით.",
                    description_en: "Unscrew clamp and extract the factory airbox and filter element."
                },
                {
                    step_number: 4,
                    description_ka: "გაასუფთავეთ შემშვები საჰაერო არხი მტვრისგან და ნამწვისგან სუფთა მიკროფიბრის ქსოვილით.",
                    description_en: "Clean the intake duct from dust and debris using clean microfiber cloth."
                },
                {
                    step_number: 5,
                    description_ka: "ფრთხილად დაამონტაჟეთ ახალი კარბონის შემშვები სისტემა. დაუჭირეთ ხრახნები 9 Nm ძალით.",
                    description_en: "Install the new Carbon Intake System. Tighten retaining bolts to 9 Nm.",
                    warning_ka: "ზედმეტმა ძალამ შეიძლება გატეხოს ან დააზიანოს კარბონის ბოჭკოვანი კორპუსი.",
                    warning_en: "Excessive torque can crack the carbon fiber housing."
                },
                {
                    step_number: 6,
                    description_ka: "შეაერთეთ MAF სენსორი და დარწმუნდით, რომ შემშვები მილები სრულყოფილად ჰერმეტულია.",
                    description_en: "Reconnect the MAF sensor and verify airtight seal on all duct joints."
                }
            ],
            parts: [
                {
                    part_number: "9YA.129.601",
                    description_ka: "კარბონის ჰაერის ფილტრის კორპუსი (Carbon Airbox)",
                    description_en: "Carbon Fiber Air Intake Assembly",
                    status: "renew"
                },
                {
                    part_number: "970.129.620.01",
                    description_ka: "სპორტული მაღალგამტარი ჰაერის ფილტრი (Sport Filter)",
                    description_en: "High-Flow Air Filter Element",
                    status: "renew"
                },
                {
                    part_number: "N.909.125.01",
                    description_ka: "ჰერმეტული რეზინის რგოლი (O-Ring Seal)",
                    description_en: "O-Ring Seal 80x4",
                    status: "renew"
                }
            ],
            key_details_ka: [
                "კარბონის კორპუსის სამაგრი ხრახნების დაჭერა: 9 Nm",
                "შემშვები მილის საყელურის მომჭერი ხრახნი: 4 Nm",
                "MAF სენსორის ჭანჭიკები: 2 Nm"
            ],
            key_details_en: [
                "Carbon housing retaining bolts torque: 9 Nm",
                "Intake duct hose clamp torque: 4 Nm",
                "MAF sensor retaining screws: 2 Nm"
            ],
            special_tools: [
                {
                    tool_number: "T-10058",
                    name_ka: "დინამომეტრული სახრახნისი 1-10 Nm",
                    name_en: "Torque Screwdriver 1-10 Nm"
                },
                {
                    tool_number: "T-40012",
                    name_ka: "საყელურის მოსაჭერი სპეციალური მაშები",
                    name_en: "Hose Clamp Pliers"
                }
            ]
        },
        taycan: {
            title_ka: "Porsche Taycan Turbo S - ელემენტის გაგრილების სერვისი",
            title_en: "Porsche Taycan Turbo S - High-Voltage Battery Cooling System Service",
            labor_time: "4.2 Hours (სთ)",
            steps: [
                {
                    step_number: 1,
                    description_ka: "გათიშეთ მაღალი ძაბვის (HV) სისტემა სპეციალური გამთიშველი ხიდის (HV Disconnect) მეშვეობით და დაელოდეთ 10 წუთი სრულ განმუხტვას.",
                    description_en: "De-energize the High-Voltage (HV) system using the service disconnect and wait 10 minutes for discharge.",
                    warning_ka: "სასიკვდილო ძაბვა! მუშაობა დაშვებულია მხოლოდ სპეციალური სერტიფიკატის მქონე HV ტექნიკოსებისთვის!",
                    warning_en: "Lethal Voltage! Only certified high-voltage technicians may perform this procedure!"
                },
                {
                    step_number: 2,
                    description_ka: "აწიეთ მანქანა და მოხსენით ქვედა აეროდინამიკური პლასტმასის საფარები და ელემენტის დამცავი ფოლადის ჯავშანი.",
                    description_en: "Raise the vehicle and remove underbody aerodynamic covers and heavy-duty battery protection shield."
                },
                {
                    step_number: 3,
                    description_ka: "სრულად დააცალეთ გაგრილების სითხე (ანტიფრიზი) სპეციალური შემკრები რეზერვუარის გამოყენებით.",
                    description_en: "Drain the coolant from the battery thermal management circuit using a clean fluid recovery station."
                },
                {
                    step_number: 4,
                    description_ka: "უსაფრთხოდ მოხსენით დაზიანებული გაგრილების მილები და სარქველების აქტუატორები.",
                    description_en: "Disconnect the leaking cooling tubes and control valve actuators."
                },
                {
                    step_number: 5,
                    description_ka: "დაამონტაჟეთ ახალი გაგრილების მოდული და დაუჭირეთ ხრახნები 12 Nm ძალით.",
                    description_en: "Install the new cooling module assembly and torque fasteners to 12 Nm."
                },
                {
                    step_number: 6,
                    description_ka: "შეავსეთ გაგრილების სისტემა ვაკუუმ-ტუმბოთი (რათა არ დარჩეს საჰაერო საცობები) და ჩაატარეთ წნევის ტესტი.",
                    description_en: "Fill the system using vacuum filler to avoid air pockets and run a pressure leakage test."
                },
                {
                    step_number: 7,
                    description_ka: "ჩართეთ HV სისტემა და შეამოწმეთ ტემპერატურული სენსორები PIWIS III კომპიუტერით.",
                    description_en: "Re-energize the HV system and verify temperature sensor readings via PIWIS III."
                }
            ],
            parts: [
                {
                    part_number: "9J1.959.801.B",
                    description_ka: "ელემენტის გაგრილების მოდული (Cooling Plate)",
                    description_en: "HV Battery Cooling Plate Assembly",
                    status: "renew"
                },
                {
                    part_number: "9J1.959.263",
                    description_ka: "გაგრილების სპეციალური მილების ნაკრები",
                    description_en: "Coolant Hose Kit",
                    status: "renew"
                },
                {
                    part_number: "958.121.113",
                    description_ka: "Porsche-ს საფირმო ვარდისფერი ანტიფრიზი (5 ლიტრი)",
                    description_en: "Porsche G12++ Coolant Concentrate 5L",
                    status: "renew"
                }
            ],
            key_details_ka: [
                "გაგრილების ხაზის ჭანჭიკების დაჭერის მომენტი: 12 Nm",
                "HV კონექტორის საკეტი ხრახნი: 8 Nm",
                "გაგრილების სისტემის წნევის ტესტი: 1.5 bar 10 წუთის განმავლობაში"
            ],
            key_details_en: [
                "Cooling line retaining bolts torque: 12 Nm",
                "HV connector lock screw torque: 8 Nm",
                "Cooling system pressure test: 1.5 bar for 10 minutes"
            ],
            special_tools: [
                {
                    tool_number: "VAS-611.007",
                    name_ka: "მაღალი ძაბვის დამცავი ხელთათმანები (1000V)",
                    name_en: "High-Voltage Insulated Gloves 1000V"
                },
                {
                    tool_number: "VAS-6096",
                    name_ka: "გაგრილების სისტემის ვაკუუმ-შემვსები",
                    name_en: "Cooling System Vacuum Filling Device"
                },
                {
                    tool_number: "VAS-6558A",
                    name_ka: "მაღალი ძაბვის იზოლაციის ტესტერი",
                    name_en: "HV Insulation Tester"
                }
            ]
        }
    };

    demoCards.forEach(card => {
        card.addEventListener("click", () => {
            const demoKey = card.getAttribute("data-demo");
            const data = DEMO_DATA[demoKey];
            
            if (data) {
                // Show loading screen, hide landing
                landingContainer.classList.add("hidden");
                loadingSection.classList.remove("hidden");
                
                // Start speedometer simulation
                setSpeedometer(0);
                loadingStatusText.textContent = "დემო მონაცემების მყისიერი ჩატვირთვა (0-Latency RAG)...";
                
                let progress = 0;
                const progressInterval = setInterval(() => {
                    if (progress < 100) {
                        progress += 10;
                        setSpeedometer(progress);
                    }
                }, 80);

                // Start Sport Chrono Millisecond Timer
                const chronoTimeElement = document.getElementById("chrono-time");
                if (chronoTimeElement) {
                    chronoTimeElement.textContent = "00:00.00";
                }
                let startTime = Date.now();
                const chronoInterval = setInterval(() => {
                    const elapsedTime = Date.now() - startTime;
                    const minutes = Math.floor(elapsedTime / 60000);
                    const seconds = Math.floor((elapsedTime % 60000) / 1000);
                    const ms = Math.floor((elapsedTime % 1000) / 10);
                    
                    const minutesStr = String(minutes).padStart(2, "0");
                    const secondsStr = String(seconds).padStart(2, "0");
                    const msStr = String(ms).padStart(2, "0");
                    
                    if (chronoTimeElement) {
                        chronoTimeElement.textContent = `${minutesStr}:${secondsStr}.${msStr}`;
                    }
                }, 33);

                setTimeout(() => {
                    clearInterval(progressInterval);
                    clearInterval(chronoInterval);
                    renderDashboard(data);
                }, 900);
            }
        });
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

// Global function to toggle step completion (needed for inline onclick)
window.toggleStepComplete = function(button) {
    const stepCard = button.closest(".step-card");
    stepCard.classList.toggle("completed");
};
