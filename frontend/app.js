/**
 * app.js — Setu Frontend Application
 *
 * Handles:
 *  - Cinematic loading screen (KPRverse-inspired)
 *  - Ambient particle system
 *  - Hero section with scroll-triggered reveal animations
 *  - Chat interface (text + streaming response rendering)
 *  - Voice input/output via Web Speech API
 *  - Stadium map visualization (SVG, color-coded by crowd density)
 *  - Live simulation control panel (sliders, toggles, emergency)
 *  - Trace viewer panel
 *  - Fan profile selection
 *  - Accessibility mode toggle
 *  - Mobile responsive sidebar
 */

(function () {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  CONFIGURATION
  // ═══════════════════════════════════════════════════════════════════════

  const API_BASE = 'http://127.0.0.1:8000';
  let sessionId = 'session_' + Date.now().toString(36);

  // ═══════════════════════════════════════════════════════════════════════
  //  STATE
  // ═══════════════════════════════════════════════════════════════════════

  /** @type {Array<{id:string, name:string, location:{x:number,y:number}, crowd_density:number, wheelchair_accessible:boolean, status:string}>} */
  let gatesState = [];

  /** @type {{id:string, name:string, language:string, needs_wheelchair:boolean, location:{x:number,y:number}, description:string}} */
  let activeFan = {
    id: 'GUEST',
    name: 'Guest',
    language: 'en',
    needs_wheelchair: false,
    location: { x: 50, y: 50 },
    description: 'Default guest fan profile.',
  };

  const fanProfiles = [
    { id: 'FAN1', name: 'Maria', language: 'pt', needs_wheelchair: true, location: { x: 45, y: 20 }, description: 'Brazilian fan, wheelchair user, speaks Portuguese', emoji: '🇧🇷' },
    { id: 'FAN2', name: 'Raj', language: 'hi', needs_wheelchair: false, location: { x: 60, y: 40 }, description: 'Indian fan, speaks Hindi, first-time visitor', emoji: '🇮🇳' },
    { id: 'FAN3', name: 'Tom', language: 'en', needs_wheelchair: false, location: { x: 30, y: 70 }, description: 'American fan, speaks English', emoji: '🇺🇸' },
    { id: 'FAN4', name: 'Fatima', language: 'ar', needs_wheelchair: false, location: { x: 75, y: 55 }, description: 'Moroccan fan, speaks Arabic', emoji: '🇲🇦' },
  ];

  let isStreaming = false;
  let emergencyMode = false;
  let traces = [];
  let stadiumTemperature = 32; // °C — synced with backend

  // ═══════════════════════════════════════════════════════════════════════
  //  DOM REFERENCES
  // ═══════════════════════════════════════════════════════════════════════

  const $chatMessages = document.getElementById('chat-messages');
  const $welcomeScreen = document.getElementById('welcome-screen');
  const $chatInput = document.getElementById('chat-input');
  const $sendBtn = document.getElementById('send-btn');
  const $micBtn = document.getElementById('mic-btn');
  const $voiceStatus = document.getElementById('voice-status');
  const $languageSelect = document.getElementById('language-select');
  const $a11yToggle = document.getElementById('a11y-toggle');
  const $sidebarToggle = document.getElementById('sidebar-toggle');
  const $sidebar = document.getElementById('sidebar');
  const $fanCards = document.getElementById('fan-cards');
  const $gateSliders = document.getElementById('gate-sliders');
  const $gateToggles = document.getElementById('gate-toggles');
  const $emergencyBtn = document.getElementById('emergency-btn');
  const $emergencyOverlay = document.getElementById('emergency-overlay');
  const $emergencyMessage = document.getElementById('emergency-message');
  const $traceList = document.getElementById('trace-list');
  const $mapGates = document.getElementById('map-gates');
  const $mapRoute = document.getElementById('map-route');
  const $mapAmenities = document.getElementById('map-amenities');
  const $tempDisplay = document.getElementById('temp-display');
  const $tempValue = document.getElementById('temp-value');
  const $tempSlider = document.getElementById('temp-slider');
  const $tempSliderValue = document.getElementById('temp-slider-value');

  // Sidebar tab elements
  const sidebarTabs = document.querySelectorAll('.sidebar-tab');
  const tabPanels = {
    map: document.getElementById('panel-map'),
    control: document.getElementById('panel-control'),
    trace: document.getElementById('panel-trace'),
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  CINEMATIC LOADING SCREEN
  // ═══════════════════════════════════════════════════════════════════════

  const loaderOverlay = document.getElementById('loader-overlay');
  const loaderBar = document.getElementById('loader-bar');
  const loaderCounter = document.getElementById('loader-counter');
  const loaderStatus = document.getElementById('loader-status');
  const $appWrapper = document.getElementById('app-wrapper');
  const $heroSection = document.getElementById('hero-section');
  const $heroEnterBtn = document.getElementById('hero-enter-btn');
  const $appMain = document.getElementById('main-content');

  const LOADER_STATUSES = [
    'INITIALISING SYSTEMS...',
    'CONNECTING TO STADIUM NETWORK...',
    'LOADING GATE TELEMETRY...',
    'CALIBRATING AI AGENTS...',
    'BUILDING KNOWLEDGE BASE...',
    'SYNCING CROWD SENSORS...',
    'DEPLOYING SAFETY PROTOCOLS...',
    'ACTIVATING MULTILINGUAL ENGINE...',
    'RENDERING STADIUM MAP...',
    'SYSTEM READY.',
  ];

  function runLoader() {
    let progress = 0;
    const interval = setInterval(() => {
      // Accelerate: slow at start, fast at end
      const increment = progress < 30 ? 1 : progress < 70 ? 2 : progress < 90 ? 3 : 5;
      progress = Math.min(progress + increment, 100);

      loaderBar.style.width = progress + '%';
      loaderCounter.textContent = progress + '%';

      // Update status text at thresholds
      const statusIdx = Math.min(Math.floor(progress / 10), LOADER_STATUSES.length - 1);
      loaderStatus.textContent = LOADER_STATUSES[statusIdx];

      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          loaderOverlay.classList.add('hidden');
          $appWrapper.style.opacity = '1';
          // Trigger hero reveal animations
          setTimeout(revealHeroElements, 300);
        }, 400);
      }
    }, 40);
  }

  function revealHeroElements() {
    const elements = document.querySelectorAll('.anim-reveal');
    elements.forEach((el) => {
      const delay = parseInt(el.dataset.delay || 0);
      setTimeout(() => el.classList.add('revealed'), delay);
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  AMBIENT PARTICLE SYSTEM
  // ═══════════════════════════════════════════════════════════════════════

  function initParticles() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    const PARTICLE_COUNT = 60;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // Create particles
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 2 + 0.5,
        speedX: (Math.random() - 0.5) * 0.3,
        speedY: (Math.random() - 0.5) * 0.3,
        opacity: Math.random() * 0.5 + 0.1,
        // Colors: mix of blue, gold, green particles
        color: ['rgba(59,99,247,', 'rgba(251,191,36,', 'rgba(34,197,94,'][Math.floor(Math.random() * 3)],
      });
    }

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach((p) => {
        p.x += p.speedX;
        p.y += p.speedY;

        // Wrap around edges
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        // Subtle pulse
        p.opacity += (Math.random() - 0.5) * 0.01;
        p.opacity = Math.max(0.05, Math.min(0.5, p.opacity));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color + p.opacity + ')';
        ctx.fill();
      });

      // Draw connections between close particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(59,99,247,${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      requestAnimationFrame(animate);
    }
    animate();
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  HERO SECTION INTERACTIONS
  // ═══════════════════════════════════════════════════════════════════════

  function enterStadium() {
    // Fade out hero, show main chat interface
    $heroSection.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    $heroSection.style.opacity = '0';
    $heroSection.style.transform = 'translateY(-30px)';

    setTimeout(() => {
      $heroSection.style.display = 'none';
      $appMain.classList.add('active');
      // Ensure body allows main layout to fill
      document.querySelector('.app-wrapper').style.overflow = 'hidden';
    }, 600);
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  INITIALISATION
  // ═══════════════════════════════════════════════════════════════════════

  async function init() {
    // Start loader immediately
    runLoader();

    // Prepare app data in background
    renderFanCards();
    selectFan(fanProfiles[2]); // Default to Tom (English)
    await fetchGates();
    updateTemperatureDisplay();
    renderMap();
    renderControlPanel();
    bindEvents();
    fetchTraces();

    // Hero CTA button
    if ($heroEnterBtn) {
      $heroEnterBtn.addEventListener('click', enterStadium);
    }

    // Start live telemetry polling for real-time vibe
    setInterval(updateLiveTelemetry, 3000);
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  EVENT BINDING
  // ═══════════════════════════════════════════════════════════════════════

  function bindEvents() {
    // Send message
    $sendBtn.addEventListener('click', sendMessage);
    $chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    $chatInput.addEventListener('input', () => {
      $sendBtn.disabled = $chatInput.value.trim().length === 0 || isStreaming;
    });

    // Quick action buttons
    document.querySelectorAll('.quick-action-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        $chatInput.value = btn.dataset.query;
        $sendBtn.disabled = false;
        sendMessage();
      });
    });

    // Voice input
    $micBtn.addEventListener('click', toggleVoiceInput);

    // Language selector
    $languageSelect.addEventListener('change', () => {
      activeFan.language = $languageSelect.value;
    });

    // Accessibility toggle
    $a11yToggle.addEventListener('click', toggleAccessibility);

    // Sidebar toggle (mobile)
    $sidebarToggle.addEventListener('click', () => {
      $sidebar.classList.toggle('mobile-open');
    });

    // Sidebar close button (mobile)
    const $sidebarClose = document.getElementById('sidebar-close');
    if ($sidebarClose) {
      $sidebarClose.addEventListener('click', () => {
        $sidebar.classList.remove('mobile-open');
      });
    }

    // Dismiss sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 900) {
        if ($sidebar.classList.contains('mobile-open') && 
            !$sidebar.contains(e.target) && 
            !$sidebarToggle.contains(e.target)) {
          $sidebar.classList.remove('mobile-open');
        }
      }
    });

    // Sidebar tabs
    sidebarTabs.forEach((tab) => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Emergency button
    $emergencyBtn.addEventListener('click', triggerEmergency);

    // Temperature slider
    if ($tempSlider) {
      $tempSlider.addEventListener('input', (e) => {
        stadiumTemperature = parseInt(e.target.value);
        updateTemperatureDisplay();
        debouncedTempSync();
      });
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  CHAT — SEND & RECEIVE
  // ═══════════════════════════════════════════════════════════════════════

  async function sendMessage() {
    const query = $chatInput.value.trim();
    if (!query || isStreaming) return;

    // Hide welcome screen
    if ($welcomeScreen) $welcomeScreen.style.display = 'none';

    // Add user message
    appendMessage('user', query);
    $chatInput.value = '';
    $sendBtn.disabled = true;
    isStreaming = true;

    // Show typing indicator
    const typingEl = appendTyping();

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: emergencyMode ? '[EMERGENCY] ' + query : query,
          fan_profile: {
            name: activeFan.name,
            language: activeFan.language,
            needs_wheelchair: activeFan.needs_wheelchair,
            location: activeFan.location,
          },
          language: $languageSelect.value,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      // Remove typing indicator
      typingEl.remove();

      // Process NDJSON stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let assistantEl = null;
      let fullText = '';
      let traceData = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);

            if (chunk.type === 'trace') {
              traceData = chunk.trace;
            } else if (chunk.type === 'token') {
              if (!assistantEl) {
                assistantEl = appendMessage('assistant', '');
              }
              fullText += chunk.content;
              assistantEl.querySelector('.message-text').innerHTML = parseMarkdown(fullText);
              scrollToBottom();
            } else if (chunk.type === 'emergency') {
              showEmergencyOverlay(chunk.content);
              appendMessage('emergency', chunk.content);
              if (chunk.trace) traceData = chunk.trace;
            } else if (chunk.type === 'override') {
              // Output guardrail overrode the LLM response
              if (assistantEl) {
                fullText = chunk.content;
                assistantEl.querySelector('.message-text').innerHTML = parseMarkdown(fullText);
              }
            } else if (chunk.type === 'error') {
              appendMessage('assistant', chunk.content);
              if (chunk.trace) traceData = chunk.trace;
            } else if (chunk.type === 'done') {
              // Add latency badge
              if (assistantEl && chunk.latency_ms) {
                const badge = document.createElement('div');
                badge.className = 'trace-latency';
                badge.textContent = `⚡ ${Math.round(chunk.latency_ms)}ms`;
                badge.style.marginTop = '4px';
                assistantEl.querySelector('.message-content').appendChild(badge);
              }
            }
          } catch (parseErr) {
            // Skip unparseable lines
          }
        }
      }

      // Update trace viewer if we got trace data
      if (traceData) {
        addTrace(traceData, query, fullText);
      }

      // Speak the response (if voice output is supported)
      if (fullText) {
        speakResponse(fullText);
      }

      // Reset emergency mode after one query
      emergencyMode = false;

      // Refresh map (gate states may have changed)
      await fetchGates();
      renderMap();

    } catch (err) {
      typingEl.remove();
      appendMessage('assistant', `⚠️ Connection error: ${err.message}. Make sure the backend is running at ${API_BASE}.`);
    } finally {
      isStreaming = false;
      $sendBtn.disabled = $chatInput.value.trim().length === 0;
      scrollToBottom();
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  CHAT — DOM HELPERS
  // ═══════════════════════════════════════════════════════════════════════

  function appendMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    msg.setAttribute('role', 'article');

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = role === 'user' ? '👤' : role === 'emergency' ? '🚨' : '⚽';

    const content = document.createElement('div');
    content.className = 'message-content';

    const textEl = document.createElement('div');
    textEl.className = 'message-text';
    textEl.innerHTML = parseMarkdown(text);

    content.appendChild(textEl);
    msg.appendChild(avatar);
    msg.appendChild(content);
    $chatMessages.appendChild(msg);
    scrollToBottom();
    return msg;
  }

  function appendTyping() {
    const msg = document.createElement('div');
    msg.className = 'message assistant';
    msg.innerHTML = `
      <div class="message-avatar" aria-hidden="true">⚽</div>
      <div class="message-content">
        <div class="typing-indicator" aria-label="Setu is thinking">
          <span></span><span></span><span></span>
        </div>
      </div>`;
    $chatMessages.appendChild(msg);
    scrollToBottom();
    return msg;
  }

  function scrollToBottom() {
    $chatMessages.scrollTop = $chatMessages.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  VOICE INPUT / OUTPUT (Web Speech API)
  // ═══════════════════════════════════════════════════════════════════════

  let recognition = null;
  let isRecording = false;

  function toggleVoiceInput() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      $voiceStatus.textContent = 'Voice not supported in this browser';
      return;
    }

    if (isRecording) {
      stopRecording();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;

    // Map language code to BCP-47
    const langMap = { en: 'en-US', hi: 'hi-IN', es: 'es-ES', pt: 'pt-BR', fr: 'fr-FR', ar: 'ar-SA' };
    recognition.lang = langMap[$languageSelect.value] || 'en-US';

    recognition.onstart = () => {
      isRecording = true;
      $micBtn.classList.add('recording');
      $voiceStatus.textContent = '🔴 Listening...';
    };

    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      $chatInput.value = transcript;
      $sendBtn.disabled = transcript.trim().length === 0;
    };

    recognition.onend = () => {
      stopRecording();
      if ($chatInput.value.trim()) {
        sendMessage();
      }
    };

    recognition.onerror = (event) => {
      $voiceStatus.textContent = `Voice error: ${event.error}`;
      stopRecording();
    };

    recognition.start();
  }

  function stopRecording() {
    isRecording = false;
    $micBtn.classList.remove('recording');
    $voiceStatus.textContent = '';
    if (recognition) {
      recognition.stop();
      recognition = null;
    }
  }

  function speakResponse(text) {
    if (!('speechSynthesis' in window)) return;
    // Only speak short responses to avoid annoyance
    if (text.length > 500) return;

    const utterance = new SpeechSynthesisUtterance(text);
    const langMap = { en: 'en-US', hi: 'hi-IN', es: 'es-ES', pt: 'pt-BR', fr: 'fr-FR', ar: 'ar-SA' };
    utterance.lang = langMap[$languageSelect.value] || 'en-US';
    utterance.rate = 0.95;
    utterance.volume = 0.8;
    window.speechSynthesis.cancel(); // Cancel any ongoing speech
    window.speechSynthesis.speak(utterance);
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  STADIUM MAP (SVG)
  // ═══════════════════════════════════════════════════════════════════════

  async function fetchGates() {
    try {
      const res = await fetch(`${API_BASE}/gates`);
      if (res.ok) {
        const data = await res.json();
        gatesState = data.gates || [];
        // Sync temperature from backend
        if (data.temperature_c !== undefined) {
          stadiumTemperature = data.temperature_c;
          if ($tempSlider) $tempSlider.value = stadiumTemperature;
          updateTemperatureDisplay();
        }
      }
    } catch {
      // Use default empty — map will show nothing until backend is up
    }
  }

  function renderMap() {
    $mapGates.innerHTML = '';
    $mapRoute.innerHTML = '';

    gatesState.forEach((gate) => {
      const x = gate.location.x;
      const y = gate.location.y;
      const density = gate.crowd_density;
      const isOpen = gate.status === 'open';

      let color;
      if (!isOpen) {
        color = '#64748b'; // grey for closed
      } else if (density > 85) {
        color = 'var(--clr-crowd-high)';
      } else if (density > 50) {
        color = 'var(--clr-crowd-medium)';
      } else {
        color = 'var(--clr-crowd-low)';
      }

      // Gate circle (tactical player marker style)
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', x);
      circle.setAttribute('cy', y);
      circle.setAttribute('r', isOpen ? 3 : 2);
      circle.setAttribute('fill', color);
      circle.setAttribute('stroke', '#fff');
      circle.setAttribute('stroke-width', '0.4');
      circle.style.cursor = 'pointer';
      circle.style.transition = 'r 0.3s ease';

      if (isOpen) {
        const innerDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        innerDot.setAttribute('cx', x);
        innerDot.setAttribute('cy', y);
        innerDot.setAttribute('r', '0.6');
        innerDot.setAttribute('fill', '#fff');
        innerDot.style.pointerEvents = 'none';
        // Append it later so it stays on top of the circle
        setTimeout(() => $mapGates.appendChild(innerDot), 0);
      }

      // Pulse animation for high-density gates
      if (density > 85 && isOpen) {
        const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        pulse.setAttribute('cx', x);
        pulse.setAttribute('cy', y);
        pulse.setAttribute('r', 3);
        pulse.setAttribute('fill', 'none');
        pulse.setAttribute('stroke', color);
        pulse.setAttribute('stroke-width', '0.5');
        pulse.setAttribute('opacity', '0.6');
        pulse.innerHTML = `<animate attributeName="r" from="3" to="7" dur="1.5s" repeatCount="indefinite"/>
                           <animate attributeName="opacity" from="0.6" to="0" dur="1.5s" repeatCount="indefinite"/>`;
        $mapGates.appendChild(pulse);
      }

      // Wheelchair icon
      if (gate.wheelchair_accessible && isOpen) {
        const wc = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        wc.setAttribute('x', x + 4);
        wc.setAttribute('y', y - 2);
        wc.setAttribute('font-size', '3');
        wc.setAttribute('fill', '#4338ca');
        wc.textContent = '♿';
        $mapGates.appendChild(wc);
      }

      // Label
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', x);
      label.setAttribute('y', y - 4.5);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('font-size', '2.5');
      label.setAttribute('fill', 'var(--text-primary)');
      label.setAttribute('font-family', 'Inter, sans-serif');
      label.setAttribute('font-weight', '600');
      label.textContent = gate.name.replace(/Gate\s/, '').split('–')[0].trim();

      // Density badge
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      badge.setAttribute('x', x);
      badge.setAttribute('y', y + 6);
      badge.setAttribute('text-anchor', 'middle');
      badge.setAttribute('font-size', '2');
      badge.setAttribute('fill', color);
      badge.setAttribute('font-family', 'JetBrains Mono, monospace');
      badge.textContent = isOpen ? `${density}%` : 'CLOSED';

      // Tooltip on hover
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = `${gate.name}\nDensity: ${density}%\nAccessible: ${gate.wheelchair_accessible ? 'Yes' : 'No'}\nStatus: ${gate.status}`;
      circle.appendChild(title);

      $mapGates.appendChild(circle);
      $mapGates.appendChild(label);
      $mapGates.appendChild(badge);
    });

    // Draw fan location
    if (activeFan.location) {
      // Draw animated crowd flow / accessibility route lines to open gates
      gatesState.forEach((gate) => {
        if (gate.status === 'open') {
          if (activeFan.needs_wheelchair && !gate.wheelchair_accessible) return;

          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', activeFan.location.x);
          line.setAttribute('y1', activeFan.location.y);
          line.setAttribute('x2', gate.location.x);
          line.setAttribute('y2', gate.location.y);

          let routeColor = activeFan.needs_wheelchair ? '#0284c7' : 'rgba(34, 197, 94, 0.3)';
          line.setAttribute('stroke', routeColor);
          line.setAttribute('stroke-width', '0.4');
          line.setAttribute('stroke-dasharray', '2, 2');
          line.innerHTML = `<animate attributeName="stroke-dashoffset" values="20;0" dur="2s" repeatCount="indefinite"/>`;
          $mapRoute.appendChild(line);
        }
      });

      const fan = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      fan.innerHTML = `
        <circle cx="${activeFan.location.x}" cy="${activeFan.location.y}" r="2.5" fill="var(--clr-accent-secondary)" stroke="#fff" stroke-width="0.6"/>
        <circle cx="${activeFan.location.x}" cy="${activeFan.location.y}" r="2.5" fill="none" stroke="var(--clr-accent-secondary)" stroke-width="0.4" opacity="0.5">
          <animate attributeName="r" from="2.5" to="6" dur="2s" repeatCount="indefinite"/>
          <animate attributeName="opacity" from="0.5" to="0" dur="2s" repeatCount="indefinite"/>
        </circle>
        <text x="${activeFan.location.x}" y="${activeFan.location.y - 4}" text-anchor="middle" font-size="2.2" fill="var(--text-primary)" font-weight="700" font-family="Inter, sans-serif">📍 ${activeFan.name}</text>
      `;
      $mapGates.appendChild(fan);
    }
    updateLiveTelemetry();
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  CONTROL PANEL (live simulation)
  // ═══════════════════════════════════════════════════════════════════════

  function renderControlPanel() {
    $gateSliders.innerHTML = '';
    $gateToggles.innerHTML = '';

    gatesState.forEach((gate, idx) => {
      // Density slider
      const slider = document.createElement('div');
      slider.className = 'gate-control';
      slider.innerHTML = `
        <span class="gate-name">${gate.name.split('–')[0].trim()}</span>
        <input type="range" min="0" max="100" value="${gate.crowd_density}"
               aria-label="Crowd density for ${gate.name}"
               data-gate-idx="${idx}">
        <span class="density-value" style="color:${densityColor(gate.crowd_density)}">${gate.crowd_density}%</span>
      `;
      const rangeInput = slider.querySelector('input[type="range"]');
      const valueSpan = slider.querySelector('.density-value');
      rangeInput.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        gatesState[idx].crowd_density = val;
        valueSpan.textContent = val + '%';
        valueSpan.style.color = densityColor(val);
        renderMap();
        debouncedSync();
      });
      $gateSliders.appendChild(slider);

      // Open/close toggle
      const toggle = document.createElement('div');
      toggle.className = 'gate-control';
      toggle.innerHTML = `
        <span class="gate-name">${gate.name.split('–')[0].trim()}</span>
        <label class="toggle-switch">
          <input type="checkbox" ${gate.status === 'open' ? 'checked' : ''}
                 aria-label="Toggle ${gate.name} open/closed"
                 data-gate-idx="${idx}">
          <span class="slider"></span>
        </label>
        <span style="font-size:0.7rem;color:var(--text-muted)">${gate.status === 'open' ? 'Open' : 'Closed'}</span>
      `;
      const checkbox = toggle.querySelector('input[type="checkbox"]');
      const statusSpan = toggle.querySelector('span:last-child');
      checkbox.addEventListener('change', (e) => {
        gatesState[idx].status = e.target.checked ? 'open' : 'closed';
        statusSpan.textContent = e.target.checked ? 'Open' : 'Closed';
        renderMap();
        debouncedSync();
      });
      $gateToggles.appendChild(toggle);
    });
  }

  function densityColor(val) {
    if (val > 85) return '#ef4444';
    if (val > 50) return '#eab308';
    return '#22c55e';
  }

  /** Debounced sync to backend — waits 500ms after last change */
  let syncTimer = null;
  function debouncedSync() {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncGatesToBackend, 500);
  }

  async function syncGatesToBackend() {
    try {
      await fetch(`${API_BASE}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gates: gatesState }),
      });
    } catch {
      // Silently fail — demo mode
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  TEMPERATURE DISPLAY & SYNC
  // ═══════════════════════════════════════════════════════════════════════

  function updateTemperatureDisplay() {
    const t = stadiumTemperature;
    const label = `${t}°C`;

    // Update header pill
    if ($tempValue) $tempValue.textContent = label;

    // Update slider readout
    if ($tempSliderValue) {
      $tempSliderValue.textContent = label;
      $tempSliderValue.style.color = tempColor(t);
    }

    // Update header pill class for color-coding
    if ($tempDisplay) {
      $tempDisplay.classList.remove('heat-normal', 'heat-warning', 'heat-danger');
      if (t >= 42) {
        $tempDisplay.classList.add('heat-danger');
      } else if (t >= 35) {
        $tempDisplay.classList.add('heat-warning');
      } else {
        $tempDisplay.classList.add('heat-normal');
      }
    }
  }

  function tempColor(t) {
    if (t >= 42) return '#ef4444';
    if (t >= 35) return '#eab308';
    return '#22c55e';
  }

  /** Debounced temperature sync to backend */
  let tempSyncTimer = null;
  function debouncedTempSync() {
    clearTimeout(tempSyncTimer);
    tempSyncTimer = setTimeout(syncTempToBackend, 400);
  }

  async function syncTempToBackend() {
    try {
      await fetch(`${API_BASE}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temperature_c: stadiumTemperature }),
      });
    } catch {
      // Silently fail
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  EMERGENCY SIMULATION
  // ═══════════════════════════════════════════════════════════════════════

  function triggerEmergency() {
    emergencyMode = true;
    $emergencyBtn.textContent = '🚨 Emergency Mode ACTIVE — next query triggers protocol';
    $emergencyBtn.style.animation = 'pulse 1s infinite';
    // Also set all gates to high density to simulate
    gatesState.forEach((g) => {
      g.crowd_density = Math.min(g.crowd_density + 30, 100);
    });
    renderMap();
    renderControlPanel();
    syncGatesToBackend();
  }

  function showEmergencyOverlay(message) {
    $emergencyMessage.textContent = message;
    $emergencyOverlay.style.display = 'flex';
    // Auto-dismiss after 10 seconds
    setTimeout(() => {
      $emergencyOverlay.style.display = 'none';
    }, 10000);
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  FAN PROFILE SELECTOR
  // ═══════════════════════════════════════════════════════════════════════

  function renderFanCards() {
    $fanCards.innerHTML = '';
    fanProfiles.forEach((fan) => {
      const card = document.createElement('div');
      card.className = 'fan-card';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', `Select ${fan.name}'s profile`);
      card.dataset.fanId = fan.id;

      let badges = '';
      if (fan.needs_wheelchair) badges += '<span class="fan-badge wheelchair">♿ Wheelchair</span> ';
      const langNames = { pt: 'Portuguese', hi: 'Hindi', en: 'English', ar: 'Arabic', es: 'Spanish', fr: 'French' };
      badges += `<span class="fan-badge lang">${langNames[fan.language] || fan.language}</span>`;

      card.innerHTML = `
        <span class="fan-emoji">${fan.emoji}</span>
        <div class="fan-info">
          <div class="fan-name">${fan.name}</div>
          <div class="fan-desc">${fan.description}</div>
          <div style="margin-top:2px">${badges}</div>
        </div>
      `;

      card.addEventListener('click', () => selectFan(fan));
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectFan(fan);
        }
      });

      $fanCards.appendChild(card);
    });
  }

  function selectFan(fan) {
    activeFan = { ...fan };
    // Update language selector
    $languageSelect.value = fan.language;

    // Update card active state
    document.querySelectorAll('.fan-card').forEach((c) => {
      c.classList.toggle('active', c.dataset.fanId === fan.id);
    });

    renderMap();
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  SIDEBAR TABS
  // ═══════════════════════════════════════════════════════════════════════

  function switchTab(tabName) {
    sidebarTabs.forEach((t) => {
      t.classList.toggle('active', t.dataset.tab === tabName);
      t.setAttribute('aria-selected', t.dataset.tab === tabName ? 'true' : 'false');
    });

    Object.entries(tabPanels).forEach(([key, panel]) => {
      if (key === tabName) {
        panel.style.display = 'block';
        if (key === 'control') panel.classList.add('visible');
      } else {
        panel.style.display = 'none';
        if (key === 'control') panel.classList.remove('visible');
      }
    });

    // Refresh trace on tab switch
    if (tabName === 'trace') fetchTraces();
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  TRACE VIEWER
  // ═══════════════════════════════════════════════════════════════════════

  function addTrace(traceData, query, response) {
    const entry = {
      timestamp: new Date().toISOString(),
      query: query,
      ...traceData,
      response_preview: (response || '').substring(0, 100),
    };
    traces.unshift(entry);
    if (traces.length > 20) traces.pop();
    renderTraces();
  }

  async function fetchTraces() {
    try {
      const res = await fetch(`${API_BASE}/trace`);
      if (res.ok) {
        const data = await res.json();
        if (data.traces && data.traces.length > 0) {
          // Merge with local traces
          renderServerTraces(data.traces);
          return;
        }
      }
    } catch {
      // Use local traces only
    }
    renderTraces();
  }

  function renderTraces() {
    if (traces.length === 0) {
      $traceList.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;text-align:center;padding:var(--space-xl);">No traces yet. Send a message to see the agent pipeline trace.</p>';
      return;
    }
    $traceList.innerHTML = traces.map((t) => buildTraceHTML(t)).join('');
  }

  function renderServerTraces(serverTraces) {
    $traceList.innerHTML = serverTraces.map((t) => {
      const intent = t.router_output?.intent || 'unknown';
      const time = t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '';
      return `
        <div class="trace-entry">
          <div class="trace-header">
            <span class="trace-intent ${intent}">${intent}</span>
            <span class="trace-time">${time}</span>
          </div>
          <div style="font-size:0.7rem;color:var(--text-secondary);margin-bottom:4px;">
            "${(t.user_query || '').substring(0, 60)}${(t.user_query || '').length > 60 ? '...' : ''}"
          </div>
          <div class="trace-pipeline">
            <span class="trace-step">Router → ${intent}</span>
            <span class="trace-arrow">→</span>
            <span class="trace-step">Safety: ${t.safety_decision?.action || '?'}</span>
            <span class="trace-arrow">→</span>
            <span class="trace-step">Response</span>
          </div>
          <div class="trace-latency" style="margin-top:4px">⚡ ${Math.round(t.latency_ms || 0)}ms</div>
        </div>`;
    }).join('');
  }

  function buildTraceHTML(t) {
    const intent = t.router?.intent || 'unknown';
    const time = t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '';
    const safetyAction = t.safety?.action || '?';
    const ragUsed = t.rag_used ? `RAG (${t.rag_chunks} chunks)` : 'No RAG';
    const rerouted = t.safety?.rerouted ? '⚠️ Rerouted' : '';
    const vetoed = (t.safety?.gates_vetoed || []).join(', ');

    return `
      <div class="trace-entry">
        <div class="trace-header">
          <span class="trace-intent ${intent}">${intent}</span>
          <span class="trace-time">${time}</span>
        </div>
        <div style="font-size:0.7rem;color:var(--text-secondary);margin-bottom:4px;">
          "${(t.query || '').substring(0, 60)}${(t.query || '').length > 60 ? '...' : ''}"
        </div>
        <div class="trace-pipeline">
          <span class="trace-step">🤖 Router → ${intent}</span>
          <span class="trace-arrow">→</span>
          <span class="trace-step">🛡️ Safety: ${safetyAction}</span>
          ${rerouted ? `<span class="trace-step" style="color:var(--clr-warning)">${rerouted}</span>` : ''}
          <span class="trace-arrow">→</span>
          <span class="trace-step">📚 ${ragUsed}</span>
          <span class="trace-arrow">→</span>
          <span class="trace-step">💬 Response</span>
        </div>
        ${vetoed ? `<div style="font-size:0.65rem;color:var(--clr-danger);margin-top:2px;">Vetoed: ${vetoed}</div>` : ''}
        <div style="font-size:0.65rem;color:var(--text-muted);margin-top:2px;">${t.response_preview || ''}...</div>
      </div>`;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  ACCESSIBILITY
  // ═══════════════════════════════════════════════════════════════════════

  function toggleAccessibility() {
    document.body.classList.toggle('accessibility-mode');
    const isActive = document.body.classList.contains('accessibility-mode');
    $a11yToggle.setAttribute('aria-pressed', isActive);
    $a11yToggle.title = isActive ? 'Accessibility mode ON' : 'Accessibility mode OFF';
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  REAL-TIME TELEMETRY & MARKDOWN PARSING
  // ═══════════════════════════════════════════════════════════════════════

  function updateLiveTelemetry() {
    // 1. Calculate lowest density open gate
    let bestGate = null;
    let minDensity = Infinity;
    gatesState.forEach((gate) => {
      if (gate.status === 'open') {
        if (activeFan.needs_wheelchair && !gate.wheelchair_accessible) return;
        
        if (gate.crowd_density < minDensity) {
          minDensity = gate.crowd_density;
          bestGate = gate;
        }
      }
    });

    const $recommendValue = document.getElementById('telemetry-recommend');
    if ($recommendValue) {
      if (bestGate) {
        $recommendValue.textContent = `${bestGate.name.replace(/Gate\s/, '').split('–')[0].trim()} (${minDensity}%)`;
        $recommendValue.style.color = densityColor(minDensity);
      } else {
        $recommendValue.textContent = 'NONE (Closed)';
        $recommendValue.style.color = 'var(--clr-danger)';
      }
    }

    // 2. Randomly fluctuate attendance slightly to make it feel alive/real-time
    const $attendanceValue = document.getElementById('telemetry-attendance');
    if ($attendanceValue) {
      const baseAttendance = 68420;
      const variation = Math.floor(Math.sin(Date.now() / 5000) * 15) + Math.floor(Math.random() * 5);
      const currentAttendance = baseAttendance + variation;
      $attendanceValue.textContent = `${currentAttendance.toLocaleString()} / 72,000`;
    }

    // 3. Update thermal index status
    const $thermalValue = document.getElementById('telemetry-thermal');
    if ($thermalValue) {
      const t = stadiumTemperature;
      $thermalValue.textContent = t >= 42 ? '🚨 EXTREME HEAT' : t >= 35 ? '⚠️ HEAT WARNING' : '✅ NORMAL';
      $thermalValue.style.color = tempColor(t);
    }

    // 4. Update operational safety based on temperature and high density gates
    const $safetyValue = document.getElementById('telemetry-safety');
    if ($safetyValue) {
      const isExtremeHeat = stadiumTemperature >= 42;
      const anyVetoed = gatesState.some(g => g.status === 'open' && g.crowd_density > 85);
      if (isExtremeHeat) {
        $safetyValue.textContent = '🚨 RED ALERT';
        $safetyValue.style.color = 'var(--clr-danger)';
      } else if (anyVetoed || stadiumTemperature >= 35) {
        $safetyValue.textContent = '⚠️ WARN STATUS';
        $safetyValue.style.color = 'var(--clr-warning)';
      } else {
        $safetyValue.textContent = '✅ SECURE';
        $safetyValue.style.color = 'var(--clr-success)';
      }
    }
  }

  function parseMarkdown(text) {
    if (!text) return '';
    // 1. Escape HTML to prevent XSS
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

    // 2. Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 3. Italics: *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // 4. Inline code: `code`
    html = html.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>');

    // 5. Bullet points
    const lines = html.split('\n');
    let inList = false;
    const formattedLines = lines.map(line => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const itemText = trimmed.substring(2);
        if (!inList) {
          inList = true;
          return '<ul><li>' + itemText + '</li>';
        }
        return '<li>' + itemText + '</li>';
      } else {
        if (inList) {
          inList = false;
          return '</ul>' + line;
        }
        return line;
      }
    });
    if (inList) {
      formattedLines.push('</ul>');
    }
    html = formattedLines.join('<br>');

    // Clean up multiple <br> inside or after lists
    html = html.replace(/<\/ul><br>/g, '</ul>');
    html = html.replace(/<ul><br>/g, '<ul>');

    // 6. Links: [text](url)
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="chat-link">$1</a>');

    return html;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  BOOT
  // ═══════════════════════════════════════════════════════════════════════

  // Wait for DOM to be fully ready, then initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
