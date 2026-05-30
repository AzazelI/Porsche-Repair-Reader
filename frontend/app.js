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

    // Driving Mode Selector (Normal / Sport / Track / Launch Themes)
    const modeButtons = document.querySelectorAll(".btn-mode");
    modeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const mode = btn.getAttribute("data-mode");
            
            // Launch control sequence handles its own activation, overlay, and theme transitions
            if (mode === "launch") {
                triggerLaunchControlSequence();
                return;
            }
            
            modeButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            document.body.classList.remove("theme-sport", "theme-track", "theme-launch");
            
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

    function setTachometer(rpmValue) {
        // rpmValue is between 0 and 9.0 (0 to 9000 RPM)
        // Map 0 -> -120deg, 9 -> 120deg
        const minAngle = -120;
        const maxAngle = 120;
        const angle = minAngle + (rpmValue / 9) * (maxAngle - minAngle);
        
        const needleGroup = document.getElementById("tacho-needle-group");
        if (needleGroup) {
            needleGroup.style.transform = `rotate(${angle}deg)`;
        }
        
        const valueElement = document.getElementById("tacho-value");
        if (valueElement) {
            valueElement.textContent = rpmValue.toFixed(1);
        }
        
        // Shift light & screen rumble at redline (above 8.5 x1000 RPM)
        const shiftLight = document.getElementById("tacho-shift-light");
        const loadingContainer = document.getElementById("loading-section");
        
        if (rpmValue >= 8.5) {
            if (shiftLight) shiftLight.classList.add("flash-active");
            if (loadingContainer) loadingContainer.classList.add("rumble-active");
        } else {
            if (shiftLight) shiftLight.classList.remove("flash-active");
            if (loadingContainer) loadingContainer.classList.remove("rumble-active");
        }
    }

    function setSpeedometer(percent) {
        // Backward compatibility: map 0-100% progress directly to 0-9.0 RPM
        setTachometer((percent / 100) * 9.0);
    }

    function handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("გთხოვთ ატვირთოთ მხოლოდ PDF ფაილი.");
            return;
        }

        // Show loading screen, hide upload
        landingContainer.classList.add("hidden");
        loadingSection.classList.remove("hidden");
        
        // Start Tachometer rev and limit simulation
        let currentRpm = 0.0;
        let state = "revving"; // "revving", "bouncing", "settling", "climbing", "finishing"
        let bounceCount = 0;
        const tachoStartTime = Date.now();
        
        const progressInterval = setInterval(() => {
            const elapsed = Date.now() - tachoStartTime;
            
            if (state === "revving") {
                // Quick rev up to 9.0 RPM in 350ms
                currentRpm += 0.8;
                if (currentRpm >= 9.0) {
                    currentRpm = 9.0;
                    state = "bouncing";
                }
            } else if (state === "bouncing") {
                // Bounce limiter
                currentRpm = currentRpm === 9.0 ? 8.6 : 9.0;
                bounceCount++;
                if (bounceCount > 10) {
                    state = "settling";
                }
            } else if (state === "settling") {
                // Settle down to 3.0 RPM
                currentRpm -= 0.8;
                if (currentRpm <= 3.0) {
                    currentRpm = 3.0;
                    state = "climbing";
                }
            } else if (state === "climbing") {
                // Slowly climb towards 7.5 RPM during analysis (max 60 seconds)
                const climbFactor = Math.min(1, elapsed / 60000);
                currentRpm = 3.0 + climbFactor * 4.5;
            } else if (state === "finishing") {
                // Sweep up to max RPM on successful response
                currentRpm += 0.8;
                if (currentRpm >= 9.0) {
                    currentRpm = 9.0;
                }
            }
            
            setTachometer(currentRpm);
        }, 30);

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
            // Update state to finishing for final redline sweep
            state = "finishing";
            loadingStatusText.textContent = "ხელოვნური ინტელექტი აანალიზებს და თარგმნის...";
            
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || "API Error"); });
            }
            return response.json();
        })
        .then(data => {
            // Success: fill dial to max
            setTachometer(9.0);
            loadingStatusText.textContent = "ანალიზი წარმატებით დასრულდა!";
            
            setTimeout(() => {
                clearInterval(progressInterval);
                clearInterval(chronoInterval);
                
                // Clear any leftover rumble or flash styles
                const loadingContainer = document.getElementById("loading-section");
                if (loadingContainer) loadingContainer.classList.remove("rumble-active");
                const shiftLight = document.getElementById("tacho-shift-light");
                if (shiftLight) shiftLight.classList.remove("flash-active");
                
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
        },
        r1200gs: {
            title_ka: "BMW R 1200 GS - ძრავის ზეთისა და ფილტრის შეცვლა",
            title_en: "BMW R 1200 GS - Engine Oil & Filter Replacement Service",
            labor_time: "0.8 Hours (სთ) [8 FRU]",
            steps: [
                {
                    step_number: 1,
                    description_ka: "მოათავსეთ მოტოციკლი სწორ ზედაპირზე ცენტრალურ სადგამზე (Center Stand) და დააზღვიეთ გორებისგან.",
                    description_en: "Position the motorcycle on a level surface on its center stand and secure from rolling."
                },
                {
                    step_number: 2,
                    description_ka: "აამუშავეთ ძრავი და გაათბეთ სამუშაო ტემპერატურამდე (სანამ რადიატორის ვენტილატორი არ ჩაირთვება), რათა ზეთი გათხელდეს.",
                    description_en: "Start the engine and warm it up to operating temperature until oil flows freely."
                },
                {
                    step_number: 3,
                    description_ka: "მოათავსეთ ზეთის შესაგროვებელი ტაფა (Oil Drain Pan) ძრავის ქვეშ. მოხსენით ძრავის დამცავი ფირფიტა (Engine Guard plate).",
                    description_en: "Place an oil drain pan under the engine. Remove the engine underbody protection shield plate."
                },
                {
                    step_number: 4,
                    description_ka: "სპეციალური 8მმ ექვსწახნაგა გასაღებით მოუშვით ძრავის ზეთის გამოსაშვები ჭანჭიკი (Drain Plug) და სრულად დააცალეთ ზეთი.",
                    description_en: "Unscrew the engine oil drain plug using an 8mm hex tool and drain the oil completely."
                },
                {
                    step_number: 5,
                    description_ka: "სპეციალური ფილტრის გასაღებით (Oil Filter Wrench) მოხსენით ძველი ზეთის ფილტრი.",
                    description_en: "Remove the old oil filter using a dedicated oil filter wrench tool."
                },
                {
                    step_number: 6,
                    description_ka: "წაუსვით ახალი ძრავის ზეთი ახალი ფილტრის რეზინის შუასადებს. დაამონტაჟეთ ახალი ფილტრი და დაუჭირეთ 11 Nm ძალით.",
                    description_en: "Apply clean engine oil to the rubber seal of the new oil filter. Install new filter and torque to 11 Nm.",
                    warning_ka: "არ გადაუჭიროთ ფილტრს ზედმეტად, წინააღმდეგ შემთხვევაში დააზიანებთ რეზინის შუასადებს!",
                    warning_en: "Do not over-tighten the oil filter to avoid damaging the rubber ring seal!"
                },
                {
                    step_number: 7,
                    description_ka: "შეცვალეთ ზეთის სანიაღვრე ჭანჭიკის სპილენძის საყელური (Crush Washer). დაუჭირეთ ჭანჭიკი 42 Nm ძალით.",
                    description_en: "Replace the copper crush washer on the drain plug. Tighten the drain plug to 42 Nm."
                },
                {
                    step_number: 8,
                    description_ka: "ზეთის შესავსები ყელიდან ჩაასხით ზუსტად 4.0 ლიტრი რეკომენდებული 15W-50 სიბლანტის ზეთი (ან SAE 5W-40 Boxer-ისთვის).",
                    description_en: "Fill the engine with exactly 4.0 liters of recommended 15W-50 oil viscosity (or SAE 5W-40 for newer boxer engines)."
                },
                {
                    step_number: 9,
                    description_ka: "დაახრახნეთ შესავსები ხუფის სახურავი. დაქოქეთ ძრავი, შეამოწმეთ ზეთის წნევის ინდიკატორი და გაჟონვები. დააბრუნეთ ძრავის დამცავი ფირფიტა.",
                    description_en: "Reinstall the oil filler cap. Start the engine, check oil pressure warning light and look for leaks. Reinstall the guard plate."
                }
            ],
            parts: [
                {
                    part_number: "11.42.7.673.541",
                    description_ka: "BMW Boxer-ის ორიგინალი ზეთის ფილტრი (Oil Filter)",
                    description_en: "Original BMW Engine Oil Filter",
                    status: "renew"
                },
                {
                    part_number: "07.11.9.963.252",
                    description_ka: "სანიაღვრე ჭანჭიკის სპილენძის საყელური (Crush Washer A20x24)",
                    description_en: "Copper Crush Gasket A20x24",
                    status: "renew"
                },
                {
                    part_number: "83.21.2.405.947",
                    description_ka: "BMW Advantec Ultimate 15W-50 ძრავის ზეთი (4 ლიტრი)",
                    description_en: "BMW Advantec Ultimate 15W-50 Engine Oil (4 Liters)",
                    status: "renew"
                }
            ],
            key_details_ka: [
                "ზეთის სანიაღვრე ჭანჭიკის დაჭერის მომენტი: 42 Nm",
                "ზეთის ფილტრის დაჭერის მომენტი: 11 Nm",
                "ზეთის საერთო მოცულობა: 4.0 ლიტრი (ფილტრის ჩათვლით)"
            ],
            key_details_en: [
                "Oil drain plug torque specification: 42 Nm",
                "Oil filter torque specification: 11 Nm",
                "Total oil capacity: 4.0 liters (including filter replacement)"
            ],
            special_tools: [
                {
                    tool_number: "83.30.0.401.554",
                    name_ka: "ფილტრის მოხსნის სპეციალური გასაღებ-ჭიქა",
                    name_en: "Oil Filter wrench cup 76mm"
                },
                {
                    tool_number: "VAS-6558",
                    name_ka: "დინამომეტრული გასაღები 10-100 Nm",
                    name_en: "Torque Wrench 10-100 Nm"
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
                
                loadingStatusText.textContent = "დემო მონაცემების მყისიერი ჩატვირთვა (0-Latency RAG)...";
                
                // Tachometer physics simulation variables
                let currentRpm = 0.0;
                let state = "revving"; // "revving", "bouncing", "finishing"
                let bounceCount = 0;
                const tachoStartTime = Date.now();
                
                const progressInterval = setInterval(() => {
                    const elapsed = Date.now() - tachoStartTime;
                    
                    if (state === "revving") {
                        // Quick linear climb to 9.0 RPM in 300ms
                        currentRpm = (elapsed / 300) * 9.0;
                        if (currentRpm >= 9.0) {
                            currentRpm = 9.0;
                            state = "bouncing";
                        }
                    } else if (state === "bouncing") {
                        // Rev-limiter bounce (tat-tat-tat-tat!)
                        currentRpm = currentRpm === 9.0 ? 8.6 : 9.0;
                        bounceCount++;
                        if (bounceCount > 8) {
                            state = "finishing";
                        }
                    } else if (state === "finishing") {
                        currentRpm = 9.0;
                    }
                    
                    setTachometer(currentRpm);
                }, 30);

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
                    
                    // Reset tacho and loading state styles
                    setTachometer(0.0);
                    const loadingContainer = document.getElementById("loading-section");
                    if (loadingContainer) loadingContainer.classList.remove("rumble-active");
                    const shiftLight = document.getElementById("tacho-shift-light");
                    if (shiftLight) shiftLight.classList.remove("flash-active");
                    
                    renderDashboard(data);
                }, 1050); // Total 1.05s to allow for full rev limiter rumble effect
            }
        });
    });

    // ==========================================
    // NATIVE WEB AUDIO ENGINE SOUND SYNTHESIZER
    // ==========================================
    let audioCtx = null;
    let engineOsc = null;
    let engineGain = null;
    let filterNode = null;
    
    function startEngineSound() {
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            
            // Main flat-six cylinder tone
            engineOsc = audioCtx.createOscillator();
            engineOsc.type = 'sawtooth';
            engineOsc.frequency.setValueAtTime(75, audioCtx.currentTime); // Idle Hz
            
            // Sub oscillator for deep rumble
            const subOsc = audioCtx.createOscillator();
            subOsc.type = 'sawtooth';
            subOsc.frequency.setValueAtTime(37.5, audioCtx.currentTime);

            // Biquad filter to give it realistic flat-six throttle sound
            filterNode = audioCtx.createBiquadFilter();
            filterNode.type = 'lowpass';
            filterNode.frequency.setValueAtTime(240, audioCtx.currentTime);
            
            // Volume Gain Node
            engineGain = audioCtx.createGain();
            engineGain.gain.setValueAtTime(0.0, audioCtx.currentTime);
            engineGain.gain.linearRampToValueAtTime(0.18, audioCtx.currentTime + 0.1);
            
            // Connect nodes
            engineOsc.connect(filterNode);
            subOsc.connect(filterNode);
            filterNode.connect(engineGain);
            engineGain.connect(audioCtx.destination);
            
            engineOsc.start();
            subOsc.start();
            
            engineOsc._subOsc = subOsc;
        } catch (e) {
            console.warn("Web Audio API not allowed or supported yet:", e);
        }
    }
    
    function updateEngineSound(rpmValue) {
        if (!audioCtx || !engineOsc) return;
        
        // Map 0.0 - 9.0 RPM -> 55Hz - 360Hz
        const freq = 55 + (rpmValue * 34);
        engineOsc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        if (engineOsc._subOsc) {
            engineOsc._subOsc.frequency.setValueAtTime(freq / 2, audioCtx.currentTime);
        }
        
        // Open/Close filter intake based on RPM
        const filterFreq = 160 + (rpmValue * 85);
        filterNode.frequency.setValueAtTime(filterFreq, audioCtx.currentTime);
    }
    
    function stopEngineSound() {
        if (engineGain && audioCtx) {
            engineGain.gain.linearRampToValueAtTime(0.0, audioCtx.currentTime + 0.15);
            setTimeout(() => {
                try {
                    if (engineOsc) {
                        engineOsc.stop();
                        if (engineOsc._subOsc) engineOsc._subOsc.stop();
                    }
                } catch (e) {}
                audioCtx = null;
                engineOsc = null;
                engineGain = null;
            }, 200);
        }
    }
    
    function playBeep(pitch, duration) {
        try {
            const ctx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.setValueAtTime(pitch, ctx.currentTime);
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
            osc.start();
            osc.stop(ctx.currentTime + duration);
        } catch (e) {}
    }

    // ==========================================
    // LAUNCH CONTROL SEQUENCE CONTROLLER
    // ==========================================
    function triggerLaunchControlSequence() {
        const overlay = document.getElementById("launch-overlay");
        const statusText = document.getElementById("launch-status");
        const timerText = document.getElementById("launch-timer");
        const lights = document.querySelectorAll(".light");
        
        if (!overlay) return;
        
        // Reset state
        lights.forEach(l => l.classList.remove("active"));
        overlay.classList.remove("hidden");
        document.body.classList.remove("theme-launch", "theme-sport", "theme-track");
        document.body.classList.remove("body-rumble");
        
        statusText.textContent = "DEPRESS BRAKE & ACCELERATOR TO 100%";
        statusText.classList.remove("ready");
        timerText.textContent = "0.00s";
        
        // Turn on Engine Audio flat-six flat tone at low idle
        startEngineSound();
        updateEngineSound(1.2);
        
        // Drag tree sequence
        // Stage 1: Pre-stage (Yellow) at 400ms
        setTimeout(() => {
            const pl = document.querySelector(".prestage-left");
            const pr = document.querySelector(".prestage-right");
            if (pl) pl.classList.add("active");
            if (pr) pr.classList.add("active");
            playBeep(880, 0.08);
            updateEngineSound(2.2);
        }, 400);
        
        // Stage 2: Stage (Yellow) at 800ms
        setTimeout(() => {
            const sl = document.querySelector(".stage-left");
            const sr = document.querySelector(".stage-right");
            if (sl) sl.classList.add("active");
            if (sr) sr.classList.add("active");
            playBeep(880, 0.08);
            updateEngineSound(3.8);
        }, 800);
        
        // Stage 3: Countdown Red 1 at 1200ms
        setTimeout(() => {
            const c1 = document.querySelector(".count-1");
            if (c1) c1.classList.add("active");
            playBeep(520, 0.12);
            updateEngineSound(5.2);
        }, 1200);
        
        // Stage 4: Countdown Red 2 at 1600ms
        setTimeout(() => {
            const c2 = document.querySelector(".count-2");
            if (c2) c2.classList.add("active");
            playBeep(520, 0.12);
            updateEngineSound(6.8);
        }, 1600);
        
        // Stage 5: Countdown Red 3 + Launch Control Engaged at 2000ms
        let bounceInterval = null;
        setTimeout(() => {
            const c3 = document.querySelector(".count-3");
            if (c3) c3.classList.add("active");
            statusText.textContent = "LAUNCH CONTROL ACTIVE!";
            statusText.classList.add("ready");
            playBeep(520, 0.12);
            
            // Limiter bounce vibration and pops
            document.body.classList.add("body-rumble");
            let bounceToggle = false;
            bounceInterval = setInterval(() => {
                bounceToggle = !bounceToggle;
                const rpm = bounceToggle ? 9.0 : 8.6;
                updateEngineSound(rpm);
                if (bounceToggle) playBeep(70, 0.04);
            }, 60);
        }, 2000);
        
        // Stage 6: GREEN LIGHT - GO! at 2800ms
        setTimeout(() => {
            if (bounceInterval) clearInterval(bounceInterval);
            document.body.classList.remove("body-rumble");
            
            // Turn off reds, light greens
            const reds = document.querySelectorAll(".light.red");
            reds.forEach(r => r.classList.remove("active"));
            
            const gl = document.querySelector(".launch-left");
            const gr = document.querySelector(".launch-right");
            if (gl) gl.classList.add("active");
            if (gr) gr.classList.add("active");
            
            playBeep(1150, 0.35);
            updateEngineSound(9.0);
            statusText.textContent = "LAUNCH!!!";
            
            let start = Date.now();
            const launchTimerInterval = setInterval(() => {
                const elapsed = (Date.now() - start) / 1000;
                timerText.textContent = elapsed.toFixed(2) + "s";
                if (elapsed >= 1.2) {
                    clearInterval(launchTimerInterval);
                }
            }, 10);
            
            // Fade out overlay and switch to Theme Launch
            setTimeout(() => {
                overlay.style.opacity = '0';
                setTimeout(() => {
                    overlay.classList.add("hidden");
                    overlay.style.opacity = '1';
                    
                    // Switch active button to LC
                    modeButtons.forEach(b => b.classList.remove("active"));
                    const lcButton = document.querySelector(".btn-mode-lc");
                    if (lcButton) lcButton.classList.add("active");
                    
                    document.body.classList.add("theme-launch");
                    stopEngineSound();
                }, 500);
            }, 1200);
            
        }, 2800);
    }

    // ==========================================
    // GWEN AI CHAT & VOICE ASSISTANT CLIENT ENGINE
    // ==========================================
    const gwenVoicePanel = document.getElementById("gwen-voice-panel");
    const gwenHeaderToggle = document.getElementById("gwen-header-toggle");
    const gwenChatWindow = document.getElementById("gwen-chat-window");
    const gwenChatHistory = document.getElementById("gwen-chat-history");
    const gwenChatInput = document.getElementById("gwen-chat-input");
    const gwenSendBtn = document.getElementById("gwen-send-btn");
    const gwenMicBtn = document.getElementById("gwen-mic-btn");
    const gwenStatus = document.getElementById("gwen-voice-status");
    
    let voiceRecognition = null;
    let isListening = false;
    
    // Toggle expand/collapse chatbot panel
    if (gwenHeaderToggle) {
        gwenHeaderToggle.addEventListener("click", () => {
            gwenVoicePanel.classList.toggle("expanded");
            gwenChatWindow.classList.toggle("hidden");
            
            // Auto scroll chat history to bottom on expand
            if (!gwenChatWindow.classList.contains("hidden")) {
                setTimeout(() => {
                    gwenChatHistory.scrollTop = gwenChatHistory.scrollHeight;
                }, 100);
            }
        });
    }
    
    function appendChatMessage(sender, text, isUser = false) {
        if (!gwenChatHistory) return;
        
        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-message ${isUser ? 'technician' : 'gwen'}`;
        
        // Convert double asterisks to bold tag for markdown look
        let formattedText = text;
        formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        msgDiv.innerHTML = `
            <span class="chat-sender">${sender}</span>
            <p class="chat-text">${formattedText}</p>
        `;
        
        gwenChatHistory.appendChild(msgDiv);
        gwenChatHistory.scrollTop = gwenChatHistory.scrollHeight;
    }
    
    function speakText(text) {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            const voices = window.speechSynthesis.getVoices();
            const geVoice = voices.find(v => v.lang.includes("ka") || v.lang.includes("GE"));
            
            if (geVoice) {
                utterance.voice = geVoice;
                utterance.lang = "ka-GE";
            } else {
                utterance.lang = "ka-GE";
            }
            
            utterance.rate = 1.05;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
        }
    }
    
    function initializeGWENVoice() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            if (gwenStatus) gwenStatus.textContent = "ხმის მართვა არ არის მხარდაჭერილი";
            return;
        }
        
        voiceRecognition = new SpeechRecognition();
        voiceRecognition.continuous = false; // Stop after speaking a command for chat flow
        voiceRecognition.interimResults = false;
        voiceRecognition.lang = "ka-GE"; // Georgian locale
        
        voiceRecognition.onstart = () => {
            isListening = true;
            if (gwenVoicePanel) gwenVoicePanel.classList.add("listening");
            if (gwenStatus) gwenStatus.textContent = "გისმენთ... (Gwen Active)";
        };
        
        voiceRecognition.onend = () => {
            isListening = false;
            if (gwenVoicePanel) gwenVoicePanel.classList.remove("listening");
            if (gwenStatus) gwenStatus.textContent = "Standby (დააწკაპუნეთ სალაპარაკოდ)";
        };
        
        voiceRecognition.onresult = (event) => {
            const resultIndex = event.resultIndex;
            const transcript = event.results[resultIndex][0].transcript.trim();
            
            // 1. Append user's spoken command to chat
            appendChatMessage("Technician", transcript, true);
            
            // 2. Process command
            processVoiceCommand(transcript.toLowerCase());
        };
        
        voiceRecognition.onerror = (e) => {
            console.warn("Gwen recognition error:", e);
            if (gwenStatus) gwenStatus.textContent = "ხმა ვერ იქნა ამოცნობილი";
        };
    }
    
    function processVoiceCommand(command) {
        const steps = document.querySelectorAll(".step-card");
        
        // Command 0: R1200GS persistent cache search and load simulation
        if ((command.includes("ახსენი") || command.includes("მოძებნე") || command.includes("ჩატვირთე") || command.includes("explain") || command.includes("load")) && 
            (command.includes("r1200gs") || command.includes("r 1200") || command.includes("მოტოციკლი") || command.includes("ზეთი") || command.includes("oil"))) {
            
            appendChatMessage("Gwen AI", "R1200GS-ის ზეთის შეცვლის ინსტრუქცია **მოიძებნა სუპაბეისის pgvector RAG ბაზაში**. ვიწყებ ჩატვირთვას...");
            speakText("R1200GS-ის ზეთის შეცვლის ინსტრუქცია მოიძებნა სუპაბეისის ქეში. ვიწყებ ჩატვირთვას.");
            
            setTimeout(() => {
                const uploadSection = document.getElementById("upload-section");
                const landingContainer = document.getElementById("landing-container") || uploadSection;
                const loadingSection = document.getElementById("loading-section");
                const dashboardSection = document.getElementById("dashboard-section");
                
                if (landingContainer) landingContainer.classList.add("hidden");
                if (dashboardSection) dashboardSection.classList.add("hidden");
                if (loadingSection) loadingSection.classList.remove("hidden");
                
                const loadingStatusText = document.getElementById("loading-status-text");
                if (loadingStatusText) {
                    loadingStatusText.textContent = "ძებნა სუპაბეისის ბაზაში (pgvector RAG) და ჩატვირთვა...";
                }
                
                // Tachometer physics simulation variables
                let currentRpm = 0.0;
                let state = "revving"; 
                let bounceCount = 0;
                const tachoStartTime = Date.now();
                
                // Start a Boxer-engine sound flat tone using Web Audio API!
                startEngineSound();
                updateEngineSound(1.2);
                
                const progressInterval = setInterval(() => {
                    const elapsed = Date.now() - tachoStartTime;
                    
                    if (state === "revving") {
                        currentRpm = (elapsed / 300) * 9.0;
                        if (currentRpm >= 9.0) {
                            currentRpm = 9.0;
                            state = "bouncing";
                        }
                    } else if (state === "bouncing") {
                        currentRpm = currentRpm === 9.0 ? 8.6 : 9.0;
                        bounceCount++;
                        if (bounceCount > 8) {
                            state = "finishing";
                        }
                    } else if (state === "finishing") {
                        currentRpm = 9.0;
                    }
                    
                    setTachometer(currentRpm);
                }, 30);
                
                setTimeout(() => {
                    clearInterval(progressInterval);
                    stopEngineSound();
                    
                    setTachometer(0.0);
                    const loadingContainer = document.getElementById("loading-section");
                    if (loadingContainer) loadingContainer.classList.remove("rumble-active");
                    const shiftLight = document.getElementById("tacho-shift-light");
                    if (shiftLight) shiftLight.classList.remove("flash-active");
                    
                    const rData = DEMO_DATA.r1200gs;
                    renderDashboard(rData);
                    
                    appendChatMessage("Gwen AI", "BMW R1200GS-ის სარემონტო დაფა წარმატებით მომზადდა. **ნაბიჯი 1:** მოათავსეთ მოტოციკლი ცენტრალურ სადგამზე.");
                    speakText("BMW R1200GS-ის ზეთის შეცვლის ინსტრუქცია წარმატებით ჩაიტვირთა სუპაბეისის მეხსიერებიდან. პირველი ნაბიჯი: მოათავსეთ მოტოციკლი ცენტრალურ სადგამზე.");
                }, 1500); 
            }, 1000);
            
            return;
        }

        // Command 1: "შემდეგი" (Next Step)
        if (command.includes("შემდეგი") || command.includes("შემდეგ") || command.includes("next")) {
            const activeStep = document.querySelector(".step-card:not(.completed)");
            if (activeStep) {
                const checkBtn = activeStep.querySelector(".step-check-btn");
                if (checkBtn) {
                    checkBtn.click();
                    appendChatMessage("Gwen AI", "ნაბიჯი მონიშნულია შესრულებულად! გადავდივართ მომდევნო ეტაპზე...");
                    speakText("ნაბიჯი შესრულებულია");
                    
                    setTimeout(() => {
                        const nextStep = document.querySelector(".step-card:not(.completed)");
                        if (nextStep) {
                            nextStep.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            const text = nextStep.querySelector(".step-desc-ka").textContent;
                            appendChatMessage("Gwen AI", `**${nextStep.querySelector(".step-number").textContent}:** ${text}`);
                            speakText("შემდეგი ნაბიჯი: " + text);
                        } else {
                            appendChatMessage("Gwen AI", "ყველა ნაბიჯი წარმატებით შესრულებულია! **სამუშაო ბარათი მზადაა.**");
                            speakText("ყველა ნაბიჯი წარმატებით შესრულებულია! სამუშაო ბარათი მზადაა.");
                        }
                    }, 500);
                }
            } else {
                appendChatMessage("Gwen AI", "ყველა ნაბიჯი უკვე დასრულებულია.");
                speakText("ყველა ნაბიჯი დასრულებულია");
            }
        }
        
        // Command 2: "წინა" (Previous Step)
        else if (command.includes("წინა") || command.includes("უკან") || command.includes("previous")) {
            const completedSteps = document.querySelectorAll(".step-card.completed");
            if (completedSteps.length > 0) {
                const lastCompleted = completedSteps[completedSteps.length - 1];
                const checkBtn = lastCompleted.querySelector(".step-check-btn");
                if (checkBtn) {
                    checkBtn.click();
                    lastCompleted.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    const text = lastCompleted.querySelector(".step-desc-ka").textContent;
                    appendChatMessage("Gwen AI", `დავბრუნდით წინა ნაბიჯზე: ${text}`);
                    speakText("დავბრუნდით წინა ნაბიჯზე: " + text);
                }
            } else {
                appendChatMessage("Gwen AI", "ჩვენ უკვე პირველ ნაბიჯზე ვართ.");
                speakText("პირველ ნაბიჯზე ვართ");
            }
        }
        
        // Command 3: "წაიკითხე" (Read Current Step)
        else if (command.includes("წაიკითხე") || command.includes("read")) {
            const activeStep = document.querySelector(".step-card:not(.completed)") || document.querySelector(".step-card");
            if (activeStep) {
                const stepNum = activeStep.querySelector(".step-number").textContent;
                const text = activeStep.querySelector(".step-desc-ka").textContent;
                appendChatMessage("Gwen AI", `**კითხულობს:** ${stepNum}. ${text}`);
                speakText(stepNum + ". " + text);
            } else {
                appendChatMessage("Gwen AI", "სარემონტო ინსტრუქცია არ არის ჩატვირთული.");
                speakText("ინსტრუქცია არ არის ჩატვირთული");
            }
        }
        
        // Command 4: Go to specific step number
        else if (command.includes("ნაბიჯი") || command.includes("step")) {
            const match = command.match(/\d+/);
            if (match) {
                const targetNum = parseInt(match[0], 10);
                const targetStep = Array.from(steps).find(step => {
                    const numText = step.querySelector(".step-number").textContent;
                    return numText.includes(targetNum);
                });
                
                if (targetStep) {
                    targetStep.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    const text = targetStep.querySelector(".step-desc-ka").textContent;
                    appendChatMessage("Gwen AI", `გადავედით **ნაბიჯზე ${targetNum}**: ${text}`);
                    speakText("ნაბიჯი " + targetNum + ": " + text);
                } else {
                    appendChatMessage("Gwen AI", `ნაბიჯი ${targetNum} ვერ მოიძებნა.`);
                    speakText("ნაბიჯი " + targetNum + " ვერ მოიძებნა");
                }
            }
        }
        
        // Command 5: Read Torque Specs
        else if (command.includes("ძალა") || command.includes("დაჭერა") || command.includes("torque")) {
            const details = document.querySelectorAll("#details-container li strong");
            if (details.length > 0) {
                let specsText = "დაჭერის ძალებია: ";
                let specsHtml = "**დაჭერის მომენტები:**<br>";
                details.forEach(detail => {
                    specsText += detail.textContent + ". ";
                    specsHtml += `- ${detail.textContent}<br>`;
                });
                appendChatMessage("Gwen AI", specsHtml);
                speakText(specsText);
            } else {
                appendChatMessage("Gwen AI", "ძალები ან დაჭერის მომენტები მითითებული არ არის.");
                speakText("დაჭერის ძალები მითითებული არ არის");
            }
        }
        
        // Command 6: Greeting/Test
        else if (command.includes("gwen") || command.includes("გვენ") || command.includes("პივის") || command.includes("ჰელოუ") || command.includes("hello")) {
            appendChatMessage("Gwen AI", "გისმენთ! მე ვარ **Gwen AI**, თქვენი კოკპიტის ასისტენტი. შემიძლია ჩავტვირთო სარემონტო ინსტრუქციები, წავიკითხო ნაბიჯები და დაჭერის ძალები.");
            speakText("გისმენთ! მე ვარ გვენ ეიაი, თქვენი კოკპიტის ასისტენტი. შემიძლია წავიკითხო სარემონტო ნაბიჯები და დაჭერის ძალები.");
        }
        
        // Unrecognized text entry: fallback AI chat bubble
        else {
            appendChatMessage("Gwen AI", "მე შემიძლია დაგეხმაროთ R1200GS, 911 GT3, Cayenne ან Taycan-ის სარემონტო სამუშაოებში. მკითხეთ ნებისმიერი რამ, ან მითხარით: „ახსენი r1200gs ზეთის შეცვლა“.");
            speakText("რითი შემიძლია დაგეხმაროთ?");
        }
    }
    
    // Setup chat send handlers
    function handleChatMessageSubmit() {
        if (!gwenChatInput) return;
        const text = gwenChatInput.value.trim();
        if (!text) return;
        
        // 1. Append technician's typed text to chat
        appendChatMessage("Technician", text, true);
        
        // 2. Clear input
        gwenChatInput.value = "";
        
        // 3. Process the text command
        setTimeout(() => {
            processVoiceCommand(text.toLowerCase());
        }, 300);
    }
    
    if (gwenSendBtn) {
        gwenSendBtn.addEventListener("click", handleChatMessageSubmit);
    }
    
    if (gwenChatInput) {
        gwenChatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                handleChatMessageSubmit();
            }
        });
    }
    
    if (gwenMicBtn) {
        gwenMicBtn.addEventListener("click", () => {
            if (!voiceRecognition) {
                initializeGWENVoice();
            }
            
            if (voiceRecognition) {
                if (isListening) {
                    voiceRecognition.stop();
                } else {
                    voiceRecognition.start();
                    playBeep(987, 0.08);
                    setTimeout(() => playBeep(1318, 0.15), 80);
                }
            }
        });
    }
    
    if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices();
    }
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
