// ==========================================
// PORSCHE REPAIR READER INTERACTIVE ENGINE
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // AUTHENTICATION SECURITY GATE
    // ==========================================
    const appWrapper = document.getElementById("app-wrapper");
    const loginContainer = document.getElementById("login-container");
    const loginForm = document.getElementById("login-form");
    const loginEmail = document.getElementById("login-email");
    const loginPassword = document.getElementById("login-password");
    const loginError = document.getElementById("login-error");
    const loginBtn = document.getElementById("login-btn");
    const togglePassword = document.getElementById("toggle-password");
    const loginHeroBg = document.querySelector(".login-hero-bg");
    const loginAmbientGlow = document.querySelector(".login-ambient-glow");
    const logoutBtn = document.getElementById("logout-btn");

    // Password visibility toggle
    if (togglePassword) {
        togglePassword.addEventListener("click", () => {
            const isPassword = loginPassword.type === "password";
            loginPassword.type = isPassword ? "text" : "password";
            const icon = togglePassword.querySelector("i");
            if (icon) {
                if (isPassword) {
                    icon.classList.remove("fa-eye");
                    icon.classList.add("fa-eye-slash");
                } else {
                    icon.classList.remove("fa-eye-slash");
                    icon.classList.add("fa-eye");
                }
            }
        });
    }

    // Check if authenticated
    if (localStorage.getItem("reader_auth") === "true") {
        if (loginContainer) loginContainer.style.display = "none";
        if (appWrapper) appWrapper.classList.remove("hidden");
    } else {
        if (loginContainer) loginContainer.style.display = "flex";
        if (appWrapper) appWrapper.classList.add("hidden");
    }

    if (logoutBtn) {
        logoutBtn.addEventListener("click", (e) => {
            e.preventDefault();
            localStorage.removeItem("reader_auth");
            window.location.reload();
        });
    }

    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (loginError) loginError.textContent = "";

            const emailVal = loginEmail.value.trim().toLowerCase();
            const passwordVal = loginPassword.value;

            if (emailVal === "givijananashvili40@gmail.com" && passwordVal === "Suffering1@") {
                // 1. Play startup sound (ev start)
                playTaycanStartupSound();

                // 2. Animate Taycan lights glow
                if (loginHeroBg) loginHeroBg.classList.add("lit");
                if (loginAmbientGlow) loginAmbientGlow.classList.add("lit");

                // 3. Disable button, change text
                if (loginBtn) {
                    loginBtn.disabled = true;
                    loginBtn.innerHTML = '<i class="fa-solid fa-bolt animate-pulse"></i> Initializing cockpit...';
                }

                // 4. Transition screen and open workspace after sound ramp
                setTimeout(() => {
                    if (loginContainer) {
                        loginContainer.classList.add("fade-out");
                        setTimeout(() => {
                            loginContainer.style.display = "none";
                        }, 800);
                    }
                    if (appWrapper) appWrapper.classList.remove("hidden");
                    localStorage.setItem("reader_auth", "true");
                }, 1800);

            } else {
                if (loginError) loginError.textContent = "Invalid username or password.";
            }
        });
    }

    function playTaycanStartupSound() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        
        const now = ctx.currentTime;
        
        // 1. Clean Sub-Bass Hum (Sine Wave)
        const subOsc = ctx.createOscillator();
        const subGain = ctx.createGain();
        subOsc.type = 'sine';
        subOsc.frequency.setValueAtTime(35, now);
        subOsc.frequency.exponentialRampToValueAtTime(60, now + 1.8);
        
        subOsc.connect(subGain);
        subGain.connect(ctx.destination);
        
        // 2. FM Synthesis for Electric Coil Whine (Sine modulating Triangle)
        // Carrier (Triangle wave)
        const carrier = ctx.createOscillator();
        const carrierGain = ctx.createGain();
        carrier.type = 'triangle';
        carrier.frequency.setValueAtTime(100, now);
        carrier.frequency.exponentialRampToValueAtTime(320, now + 1.8);
        
        // Modulator (Sine wave)
        const modulator = ctx.createOscillator();
        const modulatorGain = ctx.createGain();
        modulator.type = 'sine';
        modulator.frequency.setValueAtTime(150, now);
        modulator.frequency.exponentialRampToValueAtTime(450, now + 1.8);
        
        // Modulation depth: sweeps up as the sound intensifies
        modulatorGain.gain.setValueAtTime(30, now);
        modulatorGain.gain.exponentialRampToValueAtTime(120, now + 1.8);
        
        // Modulator -> ModulatorGain -> Carrier Frequency
        modulator.connect(modulatorGain);
        modulatorGain.connect(carrier.frequency);
        
        // Bandpass filter to isolate the futuristic resonance
        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.Q.setValueAtTime(4.0, now);
        filter.frequency.setValueAtTime(120, now);
        filter.frequency.exponentialRampToValueAtTime(650, now + 1.6);
        
        carrier.connect(filter);
        filter.connect(carrierGain);
        carrierGain.connect(ctx.destination);
        
        // 3. Ambient Electric Space swoosh (filtered pink/white noise)
        const bufferSize = ctx.sampleRate * 2.0; // 2 seconds
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        
        const noiseFilter = ctx.createBiquadFilter();
        noiseFilter.type = 'bandpass';
        noiseFilter.Q.setValueAtTime(10.0, now);
        noiseFilter.frequency.setValueAtTime(150, now);
        noiseFilter.frequency.exponentialRampToValueAtTime(800, now + 1.5);
        
        const noiseGain = ctx.createGain();
        noise.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(ctx.destination);
        
        // Volume Envelopes
        subGain.gain.setValueAtTime(0, now);
        subGain.gain.linearRampToValueAtTime(0.8, now + 0.3);
        subGain.gain.exponentialRampToValueAtTime(0.001, now + 2.0);
        
        carrierGain.gain.setValueAtTime(0, now);
        carrierGain.gain.linearRampToValueAtTime(0.5, now + 0.4);
        carrierGain.gain.exponentialRampToValueAtTime(0.001, now + 1.9);
        
        noiseGain.gain.setValueAtTime(0, now);
        noiseGain.gain.linearRampToValueAtTime(0.2, now + 0.3);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, now + 1.7);
        
        // Play
        subOsc.start(now);
        carrier.start(now);
        modulator.start(now);
        noise.start(now);
        
        subOsc.stop(now + 2.0);
        carrier.stop(now + 2.0);
        modulator.stop(now + 2.0);
        noise.stop(now + 2.0);
    }

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
    const bypassCacheInput = document.getElementById("bypass-cache-input");
    const logoPorsche = document.getElementById("logo-porsche");
    
    // TU Modal Nodes
    const tuModal = document.getElementById("tu-modal");
    const tuClose = document.getElementById("tu-close");
    const tuInput = document.getElementById("tu-input");
    const tuLiveCalc = document.getElementById("tu-live-calc");
    const tuCancel = document.getElementById("tu-cancel");
    const tuConfirm = document.getElementById("tu-confirm");
    let pendingFileToUpload = null;
    let lastEnteredTU = null;
    
    // Ollama Config Nodes
    const ollamaUrlInput = document.getElementById("ollama-url-input");
    const btnTestOllama = document.getElementById("btn-test-ollama");
    const ollamaModelSelect = document.getElementById("ollama-model-select");
    const ollamaStatusMsg = document.getElementById("ollama-status-msg");
    
    // Loading/Speedometer Elements
    const speedoProgress = document.getElementById("speedo-progress");
    const speedoValue = document.getElementById("speedo-value");
    const speedoNeedle = document.getElementById("speedo-needle");
    const loadingStatusText = document.getElementById("loading-status-text");
    
    // Result Target Nodes
    const resLaborTime = document.getElementById("res-labor-time");
    const resLaborCost = document.getElementById("res-labor-cost");
    const resTotalParts = document.getElementById("res-total-parts");
    const resTotalTools = document.getElementById("res-total-tools");
    const resTitleKa = document.getElementById("res-title-ka");
    const resTitleEn = document.getElementById("res-title-en");
    const resVehicleModel = document.getElementById("res-vehicle-model");
    const resAiEngine = document.getElementById("res-ai-engine");
    
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

    const DEFAULT_OLLAMA_URL = "http://localhost:11434";
    let savedOllamaUrl = localStorage.getItem("ollama_host_url") || DEFAULT_OLLAMA_URL;
    let savedOllamaModel = localStorage.getItem("ollama_model_name") || "";

    if (ollamaUrlInput) {
        ollamaUrlInput.value = savedOllamaUrl;
    }
    
    // Pre-populate Ollama model list from localStorage if it exists
    if (savedOllamaModel && ollamaModelSelect) {
        ollamaModelSelect.innerHTML = "";
        const opt = document.createElement("option");
        opt.value = savedOllamaModel;
        opt.textContent = savedOllamaModel;
        opt.selected = true;
        ollamaModelSelect.appendChild(opt);
    }

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
        // Silently run connection check to pull model list if Ollama is running
        testOllamaConnection(true);
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

        // Ollama local settings save
        if (ollamaUrlInput) {
            const ollamaUrl = ollamaUrlInput.value.trim() || DEFAULT_OLLAMA_URL;
            localStorage.setItem("ollama_host_url", ollamaUrl);
            savedOllamaUrl = ollamaUrl;
        }
        if (ollamaModelSelect) {
            const ollamaModel = ollamaModelSelect.value;
            if (ollamaModel) {
                localStorage.setItem("ollama_model_name", ollamaModel);
                savedOllamaModel = ollamaModel;
            } else {
                localStorage.removeItem("ollama_model_name");
                savedOllamaModel = "";
            }
        }
        
        alert("პარამეტრები წარმატებით შეინახა!");
        settingsModal.classList.add("hidden");
    });

    // Test Connection Button Action
    if (btnTestOllama) {
        btnTestOllama.addEventListener("click", (e) => {
            e.preventDefault();
            testOllamaConnection(false);
        });
    }

    async function testOllamaConnection(silent = false) {
        const host = (ollamaUrlInput ? ollamaUrlInput.value.trim() : "") || DEFAULT_OLLAMA_URL;
        if (ollamaStatusMsg) {
            ollamaStatusMsg.style.display = "block";
            ollamaStatusMsg.style.color = "#ffaa00";
            ollamaStatusMsg.textContent = "კავშირი მყარდება...";
        }
        try {
            // Fetch list of local models from local Ollama
            const res = await fetch(`${host}/api/tags`, { method: "GET" });
            if (!res.ok) throw new Error("სერვერმა დააბრუნა შეცდომა");
            const data = await res.json();
            const models = data.models || [];
            
            if (ollamaModelSelect) {
                ollamaModelSelect.innerHTML = "";
                if (models.length === 0) {
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.textContent = "მოდელები არ არის ჩამოტვირთული (გაუშვით 'ollama pull')";
                    ollamaModelSelect.appendChild(opt);
                } else {
                    models.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.name;
                        opt.textContent = m.name;
                        if (m.name === savedOllamaModel) {
                            opt.selected = true;
                        }
                        ollamaModelSelect.appendChild(opt);
                    });
                }
            }
            if (ollamaStatusMsg) {
                ollamaStatusMsg.style.color = "#88d413";
                ollamaStatusMsg.textContent = `კავშირი წარმატებით დამყარდა! ნაპოვნია ${models.length} მოდელი.`;
            }
            if (!silent) alert("კავშირი წარმატებით დამყარდა!");
            return true;
        } catch (e) {
            console.error("Ollama connection test failed:", e);
            if (ollamaStatusMsg) {
                ollamaStatusMsg.style.color = "#d5001c";
                ollamaStatusMsg.textContent = "კავშირი ვერ დამყარდა. დარწმუნდით, რომ Ollama გაშვებულია და CORS ჩართულია.";
            }
            if (!silent) alert("კავშირის ტესტირება ჩავარდა! დარწმუნდით, რომ გაშვებულია Ollama და ჩართულია CORS (OLLAMA_ORIGINS='*').");
            return false;
        }
    }

    // ==========================================
    // TU MODAL LOGIC AND EVENT LISTENERS
    // ==========================================

    function askForTUAndUpload(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("გთხოვთ ატვირთოთ მხოლოდ PDF ფაილი.");
            return;
        }
        pendingFileToUpload = file;
        
        // Reset input field and live calculation
        if (tuInput) {
            tuInput.value = "";
        }
        if (tuLiveCalc) {
            tuLiveCalc.textContent = "გამოთვლილი დრო: 0 წუთი";
        }
        
        // Show modal
        if (tuModal) {
            tuModal.classList.remove("hidden");
            if (tuInput) tuInput.focus();
        } else {
            // Fallback if modal not found
            handleFileUpload(file, null);
        }
    }

    function calculateTUDuration(tuVal) {
        const tu = parseInt(tuVal) || 0;
        const minutes = tu * 0.6;
        const hours = minutes / 60;
        const h_part = Math.floor(hours);
        const m_part = Math.round(minutes % 60);
        
        let timeStr = "";
        if (h_part > 0) {
            timeStr = `${h_part} სთ`;
            if (m_part > 0) {
                timeStr += ` ${m_part} წთ`;
            }
        } else {
            timeStr = `${m_part} წთ`;
        }
        return { minutes, timeStr };
    }

    if (tuInput) {
        tuInput.addEventListener("input", (e) => {
            const val = e.target.value;
            if (val === "") {
                tuLiveCalc.textContent = "გამოთვლილი დრო: 0 წუთი";
                return;
            }
            const { minutes, timeStr } = calculateTUDuration(val);
            tuLiveCalc.textContent = `გამოთვლილი დრო: ${timeStr} (${minutes.toFixed(0)} წთ)`;
        });

        tuInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                confirmTUAndUpload();
            }
        });
    }

    function confirmTUAndUpload() {
        if (!tuInput || !tuInput.value) {
            alert("გთხოვთ, შეიყვანოთ სამუშაო დრო (TU) გასაგრძელებლად.");
            return;
        }
        const tuVal = parseInt(tuInput.value);
        if (isNaN(tuVal) || tuVal < 0) {
            alert("გთხოვთ, შეიყვანოთ ვალიდური დადებითი რიცხვი.");
            return;
        }
        
        lastEnteredTU = tuVal;
        if (tuModal) tuModal.classList.add("hidden");
        
        if (pendingFileToUpload) {
            handleFileUpload(pendingFileToUpload, lastEnteredTU);
        }
    }

    if (tuConfirm) {
        tuConfirm.addEventListener("click", confirmTUAndUpload);
    }

    function closeTUModal() {
        if (tuModal) tuModal.classList.add("hidden");
        pendingFileToUpload = null;
        // reset file inputs so the same file can be uploaded again
        if (fileInput) fileInput.value = "";
    }

    if (tuCancel) {
        tuCancel.addEventListener("click", closeTUModal);
    }

    if (tuClose) {
        tuClose.addEventListener("click", closeTUModal);
    }

    const GEMINI_SCHEMA = {
      type: "object",
      properties: {
        title_en: { type: "string" },
        title_ka: { type: "string" },
        model_name: { type: "string" },
        labor_time: { type: "string" },
        key_details_en: { type: "array", items: { type: "string" } },
        key_details_ka: { type: "array", items: { type: "string" } },
        parts: {
          type: "array",
          items: {
            type: "object",
            properties: {
              part_number: { type: "string" },
              description_en: { type: "string" },
              description_ka: { type: "string" },
              status: { type: "string" }
            },
            required: ["part_number", "description_en", "description_ka", "status"]
          }
        },
        steps: {
          type: "array",
          items: {
            type: "object",
            properties: {
              step_number: { type: "integer" },
              description_en: { type: "string" },
              description_ka: { type: "string" },
              warning_en: { type: "string" },
              warning_ka: { type: "string" }
            },
            required: ["step_number", "description_en", "description_ka"]
          }
        },
        special_tools: {
          type: "array",
          items: {
            type: "object",
            properties: {
              tool_number: { type: "string" },
              name_en: { type: "string" },
              name_ka: { type: "string" }
            },
            required: ["tool_number", "name_en", "name_ka"]
          }
        },
        fluid_capacities: {
          type: "array",
          items: {
            type: "object",
            properties: {
              name_en: { type: "string" },
              name_ka: { type: "string" },
              quantity: { type: "string" }
            },
            required: ["name_en", "name_ka", "quantity"]
          }
        }
      },
      required: ["title_en", "title_ka", "model_name", "labor_time", "parts", "steps", "special_tools", "fluid_capacities"]
    };

    const GWEN_SYSTEM_INSTRUCTION_FRONTEND = 
        "შენ ხარ Gwen AI (გვენი) — პრემიუმ კლასის, Porsche-ს სერვისის ჭკვიანი ხმოვანი და ტექნიკური ასისტენტი. " +
        "შენი მიზანია დაეხმარო Porsche-ს ავტორიზებულ მექანიკოსებსა და ტექნიკოსებს ავტომობილის დიაგნოსტირებასა და შეკეთებაში.\n\n" +
        "ძირითადი ქცევის წესები:\n" +
        "1. **პერსონაჟი:** ხარ პროფესიონალი, თავაზიანი, ტექნიკურად უზადოდ განათლებული და მეგობრული. საუბრობ დახვეწილი, ოფიციალური დილერის დონის ქართული საინჟინრო ენით.\n" +
        "2. **ლექსიკონი:** როდესაც ტექნიკოსი გეკითხება რაიმე ნაწილზე, განუმარტე მისი დანიშნულება, ოფიციალური ქართული სახელი და კატალოგის სექცია.\n" +
        "3. **ხმოვანი ფორმატი:** ვინაიდან შენი პასუხი ხმოვნად გაჟღერდება, პასუხები შეინარჩუნე მაქსიმალურად ლაკონიური და გასაგები. მოერიდე სპეციალურ სიმბოლოებს.";

    async function processLocalOllamaAnalysis(extracted_text, file_hash) {
        console.warn("FastAPI backend triggered fallback. Executing local Ollama structured analysis on client browser...");
        loadingStatusText.textContent = "ღრუბლოვანი API მიუწვდომელია. გააქტიურდა ლოკალური Ollama (Edge AI) ანალიზი...";
        
        const host = savedOllamaUrl || DEFAULT_OLLAMA_URL;
        const model = savedOllamaModel || "llama3";
        
        if (!model) {
            throw new Error("ლოკალური Ollama მოდელი არ არის შერჩეული. გთხოვთ, შეხვიდეთ პარამეტრებში (⚙️) და აირჩიოთ მოდელი.");
        }
        
        let text = extracted_text;
        if (text.length > 20000) {
            text = text.substring(0, 20000) + "\n... [Truncated to fit local context] ...";
        }
        
        const prompt = `You are an expert Master Service Technician and technical translator for Porsche and BMW Group.
Analyze the following repair instruction text, extract all key information, and return a highly structured JSON response in the specified schema.

JSON SCHEMA:
${JSON.stringify(GEMINI_SCHEMA, null, 2)}

Instructions:
1. Identify title (EN and translation in Georgian).
2. Identify specific vehicle/motorcycle model name (e.g. 'R 1300 GS', '911 Carrera S'). If not found, use 'Unknown Model'.
3. Format labor time strictly as 'X FRU'.
4. For parts without numbers, set part_number to 'N/A'.
5. Sequence step-by-step repair instruction steps focusing strictly on physical mechanical work (Disassembly, Main work, Reassembly). Keep timeline logical and focused (10-20 steps max). Translate using Georgian dealer-level automotive terminology.
6. Extract safety warnings or torque specs.
7. Extract special tools.

Repair Instruction Text:
${text}`;

        const payload = {
            model: model,
            messages: [
                {
                    role: "system",
                    content: "You are a precise technical translator. You must return valid JSON matching the requested schema."
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            stream: false,
            format: GEMINI_SCHEMA,
            options: {
                temperature: 0.1
            }
        };

        const ollamaRes = await fetch(`${host}/api/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!ollamaRes.ok) {
            throw new Error(`ლოკალურმა Ollama სერვერმა დააბრუნა შეცდომა: ${ollamaRes.statusText}`);
        }

        const ollamaData = await ollamaRes.json();
        const content = ollamaData.message.content;
        let parsedJSON = JSON.parse(content.trim());
        
        parsedJSON.model_name = `${model} (Local Edge AI)`;
        
        // Cache this result back to backend so future uploads hit cache immediately!
        try {
            fetch(`${savedApiUrl}/cache-local-analysis`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file_hash: file_hash, structured_data: parsedJSON })
            });
        } catch (cacheErr) {
            console.error("Failed to cache local analysis to backend:", cacheErr);
        }
        
        return parsedJSON;
    }

    async function callLocalOllamaChat(prompt) {
        console.warn("FastAPI backend triggered Gwen Chat fallback. Executing local Ollama chat on client browser...");
        const host = savedOllamaUrl || DEFAULT_OLLAMA_URL;
        const model = savedOllamaModel || "llama3";
        
        if (!model) {
            return "უკაცრავად, ლოკალური Ollama მოდელი არ არის შერჩეული. გთხოვთ, შეხვიდეთ პარამეტრებში (⚙️) და აირჩიოთ მოდელი.";
        }

        const payload = {
            model: model,
            messages: [
                {
                    role: "system",
                    content: GWEN_SYSTEM_INSTRUCTION_FRONTEND
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            stream: false,
            options: {
                temperature: 0.3
            }
        };

        const response = await fetch(`${host}/api/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`ლოკალურმა Ollama-მ დააბრუნა შეცდომა: ${response.statusText}`);
        }

        const data = await response.json();
        return data.message.content;
    }

    // ==========================================
    // DRAG AND DROP FILE HANDLERS
    // ==========================================

    // Click to select file
    dropZone.addEventListener("click", () => {
        fileInput.click();
    });

    // Keyboard access: drop zone is focusable (tabindex=0), Enter/Space opens the file picker
    dropZone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInput.click();
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            askForTUAndUpload(e.target.files[0]);
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
            askForTUAndUpload(e.dataTransfer.files[0]);
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

    function handleFileUpload(file, tu) {
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

        // Construct Request URL with query parameters
        let requestUrl = `${savedApiUrl}/analyze-instruction`;
        const queryParams = [];
        if (tu !== undefined && tu !== null) {
            queryParams.push(`tu=${tu}`);
        }
        if (bypassCacheInput && bypassCacheInput.checked) {
            queryParams.push("force_refresh=true");
        }
        if (queryParams.length > 0) {
            requestUrl += `?${queryParams.join("&")}`;
        }

        // Call FastAPI Backend (cache is used by default)
        fetch(requestUrl, {
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
            if (data && data.status === "fallback_to_local") {
                return processLocalOllamaAnalysis(data.extracted_text, data.file_hash);
            }
            return data;
        })
        .then(data => {
            // Override/Inject labor_time dynamically on frontend based on lastEnteredTU
            if (lastEnteredTU !== null) {
                const { minutes, timeStr } = calculateTUDuration(lastEnteredTU);
                data.labor_time = `${lastEnteredTU} TU (${timeStr})`;
            }
            
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

        // Calculate labor cost based on vehicle type and labor time
        let costHtml = "N/A";
        if (data.labor_time && data.labor_time !== "N/A") {
            const model = (data.model_name || "").toLowerCase();
            const titleEn = (data.title_en || "").toLowerCase();
            const titleKa = (data.title_ka || "").toLowerCase();
            
            let ratePerHour = 130;
            let vehicleLabel = "შიგაწვის ძრავი";
            let multiplierLabel = "130 ₾/სთ";
            
            if (
                model.includes("taycan") || 
                model.includes("electric") || 
                model.includes(" ev") || 
                model.endsWith("ev") ||
                titleEn.includes("taycan") ||
                titleEn.includes("electric") ||
                titleEn.includes("ev") ||
                titleKa.includes("ელექტრო") ||
                titleKa.includes("ტაიკანი")
            ) {
                ratePerHour = 200;
                vehicleLabel = "სრულიად ელექტრო";
                multiplierLabel = "200 ₾/სთ";
            } else if (
                model.includes("hybrid") || 
                model.includes("e-hybrid") || 
                model.includes("phev") || 
                model.includes("mhev") || 
                model.includes("ჰიბრიდ") ||
                titleEn.includes("hybrid") ||
                titleEn.includes("phev") ||
                titleEn.includes("mhev") ||
                titleKa.includes("ჰიბრიდ")
            ) {
                ratePerHour = 170;
                vehicleLabel = "ჰიბრიდი";
                multiplierLabel = "170 ₾/სთ";
            }
            
            // Extract hours from labor_time
            let hours = 0;
            if (lastEnteredTU !== null) {
                hours = lastEnteredTU / 100;
            } else {
                // Parse float from string like "2.5 Hours (სთ)" or "2.5 სთ" or "100 TU (1 სთ)"
                // Look for TU first
                const tuMatch = data.labor_time.match(/(\d+)\s*TU/i);
                if (tuMatch) {
                    hours = parseInt(tuMatch[1]) / 100;
                } else {
                    const hourMatch = data.labor_time.match(/([\d.]+)\s*(?:Hour|სთ|hrs|h)/i);
                    if (hourMatch) {
                        hours = parseFloat(hourMatch[1]);
                    } else {
                        const genericMatch = data.labor_time.match(/([\d.]+)/);
                        if (genericMatch) {
                            hours = parseFloat(genericMatch[1]);
                        }
                    }
                }
            }
            
            const totalCost = hours * ratePerHour;
            costHtml = `${Math.round(totalCost)} ₾ <span class="cost-subtext">${vehicleLabel} (${multiplierLabel})</span>`;
        }
        
        if (resLaborCost) {
            resLaborCost.innerHTML = costHtml;
        }
        
        // Set Titles
        resTitleKa.textContent = data.title_ka || "სარემონტო ინსტრუქცია";
        resTitleEn.textContent = `Original: ${data.title_en || "N/A"}`;

        // Set Vehicle Model and AI Engine
        if (resVehicleModel) {
            resVehicleModel.innerHTML = `<i class="fa-solid fa-car"></i> მოდელი: <strong>${data.model_name || "Unknown Model"}</strong>`;
        }
        if (resAiEngine) {
            const isLocal = data.model_name && data.model_name.includes("Local Edge AI");
            const engineName = isLocal ? data.model_name : "Cloud Gemini/Groq";
            resAiEngine.innerHTML = `<i class="fa-solid fa-robot"></i> Engine: ${engineName}`;
            if (isLocal) {
                resAiEngine.style.background = "rgba(136, 212, 19, 0.1)";
                resAiEngine.style.borderColor = "rgba(136, 212, 19, 0.3)";
                resAiEngine.style.color = "#88d413";
            } else {
                resAiEngine.style.background = "rgba(213, 0, 28, 0.1)";
                resAiEngine.style.borderColor = "rgba(213, 0, 28, 0.3)";
                resAiEngine.style.color = "#ff334b";
            }
        }

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

        // 5. Render Fluid Capacities
        const fluidsContainer = document.getElementById("fluids-container");
        if (fluidsContainer) {
            fluidsContainer.innerHTML = "";
            if (data.fluid_capacities && data.fluid_capacities.length > 0) {
                data.fluid_capacities.forEach(fluid => {
                    const formattedQty = (fluid.quantity || "")
                        .replace(/(\d+[\d,.]*)\s*l\b/gi, "$1 L")
                        .replace(/(\d+[\d,.]*)\s*ml\b/gi, "$1 mL")
                        .replace(/(\d+[\d,.]*)\s+([1il|/I])$/gi, "$1 L");
                    const row = document.createElement("div");
                    row.className = "fluid-row";
                    row.innerHTML = `
                        <div class="fluid-info">
                            <span class="fluid-name-ka">${fluid.name_ka}</span>
                            <span class="fluid-name-en">${fluid.name_en}</span>
                        </div>
                        <span class="fluid-quantity">${formattedQty}</span>
                    `;
                    fluidsContainer.appendChild(row);
                });
            } else {
                fluidsContainer.innerHTML = "<p class='no-data-card'>სითხეების მოცულობები მითითებული არ არის.</p>";
            }
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
    const handHour = document.getElementById("chrono-hand-hour");
    const handMinute = document.getElementById("chrono-hand-minute");
    const handSecond = document.getElementById("chrono-hand-second");

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

        // Hour hand moves 360 deg in 12 hours (30 deg per hour + 0.5 deg per minute for smooth sweep)
        if (handHour) {
            const hourDeg = ((hrs % 12) * 30) + (mins * 0.5);
            handHour.style.transform = `rotate(${hourDeg}deg)`;
        }

        // Minute hand moves 360 deg in 60 minutes
        if (handMinute) {
            const minDeg = ((mins + secs / 60) / 60) * 360;
            handMinute.style.transform = `rotate(${minDeg}deg)`;
        }

        // Clock hands analog sweep movement
        if (handSecond) {
            const secDeg = ((secs + ms / 1000) / 60) * 360;
            handSecond.style.transform = `rotate(${secDeg}deg)`;
        }

        requestAnimationFrame(updateLiveChrono);
    }
    
    // Initialize the ticking clock
    if (liveHms) {
        updateLiveChrono();
    }

    // Fetch live telemetry data on load: real key count, measured round-trip latency, backend status
    const healthFetchStart = performance.now();
    fetch(`${savedApiUrl}/health`)
    .then(res => res.json())
    .then(data => {
        const latencyMs = Math.round(performance.now() - healthFetchStart);
        const keyStatusElement = document.querySelector(".telemetry-item:nth-child(2) .telemetry-value");
        if (keyStatusElement && data.total_keys_count !== undefined) {
            const geminiCount = data.gemini_keys_count || 0;
            const groqCount = data.groq_keys_count || 0;
            const totalCount = data.total_keys_count || 0;
            keyStatusElement.innerHTML = `<span class="pulse-dot amber"></span> ${totalCount} KEYS OPERATIONAL`;
            keyStatusElement.setAttribute("title", `Gemini: ${geminiCount} გასაღები, Groq: ${groqCount} გასაღები`);
            keyStatusElement.style.cursor = "help";
        }
        const latencyElement = document.querySelector(".telemetry-item:nth-child(4) .telemetry-value");
        if (latencyElement) {
            const latencyClass = latencyMs < 500 ? "text-green" : (latencyMs < 1500 ? "text-amber" : "text-red");
            latencyElement.className = `telemetry-value ${latencyClass}`;
            latencyElement.textContent = `${latencyMs} ms / SECURE SSL`;
            latencyElement.setAttribute("title", "გაზომილი რეალური Round-Trip დრო ბექენდამდე");
        }
    })
    .catch(err => {
        console.warn("Failed to fetch live health telemetry:", err);
        // Reflect the outage honestly in the cockpit instead of showing a fake READY state
        const engineStatusElement = document.querySelector(".telemetry-item:nth-child(1) .telemetry-value");
        if (engineStatusElement) {
            engineStatusElement.className = "telemetry-value text-red";
            engineStatusElement.innerHTML = `<span class="pulse-dot red"></span> BACKEND OFFLINE`;
            engineStatusElement.setAttribute("title", "ბექენდი არ პასუხობს — ატვირთვა ვერ იმუშავებს, სანამ კავშირი აღდგება");
        }
        const latencyElement = document.querySelector(".telemetry-item:nth-child(4) .telemetry-value");
        if (latencyElement) {
            latencyElement.className = "telemetry-value text-red";
            latencyElement.textContent = "-- ms / NO LINK";
        }
    });

    // ==========================================
    // INTERACTIVE DEMO MODE DATA & CONTROLLER
    // ==========================================
    const demoCards = document.querySelectorAll(".demo-card");
    
    const DEMO_DATA = {
        gt3: {
            model_name: "Porsche 911 GT3 (992)",
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
            model_name: "Porsche Cayenne S (9YA)",
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
            model_name: "Porsche Taycan Turbo S",
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
            model_name: "BMW R 1200 GS",
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
                // Reset lastEnteredTU since we are loading demo data (which has pre-set hours)
                lastEnteredTU = null;
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
        // Voice synthesis disabled per user request
    }
    
    function initializeGWENVoice() {
        // Voice recognition disabled per user request
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
        
        // Command 6: Simple Greeting/Test (only matches short, non-question greetings)
        else if ((command === "gwen" || command === "გვენ" || command === "პივის" || command === "ჰელოუ" || command === "hello" || command === "გამარჯობა" || command.includes("გამარჯობა გვენ") || command === "gwen ai" || command === "გვენ ეიაი") && 
                 !command.includes("?") && 
                 !command.includes("რა") && !command.includes("სად") && !command.includes("როგორ") && !command.includes("რატომ")) {
            appendChatMessage("Gwen AI", "გისმენთ! მე ვარ **Gwen AI**, თქვენი კოკპიტის ასისტენტი. შემიძლია ჩავტვირთო სარემონტო ინსტრუქციები, წავიკითხო ნაბიჯები და დაჭერის ძალები.");
            speakText("გისმენთ! მე ვარ გვენ ეიაი, თქვენი კოკპიტის ასისტენტი. შემიძლია წავიკითხო სარემონტო ნაბიჯები და დაჭერის ძალები.");
        }
        
        // Unrecognized text entry: real-time Gwen AI Chat with technical glossary matching!
        else {
            // 1. Append loading / thinking bubble to the chat history
            const gwenHistory = document.getElementById("gwen-chat-history");
            const loadingBubble = document.createElement("div");
            loadingBubble.className = "chat-message gwen thinking-bubble";
            loadingBubble.innerHTML = `
                <span class="chat-sender">Gwen AI</span>
                <p class="chat-text"><i class="fa-solid fa-circle-notch fa-spin"></i> <em>ფიქრობს...</em></p>
            `;
            if (gwenHistory) {
                gwenHistory.appendChild(loadingBubble);
                gwenHistory.scrollTop = gwenHistory.scrollHeight;
            }
            
            // Prepare request headers with optional API Key from settings modal
            const headers = {
                "Content-Type": "application/json"
            };
            if (savedApiKey) {
                headers["X-Gemini-API-Key"] = savedApiKey;
            }
            
            // Call `/gwen-chat` backend route
            fetch(`${savedApiUrl}/gwen-chat`, {
                method: "POST",
                headers: headers,
                body: JSON.stringify({ query: command })
            })
            .then(res => {
                if (!res.ok) {
                    throw new Error("ქსელის ხარვეზი");
                }
                return res.json();
            })
            .then(data => {
                if (data && data.status === "fallback_to_local") {
                    return callLocalOllamaChat(data.prompt);
                }
                return data.response || "უკაცრავად, პასუხის მიღება ვერ მოხერხდა.";
            })
            .then(responseText => {
                // Remove loading bubble
                if (loadingBubble && loadingBubble.parentNode) {
                    loadingBubble.parentNode.removeChild(loadingBubble);
                }
                
                // Append real reply and trigger female voice synthesis
                appendChatMessage("Gwen AI", responseText);
                speakText(responseText);
            })
            .catch(err => {
                console.error("Gwen chat error:", err);
                // Clean up thinking bubble
                if (loadingBubble && loadingBubble.parentNode) {
                    loadingBubble.parentNode.removeChild(loadingBubble);
                }
                
                const errorResponse = "უკაცრავად, სერვერთან კავშირი დროებით გაწყდა. გთხოვთ შეამოწმოთ ინტერნეტი ან სცადოთ მოგვიანებით.";
                appendChatMessage("Gwen AI", errorResponse);
                speakText(errorResponse);
            });
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
    
    // Voice control event listeners disabled per user request

    // OBD-II Telemetry Simulator removed per user request
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
